"""MFA models: TOTP devices, recovery codes, login challenges."""
from datetime import datetime
from uuid import uuid4

from extensions import db


class UserMfaDevice(db.Model):
    """Authenticator app enrollment (TOTP)."""
    __tablename__ = 'user_mfa_device'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    label = db.Column(db.String(100), nullable=False, default='Authenticator')
    secret_ciphertext = db.Column(db.Text, nullable=False)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref=db.backref('mfa_devices', lazy='dynamic'))

    @property
    def is_active(self):
        return self.confirmed_at is not None and self.revoked_at is None


class UserMfaRecoveryCode(db.Model):
    """Single-use backup code (bcrypt hash only)."""
    __tablename__ = 'user_mfa_recovery_code'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('mfa_recovery_codes', lazy='dynamic'))


class UserMfaChallenge(db.Model):
    """Short-lived MFA step during login."""
    __tablename__ = 'user_mfa_challenge'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False, index=True)
    client_id = db.Column(db.String(50), nullable=False, default='govhub')
    expires_at = db.Column(db.DateTime, nullable=False)
    consumed_at = db.Column(db.DateTime, nullable=True)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('mfa_challenges', lazy='dynamic'))
