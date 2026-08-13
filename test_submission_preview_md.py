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


def test_strip_hr_adjacent_to_headings():
    raw = "---\n## Section One\n\nBody\n\n## Section Two\n---\n"
    html = markdown_to_safe_preview_html(raw) or ""
    assert "<hr" not in html.lower()
    assert "<h2>Section One</h2>" in html
    assert "<h2>Section Two</h2>" in html


def test_dp_illustration_rewrites_to_govhub_static():
    raw = (
        '# DP18 – Feedback\n\n'
        '![Illustration for Desirable Property DP18: Feedback](/content/local/assets/dp/DP18.webp)\n\n'
        '## 1. Purpose\n'
    )
    html = markdown_to_safe_preview_html(raw) or ''
    assert '/static/images/dps/full/DP18.webp' in html
    assert 'ordinals.com/content/local' not in html
