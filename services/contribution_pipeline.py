"""Contribution learning-loop pipeline queue — Scout intake (Phase 0)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from extensions import db


def contribution_registry_id(source: str, source_id: str) -> str:
    return f'dp-contrib:{source}:{source_id}'


def enqueue_contribution_pipeline_event(
    *,
    subject_type: str,
    subject_id: str,
    event_type: str,
    source_channel: str = 'gov-hub',
    payload: Optional[dict] = None,
) -> str:
    """Insert a row for Scout to process. Idempotent per subject+event within 1 minute."""
    from sqlalchemy import text

    row_id = str(uuid4())
    payload_json = json.dumps(payload or {}, default=str)
    db.session.execute(
        text("""
            INSERT INTO contribution_pipeline_queue
              (id, subject_type, subject_id, event_type, source_channel, payload_json, created_at)
            VALUES
              (:id, :subject_type, :subject_id, :event_type, :source_channel, :payload_json, :created_at)
        """),
        {
            'id': row_id,
            'subject_type': subject_type,
            'subject_id': subject_id,
            'event_type': event_type,
            'source_channel': source_channel,
            'payload_json': payload_json,
            'created_at': datetime.utcnow(),
        },
    )
    return row_id


def list_pending_pipeline_events(*, limit: int = 100) -> list[dict]:
    """Unprocessed queue rows for Scout (Phase 1)."""
    from sqlalchemy import text

    rows = db.session.execute(
        text("""
            SELECT id, subject_type, subject_id, event_type, source_channel, payload_json, created_at
            FROM contribution_pipeline_queue
            WHERE processed_at IS NULL
            ORDER BY created_at ASC
            LIMIT :limit
        """),
        {'limit': max(1, min(limit, 500))},
    ).mappings().all()
    out = []
    for row in rows:
        item = dict(row)
        try:
            item['payload'] = json.loads(item.pop('payload_json') or '{}')
        except json.JSONDecodeError:
            item['payload'] = {}
            item.pop('payload_json', None)
        out.append(item)
    return out


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


def pipeline_payload_for_proposal(proposal, submission) -> dict:
    from services.dp_proposals import submission_draft_ref

    return {
        'proposal_id': proposal.id,
        'submission_id': proposal.submission_id,
        'draft_ref': submission_draft_ref(submission),
        'ml_number': submission.ml_number if submission else None,
        'scope': proposal.scope,
        'status': proposal.status,
        'anchor_hash': proposal.anchor_hash,
        'contribution_registry_id': getattr(proposal, 'contribution_registry_id', None)
        or contribution_registry_id(
            getattr(proposal, 'source_channel', None) or 'gov-hub',
            proposal.id,
        ),
    }
