"""CLI: batch-send notification digest emails (daily / weekly)."""
from datetime import datetime, timedelta

from sqlalchemy import or_


def register_notification_digest_cli(app):
    @app.cli.command('notification-digest')
    def notification_digest_command():
        """Email batched user_notification rows for users with email_digest_mode daily or weekly."""
        from extensions import db
        from models import User, UserNotification
        from services.resend_mail import send_resend_email
        from config import PUBLIC_BASE_URL, resolved_public_base_url

        now = datetime.utcnow()
        daily_cutoff = now - timedelta(days=1)
        weekly_cutoff = now - timedelta(days=7)

        users = User.query.filter(
            User.email_notifications_opt_in.is_(True),
            or_(User.email_digest_mode == 'daily', User.email_digest_mode == 'weekly'),
        ).all()

        base = resolved_public_base_url(PUBLIC_BASE_URL)
        sent = 0
        from services.document_follow_notifications import ensure_notification_unsubscribe_token

        for user in users:
            if not (user.email or '').strip():
                continue
            cutoff = weekly_cutoff if (user.email_digest_mode or '').lower() == 'weekly' else daily_cutoff
            pending = (
                UserNotification.query.filter_by(user_id=user.id)
                .filter(UserNotification.created_at >= cutoff)
                .filter(UserNotification.email_sent_at.is_(None))
                .order_by(UserNotification.created_at.asc())
                .limit(50)
                .all()
            )
            if not pending:
                continue
            ensure_notification_unsubscribe_token(user)
            db.session.commit()
            lines = []
            for n in pending:
                link = n.link_url or base
                lines.append(f"<li><strong>{n.title}</strong> – <a href=\"{link}\">open</a><br/><span style=\"color:#666\">{n.body or ''}</span></li>")
            tok = user.notification_unsubscribe_token or ''
            unsub = f"{base}/notifications/email/unsubscribe/{tok}" if tok else base
            html = f"""<p>Your Gov Hub notification digest ({user.email_digest_mode}):</p>
<ul>{''.join(lines)}</ul>
<p style="font-size:12px;color:#666;"><a href="{unsub}">Unsubscribe from these emails</a></p>"""
            ok = send_resend_email(
                to=[user.email.strip()],
                subject=f'Gov Hub digest ({len(pending)} updates)',
                html=html,
                list_unsubscribe_url=unsub if tok else None,
            )
            if ok:
                for n in pending:
                    n.email_sent_at = now
                db.session.commit()
                sent += 1

        print(f"notification-digest: sent to {sent} user(s)")
