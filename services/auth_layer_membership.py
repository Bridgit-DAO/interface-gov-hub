"""Auto LayerMember for auth_community layers on Web3Auth sign-in."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from extensions import db
from models import Layer, LayerMember


def normalize_auth_provider(type_of_login: Optional[str]) -> str:
    login = (type_of_login or '').strip().lower()
    if login == 'custom_btc':
        return 'bitcoin'
    return login


def ensure_auth_layer_memberships(user, type_of_login: Optional[str]) -> int:
    """
    Upsert LayerMember for unmanaged auth_community layers matching auth_provider.
    Returns count of layers touched.
    """
    provider = normalize_auth_provider(type_of_login)
    if not provider:
        return 0

    layers = Layer.query.filter(
        Layer.layer_kind == 'auth_community',
        Layer.auth_provider == provider,
    ).all()

    touched = 0
    for layer in layers:
        existing = LayerMember.query.filter_by(layer_id=layer.id, user_id=user.id).first()
        if existing:
            if existing.status != 'active' or existing.left_at is not None:
                existing.status = 'active'
                existing.left_at = None
                existing.joined_at = datetime.utcnow()
                touched += 1
        else:
            db.session.add(
                LayerMember(
                    layer_id=layer.id,
                    user_id=user.id,
                    role='member',
                    status='active',
                )
            )
            touched += 1

        vid = (getattr(user, 'web3authVerifierId', None) or '').strip()
        if vid and getattr(layer, 'canopi_meta_community_id', None):
            from services.canopi_community_sync import mirror_membership_to_canopi

            mirror_membership_to_canopi(
                layer_id=layer.id,
                web3auth_verifier_id=vid,
                active=True,
            )

    if touched:
        db.session.commit()
    return touched
