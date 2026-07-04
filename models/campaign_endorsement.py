"""Public campaign endorsements (moderated)."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class CampaignEndorsement(db.Model):
    __tablename__ = 'campaign_endorsement'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    campaign_slug = db.Column(db.String(80), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    endorsement_type = db.Column(db.String(40), nullable=False, default='support_direction')
    display_name = db.Column(db.String(200), nullable=False)
    affiliation = db.Column(db.String(300), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)

    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('campaign_endorsements', lazy='dynamic'))

    ENDORSEMENT_TYPES = frozenset({
        'endorse_current_draft',
        'support_direction',
        'sign_statement',
        'support_with_reservations',
        'institutional_endorsement',
        'follow_updates',
    })
