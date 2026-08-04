"""Hermes and admin auth for support API routes."""
from __future__ import annotations

import os
from functools import wraps
from typing import Callable

from flask import jsonify, request

from services.api_auth import get_api_user
from services.identity import get_current_user


def hermes_api_secret() -> str:
    return (
        os.environ.get('GOVHUB_HERMES_API_KEY', '').strip()
        or os.environ.get('GOVHUB_SUPPORT_OPS_SECRET', '').strip()
        or os.environ.get('METAWEB_OPS_SECRET', '').strip()
        or os.environ.get('METAWEB_GOVHUB_INTERNAL_SECRET', '').strip()
    )


def hermes_authorized() -> bool:
    secret = hermes_api_secret()
    if not secret:
        return False
    auth = (request.headers.get('Authorization') or '').strip()
    bearer = auth[7:].strip() if auth.lower().startswith('bearer ') else ''
    alt = (
        request.headers.get('X-GovHub-Hermes-Key')
        or request.headers.get('X-DP-Hermes-Key')
        or request.headers.get('X-Metaweb-Hermes-Key')
        or ''
    ).strip()
    return bearer == secret or alt == secret


def require_support_admin(view: Callable):
    """Admin session (admin/editor) or Hermes API key."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if hermes_authorized():
            return view(*args, **kwargs)
        user = get_current_user() or get_api_user()
        if not user:
            return jsonify({'ok': False, 'error': 'unauthorized'}), 401
        role = user.get('role') or 'user'
        if role not in ('admin', 'editor'):
            return jsonify({'ok': False, 'error': 'forbidden'}), 403
        return view(*args, **kwargs)

    return wrapped


def require_hermes(view: Callable):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not hermes_authorized():
            return jsonify({'ok': False, 'error': 'unauthorized'}), 401
        return view(*args, **kwargs)

    return wrapped
