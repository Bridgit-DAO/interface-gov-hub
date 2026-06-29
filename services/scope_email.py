"""Layer/guild admin email campaigns with scheduling."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_

from extensions import db
from models import (
    Claim,
    EmailUnsubscribe,
    Guild,
    GuildMembership,
    Layer,
    LayerMember,
    ScopedEmailCampaign,
    ScopedEmailDelivery,
    User,
    Waitlist,
    WaitlistEmailSignup,
    WaitlistEntry,
    Workgroup,
    WorkingGroupMember,
)
from services.coordination import is_layer_admin
from services.email import make_unsubscribe_token
from services.guild_phase1 import is_guild_officer
from services.resend_mail import resend_configured, send_resend_email_result

MAX_RECIPIENTS_PER_SEND = 100
DELIVERY_BATCH_LIMIT = 50


def can_manage_scope_email(user: Optional[dict], scope_type: str, scope_id: str) -> bool:
    if not user or not scope_id:
        return False
    if scope_type == 'layer':
        layer = Layer.query.get(scope_id)
        return bool(layer and is_layer_admin(layer, user))
    if scope_type == 'guild':
        return is_guild_officer(scope_id, user['id'])
    return False


def list_admin_email_scopes(user: Optional[dict]) -> Dict[str, List[Dict[str, Any]]]:
    layers: List[Dict[str, Any]] = []
    guilds: List[Dict[str, Any]] = []
    if not user:
        return {'layers': layers, 'guilds': guilds}

    if user.get('role') == 'admin':
        for layer in Layer.query.order_by(Layer.name.asc()).all():
            layers.append({'id': layer.id, 'slug': layer.slug, 'name': layer.name})
    else:
        seen_layers = set()
        for layer in Layer.query.filter_by(initiator_id=user['id']).all():
            if layer.id not in seen_layers:
                seen_layers.add(layer.id)
                layers.append({'id': layer.id, 'slug': layer.slug, 'name': layer.name})
        from models import LayerAdmin

        for row in LayerAdmin.query.filter_by(user_id=user['id']).all():
            layer = Layer.query.get(row.layer_id)
            if layer and layer.id not in seen_layers:
                seen_layers.add(layer.id)
                layers.append({'id': layer.id, 'slug': layer.slug, 'name': layer.name})

    seen_guilds = set()
    for m in GuildMembership.query.filter_by(user_id=user['id'], membership_state='active').all():
        if m.role not in ('initiator', 'admin') or m.guild_id in seen_guilds:
            continue
        guild = Guild.query.get(m.guild_id)
        if not guild:
            continue
        seen_guilds.add(guild.id)
        guilds.append({'id': guild.id, 'slug': guild.slug, 'name': guild.name})

    return {'layers': layers, 'guilds': guilds}


def _is_unsubscribed(scope_type: str, scope_id: str, email: str, user_id: Optional[str]) -> bool:
    key = (email or '').strip().lower()
    if not key:
        return True
    q = EmailUnsubscribe.query
    if scope_type == 'layer':
        q = q.filter_by(layer_id=scope_id)
    else:
        q = q.filter_by(guild_id=scope_id)
    if user_id:
        q = q.filter(or_(EmailUnsubscribe.email == key, EmailUnsubscribe.user_id == user_id))
    else:
        q = q.filter(EmailUnsubscribe.email == key)
    return q.first() is not None


def resolve_layer_recipients(
    layer_id: str,
    groups: List[str],
    *,
    user_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    seen = set()
    result: List[Dict[str, Any]] = []

    def add(email: Optional[str], user_id: Optional[str] = None, anchor_at: Optional[datetime] = None):
        if not email or '@' not in email:
            return
        key = email.lower()
        if key in seen or _is_unsubscribed('layer', layer_id, key, user_id):
            return
        seen.add(key)
        result.append({'email': email, 'user_id': user_id, 'anchor_at': anchor_at})

    groups = groups or []
    if 'members' in groups:
        for m in LayerMember.query.filter_by(layer_id=layer_id, status='active').filter(LayerMember.left_at.is_(None)).all():
            if m.user and m.user.email:
                add(m.user.email, m.user_id, m.joined_at)

    if 'role_holders' in groups:
        for c in Claim.query.filter_by(layer_id=layer_id, status='active').all():
            if c.claimant and c.claimant.email:
                add(c.claimant.email, c.claimant_id, None)

    for k in groups:
        if not k.startswith('waitlist_'):
            continue
        wid = k.replace('waitlist_', '', 1)
        if not wid:
            continue
        for e in WaitlistEntry.query.filter_by(waitlist_id=wid, left_at=None).all():
            if e.user and e.user.email:
                add(e.user.email, e.user_id, e.joined_at)
        for e in WaitlistEmailSignup.query.filter_by(waitlist_id=wid, left_at=None).filter(
            WaitlistEmailSignup.verified_at.isnot(None)
        ).all():
            add(e.email, None, e.verified_at or e.created_at)

    if 'workgroup_members' in groups:
        for wg in Workgroup.query.filter_by(layer_id=layer_id).all():
            for m in WorkingGroupMember.query.filter_by(group_acronym=wg.acronym).all():
                if m.user_id:
                    u = User.query.get(m.user_id)
                    if u and u.email:
                        add(u.email, u.id, None)
                elif m.user_name:
                    u = User.query.filter(or_(User.username == m.user_name, User.name == m.user_name)).first()
                    if u and u.email:
                        add(u.email, u.id, None)

    if user_ids:
        for uid in user_ids:
            uid = (uid or '').strip()
            if not uid:
                continue
            u = User.query.get(uid)
            if not u or not u.email:
                continue
            member = LayerMember.query.filter_by(layer_id=layer_id, user_id=uid, status='active').first()
            anchor = member.joined_at if member else None
            add(u.email, u.id, anchor)

    return result


def resolve_guild_recipients(
    guild_id: str,
    groups: List[str],
    *,
    user_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    seen = set()
    result: List[Dict[str, Any]] = []

    def add(email: Optional[str], user_id: Optional[str] = None, anchor_at: Optional[datetime] = None):
        if not email or '@' not in email:
            return
        key = email.lower()
        if key in seen or _is_unsubscribed('guild', guild_id, key, user_id):
            return
        seen.add(key)
        result.append({'email': email, 'user_id': user_id, 'anchor_at': anchor_at})

    groups = groups or []
    memberships = GuildMembership.query.filter_by(guild_id=guild_id, membership_state='active').all()
    if 'members' in groups:
        for m in memberships:
            if m.user and m.user.email:
                add(m.user.email, m.user_id, m.joined_at)
    if 'officers' in groups:
        for m in memberships:
            if m.role in ('initiator', 'admin') and m.user and m.user.email:
                add(m.user.email, m.user_id, m.joined_at)

    if user_ids:
        member_ids = {m.user_id for m in memberships}
        for uid in user_ids:
            uid = (uid or '').strip()
            if not uid or uid not in member_ids:
                continue
            u = User.query.get(uid)
            if u and u.email:
                m = next((x for x in memberships if x.user_id == uid), None)
                add(u.email, u.id, m.joined_at if m else None)

    return result


def layer_recipient_groups(layer_id: str) -> Dict[str, Dict[str, Any]]:
    members_count = (
        LayerMember.query.filter_by(layer_id=layer_id, status='active')
        .filter(LayerMember.left_at.is_(None))
        .count()
    )
    role_holders = db.session.query(Claim.claimant_id).filter_by(layer_id=layer_id, status='active').distinct().count()
    waitlists: Dict[str, Dict[str, Any]] = {}
    for w in Waitlist.query.filter_by(layer_id=layer_id).all():
        uc = WaitlistEntry.query.filter_by(waitlist_id=w.id, left_at=None).count()
        ec = (
            WaitlistEmailSignup.query.filter_by(waitlist_id=w.id, left_at=None)
            .filter(WaitlistEmailSignup.verified_at.isnot(None))
            .count()
        )
        waitlists[f'waitlist_{w.id}'] = {'label': f'Waitlist: {w.name}', 'count': uc + ec}
    wg_count = 0
    for wg in Workgroup.query.filter_by(layer_id=layer_id).all():
        wg_count += WorkingGroupMember.query.filter_by(group_acronym=wg.acronym).count()
    groups = {
        'members': {'label': 'Layer members', 'count': members_count},
        'role_holders': {'label': 'Role holders', 'count': role_holders},
        'workgroup_members': {'label': 'Workgroup members', 'count': wg_count},
        **waitlists,
    }
    return groups


def guild_recipient_groups(guild_id: str) -> Dict[str, Dict[str, Any]]:
    memberships = GuildMembership.query.filter_by(guild_id=guild_id, membership_state='active').all()
    members_count = len(memberships)
    officers_count = sum(1 for m in memberships if m.role in ('initiator', 'admin'))
    return {
        'members': {'label': 'Guild members', 'count': members_count},
        'officers': {'label': 'Guild officers', 'count': officers_count},
    }


def _compute_send_at(
    campaign: ScopedEmailCampaign,
    recipient: Dict[str, Any],
    *,
    now: Optional[datetime] = None,
) -> datetime:
    now = now or datetime.utcnow()
    if campaign.schedule_mode == 'immediate':
        return now
    if campaign.schedule_mode == 'at':
        return campaign.scheduled_at or now
    delay = float(campaign.delay_hours or 0)
    anchor = recipient.get('anchor_at') or now
    return anchor + timedelta(hours=delay)


def _resolve_recipients(campaign: ScopedEmailCampaign) -> List[Dict[str, Any]]:
    spec = campaign.recipient_spec()
    groups = spec.get('groups') or []
    user_ids = spec.get('user_ids') or []
    if campaign.scope_type == 'layer':
        return resolve_layer_recipients(campaign.scope_id, groups, user_ids=user_ids)
    return resolve_guild_recipients(campaign.scope_id, groups, user_ids=user_ids)


def _filter_by_anchor(recipients: List[Dict[str, Any]], anchor_kind: Optional[str]) -> List[Dict[str, Any]]:
    if not anchor_kind:
        return recipients
    if anchor_kind == 'waitlist_member':
        return [r for r in recipients if r.get('anchor_at')]
    return recipients


def enqueue_campaign_deliveries(campaign: ScopedEmailCampaign) -> int:
    recipients = _resolve_recipients(campaign)
    if campaign.schedule_mode == 'after_join':
        recipients = _filter_by_anchor(recipients, campaign.anchor_kind)
    now = datetime.utcnow()
    created = 0
    for recipient in recipients:
        send_at = _compute_send_at(campaign, recipient, now=now)
        existing = None
        if recipient.get('user_id'):
            existing = ScopedEmailDelivery.query.filter_by(
                campaign_id=campaign.id,
                user_id=recipient['user_id'],
                status='pending',
            ).first()
        if existing:
            continue
        db.session.add(
            ScopedEmailDelivery(
                campaign_id=campaign.id,
                email=recipient['email'],
                user_id=recipient.get('user_id'),
                anchor_at=recipient.get('anchor_at'),
                send_at=send_at,
                status='pending',
            )
        )
        created += 1
    campaign.stats_total = (campaign.stats_total or 0) + created
    db.session.commit()
    return created


def create_campaign(
    *,
    scope_type: str,
    scope_id: str,
    user: dict,
    subject: str,
    body: str,
    schedule_mode: str,
    groups: List[str],
    user_ids: Optional[List[str]] = None,
    scheduled_at: Optional[datetime] = None,
    delay_hours: Optional[float] = None,
    anchor_kind: Optional[str] = None,
) -> Tuple[Optional[ScopedEmailCampaign], Optional[str], int]:
    if scope_type not in ('layer', 'guild'):
        return None, 'Invalid scope_type', 400
    if not can_manage_scope_email(user, scope_type, scope_id):
        return None, 'Admin access required for this layer or guild', 403
    if not resend_configured():
        return None, 'Email service not configured (RESEND_API_KEY)', 500

    schedule_mode = (schedule_mode or 'immediate').strip().lower()
    if schedule_mode not in ('immediate', 'at', 'after_join'):
        return None, 'schedule_mode must be immediate, at, or after_join', 400
    if not subject.strip():
        return None, 'Subject is required', 400
    if not body.strip():
        return None, 'Message body is required', 400
    if not groups and not user_ids:
        return None, 'Select at least one recipient group or person', 400

    if schedule_mode == 'at':
        if not scheduled_at:
            return None, 'scheduled_at is required for at mode', 400
        if scheduled_at <= datetime.utcnow():
            return None, 'scheduled_at must be in the future', 400
    if schedule_mode == 'after_join':
        if delay_hours is None or float(delay_hours) <= 0:
            return None, 'delay_hours must be greater than 0 for after_join mode', 400
        if scope_type == 'layer' and anchor_kind not in ('layer_member', 'waitlist_member'):
            return None, 'anchor_kind must be layer_member or waitlist_member', 400
        if scope_type == 'guild':
            anchor_kind = 'guild_member'

    preview = (
        resolve_layer_recipients(scope_id, groups, user_ids=user_ids)
        if scope_type == 'layer'
        else resolve_guild_recipients(scope_id, groups, user_ids=user_ids)
    )
    if not preview:
        return None, 'No recipients found for selected groups', 400
    if schedule_mode == 'immediate' and len(preview) > MAX_RECIPIENTS_PER_SEND:
        return None, f'Too many recipients ({len(preview)}). Maximum {MAX_RECIPIENTS_PER_SEND} per send.', 400

    status = 'active' if schedule_mode == 'after_join' else 'scheduled'
    campaign = ScopedEmailCampaign(
        scope_type=scope_type,
        scope_id=scope_id,
        created_by_id=user['id'],
        subject=subject.strip()[:255],
        body=body.strip(),
        schedule_mode=schedule_mode,
        scheduled_at=scheduled_at,
        delay_hours=float(delay_hours) if delay_hours is not None else None,
        anchor_kind=anchor_kind,
        recipient_spec_json=json.dumps({'groups': groups, 'user_ids': user_ids or []}),
        status=status,
    )
    db.session.add(campaign)
    db.session.commit()

    enqueue_campaign_deliveries(campaign)

    if schedule_mode == 'immediate':
        summary = process_due_deliveries(campaign_id=campaign.id, limit=MAX_RECIPIENTS_PER_SEND)
        campaign = ScopedEmailCampaign.query.get(campaign.id)
        if summary.get('sent', 0) == 0 and summary.get('failed', 0) > 0:
            return campaign, 'Failed to send email', 500

    return campaign, None, 201


def cancel_campaign(campaign: ScopedEmailCampaign, user: dict) -> Tuple[bool, Optional[str], int]:
    if not can_manage_scope_email(user, campaign.scope_type, campaign.scope_id):
        return False, 'Admin access required', 403
    if campaign.status in ('completed', 'cancelled'):
        return False, 'Campaign already finished', 400
    campaign.status = 'cancelled'
    campaign.completed_at = datetime.utcnow()
    ScopedEmailDelivery.query.filter_by(campaign_id=campaign.id, status='pending').update(
        {'status': 'cancelled'},
        synchronize_session=False,
    )
    db.session.commit()
    return True, None, 200


def enqueue_after_join(
    *,
    scope_type: str,
    scope_id: str,
    user_id: str,
    anchor_kind: str,
    anchor_at: datetime,
    waitlist_id: Optional[str] = None,
) -> int:
    campaigns = ScopedEmailCampaign.query.filter_by(
        scope_type=scope_type,
        scope_id=scope_id,
        schedule_mode='after_join',
        status='active',
        anchor_kind=anchor_kind,
    ).all()
    if not campaigns:
        return 0
    user = User.query.get(user_id)
    if not user or not user.email:
        return 0
    created = 0
    for campaign in campaigns:
        spec = campaign.recipient_spec()
        groups = spec.get('groups') or []
        user_ids = spec.get('user_ids') or []
        if campaign.anchor_kind == 'waitlist_member':
            if waitlist_id and f'waitlist_{waitlist_id}' not in groups and user_id not in user_ids:
                continue
        if user_id in user_ids:
            matched = True
        elif scope_type == 'layer':
            recs = resolve_layer_recipients(scope_id, groups, user_ids=[user_id])
            matched = any(r.get('user_id') == user_id for r in recs)
        else:
            recs = resolve_guild_recipients(scope_id, groups, user_ids=[user_id])
            matched = any(r.get('user_id') == user_id for r in recs)
        if not matched:
            continue
        existing = ScopedEmailDelivery.query.filter_by(campaign_id=campaign.id, user_id=user_id).first()
        if existing:
            continue
        send_at = anchor_at + timedelta(hours=float(campaign.delay_hours or 0))
        db.session.add(
            ScopedEmailDelivery(
                campaign_id=campaign.id,
                email=user.email.strip(),
                user_id=user_id,
                anchor_at=anchor_at,
                send_at=send_at,
                status='pending',
            )
        )
        campaign.stats_total = (campaign.stats_total or 0) + 1
        created += 1
    if created:
        db.session.commit()
    return created


def _scope_name(campaign: ScopedEmailCampaign) -> str:
    if campaign.scope_type == 'layer':
        layer = Layer.query.get(campaign.scope_id)
        return layer.name if layer else 'layer'
    guild = Guild.query.get(campaign.scope_id)
    return guild.name if guild else 'guild'


def _render_delivery_html(campaign: ScopedEmailCampaign, body: str, unsub_url: str) -> str:
    scope_name = _scope_name(campaign)
    html_body = body.replace('\n', '<br>')
    html_body += (
        f'<br><br><hr style="border:none;border-top:1px solid #eee;">'
        f'<p style="font-size:11px;color:#888;">'
        f'<a href="{unsub_url}">Unsubscribe</a> from {scope_name} emails on Gov Hub.</p>'
    )
    return html_body


def send_delivery(delivery: ScopedEmailDelivery, campaign: ScopedEmailCampaign, base_url: str) -> bool:
    uid = delivery.user_id or delivery.email
    unsub_token = make_unsubscribe_token(
        campaign.scope_id,
        str(uid),
        scope_type=campaign.scope_type,
    )
    unsub_url = f"{base_url.rstrip('/')}/unsubscribe?token={unsub_token}"
    html_body = _render_delivery_html(campaign, campaign.body, unsub_url)
    result = send_resend_email_result(
        to=[delivery.email],
        subject=campaign.subject,
        html=html_body,
        list_unsubscribe_url=unsub_url,
        tags=[
            {'name': 'category', 'value': 'scope_email'},
            {'name': 'scope', 'value': campaign.scope_type[:256]},
        ],
    )
    if result.get('ok'):
        delivery.status = 'sent'
        delivery.sent_at = datetime.utcnow()
        delivery.resend_id = result.get('id')
        campaign.stats_sent = (campaign.stats_sent or 0) + 1
        return True
    delivery.status = 'failed'
    delivery.error_message = result.get('error') or 'send failed'
    campaign.stats_failed = (campaign.stats_failed or 0) + 1
    return False


def _maybe_complete_campaign(campaign: ScopedEmailCampaign) -> None:
    if campaign.schedule_mode == 'after_join' and campaign.status == 'active':
        return
    pending = ScopedEmailDelivery.query.filter_by(campaign_id=campaign.id, status='pending').count()
    if pending == 0 and campaign.status in ('scheduled', 'active'):
        campaign.status = 'completed'
        campaign.completed_at = datetime.utcnow()


def process_due_deliveries(
    *,
    campaign_id: Optional[str] = None,
    limit: int = DELIVERY_BATCH_LIMIT,
    base_url: Optional[str] = None,
) -> Dict[str, int]:
    if not resend_configured():
        return {'sent': 0, 'failed': 0, 'skipped': 0, 'processed': 0}

    if not base_url:
        try:
            from flask import current_app
            from config import PUBLIC_BASE_URL, resolved_public_base_url

            base_url = resolved_public_base_url(current_app.config.get('PUBLIC_BASE_URL') or PUBLIC_BASE_URL)
        except RuntimeError:
            from config import PUBLIC_BASE_URL

            base_url = PUBLIC_BASE_URL

    now = datetime.utcnow()
    q = ScopedEmailDelivery.query.filter(
        ScopedEmailDelivery.status == 'pending',
        ScopedEmailDelivery.send_at <= now,
    ).order_by(ScopedEmailDelivery.send_at.asc())
    if campaign_id:
        q = q.filter_by(campaign_id=campaign_id)
    deliveries = q.limit(limit).all()

    sent = failed = skipped = 0
    touched_campaigns: Dict[str, ScopedEmailCampaign] = {}
    for delivery in deliveries:
        campaign = ScopedEmailCampaign.query.get(delivery.campaign_id)
        if not campaign or campaign.status == 'cancelled':
            delivery.status = 'cancelled'
            skipped += 1
            continue
        if campaign.status == 'scheduled' and campaign.schedule_mode == 'at':
            campaign.status = 'active'
        if _is_unsubscribed(campaign.scope_type, campaign.scope_id, delivery.email, delivery.user_id):
            delivery.status = 'skipped'
            skipped += 1
            continue
        if send_delivery(delivery, campaign, base_url):
            sent += 1
        else:
            failed += 1
        touched_campaigns[campaign.id] = campaign

    for campaign in touched_campaigns.values():
        _maybe_complete_campaign(campaign)
    db.session.commit()
    return {'sent': sent, 'failed': failed, 'skipped': skipped, 'processed': len(deliveries)}
