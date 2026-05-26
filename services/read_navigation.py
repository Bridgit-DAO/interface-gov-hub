"""Draft read-page URLs and safe back targets."""
from __future__ import annotations

from urllib.parse import quote, urlencode

from services.auth_redirect import safe_return_path


def read_page_url(draft_ref: str, return_to: str | None = None) -> str:
    """Build /doc/draft/<ref>/read/ with optional ?return_to= for the toolbar Back link."""
    ref = (draft_ref or '').strip()
    path = f'/doc/draft/{quote(ref, safe="")}/read/'
    back = safe_return_path(return_to)
    if back:
        return path + '?' + urlencode({'return_to': back})
    return path


def draft_reader_back_href(return_to_arg: str | None) -> str:
    """Resolve Back href for draft_reader from ?return_to= (default: all docs)."""
    return safe_return_path(return_to_arg) or '/doc/all/'
