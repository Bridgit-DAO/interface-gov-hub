"""Email + in-app notifications for workgroup position nominations."""
from __future__ import annotations

import html
import secrets
from datetime import datetime, timedelta
from typing import Optional

from extensions import db
from models import Layer, User, UserNotification, Workgroup, WorkingGroupChair
from services.resend_mail import send_resend_email
from services.workgroup_positions import position_label


def _public_base_url() -> str:
    from flask import current_app
    from config import PUBLIC_BASE_URL
    return (current_app.config.get('PUBLIC_BASE_URL') or PUBLIC_BASE_URL).rstrip('/')


def _user_display(user: Optional[User], fallback: str = 'Someone') -> str:
    if not user:
        return fallback
    return user.displayName or user.name or user.username or fallback


def _email_shell(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.5;color:#222;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#667eea;margin-top:0;">{html.escape(title)}</h2>
{body_html}
<p style="font-size:12px;color:#888;margin-top:32px;">Gov Hub · Interface Governance Hub</p>
</body></html>"""


def ensure_nominee_token(nomination: WorkingGroupChair, days: int = 30) -> str:
    if not nomination.nominee_response_token:
        nomination.nominee_response_token = secrets.token_urlsafe(32)[:64]
        nomination.nominee_token_expires_at = datetime.utcnow() + timedelta(days=days)
    return nomination.nominee_response_token


def nomination_respond_url(nomination: WorkingGroupChair) -> str:
    token = ensure_nominee_token(nomination)
    return f"{_public_base_url()}/nomination/respond/{token}/"


def _workgroup_context(nomination: WorkingGroupChair):
    wg = Workgroup.query.filter_by(acronym=nomination.group_acronym).first()
    layer = Layer.query.get(wg.layer_id) if wg and wg.layer_id else None
    return wg, layer


def _notify_in_app(user_id: str, title: str, body: str, link_url: str):
    db.session.add(
        UserNotification(
            user_id=user_id,
            title=title[:255],
            body=body,
            link_url=link_url[:500],
        )
    )


def send_nomination_submitted(nomination: WorkingGroupChair):
    """Email nominee (if not self-nom) and always notify nominator."""
    wg, layer = _workgroup_context(nomination)
    if not wg:
        return

    nominator = User.query.get(nomination.nominated_by_user_id) if nomination.nominated_by_user_id else None
    nominee_user = User.query.get(nomination.user_id) if nomination.user_id else None
    pos_label = position_label(nomination.position_key or 'chair')
    wg_name = wg.name or nomination.group_acronym
    layer_name = layer.name if layer else 'Gov Hub'
    nominator_name = _user_display(nominator, 'A community member')
    statement = html.escape(nomination.statement or '').replace('\n', '<br>')
    respond_url = nomination_respond_url(nomination)
    wg_url = f"{_public_base_url()}/workgroups/{wg.slug}/"

    if nomination.is_self_nomination:
        confirm_body = f"""
<p>You nominated yourself for <strong>{html.escape(pos_label)}</strong> in <strong>{html.escape(wg_name)}</strong> ({html.escape(layer_name)}).</p>
<p>Your nomination is pending review by layer administrators. You will be notified when it is approved or rejected.</p>
<p><strong>Your statement:</strong></p>
<blockquote style="border-left:3px solid #667eea;margin:12px 0;padding:8px 16px;color:#444;">{statement}</blockquote>
<p><a href="{html.escape(wg_url)}" style="color:#667eea;">View workgroup</a></p>
"""
        if nominator and nominator.email:
            send_resend_email(
                to=[nominator.email.strip()],
                subject=f'Your {pos_label} nomination was submitted — {wg_name}',
                html=_email_shell('Nomination submitted', confirm_body),
            )
        return

    nominee_body = f"""
<p><strong>{html.escape(nominator_name)}</strong> nominated you for <strong>{html.escape(pos_label)}</strong> in the workgroup <strong>{html.escape(wg_name)}</strong> on {html.escape(layer_name)}.</p>
<p><strong>Statement:</strong></p>
<blockquote style="border-left:3px solid #667eea;margin:12px 0;padding:8px 16px;color:#444;">{statement}</blockquote>
<p>Please review this nomination and let us know if you accept or decline.</p>
<p style="margin:24px 0;">
  <a href="{html.escape(respond_url)}" style="background:#667eea;color:#fff;padding:12px 20px;border-radius:8px;text-decoration:none;font-weight:600;">Review nomination</a>
</p>
<p style="font-size:13px;color:#666;">Accepting does not appoint you yet — layer administrators still review all nominations.</p>
"""
    if nomination.nominee_email:
        send_resend_email(
            to=[nomination.nominee_email.strip()],
            subject=f'You were nominated as {pos_label} — {wg_name}',
            html=_email_shell('Workgroup nomination', nominee_body),
        )

    if nominee_user:
        _notify_in_app(
            nominee_user.id,
            f'Nominated as {pos_label}',
            f'{nominator_name} nominated you for {pos_label} in {wg_name}. Review and accept or decline.',
            respond_url,
        )

    nominator_body = f"""
<p>Your nomination of <strong>{html.escape(nomination.chair_name or '')}</strong> for <strong>{html.escape(pos_label)}</strong> in <strong>{html.escape(wg_name)}</strong> was sent.</p>
<p>We emailed <strong>{html.escape(nomination.nominee_email or '')}</strong> with your statement and a link to accept or decline. You will be notified when they respond.</p>
<p><strong>Statement you submitted:</strong></p>
<blockquote style="border-left:3px solid #667eea;margin:12px 0;padding:8px 16px;color:#444;">{statement}</blockquote>
"""
    if nominator and nominator.email:
        send_resend_email(
            to=[nominator.email.strip()],
            subject=f'Nomination sent — {nomination.chair_name} for {pos_label}',
            html=_email_shell('Nomination sent', nominator_body),
        )


def send_nominee_accepted(nomination: WorkingGroupChair):
    wg, _ = _workgroup_context(nomination)
    nominator = User.query.get(nomination.nominated_by_user_id) if nomination.nominated_by_user_id else None
    pos_label = position_label(nomination.position_key or 'chair')
    wg_name = wg.name if wg else nomination.group_acronym
    nominee_name = nomination.chair_name or 'The nominee'

    body = f"""
<p><strong>{html.escape(nominee_name)}</strong> accepted your nomination for <strong>{html.escape(pos_label)}</strong> in <strong>{html.escape(wg_name)}</strong>.</p>
<p>The nomination is now pending approval by layer administrators.</p>
"""
    if nominator and nominator.email:
        send_resend_email(
            to=[nominator.email.strip()],
            subject=f'{nominee_name} accepted your nomination',
            html=_email_shell('Nominee accepted', body),
        )
    if nominator:
        _notify_in_app(
            nominator.id,
            f'{nominee_name} accepted nomination',
            f'They accepted your {pos_label} nomination in {wg_name}. Pending admin approval.',
            f"{_public_base_url()}/workgroups/{wg.slug}/" if wg else '/',
        )


def send_nominee_declined(nomination: WorkingGroupChair):
    wg, _ = _workgroup_context(nomination)
    nominator = User.query.get(nomination.nominated_by_user_id) if nomination.nominated_by_user_id else None
    pos_label = position_label(nomination.position_key or 'chair')
    wg_name = wg.name if wg else nomination.group_acronym
    nominee_name = nomination.chair_name or 'The nominee'
    reason = html.escape(nomination.nominee_decline_reason or 'No reason given').replace('\n', '<br>')

    body = f"""
<p><strong>{html.escape(nominee_name)}</strong> declined your nomination for <strong>{html.escape(pos_label)}</strong> in <strong>{html.escape(wg_name)}</strong>.</p>
<p><strong>Reason:</strong> {reason}</p>
<p>You may nominate someone else for this position.</p>
"""
    if nominator and nominator.email:
        send_resend_email(
            to=[nominator.email.strip()],
            subject=f'{nominee_name} declined your nomination',
            html=_email_shell('Nominee declined', body),
        )
    if nominator:
        _notify_in_app(
            nominator.id,
            f'{nominee_name} declined nomination',
            f'They declined your {pos_label} nomination in {wg_name}.',
            f"{_public_base_url()}/workgroups/{wg.slug}/" if wg else '/',
        )


def send_admin_decision(nomination: WorkingGroupChair, approved: bool):
    wg, _ = _workgroup_context(nomination)
    nominator = User.query.get(nomination.nominated_by_user_id) if nomination.nominated_by_user_id else None
    pos_label = position_label(nomination.position_key or 'chair')
    wg_name = wg.name if wg else nomination.group_acronym
    wg_url = f"{_public_base_url()}/workgroups/{wg.slug}/" if wg else _public_base_url()

    if approved:
        subject = f'Nomination approved — {pos_label} in {wg_name}'
        body_nominee = f'<p>Your nomination for <strong>{html.escape(pos_label)}</strong> in <strong>{html.escape(wg_name)}</strong> was approved.</p><p><a href="{html.escape(wg_url)}">View workgroup</a></p>'
        body_nominator = f'<p>The nomination of <strong>{html.escape(nomination.chair_name or "")}</strong> for <strong>{html.escape(pos_label)}</strong> in <strong>{html.escape(wg_name)}</strong> was approved.</p>'
    else:
        subject = f'Nomination not approved — {pos_label} in {wg_name}'
        body_nominee = f'<p>Your nomination for <strong>{html.escape(pos_label)}</strong> in <strong>{html.escape(wg_name)}</strong> was not approved by administrators.</p>'
        body_nominator = f'<p>The nomination of <strong>{html.escape(nomination.chair_name or "")}</strong> for <strong>{html.escape(pos_label)}</strong> in <strong>{html.escape(wg_name)}</strong> was not approved.</p>'

    if nomination.nominee_email:
        send_resend_email(to=[nomination.nominee_email.strip()], subject=subject, html=_email_shell(subject, body_nominee))
    if nominator and nominator.email:
        send_resend_email(to=[nominator.email.strip()], subject=subject, html=_email_shell(subject, body_nominator))
