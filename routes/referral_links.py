"""Scoped referral link API (v2 tokens)."""
from flask import Blueprint, jsonify, request

from extensions import db
from models import Layer, Waitlist, User
from services.identity import get_current_user, require_auth, get_or_create_referral_code
from services.coordination import is_layer_admin
from services.referral_tokens import create_scoped_share_ref_token
from services.referral_attribution import build_layer_referral_url, build_waitlist_referral_url

bp = Blueprint('referral_links', __name__, url_prefix='/api')


@bp.route('/layers/<layer_id>/referral-link/', methods=['GET'])
@require_auth
def layer_referral_link(layer_id):
    """Generate a scoped referral link for joining a layer."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    layer = Layer.query.get(layer_id)
    if not layer:
        layer = Layer.query.filter_by(slug=layer_id).first()
    if not layer:
        return jsonify({'error': 'Layer not found'}), 404

    user = User.query.get(current_user['id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    channel = (request.args.get('channel') or 'layer_join').strip()[:32]
    ref_token = create_scoped_share_ref_token(
        referrer_user_id=user.id,
        entity_type='layer',
        entity_id=layer.id,
        scope_type='layer',
        scope_id=layer.id,
        product='gov_hub',
        channel=channel,
    )
    url = build_layer_referral_url(request.host_url, layer.slug, ref_token)
    legacy_code = get_or_create_referral_code(user)

    return jsonify({
        'ref_token': ref_token,
        'url': url,
        'legacy_referral_code': legacy_code,
        'legacy_url': f"{request.host_url}layers/{layer.slug}/?ref={legacy_code}",
        'scope_type': 'layer',
        'scope_id': layer.id,
    })


@bp.route('/waitlists/<waitlist_id>/referral-link/', methods=['GET'])
@require_auth
def waitlist_referral_link(waitlist_id):
    """Generate a scoped referral link for a waitlist (when referrals enabled)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    waitlist = Waitlist.query.get_or_404(waitlist_id)
    layer = Layer.query.get_or_404(waitlist.layer_id)

    if not waitlist.referrals:
        return jsonify({'error': 'Referrals are not enabled for this waitlist'}), 400

    user = User.query.get(current_user['id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404

    channel = (request.args.get('channel') or 'waitlist').strip()[:32]
    ref_token = create_scoped_share_ref_token(
        referrer_user_id=user.id,
        entity_type='waitlist',
        entity_id=waitlist.id,
        scope_type='waitlist',
        scope_id=waitlist.id,
        product='gov_hub',
        channel=channel,
    )
    url = build_waitlist_referral_url(request.host_url, layer.slug, waitlist.id, ref_token)
    legacy_code = get_or_create_referral_code(user)

    return jsonify({
        'ref_token': ref_token,
        'url': url,
        'legacy_referral_code': legacy_code,
        'legacy_url': f"{request.host_url}layers/{layer.slug}/waitlist/{waitlist.id}/?ref={legacy_code}",
        'scope_type': 'waitlist',
        'scope_id': waitlist.id,
    })
