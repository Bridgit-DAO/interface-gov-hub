"""Shared patch mode constants and helpers (replace | insert | insert_after)."""
from __future__ import annotations

import re
from typing import FrozenSet

DP_PROPOSAL_PATCH_MODES: FrozenSet[str] = frozenset({'replace', 'insert', 'insert_after'})

_LIST_ANCHOR_RE = re.compile(r'^(?:[-*]\s+|\d+\.\s+)')


def normalize_patch_mode(mode: str | None) -> str:
    raw = (mode or 'replace').strip().lower().replace('-', '_')
    aliases = {
        'insert_below': 'insert_after',
        'insertbelow': 'insert_after',
        'insert_after': 'insert_after',
        'insert': 'insert',
        'replace': 'replace',
    }
    normalized = aliases.get(raw, raw)
    if normalized in DP_PROPOSAL_PATCH_MODES:
        return normalized
    return 'replace'


def is_insert_mode(mode: str | None) -> bool:
    return normalize_patch_mode(mode) in {'insert', 'insert_after'}


def is_list_item_anchor(text: str | None) -> bool:
    return bool(_LIST_ANCHOR_RE.match((text or '').strip()))


def suggest_patch_mode_for_anchor(anchor_text: str | None, preferred: str | None = None) -> str:
    """Pick insert_after for list-item anchors; otherwise honor preferred or replace."""
    if is_list_item_anchor(anchor_text):
        return 'insert_after'
    return normalize_patch_mode(preferred or 'replace')


def patch_mode_display_label(mode: str | None) -> str:
    normalized = normalize_patch_mode(mode)
    if normalized == 'insert':
        return 'Insert above'
    if normalized == 'insert_after':
        return 'Insert after'
    return 'Replace'


def patch_mode_status_label(mode: str | None, status: str | None) -> str | None:
    """Pending status label override for insert modes."""
    if (status or '') != 'pending':
        return None
    normalized = normalize_patch_mode(mode)
    if normalized == 'insert':
        return 'Insert above'
    if normalized == 'insert_after':
        return 'Insert after'
    return None
