"""Internal custodial BTC provenance signing.

This intentionally signs a canonical 32-byte SHA-256 digest with the user's
custodial Taproot leaf key. It is not a BIP322 message signature and does not
sign or broadcast Bitcoin transactions.
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from extensions import db
from models import User
from models.custodial_wallet import CustodialWallet
from services.custodial_btc_wallet import decrypt_wallet_secret

SIGNER_KIND = 'govhub_custodial'
METHOD = 'btc_taproot_bip340_schnorr_sha256_digest'
NETWORK = 'btc'
SIGNATURE_ENCODING = 'base64'


class SignatureRequestError(ValueError):
    """Request-level signing failure with an HTTP status and stable reason."""

    def __init__(self, message: str, *, status_code: int = 400, reason: str = 'invalid_request'):
        super().__init__(message)
        self.status_code = status_code
        self.reason = reason


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _normalize_email(raw: Optional[str]) -> str:
    return (raw or '').strip().lower()


def _resolve_user(data: dict[str, Any]) -> User:
    user_id = (data.get('govhubUserId') or data.get('userId') or '').strip()
    if user_id:
        user = User.query.get(user_id)
        if user:
            return user

    verifier_id = (
        data.get('web3authVerifierId')
        or data.get('verifierId')
        or ''
    ).strip()
    if verifier_id:
        user = User.query.filter_by(web3authVerifierId=verifier_id).first()
        if user:
            return user

    email = _normalize_email(data.get('email'))
    if email:
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user:
            return user

    raise SignatureRequestError('Custodial wallet user not found', status_code=404, reason='user_not_found')


def _resolve_digest(data: dict[str, Any]) -> tuple[str, Optional[str]]:
    digest = (data.get('digest') or '').strip().lower()
    canonical = data.get('canonical')
    if canonical is None:
        canonical = data.get('message') or data.get('payload')
    if canonical is not None and not isinstance(canonical, str):
        raise SignatureRequestError('canonical/message must be a string', reason='invalid_canonical')

    canonical_digest = None
    if canonical is not None:
        canonical_digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    if digest:
        if len(digest) != 64:
            raise SignatureRequestError('digest must be a 64-character hex SHA-256 value', reason='invalid_digest')
        try:
            bytes.fromhex(digest)
        except ValueError as exc:
            raise SignatureRequestError('digest must be hex encoded', reason='invalid_digest') from exc
        if canonical_digest and not secretsafe_digest_equal(digest, canonical_digest):
            raise SignatureRequestError('digest does not match canonical message', reason='digest_mismatch')
        return digest, canonical

    if canonical_digest:
        return canonical_digest, canonical

    raise SignatureRequestError('digest or canonical message is required', reason='digest_required')


def secretsafe_digest_equal(left: str, right: str) -> bool:
    import secrets

    return secrets.compare_digest(left, right)


def _private_key_from_secret(secret: str):
    from embit import ec
    from embit.bip32 import HDKey

    value = (secret or '').strip()
    if not value:
        raise SignatureRequestError('Custodial wallet secret is empty', status_code=500, reason='wallet_secret_empty')

    if value.startswith(('xprv', 'tprv')):
        key = HDKey.from_string(value)
        if not key.is_private:
            raise SignatureRequestError('Custodial wallet key is not private', status_code=500, reason='wallet_secret_invalid')
        return ec.PrivateKey(key.secret)

    return ec.PrivateKey.from_wif(value)


def _taproot_address_for_private_key(private_key) -> str:
    from embit.script import p2tr

    return p2tr(private_key).address()


def _key_id(*, user_id: str, address: str, derivation_path: str) -> str:
    material = f'govhub-custodial-btc-v1:{user_id}:{address}:{derivation_path}'
    return f'btc_taproot:{hashlib.sha256(material.encode()).hexdigest()[:24]}'


def sign_provenance_request(data: dict[str, Any]) -> dict[str, Any]:
    """Sign a Canopi canonical provenance digest with a Gov Hub custodial key."""
    if not isinstance(data, dict):
        raise SignatureRequestError('JSON body is required')

    user = _resolve_user(data)
    digest_hex, canonical = _resolve_digest(data)

    wallet = CustodialWallet.query.filter_by(user_id=user.id, chain='btc_taproot').first()
    if not wallet or not wallet.encrypted_secret:
        raise SignatureRequestError('Custodial BTC wallet not found', status_code=404, reason='wallet_not_found')

    expected_address = (data.get('address') or data.get('expectedAddress') or '').strip()
    stored_address = (wallet.address or getattr(user, 'bitcoinAddress', None) or '').strip()
    if expected_address and stored_address and expected_address != stored_address:
        raise SignatureRequestError('Expected address does not match custodial wallet', status_code=409, reason='address_mismatch')

    private_key = _private_key_from_secret(decrypt_wallet_secret(wallet.encrypted_secret))
    derived_address = _taproot_address_for_private_key(private_key)
    if stored_address and derived_address != stored_address:
        raise SignatureRequestError('Stored custodial address does not match key material', status_code=500, reason='stored_address_mismatch')
    if expected_address and derived_address != expected_address:
        raise SignatureRequestError('Expected address does not match key material', status_code=409, reason='address_mismatch')

    digest_bytes = bytes.fromhex(digest_hex)
    signature = private_key.schnorr_sign(digest_bytes)
    signature_bytes = signature.serialize()
    public_key = private_key.get_public_key()

    verification = {
        'available': True,
        'algorithm': 'BIP340 Schnorr',
        'signedDigest': 'sha256(canonical)',
        'messageSigningStandard': 'not_bip322',
        'publicKeyXOnly': public_key.xonly().hex(),
        'signatureLength': len(signature_bytes),
        'verifiedLocally': public_key.schnorr_verify(signature, digest_bytes),
    }

    signed_at = _utc_now_iso()
    response = {
        'ok': True,
        'address': derived_address,
        'method': METHOD,
        'network': NETWORK,
        'digest': digest_hex,
        'signature': base64.b64encode(signature_bytes).decode('ascii'),
        'signatureEncoding': SIGNATURE_ENCODING,
        'signedAt': signed_at,
        'historicalRecordedAt': data.get('historicalRecordedAt') or None,
        'signerKind': SIGNER_KIND,
        'keyId': _key_id(
            user_id=user.id,
            address=derived_address,
            derivation_path=wallet.derivation_path or '',
        ),
        'publicKey': public_key.sec().hex(),
        'publicKeyXOnly': public_key.xonly().hex(),
        'verification': verification,
    }

    if canonical is not None:
        response['canonicalHashAlgorithm'] = 'sha256'
    for field in ('entityType', 'entityId', 'action'):
        if data.get(field) is not None:
            response[field] = data.get(field)
    return response
