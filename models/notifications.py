"""Event subscriptions and in-app notifications (document-follow / EventLog delivery)."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class UserEventSubscription(db.Model):
    """Exact EventLog event_type × subject (e.g. draft name) × user; channel flags."""

    __tablename__ = 'user_event_subscription'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)
    subject_type = db.Column(db.String(40), nullable=False, index=True)
    subject_id = db.Column(db.String(200), nullable=False, index=True)
    deliver_in_app = db.Column(db.Boolean, nullable=False, default=True)
    deliver_email = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('event_subscriptions', lazy='dynamic'))

    __table_args__ = (
        db.Index(
            'idx_ues_user_subject_event',
            'user_id',
            'subject_type',
            'subject_id',
            'event_type',
        ),
    )


class UserNotification(db.Model):
    """In-app notification row; optional link to EventLog and email_sent_at for digests."""

    __tablename__ = 'user_notification'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    event_log_id = db.Column(db.String(36), db.ForeignKey('event_log.id'), nullable=True, index=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=True)
    link_url = db.Column(db.String(500), nullable=True)
    read_at = db.Column(db.DateTime, nullable=True)
    email_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic'))
    event_log = db.relationship('EventLog', backref=db.backref('user_notifications', lazy='dynamic'))
