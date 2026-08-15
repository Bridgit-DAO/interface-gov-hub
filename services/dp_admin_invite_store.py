"""DP admin invite send records and Zoho ingest helpers."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from extensions import db
from models.dp_admin_invite_send import (
    DpAdminInviteSendRecord,
    SEND_STATUSES,
    draft_excerpt,
    draft_hash,
)
from config import INSTANCE_DIR
from services.zoho_mail import admin_snapshot_key, admin_contacts_snapshot_path, normalize_admin_email

DEFAULT_AGENT_DROP_DIR = '/home/ubuntu/meta-console/agent-drop'
_HIDDEN_DIRNAME = 'invite_zoho_hidden'
_SELECTED_DIRNAME = 'invite_zoho_selected'
_AUTO_HIDE_SEND_STATUSES = frozenset({'sent', 'skipped'})


def agent_drop_dir() -> str:
    configured = (os.environ.get('AGENT_DROP_DIR') or '').strip()
    if configured:
        return configured
    return DEFAULT_AGENT_DROP_DIR


def resolve_agent_drop_file(name: str) -> Path:
    raw = (name or '').strip()
    if not raw or '..' in raw or raw.startswith('/') or raw.startswith('.'):
        raise ValueError('invalid agent drop filename')
    base = os.path.basename(raw.replace('\\', '/'))
    if not base or base.startswith('.'):
        raise ValueError('invalid agent drop filename')
    path = (Path(agent_drop_dir()) / base).resolve()
    root = Path(agent_drop_dir()).resolve()
    if path.parent != root:
        raise ValueError('path traversal blocked')
    if not path.is_file():
        raise FileNotFoundError(base)
    return path


def _encode_source_with_strategy(source: str, message_strategy: str = '') -> str:
    base = (source or 'manual').strip() or 'manual'
    strategy = (message_strategy or '').strip().lower()
    if not strategy:
        return base
    if '|strategy=' in base:
        return base
    return f'{base}|strategy={strategy}'


def record_admin_invite_send(
    *,
    admin: dict,
    recipient_email: str,
    recipient_name: str = '',
    workgroup_ids: Optional[List[str]] = None,
    body: str = '',
    status: str = 'sent',
    invitation_id: Optional[str] = None,
    send_mode: Optional[str] = None,
    source: str = 'manual',
    message_strategy: str = '',
) -> DpAdminInviteSendRecord:
    clean_status = (status or 'sent').strip().lower()
    if clean_status not in SEND_STATUSES:
        raise ValueError(f'invalid status: {status}')

    row = DpAdminInviteSendRecord(
        admin_id=admin['id'],
        admin_email=normalize_admin_email(admin.get('email') or ''),
        recipient_email=(recipient_email or '').strip().lower(),
        recipient_name=(recipient_name or '').strip(),
        workgroup_ids_json=json.dumps(workgroup_ids or []),
        draft_hash=draft_hash(body) if body.strip() else None,
        draft_excerpt=draft_excerpt(body) if body.strip() else None,
        status=clean_status,
        invitation_id=(invitation_id or '').strip() or None,
        send_mode=(send_mode or '').strip() or None,
        source=_encode_source_with_strategy(source, message_strategy),
    )
    db.session.add(row)
    db.session.commit()
    return row


def list_admin_invite_sends(
    admin: dict,
    *,
    limit: int = 50,
    recipient_email: Optional[str] = None,
) -> List[dict]:
    query = DpAdminInviteSendRecord.query.filter_by(admin_id=admin['id'])
    if recipient_email:
        query = query.filter(
            db.func.lower(DpAdminInviteSendRecord.recipient_email)
            == recipient_email.strip().lower(),
        )
    rows = (
        query.order_by(DpAdminInviteSendRecord.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [row.to_dict() for row in rows]


def send_history_by_recipient(admin: dict, emails: List[str]) -> Dict[str, List[dict]]:
    normalized = sorted({(email or '').strip().lower() for email in emails if (email or '').strip()})
    if not normalized:
        return {}
    rows = (
        DpAdminInviteSendRecord.query.filter(
            DpAdminInviteSendRecord.admin_id == admin['id'],
            db.func.lower(DpAdminInviteSendRecord.recipient_email).in_(normalized),
        )
        .order_by(DpAdminInviteSendRecord.created_at.desc())
        .all()
    )
    grouped: Dict[str, List[dict]] = {email: [] for email in normalized}
    for row in rows:
        key = (row.recipient_email or '').strip().lower()
        if key in grouped:
            grouped[key].append(row.to_dict())
    return grouped


def hidden_contacts_path(admin_email: str) -> Path:
    admin_key = admin_snapshot_key(admin_email)
    return Path(INSTANCE_DIR) / _HIDDEN_DIRNAME / f'{admin_key}.json'


def _load_hidden_payload(admin_email: str) -> dict:
    path = hidden_contacts_path(admin_email)
    if not path.is_file():
        return {'hidden_emails': {}}
    try:
        with path.open(encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {'hidden_emails': {}}
    if not isinstance(payload, dict):
        return {'hidden_emails': {}}
    hidden = payload.get('hidden_emails')
    if not isinstance(hidden, dict):
        payload['hidden_emails'] = {}
    return payload


def _save_hidden_payload(admin_email: str, payload: dict) -> None:
    path = hidden_contacts_path(admin_email)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload['updated_at'] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def manual_hidden_emails(admin_email: str) -> Set[str]:
    payload = _load_hidden_payload(admin_email)
    hidden = payload.get('hidden_emails') or {}
    return {
        normalize_admin_email(email)
        for email in hidden.keys()
        if normalize_admin_email(email)
    }


def auto_hidden_emails(admin: dict) -> Set[str]:
    rows = (
        DpAdminInviteSendRecord.query.filter(
            DpAdminInviteSendRecord.admin_id == admin['id'],
            DpAdminInviteSendRecord.status.in_(sorted(_AUTO_HIDE_SEND_STATUSES)),
        )
        .with_entities(DpAdminInviteSendRecord.recipient_email)
        .distinct()
        .all()
    )
    return {
        normalize_admin_email(row[0])
        for row in rows
        if normalize_admin_email(row[0])
    }


def hidden_invite_emails(admin: dict, *, include_auto: bool = True) -> Set[str]:
    owner = normalize_admin_email(admin.get('email') or '')
    hidden = manual_hidden_emails(owner)
    if include_auto:
        hidden |= auto_hidden_emails(admin)
    return hidden


def hide_invite_contact(
    admin: dict,
    *,
    recipient_email: str,
    note: str = '',
    reason: str = 'manual',
) -> dict:
    owner = normalize_admin_email(admin.get('email') or '')
    email = normalize_admin_email(recipient_email)
    if not email:
        raise ValueError('recipient_email is required')
    payload = _load_hidden_payload(owner)
    hidden = payload.setdefault('hidden_emails', {})
    hidden[email] = {
        'reason': (reason or 'manual').strip() or 'manual',
        'note': (note or '').strip()[:500],
        'hidden_at': datetime.now(timezone.utc).isoformat(),
    }
    _save_hidden_payload(owner, payload)
    return hidden[email]


def unhide_invite_contact(admin: dict, *, recipient_email: str) -> bool:
    owner = normalize_admin_email(admin.get('email') or '')
    email = normalize_admin_email(recipient_email)
    if not email:
        raise ValueError('recipient_email is required')
    payload = _load_hidden_payload(owner)
    hidden = payload.get('hidden_emails') or {}
    if email not in hidden:
        return False
    del hidden[email]
    payload['hidden_emails'] = hidden
    _save_hidden_payload(owner, payload)
    return True


def list_hidden_invite_contacts(admin: dict) -> List[dict]:
    owner = normalize_admin_email(admin.get('email') or '')
    payload = _load_hidden_payload(owner)
    hidden = payload.get('hidden_emails') or {}
    auto = auto_hidden_emails(admin)
    rows: List[dict] = []
    for email, meta in sorted(hidden.items()):
        if not isinstance(meta, dict):
            meta = {}
        rows.append({
            'email': email,
            'reason': meta.get('reason') or 'manual',
            'note': meta.get('note') or '',
            'hidden_at': meta.get('hidden_at') or '',
            'auto_hidden': email in auto,
            'manual': True,
        })
    for email in sorted(auto):
        if email in hidden:
            continue
        rows.append({
            'email': email,
            'reason': 'sent_or_skipped',
            'note': '',
            'hidden_at': '',
            'auto_hidden': True,
            'manual': False,
        })
    return rows


def selected_contacts_path(admin_email: str) -> Path:
    admin_key = admin_snapshot_key(admin_email)
    return Path(INSTANCE_DIR) / _SELECTED_DIRNAME / f'{admin_key}.json'


def _load_selected_payload(admin_email: str) -> dict:
    path = selected_contacts_path(admin_email)
    if not path.is_file():
        return {'selected_emails': []}
    try:
        with path.open(encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {'selected_emails': []}
    if not isinstance(payload, dict):
        return {'selected_emails': []}
    emails = payload.get('selected_emails')
    if not isinstance(emails, list):
        payload['selected_emails'] = []
    return payload


def _save_selected_payload(admin_email: str, payload: dict) -> None:
    path = selected_contacts_path(admin_email)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload['updated_at'] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def list_selected_invite_emails(admin_email: str) -> List[str]:
    payload = _load_selected_payload(admin_email)
    emails = payload.get('selected_emails') or []
    return sorted({
        normalize_admin_email(email)
        for email in emails
        if normalize_admin_email(email)
    })


def get_selected_invite_contacts(admin: dict) -> dict:
    owner = normalize_admin_email(admin.get('email') or '')
    payload = _load_selected_payload(owner)
    emails = list_selected_invite_emails(owner)
    return {
        'emails': emails,
        'updated_at': payload.get('updated_at') or '',
    }


def set_selected_invite_emails(admin: dict, emails: List[str]) -> dict:
    owner = normalize_admin_email(admin.get('email') or '')
    normalized = sorted({
        normalize_admin_email(email)
        for email in emails
        if normalize_admin_email(email)
    })
    payload = {'selected_emails': normalized}
    _save_selected_payload(owner, payload)
    return {
        'emails': normalized,
        'updated_at': payload.get('updated_at') or '',
    }


def patch_selected_invite_emails(
    admin: dict,
    *,
    add: Optional[List[str]] = None,
    remove: Optional[List[str]] = None,
) -> dict:
    owner = normalize_admin_email(admin.get('email') or '')
    current = set(list_selected_invite_emails(owner))
    for email in add or []:
        normalized = normalize_admin_email(email)
        if normalized:
            current.add(normalized)
    for email in remove or []:
        normalized = normalize_admin_email(email)
        if normalized:
            current.discard(normalized)
    return set_selected_invite_emails(admin, sorted(current))


def filter_visible_zoho_contacts(
    contacts: List[dict],
    admin: dict,
    *,
    show_hidden: bool = False,
) -> tuple[List[dict], dict]:
    if show_hidden:
        return contacts, {
            'hidden_count': 0,
            'visible_count': len(contacts),
            'show_hidden': True,
        }
    hidden = hidden_invite_emails(admin, include_auto=True)
    visible = [
        row for row in contacts
        if normalize_admin_email(row.get('email') or '') not in hidden
    ]
    return visible, {
        'hidden_count': len(contacts) - len(visible),
        'visible_count': len(visible),
        'show_hidden': False,
    }


_DISPATCH_DIRNAME = 'invite_long_gap_dispatch'


def long_gap_dispatch_path(admin_email: str) -> Path:
    admin_key = admin_snapshot_key(admin_email)
    return Path(INSTANCE_DIR) / _DISPATCH_DIRNAME / f'{admin_key}.json'


def _load_long_gap_dispatch_payload(admin_email: str) -> dict:
    path = long_gap_dispatch_path(admin_email)
    if not path.is_file():
        return {'rows': {}}
    try:
        with path.open(encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {'rows': {}}
    if not isinstance(payload, dict):
        return {'rows': {}}
    rows = payload.get('rows')
    if not isinstance(rows, dict):
        payload['rows'] = {}
    return payload


def _save_long_gap_dispatch_payload(admin_email: str, payload: dict) -> None:
    path = long_gap_dispatch_path(admin_email)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload['updated_at'] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def get_long_gap_dispatch_rows(admin_email: str) -> dict:
    owner = normalize_admin_email(admin_email)
    payload = _load_long_gap_dispatch_payload(owner)
    rows = payload.get('rows') or {}
    return {
        'rows': rows,
        'updated_at': payload.get('updated_at') or '',
    }


def save_long_gap_dispatch_rows(admin_email: str, rows: dict) -> dict:
    owner = normalize_admin_email(admin_email)
    payload = _load_long_gap_dispatch_payload(owner)
    payload['rows'] = rows
    _save_long_gap_dispatch_payload(owner, payload)
    return {
        'rows': rows,
        'updated_at': payload.get('updated_at') or '',
    }


def patch_long_gap_dispatch_row(admin_email: str, email: str, patch: dict) -> Optional[dict]:
    owner = normalize_admin_email(admin_email)
    row_email = normalize_admin_email(email)
    if not row_email:
        raise ValueError('email is required')
    payload = _load_long_gap_dispatch_payload(owner)
    rows = payload.setdefault('rows', {})
    row = rows.get(row_email)
    if not isinstance(row, dict):
        return None
    for key, value in patch.items():
        if key == 'email':
            continue
        row[key] = value
    rows[row_email] = row
    _save_long_gap_dispatch_payload(owner, payload)
    return row
