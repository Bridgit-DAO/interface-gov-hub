"""Artifact collections (e.g. constitution sets) — Unified Phase I grouping primitive."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class ArtifactCollection(db.Model):
    __tablename__ = 'artifact_collection'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    creator_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    layer = db.relationship('Layer', backref=db.backref('artifact_collections', lazy='dynamic'))
    creator = db.relationship('User', backref=db.backref('artifact_collections_created', lazy='dynamic'))

    def to_dict(self, include_items=False):
        d = {
            'id': self.id,
            'layer_id': self.layer_id,
            'title': self.title,
            'description': self.description,
            'creator_user_id': self.creator_user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_items:
            items = ArtifactCollectionItem.query.filter_by(collection_id=self.id).order_by(
                ArtifactCollectionItem.created_at.asc()
            ).all()
            d['artifact_ids'] = [i.artifact_id for i in items]
        return d


class ArtifactCollectionItem(db.Model):
    __tablename__ = 'artifact_collection_item'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    collection_id = db.Column(db.String(36), db.ForeignKey('artifact_collection.id'), nullable=False, index=True)
    artifact_id = db.Column(db.String(36), db.ForeignKey('artifact.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    collection = db.relationship('ArtifactCollection', backref=db.backref('items', lazy='dynamic'))
    artifact = db.relationship('Artifact', backref=db.backref('collection_memberships', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('collection_id', 'artifact_id', name='uq_artifact_collection_item'),
    )
