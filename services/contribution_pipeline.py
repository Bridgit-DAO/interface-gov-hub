"""Contribution learning-loop pipeline queue — Scout intake."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from extensions import db

# Dedup window for identical subject+event enqueues
IDEMPOTENCY_WINDOW_SECONDS = 60
# Scout claim lease TTL — expired claims can be reclaimed
CLAIM_LEASE_SECONDS = 300


def contribution_registry_id(source: str, source_id: str) -> str:
    return f'dp-contrib:{source}:{source_id}'


def enqueue_contribution_pipeline_event(
    *,
    subject_type: str,
    subject_id: str,
    event_type: str,
    source_channel: str = 'gov-hub',
    payload: Optional[dict] = None,
) -> Optional[str]:
    """Insert a row for Scout. Idempotent per subject+event within 1 minute.

    Returns the new (or existing) row id, or None if the insert was skipped
    because an identical unprocessed/recent row already exists.
    """
    from sqlalchemy import text

    window_start = datetime.utcnow() - timedelta(seconds=IDEMPOTENCY_WINDOW_SECONDS)
    existing = db.session.execute(
        text("""
            SELECT id FROM contribution_pipeline_queue
            WHERE subject_type = :subject_type
              AND subject_id = :subject_id
              AND event_type = :event_type
              AND created_at >= :window_start
              AND processed_at IS NULL
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {
            'subject_type': subject_type,
            'subject_id': str(subject_id),
            'event_type': event_type,
            'window_start': window_start,
        },
    ).mappings().first()
    if existing:
        return existing['id']

    row_id = str(uuid4())
    payload_json = json.dumps(payload or {}, default=str)
    db.session.execute(
        text("""
            INSERT INTO contribution_pipeline_queue
              (id, subject_type, subject_id, event_type, source_channel,
               payload_json, created_at)
            VALUES
              (:id, :subject_type, :subject_id, :event_type, :source_channel,
               :payload_json, :created_at)
        """),
        {
            'id': row_id,
            'subject_type': subject_type,
            'subject_id': str(subject_id),
            'event_type': event_type,
            'source_channel': source_channel,
            'payload_json': payload_json,
            'created_at': datetime.utcnow(),
        },
    )
    return row_id


def list_pending_pipeline_events(*, limit: int = 100) -> list[dict]:
    """Unprocessed, unclaimed (or lease-expired) queue rows for Scout."""
    from sqlalchemy import text

    lease_cutoff = datetime.utcnow() - timedelta(seconds=CLAIM_LEASE_SECONDS)
    rows = db.session.execute(
        text("""
            SELECT id, subject_type, subject_id, event_type, source_channel,
                   payload_json, created_at, claimed_at, claimed_by
            FROM contribution_pipeline_queue
            WHERE processed_at IS NULL
              AND (claimed_at IS NULL OR claimed_at < :lease_cutoff)
            ORDER BY created_at ASC
            LIMIT :limit
        """),
        {
            'limit': max(1, min(limit, 500)),
            'lease_cutoff': lease_cutoff,
        },
    ).mappings().all()
    return [_row_to_event(row) for row in rows]


def claim_pending_pipeline_events(
    *,
    claimant: str,
    limit: int = 100,
) -> list[dict]:
    """Atomically claim pending rows for a Scout worker.

    Sets claimed_at / claimed_by on up to `limit` unprocessed rows whose
    lease is free or expired. Caller must commit.
    """
    from sqlalchemy import text

    now = datetime.utcnow()
    lease_cutoff = now - timedelta(seconds=CLAIM_LEASE_SECONDS)
    claim_id = (claimant or 'scout').strip()[:80] or 'scout'

    # SQLite: select candidates then update by id list
    candidates = db.session.execute(
        text("""
            SELECT id FROM contribution_pipeline_queue
            WHERE processed_at IS NULL
              AND (claimed_at IS NULL OR claimed_at < :lease_cutoff)
            ORDER BY created_at ASC
            LIMIT :limit
        """),
        {
            'limit': max(1, min(limit, 500)),
            'lease_cutoff': lease_cutoff,
        },
    ).mappings().all()
    if not candidates:
        return []

    ids = [row['id'] for row in candidates]
    placeholders = ', '.join(f':id{i}' for i in range(len(ids)))
    params = {f'id{i}': eid for i, eid in enumerate(ids)}
    params['now'] = now
    params['claim_id'] = claim_id
    params['lease_cutoff'] = lease_cutoff

    db.session.execute(
        text(
            'UPDATE contribution_pipeline_queue '
            'SET claimed_at = :now, claimed_by = :claim_id '
            f'WHERE processed_at IS NULL '
            f'AND (claimed_at IS NULL OR claimed_at < :lease_cutoff) '
            f'AND id IN ({placeholders})'
        ),
        params,
    )

    rows = db.session.execute(
        text(
            f"""
            SELECT id, subject_type, subject_id, event_type, source_channel,
                   payload_json, created_at, claimed_at, claimed_by
            FROM contribution_pipeline_queue
            WHERE claimed_by = :claim_id
              AND processed_at IS NULL
              AND id IN ({placeholders})
            ORDER BY created_at ASC
            """
        ),
        {**{f'id{i}': eid for i, eid in enumerate(ids)}, 'claim_id': claim_id},
    ).mappings().all()
    return [_row_to_event(row) for row in rows]


def mark_pipeline_events_processed(event_ids: list[str]) -> int:
    if not event_ids:
        return 0
    from sqlalchemy import text

    placeholders = ', '.join(f':id{i}' for i in range(len(event_ids)))
    params = {f'id{i}': eid for i, eid in enumerate(event_ids)}
    params['now'] = datetime.utcnow()
    result = db.session.execute(
        text(
            'UPDATE contribution_pipeline_queue '
            f'SET processed_at = :now WHERE processed_at IS NULL AND id IN ({placeholders})'
        ),
        params,
    )
    return result.rowcount or 0


def pipeline_queue_table_exists() -> bool:
    """Startup health check — True if contribution_pipeline_queue is present."""
    from sqlalchemy import text

    try:
        row = db.session.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='contribution_pipeline_queue'"
            )
        ).first()
        return bool(row)
    except Exception:
        return False


def pipeline_payload_for_proposal(proposal, submission) -> dict:
    from services.dp_proposals import submission_draft_ref

    return {
        'proposal_id': proposal.id,
        'submission_id': proposal.submission_id,
        'draft_ref': submission_draft_ref(submission),
        'ml_number': submission.ml_number if submission else None,
        'scope': proposal.scope,
        'status': proposal.status,
        'kind': 'patch',
        'anchor_hash': proposal.anchor_hash,
        'contribution_registry_id': getattr(proposal, 'contribution_registry_id', None)
        or contribution_registry_id(
            getattr(proposal, 'source_channel', None) or 'gov-hub',
            proposal.id,
        ),
    }


def pipeline_payload_for_comment(comment, submission) -> dict:
    from services.dp_proposals import submission_draft_ref

    source = getattr(comment, 'source_channel', None) or 'gov-hub'
    return {
        'comment_id': comment.id,
        'submission_id': comment.submission_id,
        'draft_ref': submission_draft_ref(submission) if submission else comment.draft_name,
        'ml_number': submission.ml_number if submission else None,
        'kind': 'comment',
        'comment_scope': getattr(comment, 'comment_scope', None) or 'document',
        'anchor_hash': comment.anchor_hash,
        'text': (comment.text or '')[:500],
        'contribution_registry_id': getattr(comment, 'contribution_registry_id', None)
        or contribution_registry_id(source, comment.id),
    }


def _row_to_event(row) -> dict:
    item = dict(row)
    try:
        item['payload'] = json.loads(item.pop('payload_json') or '{}')
    except (json.JSONDecodeError, TypeError):
        item['payload'] = {}
        item.pop('payload_json', None)
    return item
