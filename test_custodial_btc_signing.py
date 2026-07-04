import hashlib
from uuid import uuid4


def _auth_headers(secret='test-govhub-signing-secret'):
    return {'Authorization': f'Bearer {secret}'}


def _create_user_with_wallet(app, *, with_wallet=True):
    from extensions import db
    from models import User
    from models.custodial_wallet import CustodialWallet
    from services.custodial_btc_wallet import derive_taproot_wallet, encrypt_wallet_secret

    user_id = str(uuid4())
    suffix = user_id[:8]
    with app.app_context():
        db.create_all()
        user = User(
            id=user_id,
            public_id=str(uuid4()),
            username=f'signer_{suffix}',
            handle=f'signer_{suffix}',
            email=f'signer-{suffix}@example.test',
            web3authVerifierId=f'web3auth-{suffix}',
            role='user',
        )
        db.session.add(user)
        address = None
        if with_wallet:
            address, derivation_path, secret = derive_taproot_wallet(user_id)
            user.bitcoinAddress = address
            db.session.add(
                CustodialWallet(
                    user_id=user_id,
                    chain='btc_taproot',
                    address=address,
                    derivation_path=derivation_path,
                    encrypted_secret=encrypt_wallet_secret(secret),
                )
            )
        db.session.commit()
    return {
        'userId': user_id,
        'address': address,
        'email': f'signer-{suffix}@example.test',
        'web3authVerifierId': f'web3auth-{suffix}',
    }


def _delete_user(app, user_id):
    from extensions import db
    from models import User
    from models.custodial_wallet import CustodialWallet

    with app.app_context():
        CustodialWallet.query.filter_by(user_id=user_id).delete(synchronize_session=False)
        User.query.filter_by(id=user_id).delete(synchronize_session=False)
        db.session.commit()


def test_custodial_btc_signing_rejects_missing_auth(monkeypatch):
    from app import app

    monkeypatch.setenv('GOV_HUB_API_KEY', 'test-govhub-signing-secret')
    response = app.test_client().post('/api/internal/custodial-btc/sign-provenance', json={})

    assert response.status_code == 401
    assert response.get_json()['error'] == 'Unauthorized'


def test_custodial_btc_signing_reports_missing_user(monkeypatch):
    from app import app

    monkeypatch.setenv('GOV_HUB_API_KEY', 'test-govhub-signing-secret')
    response = app.test_client().post(
        '/api/internal/custodial-btc/sign-provenance',
        headers=_auth_headers(),
        json={
            'web3authVerifierId': f'missing-{uuid4()}',
            'digest': hashlib.sha256(b'missing').hexdigest(),
        },
    )

    assert response.status_code == 404
    assert response.get_json()['reason'] == 'user_not_found'


def test_custodial_btc_signing_reports_missing_wallet(monkeypatch):
    from app import app

    monkeypatch.setenv('GOV_HUB_API_KEY', 'test-govhub-signing-secret')
    user = _create_user_with_wallet(app, with_wallet=False)
    try:
        response = app.test_client().post(
            '/api/internal/custodial-btc/sign-provenance',
            headers=_auth_headers(),
            json={
                'web3authVerifierId': user['web3authVerifierId'],
                'digest': hashlib.sha256(b'no-wallet').hexdigest(),
            },
        )
    finally:
        _delete_user(app, user['userId'])

    assert response.status_code == 404
    assert response.get_json()['reason'] == 'wallet_not_found'


def test_custodial_btc_signing_rejects_expected_address_mismatch(monkeypatch):
    from app import app

    monkeypatch.setenv('GOV_HUB_API_KEY', 'test-govhub-signing-secret')
    user = _create_user_with_wallet(app)
    try:
        response = app.test_client().post(
            '/api/internal/custodial-btc/sign-provenance',
            headers=_auth_headers(),
            json={
                'web3authVerifierId': user['web3authVerifierId'],
                'address': 'bc1pwrongaddress',
                'digest': hashlib.sha256(b'mismatch').hexdigest(),
            },
        )
    finally:
        _delete_user(app, user['userId'])

    assert response.status_code == 409
    assert response.get_json()['reason'] == 'address_mismatch'


def test_custodial_btc_signing_returns_real_schnorr_signature(monkeypatch):
    from app import app

    monkeypatch.setenv('GOV_HUB_API_KEY', 'test-govhub-signing-secret')
    user = _create_user_with_wallet(app)
    canonical = '{"action":"patch.provenance","domain":"canopi.provenance"}'
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    try:
        response = app.test_client().post(
            '/api/internal/custodial-btc/sign-provenance',
            headers=_auth_headers(),
            json={
                'web3authVerifierId': user['web3authVerifierId'],
                'address': user['address'],
                'canonical': canonical,
                'digest': digest,
                'entityType': 'patch',
                'entityId': 'patch-1',
                'action': 'patch.provenance',
                'historicalRecordedAt': '2026-01-01T00:00:00.000Z',
            },
        )
    finally:
        _delete_user(app, user['userId'])

    data = response.get_json()
    assert response.status_code == 200
    assert data['ok'] is True
    assert data['address'] == user['address']
    assert data['method'] == 'btc_taproot_bip340_schnorr_sha256_digest'
    assert data['network'] == 'btc'
    assert data['digest'] == digest
    assert data['signerKind'] == 'govhub_custodial'
    assert data['signatureEncoding'] == 'base64'
    assert data['historicalRecordedAt'] == '2026-01-01T00:00:00.000Z'
    assert data['keyId'].startswith('btc_taproot:')
    assert data['verification']['verifiedLocally'] is True
    assert len(data['signature']) >= 80
