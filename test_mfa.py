"""Tests for TOTP MFA enrollment, verification, and login gate."""
import os
import sys
from unittest.mock import patch
from uuid import uuid4

import pyotp
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def app():
    from app import app as flask_app
    return flask_app


def _create_user(app, *, with_mfa=False):
    from extensions import db
    from models import User
    from models.mfa import UserMfaDevice
    from services.mfa import confirm_device, encrypt_totp_secret, start_device_enrollment

    user_id = str(uuid4())
    suffix = user_id[:8]
    secret = pyotp.random_base32()
    with app.app_context():
        db.create_all()
        user = User(
            id=user_id,
            public_id=str(uuid4()),
            username=f'mfa_{suffix}',
            handle=f'mfa_{suffix}',
            email=f'mfa-{suffix}@example.test',
            web3authVerifierId=f'web3auth-mfa-{suffix}',
            role='user',
        )
        db.session.add(user)
        db.session.commit()
        if with_mfa:
            device, _, _ = start_device_enrollment(user_id, 'Test phone')
            row = UserMfaDevice.query.get(device.id)
            row.secret_ciphertext = encrypt_totp_secret(secret)
            db.session.commit()
            confirm_device(user_id, device.id, pyotp.TOTP(secret).now())
    return {
        'userId': user_id,
        'username': f'mfa_{suffix}',
        'secret': secret,
        'web3authVerifierId': f'web3auth-mfa-{suffix}',
        'email': f'mfa-{suffix}@example.test',
    }


def _cleanup_user(app, user_id):
    from extensions import db
    from models import User
    from models.mfa import UserMfaChallenge, UserMfaDevice, UserMfaRecoveryCode
    from sqlalchemy import text

    with app.app_context():
        try:
            UserMfaChallenge.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            UserMfaRecoveryCode.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            UserMfaDevice.query.filter_by(user_id=user_id).delete(synchronize_session=False)
            db.session.execute(
                text('DELETE FROM layer_member WHERE user_id = :uid'),
                {'uid': user_id},
            )
            db.session.execute(
                text('DELETE FROM working_group_member WHERE user_id = :uid'),
                {'uid': user_id},
            )
            User.query.filter_by(id=user_id).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()


def test_mfa_enroll_confirm_and_status(app):
    from extensions import db
    from models.mfa import UserMfaDevice
    from services.mfa import (
        confirm_device,
        encrypt_totp_secret,
        mfa_status,
        start_device_enrollment,
        user_mfa_enabled,
    )

    user = _create_user(app)
    secret = pyotp.random_base32()
    try:
        with app.app_context():
            device, _, uri = start_device_enrollment(user['userId'], 'Phone')
            assert 'otpauth' in uri
            row = UserMfaDevice.query.get(device.id)
            row.secret_ciphertext = encrypt_totp_secret(secret)
            db.session.commit()
            assert not user_mfa_enabled(user['userId'])
            ok, recovery = confirm_device(user['userId'], device.id, pyotp.TOTP(secret).now())
            assert ok is True
            assert recovery is not None
            assert len(recovery) == 10
            assert user_mfa_enabled(user['userId'])
            status = mfa_status(user['userId'])
            assert status['enabled'] is True
            assert status['deviceCount'] == 1
            assert status['recoveryCodesRemaining'] == 10
    finally:
        _cleanup_user(app, user['userId'])


def test_web3auth_login_requires_mfa_when_enabled(app):
    from models.mfa import UserMfaDevice
    from services.mfa import decrypt_totp_secret

    user = _create_user(app, with_mfa=True)
    fake_claims = {
        'userId': user['web3authVerifierId'],
        'email': user['email'],
        'name': 'MFA User',
        'groupedAuthConnectionId': 'web3auth-google-sapphire-devnet',
    }
    client = app.test_client()
    try:
        with patch('services.web3auth_verify.verify_web3auth_id_token', return_value=fake_claims), \
             patch('services.auth_layer_membership.ensure_auth_layer_memberships'):
            response = client.post(
                '/api/auth/web3auth',
                json={'idToken': 'fake.jwt.token'},
                content_type='application/json',
            )
        assert response.status_code == 200
        data = response.get_json()
        assert data['mfaRequired'] is True
        assert data.get('challengeToken')

        with app.app_context():
            device = UserMfaDevice.query.filter_by(user_id=user['userId']).first()
            code = pyotp.TOTP(decrypt_totp_secret(device.secret_ciphertext)).now()
        with patch('services.auth_layer_membership.ensure_auth_layer_memberships'):
            verify_resp = client.post(
                '/api/mfa/verify-login',
                json={'challengeToken': data['challengeToken'], 'code': code},
                content_type='application/json',
            )
        assert verify_resp.status_code == 200
        assert verify_resp.get_json()['success'] is True
        me = client.get('/api/user/me')
        assert me.status_code == 200
    finally:
        _cleanup_user(app, user['userId'])


def test_recovery_code_login(app):
    from services.mfa import create_challenge, regenerate_recovery_codes, verify_login_challenge

    user = _create_user(app, with_mfa=True)
    try:
        with app.app_context():
            codes = regenerate_recovery_codes(user['userId'])
            backup = codes[0]
            challenge = create_challenge(user['userId'])
            uid, err = verify_login_challenge(challenge.id, backup)
            assert uid == user['userId']
            assert err == ''
    finally:
        _cleanup_user(app, user['userId'])
