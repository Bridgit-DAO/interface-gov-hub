"""Canonical referral conversion records (scoped attribution contract v1)."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class ReferralAttribution(db.Model):
    __tablename__ = 'referral_attribution'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    product = db.Column(db.String(20), nullable=False, default='gov_hub', index=True)
    referrer_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    converted_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    scope_type = db.Column(db.String(32), nullable=False, index=True)
    scope_id = db.Column(db.String(36), nullable=False, index=True)
    entity_type = db.Column(db.String(32), nullable=False)
    entity_id = db.Column(db.String(36), nullable=False)
    conversion_type = db.Column(db.String(32), nullable=False, index=True)
    channel = db.Column(db.String(32), nullable=True)
    campaign = db.Column(db.String(64), nullable=True)
    share_event_id = db.Column(db.String(36), nullable=True)
    referral_token = db.Column(db.Text, nullable=True)
    legacy_referral_code = db.Column(db.String(50), nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)  # JSON string
    converted_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    referrer = db.relationship('User', foreign_keys=[referrer_user_id], backref='referral_conversions_made')
    converted_user = db.relationship('User', foreign_keys=[converted_user_id], backref='referral_conversions_received')

    def to_dict(self):
        import json
        meta = None
        if self.metadata_json:
            try:
                meta = json.loads(self.metadata_json)
            except (TypeError, ValueError):
                meta = None
        return {
            'id': self.id,
            'product': self.product,
            'referrer_user_id': self.referrer_user_id,
            'converted_user_id': self.converted_user_id,
            'scope_type': self.scope_type,
            'scope_id': self.scope_id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'conversion_type': self.conversion_type,
            'channel': self.channel,
            'campaign': self.campaign,
            'share_event_id': self.share_event_id,
            'legacy_referral_code': self.legacy_referral_code,
            'metadata': meta,
            'converted_at': self.converted_at.isoformat() if self.converted_at else None,
        }
