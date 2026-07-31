"""Canopi smart-tag contributions → Gov Hub dp_proposal / comment (Phase 1 intake)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Tuple
from uuid import uuid4

from extensions import db
from models import Comment, DpProposal, Submission, User
from services.contribution_pipeline import (
    contribution_registry_id,
    enqueue_contribution_pipeline_event,
    pipeline_payload_for_comment,
    pipeline_payload_for_proposal,
)
from services.document_reader_comments import create_reader_comment, validate_comment_payload
from services.dp_proposals import (
    create_dp_proposal,
    resolve_canonical_submission,
    resolve_submission_for_proposals,
)


def _normalize_email(raw: str | None) -> str:
    return (raw or '').strip().lower()


def _resolve_author_user_id(*, author_user_id: str | None, author_email: str | None) -> Tuple[Optional[str], Optional[str]]:
    if author_user_id:
        user = User.query.get(author_user_id)
        if user:
            return user.id, None
        return None, 'author_user_id not found'
    email = _normalize_email(author_email)
    if not email:
        return None, 'author_email or author_user_id required'
    user = User.query.filter(db.func.lower(User.email) == email).first()
    if not user:
        return None, 'author not found in Gov Hub'
    return user.id, None


def _find_existing_canopi_patch(external_id: str) -> Optional[DpProposal]:
    return DpProposal.query.filter_by(
        source_channel='canopi',
        external_id=external_id,
    ).first()


def _find_existing_canopi_comment(external_id: str) -> Optional[Comment]:
    return Comment.query.filter_by(
        source_channel='canopi',
        external_id=external_id,
    ).first()


def _enqueue_patch_pipeline(proposal: DpProposal, event_type: str = 'submitted') -> None:
    try:
        enqueue_contribution_pipeline_event(
            subject_type='dp_proposal',
            subject_id=proposal.id,
            event_type=event_type,
            source_channel='canopi',
            payload=pipeline_payload_for_proposal(proposal, proposal.submission),
        )
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning(
                '[ContributionPipeline] Canopi patch enqueue failed for %s: %s',
                proposal.id,
                e,
            )
        except RuntimeError:
            pass


def _enqueue_comment_pipeline(comment: Comment, submission: Submission, event_type: str = 'submitted') -> None:
    try:
        enqueue_contribution_pipeline_event(
            subject_type='comment',
            subject_id=comment.id,
            event_type=event_type,
            source_channel='canopi',
            payload=pipeline_payload_for_comment(comment, submission),
        )
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning(
                '[ContributionPipeline] Canopi comment enqueue failed for %s: %s',
                comment.id,
                e,
            )
        except RuntimeError:
            pass


def intake_canopi_patch(
    *,
    draft_ref: str,
    external_id: str,
    author_user_id: str | None = None,
    author_email: str | None = None,
    canopi_overlay_id: str | None = None,
    payload: dict,
) -> Tuple[dict, int]:
    ext = (external_id or '').strip()
    if not ext:
        return {'error': 'external_id required'}, 400

    existing = _find_existing_canopi_patch(ext)
    if existing:
        return {
            'proposal': existing.to_dict(),
            'status_label': existing.status_label(),
            'idempotent': True,
        }, 200

    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return {'error': err}, 404 if err == 'Document not found' else 400
    if submission.status != 'approved':
        return {'error': 'Patches require an approved document'}, 400
    submission = resolve_canonical_submission(submission) or submission

    uid, author_err = _resolve_author_user_id(
        author_user_id=author_user_id,
        author_email=author_email,
    )
    if author_err:
        return {'error': author_err}, 400

    original = (payload.get('original_text') or '').strip()
    proposed = (payload.get('proposed_text') or '').strip()
    if not original or not proposed:
        return {'error': 'original_text and proposed_text required'}, 400

    scope = (payload.get('scope') or 'dp').strip().lower()
    if scope not in ('dp', 'document'):
        return {'error': 'scope must be dp or document'}, 400

    row = create_dp_proposal(
        submission,
        author_user_id=uid,
        original_text=original,
        proposed_text=proposed,
        context_anchor=payload.get('context_anchor'),
        scope=scope,
        rationale=(payload.get('rationale') or None),
        reference_url=(payload.get('reference_url') or None),
        source_channel='canopi',
        external_id=ext,
        canopi_overlay_id=(canopi_overlay_id or None),
    )
    db.session.flush()
    row.contribution_registry_id = contribution_registry_id('canopi', row.id)
    _enqueue_patch_pipeline(row, 'submitted')
    db.session.commit()
    return {
        'proposal': row.to_dict(),
        'status_label': row.status_label(),
        'contribution_registry_id': row.contribution_registry_id,
    }, 201


def intake_canopi_comment(
    *,
    draft_ref: str,
    external_id: str,
    author_user_id: str | None = None,
    author_email: str | None = None,
    canopi_overlay_id: str | None = None,
    payload: dict,
) -> Tuple[dict, int]:
    ext = (external_id or '').strip()
    if not ext:
        return {'error': 'external_id required'}, 400

    existing = _find_existing_canopi_comment(ext)
    if existing:
        from services.document_reader_comments import _comment_to_dict
        from services.identity import get_current_user
        return {
            'comment': _comment_to_dict(existing, current_user=get_current_user()),
            'idempotent': True,
        }, 200

    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return {'error': err}, 404 if err == 'Document not found' else 400
    if submission.status != 'approved':
        return {'error': 'Comments require an approved document'}, 400
    submission = resolve_canonical_submission(submission) or submission

    uid, author_err = _resolve_author_user_id(
        author_user_id=author_user_id,
        author_email=author_email,
    )
    if author_err:
        return {'error': author_err}, 400

    body = dict(payload or {})
    body.setdefault('comment_scope', body.get('comment_scope') or 'document')
    validated, val_err = validate_comment_payload(body, require_passage=False)
    if val_err:
        return {'error': val_err}, 400

    row, create_err = create_reader_comment(
        submission,
        author_user_id=uid,
        payload=validated,
    )
    if create_err:
        return {'error': create_err}, 400

    row.source_channel = 'canopi'
    row.external_id = ext
    row.canopi_overlay_id = canopi_overlay_id or None
    row.contribution_registry_id = contribution_registry_id('canopi', row.id)
    _enqueue_comment_pipeline(row, submission, 'submitted')
    db.session.commit()

    from services.document_reader_comments import _comment_to_dict
    from services.identity import get_current_user

    return {
        'comment': _comment_to_dict(row, current_user=get_current_user()),
        'contribution_registry_id': row.contribution_registry_id,
    }, 201


def intake_canopi_contribution(body: Any) -> Tuple[dict, int]:
    if not isinstance(body, dict):
        return {'error': 'JSON body required'}, 400

    kind = (body.get('kind') or '').strip().lower()
    draft_ref = (body.get('draft_ref') or body.get('draftRef') or '').strip()
    external_id = (body.get('external_id') or body.get('externalId') or '').strip()
    payload = body.get('payload') if isinstance(body.get('payload'), dict) else body

    if not draft_ref:
        return {'error': 'draft_ref required'}, 400

    common = {
        'draft_ref': draft_ref,
        'external_id': external_id,
        'author_user_id': body.get('author_user_id') or body.get('authorUserId'),
        'author_email': body.get('author_email') or body.get('authorEmail'),
        'canopi_overlay_id': body.get('canopi_overlay_id') or body.get('canopiOverlayId'),
    }

    if kind == 'patch':
        return intake_canopi_patch(**common, payload=payload)
    if kind == 'comment':
        return intake_canopi_comment(**common, payload=payload)
    return {'error': 'kind must be patch or comment'}, 400
