"""DpProposal model — sentence-level patches on DP and non-DP documents."""
from datetime import datetime
from uuid import uuid4

from extensions import db

DP_PROPOSAL_STATUSES = frozenset({
    'pending',
    'accepted',
    'declined',
    'incorporated',
    'orphaned',
})

DP_PROPOSAL_SCOPES = frozenset({'dp', 'document'})


class DpProposal(db.Model):
    """Sentence-level text change (patch → merged when accepted)."""
    __tablename__ = 'dp_proposal'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    submission_id = db.Column(db.String(36), db.ForeignKey('submission.id'), nullable=False, index=True)
    scope = db.Column(db.String(20), default='dp', nullable=False, index=True)
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    anchor_hash = db.Column(db.String(64), nullable=False, index=True)
    context_anchor = db.Column(db.Text, nullable=True)
    original_text = db.Column(db.Text, nullable=False)
    proposed_text = db.Column(db.Text, nullable=False)
    rationale = db.Column(db.Text, nullable=True)
    reference_url = db.Column(db.String(2048), nullable=True)
    content_hash_at_create = db.Column(db.String(64), nullable=True, index=True)
    author_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    reviewed_by_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    incorporated_submission_id = db.Column(db.String(36), db.ForeignKey('submission.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    submission = db.relationship(
        'Submission',
        foreign_keys=[submission_id],
        backref=db.backref('dp_proposals', lazy='dynamic'),
    )
    author = db.relationship('User', foreign_keys=[author_user_id], backref='dp_proposals_authored')
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_user_id], backref='dp_proposals_reviewed')
    incorporated_submission = db.relationship(
        'Submission',
        foreign_keys=[incorporated_submission_id],
    )

    def status_label(self) -> str:
        labels = {
            'pending': 'Patch',
            'accepted': 'Merged',
            'declined': 'Declined',
            'incorporated': 'Published in revision',
            'orphaned': 'Original text not found',
        }
        return labels.get(self.status or '', self.status or 'Unknown')

    def to_dict(self, *, include_anchor: bool = True) -> dict:
        author_name = None
        if self.author:
            author_name = self.author.displayName or self.author.username
        reviewer_name = None
        if self.reviewed_by:
            reviewer_name = self.reviewed_by.displayName or self.reviewed_by.username
        data = {
            'id': self.id,
            'submission_id': self.submission_id,
            'scope': self.scope,
            'status': self.status,
            'status_label': self.status_label(),
            'anchor_hash': self.anchor_hash,
            'original_text': self.original_text,
            'proposed_text': self.proposed_text,
            'rationale': self.rationale,
            'reference_url': self.reference_url,
            'content_hash_at_create': self.content_hash_at_create,
            'author_user_id': self.author_user_id,
            'author_name': author_name,
            'reviewed_by_user_id': self.reviewed_by_user_id,
            'reviewed_by_name': reviewer_name,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'incorporated_submission_id': self.incorporated_submission_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_anchor and self.context_anchor:
            data['context_anchor'] = self.context_anchor
        return data
