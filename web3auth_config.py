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

    Gov Hub uses sapphire_devnet everywhere (dev and prod) unless
    WEB3AUTH_USE_MAINNET=true and WEB3AUTH_CLIENT_ID are set for a paid plan.
    """
    devnet_id = (
        os.environ.get('WEB3AUTH_CLIENT_ID_DEVNET') or DEFAULT_DEVNET_CLIENT_ID
    ).strip()
    mainnet_id = (os.environ.get('WEB3AUTH_CLIENT_ID') or '').strip()
    use_mainnet = os.environ.get('WEB3AUTH_USE_MAINNET', '').strip().lower() in (
        '1',
        'true',
        'yes',
        'on',
    )

    if use_mainnet and mainnet_id and not IS_DEVELOPMENT:
        return {'client_id': mainnet_id, **_MAINNET}

    return {'client_id': devnet_id, **_DEVNET}


def web3auth_client_id() -> str:
    return get_web3auth_settings()['client_id']
