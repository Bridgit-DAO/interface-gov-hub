"""Fetch public Canopi profile data (avatar, handle) for Gov Hub users."""
from __future__ import annotations

from typing import Optional

import requests

from config import CANOPI_API_URL


def fetch_canopi_avatar_by_id(canopi_user_id: Optional[str]) -> Optional[str]:
    cid = (canopi_user_id or '').strip()
    if not cid:
        return None
    try:
        resp = requests.get(
            f'{CANOPI_API_URL}/v1/users/{cid}',
            headers={'Accept': 'application/json'},
            timeout=8,
        )
        if not resp.ok:
            return None
        data = resp.json() if resp.content else {}
        url = (data.get('avatarUrl') or data.get('avatar_url') or '').strip()
        return url or None
    except Exception:
        return None


def fetch_canopi_avatar_by_handle(handle: Optional[str]) -> Optional[str]:
    h = (handle or '').strip().lstrip('@')
    if not h or '@' in h or len(h) < 2:
        return None
    try:
        resp = requests.get(
            f'{CANOPI_API_URL}/v1/users/by-handle/{requests.utils.quote(h)}',
            headers={'Accept': 'application/json'},
            timeout=8,
        )
        if not resp.ok:
            return None
        data = resp.json() if resp.content else {}
        url = (data.get('avatarUrl') or data.get('avatar_url') or '').strip()
        return url or None
    except Exception:
        return None


def resolve_canopi_avatar(
    *,
    canopi_user_id: Optional[str] = None,
    handle: Optional[str] = None,
    username: Optional[str] = None,
) -> Optional[str]:
    """Best-effort real avatar URL from Canopi (id first, then handle/username)."""
    url = fetch_canopi_avatar_by_id(canopi_user_id)
    if url:
        return url
    for candidate in (handle, username):
        url = fetch_canopi_avatar_by_handle(candidate)
        if url:
            return url
    return None


def sync_user_avatar_from_canopi(user, *, commit: bool = False) -> bool:
    """
    Store Canopi avatar on User.profileImage when missing.
    Skips users who already uploaded a Gov Hub profile image.
    """
    from extensions import db
    from services.avatar import is_user_uploaded_profile_image

    if is_user_uploaded_profile_image(getattr(user, 'profileImage', None)):
        return False
    if (getattr(user, 'profileImage', None) or '').strip():
        return False

    url = resolve_canopi_avatar(
        handle=getattr(user, 'handle', None),
        username=getattr(user, 'username', None),
    )
    if not url:
        return False

    user.profileImage = url
    if commit:
        db.session.commit()
    return True
