"""Email notifications for platform invitations."""
from __future__ import annotations

import html
import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from models import PlatformInvitation, User
from services.email_layout import email_shell, user_display
from services.resend_mail import EMAIL_ONLY_RE, normalize_email, send_resend_email

MULTI_WG_INVITE_SUBJECT = 'Invitation to join a Desirable Properties workgroup'


def build_multi_workgroup_invite_plain_body(
    *,
    invitee_name: str,
    body_text: str,
    links: List[dict],
) -> str:
    """Plain-text body for platform HTML email and client mailto."""
    name = (invitee_name or 'there').strip() or 'there'
    parts = [f'Hi {name},', '']
    text = (body_text or '').strip()
    if text:
        parts.append(text)
        parts.append('')
    parts.append('Join link(s):')
    for item in links or []:
        wg_name = (item.get('workgroup_name') or 'Workgroup').strip()
        url = (item.get('landing_url') or '').strip()
        if url:
            parts.append(f'- {wg_name}: {url}')
    parts.append('')
    parts.append('Use the same email address this message was sent to when signing in.')
    return '\n'.join(parts).strip() + '\n'


def build_multi_workgroup_invite_mailto(
    *,
    invitee_email: str,
    invitee_name: str,
    body_text: str,
    links: List[dict],
) -> Dict[str, str]:
    subject = MULTI_WG_INVITE_SUBJECT
    body = build_multi_workgroup_invite_plain_body(
        invitee_name=invitee_name,
        body_text=body_text,
        links=links,
    )
    to = normalize_email(invitee_email)
    mailto = f'mailto:{to}?subject={quote(subject)}&body={quote(body)}'
    return {
        'mailto': mailto,
        'subject': subject,
        'body': body,
        'to': to,
    }


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

    inviter_name = html.escape(user_display(inviter))
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
            '<strong>select the sentence(s)</strong> you want to edit in the text – '
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
    html_doc = email_shell(f'Invitation – {short_name}', body)
    return send_resend_email(
        to=[invitee_email.strip()],
        subject=f'Invitation: {short_name} on Gov Hub',
        html=html_doc,
    )


def send_multi_workgroup_invitation_email(
    *,
    inviter: User,
    invitee_email: str,
    invitee_name: str,
    body_text: str,
    links: list,
    bcc_inviter: Optional[bool] = None,
) -> bool:
    """Single email with custom body and one join link per workgroup.

    From display name uses the inviter profile; Reply-To is the inviter email.
    Optional BCC of the inviter (env WORKGROUP_INVITE_BCC_INVITER=0 to disable).
    """
    inviter_name = html.escape(user_display(inviter))
    name_esc = html.escape(invitee_name or 'there')
    note = (
        f'<p style="white-space:pre-wrap;line-height:1.6;">{html.escape(body_text.strip())}</p>'
        if body_text and body_text.strip()
        else ''
    )
    link_blocks = []
    for item in links or []:
        wg_name = html.escape(item.get('workgroup_name') or 'Workgroup')
        url = html.escape(item.get('landing_url') or '', quote=True)
        if not url:
            continue
        link_blocks.append(
            f'<p style="margin:12px 0;">'
            f'<strong>{wg_name}</strong><br>'
            f'<a href="{url}" style="display:inline-block;margin-top:6px;padding:8px 14px;'
            f'background:#667eea;color:#fff;text-decoration:none;border-radius:6px;">Join workgroup</a>'
            f'</p>',
        )
    links_html = ''.join(link_blocks) or '<p>Workgroup invitation links will be sent separately.</p>'
    sign_in_note = (
        '<p style="font-size:13px;color:#555;margin-top:16px;">'
        'Use the same email address this message was sent to when signing in to Gov Hub.</p>'
    )
    body = f"""
<p>Hi {name_esc},</p>
{note}
<p>{inviter_name} invited you to join workgroup(s) on Gov Hub:</p>
{links_html}
{sign_in_note}
"""
    html_doc = email_shell('Workgroup invitation', body)
    plain = build_multi_workgroup_invite_plain_body(
        invitee_name=invitee_name,
        body_text=body_text,
        links=links,
    )

    inviter_email = normalize_email(getattr(inviter, 'email', None))
    reply_to = inviter_email if EMAIL_ONLY_RE.match(inviter_email) else None
    if bcc_inviter is None:
        bcc_inviter = os.environ.get('WORKGROUP_INVITE_BCC_INVITER', '1').strip().lower() not in (
            '0', 'false', 'no', 'off',
        )
    bcc = [inviter_email] if (bcc_inviter and reply_to) else None

    return send_resend_email(
        to=[invitee_email.strip()],
        subject=MULTI_WG_INVITE_SUBJECT,
        html=html_doc,
        text=plain,
        from_display_name=user_display(inviter),
        reply_to=reply_to,
        bcc=bcc,
    )
