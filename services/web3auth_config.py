"""Web3Auth client settings shared by server verification and browser init."""
from __future__ import annotations

import os
from typing import Dict

from config import IS_DEVELOPMENT

DEFAULT_DEVNET_CLIENT_ID = (
    'BKvRj4akAwrNHHk4UyYCC4zt9KWigdiuosCX5-idVNclsk9hPPQ4_b8grcl0JF4NhT26oLWb3O5K949SVv6lTGk'
)

_DEVNET = {
    'network': 'sapphire_devnet',
    'google_verifier': 'web3auth-google-sapphire-devnet',
}

_MAINNET = {
    'network': 'sapphire_mainnet',
    'google_verifier': 'web3auth-google-sapphire',
}


def get_web3auth_settings() -> Dict[str, str]:
    """
    Return clientId, network, and google verifier for the active environment.

    Development uses sapphire_devnet. Production uses WEB3AUTH_CLIENT_ID on
    sapphire_mainnet. Set WEB3AUTH_USE_DEVNET=true only as a temporary override
    (e.g. before govhub.live is on the mainnet Web3Auth allowlist).
    """
    devnet_id = (
        os.environ.get('WEB3AUTH_CLIENT_ID_DEVNET') or DEFAULT_DEVNET_CLIENT_ID
    ).strip()
    mainnet_id = (os.environ.get('WEB3AUTH_CLIENT_ID') or '').strip()
    use_devnet_override = os.environ.get('WEB3AUTH_USE_DEVNET', '').strip().lower() in (
        '1',
        'true',
        'yes',
        'on',
    )

    if IS_DEVELOPMENT or use_devnet_override:
        return {'client_id': devnet_id, **_DEVNET}

    if not mainnet_id:
        raise ValueError('WEB3AUTH_CLIENT_ID must be set in production')

    return {'client_id': mainnet_id, **_MAINNET}


def web3auth_client_id() -> str:
    return get_web3auth_settings()['client_id']
