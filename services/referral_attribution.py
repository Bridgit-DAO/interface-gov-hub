"""Referral attribution recording and referrer resolution for Gov Hub."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from extensions import db
from models import User, ReferralAttribution
from services.referral_tokens import attribution_from_token


def resolve_referrer(
    *,
    ref_token: Optional[str] = None,
    referral_code: Optional[str] = None,
    current_user_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """
    Resolve referrer from scoped token or legacy referral code.
    Returns (referrer_user_id, legacy_code_used, token_attribution_dict).
    """
    if ref_token:
        attr = attribution_from_token(ref_token)
        if attr and attr.get('valid'):
            referrer_id = attr.get('referrer_user_id')
            if referrer_id and referrer_id != current_user_id:
                user = User.query.get(referrer_id)
                if user:
                    return referrer_id, None, attr

    code = (referral_code or '').strip()
    if not code or code.startswith('invite:'):
        return None, code or None, None

    referrer = User.query.filter_by(referral_code=code).first()
    if referrer and referrer.id != current_user_id:
        return referrer.id, code, None
    return None, code, None


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
    legacy_referral_code: Optional[str] = None,
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
        legacy_referral_code=legacy_referral_code,
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
