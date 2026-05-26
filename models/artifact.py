"""Artifact models: Submission, Artifact, ArtifactRelation, Comment, DocumentHistory, SiteConfig, InscriptionOrder."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import or_, func
from extensions import db


class SiteConfig(db.Model):
    """Key-value store for admin-editable config (e.g. inscription pricing)."""
    __tablename__ = 'site_config'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)


class InscriptionOrder(db.Model):
    """Stripe payment for inscription via wizard flow."""
    __tablename__ = 'inscription_order'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=True, index=True)
    status = db.Column(db.String(30), default='pending_payment')
    content_text = db.Column(db.Text, nullable=True)
    content_filename = db.Column(db.String(255), nullable=True)
    page_count = db.Column(db.Integer, default=1)
    image_count = db.Column(db.Integer, default=0)
    phone_number = db.Column(db.String(30), nullable=True)
    country_code = db.Column(db.String(5), nullable=True)
    phone_verified = db.Column(db.Boolean, default=False)
    tier = db.Column(db.Integer, default=1)
    base_price_usd = db.Column(db.Numeric(10, 2))
    discount_pct = db.Column(db.Integer, default=0)
    final_price_usd = db.Column(db.Numeric(10, 2))
    stripe_payment_intent_id = db.Column(db.String(100), nullable=True)
    stripe_client_secret = db.Column(db.String(200), nullable=True)
    btc_taproot_address = db.Column(db.String(255), nullable=True)
    unisat_order_id = db.Column(db.String(255), nullable=True)
    inscription_id = db.Column(db.String(255), nullable=True)
    acknowledged_timing = db.Column(db.Boolean, default=False)
    notify_when_ready = db.Column(db.Boolean, default=False)
    title = db.Column(db.String(255), nullable=True)
    authors = db.Column(db.JSON, nullable=True)
    abstract = db.Column(db.Text, nullable=True)
    workgroup = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)


class Comment(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    draft_name = db.Column(db.String(255), index=True)  # Legacy: keep for backcompat with document comments
    artifact_id = db.Column(db.String(36), db.ForeignKey('artifact.id'), nullable=True, index=True)  # New: artifact comments
    text = db.Column(db.Text)
    author = db.Column(db.String(100))  # Legacy: display name string
    author_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)  # New: proper user ref
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    parent_id = db.Column(db.String(36), db.ForeignKey('comment.id'), nullable=True)
    edited_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    original_text = db.Column(db.Text, nullable=True)

    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True)
    artifact = db.relationship('Artifact', backref=db.backref('comments', lazy='dynamic'), foreign_keys=[artifact_id])
    author_user = db.relationship('User', backref=db.backref('comments_authored', lazy='dynamic'), foreign_keys=[author_user_id])


class DocumentHistory(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    draft_name = db.Column(db.String(255), index=True)
    action = db.Column(db.String(50))
    user = db.Column(db.String(100))
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Artifact(db.Model):
    """Central knowledge object per artifact_specification.md. Submission linked via artifact_id."""
    __tablename__ = 'artifact'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=True, index=True)
    creator_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    artifact_type = db.Column(db.String(50), nullable=False, index=True)
    artifact_subtype = db.Column(db.String(50), nullable=True, index=True)
    title = db.Column(db.String(255), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    body = db.Column(db.Text, nullable=True)
    uri = db.Column(db.String(500), nullable=True)
    source_language = db.Column(db.String(20), nullable=True)
    current_language = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), default='draft', nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)
    # Knowledge layer (contribution type + optional scaffold) — see services/knowledge_layer.py
    knowledge_form = db.Column(db.String(30), nullable=True, index=True)
    knowledge_scaffold = db.Column(db.JSON, nullable=True)

    layer = db.relationship('Layer', backref=db.backref('artifacts', lazy='dynamic'))
    creator = db.relationship('User', backref=db.backref('created_artifacts', lazy='dynamic'))

    @property
    def public_ref(self):
        """Public artifact reference with io suffix (artifact_specification.md)."""
        raw = (self.public_id or self.id or '').replace('-', '')[:8]
        return f"{raw}io" if raw else ""

    def to_dict(self):
        return {
            'id': self.id,
            'public_id': self.public_id,
            'public_ref': self.public_ref,
            'layer_id': self.layer_id,
            'creator_user_id': self.creator_user_id,
            'artifact_type': self.artifact_type,
            'artifact_subtype': getattr(self, 'artifact_subtype', None),
            'title': self.title,
            'summary': self.summary,
            'body': getattr(self, 'body', None),
            'uri': self.uri,
            'source_language': getattr(self, 'source_language', None),
            'current_language': getattr(self, 'current_language', None),
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if getattr(self, 'updated_at', None) else None,
            'knowledge_form': getattr(self, 'knowledge_form', None),
            'knowledge_scaffold': getattr(self, 'knowledge_scaffold', None),
        }


class ArtifactRelation(db.Model):
    """Typed relationships between artifacts."""
    __tablename__ = 'artifact_relation'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    from_object_type = db.Column(db.String(50), nullable=False, index=True)
    from_object_id = db.Column(db.String(100), nullable=False, index=True)
    to_object_type = db.Column(db.String(50), nullable=False, index=True)
    to_object_id = db.Column(db.String(100), nullable=False, index=True)
    relation_type = db.Column(db.String(50), nullable=False, index=True)
    created_by_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    created_by = db.relationship('User', backref=db.backref('artifact_relations_created', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_artifact_relation_from', 'from_object_type', 'from_object_id'),
        db.Index('idx_artifact_relation_to', 'to_object_type', 'to_object_id'),
    )


class Submission(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    title = db.Column(db.String(255))
    authors = db.Column(db.JSON)
    abstract = db.Column(db.Text)
    group = db.Column(db.String(50))
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=True, index=True)
    filename = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    draft_name = db.Column(db.String(255))
    status = db.Column(db.String(20), default='submitted')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    submitted_by = db.Column(db.String(100), default='Anonymous User')
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    ml_number = db.Column(db.String(20), nullable=True)
    content_hash = db.Column(db.String(64), nullable=True, index=True)
    doc_type = db.Column(db.String(10), default='draft')
    pages = db.Column(db.Integer, default=1)
    words = db.Column(db.Integer, default=0)
    sourceType = db.Column(db.String(20), default='file')
    ordinalId = db.Column(db.String(255), nullable=True)
    ordinalContentUrl = db.Column(db.String(500), nullable=True)
    ordinalContentType = db.Column(db.String(100), nullable=True)
    inscriptionNumber = db.Column(db.Integer, nullable=True)
    blockHeight = db.Column(db.Integer, nullable=True)
    inscriptionTimestamp = db.Column(db.DateTime, nullable=True)
    parent_draft_name = db.Column(db.String(255), nullable=True)
    revision_number = db.Column(db.String(10), nullable=True)
    what_changed = db.Column(db.Text, nullable=True)
    is_revision = db.Column(db.Boolean, default=False)
    rfc_number = db.Column(db.Integer, nullable=True)
    inscription_order_id = db.Column(db.String(36), nullable=True, index=True)
    artifact_id = db.Column(db.String(36), db.ForeignKey('artifact.id'), nullable=True, index=True)
    # Model C category: document | template | tool | guide | glossary | policy
    document_category = db.Column(db.String(32), nullable=True, index=True)

    # File-backed submission may show a linked ordinal body in the reader while keeping file + revision history.
    displayBodySource = db.Column(db.String(20), default='file')  # 'file' | 'ordinal'
    displayOrdinalId = db.Column(db.String(255), nullable=True)
    displayOrdinalContentUrl = db.Column(db.String(500), nullable=True)
    displayOrdinalContentType = db.Column(db.String(100), nullable=True)
    displaySwitchedAt = db.Column(db.DateTime, nullable=True)
    displaySwitchedBy = db.Column(db.String(100), nullable=True)

    artifact = db.relationship('Artifact', backref=db.backref('submissions', lazy='dynamic'), foreign_keys=[artifact_id])
