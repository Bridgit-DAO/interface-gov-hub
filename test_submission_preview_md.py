"""Markdown preview helpers."""
from services.submission_preview_md import (
    markdown_to_safe_preview_html,
    normalize_backslash_escaped_markdown,
)


def test_normalize_backslash_escaped_headers():
    raw = r"\## Section\n\n\- \*\*bold\*\* item\n"
    norm = normalize_backslash_escaped_markdown(raw)
    assert norm.startswith('## Section')
    html = markdown_to_safe_preview_html(raw) or ''
    assert '<h2>Section</h2>' in html
    assert '<p>##' not in html
