"""API authentication: Flask session or Bearer Web3Auth idToken."""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, Optional

from flask import jsonify, request

from models import User
from services.identity import get_current_user
from services.web3auth_verify import normalize_user_email


def _user_dict_from_model(user: User) -> Dict[str, Any]:
    user_name = user.name or user.displayName or user.oauthName or user.username
    return {
        'id': user.id,
        'username': user.username,
        'name': user_name,
        'email': user.email,
        'role': user.role,
        'theme': user.theme,
        'displayName': user.displayName,
        'oauthName': user.oauthName,
        'profileImage': user.profileImage,
        'typeOfLogin': user.typeOfLogin,
        'evmAddress': user.evmAddress,
        'solanaAddress': user.solanaAddress,
        'bitcoinAddress': getattr(user, 'bitcoinAddress', None),
    }


def _dp_proxy_admin_user() -> Optional[Dict[str, Any]]:
    """DP challenge-site server proxy: Hermes secret + X-DP-Admin-Email header."""
    from config import DP_ADMIN_EMAILS
    from services.support_auth import hermes_authorized

    if not hermes_authorized():
        return None

    admin_email = normalize_user_email(request.headers.get('X-DP-Admin-Email'))
    if not admin_email or admin_email not in DP_ADMIN_EMAILS:
        return None

    user = User.query.filter_by(email=admin_email).first()
    if user:
        return _user_dict_from_model(user)

    local_part = admin_email.split('@', 1)[0]
    return {
        'id': f'dp-proxy:{admin_email}',
        'username': local_part,
        'name': local_part,
        'email': admin_email,
        'role': 'user',
        'theme': None,
        'displayName': local_part,
        'oauthName': None,
        'profileImage': None,
        'typeOfLogin': 'dp_proxy',
        'evmAddress': None,
        'solanaAddress': None,
        'bitcoinAddress': None,
    }


def get_api_user() -> Optional[Dict[str, Any]]:
    """Resolve current user from session cookie or Authorization: Bearer idToken."""
    session_user = get_current_user()
    if session_user:
        return session_user

    proxy_user = _dp_proxy_admin_user()
    if proxy_user:
        return proxy_user

    auth = (request.headers.get('Authorization') or '').strip()
    if not auth.lower().startswith('bearer '):
        return None

    id_token = auth[7:].strip()
    if not id_token:
        return None

    try:
        from jwt.exceptions import InvalidTokenError, PyJWKClientError
        from services.web3auth_verify import identity_from_web3auth_claims, verify_web3auth_id_token

        claims = verify_web3auth_id_token(id_token)
        identity = identity_from_web3auth_claims(claims)
        user = User.query.filter_by(web3authVerifierId=identity['verifierId']).first()
        if not user:
            return None
        return _user_dict_from_model(user)
    except (InvalidTokenError, PyJWKClientError, ValueError):
        return None


def require_api_auth(view: Callable):
    """JSON-friendly auth decorator (401 instead of login redirect)."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not get_api_user():
            return jsonify({
                'error': 'Authentication required',
                'code': 'authentication_required',
            }), 401
        return view(*args, **kwargs)

    return wrapped
