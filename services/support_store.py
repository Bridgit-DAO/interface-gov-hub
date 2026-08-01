"""File-backed support tickets (same schema as Desirable Properties challenge-site)."""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import INSTANCE_DIR

SUPPORT_CATEGORIES = (
    'workgroup_help',
    'layer_governance',
    'nominations',
    'technical_support',
    'content_clarification',
    'general',
)
VALID_URGENCY = frozenset({'critical', 'blocking', 'non_blocking'})
VALID_STATUS = frozenset({'open', 'triaged', 'closed'})
VALID_NOTE_KIND = frozenset({'investigation', 'draft_reply', 'system', 'reply_sent'})
URGENCY_RANK = {'critical': 0, 'blocking': 1, 'non_blocking': 2}
TICKET_SOURCE = 'govhub'
MIME_OK = re.compile(r'^image/(png|jpeg|jpg|webp|gif)$', re.I)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _norm(value: Any, max_len: int = 8000) -> str:
    return str(value or '').strip()[:max_len]


def support_data_dir() -> str:
    return os.path.join(INSTANCE_DIR, 'support-tickets')


def _tickets_dir(data_dir: str) -> str:
    return data_dir


def _attachments_root(data_dir: str) -> str:
    return os.path.join(data_dir, 'attachments')


def _ticket_path(data_dir: str, ticket_id: str) -> str:
    return os.path.join(data_dir, f'{ticket_id}.json')


def _ensure_dirs(data_dir: str) -> None:
    os.makedirs(_attachments_root(data_dir), exist_ok=True)


def _empty_draft() -> Dict[str, Any]:
    return {'subject': '', 'body': '', 'createdAt': None, 'updatedAt': None, 'sentAt': None, 'sentBy': None}


def _normalize_ticket(ticket: Dict[str, Any]) -> Dict[str, Any]:
    ticket.setdefault('agentNotes', [])
    ticket.setdefault('draftReply', _empty_draft())
    if ticket.get('escalatedToHuman') is None:
        ticket['escalatedToHuman'] = ticket.get('urgency') == 'critical'
    ticket.setdefault('proposedResolution', None)
    ticket.setdefault('resolution', None)
    return ticket


def read_ticket(data_dir: str, ticket_id: str) -> Optional[Dict[str, Any]]:
    fp = _ticket_path(data_dir, ticket_id)
    if not os.path.isfile(fp):
        return None
    try:
        with open(fp, 'r', encoding='utf-8') as fh:
            return _normalize_ticket(json.load(fh))
    except (OSError, json.JSONDecodeError):
        return None


def _write_ticket(data_dir: str, ticket: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_dirs(data_dir)
    ticket['updatedAt'] = _now_iso()
    with open(_ticket_path(data_dir, ticket['id']), 'w', encoding='utf-8') as fh:
        json.dump(ticket, fh, indent=2)
    return ticket


def _list_ticket_ids(data_dir: str) -> List[str]:
    _ensure_dirs(data_dir)
    if not os.path.isdir(data_dir):
        return []
    return [f[:-5] for f in os.listdir(data_dir) if f.endswith('.json')]


def list_tickets(data_dir: str) -> List[Dict[str, Any]]:
    rows = [read_ticket(data_dir, tid) for tid in _list_ticket_ids(data_dir)]
    rows = [r for r in rows if r]

    def sort_key(t: Dict[str, Any]) -> Tuple[int, str]:
        return URGENCY_RANK.get(t.get('urgency'), 9), t.get('createdAt') or ''

    return sorted(rows, key=sort_key)


def public_ticket_summary(ticket: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'id': ticket['id'],
        'createdAt': ticket.get('createdAt'),
        'updatedAt': ticket.get('updatedAt'),
        'status': ticket.get('status'),
        'subject': ticket.get('subject'),
        'urgency': ticket.get('urgency'),
        'category': ticket.get('category'),
        'pageUrl': ticket.get('pageUrl'),
        'hasScreenshots': ticket.get('hasScreenshots'),
    }


def public_base() -> str:
    from flask import current_app
    return str(current_app.config.get('PUBLIC_BASE_URL') or 'https://hub.themetalayer.org').rstrip('/')


def attachment_urls(ticket: Dict[str, Any]) -> List[Dict[str, Any]]:
    base = public_base()
    out = []
    for att in ticket.get('attachments') or []:
        fn = att.get('filename')
        if not fn:
            continue
        out.append({
            'filename': fn,
            'mimeType': att.get('mimeType'),
            'size': att.get('size'),
            'url': f"{base}/api/support/hermes/tickets/{ticket['id']}/attachments/{fn}",
        })
    return out


def public_ticket_summary_extended(ticket: Dict[str, Any], *, include_body: bool = False) -> Dict[str, Any]:
    summary = {
        **public_ticket_summary(ticket),
        'email': ticket.get('email'),
        'handle': ticket.get('handle'),
        'userId': ticket.get('userId'),
        'escalatedToHuman': ticket.get('escalatedToHuman'),
        'bodyPreview': str(ticket.get('body') or '')[:280],
    }
    if include_body:
        for key in (
            'body', 'stepsToReproduce', 'expectedBehavior', 'actualBehavior', 'triedAlready',
            'agentNotes', 'draftReply', 'proposedResolution', 'resolution', 'diagnosticBundle',
            'browser', 'os', 'attachments',
        ):
            summary[key] = ticket.get(key)
    summary['attachmentUrls'] = attachment_urls(ticket)
    return summary


def ticket_for_hermes(ticket: Dict[str, Any]) -> Dict[str, Any]:
    return public_ticket_summary_extended(ticket, include_body=True)


def _save_attachments(data_dir: str, ticket_id: str, screenshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    saved: List[Dict[str, Any]] = []
    att_dir = os.path.join(_attachments_root(data_dir), ticket_id)
    os.makedirs(att_dir, exist_ok=True)
    for i, item in enumerate((screenshots or [])[:5]):
        mime = _norm(item.get('mimeType') or 'image/png', 64).lower()
        if not MIME_OK.match(mime):
            continue
        raw = str(item.get('dataBase64') or '')
        if raw.startswith('data:'):
            raw = raw.split(',', 1)[-1]
        if not raw:
            continue
        try:
            buf = base64.b64decode(raw, validate=True)
        except (ValueError, binascii.Error):
            continue
        if not buf or len(buf) > 1_500_000:
            continue
        ext = 'jpg' if 'jpeg' in mime or 'jpg' in mime else 'webp' if 'webp' in mime else 'gif' if 'gif' in mime else 'png'
        att_id = f'{i + 1}-{uuid.uuid4().hex[:8]}'
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', _norm(item.get('filename') or f'screenshot-{att_id}.{ext}', 120))
        rel = os.path.join('attachments', ticket_id, filename)
        abs_path = os.path.join(data_dir, rel)
        with open(abs_path, 'wb') as fh:
            fh.write(buf)
        saved.append({'id': att_id, 'filename': filename, 'mimeType': mime, 'size': len(buf), 'path': rel})
    return saved


def _find_duplicates(data_dir: str, user_id: Optional[str], subject: str, hours: int = 24) -> List[str]:
    if not user_id:
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
    subj = _norm(subject, 200).lower()
    out = []
    for t in list_tickets(data_dir):
        if t.get('userId') != user_id:
            continue
        try:
            created = datetime.fromisoformat(str(t.get('createdAt', '')).replace('Z', '+00:00')).timestamp()
        except ValueError:
            continue
        if created < cutoff:
            continue
        other = _norm(t.get('subject'), 200).lower()
        if other == subj or subj in other or other in subj:
            out.append(t['id'])
    return out


def create_ticket(data_dir: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    urgency = _norm(payload.get('urgency') or 'non_blocking', 32).lower()
    category = _norm(payload.get('category') or 'general', 64).lower()
    if urgency not in VALID_URGENCY:
        return {'ok': False, 'error': 'invalid_urgency'}
    if category not in SUPPORT_CATEGORIES:
        return {'ok': False, 'error': 'invalid_category'}

    subject = _norm(payload.get('subject'), 200)
    body = _norm(payload.get('body'), 8000)
    if not subject:
        return {'ok': False, 'error': 'subject_required'}
    if not body:
        return {'ok': False, 'error': 'body_required'}

    ticket_id = str(uuid.uuid4())
    now = _now_iso()
    attachments = _save_attachments(data_dir, ticket_id, payload.get('screenshots') or [])
    has_screenshots = bool(attachments)
    if category == 'technical_support' and not payload.get('screenshotAcknowledged') and not has_screenshots:
        return {'ok': False, 'error': 'screenshot_ack_required'}

    user_id = _norm(payload.get('userId'), 128) or None
    ticket = _normalize_ticket({
        'id': ticket_id,
        'createdAt': now,
        'updatedAt': now,
        'status': 'open',
        'subject': subject,
        'body': body,
        'urgency': urgency,
        'category': category,
        'screenshotAcknowledged': bool(payload.get('screenshotAcknowledged')),
        'userId': user_id,
        'email': _norm(payload.get('email'), 200).lower() or None,
        'handle': _norm(payload.get('handle'), 80) or None,
        'pageUrl': _norm(payload.get('pageUrl'), 500) or None,
        'browser': _norm(payload.get('browser'), 200) or None,
        'os': _norm(payload.get('os'), 120) or None,
        'canopiMode': _norm(payload.get('canopiMode'), 64) or None,
        'stepsToReproduce': _norm(payload.get('stepsToReproduce'), 4000) or None,
        'expectedBehavior': _norm(payload.get('expectedBehavior'), 1000) or None,
        'actualBehavior': _norm(payload.get('actualBehavior'), 1000) or None,
        'triedAlready': _norm(payload.get('triedAlready'), 4000) or None,
        'diagnosticBundle': payload.get('diagnosticBundle') if isinstance(payload.get('diagnosticBundle'), dict) else None,
        'attachments': attachments,
        'hasScreenshots': has_screenshots,
        'relatedTicketIds': [x for x in _find_duplicates(data_dir, user_id, subject) if x != ticket_id],
        'source': TICKET_SOURCE,
        'agentNotes': [],
        'draftReply': _empty_draft(),
        'proposedResolution': None,
        'resolution': None,
        'escalatedToHuman': urgency == 'critical',
    })
    return {'ok': True, 'ticket': _write_ticket(data_dir, ticket)}


def search_tickets(data_dir: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = filters or {}
    q = _norm(filters.get('q'), 200).lower()
    urgency = _norm(filters.get('urgency'), 32).lower()
    category = _norm(filters.get('category'), 64).lower()
    status = _norm(filters.get('status'), 32).lower()
    user_id = _norm(filters.get('userId'), 128)
    limit = min(100, max(1, int(filters.get('limit') or 50)))
    offset = max(0, int(filters.get('offset') or 0))

    rows = list_tickets(data_dir)
    if urgency in VALID_URGENCY:
        rows = [t for t in rows if t.get('urgency') == urgency]
    if category in SUPPORT_CATEGORIES:
        rows = [t for t in rows if t.get('category') == category]
    if status in VALID_STATUS:
        rows = [t for t in rows if t.get('status') == status]
    if user_id:
        rows = [t for t in rows if t.get('userId') == user_id]
    if q:
        def hay(t: Dict[str, Any]) -> str:
            return ' '.join(str(t.get(k) or '') for k in (
                'id', 'subject', 'body', 'email', 'handle', 'userId', 'category', 'urgency', 'pageUrl'
            )).lower()
        rows = [t for t in rows if q in hay(t)]

    return {'total': len(rows), 'offset': offset, 'limit': limit, 'tickets': rows[offset:offset + limit]}


def attachment_abs_path(data_dir: str, ticket_id: str, filename: str) -> Optional[str]:
    safe = os.path.basename(str(filename or ''))
    if not safe or safe != filename:
        return None
    ticket = read_ticket(data_dir, ticket_id)
    if not ticket:
        return None
    att = next((a for a in ticket.get('attachments') or [] if a.get('filename') == safe), None)
    if not att:
        return None
    return os.path.join(data_dir, att['path'])


def patch_ticket(data_dir: str, ticket_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    ticket = read_ticket(data_dir, ticket_id)
    if not ticket:
        return {'ok': False, 'error': 'not_found'}

    if patch.get('status') is not None:
        nxt = _norm(patch['status'], 32).lower()
        if nxt not in VALID_STATUS:
            return {'ok': False, 'error': 'invalid_status'}
        ticket['status'] = nxt
    if patch.get('proposedResolution') is not None:
        ticket['proposedResolution'] = _norm(patch['proposedResolution'], 4000) or None
    if patch.get('resolution') is not None:
        ticket['resolution'] = _norm(patch['resolution'], 4000) or None
    if patch.get('escalatedToHuman') is not None:
        ticket['escalatedToHuman'] = bool(patch['escalatedToHuman'])
    dr = patch.get('draftReply')
    if isinstance(dr, dict):
        now = _now_iso()
        if dr.get('subject') is not None:
            ticket['draftReply']['subject'] = _norm(dr['subject'], 200)
        if dr.get('body') is not None:
            ticket['draftReply']['body'] = _norm(dr['body'], 8000)
        ticket['draftReply']['updatedAt'] = now
        if not ticket['draftReply'].get('createdAt'):
            ticket['draftReply']['createdAt'] = now
    note = patch.get('note')
    if note:
        kind = note.get('kind') if note.get('kind') in VALID_NOTE_KIND else 'investigation'
        text = _norm(note.get('text'), 8000)
        if not text:
            return {'ok': False, 'error': 'note_text_required'}
        ticket['agentNotes'].append({
            'id': str(uuid.uuid4()),
            'at': _now_iso(),
            'author': _norm(note.get('author'), 80) or 'hermes',
            'kind': kind,
            'text': text,
        })
    return {'ok': True, 'ticket': _write_ticket(data_dir, ticket)}


def mark_draft_reply_sent(data_dir: str, ticket_id: str, sent_by: str) -> Dict[str, Any]:
    ticket = read_ticket(data_dir, ticket_id)
    if not ticket:
        return {'ok': False, 'error': 'not_found'}
    now = _now_iso()
    ticket['draftReply']['sentAt'] = now
    ticket['draftReply']['sentBy'] = _norm(sent_by, 80) or 'admin'
    ticket['agentNotes'].append({
        'id': str(uuid.uuid4()),
        'at': now,
        'author': _norm(sent_by, 80) or 'admin',
        'kind': 'reply_sent',
        'text': f"Reply sent to {ticket.get('email') or 'unknown'}: {ticket['draftReply'].get('subject')}",
    })
    if ticket.get('status') == 'open':
        ticket['status'] = 'triaged'
    return {'ok': True, 'ticket': _write_ticket(data_dir, ticket)}
