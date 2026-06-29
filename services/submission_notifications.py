"""Emit EventLog + dispatch document-follow notifications when submissions change status."""
from __future__ import annotations

from typing import Any, Optional, Tuple

from sqlalchemy import or_

from models import Submission, User
from services.document_follow_notifications import (
    dispatch_document_followers,
    draft_key_for_submission,
)
from services.events import emit_event
from services.utils import coerce_storage_bool


def submitter_user_id(submission: Submission) -> Optional[str]:
    """Resolve submitter User.id from Submission.submitted_by display name."""
    name = (submission.submitted_by or '').strip()
    if not name or name == 'Anonymous User':
        return None
    user = User.query.filter(
        or_(User.username == name, User.displayName == name)
    ).first()
    return str(user.id) if user else None


def emit_draft_created(
    submission: Submission,
    *,
    actor_user_id: Optional[str] = None,
) -> None:
    """Emit when a new draft is approved and receives its ML number (attributed to submitter)."""
    actor_id = actor_user_id or submitter_user_id(submission)
    if not actor_id:
        return
    draft_key = draft_key_for_submission(submission)
    emit_event(
        'draft_created',
        actor_type='user',
        actor_id=actor_id,
        subject_type='submission',
        subject_id=submission.id,
        layer_id=submission.layer_id,
        payload={
            'draft_name': draft_key,
            'ml_number': submission.ml_number,
            'title': submission.title,
            'source_type': getattr(submission, 'sourceType', None) or 'file',
            'status': submission.status,
        },
    )


def emit_submission_status_notification(
    submission: Submission,
    *,
    actor_user_id: str,
    old_status: str,
    new_status: str,
    rfc_number: Optional[Any] = None,
) -> Optional[Tuple[Any, str, str, str, str, str]]:
    """
    If status transition warrants document-follow notification, emit EventLog and return
    (event_log, draft_key, event_type, title, body, link_path) for dispatch after commit.
    """
    if old_status == new_status:
        return None
    if new_status not in ('approved', 'published'):
        return None

    draft_key = draft_key_for_submission(submission)
    layer_id = submission.layer_id

    if new_status == 'published':
        rfc = rfc_number
        if rfc is None and submission.rfc_number is not None:
            rfc = submission.rfc_number
        evt = emit_event(
            'draft_published_as_rfc',
            actor_type='user',
            actor_id=actor_user_id,
            subject_type='submission',
            subject_id=submission.id,
            layer_id=layer_id,
            payload={
                'draft_name': draft_key,
                'ml_number': submission.ml_number,
                'rfc_number': rfc,
            },
        )
        title = f'RFC published: {submission.title or draft_key}'
        body = f'Document {submission.ml_number or draft_key} was published as RFC {rfc}.'
        return evt, draft_key, 'draft_published_as_rfc', title, body, f'/doc/draft/{draft_key}/'

    # approved (SQLite may store is_revision as TEXT '0'/'1'; bool('0') is True in Python)
    is_revision = coerce_storage_bool(getattr(submission, 'is_revision', False), default=False)
    has_revision_context = bool(
        (getattr(submission, 'revision_number', None) or '').strip()
        or (getattr(submission, 'parent_draft_name', None) or '').strip()
    )
    if is_revision and has_revision_context:
        evt = emit_event(
            'draft_revision_approved',
            actor_type='user',
            actor_id=actor_user_id,
            subject_type='submission',
            subject_id=submission.id,
            layer_id=layer_id,
            payload={
                'draft_name': draft_key,
                'ml_number': submission.ml_number,
                'revision_number': getattr(submission, 'revision_number', None),
            },
        )
        rev = getattr(submission, 'revision_number', '') or ''
        title = f'New revision approved: {submission.ml_number or draft_key}'
        body = f'Revision {rev} is now approved for {submission.ml_number or draft_key}.'
        event_type = 'draft_revision_approved'
    else:
        evt = emit_event(
            'draft_submission_approved',
            actor_type='user',
            actor_id=actor_user_id,
            subject_type='submission',
            subject_id=submission.id,
            layer_id=layer_id,
            payload={'draft_name': draft_key, 'ml_number': submission.ml_number},
        )
        emit_draft_created(submission)
        title = f'Draft approved: {submission.title or draft_key}'
        body = f'{submission.ml_number or draft_key} has been approved.'
        event_type = 'draft_submission_approved'

    return evt, draft_key, event_type, title, body, f'/doc/draft/{draft_key}/'


def run_submission_notification_dispatch(bundle: Tuple[Any, str, str, str, str, str], actor_user_id: str) -> None:
    evt, draft_key, event_type, title, body, link_path = bundle
    dispatch_document_followers(
        draft_name=draft_key,
        event_type=event_type,
        event_log=evt,
        actor_user_id=actor_user_id,
        title=title,
        body=body,
        link_path=link_path,
    )
