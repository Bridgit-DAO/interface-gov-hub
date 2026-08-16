"""Scoped email campaign API (layer/guild admin only)."""
from __future__ import annotations

from datetime import datetime

from dateutil import parser as date_parser
from flask import Blueprint, jsonify, request

from models import Guild, Layer, ScopedEmailCampaign, User
from services.identity import get_current_user, require_auth
from services.resend_mail import get_resend_from
from services.scope_email import (
    cancel_campaign,
    can_manage_scope_email,
    create_campaign,
    guild_recipient_groups,
    layer_recipient_groups,
    list_admin_email_scopes,
    process_due_deliveries,
)

bp = Blueprint('scope_email', __name__, url_prefix='/api/scope-email')


@bp.route('/admin-scopes/', methods=['GET'])
@require_auth
def api_admin_email_scopes():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    return jsonify(list_admin_email_scopes(user)), 200


@bp.route('/layers/<layer_id>/recipients/', methods=['GET'])
@require_auth
def api_layer_email_recipients(layer_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    if not can_manage_scope_email(user, 'layer', layer_id):
        return jsonify({'error': 'Layer admin required'}), 403
    layer = Layer.query.get_or_404(layer_id)
    from_config = get_resend_from()
    from_addr = (from_config or {}).get('formatted') or 'Gov Hub <no-reply@hub.themetalayer.org>'
    from models import LayerMember

    people = []
    seen = set()
    for m in LayerMember.query.filter_by(layer_id=layer_id, status='active').filter(LayerMember.left_at.is_(None)).all():
        if not m.user or not m.user.email or m.user_id in seen:
            continue
        seen.add(m.user_id)
        people.append({
            'user_id': m.user_id,
            'email': m.user.email,
            'label': m.user.displayName or m.user.username or m.user.email,
        })
    return jsonify({
        'scope_type': 'layer',
        'scope_id': layer_id,
        'scope_name': layer.name,
        'groups': layer_recipient_groups(layer_id),
        'people': people,
        'from_options': [{'value': from_addr, 'label': 'Default (Gov Hub noreply)'}],
        'schedule_modes': [
            {'value': 'immediate', 'label': 'Send now'},
            {'value': 'at', 'label': 'Send at date/time'},
            {'value': 'after_join', 'label': 'Hours after join'},
        ],
        'anchor_kinds': [
            {'value': 'layer_member', 'label': 'Layer membership join'},
            {'value': 'waitlist_member', 'label': 'Waitlist join'},
        ],
    }), 200


@bp.route('/guilds/<guild_id>/recipients/', methods=['GET'])
@require_auth
def api_guild_email_recipients(guild_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    if not can_manage_scope_email(user, 'guild', guild_id):
        return jsonify({'error': 'Guild admin required'}), 403
    guild = Guild.query.get_or_404(guild_id)
    from_config = get_resend_from()
    from_addr = (from_config or {}).get('formatted') or 'Gov Hub <no-reply@hub.themetalayer.org>'
    people = []
    from models import GuildMembership

    for m in GuildMembership.query.filter_by(guild_id=guild_id, membership_state='active').all():
        if not m.user or not m.user.email:
            continue
        people.append({
            'user_id': m.user_id,
            'email': m.user.email,
            'label': m.user.displayName or m.user.username or m.user.email,
        })
    return jsonify({
        'scope_type': 'guild',
        'scope_id': guild_id,
        'scope_name': guild.name,
        'groups': guild_recipient_groups(guild_id),
        'people': people,
        'from_options': [{'value': from_addr, 'label': 'Default (Gov Hub noreply)'}],
        'schedule_modes': [
            {'value': 'immediate', 'label': 'Send now'},
            {'value': 'at', 'label': 'Send at date/time'},
            {'value': 'after_join', 'label': 'Hours after guild join'},
        ],
        'anchor_kinds': [{'value': 'guild_member', 'label': 'Guild membership join'}],
    }), 200


def _parse_campaign_payload(data: dict):
    groups = data.get('groups') or []
    user_ids = data.get('user_ids') or []
    subject = (data.get('subject') or '').strip()
    body = (data.get('body') or '').strip()
    schedule_mode = (data.get('schedule_mode') or 'immediate').strip().lower()
    scheduled_at = None
    if data.get('scheduled_at'):
        try:
            scheduled_at = date_parser.parse(str(data.get('scheduled_at')))
        except Exception:
            return None, 'Invalid scheduled_at', 400
    delay_hours = data.get('delay_hours')
    if delay_hours is not None and delay_hours != '':
        try:
            delay_hours = float(delay_hours)
        except (TypeError, ValueError):
            return None, 'Invalid delay_hours', 400
    else:
        delay_hours = None
    anchor_kind = (data.get('anchor_kind') or '').strip() or None
    return {
        'groups': groups,
        'user_ids': user_ids,
        'subject': subject,
        'body': body,
        'schedule_mode': schedule_mode,
        'scheduled_at': scheduled_at,
        'delay_hours': delay_hours,
        'anchor_kind': anchor_kind,
    }, None, None


@bp.route('/layers/<layer_id>/campaigns/', methods=['GET'])
@require_auth
def api_list_layer_campaigns(layer_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    if not can_manage_scope_email(user, 'layer', layer_id):
        return jsonify({'error': 'Layer admin required'}), 403
    rows = (
        ScopedEmailCampaign.query.filter_by(scope_type='layer', scope_id=layer_id)
        .order_by(ScopedEmailCampaign.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({'campaigns': [r.to_dict() for r in rows]}), 200


@bp.route('/guilds/<guild_id>/campaigns/', methods=['GET'])
@require_auth
def api_list_guild_campaigns(guild_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    if not can_manage_scope_email(user, 'guild', guild_id):
        return jsonify({'error': 'Guild admin required'}), 403
    rows = (
        ScopedEmailCampaign.query.filter_by(scope_type='guild', scope_id=guild_id)
        .order_by(ScopedEmailCampaign.created_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({'campaigns': [r.to_dict() for r in rows]}), 200


@bp.route('/layers/<layer_id>/campaigns/', methods=['POST'])
@require_auth
def api_create_layer_campaign(layer_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    payload, err, code = _parse_campaign_payload(request.get_json() or {})
    if err:
        return jsonify({'error': err}), code
    campaign, err, code = create_campaign(
        scope_type='layer',
        scope_id=layer_id,
        user=user,
        **payload,
    )
    if err:
        return jsonify({'error': err}), code
    return jsonify({'campaign': campaign.to_dict()}), code


@bp.route('/guilds/<guild_id>/campaigns/', methods=['POST'])
@require_auth
def api_create_guild_campaign(guild_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    payload, err, code = _parse_campaign_payload(request.get_json() or {})
    if err:
        return jsonify({'error': err}), code
    campaign, err, code = create_campaign(
        scope_type='guild',
        scope_id=guild_id,
        user=user,
        **payload,
    )
    if err:
        return jsonify({'error': err}), code
    return jsonify({'campaign': campaign.to_dict()}), code


@bp.route('/campaigns/<campaign_id>/', methods=['DELETE'])
@require_auth
def api_cancel_campaign(campaign_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    campaign = ScopedEmailCampaign.query.get_or_404(campaign_id)
    ok, err, code = cancel_campaign(campaign, user)
    if not ok:
        return jsonify({'error': err}), code
    return jsonify({'campaign': campaign.to_dict()}), code


@bp.route('/process-due/', methods=['POST'])
@require_auth
def api_process_due_campaigns():
    """Site admin manual trigger; cron uses CLI."""
    user = get_current_user()
    if not user or user.get('role') != 'admin':
        return jsonify({'error': 'Site admin required'}), 403
    summary = process_due_deliveries()
    return jsonify(summary), 200
