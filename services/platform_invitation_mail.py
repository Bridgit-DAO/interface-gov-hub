"""Email notifications for platform invitations."""
from __future__ import annotations

import html
import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from models import PlatformInvitation, User
from services.email_layout import email_shell, user_display
from services.resend_mail import (
    EMAIL_ONLY_RE,
    format_resend_from,
    normalize_email,
    send_resend_email,
)

MULTI_WG_INVITE_SUBJECT = 'Invitation to join a Desirable Properties workgroup'

_JOIN_PRIMARY_RE = re.compile(r'\[JOIN_PRIMARY\]', re.IGNORECASE)
_JOIN_EXTRA_RE = re.compile(r'\[JOIN_EXTRA_(\d+)\]', re.IGNORECASE)


def invite_body_uses_join_placeholders(body_text: str) -> bool:
    """True when the draft expects inline join URLs instead of appended link blocks."""
    text = body_text or ''
    return bool(_JOIN_PRIMARY_RE.search(text) or _JOIN_EXTRA_RE.search(text))


def substitute_workgroup_join_placeholders(body_text: str, links: List[dict]) -> str:
    """Replace [JOIN_PRIMARY] and [JOIN_EXTRA_N] with invitation landing URLs."""
    text = body_text or ''
    if not text:
        return text

    primary_url = ''
    if links:
        primary_url = (links[0].get('landing_url') or '').strip()
    text = _JOIN_PRIMARY_RE.sub(primary_url, text)

    for index, item in enumerate(links[1:], start=1):
        url = (item.get('landing_url') or '').strip()
        text = re.sub(rf'\[JOIN_EXTRA_{index}\]', url, text, flags=re.IGNORECASE)

    text = _JOIN_EXTRA_RE.sub('', text)
    return text


def _bcc_inviter_enabled(override: Optional[bool] = None) -> bool:
    if override is not None:
        return bool(override)
    return os.environ.get('WORKGROUP_INVITE_BCC_INVITER', '1').strip().lower() not in (
        '0', 'false', 'no', 'off',
    )


def inviter_delivery_options(
    inviter: User,
    *,
    bcc_inviter: Optional[bool] = None,
) -> Dict[str, Any]:
    """From display name, Reply-To, and optional BCC derived from inviter profile.

    From address stays the verified Resend domain; only the display name is overridden.
    Reply-To uses the inviter's profile email so replies go to them.
    BCC defaults on (``WORKGROUP_INVITE_BCC_INVITER``; set ``0``/``false`` to disable).
    """
    display = user_display(inviter)
    inviter_email = normalize_email(getattr(inviter, 'email', None))
    reply_to = None
    if EMAIL_ONLY_RE.match(inviter_email):
        reply_to = format_resend_from(name=display, email=inviter_email) or inviter_email
    bcc = [inviter_email] if (_bcc_inviter_enabled(bcc_inviter) and reply_to) else None
    return {
        'from_display_name': display,
        'reply_to': reply_to,
        'bcc': bcc,
    }


def build_multi_workgroup_invite_plain_body(
    *,
    invitee_name: str,
    body_text: str,
    links: List[dict],
    inline_join_links: bool = False,
) -> str:
    """Plain-text body for platform HTML email and client mailto."""
    name = (invitee_name or 'there').strip() or 'there'
    parts = [f'Hi {name},', '']
    text = (body_text or '').strip()
    if text:
        parts.append(text)
        parts.append('')
    if not inline_join_links:
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
    inline_join_links: bool = False,
) -> Dict[str, str]:
    subject = MULTI_WG_INVITE_SUBJECT
    body = build_multi_workgroup_invite_plain_body(
        invitee_name=invitee_name,
        body_text=body_text,
        links=links,
        inline_join_links=inline_join_links,
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
    bcc_inviter: Optional[bool] = None,
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
    delivery = inviter_delivery_options(inviter, bcc_inviter=bcc_inviter)
    return send_resend_email(
        to=[invitee_email.strip()],
        subject=f'Invitation: {short_name} on Gov Hub',
        html=html_doc,
        from_display_name=delivery['from_display_name'],
        reply_to=delivery['reply_to'],
        bcc=delivery['bcc'],
    )


def send_multi_workgroup_invitation_email(
    *,
    inviter: User,
    invitee_email: str,
    invitee_name: str,
    body_text: str,
    links: list,
    bcc_inviter: Optional[bool] = None,
    inline_join_links: bool = False,
) -> bool:
    """Single email with custom body and one join link per workgroup.

    From display name uses the inviter profile; Reply-To is the inviter email.
    Optional BCC of the inviter (env WORKGROUP_INVITE_BCC_INVITER=0 to disable).
    When ``inline_join_links`` is true, join URLs are expected in ``body_text`` already.
    """
    inviter_name = html.escape(user_display(inviter))
    name_esc = html.escape(invitee_name or 'there')
    note = (
        f'<p style="white-space:pre-wrap;line-height:1.6;">{html.escape(body_text.strip())}</p>'
        if body_text and body_text.strip()
        else ''
    )
    sign_in_note = (
        '<p style="font-size:13px;color:#555;margin-top:16px;">'
        'Use the same email address this message was sent to when signing in to Desirable Properties.</p>'
    )
    if inline_join_links:
        body = f"""
<p>Hi {name_esc},</p>
{note}
{sign_in_note}
"""
    else:
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
        body = f"""
<p>Hi {name_esc},</p>
{note}
<p>{inviter_name} invited you to join workgroup(s) on Desirable Properties:</p>
{links_html}
{sign_in_note}
"""
    html_doc = email_shell('Workgroup invitation', body)
    plain = build_multi_workgroup_invite_plain_body(
        invitee_name=invitee_name,
        body_text=body_text,
        links=links,
        inline_join_links=inline_join_links,
    )
    delivery = inviter_delivery_options(inviter, bcc_inviter=bcc_inviter)

    return send_resend_email(
        to=[invitee_email.strip()],
        subject=MULTI_WG_INVITE_SUBJECT,
        html=html_doc,
        text=plain,
        from_display_name=delivery['from_display_name'],
        reply_to=delivery['reply_to'],
        bcc=delivery['bcc'],
    )
