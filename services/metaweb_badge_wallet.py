"""Metaweb Book integration: ensure Gov Hub custodial badge wallet (bc1p) for a Web3Auth identity."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from extensions import db
from models import User


def _find_user(*, verifier_id: str, email: Optional[str]) -> Optional[User]:
    vid = (verifier_id or '').strip()
    if vid:
        user = User.query.filter_by(web3authVerifierId=vid).first()
        if user:
            return user
    em = (email or '').strip().lower()
    if em:
        return User.query.filter(db.func.lower(User.email) == em).first()
    return None


def _unique_handle(*, email: Optional[str], evm_address: Optional[str], type_of_login: str) -> str:
    existing_handles = {row[0] for row in db.session.query(User.username).all()}
    evm = (evm_address or '').strip()
    if type_of_login == 'wallet' and evm:
        short_address = f'{evm[:6]}...{evm[-4:]}'
        handle = f'wallet_{short_address}'
        counter = 1
        while handle in existing_handles:
            handle = f'wallet_{short_address}_{counter}'
            counter += 1
        return handle
    base_handle = email.split('@')[0] if email else 'user'
    base_handle = re.sub(r'[^a-zA-Z0-9_]', '', base_handle)
    if len(base_handle) < 3:
        base_handle = 'user'
    handle = base_handle
    counter = 1
    while handle in existing_handles:
        handle = f'{base_handle}{counter}'
        counter += 1
    return handle


def ensure_metaweb_pioneers_membership(user, *, verifier_id: str = '') -> dict:
    """
    Add Gov Hub user to Metaweb Pioneers layer and mirror membership to Canopi.
    Book buyers bypass nft_gated join — trusted server path after purchase bind.
    """
    from config import METAWEB_PIONEERS_LAYER_SLUG
    from models import Layer, LayerMember
    from services.canopi_community_sync import mirror_membership_to_canopi, provision_or_sync_layer

    slug = (METAWEB_PIONEERS_LAYER_SLUG or 'metaweb-pioneers').strip()
    layer = Layer.query.filter_by(slug=slug).first()
    if not layer:
        return {'ok': False, 'skipped': True, 'reason': f'layer_not_found:{slug}'}

    existing = LayerMember.query.filter_by(layer_id=layer.id, user_id=user.id).first()
    member_created = False
    if existing:
        if existing.status != 'active' or existing.left_at is not None:
            existing.status = 'active'
            existing.left_at = None
            existing.joined_at = datetime.utcnow()
    else:
        db.session.add(
            LayerMember(
                layer_id=layer.id,
                user_id=user.id,
                role='member',
                status='active',
            )
        )
        member_created = True

    db.session.commit()

    # Keep Canopi MetaCommunity logo/name in sync (image_url is Gov Hub–hosted).
    provision_or_sync_layer(layer, force=True)

    vid = (verifier_id or getattr(user, 'web3authVerifierId', None) or '').strip()
    canopi_mirror = None
    if vid and getattr(layer, 'canopi_meta_community_id', None):
        canopi_mirror = mirror_membership_to_canopi(
            layer_id=layer.id,
            web3auth_verifier_id=vid,
            active=True,
        )

    return {
        'ok': True,
        'layerId': layer.id,
        'layerSlug': slug,
        'canopiMetaCommunityId': getattr(layer, 'canopi_meta_community_id', None),
        'memberCreated': member_created,
        'canopiMirror': canopi_mirror,
    }


def ensure_metaweb_badge_wallet(
    *,
    web3auth_verifier_id: str = '',
    email: Optional[str] = None,
    name: Optional[str] = None,
    canopi_user_id: Optional[str] = None,
    evm_address: Optional[str] = None,
    type_of_login: Optional[str] = None,
) -> dict:
    """
    Find or create a Gov Hub user and ensure custodial BIP86 Taproot in custodial_wallet.

    Trusted server-to-server call from Metaweb Book bind-purchase (after Canopi Web3Auth).
    """
    from services.custodial_btc_wallet import provision_custodial_btc_wallet
    from services.user_wallets import ensure_user_wallet_addresses
    from services.web3auth_verify import normalize_user_email

    verifier_id = (web3auth_verifier_id or '').strip()
    normalized_email = normalize_user_email(email) if email else None
    login_type = (type_of_login or 'metaweb').strip() or 'metaweb'

    if not verifier_id and not normalized_email:
        raise ValueError('web3authVerifierId or email is required')

    user = _find_user(verifier_id=verifier_id, email=normalized_email)
    user_created = False

    if user:
        if verifier_id and not (user.web3authVerifierId or '').strip():
            user.web3authVerifierId = verifier_id
        if normalized_email and not (user.email or '').strip():
            conflict = User.query.filter(
                db.func.lower(User.email) == normalized_email,
                User.id != user.id,
            ).first()
            if not conflict:
                user.email = normalized_email
        if name and not (user.displayName or '').strip():
            user.displayName = name.strip()
            user.displayNameSetAt = datetime.utcnow()
            user.oauthName = name.strip()
        user.last_login = datetime.utcnow()
        had_addr = bool((getattr(user, 'bitcoinAddress', None) or '').strip())
        ensure_user_wallet_addresses(user, evm_address=evm_address)
        db.session.commit()
        wallet_created = not had_addr and bool((user.bitcoinAddress or '').strip())
    else:
        if not verifier_id:
            raise ValueError('web3authVerifierId is required to create a new Gov Hub user')
        handle = _unique_handle(
            email=normalized_email,
            evm_address=evm_address,
            type_of_login=login_type,
        )
        user = User(
            web3authVerifierId=verifier_id,
            typeOfLogin=login_type,
            displayName=name.strip() if name else None,
            displayNameSetAt=datetime.utcnow() if name else None,
            oauthName=name.strip() if name else None,
            email=normalized_email,
            username=handle,
            handle=handle,
            role='user',
            theme='dark',
            last_login=datetime.utcnow(),
        )
        db.session.add(user)
        db.session.flush()
        ensure_user_wallet_addresses(user, evm_address=evm_address)
        try:
            from services.document_follow_notifications import ensure_notification_unsubscribe_token

            ensure_notification_unsubscribe_token(user)
        except Exception:
            pass
        db.session.commit()
        user_created = True
        wallet_created = True

    address = (getattr(user, 'bitcoinAddress', None) or '').strip() or None
    if not address:
        created, address = provision_custodial_btc_wallet(user, commit=True)
        wallet_created = wallet_created or created

    pioneers = ensure_metaweb_pioneers_membership(
        user,
        verifier_id=verifier_id,
    )

    from services.auth_layer_membership import ensure_auth_layer_memberships

    auth_layers_touched = ensure_auth_layer_memberships(user, login_type)

    return {
        'ok': True,
        'govhubUserId': user.id,
        'bitcoinAddress': address,
        'badgeWallet': address,
        'userCreated': user_created,
        'walletCreated': wallet_created,
        'canopiUserId': (canopi_user_id or '').strip() or None,
        'metawebPioneers': pioneers,
        'authLayerMembershipsTouched': auth_layers_touched,
    }
