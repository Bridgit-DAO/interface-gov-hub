"""DP admin invite send records and Zoho ingest helpers."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from extensions import db
from models.dp_admin_invite_send import (
    DpAdminInviteSendRecord,
    SEND_STATUSES,
    draft_excerpt,
    draft_hash,
)
from services.zoho_mail import admin_contacts_snapshot_path, normalize_admin_email

DEFAULT_AGENT_DROP_DIR = '/home/ubuntu/meta-console/agent-drop'


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
        source=(source or 'manual').strip() or 'manual',
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
