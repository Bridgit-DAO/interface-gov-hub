"""Campaign vanity-domain auth: hub-canonical Web3Auth login and session handoff."""
from __future__ import annotations

import os
import re
from typing import Optional
from urllib.parse import quote, urlparse

from flask import redirect, request

from config import IS_DEVELOPMENT
from services.auth_redirect import login_url, safe_return_path
from services.campaign_pages import CampaignConfig, campaign_for_host, campaign_href, get_campaign

_HUB_HOSTS = frozenset(
    h.lower()
    for h in (
        'interfacehub.net',
        'www.interfacehub.net',
        'dev.interfacehub.net',
        'staging.interfacehub.net',
        'hub.themetalayer.org',
        'dev.hub.themetalayer.org',
        'staging.hub.themetalayer.org',
        'dev.govhub.live',
        'govhub.live',
        'rfc.themetalayer.org',
        'localhost',
        '127.0.0.1',
    )
)


def gov_hub_public_url() -> str:
    """Canonical Gov Hub origin for Web3Auth (whitelisted in dashboard)."""
    override = (os.environ.get('GOV_HUB_PUBLIC_URL') or '').strip().rstrip('/')
    if override:
        return override
    if IS_DEVELOPMENT:
        return 'https://dev.interfacehub.net'
    return 'https://interfacehub.net'


def _request_host() -> str:
    host = (
        request.headers.get('X-Forwarded-Host')
        or request.host
        or ''
    ).split(',')[0].strip().split(':')[0].lower()
    return host


def is_hub_host(host: str) -> bool:
    host_l = (host or '').lower().split(':')[0]
    if host_l in _HUB_HOSTS:
        return True
    if host_l.endswith('.interfacehub.net'):
        return True
    if host_l.endswith('.hub.themetalayer.org'):
        return True
    if host_l.endswith('.govhub.live'):
        return True
    return False


def campaign_for_vanity_host(host: Optional[str] = None) -> Optional[CampaignConfig]:
    host_l = (host or _request_host()).lower()
    if is_hub_host(host_l):
        return None
    return campaign_for_host(host_l)


def _campaign_prefix(slug: str) -> str:
    return f'/campaign/{slug}'


def vanity_path_for_campaign(slug: str, path: str) -> str:
    """Map /campaign/<slug>/docs/foo/ → /docs/foo/ for vanity host URLs."""
    prefix = _campaign_prefix(slug).rstrip('/')
    raw = (path or '/').strip()
    if not raw.startswith('/'):
        raw = '/' + raw
    if raw.startswith(prefix + '/'):
        return raw[len(prefix):] or '/'
    if raw == prefix or raw == prefix + '/':
        return '/'
    return raw


def vanity_absolute_url(cfg: CampaignConfig, path: str, host: Optional[str] = None) -> str:
    host_l = (host or _request_host()).lower()
    vanity_path = vanity_path_for_campaign(cfg.slug, path)
    if not vanity_path.startswith('/'):
        vanity_path = '/' + vanity_path
    scheme = 'https'
    return f'{scheme}://{host_l}{vanity_path}'


def _registered_campaign_hosts() -> frozenset[str]:
    from services.campaign_pages import _load_all_campaigns

    hosts: set[str] = set()
    for cfg in _load_all_campaigns().values():
        hosts.update(cfg.hosts())
    return frozenset(h.lower() for h in hosts if h)


def is_registered_campaign_host(host: str) -> bool:
    host_l = (host or '').lower().split(':')[0]
    return host_l in _registered_campaign_hosts()


def safe_campaign_return_url(raw: str | None) -> str | None:
    """
    Allow https return URLs on registered campaign vanity hosts, or same-site paths.
    """
    rel = safe_return_path(raw)
    if rel:
        return rel
    if not raw:
        return None
    candidate = raw.strip()
    if not candidate.startswith('https://'):
        return None
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    host = (parsed.hostname or '').lower()
    if not host or not is_registered_campaign_host(host):
        return None
    path = parsed.path or '/'
    if parsed.query:
        path = f'{path}?{parsed.query}'
    return f'https://{host}{path}'


def hub_login_url(return_to: str | None = None) -> str:
    base = gov_hub_public_url()
    target = safe_campaign_return_url(return_to) or safe_return_path(return_to)
    if target:
        return f'{base}/login/?next={quote(target, safe="")}'
    return f'{base}/login/'


def campaign_login_url(
    cfg: CampaignConfig,
    path: str = '/',
    *,
    host: Optional[str] = None,
) -> str:
    """
    Sign-in URL for campaign pages.

    On a vanity host, sends users to hub Web3Auth with an absolute return URL.
    On hub or path-only hosts, uses relative /login/?next=.
    """
    campaign_path = campaign_href(cfg.slug, path)
    vanity_cfg = campaign_for_vanity_host(host)
    if vanity_cfg and vanity_cfg.slug == cfg.slug:
        return hub_login_url(vanity_absolute_url(cfg, campaign_path, host=host))
    rel = safe_return_path(campaign_path)
    return login_url(rel)


def redirect_vanity_login_to_hub(return_to_raw: str | None = None):
    """If Web3Auth would run on an unwhitelisted vanity host, redirect to hub login."""
    cfg = campaign_for_vanity_host()
    if not cfg:
        return None
    if return_to_raw and return_to_raw.startswith('https://'):
        next_url = safe_campaign_return_url(return_to_raw)
    else:
        rel = safe_return_path(return_to_raw) or request.full_path.rstrip('?') or request.path
        next_url = vanity_absolute_url(cfg, rel)
    return redirect(hub_login_url(next_url))


def campaign_handoff_allowed_hosts_json() -> str:
    """JSON array of allowed external return hosts for post-login JS."""
    import json

    return json.dumps(sorted(_registered_campaign_hosts()))


def _handoff_secret() -> str:
    secret = (
        os.environ.get('CAMPAIGN_HANDOFF_SECRET')
        or os.environ.get('SECRET_KEY')
        or 'govhub-dev-campaign-handoff-insecure'
    ).strip()
    return secret


def make_campaign_handoff_token(username: str, *, max_age_seconds: int = 120) -> str:
    import base64
    import hashlib
    import hmac
    import json
    import time

    payload = {
        'user': username,
        'exp': int(time.time()) + max_age_seconds,
    }
    raw = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
    encoded = base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')
    sig = hmac.new(
        _handoff_secret().encode('utf-8'),
        encoded.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return f'{encoded}.{sig}'


def verify_campaign_handoff_token(token: str) -> Optional[str]:
    import base64
    import hashlib
    import hmac
    import json
    import time

    if not token or '.' not in token:
        return None
    encoded, sig = token.rsplit('.', 1)
    expected = hmac.new(
        _handoff_secret().encode('utf-8'),
        encoded.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        pad = '=' * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + pad).decode('utf-8'))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get('exp') or 0) < int(time.time()):
        return None
    user = (payload.get('user') or '').strip()
    return user or None


def build_campaign_handoff_redirect(return_url: str, username: str) -> str:
    parsed = urlparse(return_url)
    host = (parsed.hostname or '').lower()
    if not is_registered_campaign_host(host):
        raise ValueError('return URL host is not a registered campaign domain')
    vanity_path = parsed.path or '/'
    if parsed.query:
        vanity_path = f'{vanity_path}?{parsed.query}'
    token = make_campaign_handoff_token(username)
    q = quote(vanity_path, safe='/?=&')
    t = quote(token, safe='')
    return f'https://{host}/auth/campaign-handoff/?token={t}&next={q}'
