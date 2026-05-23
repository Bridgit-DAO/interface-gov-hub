"""Emit EventLog + dispatch document-follow notifications when submissions change status."""
from __future__ import annotations

from typing import Any, Optional, Tuple

from models import Submission
from services.document_follow_notifications import (
    dispatch_document_followers,
    draft_key_for_submission,
)
from services.events import emit_event


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

    # approved
    is_revision = bool(getattr(submission, 'is_revision', False))
    if is_revision:
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
