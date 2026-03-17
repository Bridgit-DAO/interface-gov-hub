"""Bridge models: Bridge, BridgeSession. Web2 bridges between content (URL + text/image/video/audio)."""
from datetime import datetime, timedelta
from uuid import uuid4

from extensions import db


class Bridge(db.Model):
    """A bridge between two content references (source and target). BRC222-compatible."""
    __tablename__ = 'bridge'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    name = db.Column(db.String(255), nullable=False)

    # Source content reference
    source_url = db.Column(db.String(2000), nullable=False, index=True)
    source_content_type = db.Column(db.String(20), nullable=False)  # text, image, video, audio
    source_text_excerpt = db.Column(db.Text, nullable=True)
    source_media_url = db.Column(db.String(2000), nullable=True)
    source_media_alt = db.Column(db.String(500), nullable=True)
    source_name = db.Column(db.String(255), nullable=True)
    source_page_title = db.Column(db.String(500), nullable=True)
    source_selector = db.Column(db.String(500), nullable=True)
    source_video_timestamp = db.Column(db.Integer, nullable=True)

    # Target content reference
    target_url = db.Column(db.String(2000), nullable=False, index=True)
    target_content_type = db.Column(db.String(20), nullable=False)
    target_text_excerpt = db.Column(db.Text, nullable=True)
    target_media_url = db.Column(db.String(2000), nullable=True)
    target_media_alt = db.Column(db.String(500), nullable=True)
    target_name = db.Column(db.String(255), nullable=True)
    target_page_title = db.Column(db.String(500), nullable=True)
    target_selector = db.Column(db.String(500), nullable=True)
    target_video_timestamp = db.Column(db.Integer, nullable=True)

    # Relationship
    relationship = db.Column(db.String(50), nullable=False, index=True)
    # cites, contradicts, supports, extends, timeline, related (extensible)
    explanation = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    inscription_id = db.Column(db.String(255), nullable=True, index=True)
    inscribed_at = db.Column(db.DateTime, nullable=True)

    creator = db.relationship('User', backref=db.backref('bridges_created', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'source': {
                'url': self.source_url,
                'content_type': self.source_content_type,
                'text_excerpt': self.source_text_excerpt,
                'media_url': self.source_media_url,
                'media_alt': self.source_media_alt,
                'name': self.source_name,
                'page_title': self.source_page_title,
                'selector': self.source_selector,
                'video_timestamp': self.source_video_timestamp,
            },
            'target': {
                'url': self.target_url,
                'content_type': self.target_content_type,
                'text_excerpt': self.target_text_excerpt,
                'media_url': self.target_media_url,
                'media_alt': self.target_media_alt,
                'name': self.target_name,
                'page_title': self.target_page_title,
                'selector': self.target_selector,
                'video_timestamp': self.target_video_timestamp,
            },
            'relationship': self.relationship,
            'explanation': self.explanation,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'inscription_id': self.inscription_id,
            'inscribed_at': self.inscribed_at.isoformat() if self.inscribed_at else None,
        }


class BridgeSession(db.Model):
    """Active bridge-making session for extension flow. 1-hour expiry."""
    __tablename__ = 'bridge_session'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    source_content = db.Column(db.JSON, nullable=True)
    target_content = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(20), default='open', nullable=False, index=True)
    # open, source_set, target_set, complete

    user = db.relationship('User', backref=db.backref('bridge_sessions', lazy='dynamic'))

    @property
    def is_expired(self):
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @classmethod
    def create_for_user(cls, user_id):
        """Create a new session with 1-hour expiry."""
        session = cls(
            user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        return session

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'source_content': self.source_content,
            'target_content': self.target_content,
            'status': self.status,
            'is_expired': self.is_expired,
        }
