"""Unified layer-scoped tags for artifacts, submissions (documents), etc."""
from datetime import datetime
from uuid import uuid4

from extensions import db

SUBJECT_ARTIFACT = 'artifact'
SUBJECT_SUBMISSION = 'submission'


class LayerTag(db.Model):
    __tablename__ = 'layer_tag'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    slug = db.Column(db.String(48), nullable=False)
    label = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(7), nullable=True)
    created_by_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    layer = db.relationship('Layer', backref=db.backref('layer_tags', lazy='dynamic'))
    created_by = db.relationship('User', backref=db.backref('layer_tags_created', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('layer_id', 'slug', name='uq_layer_tag_layer_slug'),
        db.Index('idx_layer_tag_layer_slug', 'layer_id', 'slug'),
    )

    def to_dict(self, link_counts=None):
        d = {
            'id': self.id,
            'layer_id': self.layer_id,
            'slug': self.slug,
            'label': self.label,
            'description': self.description,
            'color': self.color,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if link_counts is not None:
            d['artifact_count'] = int(link_counts.get('artifact', 0))
            d['submission_count'] = int(link_counts.get('submission', 0))
            d['link_count'] = d['artifact_count'] + d['submission_count']
        return d


class LayerTagLink(db.Model):
    __tablename__ = 'layer_tag_link'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    tag_id = db.Column(db.String(36), db.ForeignKey('layer_tag.id'), nullable=False, index=True)
    subject_type = db.Column(db.String(32), nullable=False, index=True)
    subject_id = db.Column(db.String(36), nullable=False, index=True)
    created_by_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    tag = db.relationship('LayerTag', backref=db.backref('links', lazy='dynamic'))
    created_by = db.relationship('User', backref=db.backref('layer_tag_links_created', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('subject_type', 'subject_id', 'tag_id', name='uq_layer_tag_link_subject_tag'),
        db.Index('idx_layer_tag_link_subject', 'subject_type', 'subject_id'),
    )
