"""Identity models: User, UserFollow, HypothesisAccount."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    public_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid4()))
    username = db.Column(db.String(50), unique=True, index=True)
    password_hash = db.Column(db.String(255))

    # Web3Auth fields
    web3authVerifierId = db.Column(db.String(255), unique=True, index=True)
    typeOfLogin = db.Column(db.String(50))  # 'google', 'wallet', 'twitter', 'email_passwordless'

    # Display name system (user-editable)
    displayName = db.Column(db.String(50))
    displayNameSetAt = db.Column(db.DateTime)

    # OAuth data (read-only reference)
    oauthName = db.Column(db.String(100))
    name = db.Column(db.String(100))  # Legacy field
    email = db.Column(db.String(100), unique=True, index=True)
    profileImage = db.Column(db.String(500))

    # Wallet data
    evmAddress = db.Column(db.String(42), unique=True, index=True)
    solanaAddress = db.Column(db.String(44), unique=True, index=True)

    # Handle (unique identifier)
    handle = db.Column(db.String(50), unique=True, index=True)

    # Profile customization
    banner_image = db.Column(db.String(500))
    headline = db.Column(db.String(200))
    bio = db.Column(db.Text)
    social_links = db.Column(db.Text)  # JSON string

    # Referral system
    referral_code = db.Column(db.String(50), unique=True, index=True)

    # Other fields
    role = db.Column(db.String(20), default='user')  # admin, editor, user
    theme = db.Column(db.String(10), default='dark')  # light, dark, auto
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)


class UserFollow(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    draft_name = db.Column(db.String(100), nullable=False)
    followed_at = db.Column(db.DateTime, default=datetime.utcnow)
    notification_level = db.Column(db.String(20), default='all')  # all, significant, major, comments, none

    user = db.relationship('User', backref=db.backref('follows', lazy=True))

    __table_args__ = (db.UniqueConstraint('user_id', 'draft_name', name='unique_user_draft_follow'),)

    NOTIFICATION_LEVELS = {
        'all': 'All changes and comments',
        'significant': 'Only significant changes (state changes, new revisions)',
        'major': 'Only major changes (IESG actions, RFC publication)',
        'comments': 'Only comments',
        'none': 'No notifications (just tracking)'
    }


class HypothesisAccount(db.Model):
    """Links Meta-Layer users to their Hypothesis accounts"""
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, unique=True)
    hypothesis_username = db.Column(db.String(100), nullable=False, unique=True)
    hypothesis_userid = db.Column(db.String(100), nullable=False, unique=True)  # acct:username@authority
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('hypothesis_account', uselist=False))


class UserLinkedAccount(db.Model):
    """OAuth-linked social accounts for profile (Google, GitHub, Twitter, etc.)."""
    __tablename__ = 'user_linked_account'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    provider = db.Column(db.String(50), nullable=False, index=True)
    provider_user_id = db.Column(db.String(255), nullable=False, index=True)
    profile_url = db.Column(db.String(500))
    avatar_url = db.Column(db.String(500))
    display_name = db.Column(db.String(200))
    access_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('linked_accounts', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
        db.UniqueConstraint('provider', 'provider_user_id', name='uq_provider_user'),
    )
