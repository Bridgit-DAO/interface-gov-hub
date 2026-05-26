"""ML-Draft numbering, reordering, and duplicate detection."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from extensions import db
from models import SiteConfig, Submission
from services.utils import coerce_storage_bool

ACTIVE_STATUSES = ('submitted', 'approved', 'published')
ML_NUMBERING_SEALED_KEY = 'ml_numbering_sealed'
_ML_DRAFT_RE = re.compile(r'^ML-Draft-(\d+)$', re.IGNORECASE)


def normalize_title(title: str) -> str:
    """Case-insensitive trimmed title for duplicate comparison."""
    t = re.sub(r'\s+', ' ', (title or '').strip()).casefold()
    t = re.sub(r'[–—−]', '-', t)
    return t


def is_parent_submission(submission: Submission) -> bool:
    """True when this row is the initial submission (not a revision)."""
    from sqlalchemy import text

    row = db.session.execute(
        text('SELECT is_revision FROM submission WHERE id = :id'),
        {'id': submission.id},
    ).fetchone()
    if row is not None:
        return not coerce_storage_bool(row[0], default=False)
    return not coerce_storage_bool(getattr(submission, 'is_revision', False), default=False)


def format_ml_draft_number(seq: int) -> str:
    if seq < 1000:
        return f'ML-Draft-{seq:03d}'
    return f'ML-Draft-{seq:04d}'


def parse_ml_draft_seq(ml_number: Optional[str]) -> Optional[int]:
    if not ml_number:
        return None
    match = _ML_DRAFT_RE.match(str(ml_number).strip())
    return int(match.group(1)) if match else None


def is_ml_numbering_sealed() -> bool:
    """When sealed, ML numbers are immutable and auto-renumber is disabled."""
    row = SiteConfig.query.filter_by(key=ML_NUMBERING_SEALED_KEY).first()
    if not row or not (row.value or '').strip():
        return False
    return row.value.strip().lower() in ('1', 'true', 'yes', 'on', 'sealed')


def seal_ml_numbering(*, note: str = '') -> None:
    """Mark ML numbering as locked. New approvals still receive the next number."""
    payload = note.strip() or datetime.utcnow().isoformat(timespec='seconds') + 'Z'
    row = SiteConfig.query.filter_by(key=ML_NUMBERING_SEALED_KEY).first()
    if row:
        row.value = payload
    else:
        db.session.add(SiteConfig(key=ML_NUMBERING_SEALED_KEY, value=payload))
    db.session.commit()


def creation_order_sort_key(parent: Submission, members: list[Submission]) -> tuple:
    """
    Order ML numbers by document family creation time (earliest submission in lineage).
    Tie-break on parent id for stable ordering.
    """
    timestamps = [m.submitted_at for m in members if m.submitted_at]
    first = min(timestamps) if timestamps else datetime.min
    return (first, parent.id or '')


def canonical_document_sort_key(submission: Submission) -> tuple:
    """Deprecated alias kept for tests importing the old name."""
    return creation_order_sort_key(submission, [submission])


def _family_members(parent: Submission) -> list[Submission]:
    """Parent plus all revision rows sharing its lineage."""
    members = [parent]
    parent_refs = {parent.id}
    if parent.draft_name:
        parent_refs.add(parent.draft_name)
    revisions = Submission.query.filter(
        Submission.parent_draft_name.in_(parent_refs),
    ).all()
    members.extend(revisions)
    return members


def iter_document_families(*, statuses: tuple[str, ...] = ACTIVE_STATUSES) -> list[dict[str, Any]]:
    """
    One entry per active parent document family, sorted by creation order.
    Revisions inherit the parent's ML number.
    """
    parents = (
        Submission.query.filter(
            Submission.status.in_(statuses),
            Submission.doc_type == 'draft',
        )
        .all()
    )
    families = []
    seen_parent_ids: set[str] = set()

    for sub in parents:
        if not is_parent_submission(sub):
            continue
        if sub.id in seen_parent_ids:
            continue
        seen_parent_ids.add(sub.id)
        members = _family_members(sub)
        families.append({
            'parent': sub,
            'members': members,
            'sort_key': creation_order_sort_key(sub, members),
            'old_ml': (sub.ml_number or '').strip() or None,
        })

    families.sort(key=lambda f: f['sort_key'])
    return families


def build_ml_renumber_plan(*, statuses: tuple[str, ...] = ACTIVE_STATUSES) -> list[dict[str, Any]]:
    """Return planned old → new ML numbers for each document family (creation order)."""
    families = iter_document_families(statuses=statuses)
    plan = []
    for idx, family in enumerate(families, start=1):
        new_ml = format_ml_draft_number(idx)
        old_ml = family['old_ml']
        first_sub = family['sort_key'][0]
        plan.append({
            'parent_id': family['parent'].id,
            'title': family['parent'].title,
            'old_ml': old_ml,
            'new_ml': new_ml,
            'first_submitted_at': first_sub.isoformat() if first_sub != datetime.min else None,
            'member_ids': [m.id for m in family['members']],
            'changes': old_ml != new_ml,
        })
    return plan


def apply_ml_renumber_plan(plan: list[dict[str, Any]], *, force: bool = False) -> int:
    """
    Apply renumber plan using a two-phase update to avoid transient collisions.
    Returns count of families updated.
    """
    if is_ml_numbering_sealed() and not force:
        raise RuntimeError(
            'ML numbering is sealed; renumbering is blocked. '
            'Use scripts/renumber_ml_drafts.py --force if you must override.'
        )

    to_update = [entry for entry in plan if entry['changes']]
    if not to_update:
        return 0

    id_to_final: dict[str, str] = {}
    for entry in to_update:
        for member_id in entry['member_ids']:
            id_to_final[member_id] = entry['new_ml']

    for sub_id, _final_ml in id_to_final.items():
        sub = db.session.get(Submission, sub_id)
        if sub:
            sub.ml_number = f'_TMP_{sub_id}'

    db.session.flush()

    for sub_id, final_ml in id_to_final.items():
        sub = db.session.get(Submission, sub_id)
        if sub:
            sub.ml_number = final_ml

    return len(to_update)


def needs_ml_renumber(*, statuses: tuple[str, ...] = ACTIVE_STATUSES) -> bool:
    """True when any active document family is out of creation-order sequence."""
    if is_ml_numbering_sealed():
        return False
    plan = build_ml_renumber_plan(statuses=statuses)
    return any(entry['changes'] for entry in plan)


def find_conflicting_submission(
    title: str,
    *,
    exclude_submission_id: Optional[str] = None,
    statuses: tuple[str, ...] = ACTIVE_STATUSES,
) -> Optional[Submission]:
    """Backward-compatible title-only duplicate check."""
    from services.submission_dedup import find_submission_conflict

    result = find_submission_conflict(
        title=title,
        exclude_family_parent_id=exclude_submission_id,
    )
    if result and result[0] == 'title':
        return result[1]
    return None


def conflict_message(conflict: Submission) -> str:
    from services.submission_dedup import conflict_message as _msg

    return _msg('title', conflict)
