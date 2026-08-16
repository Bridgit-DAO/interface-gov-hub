"""Gov Hub custodial Bitcoin badge wallets (BIP86 Taproot).

Addresses are derived from a server-held master key (GOVHUB_BTC_CUSTODY_MNEMONIC
or GOVHUB_BTC_CUSTODY_XPRV). Per-user leaf private keys are stored encrypted in
custodial_wallet so Gov Hub can sign or recover without re-deriving from logs.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional, Tuple
from uuid import uuid4

from extensions import db

_BIP86_ACCOUNT = "m/86'/0'/0'"


def _fernet():
    from cryptography.fernet import Fernet

    material = (
        os.environ.get('GOVHUB_WALLET_ENCRYPTION_KEY')
        or os.environ.get('SECRET_KEY')
        or ''
    ).strip()
    if not material:
        raise RuntimeError(
            'GOVHUB_WALLET_ENCRYPTION_KEY or SECRET_KEY required for custodial wallet encryption'
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode()).digest())
    return Fernet(key)


def encrypt_wallet_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_wallet_secret(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()


def _master_hdkey():
    from embit import bip39
    from embit.bip32 import HDKey

    xprv = (os.environ.get('GOVHUB_BTC_CUSTODY_XPRV') or '').strip()
    if xprv:
        return HDKey.from_string(xprv)

    mnemonic = (os.environ.get('GOVHUB_BTC_CUSTODY_MNEMONIC') or '').strip()
    if mnemonic:
        seed = bip39.mnemonic_to_seed(mnemonic)
        return HDKey.from_seed(seed)

    fallback = (os.environ.get('SECRET_KEY') or 'govhub-dev-custody-insecure').encode()
    seed = hashlib.pbkdf2_hmac('sha256', fallback, b'govhub-btc-custody-v1', 200_000, dklen=64)
    return HDKey.from_seed(seed)


def derivation_index_for_user(user_id: str) -> int:
    digest = hashlib.sha256(f'govhub-badge-wallet:{user_id}'.encode()).digest()
    return int.from_bytes(digest[:4], 'big') % (2**31 - 1)


def derivation_path_for_user(user_id: str) -> str:
    return f"{_BIP86_ACCOUNT}/{derivation_index_for_user(user_id)}"


def derive_taproot_wallet(user_id: str) -> Tuple[str, str, str]:
    """Return (address, derivation_path, wif) for a user."""
    from embit.script import p2tr

    path = derivation_path_for_user(user_id)
    leaf = _master_hdkey().derive(path)
    address = p2tr(leaf).address()
    wif = leaf.to_string()
    if not leaf.is_private:
        raise RuntimeError('Derived HD key is not private')
    return address, path, wif


def provision_custodial_btc_wallet(user, *, commit: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Create custodial badge wallet for user if missing.
    Returns (created, address).
    """
    from models import User
    from models.custodial_wallet import CustodialWallet

    # Column defaults are INSERT-time only. New User() objects have id=None
    # until flush; inserting custodial_wallet then fails NOT NULL user_id and
    # was misreported as "email already linked".
    if not (getattr(user, 'id', None) or '').strip():
        user.id = str(uuid4())
    if not (getattr(user, 'public_id', None) or '').strip():
        user.public_id = str(uuid4())

    existing_addr = (getattr(user, 'bitcoinAddress', None) or '').strip()
    row = CustodialWallet.query.filter_by(user_id=user.id, chain='btc_taproot').first()

    if row and existing_addr:
        return False, existing_addr

    if existing_addr and not row:
        address, path, wif = derive_taproot_wallet(user.id)
        if existing_addr != address:
            user.bitcoinAddress = address
        db.session.add(
            CustodialWallet(
                user_id=user.id,
                chain='btc_taproot',
                address=address,
                derivation_path=path,
                encrypted_secret=encrypt_wallet_secret(wif),
            )
        )
        if commit:
            db.session.commit()
        return existing_addr != address, address

    address, path, wif = derive_taproot_wallet(user.id)
    conflict = User.query.filter(
        User.bitcoinAddress == address,
        User.id != user.id,
    ).first()
    if conflict:
        raise RuntimeError(f'Address collision for user {user.id}')

    user.bitcoinAddress = address
    if row:
        row.address = address
        row.derivation_path = path
        row.encrypted_secret = encrypt_wallet_secret(wif)
    else:
        db.session.add(
            CustodialWallet(
                user_id=user.id,
                chain='btc_taproot',
                address=address,
                derivation_path=path,
                encrypted_secret=encrypt_wallet_secret(wif),
            )
        )
    if commit:
        db.session.commit()
    return True, address


def reprovision_custodial_btc_wallet(user, *, commit: bool = True) -> Tuple[bool, Optional[str]]:
    """Replace badge wallet with a fresh derive from the current master key."""
    from models.custodial_wallet import CustodialWallet

    CustodialWallet.query.filter_by(user_id=user.id, chain='btc_taproot').delete(
        synchronize_session=False
    )
    user.bitcoinAddress = None
    if commit:
        db.session.flush()
    return provision_custodial_btc_wallet(user, commit=commit)


def get_custodial_wif(user_id: str) -> Optional[str]:
    """Decrypt leaf WIF for server-side signing (ops only)."""
    from models.custodial_wallet import CustodialWallet

    row = CustodialWallet.query.filter_by(user_id=user_id, chain='btc_taproot').first()
    if not row or not row.encrypted_secret:
        return None
    return decrypt_wallet_secret(row.encrypted_secret)
