"""Organization-owned evidence; User and Layer remain identity authorities."""
from datetime import datetime
from uuid import uuid4
from extensions import db


def uuid():
    return str(uuid4())


class CIOrganization(db.Model):
    __tablename__ = 'ci_organization'
    id = db.Column(db.String(36), primary_key=True, default=uuid)
    name = db.Column(db.String(200), nullable=False)
    created_by = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)


class CIMembership(db.Model):
    __tablename__ = 'ci_membership'
    organization_id = db.Column(db.String(36), db.ForeignKey('ci_organization.id'), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), primary_key=True)
    role = db.Column(db.String(20), nullable=False)
    __table_args__ = (db.CheckConstraint("role IN ('administrator','steward','contributor')"),)


class CIProgram(db.Model):
    __tablename__ = 'ci_program'
    id = db.Column(db.String(36), primary_key=True, default=uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey('ci_organization.id'), nullable=False, index=True)
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    lifecycle = db.Column(db.String(20), nullable=False, default='unknown')
    revision = db.Column(db.Integer, nullable=False, default=1)
    changed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    effective_date = db.Column(db.Date, nullable=True)
    __table_args__ = (db.CheckConstraint("lifecycle IN ('unknown','planned','active','paused','completed','discontinued')"),)


class CISource(db.Model):
    """Immutable contribution/version; originals have no public blob URL."""
    __tablename__ = 'ci_source'
    id = db.Column(db.String(36), primary_key=True, default=uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey('ci_organization.id'), nullable=False, index=True)
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    program_id = db.Column(db.String(36), db.ForeignKey('ci_program.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    original = db.Column(db.LargeBinary, nullable=True)
    visibility = db.Column(db.String(20), nullable=False, default='private')
    state = db.Column(db.String(20), nullable=False, default='queued')
    revision = db.Column(db.Integer, nullable=False, default=1)
    extractor_version = db.Column(db.String(40), nullable=False, default='passages-v1')
    attempts = db.Column(db.Integer, nullable=False, default=0)
    warning = db.Column(db.Text, nullable=True)
    error = db.Column(db.String(300), nullable=True)
    submitted_by = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    published_date = db.Column(db.Date, nullable=True)
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'layer_id', 'program_id', 'digest', name='uq_ci_source_delivery'),
        db.CheckConstraint("visibility IN ('private','layer')"),
        db.CheckConstraint("state IN ('queued','processing','needs_review','ready','failed','withdrawn')"),
    )


class CIClaim(db.Model):
    __tablename__ = 'ci_claim'
    id = db.Column(db.String(36), primary_key=True, default=uuid)
    source_id = db.Column(db.String(36), db.ForeignKey('ci_source.id'), nullable=False, index=True)
    locator = db.Column(db.String(120), nullable=False)
    evidence = db.Column(db.Text, nullable=False)
    statement = db.Column(db.Text, nullable=False)
    standing = db.Column(db.String(20), nullable=False, default='proposed')
    kind = db.Column(db.String(20), nullable=False, default='description')
    topic = db.Column(db.String(100), nullable=True)
    reviewed_by = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    __table_args__ = (
        db.UniqueConstraint('source_id', 'locator', name='uq_ci_claim_locator'),
        db.CheckConstraint("standing IN ('proposed','confirmed','rejected','disputed')"),
        db.CheckConstraint("kind IN ('description','need','offer')"),
    )


class CIAudit(db.Model):
    """Private content-free events, never exposed through the public activity feed."""
    __tablename__ = 'ci_audit'
    id = db.Column(db.String(36), primary_key=True, default=uuid)
    organization_id = db.Column(db.String(36), db.ForeignKey('ci_organization.id'), nullable=False, index=True)
    actor_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)
    target_id = db.Column(db.String(36), nullable=False)
    action = db.Column(db.String(60), nullable=False)
    revision = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CIRoom(db.Model):
    """Fixed audience; derived content is readable only while every dependency is valid."""
    __tablename__ = 'ci_room'
    id = db.Column(db.String(36), primary_key=True, default=uuid)
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=False, index=True)
    created_by = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    members = db.Column(db.JSON, nullable=False)  # immutable user IDs, no room-expansion API
    evidence = db.Column(db.JSON, nullable=False)  # claim/source/program IDs and exact revisions
    request_key = db.Column(db.String(64), nullable=False)
    revision = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('layer_id', 'created_by', 'request_key', name='uq_ci_room_request'),)


class CIRoomMessage(db.Model):
    __tablename__ = 'ci_room_message'
    id = db.Column(db.String(36), primary_key=True, default=uuid)
    room_id = db.Column(db.String(36), db.ForeignKey('ci_room.id'), nullable=False, index=True)
    author_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default='human')
    body = db.Column(db.Text, nullable=False)
    request_key = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('room_id', 'author_id', 'request_key', name='uq_ci_message_request'),)


class CIAction(db.Model):
    __tablename__ = 'ci_action'
    id = db.Column(db.String(36), primary_key=True, default=uuid)
    room_id = db.Column(db.String(36), db.ForeignKey('ci_room.id'), nullable=False, index=True)
    text = db.Column(db.Text, nullable=False)
    proposed_by = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    owner_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='proposed')
    revision = db.Column(db.Integer, nullable=False, default=1)
    request_key = db.Column(db.String(64), nullable=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('room_id', 'proposed_by', 'request_key', name='uq_ci_action_request'),
        db.CheckConstraint("status IN ('proposed','accepted','declined')"),
    )
