"""HMAC signed referral tokens – interoperable with canopi/utils/shareRefToken.js."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

DEFAULT_TTL_DAYS = 90
UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.I,
)

VALID_ENTITY_TYPES = frozenset({
    'message', 'anchor', 'community', 'profile',
    'layer', 'waitlist', 'user_signup', 'embed_instance',
})
VALID_SCOPE_TYPES = frozenset({
    'platform', 'org', 'layer', 'waitlist', 'campaign', 'community', 'embed',
})
VALID_PRODUCTS = frozenset({'canopi', 'gov_hub'})


def _secret() -> str:
    secret = (
        os.environ.get('REFERRAL_TOKEN_SECRET')
        or os.environ.get('SHARE_REF_HMAC_SECRET')
        or os.environ.get('SECRET_KEY')
        or ''
    ).strip()
    if len(secret) < 16:
        raise ValueError(
            'REFERRAL_TOKEN_SECRET or SHARE_REF_HMAC_SECRET must be at least 16 characters'
        )
    return secret


def _b64url_encode(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(',', ':'), sort_keys=False).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _b64url_decode(encoded: str) -> Dict[str, Any]:
    pad = '=' * (-len(encoded) % 4)
    raw = base64.urlsafe_b64decode(encoded + pad)
    return json.loads(raw.decode('utf-8'))


def _sign(encoded_payload: str) -> str:
    digest = hmac.new(
        _secret().encode('utf-8'),
        encoded_payload.encode('utf-8'),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).decode('ascii').rstrip('=')


def _build_payload(
    *,
    version: int,
    referrer_user_id: str,
    entity_type: str,
    entity_id: str,
    share_event_id: Optional[str] = None,
    product: Optional[str] = None,
    scope_type: Optional[str] = None,
    scope_id: Optional[str] = None,
    campaign: Optional[str] = None,
    channel: Optional[str] = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> Dict[str, Any]:
    if not UUID_RE.match(str(referrer_user_id or '')):
        raise ValueError('referrer_user_id must be a UUID')
    if entity_type not in VALID_ENTITY_TYPES:
        raise ValueError(f'entity_type must be one of: {sorted(VALID_ENTITY_TYPES)}')
    entity_id = str(entity_id or '').strip()
    if not entity_id:
        raise ValueError('entity_id is required')
    now = int(time.time())
    payload: Dict[str, Any] = {
        'v': version,
        'referrerUserId': str(referrer_user_id),
        'entityType': entity_type,
        'entityId': entity_id,
        'iat': now,
        'exp': now + max(1, int(ttl_days or DEFAULT_TTL_DAYS)) * 86400,
    }
    if share_event_id:
        payload['shareEventId'] = str(share_event_id)
    if version >= 2:
        prod = (product or 'gov_hub').strip()
        if prod not in VALID_PRODUCTS:
            raise ValueError(f'product must be one of: {sorted(VALID_PRODUCTS)}')
        st = (scope_type or 'layer').strip()
        if st not in VALID_SCOPE_TYPES:
            raise ValueError(f'scope_type must be one of: {sorted(VALID_SCOPE_TYPES)}')
        sid = str(scope_id or '').strip()
        if not sid:
            raise ValueError('scope_id is required for v2 tokens')
        payload['product'] = prod
        payload['scopeType'] = st
        payload['scopeId'] = sid
        if campaign:
            payload['campaign'] = str(campaign)[:64]
        if channel:
            payload['channel'] = str(channel)[:32]
    return payload


def create_scoped_share_ref_token(
    *,
    referrer_user_id: str,
    entity_type: str,
    entity_id: str,
    scope_type: str,
    scope_id: str,
    product: str = 'gov_hub',
    campaign: Optional[str] = None,
    channel: Optional[str] = None,
    share_event_id: Optional[str] = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
) -> str:
    payload = _build_payload(
        version=2,
        referrer_user_id=referrer_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        share_event_id=share_event_id,
        product=product,
        scope_type=scope_type,
        scope_id=scope_id,
        campaign=campaign,
        channel=channel,
        ttl_days=ttl_days,
    )
    encoded = _b64url_encode(payload)
    return f'{encoded}.{_sign(encoded)}'


def verify_share_ref_token(token: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    if not token or '.' not in token:
        return False, None, 'missing_token'
    encoded_payload, signature = token.split('.', 1)
    if not encoded_payload or not signature:
        return False, None, 'malformed_token'
    expected = _sign(encoded_payload)
    if not hmac.compare_digest(expected, signature):
        return False, None, 'bad_signature'
    try:
        payload = _b64url_decode(encoded_payload)
    except (json.JSONDecodeError, ValueError):
        return False, None, 'bad_payload'
    if not payload.get('exp') or int(payload['exp']) < int(time.time()):
        return False, None, 'expired'
    version = int(payload.get('v') or 1)
    if version not in (1, 2):
        return False, None, 'unsupported_version'
    if not UUID_RE.match(str(payload.get('referrerUserId') or '')):
        return False, None, 'invalid_referrer'
    if str(payload.get('entityType') or '') not in VALID_ENTITY_TYPES:
        return False, None, 'invalid_entity_type'
    if version >= 2:
        if str(payload.get('product') or '') not in VALID_PRODUCTS:
            return False, None, 'invalid_product'
        if str(payload.get('scopeType') or '') not in VALID_SCOPE_TYPES:
            return False, None, 'invalid_scope_type'
        if not str(payload.get('scopeId') or '').strip():
            return False, None, 'missing_scope_id'
    return True, payload, None


def attribution_from_token(token: str) -> Optional[Dict[str, Any]]:
    ok, payload, reason = verify_share_ref_token(token)
    if not ok or not payload:
        return {'valid': False, 'reason': reason}
    version = int(payload.get('v') or 1)
    return {
        'valid': True,
        'version': version,
        'referrer_user_id': payload.get('referrerUserId'),
        'entity_type': payload.get('entityType'),
        'entity_id': payload.get('entityId'),
        'share_event_id': payload.get('shareEventId'),
        'product': payload.get('product') or 'canopi',
        'scope_type': payload.get('scopeType') or 'platform',
        'scope_id': payload.get('scopeId'),
        'campaign': payload.get('campaign'),
        'channel': payload.get('channel'),
    }
