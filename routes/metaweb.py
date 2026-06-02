"""Metaweb Book server-to-server routes (badge wallet provisioning)."""
from __future__ import annotations

import os
import secrets

from flask import Blueprint, jsonify, request

bp = Blueprint('metaweb', __name__)


def _metaweb_internal_allowed() -> bool:
    secret = (os.environ.get('METAWEB_GOVHUB_INTERNAL_SECRET') or '').strip()
    if not secret:
        return False
    supplied = (
        request.headers.get('X-Metaweb-Govhub-Secret')
        or request.headers.get('Authorization', '').replace('Bearer ', '', 1).strip()
        or ''
    ).strip()
    return bool(supplied) and secrets.compare_digest(supplied, secret)


@bp.route('/api/metaweb/ensure-badge-wallet', methods=['POST'])
def ensure_badge_wallet():
    """
    Provision or return Gov Hub custodial Taproot (bc1p) for a Web3Auth identity.

    Auth: METAWEB_GOVHUB_INTERNAL_SECRET via X-Metaweb-Govhub-Secret or Authorization: Bearer.
    """
    if not _metaweb_internal_allowed():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    verifier_id = (data.get('web3authVerifierId') or data.get('verifierId') or '').strip()
    email = (data.get('email') or '').strip() or None
    name = (data.get('name') or data.get('displayName') or '').strip() or None
    canopi_user_id = (data.get('canopiUserId') or '').strip() or None
    evm_address = (data.get('evmAddress') or '').strip() or None
    type_of_login = (data.get('typeOfLogin') or '').strip() or None

    try:
        from services.metaweb_badge_wallet import ensure_metaweb_badge_wallet

        result = ensure_metaweb_badge_wallet(
            web3auth_verifier_id=verifier_id,
            email=email,
            name=name,
            canopi_user_id=canopi_user_id,
            evm_address=evm_address,
            type_of_login=type_of_login,
        )
        return jsonify(result)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:
        from flask import current_app

        current_app.logger.exception('ensure-badge-wallet failed')
        return jsonify({'error': 'Internal error', 'detail': str(exc)}), 500
