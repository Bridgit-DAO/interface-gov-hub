"""Transactional email via Resend (shared across Gov Hub)."""
from __future__ import annotations

import os
import re
import time
from typing import Any, Dict, List, Optional, TypedDict, Union

DEFAULT_RESEND_FROM_NAME = 'Gov Hub'
DEFAULT_RESEND_FROM_EMAIL = 'no-reply@govhub.live'
EMAIL_ONLY_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
NAMED_FROM_RE = re.compile(r'^(.+?)\s*<([^>]+)>$')
QUOTED_DISPLAY_NAME_RE = re.compile(r'^"(.+)"$')
OUTER_ENV_QUOTE_RE = re.compile(r'^(["\'])([\s\S]*)\1$')

ResendTag = Dict[str, str]


class ResendSendResult(TypedDict, total=False):
    ok: bool
    id: str
    error: str
    skipped: bool
    reason: str


def strip_outer_env_quotes(raw: Optional[str]) -> str:
    trimmed = str(raw or '').strip()
    match = OUTER_ENV_QUOTE_RE.match(trimmed)
    return match.group(2).strip() if match else trimmed


def strip_display_name_quotes(name: Optional[str]) -> str:
    trimmed = str(name or '').strip()
    match = QUOTED_DISPLAY_NAME_RE.match(trimmed)
    if match:
        return match.group(1).replace('\\"', '"')
    return trimmed


def normalize_email(email: Optional[str]) -> str:
    return str(email or '').strip().lower()


def email_domain(email: Optional[str]) -> str:
    normalized = normalize_email(email)
    at = normalized.rfind('@')
    return normalized[at + 1:] if at >= 0 else ''


def _reply_to_aligns_with_from(from_email: str, reply_email: str) -> bool:
    from_domain = email_domain(from_email)
    reply_domain = email_domain(reply_email)
    return bool(from_domain and reply_domain and from_domain == reply_domain)


def _default_same_domain_reply_email(from_domain: str) -> Optional[str]:
    override = normalize_email(os.environ.get('RESEND_REPLY_TO_EMAIL', ''))
    if override and EMAIL_ONLY_RE.match(override) and email_domain(override) == from_domain:
        return override
    for candidate in (f'support@{from_domain}', f'info@{from_domain}', f'academy@{from_domain}'):
        if EMAIL_ONLY_RE.match(candidate):
            return candidate
    return None


def format_resend_from(*, name: str, email: str) -> Optional[str]:
    addr = normalize_email(email)
    if not EMAIL_ONLY_RE.match(addr):
        return None
    display_name = strip_display_name_quotes(name).strip()
    if not display_name:
        return addr
    return f'{display_name} <{addr}>'


def parse_resend_from(env_value: Optional[str]) -> Optional[Dict[str, str]]:
    raw = strip_outer_env_quotes(env_value)
    if not raw:
        return None

    named_match = NAMED_FROM_RE.match(raw)
    if named_match:
        name = strip_display_name_quotes(named_match.group(1).strip())
        email = named_match.group(2).strip().lower()
        if not EMAIL_ONLY_RE.match(email):
            return None
        return {'name': name, 'email': email}

    email = normalize_email(raw)
    if EMAIL_ONLY_RE.match(email):
        return {'name': DEFAULT_RESEND_FROM_NAME, 'email': email}
    return None


def get_resend_from() -> Optional[Dict[str, str]]:
    name_override = str(os.environ.get('RESEND_FROM_NAME', '')).strip()
    email_override = normalize_email(os.environ.get('RESEND_FROM_EMAIL', ''))
    parsed = parse_resend_from(os.environ.get('RESEND_FROM'))

    email = normalize_email(email_override or (parsed or {}).get('email', ''))
    if not EMAIL_ONLY_RE.match(email):
        return None

    display_name = name_override or (parsed or {}).get('name') or DEFAULT_RESEND_FROM_NAME
    formatted = format_resend_from(name=display_name, email=email)
    if not formatted:
        return None
    return {
        'displayName': strip_display_name_quotes(display_name),
        'email': email,
        'formatted': formatted,
    }


def get_resend_reply_to() -> Optional[str]:
    from_config = get_resend_from()
    from_email = (from_config or {}).get('email', '')
    from_domain = email_domain(from_email)
    display_name = (from_config or {}).get('displayName') or DEFAULT_RESEND_FROM_NAME

    def format_aligned(email: str) -> Optional[str]:
        normalized = normalize_email(email)
        if not EMAIL_ONLY_RE.match(normalized):
            return None
        return format_resend_from(name=display_name, email=normalized)

    override = str(os.environ.get('RESEND_REPLY_TO', '')).strip()
    if override:
        parsed = parse_resend_from(override)
        if parsed and parsed.get('email') and _reply_to_aligns_with_from(from_email, parsed['email']):
            return format_resend_from(name=parsed.get('name') or display_name, email=parsed['email'])
        email = normalize_email(override)
        if EMAIL_ONLY_RE.match(email) and _reply_to_aligns_with_from(from_email, email):
            return format_aligned(email)
        _log_resend_warning(
            f'RESEND_REPLY_TO domain ({email_domain(parsed["email"] if parsed else email)}) '
            f'differs from From ({from_domain}); using same-domain Reply-To'
        )

    support = normalize_email(
        os.environ.get('GOVHUB_SUPPORT_EMAIL')
        or os.environ.get('METAWEB_SUPPORT_EMAIL')
        or ''
    )
    if EMAIL_ONLY_RE.match(support) and _reply_to_aligns_with_from(from_email, support):
        return format_aligned(support)

    if from_domain:
        same_domain = _default_same_domain_reply_email(from_domain)
        if same_domain:
            return format_aligned(same_domain)
    return None


def resend_configured() -> bool:
    return bool(os.environ.get('RESEND_API_KEY', '').strip() and get_resend_from())


def _normalize_recipients(values: Union[str, List[str], None]) -> List[str]:
    if not values:
        return []
    items = values if isinstance(values, list) else [values]
    out: List[str] = []
    for item in items:
        email = normalize_email(item)
        if EMAIL_ONLY_RE.match(email):
            out.append(email)
    return out


def _log_resend_info(message: str) -> None:
    try:
        from flask import current_app
        current_app.logger.info(message)
    except RuntimeError:
        pass


def _log_resend_warning(message: str) -> None:
    try:
        from flask import current_app
        current_app.logger.warning(message)
    except RuntimeError:
        pass


def _log_resend_error(message: str) -> None:
    try:
        from flask import current_app
        current_app.logger.error(message)
    except RuntimeError:
        pass


def send_resend_email_result(
    *,
    to: Union[str, List[str]],
    subject: str,
    html: str,
    text: Optional[str] = None,
    bcc: Optional[Union[str, List[str]]] = None,
    reply_to: Optional[Union[str, List[str]]] = None,
    from_display_name: Optional[str] = None,
    tags: Optional[List[ResendTag]] = None,
    list_unsubscribe_url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> ResendSendResult:
    """Send one email via Resend. Returns structured result."""
    api_key = os.environ.get('RESEND_API_KEY', '').strip()
    from_config = get_resend_from()
    from_email = (from_config or {}).get('email', '')
    display_override = strip_display_name_quotes(from_display_name).strip() if from_display_name else ''
    if display_override and from_email:
        from_addr = format_resend_from(name=display_override, email=from_email) or ''
    else:
        from_addr = (from_config or {}).get('formatted', '')
    if not api_key:
        _log_resend_warning('RESEND_API_KEY not set – skipping email')
        return {'ok': False, 'error': 'RESEND_API_KEY is not set.'}
    if not from_addr:
        _log_resend_warning('RESEND_FROM is not configured – skipping email')
        return {'ok': False, 'error': 'RESEND_FROM is not set.'}

    to_list = _normalize_recipients(to)
    if not to_list:
        return {'ok': False, 'error': 'Invalid recipient email.'}

    params: Dict[str, Any] = {
        'from': from_addr,
        'to': to_list,
        'subject': str(subject or '').strip(),
        'html': html,
    }
    if text:
        params['text'] = text

    bcc_list = _normalize_recipients(bcc)
    if bcc_list:
        params['bcc'] = bcc_list

    reply_raw = reply_to if reply_to is not None else get_resend_reply_to()
    if reply_raw:
        # Bare emails must not inherit parse_resend_from's default "Gov Hub" name.
        reply_display = (
            display_override
            or (from_config or {}).get('displayName')
            or DEFAULT_RESEND_FROM_NAME
        )
        reply_list: List[str] = []
        for entry in reply_raw if isinstance(reply_raw, list) else [reply_raw]:
            raw = strip_outer_env_quotes(str(entry))
            named_match = NAMED_FROM_RE.match(raw)
            if named_match:
                name = strip_display_name_quotes(named_match.group(1).strip())
                email = named_match.group(2).strip().lower()
                if EMAIL_ONLY_RE.match(email):
                    formatted = format_resend_from(name=name or reply_display, email=email)
                    if formatted:
                        reply_list.append(formatted)
                continue
            email = normalize_email(raw)
            if EMAIL_ONLY_RE.match(email):
                formatted = format_resend_from(name=reply_display, email=email)
                if formatted:
                    reply_list.append(formatted)
        if reply_list:
            params['reply_to'] = reply_list[0] if len(reply_list) == 1 else reply_list

    clean_tags: List[ResendTag] = []
    for tag in tags or []:
        name = str((tag or {}).get('name') or '').strip()
        value = str((tag or {}).get('value') or '').strip()
        if name and value and len(name) <= 256 and len(value) <= 256:
            clean_tags.append({'name': name, 'value': value})
    if clean_tags:
        params['tags'] = clean_tags

    hdrs: Dict[str, str] = {}
    for key, value in (headers or {}).items():
        k = str(key).strip()
        v = str(value or '').strip()
        if k and v:
            hdrs[k] = v
    if list_unsubscribe_url:
        hdrs['List-Unsubscribe'] = f'<{list_unsubscribe_url}>'
        hdrs['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
    if hdrs:
        params['headers'] = hdrs

    if os.environ.get('RESEND_LOG_PAYLOAD') == '1':
        _log_resend_info(f'Resend payload: {params}')

    try:
        import resend

        resend.api_key = api_key
        resp = resend.Emails.send(params)
        msg_id = resp.get('id') if isinstance(resp, dict) else getattr(resp, 'id', None)
        _log_resend_info(f'Resend sent to {to_list} id={msg_id}')
        result: ResendSendResult = {'ok': True}
        if msg_id:
            result['id'] = str(msg_id)
        return result
    except Exception as exc:
        _log_resend_error(f'Resend send failed: {exc}')
        return {'ok': False, 'error': str(exc)}


def send_resend_email(
    *,
    to: List[str],
    subject: str,
    html: str,
    text: Optional[str] = None,
    bcc: Optional[Union[str, List[str]]] = None,
    reply_to: Optional[Union[str, List[str]]] = None,
    from_display_name: Optional[str] = None,
    tags: Optional[List[ResendTag]] = None,
    list_unsubscribe_url: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> bool:
    """Send one email. Returns True on success."""
    return bool(
        send_resend_email_result(
            to=to,
            subject=subject,
            html=html,
            text=text,
            bcc=bcc,
            reply_to=reply_to,
            from_display_name=from_display_name,
            tags=tags,
            list_unsubscribe_url=list_unsubscribe_url,
            headers=headers,
        ).get('ok')
    )


def send_resend_batch(
    messages: List[Dict[str, Any]],
    *,
    interval_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Send many emails with optional throttling between sends."""
    delay = interval_ms
    if delay is None:
        delay = int(os.environ.get('RESEND_SEND_INTERVAL_MS', '200') or '200')
    sent = 0
    failed = 0
    errors: List[str] = []
    for idx, msg in enumerate(messages):
        if idx and delay > 0:
            time.sleep(delay / 1000.0)
        result = send_resend_email_result(**msg)
        if result.get('ok'):
            sent += 1
        else:
            failed += 1
            err = result.get('error') or 'unknown error'
            errors.append(str(err))
    return {'sent': sent, 'failed': failed, 'total': len(messages), 'errors': errors[:20]}
