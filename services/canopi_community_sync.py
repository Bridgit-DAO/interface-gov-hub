"""HTTP sync from Gov Hub Layer → Canopi MetaCommunity (Revised Option C)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

import requests

log = logging.getLogger(__name__)


def _api_base() -> str:
    from flask import current_app

    return (
        os.environ.get('CANOPI_INTERNAL_API_URL')
        or current_app.config.get('CANOPI_INTERNAL_API_URL')
        or current_app.config.get('CANOPI_PUBLIC_URL')
        or 'http://127.0.0.1:3001'
    ).rstrip('/')


def _api_key() -> str:
    return (os.environ.get('GOV_HUB_API_KEY') or '').strip()


def _headers() -> Dict[str, str]:
    headers = {'Content-Type': 'application/json'}
    key = _api_key()
    if key:
        headers['Authorization'] = f'Bearer {key}'
    return headers


def _layer_payload(layer) -> Dict[str, Any]:
    from services.layer_features import get_effective_features

    payload = layer.to_dict()
    try:
        payload['effective_features'] = get_effective_features(layer)
    except Exception:
        pass
    return payload


def _should_sync(layer, *, force: bool = False) -> bool:
    if force:
        return True
    kind = (getattr(layer, 'layer_kind', None) or '').strip()
    if kind == 'auth_community':
        return True
    return (getattr(layer, 'approval_status', None) or '') == 'approved'


def provision_or_sync_layer(
    layer,
    *,
    canopi_meta_community_id: Optional[str] = None,
    force: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    POST provision or PATCH by-layer. Persists canopi_meta_community_id on success.
    Returns parsed JSON body or None when skipped/failed.
    """
    from extensions import db

    if not _should_sync(layer, force=force):
        return None

    if not _api_key():
        log.warning('GOV_HUB_API_KEY not set; skipping Canopi community sync for layer %s', layer.id)
        return None

    base = _api_base()
    body_layer = _layer_payload(layer)
    linked_id = getattr(layer, 'canopi_meta_community_id', None)
    link_target = canopi_meta_community_id or linked_id

    try:
        if linked_id:
            url = f'{base}/v1/internal/gov-hub/communities/by-layer/{layer.id}'
            resp = requests.patch(
                url,
                json={'layer': body_layer},
                headers=_headers(),
                timeout=30,
            )
        else:
            url = f'{base}/v1/internal/gov-hub/communities/provision'
            payload: Dict[str, Any] = {'layer': body_layer}
            if link_target:
                payload['canopiMetaCommunityId'] = link_target
            resp = requests.post(url, json=payload, headers=_headers(), timeout=30)

        if resp.status_code >= 400:
            log.warning(
                'Canopi community sync failed layer=%s status=%s body=%s',
                layer.id,
                resp.status_code,
                resp.text[:500],
            )
            return None

        data = resp.json() if resp.text else {}
        new_id = data.get('metaCommunityId')
        if new_id and getattr(layer, 'canopi_meta_community_id', None) != new_id:
            layer.canopi_meta_community_id = new_id
            db.session.commit()
        return data
    except requests.RequestException as exc:
        log.warning('Canopi community sync request error layer=%s: %s', layer.id, exc)
        return None


def mirror_membership_to_canopi(
    *,
    layer_id: str,
    web3auth_verifier_id: str,
    active: bool = True,
) -> Optional[Dict[str, Any]]:
    """Mirror Gov Hub LayerMember → Canopi MetaCommunityMembership."""
    if not _api_key():
        return None
    vid = (web3auth_verifier_id or '').strip()
    if not vid:
        return None
    base = _api_base()
    try:
        resp = requests.post(
            f'{base}/v1/internal/gov-hub/communities/membership',
            json={
                'web3authVerifierId': vid,
                'layerId': layer_id,
                'active': active,
            },
            headers=_headers(),
            timeout=20,
        )
        if resp.status_code >= 400:
            log.warning(
                'Canopi membership mirror failed layer=%s status=%s',
                layer_id,
                resp.status_code,
            )
            return None
        return resp.json() if resp.text else {}
    except requests.RequestException as exc:
        log.warning('Canopi membership mirror error layer=%s: %s', layer_id, exc)
        return None
