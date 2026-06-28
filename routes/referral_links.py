"""Scoped referral link API, landings, and stats."""
from flask import Blueprint, jsonify, request

from extensions import db
from models import Layer, Waitlist, User
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin
from services.referral_attribution import (
    issue_layer_referral_link,
    issue_waitlist_referral_link,
    record_referral_landing,
    get_scope_referral_stats,
)

bp = Blueprint('referral_links', __name__, url_prefix='/api')


@bp.route('/referral/landings/', methods=['POST'])
def record_landing():
    """Record anonymous landing from ref_token (no auth)."""
    data = request.get_json() or {}
    ref_token = (data.get('ref_token') or data.get('refToken') or '').strip()
    landing_url = (data.get('landing_url') or data.get('landingUrl') or request.referrer or '').strip()
    if not ref_token:
        return jsonify({'error': 'ref_token is required'}), 400
    if not landing_url:
        landing_url = f"{request.host_url.rstrip('/')}{request.path}"

    row = record_referral_landing(
        ref_token=ref_token,
        landing_url=landing_url,
        user_agent=request.headers.get('User-Agent'),
        metadata={
            'utm_source': data.get('utm_source') or data.get('utmSource'),
            'utm_medium': data.get('utm_medium') or data.get('utmMedium'),
            'utm_campaign': data.get('utm_campaign') or data.get('utmCampaign'),
        },
    )
    if not row:
        return jsonify({'error': 'Invalid or expired ref_token'}), 400
    db.session.commit()
    return jsonify({'success': True, 'landing_id': row.id}), 201


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
    payload = issue_layer_referral_link(request.host_url, layer, user, channel=channel)
    return jsonify(payload)


@bp.route('/layers/<layer_id>/referral-stats/', methods=['GET'])
@require_auth
def layer_referral_stats(layer_id):
    """Referral funnel stats for a layer (layer admin only)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    layer = Layer.query.get(layer_id)
    if not layer:
        layer = Layer.query.filter_by(slug=layer_id).first()
    if not layer:
        return jsonify({'error': 'Layer not found'}), 404
    if not is_layer_admin(layer, current_user):
        return jsonify({'error': 'Layer admin access required'}), 403

    stats = get_scope_referral_stats('layer', layer.id)
    stats['layer_id'] = layer.id
    stats['layer_slug'] = layer.slug
    return jsonify(stats)


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
    payload = issue_waitlist_referral_link(request.host_url, layer, waitlist, user, channel=channel)
    return jsonify(payload)


@bp.route('/waitlists/<waitlist_id>/referral-stats/', methods=['GET'])
@require_auth
def waitlist_referral_stats(waitlist_id):
    """Referral funnel stats for a waitlist (layer admin only)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    waitlist = Waitlist.query.get_or_404(waitlist_id)
    layer = Layer.query.get_or_404(waitlist.layer_id)
    if not is_layer_admin(layer, current_user):
        return jsonify({'error': 'Layer admin access required'}), 403

    stats = get_scope_referral_stats('waitlist', waitlist.id)
    stats['waitlist_id'] = waitlist.id
    stats['waitlist_name'] = waitlist.name
    return jsonify(stats)
