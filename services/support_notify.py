"""Support ticket email notifications via Resend."""
from __future__ import annotations

import html
import os
from typing import Any, Dict, List, Optional

from services.resend_mail import send_resend_email_result


def _default_ops_email() -> str:
    return (
        os.environ.get('GOVHUB_SUPPORT_EMAIL', '').strip().lower()
        or os.environ.get('SUPPORT_EMAIL', '').strip().lower()
        or 'support@themetalayer.org'
    )


def _alert_email_for_ticket(ticket: Dict[str, Any]) -> str:
    urgency = str(ticket.get('urgency') or '').lower()
    if urgency == 'critical':
        return os.environ.get('GOVHUB_SUPPORT_CRITICAL_EMAIL', '').strip().lower() or _default_ops_email()
    if urgency == 'blocking':
        return os.environ.get('GOVHUB_SUPPORT_BLOCKING_EMAIL', '').strip().lower() or _default_ops_email()
    return _default_ops_email()


def _public_base() -> str:
    from flask import current_app
    return str(current_app.config.get('PUBLIC_BASE_URL') or 'https://interfacehub.net').rstrip('/')


def _category_label(category: str) -> str:
    return str(category or 'general').replace('_', ' ')


def send_support_ticket_alert(data_dir: str, ticket: Dict[str, Any]) -> Dict[str, Any]:
    to = _alert_email_for_ticket(ticket)
    admin_base = _public_base()
    subject = f"[Gov Hub Support · {ticket.get('urgency')}] {ticket.get('subject')}"
    body_html = html.escape(str(ticket.get('body') or ''))
    page_html = html.escape(str(ticket.get('pageUrl') or '—'))
    html_doc = f"""
    <h2>New Gov Hub support request</h2>
    <p><strong>Ticket:</strong> {html.escape(ticket.get('id') or '')}</p>
    <p><strong>Category:</strong> {_category_label(ticket.get('category'))}</p>
    <p><strong>Urgency:</strong> {html.escape(str(ticket.get('urgency') or ''))}</p>
    <p><strong>From:</strong> {html.escape(str(ticket.get('handle') or ticket.get('email') or ticket.get('userId') or 'unknown'))}</p>
    <p><strong>Page:</strong> {page_html}</p>
    <p><strong>Admin:</strong> <a href="{admin_base}/support/admin">{admin_base}/support/admin</a></p>
    <hr />
    <pre style="white-space:pre-wrap;font-family:system-ui,sans-serif">{body_html}</pre>
    """
    result = send_resend_email_result(to=to, subject=subject, html=html_doc)
    if result.get('ok'):
        return {'ok': True, 'id': result.get('id')}
    return {'ok': False, 'error': result.get('error') or 'send_failed'}


def send_support_ticket_ack(ticket: Dict[str, Any]) -> Dict[str, Any]:
    to = str(ticket.get('email') or '').strip().lower()
    if not to or '@' not in to:
        return {'ok': False, 'error': 'ticket_missing_email'}
    base = _public_base()
    subject = f"We received your support request: {ticket.get('subject')}"
    html_doc = f"""<!DOCTYPE html><html><body style="font-family:Georgia,serif;line-height:1.6;color:#111;">
<p>Hello,</p>
<p>We received your support request (reference <code>{html.escape(ticket.get('id') or '')}</code>).</p>
<p><strong>{html.escape(ticket.get('subject') or '')}</strong></p>
<p>Our team will review it and follow up soon. When signed in, track status at <a href="{html.escape(base + '/support')}">{html.escape(base + '/support')}</a>.</p>
<p style="margin-top:2em;font-size:12px;color:#666;">Gov Hub support</p>
</body></html>"""
    result = send_resend_email_result(to=to, subject=subject, html=html_doc)
    if result.get('ok'):
        return {'ok': True, 'id': result.get('id')}
    return {'ok': False, 'error': result.get('error') or 'send_failed'}


def send_support_reply_email(ticket: Dict[str, Any], *, subject: Optional[str] = None, body: Optional[str] = None) -> Dict[str, Any]:
    to = str(ticket.get('email') or '').strip().lower()
    if not to or '@' not in to:
        return {'ok': False, 'error': 'ticket_missing_email'}
    draft = ticket.get('draftReply') or {}
    subj = str(subject or draft.get('subject') or '').strip() or f"Re: {ticket.get('subject') or 'Gov Hub support'}"
    reply_body = str(body or draft.get('body') or '').strip()
    if not reply_body:
        return {'ok': False, 'error': 'reply_body_required'}
    body_html = html.escape(reply_body).replace('\n', '<br>\n')
    ref = f" · ref {html.escape(ticket.get('id') or '')}" if ticket.get('id') else ''
    html_doc = f"""<!DOCTYPE html><html><body style="font-family:Georgia,serif;line-height:1.6;color:#111;">
{body_html}
<p style="margin-top:2em;font-size:12px;color:#666;">Gov Hub support{ref}</p>
</body></html>"""
    result = send_resend_email_result(to=to, subject=subj, html=html_doc)
    if result.get('ok'):
        return {'ok': True, 'id': result.get('id')}
    return {'ok': False, 'error': result.get('error') or 'send_failed'}
