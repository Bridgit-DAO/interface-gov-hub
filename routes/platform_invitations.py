"""Platform invitation API (unified invite flows)."""
from flask import Blueprint, jsonify, request, session

from services.identity import get_current_user
from services.platform_invitations import (
    accept_invitation,
    create_invitation,
    create_invitations_bulk,
    decline_invitation,
    get_shareable_platform_campaign,
    preview_invitation,
    revoke_invitation,
)

bp = Blueprint('platform_invitations', __name__, url_prefix='/api/invitations')


def _auth_required_json():
    """Return 401 JSON for API clients (avoid HTML redirect from @require_auth)."""
    if 'user' not in session:
        return jsonify({'error': 'Authentication required'}), 401
    return None


@bp.route('/', methods=['POST'])
def create_invite():
    auth_err = _auth_required_json()
    if auth_err:
        return auth_err
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body = request.get_json(silent=True) or {}
    invite_type = (body.get('type') or body.get('invite_type') or '').strip()
    email = (body.get('email') or body.get('invitee_email') or '').strip()
    message = body.get('message')
    target = body.get('target')
    if not isinstance(target, dict):
        target = {}
    resp, status = create_invitation(
        invite_type=invite_type,
        inviter_id=current_user['id'],
        invitee_email=email,
        message=message,
        target=target,
    )
    return jsonify(resp), status


@bp.route('/campaign/', methods=['POST'])
def shareable_campaign():
    """Create or return the shareable invitation link for this type+target (no email)."""
    auth_err = _auth_required_json()
    if auth_err:
        return auth_err
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body = request.get_json(silent=True) or {}
    invite_type = (body.get('type') or body.get('invite_type') or '').strip()
    message = body.get('message')
    target = body.get('target')
    if not isinstance(target, dict):
        target = {}
    resp, status = get_shareable_platform_campaign(
        invite_type=invite_type,
        inviter_id=current_user['id'],
        target=target,
        message=message,
    )
    return jsonify(resp), status


@bp.route('/batch/', methods=['POST'])
def create_invite_batch():
    """Send the same invitation to multiple emails and/or Gov Hub users."""
    auth_err = _auth_required_json()
    if auth_err:
        return auth_err
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body = request.get_json(silent=True) or {}
    invite_type = (body.get('type') or body.get('invite_type') or '').strip()
    message = body.get('message')
    target = body.get('target')
    if not isinstance(target, dict):
        target = {}
    emails = body.get('emails')
    if emails is None and body.get('email'):
        emails = body.get('email')
    invitee_user_ids = body.get('invitee_user_ids') or body.get('user_ids') or []
    if not isinstance(invitee_user_ids, list):
        invitee_user_ids = [invitee_user_ids] if invitee_user_ids else []
    resp, status = create_invitations_bulk(
        invite_type=invite_type,
        inviter_id=current_user['id'],
        emails=emails,
        invitee_user_ids=invitee_user_ids,
        message=message,
        target=target,
    )
    return jsonify(resp), status


@bp.route('/by-token/<token>/', methods=['GET'])
def preview_invite(token):
    body, status = preview_invitation(token)
    return jsonify(body), status


@bp.route('/by-token/<token>/accept/', methods=['POST'])
def accept_invite(token):
    auth_err = _auth_required_json()
    if auth_err:
        return auth_err
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body, status = accept_invitation(token, current_user['id'])
    return jsonify(body), status


@bp.route('/by-token/<token>/revoke/', methods=['POST'])
def revoke_invite(token):
    auth_err = _auth_required_json()
    if auth_err:
        return auth_err
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body, status = revoke_invitation(token, current_user['id'])
    return jsonify(body), status


@bp.route('/by-token/<token>/decline/', methods=['POST'])
def decline_invite(token):
    auth_err = _auth_required_json()
    if auth_err:
        return auth_err
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    body, status = decline_invitation(token, current_user['id'])
    return jsonify(body), status
