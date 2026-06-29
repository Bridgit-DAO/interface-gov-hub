"""Badge wallet (Bitcoin address) ordinals for private profile dashboard."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests

_IMAGE_TYPES = frozenset({
    'image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp', 'image/svg+xml',
})
_HTML_TYPES = frozenset({'text/html', 'application/xhtml+xml'})


def fetch_badge_wallet_inscriptions(
    address: str,
    *,
    limit: int = 24,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Return inscription cards for display; error string if API unavailable."""
    address = (address or '').strip()
    if not address:
        return [], 'No badge wallet address'
    api_key = (os.environ.get('UNISAT_API_KEY') or '').strip()
    if not api_key:
        return [], 'Ordinals lookup is not configured on this server'

    base = (
        'https://open-api-testnet.unisat.io'
        if os.environ.get('UNISAT_TESTNET')
        else 'https://open-api.unisat.io'
    )
    out: List[Dict[str, Any]] = []
    cursor = 0
    size = min(60, max(limit, 1))
    try:
        while len(out) < limit:
            resp = requests.get(
                f'{base}/v1/indexer/address/{address}/inscription-data',
                params={'cursor': cursor, 'size': size},
                headers={'Authorization': f'Bearer {api_key}'},
                timeout=15,
            )
            if resp.status_code != 200:
                return out, 'Could not load badge wallet inscriptions'
            body = resp.json()
            if body.get('code') != 0:
                return out, body.get('msg') or 'Unisat API error'
            payload = body.get('data') or {}
            for item in payload.get('inscription') or []:
                iid = (item.get('inscriptionId') or item.get('inscription_id') or '').strip()
                if not iid:
                    continue
                ctype = (item.get('contentType') or item.get('content_type') or '').lower()
                display = 'other'
                if any(t in ctype for t in _IMAGE_TYPES):
                    display = 'image'
                elif any(t in ctype for t in _HTML_TYPES) or 'html' in ctype:
                    display = 'html'
                out.append({
                    'inscription_id': iid,
                    'inscription_number': item.get('inscriptionNumber'),
                    'content_type': ctype,
                    'display': display,
                    'content_url': f'https://ordinals.com/content/{iid}',
                    'preview_url': f'https://ordinals.com/preview/{iid}',
                })
                if len(out) >= limit:
                    break
            cursor = payload.get('cursor')
            if not cursor:
                break
    except requests.RequestException:
        return out, 'Network error loading badge wallet'
    return out, None
