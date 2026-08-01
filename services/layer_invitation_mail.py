"""Email notifications for layer membership invitations."""
from __future__ import annotations

import html
from typing import Optional

from models import Layer, User
from services.email_layout import email_shell, user_display
from services.public_urls import public_base_url
from services.resend_mail import send_resend_email


def send_layer_invitation_email(
    *,
    invitation_token: str,
    layer: Layer,
    inviter: User,
    invitee_email: str,
    message: Optional[str] = None,
) -> bool:
    accept_url = f"{public_base_url()}/layer/invite/{invitation_token}/"
    layer_name = html.escape(layer.name or 'this layer')
    inviter_name = html.escape(user_display(inviter, 'A layer member'))
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
    html_doc = email_shell('Layer invitation', body)
    return send_resend_email(
        to=[invitee_email.strip()],
        subject=f'Invitation to join {layer.name or "a layer"} on Gov Hub',
        html=html_doc,
    )
