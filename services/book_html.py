"""Prepare Metaweb book chapter HTML for Gov Hub draft reader embedding."""
from __future__ import annotations

import json
import re
from pathlib import Path

_OVERRIDES_REL = 'images/book/inscription-overrides.json'
_CONTENT_INSCRIPTION_RE = re.compile(
    r'''(src|href)=(["'])(/content/([a-f0-9]{64}i\d+))\2''',
    re.IGNORECASE,
)


def looks_like_html_document(text: str) -> bool:
    """True when file body is a full HTML document (Metaweb book chapters)."""
    s = (text or '').lstrip()[:16000].lower()
    return s.startswith('<!doctype html') or s.startswith('<html')


def _load_inscription_overrides(static_folder: Path | None) -> dict[str, str]:
    if not static_folder:
        return {}
    path = static_folder / _OVERRIDES_REL
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).lower(): str(v) for k, v in data.items()}


def _static_folder() -> Path | None:
    try:
        from flask import current_app

        folder = current_app.static_folder
        return Path(folder) if folder else None
    except RuntimeError:
        return None


def rewrite_ordinals_content_urls(html: str, overrides: dict[str, str] | None = None) -> str:
    """Resolve /content/<inscription> for Gov Hub (Hub static overrides, else ordinals.com)."""
    overrides = overrides or _load_inscription_overrides(_static_folder())

    def repl(match: re.Match[str]) -> str:
        attr = match.group(1)
        quote = match.group(2)
        path = match.group(3)
        iid = (match.group(4) or '').lower()
        if iid and iid in overrides:
            return f'{attr}={quote}{overrides[iid]}{quote}'
        return f'{attr}={quote}https://ordinals.com{path}{quote}'

    return _CONTENT_INSCRIPTION_RE.sub(repl, html)


def _scope_book_css(css: str) -> str:
    """Scope chapter CSS so it does not restyle the Gov Hub shell."""
    scoped = re.sub(r'\bbody\b', '.metaweb-book-chapter', css)
    scoped = re.sub(r'(?<![\w-])img\s*\{', '.metaweb-book-chapter img {', scoped)
    return scoped


def prepare_book_html_fragment(full_html: str) -> str:
    """
    Extract embedded styles + body for the draft reader.

    Full book chapters are HTML documents with <head><style> and <body>. Gov Hub
    embeds a fragment inside .draft-reader-body; styles are scoped to
    .metaweb-book-chapter so body/img rules do not affect site chrome.
    """
    text = full_html or ''
    styles = re.findall(r'<style[^>]*>(.*?)</style>', text, flags=re.IGNORECASE | re.DOTALL)
    body_match = re.search(r'<body[^>]*>(.*)</body>', text, flags=re.IGNORECASE | re.DOTALL)
    body_inner = body_match.group(1).strip() if body_match else text.strip()

    parts: list[str] = []
    if styles:
        combined = _scope_book_css('\n'.join(s.strip() for s in styles if s.strip()))
        parts.append(f'<style type="text/css">\n{combined}\n</style>')
    parts.append(f'<div class="metaweb-book-chapter">{body_inner}</div>')
    fragment = '\n'.join(parts)
    return rewrite_ordinals_content_urls(fragment)


def load_book_html_for_reader(raw_text: str) -> str:
    """Return reader-ready HTML for a book chapter file or fragment."""
    if not raw_text or not raw_text.strip():
        return ''
    if looks_like_html_document(raw_text):
        return prepare_book_html_fragment(raw_text)
    return rewrite_ordinals_content_urls(raw_text)
