"""Markdown → sanitized HTML for submission status / ordinal previews."""
from __future__ import annotations

import re
from typing import Optional

_ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'ul', 'ol', 'li', 'a', 'img', 'code', 'pre', 'blockquote', 'table',
    'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'div', 'span',
]

_HEADING_RE = re.compile(r'^(?: {0,3})#{1,6}\s+')
_HR_RE = re.compile(r'^(?: {0,3})(?:-{3,}|_{3,}|\*{3,})\s*$')


def strip_hr_adjacent_to_headings(text: str) -> str:
    """Drop markdown horizontal rules immediately before/after headings (book viewer parity)."""
    if not text or not text.strip():
        return text
    lines = text.splitlines()
    drop = [False] * len(lines)

    def prev_non_empty(idx: int) -> int:
        for j in range(idx, -1, -1):
            if lines[j].strip():
                return j
        return -1

    def next_non_empty(idx: int) -> int:
        for j in range(idx, len(lines)):
            if lines[j].strip():
                return j
        return -1

    for i, line in enumerate(lines):
        if not _HR_RE.match(line):
            continue
        prev_i = prev_non_empty(i - 1)
        next_i = next_non_empty(i + 1)
        if (prev_i >= 0 and _HEADING_RE.match(lines[prev_i])) or (
            next_i >= 0 and _HEADING_RE.match(lines[next_i])
        ):
            drop[i] = True

    return "\n".join(line for line, d in zip(lines, drop) if not d)


_ALLOWED_ATTRS = {
    'a': ['href', 'title', 'target'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
}


def normalize_backslash_escaped_markdown(text: str) -> str:
    """
    Undo common erroneous backslash escapes in uploaded plain text (e.g. \\##, \\-, \\*\\*).
    Some exports (Notion, PDF pipelines, etc.) escape markdown; without this, headers render as literal ## in <p>.
    """
    if not text or '\\' not in text:
        return text
    escape_hits = len(re.findall(r'\\[#\-*]', text))
    if escape_hits < 3:
        return text
    out_lines = []
    for line in text.splitlines():
        ln = line
        ln = re.sub(r'^\\+(#{1,6})\s', r'\1 ', ln)
        ln = re.sub(r'^\\-(\s)', r'-\1', ln)
        ln = re.sub(r'^(\d+)\\\.(\s+)', r'\1.\2', ln)
        ln = ln.replace('\\*\\*', '**')
        ln = re.sub(r'\\\*([^*\\]+?)\\\*', r'*\1*', ln)
        out_lines.append(ln)
    return '\n'.join(out_lines)


def markdown_to_safe_preview_html(markdown_text: str) -> Optional[str]:
    """
    Convert markdown to sanitized HTML for embedding in the Content Preview card.
    Tries markdown2 first, then the `markdown` package (already in requirements for IETF tooling).
    Returns None if no converter is available or conversion fails.
    """
    if markdown_text is None:
        return None
    text = markdown_text if isinstance(markdown_text, str) else str(markdown_text)
    if not text.strip():
        return None
    text = normalize_backslash_escaped_markdown(text)
    text = strip_hr_adjacent_to_headings(text)

    html_raw: Optional[str] = None
    try:
        import markdown2

        html_raw = markdown2.markdown(
            text, extras=['fenced-code-blocks', 'tables', 'break-on-newline']
        )
    except Exception:
        try:
            import markdown as md_lib

            html_raw = md_lib.markdown(
                text,
                extensions=['extra', 'nl2br', 'sane_lists'],
            )
        except Exception:
            return None

    if not html_raw or not str(html_raw).strip():
        return None

    try:
        import bleach

        cleaned = bleach.clean(
            html_raw,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRS,
            strip=True,
        )
        return re.sub(
            r'src="(/content/[^"]+)"',
            r'src="https://ordinals.com\1"',
            cleaned,
        )
    except Exception:
        return None


def text_looks_like_markdown(text: str) -> bool:
    """Heuristic for text/plain ordinal bodies that are actually markdown."""
    if not text or not text.strip():
        return False
    patterns = [
        r'^#{1,6}\s+.+$',
        r'\*\*.+\*\*',
        r'^\s*[-*+]\s+',
        r'^\s*\d+\.\s+',
        r'\[.+\]\(.+\)',
        r'!\[.*\]\(.+\)',
        # Italic: single *word* – avoid matching ** (handled by bold elsewhere)
        r'(?<!\*)\*(?!\*)([^*]+)\*(?!\*)',
    ]
    for pattern in patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    return False
