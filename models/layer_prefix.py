"""LayerPrefix model: per-layer two-letter draft prefix (e.g. "ML", "CL")."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from extensions import db, StorageBoolean


class LayerPrefix(db.Model):
    """Two-letter draft prefix scoped to a layer.

    Each prefix is globally unique across the entire Gov Hub (only one layer
    can claim a given "ML" / "CL" / etc). A layer has at least one
    ``is_default`` prefix which the site header chip will surface to users
    who are members of that layer.
    """

    __tablename__ = 'layer_prefix'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    layer_id = db.Column(
        db.String(36),
        db.ForeignKey('layer.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    prefix = db.Column(db.String(2), nullable=False, unique=True, index=True)
    is_default = db.Column(
        StorageBoolean(),
        nullable=False,
        default=False,
    )
    created_by = db.Column(
        db.String(36),
        db.ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'layer_id': self.layer_id,
            'prefix': self.prefix,
            'is_default': bool(self.is_default),
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f'<LayerPrefix {self.prefix} layer={self.layer_id} default={bool(self.is_default)}>'
