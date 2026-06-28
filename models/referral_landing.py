"""Anonymous referral link landing events (pre-auth funnel)."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class ReferralLanding(db.Model):
    __tablename__ = 'referral_landing'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    referrer_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    scope_type = db.Column(db.String(32), nullable=False, index=True)
    scope_id = db.Column(db.String(36), nullable=False, index=True)
    entity_type = db.Column(db.String(32), nullable=False)
    entity_id = db.Column(db.String(36), nullable=False)
    channel = db.Column(db.String(32), nullable=True)
    landing_url = db.Column(db.String(500), nullable=False)
    referral_token = db.Column(db.Text, nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    referrer = db.relationship('User', foreign_keys=[referrer_user_id])

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
            'referrer_user_id': self.referrer_user_id,
            'scope_type': self.scope_type,
            'scope_id': self.scope_id,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'channel': self.channel,
            'landing_url': self.landing_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'metadata': meta,
        }
