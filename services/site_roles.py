"""Human-readable site role labels (never show end users as "user")."""
from __future__ import annotations

from typing import Optional


def site_role_label(role: Optional[str]) -> str:
    """Map stored role to display label; default and legacy ``user`` → participant."""
    raw = (role or 'user').strip().lower()
    if raw == 'user':
        return 'participant'
    return raw


def site_role_badge_class(role: Optional[str]) -> str:
    """Bootstrap badge background token for a site role."""
    raw = (role or 'user').strip().lower()
    if raw == 'admin':
        return 'danger'
    if raw == 'editor':
        return 'warning'
    return 'secondary'
