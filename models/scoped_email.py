"""Admin-scoped email campaigns (layer / guild) with optional scheduling."""
from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from extensions import db

SCOPE_TYPES = ('layer', 'guild')
SCHEDULE_MODES = ('immediate', 'at', 'after_join')
ANCHOR_KINDS = ('layer_member', 'guild_member', 'waitlist_member')
CAMPAIGN_STATUSES = ('scheduled', 'active', 'completed', 'cancelled')
DELIVERY_STATUSES = ('pending', 'sent', 'failed', 'skipped', 'cancelled')


class ScopedEmailCampaign(db.Model):
    __tablename__ = 'scoped_email_campaign'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    scope_type = db.Column(db.String(16), nullable=False, index=True)
    scope_id = db.Column(db.String(36), nullable=False, index=True)
    created_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)

    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)

    schedule_mode = db.Column(db.String(20), nullable=False, default='immediate', index=True)
    scheduled_at = db.Column(db.DateTime, nullable=True, index=True)
    delay_hours = db.Column(db.Float, nullable=True)
    anchor_kind = db.Column(db.String(32), nullable=True)

    recipient_spec_json = db.Column(db.Text, nullable=False, default='{}')
    status = db.Column(db.String(20), nullable=False, default='scheduled', index=True)

    stats_sent = db.Column(db.Integer, nullable=False, default=0)
    stats_failed = db.Column(db.Integer, nullable=False, default=0)
    stats_total = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    created_by = db.relationship('User', foreign_keys=[created_by_id])

    def recipient_spec(self) -> dict:
        try:
            data = json.loads(self.recipient_spec_json or '{}')
        except (TypeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'scope_type': self.scope_type,
            'scope_id': self.scope_id,
            'created_by_id': self.created_by_id,
            'subject': self.subject,
            'body': self.body,
            'schedule_mode': self.schedule_mode,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'delay_hours': self.delay_hours,
            'anchor_kind': self.anchor_kind,
            'recipient_spec': self.recipient_spec(),
            'status': self.status,
            'stats_sent': self.stats_sent,
            'stats_failed': self.stats_failed,
            'stats_total': self.stats_total,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }


class ScopedEmailDelivery(db.Model):
    __tablename__ = 'scoped_email_delivery'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    campaign_id = db.Column(db.String(36), db.ForeignKey('scoped_email_campaign.id'), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)

    anchor_at = db.Column(db.DateTime, nullable=True)
    send_at = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    sent_at = db.Column(db.DateTime, nullable=True)
    resend_id = db.Column(db.String(64), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    campaign = db.relationship('ScopedEmailCampaign', backref=db.backref('deliveries', lazy='dynamic'))
    user = db.relationship('User', foreign_keys=[user_id])

    __table_args__ = (
        db.Index('idx_scoped_email_delivery_campaign_user', 'campaign_id', 'user_id'),
    )
