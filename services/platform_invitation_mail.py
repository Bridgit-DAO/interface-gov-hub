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
LONG_GAP_EMAIL_SUBJECT = 'From the Metaweb to a Layered Web: Your Input is Requested'
LONG_GAP_PROGRESSION_IMAGE_URL = 'https://desirableproperties.org/images/dp-challenge-arc.jpg'
DP_CHALLENGE_SITE_BASE = 'https://desirableproperties.org'

_JOIN_PRIMARY_RE = re.compile(r'\[JOIN_PRIMARY\]', re.IGNORECASE)
_JOIN_EXTRA_RE = re.compile(r'\[JOIN_EXTRA_(\d+)\]', re.IGNORECASE)
_JOIN_ANY_RE = re.compile(r'\[JOIN_[^\]]*\]', re.IGNORECASE)
_INTERNAL_BRACKET_ONLY_LINE_RE = re.compile(
    r'^\s*\[(?![^\]]*https?://)([^\]]{6,})\]\s*$',
    re.IGNORECASE | re.MULTILINE,
)
_INTERNAL_BRACKET_INLINE_RE = re.compile(
    r'\[(?:Then\s+workgroup|Close\s+warmly|Lead\s+with|MESSAGE\s+STRATEGY|'
    r'transition\s+into|join\s+placeholders?|reference\s+shared)[^\]]*\]',
    re.IGNORECASE,
)
_PROMPT_LEAK_LINE_RE = re.compile(
    r'^\s*(?:MESSAGE STRATEGY|INVITE CONTENT STRUCTURE|EVENTS TO MENTION|'
    r'PERSPECTIVES TO MENTION|ZOHO EMAIL HISTORY)(?:\s|\().*$',
    re.IGNORECASE | re.MULTILINE,
)
_EMAIL_OFF_LINE_RE = re.compile(r'^\s*Email is off\.?\s*$', re.IGNORECASE | re.MULTILINE)
_GREETING_PREFIX_RE = re.compile(r'^(hi|hello|dear)\b', re.IGNORECASE)
_PLANNING_LEAK_SECTION_RE = re.compile(
    r'\n\n(?:Let me (?:check(?:\s+requirements)?|finalize|reconsider|verify|'
    r'double-?check|count(?:\s+words)?|adjust|draft(?:\s+more carefully)?|'
    r'expand|recount|revise|add|also (?:check|verify|consider))|'
    r'---\s*\n\nLet me )',
    re.IGNORECASE,
)
_PLANNING_LEAK_LINE_RE = re.compile(
    r'^\s*(?:Let me (?:check(?:\s+requirements)?|finalize|reconsider|verify|'
    r'double-?check|count(?:\s+words)?|adjust|draft(?:\s+more carefully)?|'
    r'expand|recount|revise|add|also (?:check|verify|consider))|'
    r'Hmm let me|That\'?s about \d+ words|Total:\s*~?\d+).*$',
    re.IGNORECASE | re.MULTILINE,
)
_PLANNING_CHECKLIST_LINE_RE = re.compile(
    r'^\s*-\s+(?:"[^"]+"|\'[^\']+\'|.+)[\s(]\d+\)?\s*$|^\s*-\s+.+[✓✔]\s*$',
    re.IGNORECASE | re.MULTILINE,
)
_HTTPS_URL_RE = re.compile(r'https?://[^\s<>"\'\]]+')


def _trim_trailing_url_punctuation(url: str) -> str:
    trimmed = url
    while trimmed and trimmed[-1] in '.,);:]}>':
        trimmed = trimmed[:-1]
    return trimmed


def body_text_to_html_paragraph(body_text: str) -> str:
    """Escape plain invite body text and autolink https:// URLs for HTML email."""
    text = (body_text or '').strip()
    if not text:
        return ''
    parts: List[str] = []
    pos = 0
    for match in _HTTPS_URL_RE.finditer(text):
        start, end = match.span()
        parts.append(html.escape(text[pos:start]))
        raw_url = _trim_trailing_url_punctuation(match.group(0))
        end = start + len(raw_url)
        href = html.escape(raw_url, quote=True)
        label = html.escape(raw_url)
        parts.append(f'<a href="{href}">{label}</a>')
        pos = end
    parts.append(html.escape(text[pos:]))
    inner = ''.join(parts)
    return f'<p style="white-space:pre-wrap;line-height:1.6;">{inner}</p>'


def sanitize_invite_email_body(body_text: str) -> str:
    """Remove internal join markers, bracket stage directions, and prompt leaks."""
    text = (body_text or '').strip()
    if not text:
        return text

    planning_match = _PLANNING_LEAK_SECTION_RE.search(text)
    if planning_match:
        text = text[:planning_match.start()].rstrip()

    text = _JOIN_ANY_RE.sub('', text)
    text = _INTERNAL_BRACKET_INLINE_RE.sub('', text)
    text = _INTERNAL_BRACKET_ONLY_LINE_RE.sub('', text)
    text = _PROMPT_LEAK_LINE_RE.sub('', text)
    text = _EMAIL_OFF_LINE_RE.sub('', text)
    text = _PLANNING_LEAK_LINE_RE.sub('', text)
    text = _PLANNING_CHECKLIST_LINE_RE.sub('', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def body_text_has_greeting(body_text: str) -> bool:
    """True when draft body already opens with Hi/Hello/Dear (avoid double greeting in shell)."""
    text = (body_text or '').strip()
    if not text:
        return False
    return bool(_GREETING_PREFIX_RE.match(text))


def dp_number_from_label(dp_label: str) -> Optional[int]:
    """Extract DP number from labels like DP22 or DP6 - Commerce."""
    match = re.search(r'DP\s*0*(\d+)', (dp_label or ''), re.IGNORECASE)
    if not match:
        return None
    number = int(match.group(1))
    return number if 1 <= number <= 23 else None


def dp_workgroup_card_image_url(
    *,
    dp_label: str = '',
    dp_number: Optional[int] = None,
) -> Optional[str]:
    """Absolute HTTPS URL for a numbered DP card image on desirableproperties.org."""
    number = dp_number if dp_number is not None else dp_number_from_label(dp_label)
    if number is None:
        return None
    return f'{DP_CHALLENGE_SITE_BASE}/images/dps/card/DP{number}.webp'


def normalize_long_gap_greeting_in_body(body_text: str, invitee_name: str) -> str:
    """Replace a stale or quoted greeting line with Hi {sanitized_first_name},"""
    from services.workgroup_invite_ai import _invitee_greeting_name

    first_name = _invitee_greeting_name(invitee_name)
    text = (body_text or '').strip()
    if not text:
        return f'Hi {first_name},'
    paragraphs = text.split('\n\n')
    if paragraphs and _GREETING_PREFIX_RE.match(paragraphs[0].strip()):
        paragraphs[0] = f'Hi {first_name},'
        return '\n\n'.join(paragraphs)
    return text


def build_long_gap_progression_image_html(
    *,
    link_url: Optional[str] = None,
) -> str:
    """Full-width progression diagram (DPs to Overweb) for long-gap outreach HTML."""
    src = html.escape(LONG_GAP_PROGRESSION_IMAGE_URL, quote=True)
    alt = html.escape(
        'Desirable Properties Challenge, Requirements, ADRs, and Overweb progression',
    )
    img = (
        f'<img src="{src}" alt="{alt}" '
        'style="width:100%;max-width:600px;height:auto;display:block;border-radius:8px;margin:0 auto;" />'
    )
    if link_url:
        href = html.escape(link_url.strip(), quote=True)
        return (
            f'<p style="margin:0 0 20px;text-align:center;">'
            f'<a href="{href}" style="text-decoration:none;">{img}</a></p>'
        )
    return f'<p style="margin:0 0 20px;text-align:center;">{img}</p>'


def build_long_gap_dp_card_image_html(image_url: str, *, alt: str = 'Workgroup illustration') -> str:
    src = html.escape((image_url or '').strip(), quote=True)
    if not src:
        return ''
    alt_esc = html.escape(alt)
    return (
        f'<p style="margin:20px 0 12px;text-align:center;">'
        f'<img src="{src}" alt="{alt_esc}" '
        'style="width:100%;max-width:480px;height:auto;display:block;border-radius:8px;margin:0 auto;" />'
        '</p>'
    )


def build_long_gap_outreach_html(
    body_text: str,
    invitee_name: str,
    *,
    dp_card_image_url: Optional[str] = None,
    progression_link_url: Optional[str] = None,
) -> str:
    """HTML body for long-gap outreach: progression image, greeting, paragraphs, optional DP art."""
    from services.workgroup_invite_ai import _invitee_greeting_name

    normalized = normalize_long_gap_greeting_in_body(body_text, invitee_name)
    paragraphs = [part.strip() for part in normalized.split('\n\n') if part.strip()]

    main_paragraphs: List[str] = []
    signoff_paragraphs: List[str] = []
    in_signoff = False
    greeting_skipped = False
    dp_insert_index: Optional[int] = None

    for paragraph in paragraphs:
        if not greeting_skipped and _GREETING_PREFIX_RE.match(paragraph):
            greeting_skipped = True
            continue
        if paragraph.startswith('Warmly'):
            in_signoff = True
        if in_signoff:
            signoff_paragraphs.append(paragraph)
            continue
        if dp_card_image_url and dp_insert_index is None:
            lowered = paragraph.lower()
            if 'would love your input on' in lowered or 'take a look here:' in lowered:
                dp_insert_index = len(main_paragraphs)
        main_paragraphs.append(paragraph)

    greet = html.escape(_invitee_greeting_name(invitee_name))
    parts: List[str] = [build_long_gap_progression_image_html(link_url=progression_link_url)]
    parts.append(f'<p>Hi {greet},</p>')

    for index, paragraph in enumerate(main_paragraphs):
        if (
            dp_card_image_url
            and dp_insert_index is not None
            and index == dp_insert_index
        ):
            parts.append(build_long_gap_dp_card_image_html(dp_card_image_url))
        parts.append(body_text_to_html_paragraph(paragraph))

    for paragraph in signoff_paragraphs:
        parts.append(body_text_to_html_paragraph(paragraph))

    return '\n'.join(parts)


def send_long_gap_outreach_email(
    inviter: User,
    to_email: str,
    to_name: str,
    body_text: str,
    *,
    dp_card_image_url: Optional[str] = None,
    progression_link_url: Optional[str] = None,
    bcc_inviter: Optional[bool] = None,
) -> bool:
    """Send long-gap outreach with progression/DP images and the standard subject line."""
    clean_body = sanitize_invite_email_body((body_text or '').strip())
    if not clean_body:
        return False
    clean_body = normalize_long_gap_greeting_in_body(clean_body, to_name)
    html_inner = build_long_gap_outreach_html(
        clean_body,
        to_name,
        dp_card_image_url=dp_card_image_url,
        progression_link_url=progression_link_url,
    )
    html_doc = email_shell('Desirable Properties', html_inner)
    delivery = inviter_delivery_options(inviter, bcc_inviter=bcc_inviter)
    return send_resend_email(
        to=[normalize_email(to_email)],
        subject=LONG_GAP_EMAIL_SUBJECT,
        html=html_doc,
        text=clean_body,
        from_display_name=delivery['from_display_name'],
        reply_to=delivery['reply_to'],
        bcc=delivery['bcc'],
    )


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
    text = (body_text or '').strip()
    parts: List[str] = []
    if text:
        if not body_text_has_greeting(text):
            parts.extend([f'Hi {name},', '', text, ''])
        else:
            parts.extend([text, ''])
    else:
        parts.extend([f'Hi {name},', ''])
    if not inline_join_links:
        parts.append('Join link(s):')
        for item in links or []:
            wg_name = (item.get('workgroup_name') or 'Workgroup').strip()
            url = (item.get('landing_url') or '').strip()
            if url:
                parts.append(f'- {wg_name}: {url}')
        parts.append('')
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
    long_gap_outreach: bool = False,
    long_gap_dp_image_url: Optional[str] = None,
    subject_override: Optional[str] = None,
) -> bool:
    """Single email with custom body and one join link per workgroup.

    From display name uses the inviter profile; Reply-To is the inviter email.
    Optional BCC of the inviter (env WORKGROUP_INVITE_BCC_INVITER=0 to disable).
    When ``inline_join_links`` is true, join URLs are expected in ``body_text`` already.
  When ``long_gap_outreach`` is true, use the long-gap HTML layout with progression/DP images.
    """
    inviter_name = html.escape(user_display(inviter))
    name_esc = html.escape(invitee_name or 'there')
    resolved_body = normalize_long_gap_greeting_in_body(body_text, invitee_name) if long_gap_outreach else body_text
    note = body_text_to_html_paragraph(resolved_body) if resolved_body and resolved_body.strip() else ''
    greeting_html = ''
    if not body_text_has_greeting(resolved_body):
        greeting_html = f'<p>Hi {name_esc},</p>'
    if long_gap_outreach:
        html_inner = build_long_gap_outreach_html(
            resolved_body,
            invitee_name,
            dp_card_image_url=long_gap_dp_image_url,
        )
        if inline_join_links:
            body = html_inner
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
            links_html = ''.join(link_blocks)
            body = f'{html_inner}\n{links_html}'
        html_doc = email_shell('Desirable Properties', body)
        plain = build_multi_workgroup_invite_plain_body(
            invitee_name=invitee_name,
            body_text=resolved_body,
            links=links,
            inline_join_links=inline_join_links,
        )
        subject = subject_override or LONG_GAP_EMAIL_SUBJECT
    elif inline_join_links:
        body = f"""
{greeting_html}
{note}
"""
        html_doc = email_shell('Workgroup invitation', body)
        plain = build_multi_workgroup_invite_plain_body(
            invitee_name=invitee_name,
            body_text=body_text,
            links=links,
            inline_join_links=inline_join_links,
        )
        subject = subject_override or MULTI_WG_INVITE_SUBJECT
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
{greeting_html}
{note}
<p>{inviter_name} invited you to join workgroup(s) on Desirable Properties:</p>
{links_html}
"""
        html_doc = email_shell('Workgroup invitation', body)
        plain = build_multi_workgroup_invite_plain_body(
            invitee_name=invitee_name,
            body_text=body_text,
            links=links,
            inline_join_links=inline_join_links,
        )
        subject = subject_override or MULTI_WG_INVITE_SUBJECT
    delivery = inviter_delivery_options(inviter, bcc_inviter=bcc_inviter)

    return send_resend_email(
        to=[invitee_email.strip()],
        subject=subject,
        html=html_doc,
        text=plain,
        from_display_name=delivery['from_display_name'],
        reply_to=delivery['reply_to'],
        bcc=delivery['bcc'],
    )
