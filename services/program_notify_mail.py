"""Program notify-list and launch emails (e.g. DP Challenge on The Metaweb)."""
from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from extensions import db
from models import Layer, LayerProgram, User, WaitlistEntry
from services.layer_programs import format_launch_at_pacific, parse_entry_dp_interests
import os
import time

from services.resend_mail import send_resend_email_result


def _public_base_url() -> str:
    from flask import current_app
    from config import PUBLIC_BASE_URL, resolved_public_base_url

    return resolved_public_base_url(current_app.config.get('PUBLIC_BASE_URL') or PUBLIC_BASE_URL)


def _user_display(user: Optional[User]) -> str:
    if not user:
        return 'there'
    return user.displayName or user.name or user.username or 'there'


def _email_shell(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="font-family:system-ui,-apple-system,sans-serif;line-height:1.5;color:#222;max-width:560px;margin:0 auto;padding:24px;">
<h2 style="color:#667eea;margin-top:0;">{html.escape(title)}</h2>
{body_html}
<p style="font-size:12px;color:#888;margin-top:32px;">Gov Hub · Meta-Layer Governance Hub</p>
</body></html>"""


def _program_hub_url(program: LayerProgram, layer: Optional[Layer]) -> str:
    base = _public_base_url()
    if program.hub_path:
        path = program.hub_path if program.hub_path.startswith('/') else f'/{program.hub_path}'
        return f'{base}{path}'
    if layer:
        return f'{base}/layers/{layer.slug}/#program-{program.slug}'
    return base


def _interest_lines(interests: List[Dict[str, Any]]) -> str:
    if not interests:
        return ''
    items = ''.join(
        f'<li>{html.escape(str(item.get("label") or item.get("draft_ref") or "Draft"))}</li>'
        for item in interests
    )
    return f'<p>You asked to be notified about:</p><ul>{items}</ul>'


def send_program_notify_confirmation(
    *,
    user: User,
    program: LayerProgram,
    dp_interests: Optional[List[Dict[str, Any]]] = None,
    updated: bool = False,
) -> bool:
    """Confirmation after joining/updating a program notify waitlist."""
    email = (user.email or '').strip()
    if not email:
        return False

    layer = Layer.query.get(program.layer_id)
    launch_label = format_launch_at_pacific(program.launch_at)
    when_line = (
        f'<p>We plan to open <strong>{html.escape(program.name)}</strong> around '
        f'<strong>{html.escape(launch_label)}</strong>.</p>'
        if launch_label
        else f'<p>We will email you when <strong>{html.escape(program.name)}</strong> opens.</p>'
    )
    action = 'updated your notification preferences for' if updated else 'added you to the notify list for'
    body = f"""
<p>Hi {html.escape(_user_display(user))},</p>
<p>You are on the list — we {action} <strong>{html.escape(program.name)}</strong>
{f' on {html.escape(layer.name)}' if layer and layer.name else ''}.</p>
{when_line}
{_interest_lines(dp_interests or [])}
<p style="font-size:13px;color:#666;">No action needed. We will send another email when participation opens.</p>
"""
    text_lines = [
        f'Hi {_user_display(user)},',
        '',
        f'You are on the notify list for {program.name}.',
        f'Launch: {launch_label}' if launch_label else 'We will email you when it opens.',
    ]
    if dp_interests:
        text_lines.append('Your DP interests:')
        for item in dp_interests:
            text_lines.append(f'- {item.get("label") or item.get("draft_ref") or "Draft"}')

    result = send_resend_email_result(
        to=[email],
        subject=f'You\'re on the list — {program.name}',
        html=_email_shell('Notify list confirmed', body),
        text='\n'.join(text_lines),
        tags=[
            {'name': 'category', 'value': 'program_notify'},
            {'name': 'program', 'value': program.slug[:256]},
        ],
    )
    return bool(result.get('ok'))


def _entry_launch_notified(entry: WaitlistEntry) -> bool:
    if not entry.metadata_json:
        return False
    try:
        meta = json.loads(entry.metadata_json)
    except (TypeError, json.JSONDecodeError):
        return False
    return bool(meta.get('launch_notified_at'))


def _mark_entry_launch_notified(entry: WaitlistEntry) -> None:
    meta: Dict[str, Any] = {}
    if entry.metadata_json:
        try:
            meta = json.loads(entry.metadata_json)
        except (TypeError, json.JSONDecodeError):
            meta = {}
    meta['launch_notified_at'] = datetime.utcnow().isoformat()
    entry.metadata_json = json.dumps(meta)


def send_program_launch_notifications(program: LayerProgram) -> Dict[str, Any]:
    """Email all notify-list members when a program opens."""
    if not program.waitlist_id:
        return {'sent': 0, 'failed': 0, 'total': 0, 'skipped': True, 'reason': 'no_waitlist'}

    layer = Layer.query.get(program.layer_id)
    hub_url = _program_hub_url(program, layer)
    entries = (
        WaitlistEntry.query.filter_by(waitlist_id=program.waitlist_id, left_at=None)
        .order_by(WaitlistEntry.position.asc())
        .all()
    )

    delay_ms = int(os.environ.get('RESEND_SEND_INTERVAL_MS', '200') or '200')
    sent = 0
    failed = 0
    total = 0
    errors: List[str] = []

    for entry in entries:
        if _entry_launch_notified(entry):
            continue
        user = User.query.get(entry.user_id)
        email = (user.email or '').strip() if user else ''
        if not email:
            continue

        total += 1
        if sent + failed > 0 and delay_ms > 0:
            time.sleep(delay_ms / 1000.0)

        interests = parse_entry_dp_interests(entry)
        interest_html = _interest_lines(interests)
        display = _user_display(user)
        body = f"""
<p>Hi {html.escape(display)},</p>
<p><strong>{html.escape(program.name)}</strong> is now open for participation
{f' on {html.escape(layer.name)}' if layer and layer.name else ''}.</p>
{interest_html}
<p><a href="{html.escape(hub_url, quote=True)}" style="display:inline-block;padding:10px 18px;background:#667eea;color:#fff;text-decoration:none;border-radius:6px;">Open {html.escape(program.name)}</a></p>
<p style="font-size:13px;color:#666;">Or copy this link:<br><code>{html.escape(hub_url)}</code></p>
"""
        text_lines = [
            f'Hi {display},',
            '',
            f'{program.name} is now open.',
            f'Participate: {hub_url}',
        ]
        if interests:
            text_lines.append('Your DP interests:')
            for item in interests:
                text_lines.append(f'- {item.get("label") or item.get("draft_ref") or "Draft"}')

        result = send_resend_email_result(
            to=[email],
            subject=f'{program.name} is open',
            html=_email_shell(f'{program.name} is open', body),
            text='\n'.join(text_lines),
            tags=[
                {'name': 'category', 'value': 'program_launch'},
                {'name': 'program', 'value': program.slug[:256]},
            ],
        )
        if result.get('ok'):
            sent += 1
            _mark_entry_launch_notified(entry)
            db.session.commit()
        else:
            failed += 1
            errors.append(result.get('error') or 'unknown error')

    if total == 0:
        return {'sent': 0, 'failed': 0, 'total': 0, 'skipped': True, 'reason': 'no_recipients'}
    return {'sent': sent, 'failed': failed, 'total': total, 'errors': errors[:20]}
