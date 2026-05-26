"""Transactional email via Resend (shared with waitlist verification)."""
from __future__ import annotations

import os
from typing import List, Optional


def send_resend_email(
    *,
    to: List[str],
    subject: str,
    html: str,
    list_unsubscribe_url: Optional[str] = None,
) -> bool:
    """Send one email. Returns True on success."""
    api_key = os.environ.get('RESEND_API_KEY', '').strip()
    from_email = os.environ.get('RESEND_FROM', 'Gov Hub <no-reply@govhub.live>').strip()
    if not api_key:
        try:
            from flask import current_app
            current_app.logger.warning('RESEND_API_KEY not set — skipping email')
        except RuntimeError:
            pass
        return False
    try:
        import resend
        resend.api_key = api_key
        params = {
            'from': from_email,
            'to': to,
            'subject': subject,
            'html': html,
        }
        if list_unsubscribe_url:
            params['headers'] = {
                'List-Unsubscribe': f'<{list_unsubscribe_url}>',
                'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
            }
        resp = resend.Emails.send(params)
        try:
            from flask import current_app
            msg_id = resp.get('id') if isinstance(resp, dict) else getattr(resp, 'id', None)
            current_app.logger.info(f'Resend sent to {to} id={msg_id}')
        except RuntimeError:
            pass
        return True
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(f'Resend send failed: {e}')
        except RuntimeError:
            pass
        return False
