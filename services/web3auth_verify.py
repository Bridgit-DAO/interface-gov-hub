"""Verify Web3Auth identity tokens server-side (JWKS / ES256)."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Optional

import jwt
from jwt import PyJWKClient

from services.web3auth_config import web3auth_client_id

WEB3AUTH_JWKS_URL = 'https://api-auth.web3auth.io/jwks'
WEB3AUTH_ISSUER = 'https://api-auth.web3auth.io'
WEB3AUTH_ALGORITHMS = ['ES256']


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(WEB3AUTH_JWKS_URL, cache_keys=True, lifespan=600)


def verify_web3auth_id_token(id_token: str) -> Dict[str, Any]:
    """Validate signature, issuer, audience, and expiry. Returns JWT claims."""
    if not id_token or not str(id_token).strip():
        raise ValueError('idToken required')

    client_id = web3auth_client_id()
    if not client_id:
        raise ValueError('WEB3AUTH_CLIENT_ID not configured')

    signing_key = _jwks_client().get_signing_key_from_jwt(id_token)
    return jwt.decode(
        id_token,
        signing_key.key,
        algorithms=WEB3AUTH_ALGORITHMS,
        audience=client_id,
        issuer=WEB3AUTH_ISSUER,
    )


def _login_type_from_claims(claims: Dict[str, Any]) -> str:
    grouped = (claims.get('groupedAuthConnectionId') or '').lower()
    if 'google' in grouped:
        return 'google'
    if 'twitter' in grouped:
        return 'twitter'
    if 'email' in grouped:
        return 'email_passwordless'
    if 'wallet' in grouped:
        return 'wallet'
    auth_connection = (claims.get('authConnection') or '').strip()
    return auth_connection or 'unknown'


def identity_from_web3auth_claims(claims: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Map verified JWT claims to Gov Hub user fields.
    Identity MUST come from verified claims only (never trust client JSON).
    """
    verifier_id = (claims.get('userId') or claims.get('sub') or '').strip()
    if not verifier_id:
        raise ValueError('Token missing userId')

    email = (claims.get('email') or '').strip() or None
    name = (claims.get('name') or '').strip() or None
    profile_image = (claims.get('profileImage') or '').strip() or None

    return {
        'verifierId': verifier_id,
        'typeOfLogin': _login_type_from_claims(claims),
        'email': email,
        'name': name,
        'profileImage': profile_image,
    }
