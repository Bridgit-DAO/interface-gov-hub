"""Shared helper for building absolute site URLs (email links, redirects)."""
from __future__ import annotations


def public_base_url() -> str:
    from flask import current_app
    from config import PUBLIC_BASE_URL, resolved_public_base_url
    return resolved_public_base_url(current_app.config.get('PUBLIC_BASE_URL') or PUBLIC_BASE_URL)
