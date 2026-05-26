"""Tests for Web3Auth JWT verification helpers and login endpoint guards."""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_identity_from_web3auth_claims_maps_user_id():
    from services.web3auth_verify import identity_from_web3auth_claims

    claims = {
        'userId': 'alice@example.com',
        'email': 'alice@example.com',
        'name': 'Alice',
        'profileImage': 'https://example.com/a.png',
        'groupedAuthConnectionId': 'web3auth-google-sapphire-devnet',
    }
    identity = identity_from_web3auth_claims(claims)
    assert identity['verifierId'] == 'alice@example.com'
    assert identity['email'] == 'alice@example.com'
    assert identity['name'] == 'Alice'
    assert identity['typeOfLogin'] == 'google'


def test_identity_from_web3auth_claims_requires_user_id():
    from services.web3auth_verify import identity_from_web3auth_claims

    with pytest.raises(ValueError, match='userId'):
        identity_from_web3auth_claims({'email': 'a@b.com'})


def test_web3auth_login_requires_id_token():
    from app import app

    client = app.test_client()
    response = client.post(
        '/api/auth/web3auth',
        json={'verifierId': 'fake-user'},
        content_type='application/json',
    )
    assert response.status_code == 400
    assert response.get_json()['error'] == 'idToken required'


def test_web3auth_login_rejects_invalid_token():
    from app import app
    from jwt.exceptions import InvalidTokenError

    client = app.test_client()
    with patch('services.web3auth_verify.verify_web3auth_id_token', side_effect=InvalidTokenError('bad')):
        response = client.post(
            '/api/auth/web3auth',
            json={'idToken': 'not-a-real-jwt'},
            content_type='application/json',
        )
    assert response.status_code == 401


def test_web3auth_login_rejects_email_collision(monkeypatch):
    from app import app
    from extensions import db
    from models import User

    with app.app_context():
        existing = User.query.filter(User.email.isnot(None)).first()
        if not existing:
            pytest.skip('Need a user with email in DB')
        email = existing.email
        other_verifier = 'brand-new-verifier-id-for-test'

    fake_claims = {
        'userId': other_verifier,
        'email': email,
        'name': 'Attacker',
        'groupedAuthConnectionId': 'web3auth-google-sapphire-devnet',
    }

    client = app.test_client()
    with patch('services.web3auth_verify.verify_web3auth_id_token', return_value=fake_claims):
        response = client.post(
            '/api/auth/web3auth',
            json={'idToken': 'fake.jwt.token'},
            content_type='application/json',
        )

    assert response.status_code == 409
    with app.app_context():
        assert User.query.filter_by(web3authVerifierId=other_verifier).first() is None


def test_production_defaults_to_devnet_client_for_jwt_audience(monkeypatch):
    from services import web3auth_config

    devnet = 'BKvRj4akAwrNHHk4UyYCC4zt9KWigdiuosCX5-idVNclsk9hPPQ4_b8grcl0JF4NhT26oLWb3O5K949SVv6lTGk'
    mainnet = 'BKauYfCPme6fKX3P25DwcBr_AcyO-DRDTxge5t99IlAU_NYjxyOY0aPvAN0v7d8GaJLl7SDyFHveWQG3bNcIyQo'
    monkeypatch.setenv('WEB3AUTH_CLIENT_ID', mainnet)
    monkeypatch.setenv('WEB3AUTH_CLIENT_ID_DEVNET', devnet)
    monkeypatch.delenv('WEB3AUTH_USE_MAINNET', raising=False)
    monkeypatch.setattr(web3auth_config, 'IS_DEVELOPMENT', False, raising=False)

    settings = web3auth_config.get_web3auth_settings()
    assert settings['client_id'] == devnet
    assert settings['network'] == 'sapphire_devnet'
    assert web3auth_config.web3auth_client_id() == devnet
