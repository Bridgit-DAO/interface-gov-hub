"""Layer-scoped tags for artifacts (folksonomy labels)."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class ArtifactTag(db.Model):
    __tablename__ = 'artifact_tag'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    slug = db.Column(db.String(48), nullable=False)
    label = db.Column(db.String(64), nullable=False)
    description = db.Column(db.Text, nullable=True)
    color = db.Column(db.String(7), nullable=True)
    created_by_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    layer = db.relationship('Layer', backref=db.backref('artifact_tags', lazy='dynamic'))
    created_by = db.relationship('User', backref=db.backref('artifact_tags_created', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('layer_id', 'slug', name='uq_artifact_tag_layer_slug'),
        db.Index('idx_artifact_tag_layer_slug', 'layer_id', 'slug'),
    )

    def to_dict(self, artifact_count=None):
        d = {
            'id': self.id,
            'layer_id': self.layer_id,
            'slug': self.slug,
            'label': self.label,
            'description': self.description,
            'color': self.color,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if artifact_count is not None:
            d['artifact_count'] = artifact_count
        return d


class ArtifactTagLink(db.Model):
    __tablename__ = 'artifact_tag_link'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    artifact_id = db.Column(db.String(36), db.ForeignKey('artifact.id'), nullable=False, index=True)
    tag_id = db.Column(db.String(36), db.ForeignKey('artifact_tag.id'), nullable=False, index=True)
    created_by_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    artifact = db.relationship('Artifact', backref=db.backref('tag_links', lazy='dynamic', cascade='all, delete-orphan'))
    tag = db.relationship('ArtifactTag', backref=db.backref('artifact_links', lazy='dynamic'))
    created_by = db.relationship('User', backref=db.backref('artifact_tag_links_created', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('artifact_id', 'tag_id', name='uq_artifact_tag_link'),
    )
