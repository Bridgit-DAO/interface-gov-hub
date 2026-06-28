"""Referral attribution recording and referrer resolution for Gov Hub."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from extensions import db
from models import User, ReferralAttribution, ReferralLanding
from services.referral_tokens import attribution_from_token, create_scoped_share_ref_token


def resolve_referrer_from_token(
    ref_token: Optional[str],
    *,
    current_user_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Resolve referrer from a scoped ref_token only.
    Returns (referrer_user_id, token_attribution_dict).
    """
    if not ref_token:
        return None, None
    attr = attribution_from_token(ref_token)
    if not attr or not attr.get('valid'):
        return None, attr
    referrer_id = attr.get('referrer_user_id')
    if not referrer_id or referrer_id == current_user_id:
        return None, attr
    if not User.query.get(referrer_id):
        return None, attr
    return referrer_id, attr


def record_referral_attribution(
    *,
    referrer_user_id: str,
    converted_user_id: Optional[str],
    scope_type: str,
    scope_id: str,
    entity_type: str,
    entity_id: str,
    conversion_type: str,
    channel: Optional[str] = None,
    campaign: Optional[str] = None,
    share_event_id: Optional[str] = None,
    referral_token: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ReferralAttribution:
    import json

    meta_str = json.dumps(metadata) if metadata else None
    row = ReferralAttribution(
        id=str(uuid4()),
        product='gov_hub',
        referrer_user_id=referrer_user_id,
        converted_user_id=converted_user_id,
        scope_type=scope_type,
        scope_id=scope_id,
        entity_type=entity_type,
        entity_id=entity_id,
        conversion_type=conversion_type,
        channel=channel,
        campaign=campaign,
        share_event_id=share_event_id,
        referral_token=referral_token,
        legacy_referral_code=None,
        metadata_json=meta_str,
        converted_at=datetime.utcnow(),
    )
    db.session.add(row)
    return row


def build_waitlist_referral_url(host_url: str, layer_slug: str, waitlist_id: str, ref_token: str) -> str:
    base = host_url.rstrip('/')
    return f'{base}/layers/{layer_slug}/waitlist/{waitlist_id}/?ref_token={ref_token}'


def build_layer_referral_url(host_url: str, layer_slug: str, ref_token: str) -> str:
    base = host_url.rstrip('/')
    return f'{base}/layers/{layer_slug}/?ref_token={ref_token}'


def issue_layer_referral_link(host_url: str, layer, user, channel: str = 'layer_join') -> Dict[str, str]:
    ref_token = create_scoped_share_ref_token(
        referrer_user_id=user.id,
        entity_type='layer',
        entity_id=layer.id,
        scope_type='layer',
        scope_id=layer.id,
        product='gov_hub',
        channel=channel,
    )
    return {
        'ref_token': ref_token,
        'url': build_layer_referral_url(host_url, layer.slug, ref_token),
        'scope_type': 'layer',
        'scope_id': layer.id,
    }


def issue_waitlist_referral_link(host_url: str, layer, waitlist, user, channel: str = 'waitlist') -> Dict[str, str]:
    ref_token = create_scoped_share_ref_token(
        referrer_user_id=user.id,
        entity_type='waitlist',
        entity_id=waitlist.id,
        scope_type='waitlist',
        scope_id=waitlist.id,
        product='gov_hub',
        channel=channel,
    )
    return {
        'ref_token': ref_token,
        'url': build_waitlist_referral_url(host_url, layer.slug, waitlist.id, ref_token),
        'scope_type': 'waitlist',
        'scope_id': waitlist.id,
    }


def record_referral_landing(
    *,
    ref_token: str,
    landing_url: str,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[ReferralLanding]:
    """Record an anonymous landing from a scoped ref_token."""
    attr = attribution_from_token(ref_token)
    if not attr or not attr.get('valid'):
        return None
    import json

    row = ReferralLanding(
        id=str(uuid4()),
        referrer_user_id=attr.get('referrer_user_id'),
        scope_type=attr.get('scope_type') or 'platform',
        scope_id=attr.get('scope_id') or '',
        entity_type=attr.get('entity_type') or 'layer',
        entity_id=attr.get('entity_id') or '',
        channel=attr.get('channel'),
        landing_url=landing_url[:500],
        referral_token=ref_token,
        user_agent=(user_agent or '')[:500] or None,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.session.add(row)
    return row


def get_scope_referral_stats(scope_type: str, scope_id: str) -> Dict[str, Any]:
    """Aggregate landings and conversions for a scope (layer, waitlist, …)."""
    from sqlalchemy import func

    landing_count = ReferralLanding.query.filter_by(scope_type=scope_type, scope_id=scope_id).count()
    conversion_count = ReferralAttribution.query.filter_by(scope_type=scope_type, scope_id=scope_id).count()

    conversion_rows = (
        db.session.query(
            ReferralAttribution.referrer_user_id,
            ReferralAttribution.conversion_type,
            func.count(ReferralAttribution.id),
        )
        .filter_by(scope_type=scope_type, scope_id=scope_id)
        .group_by(ReferralAttribution.referrer_user_id, ReferralAttribution.conversion_type)
        .all()
    )
    landing_rows = (
        db.session.query(ReferralLanding.referrer_user_id, func.count(ReferralLanding.id))
        .filter_by(scope_type=scope_type, scope_id=scope_id)
        .group_by(ReferralLanding.referrer_user_id)
        .all()
    )

    referrer_ids = {r[0] for r in conversion_rows if r[0]} | {r[0] for r in landing_rows if r[0]}
    users = {u.id: u for u in User.query.filter(User.id.in_(list(referrer_ids))).all()} if referrer_ids else {}

    by_referrer: Dict[str, Dict[str, Any]] = {}
    for uid, conv_type, n in conversion_rows:
        if not uid:
            continue
        entry = by_referrer.setdefault(uid, {'landings': 0, 'conversions': 0, 'by_type': {}})
        entry['conversions'] += n
        entry['by_type'][conv_type] = entry['by_type'].get(conv_type, 0) + n
    for uid, n in landing_rows:
        if not uid:
            continue
        entry = by_referrer.setdefault(uid, {'landings': 0, 'conversions': 0, 'by_type': {}})
        entry['landings'] = n

    referrers = []
    for uid, stats in by_referrer.items():
        u = users.get(uid)
        referrers.append({
            'user_id': uid,
            'username': u.username if u else None,
            'display_name': (u.displayName or u.name or u.username) if u else None,
            'landings': stats['landings'],
            'conversions': stats['conversions'],
            'by_type': stats['by_type'],
        })
    referrers.sort(key=lambda x: (-x['conversions'], -x['landings']))

    return {
        'scope_type': scope_type,
        'scope_id': scope_id,
        'landing_count': landing_count,
        'conversion_count': conversion_count,
        'referrers': referrers,
    }
