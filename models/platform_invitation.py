"""Unified platform invitations (DP Challenge, document edit, workgroup join)."""
from datetime import datetime
from uuid import uuid4

from extensions import db

INVITE_TYPES = frozenset({
    'participate_dp',
    'edit_document',
    'edit_document_passage',
    'review_document',
    'join_workgroup',
})

RATE_CATEGORIES = frozenset({'standard', 'participation'})

INVITE_STATUSES = frozenset({
    'pending',
    'accepted',
    'declined',
    'expired',
    'revoked',
    'duplicate',
})  # revoked: link disabled via revoked_at + status


class PlatformInvitation(db.Model):
    __tablename__ = 'platform_invitation'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    invite_type = db.Column(db.String(40), nullable=False, index=True)
    rate_category = db.Column(db.String(20), nullable=False, default='standard', index=True)
    inviter_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    invitee_email = db.Column(db.String(255), nullable=False, index=True)
    invitee_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    message = db.Column(db.Text, nullable=True)
    target_json = db.Column(db.Text, nullable=False, default='{}')
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    outcome_note = db.Column(db.String(255), nullable=True)
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    binding_mode = db.Column(db.String(20), nullable=False, default='private', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)

    inviter = db.relationship('User', foreign_keys=[inviter_id], backref='sent_platform_invitations')
    invitee = db.relationship('User', foreign_keys=[invitee_id], backref='received_platform_invitations')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'invite_type': self.invite_type,
            'rate_category': self.rate_category,
            'inviter_id': self.inviter_id,
            'invitee_email': self.invitee_email,
            'invitee_id': self.invitee_id,
            'message': self.message,
            'target_json': self.target_json,
            'status': self.status,
            'outcome_note': self.outcome_note,
            'binding_mode': getattr(self, 'binding_mode', None) or 'private',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'revoked_at': self.revoked_at.isoformat() if getattr(self, 'revoked_at', None) else None,
            'responded_at': self.responded_at.isoformat() if self.responded_at else None,
        }


class PlatformInvitationAcceptance(db.Model):
    """Per-user accept log for shareable (multi-use) platform invitations."""
    __tablename__ = 'platform_invitation_acceptance'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    invitation_id = db.Column(
        db.String(36),
        db.ForeignKey('platform_invitation.id'),
        nullable=False,
        index=True,
    )
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    invitation = db.relationship(
        'PlatformInvitation',
        backref=db.backref('acceptances', lazy='dynamic'),
    )
    user = db.relationship('User', backref=db.backref('platform_invite_acceptances', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('invitation_id', 'user_id', name='uq_platform_invite_accept_user'),
    )
