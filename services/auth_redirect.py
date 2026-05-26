"""Safe post-login return URLs (shared by auth routes and decorators)."""
from __future__ import annotations

from urllib.parse import quote


def safe_return_path(raw: str | None) -> str | None:
    """Allow same-site relative paths only."""
    if not raw:
        return None
    path = raw.strip()
    if not path.startswith('/') or path.startswith('//'):
        return None
    return path


def login_url(return_to: str | None = None) -> str:
    """Build /login/ URL with optional return path (?next=)."""
    target = safe_return_path(return_to)
    if target:
        return f'/login/?next={quote(target, safe="")}'
    return '/login/'
