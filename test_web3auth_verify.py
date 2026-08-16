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


def test_identity_from_web3auth_claims_normalizes_email_case():
    from services.web3auth_verify import identity_from_web3auth_claims

    claims = {
        'userId': 'Dave@bridgit.io',
        'email': 'Dave@bridgit.io',
        'groupedAuthConnectionId': 'web3auth-google-sapphire-devnet',
    }
    identity = identity_from_web3auth_claims(claims)
    assert identity['verifierId'] == 'Dave@bridgit.io'
    assert identity['email'] == 'dave@bridgit.io'


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

    collision_email = 'collision-test@example.com'
    with app.app_context():
        User.query.filter_by(email=collision_email).delete()
        user = User(
            username='collisiontest',
            handle='collisiontest',
            email=collision_email,
            role='user',
            web3authVerifierId='existing-linked-verifier-for-collision-test',
        )
        db.session.add(user)
        db.session.commit()

    other_verifier = 'brand-new-verifier-id-for-test'
    fake_claims = {
        'userId': other_verifier,
        'email': collision_email,
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
        existing = User.query.filter_by(email=collision_email).first()
        assert existing.web3authVerifierId == 'existing-linked-verifier-for-collision-test'
        db.session.delete(existing)
        db.session.commit()


def test_web3auth_login_links_email_passwordless_to_google_verifier(monkeypatch):
    """Regression: prod used to 409 when email matched but verifier_id changed."""
    from app import app
    from extensions import db
    from models import User
    from models.custodial_wallet import CustodialWallet

    email = 'link-upgrade-test@example.com'
    old_verifier = email
    new_verifier = 'google-subject-link-upgrade-test'
    with app.app_context():
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user:
            CustodialWallet.query.filter_by(user_id=user.id).delete(synchronize_session=False)
            db.session.delete(user)
            db.session.commit()
        user = User(
            username='linkupgradetest',
            handle='linkupgradetest',
            email=email,
            role='user',
            web3authVerifierId=old_verifier,
            typeOfLogin='email_passwordless',
        )
        db.session.add(user)
        db.session.commit()

    fake_claims = {
        'userId': new_verifier,
        'email': email,
        'name': 'Link Upgrade',
        'groupedAuthConnectionId': 'web3auth-google-sapphire-devnet',
    }

    client = app.test_client()
    with patch('services.web3auth_verify.verify_web3auth_id_token', return_value=fake_claims):
        response = client.post(
            '/api/auth/web3auth',
            json={'idToken': 'fake.jwt.token'},
            content_type='application/json',
        )

    assert response.status_code == 200
    with app.app_context():
        linked = User.query.filter_by(email=email).first()
        assert linked.web3authVerifierId == new_verifier
        assert linked.typeOfLogin == 'google'
        CustodialWallet.query.filter_by(user_id=linked.id).delete(synchronize_session=False)
        db.session.delete(linked)
        db.session.commit()


def test_web3auth_login_creates_new_user_with_custodial_wallet(monkeypatch):
    """New sign-up used to 409 with a false 'email already linked' error because
    custodial_wallet was inserted before user.id existed."""
    from uuid import uuid4

    from app import app
    from extensions import db
    from models import User
    from models.custodial_wallet import CustodialWallet

    suffix = uuid4().hex[:10]
    email = f'new-signup-{suffix}@example.com'
    verifier = f'google-sub-new-signup-{suffix}'
    with app.app_context():
        existing = User.query.filter(db.func.lower(User.email) == email).first()
        if existing:
            CustodialWallet.query.filter_by(user_id=existing.id).delete(synchronize_session=False)
            db.session.delete(existing)
            db.session.commit()

    fake_claims = {
        'userId': verifier,
        'email': email,
        'name': 'New Signup',
        'groupedAuthConnectionId': 'web3auth-google-sapphire-devnet',
    }

    client = app.test_client()
    with patch('services.web3auth_verify.verify_web3auth_id_token', return_value=fake_claims):
        response = client.post(
            '/api/auth/web3auth',
            json={'idToken': 'fake.jwt.token'},
            content_type='application/json',
        )

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['user']['email'] == email
    with app.app_context():
        created = User.query.filter_by(web3authVerifierId=verifier).first()
        assert created is not None
        assert created.id
        wallet = CustodialWallet.query.filter_by(user_id=created.id, chain='btc_taproot').first()
        assert wallet is not None
        assert (created.bitcoinAddress or '').strip()
        CustodialWallet.query.filter_by(user_id=created.id).delete(synchronize_session=False)
        db.session.delete(created)
        db.session.commit()


def test_web3auth_login_links_orphan_email_account(monkeypatch):
    from app import app
    from extensions import db
    from models import User
    from models.custodial_wallet import CustodialWallet

    orphan_email = 'orphan-link-test@example.com'
    new_verifier = 'new-google-verifier-for-orphan-test'
    with app.app_context():
        user = User.query.filter_by(email=orphan_email).first()
        if user:
            CustodialWallet.query.filter_by(user_id=user.id).delete(synchronize_session=False)
            db.session.delete(user)
            db.session.commit()
        user = User(
            username='orphanlinktest',
            handle='orphanlinktest',
            email=orphan_email,
            role='user',
            web3authVerifierId=None,
        )
        db.session.add(user)
        db.session.commit()

    fake_claims = {
        'userId': new_verifier,
        'email': orphan_email,
        'name': 'Orphan User',
        'groupedAuthConnectionId': 'web3auth-google-sapphire-devnet',
    }

    client = app.test_client()
    with patch('services.web3auth_verify.verify_web3auth_id_token', return_value=fake_claims):
        response = client.post(
            '/api/auth/web3auth',
            json={'idToken': 'fake.jwt.token'},
            content_type='application/json',
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['user']['email'] == orphan_email
    with app.app_context():
        linked = User.query.filter_by(email=orphan_email).first()
        assert linked is not None
        assert linked.web3authVerifierId == new_verifier
        assert linked.typeOfLogin == 'google'
        CustodialWallet.query.filter_by(user_id=linked.id).delete(synchronize_session=False)
        db.session.delete(linked)
        db.session.commit()


def test_production_uses_devnet_by_default(monkeypatch):
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


def test_production_mainnet_requires_explicit_opt_in(monkeypatch):
    from services import web3auth_config

    devnet = 'BKvRj4akAwrNHHk4UyYCC4zt9KWigdiuosCX5-idVNclsk9hPPQ4_b8grcl0JF4NhT26oLWb3O5K949SVv6lTGk'
    mainnet = 'BKauYfCPme6fKX3P25DwcBr_AcyO-DRDTxge5t99IlAU_NYjxyOY0aPvAN0v7d8GaJLl7SDyFHveWQG3bNcIyQo'
    monkeypatch.setenv('WEB3AUTH_CLIENT_ID', mainnet)
    monkeypatch.setenv('WEB3AUTH_CLIENT_ID_DEVNET', devnet)
    monkeypatch.setenv('WEB3AUTH_USE_MAINNET', 'true')
    monkeypatch.setattr(web3auth_config, 'IS_DEVELOPMENT', False, raising=False)

    settings = web3auth_config.get_web3auth_settings()
    assert settings['client_id'] == mainnet
    assert settings['network'] == 'sapphire_mainnet'
