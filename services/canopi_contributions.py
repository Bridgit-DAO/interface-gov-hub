"""Canopi smart-tag contributions → Gov Hub dp_proposal / comment (Phase 1 intake)."""
from __future__ import annotations

from typing import Any, Optional, Tuple

from extensions import db
from models import Comment, DpProposal, Submission, User
from sqlalchemy.exc import IntegrityError
from services.contribution_pipeline import (
    contribution_registry_id,
    enqueue_contribution_pipeline_event,
    pipeline_payload_for_comment,
    pipeline_payload_for_proposal,
)
from services.document_reader_comments import create_reader_comment, validate_comment_payload
from services.dp_proposals import (
    create_dp_proposal,
    expected_proposal_scope,
    passage_exists_in_current_document,
    resolve_canonical_submission,
    resolve_submission_for_proposals,
    validate_create_payload,
    validate_proposal_scope_for_submission,
)


def _normalize_email(raw: str | None) -> str:
    return (raw or '').strip().lower()


def _resolve_author_user_id(*, author_user_id: str | None, author_email: str | None) -> Tuple[Optional[str], Optional[str]]:
    email = _normalize_email(author_email)
    if not author_user_id or not email:
        return None, 'author_user_id and author_email are required'
    user = User.query.get(author_user_id)
    if not user:
        return None, 'author_user_id not found'
    if _normalize_email(user.email) != email:
        return None, 'author identity mismatch'
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

    from services.product_rollout import is_feature_enabled
    if not is_feature_enabled('patches'):
        return {'error': 'Patches are not enabled.', 'error_code': 'FEATURE_DISABLED'}, 403

    uid, author_err = _resolve_author_user_id(
        author_user_id=author_user_id,
        author_email=author_email,
    )
    if author_err:
        return {'error': author_err}, 400

    if not isinstance(payload, dict):
        return {'error': 'payload must be an object'}, 400
    payload = dict(payload)
    payload.setdefault('scope', expected_proposal_scope(submission))
    normalized, val_err = validate_create_payload(payload)
    if val_err:
        return {'error': val_err}, 400
    scope_err = validate_proposal_scope_for_submission(submission, normalized['scope'])
    if scope_err:
        return {'error': scope_err}, 400
    if not passage_exists_in_current_document(submission, normalized['original_text']):
        return {
            'error': 'Selected passage was not found in the current document.',
            'error_code': 'PASSAGE_NOT_FOUND',
        }, 400

    row = create_dp_proposal(
        submission,
        author_user_id=uid,
        original_text=normalized['original_text'],
        proposed_text=normalized['proposed_text'],
        context_anchor=normalized.get('context_anchor'),
        scope=normalized['scope'],
        rationale=normalized.get('rationale'),
        reference_url=normalized.get('reference_url'),
        source_channel='canopi',
        external_id=ext,
        canopi_overlay_id=(canopi_overlay_id or None),
    )
    db.session.flush()
    row.contribution_registry_id = contribution_registry_id('canopi', ext)
    from services.events import emit_event
    emit_event(
        'dp_proposal_submitted',
        actor_type='canopi',
        actor_id=uid,
        subject_type='dp_proposal',
        subject_id=row.id,
        layer_id=submission.layer_id,
        payload={
            'source_channel': 'canopi',
            'external_id': ext,
            'submission_id': submission.id,
            'proposal_id': row.id,
        },
    )
    _enqueue_patch_pipeline(row, 'submitted')
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = _find_existing_canopi_patch(ext)
        if existing:
            return {
                'proposal': existing.to_dict(),
                'status_label': existing.status_label(),
                'contribution_registry_id': existing.contribution_registry_id,
                'idempotent': True,
            }, 200
        raise
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

    from services.product_rollout import is_feature_enabled
    if not is_feature_enabled('patches'):
        return {'error': 'Patches are not enabled.', 'error_code': 'FEATURE_DISABLED'}, 403

    uid, author_err = _resolve_author_user_id(
        author_user_id=author_user_id,
        author_email=author_email,
    )
    if author_err:
        return {'error': author_err}, 400

    if not isinstance(payload, dict):
        return {'error': 'payload must be an object'}, 400
    body = dict(payload)
    body.setdefault('comment_scope', body.get('comment_scope') or 'document')
    if body.get('parent_id'):
        return {'error': 'Canopi comments may not set parent_id'}, 400
    validated, val_err = validate_comment_payload(body, require_passage=False)
    if val_err:
        return {'error': val_err}, 400
    if (
        validated['comment_scope'] == 'passage'
        and not passage_exists_in_current_document(submission, validated['original_text'])
    ):
        return {
            'error': 'Selected passage was not found in the current document.',
            'error_code': 'PASSAGE_NOT_FOUND',
        }, 400

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
    row.contribution_registry_id = contribution_registry_id('canopi', ext)
    from services.events import emit_event
    emit_event(
        'reader_comment_created',
        actor_type='canopi',
        actor_id=uid,
        subject_type='comment',
        subject_id=row.id,
        layer_id=submission.layer_id,
        payload={
            'source_channel': 'canopi',
            'external_id': ext,
            'submission_id': submission.id,
            'comment_id': row.id,
        },
    )
    _enqueue_comment_pipeline(row, submission, 'submitted')
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing = _find_existing_canopi_comment(ext)
        if existing:
            from services.document_reader_comments import _comment_to_dict
            from services.identity import get_current_user
            return {
                'comment': _comment_to_dict(existing, current_user=get_current_user()),
                'contribution_registry_id': existing.contribution_registry_id,
                'idempotent': True,
            }, 200
        raise

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
    if 'payload' not in body or not isinstance(body.get('payload'), dict):
        return {'error': 'payload object required'}, 400
    payload = body['payload']

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
