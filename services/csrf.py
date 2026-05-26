"""CSRF token helpers (shared by middleware and page rendering)."""
from __future__ import annotations

import secrets

from flask import session


def get_or_create_csrf_token() -> str:
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


def csrf_token_valid(supplied: str | None, expected: str | None = None) -> bool:
    if expected is None:
        expected = session.get('_csrf_token')
    if not expected or not supplied:
        return False
    return secrets.compare_digest(expected, supplied)
