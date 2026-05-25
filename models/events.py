"""Event models: EventLog, StatusChange."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class StatusChange(db.Model):
    """Audit trail for status changes across all entities"""
    __tablename__ = 'status_change'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    entity_type = db.Column(db.String(20), nullable=False)
    entity_id = db.Column(db.String(50), nullable=False, index=True)
    field_name = db.Column(db.String(50), nullable=False)
    from_value = db.Column(db.String(100), nullable=True)
    to_value = db.Column(db.String(100), nullable=False)
    note = db.Column(db.Text, nullable=True)
    changed_by_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    changed_by = db.relationship('User', backref='status_changes')

    __table_args__ = (
        db.Index('idx_status_change_entity', 'entity_type', 'entity_id'),
        db.Index('idx_status_change_changed_at', 'changed_at'),
    )


class EventLog(db.Model):
    """Append-only governance event log. Powers activity feeds, notifications, audit trails."""
    __tablename__ = 'event_log'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    event_type = db.Column(db.String(50), nullable=False, index=True)
    actor_type = db.Column(db.String(30), nullable=True)   # user, system
    actor_id = db.Column(db.String(50), nullable=True, index=True)
    subject_type = db.Column(db.String(30), nullable=True)
    subject_id = db.Column(db.String(50), nullable=True, index=True)
    layer_id = db.Column(db.String(36), db.ForeignKey('layer.id'), nullable=True, index=True)
    payload_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    layer = db.relationship('Layer', backref=db.backref('event_logs', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_event_log_layer_created', 'layer_id', 'created_at'),
    )
