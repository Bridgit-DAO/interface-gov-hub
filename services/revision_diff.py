"""Block-level diff between two revisions of a document.

The reader diff in ``services/text_diff.py`` compares one short passage, so it
marks every changed word. A whole chapter is too long for that: diffing word by
word across ~10k words buries the handful of real edits. This module first lines
the two bodies up paragraph by paragraph, then falls back to the word-level diff
inside paragraphs that were rewritten rather than added or dropped wholesale.
"""
from __future__ import annotations

import html as html_mod
import os
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence

from services.text_diff import build_diff_html, change_counts

#: Paragraphs per body. Chapters run to a few hundred; past this the quadratic
#: matcher cost stops being worth the result and we report the diff as too large.
MAX_BLOCKS = 3000

#: Unchanged paragraphs kept either side of a change, so a hunk reads in context.
CONTEXT_BLOCKS = 1

#: Below this word-level similarity two paragraphs are treated as unrelated (one
#: dropped, one added) rather than as a rewrite worth showing word by word.
#: Short paragraphs share enough function words to score ~0.4 by accident, so
#: the bar sits above that.
REWRITE_SIMILARITY = 0.55

#: Candidate pairs considered when matching paragraphs inside one replaced
#: region. Past this the pairwise scan costs more than the better pairing is
#: worth, and matching falls back to comparing paragraphs position by position.
MAX_PAIRING_CANDIDATES = 2500

_BLOCK_SPLIT_RE = re.compile(r'\n\s*\n')
_TEXT_EXTENSIONS = ('.txt', '.xml', '.md', '.markdown')

#: Markdown rules (``---``, ``***``). They carry no prose, and a revision that
#: restyles a chapter adds dozens of them, which would swamp the real edits.
_SEPARATOR_RE = re.compile(r'^[-*_=\s]+$')


def revision_body_text(submission) -> str:
    """
    Plain text of one revision, with paragraph breaks intact.

    Prefers the stored upload because it keeps the newlines the diff aligns on.
    Ordinal-backed rows have no file, so they fall back to the rendered body
    flattened to text; that still diffs, just as one long paragraph.
    """
    if not submission:
        return ''
    path = getattr(submission, 'file_path', '') or ''
    filename = getattr(submission, 'filename', '') or ''
    if path and os.path.exists(path):
        _, ext = os.path.splitext(filename.lower())
        if ext in _TEXT_EXTENSIONS or ext in ('.docx', '.pdf'):
            from services.documents import extract_text_from_file

            text = extract_text_from_file(path, filename)
            if text:
                return text.replace('\r\n', '\n')

    from services.dp_proposals import load_submission_plain_document_text

    return load_submission_plain_document_text(submission)


def split_blocks(text: str) -> List[str]:
    """Split a body into comparable paragraphs, dropping blank runs and rules."""
    if not text:
        return []
    blocks = (b.strip() for b in _BLOCK_SPLIT_RE.split(text.replace('\r\n', '\n')))
    return [b for b in blocks if b and not _SEPARATOR_RE.match(b)]


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(a=a.split(), b=b.split(), autojunk=False).ratio()


def _pair_rewrites(old: Sequence[str], new: Sequence[str]) -> Dict[int, int]:
    """
    Map old-paragraph index to the new paragraph that rewrites it.

    Pairs are taken best-score first, so a paragraph that moved a few positions
    still matches its rewrite instead of latching onto whatever sits opposite
    it. Pairings that would cross an already-accepted pair are skipped, keeping
    the diff in reading order.
    """
    if len(old) * len(new) > MAX_PAIRING_CANDIDATES:
        return {
            i: i for i in range(min(len(old), len(new)))
            if _similarity(old[i], new[i]) >= REWRITE_SIMILARITY
        }

    scored = sorted(
        (
            (_similarity(o, n), i, j)
            for i, o in enumerate(old)
            for j, n in enumerate(new)
        ),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    pairs: Dict[int, int] = {}
    for score, i, j in scored:
        if score < REWRITE_SIMILARITY:
            break
        if i in pairs or j in pairs.values():
            continue
        if any((i - pi) * (j - pj) < 0 for pi, pj in pairs.items()):
            continue
        pairs[i] = j
    return pairs


def _changed_rows(old: Sequence[str], new: Sequence[str]) -> List[Dict[str, Any]]:
    """
    Turn one replaced region into rows in reading order.

    Paragraphs that still resemble each other pair up into a word-level rewrite;
    everything left over is a plain removal or addition.
    """
    pairs = _pair_rewrites(old, new)
    partner = {j: i for i, j in pairs.items()}
    rows: List[Dict[str, Any]] = []
    i = j = 0
    while i < len(old) or j < len(new):
        if i < len(old) and i in pairs:
            target = pairs[i]
            while j < target:
                if j not in partner:
                    rows.append({'kind': 'added', 'old': '', 'new': new[j]})
                j += 1
            rows.append({'kind': 'rewritten', 'old': old[i], 'new': new[target]})
            i += 1
            j = target + 1
            continue
        if i < len(old):
            rows.append({'kind': 'removed', 'old': old[i], 'new': ''})
            i += 1
            continue
        if j not in partner:
            rows.append({'kind': 'added', 'old': '', 'new': new[j]})
        j += 1
    return rows


def diff_revisions(old_text: str, new_text: str) -> Dict[str, Any]:
    """
    Compare two bodies paragraph by paragraph.

    Returns ``{'available', 'reason', 'rows', 'stats'}``. ``rows`` interleaves
    ``unchanged`` markers (a count of skipped paragraphs) with ``added``,
    ``removed``, ``rewritten`` and ``context`` rows, in document order.
    """
    old_blocks = split_blocks(old_text)
    new_blocks = split_blocks(new_text)

    if not old_blocks and not new_blocks:
        return {
            'available': False,
            'reason': 'Neither revision has readable text to compare.',
            'rows': [],
            'stats': _empty_stats(),
        }
    if len(old_blocks) > MAX_BLOCKS or len(new_blocks) > MAX_BLOCKS:
        return {
            'available': False,
            'reason': (
                f'These revisions are too long to diff in the browser '
                f'(over {MAX_BLOCKS} paragraphs).'
            ),
            'rows': [],
            'stats': _empty_stats(),
        }

    rows: List[Dict[str, Any]] = []
    stats = _empty_stats()
    matcher = SequenceMatcher(a=old_blocks, b=new_blocks, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            rows.extend(_equal_rows(old_blocks[i1:i2]))
            continue
        if tag == 'delete':
            changed = [{'kind': 'removed', 'old': b, 'new': ''} for b in old_blocks[i1:i2]]
        elif tag == 'insert':
            changed = [{'kind': 'added', 'old': '', 'new': b} for b in new_blocks[j1:j2]]
        else:
            changed = _changed_rows(old_blocks[i1:i2], new_blocks[j1:j2])
        for row in changed:
            stats[row['kind']] += 1
            if row['kind'] == 'rewritten':
                added, removed = change_counts(row['old'], row['new'])
                stats['chars_added'] += added
                stats['chars_removed'] += removed
        rows.extend(changed)

    identical = not any(r['kind'] in ('added', 'removed', 'rewritten') for r in rows)
    return {
        'available': True,
        'reason': 'These two revisions have identical text.' if identical else '',
        'rows': [] if identical else _trim_leading_trailing_context(rows),
        'stats': stats,
    }


def _empty_stats() -> Dict[str, int]:
    return {'added': 0, 'removed': 0, 'rewritten': 0, 'chars_added': 0, 'chars_removed': 0}


def _equal_rows(blocks: Sequence[str]) -> List[Dict[str, Any]]:
    """Keep a paragraph of context each side of a run, collapse the middle."""
    if len(blocks) <= CONTEXT_BLOCKS * 2 + 1:
        return [{'kind': 'context', 'old': b, 'new': b} for b in blocks]
    head = blocks[:CONTEXT_BLOCKS]
    tail = blocks[len(blocks) - CONTEXT_BLOCKS:]
    skipped = len(blocks) - CONTEXT_BLOCKS * 2
    return (
        [{'kind': 'context', 'old': b, 'new': b} for b in head]
        + [{'kind': 'unchanged', 'count': skipped}]
        + [{'kind': 'context', 'old': b, 'new': b} for b in tail]
    )


def _trim_leading_trailing_context(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop context and skip markers before the first change and after the last."""
    changed_positions = [
        idx for idx, row in enumerate(rows)
        if row['kind'] in ('added', 'removed', 'rewritten')
    ]
    if not changed_positions:
        return []
    start = max(0, changed_positions[0] - CONTEXT_BLOCKS)
    end = min(len(rows), changed_positions[-1] + CONTEXT_BLOCKS + 1)
    trimmed = rows[start:end]
    return [r for r in trimmed if r['kind'] != 'unchanged' or r.get('count')]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_ROW_META = {
    'added': ('gh-revdiff-added', 'fa-plus', 'Added'),
    'removed': ('gh-revdiff-removed', 'fa-minus', 'Removed'),
    'rewritten': ('gh-revdiff-rewritten', 'fa-pen', 'Rewritten'),
}


def _render_row(row: Dict[str, Any]) -> str:
    kind = row['kind']
    if kind == 'unchanged':
        count = row.get('count', 0)
        return (
            '<li class="gh-revdiff-skip">'
            f'{count} unchanged paragraph{"" if count == 1 else "s"}</li>'
        )
    if kind == 'context':
        return (
            '<li class="gh-revdiff-row gh-revdiff-context">'
            f'<p class="gh-revdiff-text">{html_mod.escape(row["old"])}</p></li>'
        )

    css_class, icon, label = _ROW_META[kind]
    if kind == 'rewritten':
        body = f'<p class="gh-revdiff-text">{build_diff_html(row["old"], row["new"])}</p>'
    else:
        text = row['new'] if kind == 'added' else row['old']
        body = f'<p class="gh-revdiff-text">{html_mod.escape(text)}</p>'
    return (
        f'<li class="gh-revdiff-row {css_class}">'
        f'<span class="gh-revdiff-tag"><i class="fas {icon} me-1" aria-hidden="true"></i>'
        f'{label}</span>{body}</li>'
    )


def render_diff_stats(stats: Dict[str, int]) -> str:
    """One-line tally of what changed between the two revisions."""
    chips = []
    for key, css, phrase in (
        ('added', 'gh-revdiff-chip-added', 'paragraph{s} added'),
        ('removed', 'gh-revdiff-chip-removed', 'paragraph{s} removed'),
        ('rewritten', 'gh-revdiff-chip-rewritten', 'paragraph{s} rewritten'),
    ):
        count = stats.get(key, 0)
        if not count:
            continue
        chips.append(
            f'<span class="badge gh-revdiff-chip {css}">'
            f'{count} {phrase.format(s="" if count == 1 else "s")}</span>'
        )
    if not chips:
        return ''
    if stats.get('rewritten'):
        chips.append(
            '<span class="gh-revdiff-chars small text-muted">'
            f'+{stats.get("chars_added", 0)} / −{stats.get("chars_removed", 0)} '
            'characters inside rewritten paragraphs</span>'
        )
    return f'<div class="gh-revdiff-stats mb-3">{" ".join(chips)}</div>'


def render_revision_diff(
    old_submission,
    new_submission,
    *,
    old_label: str,
    new_label: str,
) -> str:
    """Full diff panel body: tally plus the ordered list of changed paragraphs."""
    result = diff_revisions(
        revision_body_text(old_submission), revision_body_text(new_submission)
    )
    heading = (
        '<p class="text-muted small mb-3">Comparing '
        f'<strong>{html_mod.escape(old_label)}</strong> with '
        f'<strong>{html_mod.escape(new_label)}</strong>. '
        'Struck-through text was removed; highlighted text was added.</p>'
    )
    if not result['available'] or not result['rows']:
        note = result['reason'] or 'These two revisions have identical text.'
        return (
            f'{heading}<div class="alert alert-secondary mb-0" role="note">'
            f'<i class="fas fa-circle-info me-2" aria-hidden="true"></i>'
            f'{html_mod.escape(note)}</div>'
        )
    body = ''.join(_render_row(row) for row in result['rows'])
    return (
        f'{heading}{render_diff_stats(result["stats"])}'
        f'<ol class="gh-revdiff-list">{body}</ol>'
    )


def revision_options(
    rows: Sequence[Any],
    selected_id: Optional[str],
    *,
    name: str,
    label: str,
) -> str:
    """A ``<select>`` of every revision in the family, newest first."""
    options = ''.join(
        f'<option value="{html_mod.escape(str(row["id"]), quote=True)}"'
        f'{" selected" if str(row["id"]) == str(selected_id) else ""}>'
        f'{html_mod.escape(row["label"])}</option>'
        for row in rows
    )
    select_id = f'ghRevDiff{name.title()}'
    return (
        f'<div class="col-auto"><label class="form-label small mb-1" for="{select_id}">'
        f'{html_mod.escape(label)}</label>'
        f'<select class="form-select form-select-sm" id="{select_id}" name="{name}">'
        f'{options}</select></div>'
    )
