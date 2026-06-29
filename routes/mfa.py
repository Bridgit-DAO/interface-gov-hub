"""MFA API routes: device CRUD, recovery codes, login verification."""
from flask import Blueprint, jsonify, request, session

from extensions import db
from models import User
from services.identity import get_current_user
from services.mfa import (
    confirm_device,
    create_challenge,
    list_devices,
    mfa_status,
    recovery_codes_remaining,
    regenerate_recovery_codes,
    rename_device,
    revoke_device,
    start_device_enrollment,
    user_mfa_enabled,
    verify_login_challenge,
    verify_user_code,
)
from services.utils import check_rate_limit

bp = Blueprint('mfa', __name__, url_prefix='')


def _require_session_user():
    username = session.get('user')
    if not username:
        return None, (jsonify({'error': 'Unauthorized'}), 401)
    user = User.query.filter_by(username=username).first()
    if not user:
        return None, (jsonify({'error': 'User not found'}), 404)
    return user, None


def _safe_user_payload(user):
    return {
        'id': user.id,
        'public_id': user.public_id,
        'username': user.username,
        'displayName': user.displayName,
        'oauthName': user.oauthName,
        'email': user.email,
        'profileImage': user.profileImage,
        'evmAddress': user.evmAddress,
        'solanaAddress': user.solanaAddress,
        'bitcoinAddress': getattr(user, 'bitcoinAddress', None),
        'typeOfLogin': user.typeOfLogin,
        'theme': user.theme,
    }


@bp.route('/api/mfa/status', methods=['GET'])
def api_mfa_status():
    user, err = _require_session_user()
    if err:
        return err
    return jsonify(mfa_status(user.id))


@bp.route('/api/mfa/devices', methods=['POST'])
def api_mfa_create_device():
    user, err = _require_session_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    label = (data.get('label') or 'Authenticator').strip()
    try:
        device, secret, otpauth_uri = start_device_enrollment(user.id, label)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({
        'deviceId': device.id,
        'label': device.label,
        'secret': secret,
        'otpauthUri': otpauth_uri,
    })


@bp.route('/api/mfa/devices/<device_id>/confirm', methods=['POST'])
def api_mfa_confirm_device(device_id):
    user, err = _require_session_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code:
        return jsonify({'error': 'Verification code required'}), 400
    ok, recovery_codes = confirm_device(user.id, device_id, code)
    if not ok:
        return jsonify({'error': 'Invalid code or device not found'}), 400
    payload = {'success': True, 'enabled': True}
    if recovery_codes:
        payload['recoveryCodes'] = recovery_codes
        payload['recoveryCodesGenerated'] = True
    return jsonify(payload)


@bp.route('/api/mfa/devices/<device_id>', methods=['PATCH'])
def api_mfa_update_device(device_id):
    user, err = _require_session_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    label = (data.get('label') or '').strip()
    if not rename_device(user.id, device_id, label):
        return jsonify({'error': 'Device not found or label invalid'}), 400
    return jsonify({'success': True})


@bp.route('/api/mfa/devices/<device_id>', methods=['DELETE'])
def api_mfa_delete_device(device_id):
    user, err = _require_session_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code:
        return jsonify({'error': 'Verification code required to remove a device'}), 400
    ok, message = revoke_device(user.id, device_id, code=code)
    if not ok:
        return jsonify({'error': message or 'Could not remove device'}), 400
    return jsonify({
        'success': True,
        'enabled': user_mfa_enabled(user.id),
        'recoveryCodesRemaining': recovery_codes_remaining(user.id),
    })


@bp.route('/api/mfa/recovery-codes/regenerate', methods=['POST'])
def api_mfa_regenerate_recovery_codes():
    user, err = _require_session_user()
    if err:
        return err
    if not user_mfa_enabled(user.id):
        return jsonify({'error': 'Enable two-factor authentication first'}), 400
    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    if not code:
        return jsonify({'error': 'Authenticator code required'}), 400
    if not verify_user_code(user.id, code):
        return jsonify({'error': 'Invalid verification code'}), 400
    codes = regenerate_recovery_codes(user.id)
    return jsonify({'success': True, 'recoveryCodes': codes})


@bp.route('/api/mfa/recovery-codes/count', methods=['GET'])
def api_mfa_recovery_count():
    user, err = _require_session_user()
    if err:
        return err
    return jsonify({'remaining': recovery_codes_remaining(user.id)})


@bp.route('/api/mfa/verify-login', methods=['POST'])
def api_mfa_verify_login():
    """Complete login after Web3Auth when MFA is enabled."""
    data = request.get_json(silent=True) or {}
    challenge_token = (data.get('challengeToken') or data.get('challenge_token') or '').strip()
    code = (data.get('code') or '').strip()
    if not challenge_token or not code:
        return jsonify({'error': 'challengeToken and code are required'}), 400

    client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', 'unknown')
    if not check_rate_limit(f'mfa_login_{client_ip}', max_requests=30, window_seconds=600):
        return jsonify({'error': 'Too many attempts. Please wait and try again.'}), 429

    user_id, error = verify_login_challenge(challenge_token, code)
    if not user_id:
        return jsonify({'error': error or 'Verification failed'}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    session['user'] = user.username
    session['theme'] = user.theme
    session.permanent = True
    session.modified = True

    try:
        from services.auth_layer_membership import ensure_auth_layer_memberships

        ensure_auth_layer_memberships(user, user.typeOfLogin)
    except Exception:
        pass

    return jsonify({'success': True, 'user': _safe_user_payload(user)})
