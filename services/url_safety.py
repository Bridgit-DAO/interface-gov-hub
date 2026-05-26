"""Validate outbound fetch URLs (SSRF mitigation for ordinals / user-supplied links)."""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

ORDINALS_CONTENT_HOSTS = frozenset({'ordinals.com', 'www.ordinals.com'})
ORDINALS_INSCRIPTION_ID_RE = re.compile(r'^[a-fA-F0-9]{64}(i\d+)?$')


def _host_resolves_to_blocked_ip(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError:
        return True
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return True
    return False


def validate_ordinals_fetch_url(url: str) -> str:
    """
    Allow only ordinals.com /content/… URLs over http(s).
    Raises ValueError when the URL is not safe to fetch server-side.
    """
    raw = (url or '').strip()
    if not raw:
        raise ValueError('URL is required')

    parsed = urlparse(raw)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError('URL must use http or https')
    if parsed.username or parsed.password:
        raise ValueError('URL must not contain credentials')

    host = (parsed.hostname or '').lower()
    if not host or host not in ORDINALS_CONTENT_HOSTS:
        raise ValueError('Only ordinals.com content URLs are allowed')
    if _host_resolves_to_blocked_ip(host):
        raise ValueError('URL host is not allowed')

    path = parsed.path or ''
    if not path.startswith('/content/'):
        raise ValueError('URL must be an ordinals.com content path')

    return raw


def ordinals_content_url_from_id(inscription_id: str) -> str:
    """Build a validated ordinals.com content URL from an inscription id."""
    iid = (inscription_id or '').strip()
    if not ORDINALS_INSCRIPTION_ID_RE.match(iid):
        raise ValueError('Invalid inscription id format')
    return validate_ordinals_fetch_url(f'https://ordinals.com/content/{iid}')
