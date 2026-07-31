"""Word-level inline diff rendering.

Server-side twin of ``buildDiffHtml`` in ``static/js/dp-proposals/proposal-display.js``.
Both emit the same ``dp-diff-del`` / ``dp-diff-ins`` markup so a diff looks identical
whether it is rendered in the reader's patch modal or on the patches list page.
"""
from __future__ import annotations

import html as html_mod
import re
from difflib import SequenceMatcher
from typing import List

_TOKEN_RE = re.compile(r'\S+|\s+')

# Guard against pathological inputs; passage-anchored patches are short.
_MAX_TOKENS = 4000


def tokenize_words(text: str) -> List[str]:
    """Split into words and the whitespace runs between them, preserving both."""
    return _TOKEN_RE.findall(text or '')


def build_diff_html(original: str, proposed: str) -> str:
    """Render ``original`` -> ``proposed`` as inline HTML with deletions and insertions marked."""
    a = tokenize_words(original)
    b = tokenize_words(proposed)

    if len(a) > _MAX_TOKENS or len(b) > _MAX_TOKENS:
        return html_mod.escape(proposed or '')

    parts: List[str] = []
    matcher = SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            parts.append(html_mod.escape(''.join(a[i1:i2])))
            continue
        if tag in ('delete', 'replace'):
            parts.append(
                f'<del class="dp-diff-del">{html_mod.escape("".join(a[i1:i2]))}</del>'
            )
        if tag in ('insert', 'replace'):
            parts.append(
                f'<mark class="dp-diff-ins">{html_mod.escape("".join(b[j1:j2]))}</mark>'
            )

    return ''.join(parts)


def change_counts(original: str, proposed: str) -> tuple[int, int]:
    """Return ``(added_chars, removed_chars)`` between the two texts."""
    a = tokenize_words(original)
    b = tokenize_words(proposed)
    added = removed = 0
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ('delete', 'replace'):
            removed += len(''.join(a[i1:i2]).strip())
        if tag in ('insert', 'replace'):
            added += len(''.join(b[j1:j2]).strip())
    return added, removed
