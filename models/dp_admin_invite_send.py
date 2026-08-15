"""DP site admin invite send audit log (Zoho batch + manual outreach)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4

from extensions import db

SEND_STATUSES = frozenset({'sent', 'skipped', 'draft', 'client_prepared'})


class DpAdminInviteSendRecord(db.Model):
    __tablename__ = 'dp_admin_invite_send_record'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    admin_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    admin_email = db.Column(db.String(255), nullable=False, index=True)
    recipient_email = db.Column(db.String(255), nullable=False, index=True)
    recipient_name = db.Column(db.String(255), nullable=False, default='')
    workgroup_ids_json = db.Column(db.Text, nullable=False, default='[]')
    draft_hash = db.Column(db.String(64), nullable=True)
    draft_excerpt = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(24), nullable=False, default='sent', index=True)
    invitation_id = db.Column(db.String(36), nullable=True, index=True)
    send_mode = db.Column(db.String(20), nullable=True)
    source = db.Column(db.String(40), nullable=False, default='manual', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    admin = db.relationship('User', foreign_keys=[admin_id])

    def workgroup_ids(self) -> list[str]:
        try:
            data = json.loads(self.workgroup_ids_json or '[]')
        except (TypeError, json.JSONDecodeError):
            return []
        return [str(item) for item in data if str(item).strip()]

    def to_dict(self) -> dict:
        strategy = message_strategy_from_source(self.source or '')
        return {
            'id': self.id,
            'admin_id': self.admin_id,
            'admin_email': self.admin_email,
            'recipient_email': self.recipient_email,
            'recipient_name': self.recipient_name,
            'workgroup_ids': self.workgroup_ids(),
            'draft_hash': self.draft_hash,
            'draft_excerpt': self.draft_excerpt,
            'status': self.status,
            'invitation_id': self.invitation_id,
            'send_mode': self.send_mode,
            'source': source_without_strategy(self.source or ''),
            'message_strategy': strategy or None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def draft_hash(body: str) -> str:
    normalized = (body or '').strip().encode('utf-8')
    return hashlib.sha256(normalized).hexdigest()


def draft_excerpt(body: str, *, limit: int = 500) -> str:
    return (body or '').strip()[:limit]


def message_strategy_from_source(source: str) -> str:
    raw = (source or '').strip()
    marker = '|strategy='
    if marker not in raw:
        return ''
    return raw.split(marker, 1)[1].strip().lower()


def source_without_strategy(source: str) -> str:
    raw = (source or '').strip()
    marker = '|strategy='
    if marker not in raw:
        return raw or 'manual'
    return raw.split(marker, 1)[0].strip() or 'manual'
