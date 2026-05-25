"""
Dispatch in-app UserNotification + optional Resend for users subscribed to this EventLog type + subject.

Subscriptions live in UserEventSubscription (event_type × subject_type/subject_id × channels).
"""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import or_

from extensions import db
from models import EmailUnsubscribe, EventLog, Submission, User, UserEventSubscription, UserNotification


def ensure_notification_unsubscribe_token(user: User) -> str:
    if not user.notification_unsubscribe_token:
        user.notification_unsubscribe_token = secrets.token_urlsafe(32)[:64]
    return user.notification_unsubscribe_token


def draft_key_for_submission(submission: Submission) -> str:
    if getattr(submission, 'is_revision', False) and getattr(submission, 'parent_draft_name', None):
        return submission.parent_draft_name
    return submission.draft_name or submission.id


def resolve_layer_id_for_draft(draft_name: str) -> Optional[str]:
    row = (
        Submission.query.filter(
            or_(
                Submission.draft_name == draft_name,
                Submission.id == draft_name,
                Submission.parent_draft_name == draft_name,
            ),
            Submission.status == 'approved',
            Submission.layer_id.isnot(None),
        )
        .order_by(Submission.submitted_at.desc())
        .first()
    )
    return str(row.layer_id) if row else None


def _is_layer_email_unsubscribed(layer_id: Optional[str], user: User) -> bool:
    if not layer_id:
        return False
    q = EmailUnsubscribe.query.filter_by(layer_id=layer_id)
    if user.email:
        hit = q.filter(
            or_(EmailUnsubscribe.user_id == user.id, EmailUnsubscribe.email == user.email)
        ).first()
    else:
        hit = q.filter_by(user_id=user.id).first()
    return hit is not None


def get_subscribed_users_for_draft_event(
    draft_name: str,
    event_type: str,
) -> List[Tuple[User, UserEventSubscription]]:
    out: List[Tuple[User, UserEventSubscription]] = []
    q = UserEventSubscription.query.filter_by(
        event_type=event_type,
        subject_type='draft',
        subject_id=draft_name,
    )
    for sub in q.all():
        user = User.query.get(sub.user_id)
        if user:
            out.append((user, sub))
    return out


def dispatch_document_followers(
    *,
    draft_name: str,
    event_type: str,
    event_log: Optional[EventLog],
    actor_user_id: Optional[str],
    title: str,
    body: str,
    link_path: str,
) -> None:
    """After caller's transaction commit: notify subscribers matching event_type + draft subject."""
    from flask import current_app

    from config import PUBLIC_BASE_URL
    from services.resend_mail import send_resend_email

    layer_id = resolve_layer_id_for_draft(draft_name)
    base = (current_app.config.get('PUBLIC_BASE_URL') or PUBLIC_BASE_URL).rstrip('/')
    full_link = f"{base}{link_path}" if link_path.startswith('/') else f"{base}/{link_path}"
    ev_id = event_log.id if event_log else None

    recipients_in_app: List[Tuple[User, UserEventSubscription]] = []
    for user, sub in get_subscribed_users_for_draft_event(draft_name, event_type):
        if actor_user_id and str(user.id) == str(actor_user_id):
            continue
        if _is_layer_email_unsubscribed(layer_id, user):
            continue
        if sub.deliver_in_app:
            db.session.add(
                UserNotification(
                    user_id=user.id,
                    event_log_id=ev_id,
                    title=title[:255],
                    body=body,
                    link_url=full_link[:500],
                )
            )
            recipients_in_app.append((user, sub))

    db.session.commit()

    for user, sub in recipients_in_app:
        if not sub.deliver_email:
            continue
        if not user.email_notifications_opt_in or not (user.email or '').strip():
            continue
        mode = (user.email_digest_mode or 'immediate').lower()
        if mode in ('daily', 'weekly', 'off'):
            continue

        ensure_notification_unsubscribe_token(user)
        db.session.commit()

        unsub = f"{base}/notifications/email/unsubscribe/{user.notification_unsubscribe_token}"
        subject = title[:200]
        canopi_url = (current_app.config.get('CANOPI_PUBLIC_URL') or '').strip()
        canopi_line = ""
        if canopi_url:
            canopi_line = (
                f'<p style="font-size:13px;color:#444;">Discuss on the page with '
                f'<a href="{canopi_url}">Canopi</a> (annotations and presence).</p>'
            )
        html = f"""<p>{body}</p>
<p><a href="{full_link}">Open in Gov Hub</a></p>
{canopi_line}
<p style="font-size:12px;color:#666;"><a href="{unsub}">Unsubscribe from these emails</a></p>"""
        ok = send_resend_email(
            to=[user.email.strip()],
            subject=subject,
            html=html,
            list_unsubscribe_url=unsub,
        )
        if ok:
            n = (
                UserNotification.query.filter_by(user_id=user.id, event_log_id=ev_id)
                .order_by(UserNotification.created_at.desc())
                .first()
            )
            if n:
                n.email_sent_at = datetime.utcnow()
                db.session.commit()
