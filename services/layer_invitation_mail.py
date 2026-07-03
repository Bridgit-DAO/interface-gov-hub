"""Email notifications for layer membership invitations."""
from __future__ import annotations

import html
from typing import Optional

from models import Layer, User
from services.resend_mail import send_resend_email


def _public_base_url() -> str:
    from flask import current_app
    from config import PUBLIC_BASE_URL
    return (current_app.config.get('PUBLIC_BASE_URL') or PUBLIC_BASE_URL).rstrip('/')


def _display(user: Optional[User], fallback: str = 'A layer member') -> str:
    if not user:
        return fallback
    return user.displayName or user.name or user.username or fallback


def send_layer_invitation_email(
    *,
    invitation_token: str,
    layer: Layer,
    inviter: User,
    invitee_email: str,
    message: Optional[str] = None,
) -> bool:
    accept_url = f"{_public_base_url()}/layer/invite/{invitation_token}/"
    layer_name = html.escape(layer.name or 'this layer')
    inviter_name = html.escape(_display(inviter))
    note = ''
    if message and message.strip():
        note = (
            f'<p style="background:#f4f4f8;padding:12px;border-radius:8px;">'
            f'<em>{html.escape(message.strip())}</em></p>'
        )
    body = f"""
<p>{inviter_name} invited you to join <strong>{layer_name}</strong> on Gov Hub.</p>
{note}
<p><a href="{html.escape(accept_url, quote=True)}" style="display:inline-block;padding:10px 18px;background:#667eea;color:#fff;text-decoration:none;border-radius:6px;">Accept invitation</a></p>
<p style="font-size:13px;color:#666;">Or copy this link:<br><code>{html.escape(accept_url)}</code></p>
"""
    html_doc = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.5;color:#222;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#667eea;margin-top:0;">Layer invitation</h2>
{body}
<p style="font-size:12px;color:#888;margin-top:32px;">Gov Hub · Interface Governance Hub</p>
</body></html>"""
    return send_resend_email(
        to=[invitee_email.strip()],
        subject=f'Invitation to join {layer.name or "a layer"} on Gov Hub',
        html=html_doc,
    )
