"""Desirable Properties public URLs for cross-site invitation links."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models import PlatformInvitation

DP_CHALLENGE_SITE_BASE = os.environ.get(
    'DP_CHALLENGE_SITE_BASE', 'https://desirableproperties.org'
).rstrip('/')


def dp_challenge_site_base() -> str:
    return DP_CHALLENGE_SITE_BASE


def workgroup_collab_path(slug: str, *, invite_token: str | None = None) -> str:
    """Canonical DP workgroup collab path (no trailing slash)."""
    path = f'/workgroups/{(slug or "").strip()}'
    if invite_token:
        return f'{path}?invite={invite_token}'
    return path


def workgroup_invite_landing_path(inv: 'PlatformInvitation') -> str:
    """Relative landing path on desirableproperties.org for a workgroup invite."""
    from services.platform_invitations import _load_target

    target = _load_target(inv)
    slug = (target.get('workgroup_slug') or '').strip()
    if not slug:
        return f'/workgroups?invite={inv.token}'
    return workgroup_collab_path(slug, invite_token=inv.token)


def workgroup_invite_landing_url(inv: 'PlatformInvitation') -> str:
    return dp_challenge_site_base() + workgroup_invite_landing_path(inv)


def workgroup_post_accept_path(slug: str) -> str:
    """Post-accept redirect on DP (and relative paths work site-wide)."""
    slug = (slug or '').strip()
    return f'/workgroups/{slug}' if slug else '/workgroups'
