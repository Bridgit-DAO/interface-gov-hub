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


def _govhub_api_key_allowed() -> bool:
    secret = (os.environ.get('GOV_HUB_API_KEY') or '').strip()
    if not secret:
        return False
    supplied = (
        request.headers.get('Authorization', '').replace('Bearer ', '', 1).strip()
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


@bp.route('/api/metaweb/action-status', methods=['POST'])
def action_status():
    """
    Batch read-only checks for Metaweb Book `awardType: govhub_action` blueberries.

    Auth: METAWEB_GOVHUB_INTERNAL_SECRET via X-Metaweb-Govhub-Secret or Authorization: Bearer.
    """
    if not _metaweb_internal_allowed():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    govhub_user_id = (data.get('govhubUserId') or '').strip() or None
    web3auth_verifier_id = (data.get('web3authVerifierId') or '').strip() or None
    checks = data.get('checks')

    if not govhub_user_id and not web3auth_verifier_id:
        return jsonify({'error': 'govhubUserId or web3authVerifierId required'}), 400
    if not isinstance(checks, list):
        return jsonify({'error': 'checks array required'}), 400
    if len(checks) > 20:
        return jsonify({'error': 'too_many_checks'}), 400

    from services.metaweb_action_status import evaluate_action_checks, resolve_govhub_user

    user = resolve_govhub_user(
        govhub_user_id=govhub_user_id,
        web3auth_verifier_id=web3auth_verifier_id,
    )
    if not user:
        return jsonify({'error': 'user_not_found'}), 404

    results = evaluate_action_checks(user, checks)
    return jsonify({'ok': True, 'govhubUserId': str(user.id), 'results': results})


@bp.route('/api/internal/custodial-btc/sign-provenance', methods=['POST'])
def sign_custodial_btc_provenance():
    """
    Sign a canonical Canopi provenance digest with Gov Hub custodial BTC key material.

    Auth: GOV_HUB_API_KEY via Authorization: Bearer.
    Body: userId/govhubUserId, web3authVerifierId, or email; optional expected address;
    digest and/or canonical message; provenance metadata.
    """
    if not _govhub_api_key_allowed():
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    from services.custodial_btc_provenance_signer import (
        SignatureRequestError,
        sign_provenance_request,
    )

    try:
        return jsonify(sign_provenance_request(data))
    except SignatureRequestError as exc:
        return jsonify({'ok': False, 'error': str(exc), 'reason': exc.reason}), exc.status_code
    except Exception:
        from flask import current_app

        current_app.logger.exception('custodial BTC provenance signing failed')
        return jsonify({'ok': False, 'error': 'Internal error', 'reason': 'signing_internal_error'}), 500
