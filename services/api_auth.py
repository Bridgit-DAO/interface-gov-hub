"""API authentication: Flask session or Bearer Web3Auth idToken."""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, Optional

from flask import jsonify, request

from models import User
from services.identity import get_current_user


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


def get_api_user() -> Optional[Dict[str, Any]]:
    """Resolve current user from session cookie or Authorization: Bearer idToken."""
    session_user = get_current_user()
    if session_user:
        return session_user

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
            return jsonify({'error': 'Authentication required'}), 401
        return view(*args, **kwargs)

    return wrapped
