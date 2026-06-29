"""Ensure Gov Hub user wallet columns (EVM/SOL from Web3Auth; BTC custodial badge wallet)."""
from __future__ import annotations

from typing import Optional

from extensions import db
from models import User


def ensure_user_wallet_addresses(
    user: User,
    *,
    evm_address: Optional[str] = None,
    solana_address: Optional[str] = None,
    bitcoin_address: Optional[str] = None,
) -> bool:
    """Fill empty EVM/SOL from client; always ensure custodial BTC badge wallet."""
    changed = False
    evm = (evm_address or '').strip()
    sol = (solana_address or '').strip()

    if evm and not (user.evmAddress or '').strip():
        conflict = User.query.filter(User.evmAddress == evm, User.id != user.id).first()
        if not conflict:
            user.evmAddress = evm
            changed = True
    if sol and not (user.solanaAddress or '').strip():
        conflict = User.query.filter(User.solanaAddress == sol, User.id != user.id).first()
        if not conflict:
            user.solanaAddress = sol
            changed = True

    from services.custodial_btc_wallet import provision_custodial_btc_wallet

    created, _addr = provision_custodial_btc_wallet(user, commit=False)
    if created:
        changed = True
    return changed


def user_wallet_summary(user: User) -> dict:
    return {
        'evmAddress': user.evmAddress,
        'solanaAddress': user.solanaAddress,
        'bitcoinAddress': getattr(user, 'bitcoinAddress', None),
        'badge_wallet': getattr(user, 'bitcoinAddress', None),
        'badge_wallet_custodial': True,
    }
