"""Prepare Metaweb book chapter HTML for Gov Hub draft reader embedding."""
from __future__ import annotations

import re


def looks_like_html_document(text: str) -> bool:
    """True when file body is a full HTML document (Metaweb book chapters)."""
    s = (text or '').lstrip()[:16000].lower()
    return s.startswith('<!doctype html') or s.startswith('<html')


def rewrite_ordinals_content_urls(html: str) -> str:
    """Resolve /content/<inscription> paths for Gov Hub (off ordinals.com origin)."""

    def repl(match: re.Match[str]) -> str:
        attr = match.group(1)
        quote = match.group(2)
        path = match.group(3)
        return f'{attr}={quote}https://ordinals.com{path}{quote}'

    pattern = re.compile(
        r'''(src|href)=(["'])(/content/[a-f0-9]{64}i\d+)\2''',
        re.IGNORECASE,
    )
    return pattern.sub(repl, html)


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
