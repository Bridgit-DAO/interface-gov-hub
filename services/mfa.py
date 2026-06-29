"""TOTP MFA: device CRUD, recovery codes, login challenges."""
from __future__ import annotations

import base64
import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import pyotp
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models.mfa import UserMfaChallenge, UserMfaDevice, UserMfaRecoveryCode
from services.utils import check_rate_limit

TOTP_ISSUER = 'Gov Hub'
RECOVERY_CODE_COUNT = 10
CHALLENGE_TTL_SECONDS = 600
MAX_CHALLENGE_ATTEMPTS = 5
RECOVERY_CHARSET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'

_RECOVERY_NORMALIZE = re.compile(r'[^A-Z0-9]')


def _fernet():
    from cryptography.fernet import Fernet

    material = (
        os.environ.get('GOVHUB_WALLET_ENCRYPTION_KEY')
        or os.environ.get('SECRET_KEY')
        or ''
    ).strip()
    if not material:
        raise RuntimeError(
            'GOVHUB_WALLET_ENCRYPTION_KEY or SECRET_KEY required for MFA encryption'
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode()).digest())
    return Fernet(key)


def encrypt_totp_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_totp_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def user_mfa_enabled(user_id: str) -> bool:
    return (
        UserMfaDevice.query.filter_by(user_id=user_id, revoked_at=None)
        .filter(UserMfaDevice.confirmed_at.isnot(None))
        .count()
        > 0
    )


def list_devices(user_id: str) -> list:
    rows = (
        UserMfaDevice.query.filter_by(user_id=user_id, revoked_at=None)
        .order_by(UserMfaDevice.created_at.asc())
        .all()
    )
    return [
        {
            'id': d.id,
            'label': d.label,
            'confirmed': d.confirmed_at is not None,
            'confirmedAt': d.confirmed_at.isoformat() if d.confirmed_at else None,
            'lastUsedAt': d.last_used_at.isoformat() if d.last_used_at else None,
            'createdAt': d.created_at.isoformat() if d.created_at else None,
        }
        for d in rows
    ]


def mfa_status(user_id: str) -> dict:
    devices = list_devices(user_id)
    active = [d for d in devices if d['confirmed']]
    unused_codes = recovery_codes_remaining(user_id)
    return {
        'enabled': len(active) > 0,
        'deviceCount': len(active),
        'pendingDeviceCount': len(devices) - len(active),
        'devices': devices,
        'recoveryCodesRemaining': unused_codes,
    }


def _account_label(user) -> str:
    return (user.email or user.username or user.id or 'user').strip()


def build_otpauth_uri(*, account: str, secret: str, label: str) -> str:
    name = f'{TOTP_ISSUER}:{account}'
    return pyotp.totp.TOTP(secret).provisioning_uri(name=name, issuer_name=TOTP_ISSUER)


def start_device_enrollment(user_id: str, label: str = 'Authenticator') -> Tuple[UserMfaDevice, str, str]:
    from models import User

    user = User.query.get(user_id)
    if not user:
        raise ValueError('User not found')
    clean_label = (label or 'Authenticator').strip()[:100] or 'Authenticator'
    secret = pyotp.random_base32()
    device = UserMfaDevice(
        user_id=user_id,
        label=clean_label,
        secret_ciphertext=encrypt_totp_secret(secret),
    )
    db.session.add(device)
    db.session.commit()
    uri = build_otpauth_uri(account=_account_label(user), secret=secret, label=clean_label)
    return device, secret, uri


def confirm_device(user_id: str, device_id: str, code: str) -> Tuple[bool, Optional[List[str]]]:
    device = UserMfaDevice.query.filter_by(id=device_id, user_id=user_id, revoked_at=None).first()
    if not device:
        return False, None
    if device.confirmed_at is not None:
        return False, None
    if not _verify_device_code(device, code):
        return False, None
    device.confirmed_at = datetime.utcnow()
    db.session.commit()

    recovery_codes = None
    if recovery_codes_remaining(user_id) == 0:
        recovery_codes = regenerate_recovery_codes(user_id)
    return True, recovery_codes


def rename_device(user_id: str, device_id: str, label: str) -> bool:
    device = UserMfaDevice.query.filter_by(
        id=device_id, user_id=user_id, revoked_at=None
    ).first()
    if not device or not device.confirmed_at:
        return False
    clean = (label or '').strip()[:100]
    if not clean:
        return False
    device.label = clean
    db.session.commit()
    return True


def revoke_device(user_id: str, device_id: str, *, code: str) -> Tuple[bool, str]:
    """Remove a device; requires valid TOTP or recovery code."""
    if not verify_user_code(user_id, code):
        return False, 'Invalid verification code'
    device = UserMfaDevice.query.filter_by(
        id=device_id, user_id=user_id, revoked_at=None
    ).first()
    if not device:
        return False, 'Device not found'
    device.revoked_at = datetime.utcnow()
    db.session.commit()
    return True, ''


def _verify_device_code(device: UserMfaDevice, code: str) -> bool:
    try:
        secret = decrypt_totp_secret(device.secret_ciphertext)
        totp = pyotp.TOTP(secret)
        normalized = (code or '').strip().replace(' ', '')
        if not totp.verify(normalized, valid_window=1):
            return False
        device.last_used_at = datetime.utcnow()
        db.session.commit()
        return True
    except Exception:
        return False


def verify_user_code(user_id: str, code: str) -> bool:
    """Accept TOTP from any active device or a recovery code."""
    raw = (code or '').strip()
    if not raw:
        return False
    if _looks_like_recovery_code(raw):
        return _consume_recovery_code(user_id, raw)
    devices = (
        UserMfaDevice.query.filter_by(user_id=user_id, revoked_at=None)
        .filter(UserMfaDevice.confirmed_at.isnot(None))
        .all()
    )
    for device in devices:
        if _verify_device_code(device, raw):
            return True
    return False


def _looks_like_recovery_code(code: str) -> bool:
    normalized = _RECOVERY_NORMALIZE.sub('', code.upper())
    return len(normalized) >= 8 and not normalized.isdigit()


def _format_recovery_code(raw: str) -> str:
    return f'{raw[:4]}-{raw[4:8]}'


def _generate_recovery_code_raw() -> str:
    return ''.join(secrets.choice(RECOVERY_CHARSET) for _ in range(8))


def regenerate_recovery_codes(user_id: str) -> List[str]:
    UserMfaRecoveryCode.query.filter_by(user_id=user_id, used_at=None).delete(
        synchronize_session=False
    )
    plaintext_codes = []
    for _ in range(RECOVERY_CODE_COUNT):
        raw = _generate_recovery_code_raw()
        formatted = _format_recovery_code(raw)
        plaintext_codes.append(formatted)
        db.session.add(
            UserMfaRecoveryCode(
                user_id=user_id,
                code_hash=generate_password_hash(formatted),
            )
        )
    db.session.commit()
    return plaintext_codes


def recovery_codes_remaining(user_id: str) -> int:
    return UserMfaRecoveryCode.query.filter_by(user_id=user_id, used_at=None).count()


def _consume_recovery_code(user_id: str, code: str) -> bool:
    normalized = _RECOVERY_NORMALIZE.sub('', code.upper())
    if len(normalized) < 8:
        return False
    formatted = _format_recovery_code(normalized[:8])
    rows = UserMfaRecoveryCode.query.filter_by(user_id=user_id, used_at=None).all()
    for row in rows:
        if check_password_hash(row.code_hash, formatted):
            row.used_at = datetime.utcnow()
            db.session.commit()
            return True
    return False


def create_challenge(user_id: str, client_id: str = 'govhub') -> UserMfaChallenge:
    challenge = UserMfaChallenge(
        user_id=user_id,
        client_id=(client_id or 'govhub').strip()[:50] or 'govhub',
        expires_at=datetime.utcnow() + timedelta(seconds=CHALLENGE_TTL_SECONDS),
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def verify_login_challenge(challenge_id: str, code: str) -> Tuple[Optional[str], str]:
    """Verify MFA during login. Returns (user_id, error_message)."""
    rate_key = f'mfa_verify_{challenge_id}'
    if not check_rate_limit(rate_key, max_requests=MAX_CHALLENGE_ATTEMPTS, window_seconds=900):
        return None, 'Too many attempts. Please sign in again.'

    challenge = UserMfaChallenge.query.get(challenge_id)
    if not challenge or challenge.consumed_at is not None:
        return None, 'Invalid or expired challenge'
    if challenge.expires_at < datetime.utcnow():
        return None, 'Challenge expired. Please sign in again.'
    if challenge.failed_attempts >= MAX_CHALLENGE_ATTEMPTS:
        return None, 'Too many failed attempts. Please sign in again.'

    if not verify_user_code(challenge.user_id, code):
        challenge.failed_attempts += 1
        db.session.commit()
        return None, 'Invalid code'

    challenge.consumed_at = datetime.utcnow()
    db.session.commit()
    return challenge.user_id, ''
