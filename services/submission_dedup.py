"""Submission duplicate detection via title, inscription ID, and content hash."""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from typing import Literal, Optional

import requests

from extensions import db
from models import Submission
from services.documents import extract_text_from_file
from services.ml_numbering import normalize_title
from services.submissions import get_submission_by_ref
from services.utils import coerce_storage_bool

ACTIVE_STATUSES = ('submitted', 'approved', 'published')
ConflictReason = Literal['title', 'ordinal_id', 'content_hash']


def normalize_ordinal_id(ordinal_id: str) -> str:
    return (ordinal_id or '').strip().lower()


def normalize_text_for_hash(text: str) -> str:
    """Whitespace- and case-normalized text so identical prose hashes match."""
    t = unicodedata.normalize('NFKC', text or '')
    t = re.sub(r'\s+', ' ', t.strip())
    return t.casefold()


def hash_text_content(text: str) -> str:
    return hashlib.sha256(normalize_text_for_hash(text).encode('utf-8')).hexdigest()


def hash_binary_content(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_text_content_type(content_type: str, filename: str = '') -> bool:
    ct = (content_type or '').lower()
    ext = os.path.splitext((filename or '').lower())[1]
    if ext in ('.txt', '.md', '.markdown', '.xml'):
        return True
    return (
        ct.startswith('text/')
        or 'markdown' in ct
        or 'json' in ct
        or 'javascript' in ct
    )


def compute_content_hash_from_bytes(
    data: bytes,
    *,
    content_type: str = '',
    filename: str = '',
) -> str:
    if is_text_content_type(content_type, filename):
        text = data.decode('utf-8', errors='replace')
        if text.strip():
            return hash_text_content(text)
    return hash_binary_content(data)


def compute_content_hash_for_file(file_path: str, filename: str) -> Optional[str]:
    if not file_path or not os.path.isfile(file_path):
        return None
    text = extract_text_from_file(file_path, filename)
    if text.strip():
        return hash_text_content(text)
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        if data:
            return hash_binary_content(data)
    except OSError:
        return None
    return None


def compute_content_hash_for_ordinal_url(
    content_url: str,
    content_type: str = '',
    *,
    timeout: int = 30,
) -> Optional[str]:
    if not content_url:
        return None
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': '*/*',
        }
        response = requests.get(content_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return compute_content_hash_from_bytes(
            response.content,
            content_type=content_type or response.headers.get('Content-Type', ''),
        )
    except Exception:
        return None


def compute_content_hash_for_submission(submission: Submission) -> Optional[str]:
    stored = (getattr(submission, 'content_hash', None) or '').strip()
    if stored:
        return stored

    source = (getattr(submission, 'sourceType', None) or 'file').lower()
    if source == 'ordinal':
        url = getattr(submission, 'ordinalContentUrl', None)
        ctype = getattr(submission, 'ordinalContentType', None) or ''
        return compute_content_hash_for_ordinal_url(url, ctype)

    file_path = getattr(submission, 'file_path', None)
    filename = getattr(submission, 'filename', None) or ''
    return compute_content_hash_for_file(file_path, filename)


def _submission_family_ids(submission: Submission) -> set[str]:
    ids = {submission.id}
    if submission.draft_name:
        ids.add(submission.draft_name)
    parent_ref = getattr(submission, 'parent_draft_name', None)
    if parent_ref:
        ids.add(parent_ref)
        parent = get_submission_by_ref(parent_ref)
        if parent:
            ids.add(parent.id)
            if parent.draft_name:
                ids.add(parent.draft_name)
    return ids


def _is_excluded_family(sub: Submission, exclude_family_parent_id: Optional[str]) -> bool:
    if not exclude_family_parent_id:
        return False
    anchor = get_submission_by_ref(exclude_family_parent_id)
    if not anchor:
        return sub.id == exclude_family_parent_id or sub.parent_draft_name == exclude_family_parent_id
    family = _submission_family_ids(anchor)
    sub_refs = _submission_family_ids(sub)
    return bool(family & sub_refs)


def _active_candidates() -> list[Submission]:
    return Submission.query.filter(
        Submission.status.in_(ACTIVE_STATUSES),
        Submission.doc_type == 'draft',
    ).all()


def find_submission_conflict(
    *,
    title: str,
    ordinal_id: Optional[str] = None,
    content_hash: Optional[str] = None,
    exclude_family_parent_id: Optional[str] = None,
) -> Optional[tuple[ConflictReason, Submission]]:
    """
    Return the first duplicate conflict for a new draft/revision upload.
    Checks inscription ID, content hash, then title (in that order).
    """
    norm_oid = normalize_ordinal_id(ordinal_id or '')
    norm_title = normalize_title(title)
    norm_hash = (content_hash or '').strip().lower()

    for sub in _active_candidates():
        if _is_excluded_family(sub, exclude_family_parent_id):
            continue

        if norm_oid:
            existing_oid = normalize_ordinal_id(getattr(sub, 'ordinalId', None) or '')
            if existing_oid and existing_oid == norm_oid:
                return ('ordinal_id', sub)

        if norm_hash:
            existing_hash = (getattr(sub, 'content_hash', None) or '').strip().lower()
            if not existing_hash:
                existing_hash = (compute_content_hash_for_submission(sub) or '').lower()
            if existing_hash and existing_hash == norm_hash:
                return ('content_hash', sub)

        if norm_title and normalize_title(sub.title or '') == norm_title:
            from services.ml_numbering import is_parent_submission

            if is_parent_submission(sub):
                return ('title', sub)

    return None


def conflict_message(reason: ConflictReason, conflict: Submission) -> str:
    label = (conflict.ml_number or conflict.id or 'existing document').strip()
    title = (conflict.title or 'Untitled').strip()
    if reason == 'ordinal_id':
        oid = getattr(conflict, 'ordinalId', None) or 'unknown'
        return (
            f'This inscription is already registered as "{title}" ({label}). '
            f'Inscription ID: {oid}. Submit a revision instead of a new draft.'
        )
    if reason == 'content_hash':
        return (
            f'This document content already exists as "{title}" ({label}), '
            f'even though the title differs. Submit a revision instead of a new draft.'
        )
    return (
        f'A document titled "{title}" already exists ({label}). '
        f'Submit a revision to that document instead of uploading a new draft.'
    )


def backfill_submission_content_hashes(*, commit: bool = True) -> dict[str, int]:
    """Compute and store content_hash for submissions missing it."""
    stats = {'updated': 0, 'skipped': 0, 'failed': 0}
    for sub in Submission.query.filter_by(doc_type='draft').all():
        if (getattr(sub, 'content_hash', None) or '').strip():
            stats['skipped'] += 1
            continue
        h = compute_content_hash_for_submission(sub)
        if not h:
            stats['failed'] += 1
            continue
        sub.content_hash = h
        stats['updated'] += 1
    if commit and stats['updated']:
        db.session.commit()
    return stats
