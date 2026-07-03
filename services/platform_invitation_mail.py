"""Email notifications for platform invitations."""
from __future__ import annotations

import html
import json
from typing import Any, Dict, Optional

from models import PlatformInvitation, User
from services.resend_mail import send_resend_email


def _public_base_url() -> str:
    from flask import current_app
    from config import PUBLIC_BASE_URL
    return (current_app.config.get('PUBLIC_BASE_URL') or PUBLIC_BASE_URL).rstrip('/')


def _display(user: Optional[User], fallback: str = 'Someone') -> str:
    if not user:
        return fallback
    return user.displayName or user.name or user.username or fallback


def _passage_excerpt(target: Dict[str, Any]) -> str:
    """Quoted passage for edit_document_passage emails."""
    if not isinstance(target, dict):
        return ''
    anchor = target.get('context_anchor')
    if not isinstance(anchor, dict):
        return ''
    text_quote = anchor.get('textQuote')
    if not isinstance(text_quote, dict):
        return ''
    exact = (text_quote.get('exact') or '').strip()
    if not exact:
        return ''
    if len(exact) > 400:
        return exact[:397] + '…'
    return exact


def _invite_labels(invite_type: str) -> tuple[str, str]:
    labels = {
        'participate_dp': ('DP Challenge', 'join the DP Challenge and propose edits on Desirable Property drafts'),
        'edit_document': ('a document', 'review the document and suggest edits'),
        'edit_document_passage': ('a passage', 'propose an edit on a specific passage'),
        'review_document': ('a document', 'review this document'),
        'join_workgroup': ('a workgroup', 'join this workgroup'),
    }
    return labels.get(invite_type, ('Gov Hub', 'participate on Gov Hub'))


def send_platform_invitation_email(
    *,
    invitation: PlatformInvitation,
    inviter: User,
    invitee_email: str,
    landing_url: str,
    target_title: str,
) -> bool:
    try:
        target = json.loads(invitation.target_json or '{}')
    except json.JSONDecodeError:
        target = {}
    short_name, action_phrase = _invite_labels(invitation.invite_type)
    if target_title:
        short_name = target_title

    inviter_name = html.escape(_display(inviter))
    title_esc = html.escape(short_name)
    accept_url = html.escape(landing_url, quote=True)
    note = ''
    if invitation.message and invitation.message.strip():
        note = (
            f'<p style="background:#f4f4f8;padding:12px;border-radius:8px;">'
            f'<em>{html.escape(invitation.message.strip())}</em></p>'
        )
    passage_block = ''
    if invitation.invite_type == 'edit_document_passage':
        excerpt = _passage_excerpt(target)
        if excerpt:
            passage_block = (
                '<p style="margin:16px 0 8px;font-weight:600;">Passage to edit:</p>'
                f'<blockquote style="margin:0 0 16px;padding:12px 16px;border-left:4px solid #667eea;'
                f'background:#f4f4f8;font-size:15px;line-height:1.5;">'
                f'{html.escape(excerpt)}</blockquote>'
            )
    elif invitation.invite_type == 'edit_document':
        passage_block = (
            '<p style="margin:16px 0 8px;line-height:1.5;">'
            'You will open this document on Gov Hub. To suggest a change, '
            '<strong>select the sentence(s)</strong> you want to edit in the text — '
            'a compose panel will open automatically.</p>'
        )
    sign_in_note = (
        '<p style="font-size:13px;color:#555;margin-top:16px;">'
        'When you open the link, accept the invitation in the welcome dialog. '
        'If you are not signed in, use <strong>Google</strong> or <strong>email</strong> with the same address '
        'this invitation was sent to (not wallet sign-in).</p>'
    )
    body = f"""
<p>{inviter_name} invited you to {html.escape(action_phrase)} on <strong>{title_esc}</strong> on Gov Hub.</p>
{passage_block}
{note}
<p><a href="{accept_url}" style="display:inline-block;padding:10px 18px;background:#667eea;color:#fff;text-decoration:none;border-radius:6px;">Open invitation</a></p>
{sign_in_note}
<p style="font-size:13px;color:#666;">Or copy this link:<br><code>{accept_url}</code></p>
"""
    html_doc = f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.5;color:#222;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#667eea;margin-top:0;">Invitation — {html.escape(short_name)}</h2>
{body}
<p style="font-size:12px;color:#888;margin-top:32px;">Gov Hub · Interface Governance Hub</p>
</body></html>"""
    return send_resend_email(
        to=[invitee_email.strip()],
        subject=f'Invitation: {short_name} on Gov Hub',
        html=html_doc,
    )
