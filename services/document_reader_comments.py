"""Threaded comments on approved document read pages (document-wide and passage-anchored)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from extensions import db
from models import Comment, Submission, User
from services.dp_proposals import resolve_canonical_submission
from sqlalchemy import or_

from services.dp_proposals import (
    align_context_anchor_to_original,
    compute_anchor_hash,
    normalize_proposal_text,
    resolve_submission_for_proposals,
    serialize_context_anchor,
    submission_draft_ref,
)
from models.db_types import comment_is_deleted
from services.submissions import get_submission_by_ref

COMMENT_EDIT_WINDOW_MINUTES = 15


def _author_display(user: User) -> str:
    return (user.displayName or user.name or user.username or 'User').strip()


def _comment_owned_by_user(comment: Comment, current_user: Optional[dict]) -> bool:
    if not current_user:
        return False
    uid = current_user.get('id')
    if comment.author_user_id and uid and comment.author_user_id == uid:
        return True
    author_name = (current_user.get('name') or '').strip()
    return bool(author_name and comment.author == author_name)


def comment_edit_permissions(comment: Comment, current_user: Optional[dict]) -> dict:
    """Whether the current user may edit/delete within the time window."""
    window = COMMENT_EDIT_WINDOW_MINUTES
    base = {
        'can_edit': False,
        'can_delete': False,
        'edit_window_minutes': window,
        'minutes_remaining': 0,
    }
    if not current_user or comment_is_deleted(comment.is_deleted):
        return base
    if not _comment_owned_by_user(comment, current_user):
        return base
    if not comment.timestamp:
        return base
    elapsed = datetime.utcnow() - comment.timestamp
    remaining = window - int(elapsed.total_seconds() // 60)
    allowed = elapsed <= timedelta(minutes=window)
    return {
        'can_edit': allowed,
        'can_delete': allowed,
        'edit_window_minutes': window,
        'minutes_remaining': max(0, remaining),
    }


def _comment_to_dict(
    c: Comment,
    *,
    children: Optional[List[dict]] = None,
    current_user: Optional[dict] = None,
) -> dict:
    author_name = c.author
    if c.author_user_id:
        u = User.query.get(c.author_user_id)
        if u:
            author_name = _author_display(u)
    original = (c.original_text or c.passage_excerpt or '').strip()
    if original.endswith('…'):
        original = original[:-1].strip()
    perms = comment_edit_permissions(c, current_user)
    return {
        'id': c.id,
        'submission_id': c.submission_id,
        'draft_name': c.draft_name,
        'comment_scope': getattr(c, 'comment_scope', None) or 'document',
        'anchor_hash': c.anchor_hash,
        'context_anchor': _parse_anchor(c.context_anchor),
        'original_text': original or None,
        'passage_excerpt': c.passage_excerpt,
        'text': c.text,
        'author': author_name,
        'author_user_id': c.author_user_id,
        'parent_id': c.parent_id,
        'timestamp': c.timestamp.isoformat() if c.timestamp else None,
        'is_deleted': bool(comment_is_deleted(c.is_deleted)),
        'edited_at': c.edited_at.isoformat() if c.edited_at else None,
        'replies': children or [],
        **perms,
    }


def comment_query_for_draft_ref(draft_ref: str):
    """Comments for a document whether the URL uses ml_number, draft_name, or id."""
    ref = (draft_ref or '').strip()
    submission = get_submission_by_ref(ref) if ref else None
    if submission:
        keys = {ref}
        submission_ids = set()
        for sub in (submission, resolve_canonical_submission(submission)):
            if not sub:
                continue
            submission_ids.add(sub.id)
            for attr in ('id', 'draft_name', 'ml_number'):
                val = getattr(sub, attr, None)
                if val:
                    keys.add(str(val).strip())
        ml = (submission.ml_number or '').strip()
        if ml:
            for sibling in Submission.query.filter_by(ml_number=ml).all():
                submission_ids.add(sibling.id)
                if sibling.draft_name:
                    keys.add(str(sibling.draft_name).strip())
                keys.add(ml)
        return Comment.query.filter(
            Comment.is_deleted == False,  # noqa: E712
            or_(
                Comment.submission_id.in_(list(submission_ids)),
                Comment.draft_name.in_(list(keys)),
            ),
        )
    return Comment.query.filter(
        Comment.is_deleted == False,  # noqa: E712
        Comment.draft_name == ref,
    )


def count_comments_for_draft_ref(draft_ref: str) -> int:
    return comment_query_for_draft_ref(draft_ref).count()


def _parse_anchor(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def list_reader_comments_for_draft_ref(
    draft_ref: str,
    *,
    current_user: Optional[dict] = None,
) -> List[dict]:
    rows = comment_query_for_draft_ref(draft_ref).order_by(Comment.timestamp.asc()).all()
    by_id = {r.id: _comment_to_dict(r, current_user=current_user) for r in rows}
    roots: List[dict] = []
    for row in rows:
        node = by_id[row.id]
        if row.parent_id and row.parent_id in by_id:
            by_id[row.parent_id]['replies'].append(node)
        else:
            roots.append(node)
    return roots


def validate_comment_payload(data: Any, *, require_passage: bool) -> Tuple[Optional[dict], Optional[str]]:
    if not isinstance(data, dict):
        return None, 'JSON body required'
    text = (data.get('text') or '').strip()
    if not text:
        return None, 'Comment text is required'
    if len(text) > 8000:
        return None, 'Comment is too long (max 8000 characters)'
    scope = (data.get('comment_scope') or 'document').strip().lower()
    if scope not in ('document', 'passage'):
        return None, 'comment_scope must be document or passage'
    parent_id = (data.get('parent_id') or '').strip() or None
    original = normalize_proposal_text(data.get('original_text') or data.get('passage_text') or '')
    if scope == 'passage' or require_passage:
        if not original:
            return None, 'Select passage text before posting a passage comment'
        scope = 'passage'
    context_anchor = align_context_anchor_to_original(data.get('context_anchor'), original)
    if context_anchor is not None and not isinstance(context_anchor, (dict, str)):
        return None, 'context_anchor must be a JSON object'
    return {
        'text': text,
        'comment_scope': scope,
        'parent_id': parent_id,
        'original_text': original,
        'context_anchor': context_anchor,
    }, None


def create_reader_comment(
    submission: Submission,
    *,
    author_user_id: str,
    payload: dict,
    source_channel: str = 'gov-hub',
) -> Tuple[Comment, Optional[str]]:
    user = User.query.get(author_user_id)
    if not user:
        return None, 'User not found'  # type: ignore[return-value]

    if payload.get('parent_id'):
        parent = Comment.query.filter_by(
            id=payload['parent_id'],
            submission_id=submission.id,
            is_deleted=False,
        ).first()
        if not parent:
            return None, 'Parent comment not found'  # type: ignore[return-value]

    scope = payload['comment_scope']
    anchor_hash = None
    serialized_anchor = None
    excerpt = None
    if scope == 'passage':
        original = payload['original_text']
        excerpt = original[:500] + ('…' if len(original) > 500 else '')
        anchor_hash = compute_anchor_hash(
            submission.id,
            submission.content_hash,
            original,
        )
        serialized_anchor = serialize_context_anchor(payload.get('context_anchor'))

    draft_name = submission_draft_ref(submission) or submission.draft_name or submission.id
    comment_id = str(uuid4())
    source_channel = source_channel or 'gov-hub'
    try:
        from services.contribution_pipeline import contribution_registry_id
        registry_id = contribution_registry_id(source_channel, comment_id)
    except Exception:
        registry_id = f'dp-contrib:{source_channel}:{comment_id}'

    row = Comment(
        id=comment_id,
        draft_name=draft_name,
        submission_id=submission.id,
        comment_scope=scope,
        anchor_hash=anchor_hash,
        context_anchor=serialized_anchor,
        passage_excerpt=excerpt,
        original_text=original if scope == 'passage' else None,
        text=payload['text'],
        author=_author_display(user),
        author_user_id=user.id,
        parent_id=payload.get('parent_id'),
        timestamp=datetime.utcnow(),
        is_deleted=False,
        source_channel=source_channel,
        contribution_registry_id=registry_id,
    )
    db.session.add(row)
    return row, None


def _enqueue_comment_pipeline(comment: Comment, submission: Submission, event_type: str = 'submitted') -> None:
    """Best-effort Scout queue write — never block comment create."""
    try:
        from services.contribution_pipeline import (
            enqueue_contribution_pipeline_event,
            pipeline_payload_for_comment,
        )

        enqueue_contribution_pipeline_event(
            subject_type='comment',
            subject_id=comment.id,
            event_type=event_type,
            source_channel=getattr(comment, 'source_channel', None) or 'gov-hub',
            payload=pipeline_payload_for_comment(comment, submission),
        )
    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.warning(
                '[ContributionPipeline] Failed to enqueue %s for comment %s: %s',
                event_type,
                getattr(comment, 'id', None),
                e,
            )
        except RuntimeError:
            pass


def create_reader_comment_for_draft(
    draft_ref: str,
    *,
    author_user_id: str,
    body: dict,
    source_channel: str = 'gov-hub',
    enqueue_pipeline: bool = True,
) -> Tuple[dict, int]:
    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return {'error': err}, 404 if err == 'Document not found' else 400
    if submission.status != 'approved':
        return {'error': 'Comments are only available on approved documents'}, 400
    submission = resolve_canonical_submission(submission) or submission

    payload, val_err = validate_comment_payload(body, require_passage=False)
    if val_err:
        return {'error': val_err}, 400

    row, create_err = create_reader_comment(
        submission,
        author_user_id=author_user_id,
        payload=payload,
        source_channel=source_channel,
    )
    if create_err:
        return {'error': create_err}, 400
    if enqueue_pipeline:
        _enqueue_comment_pipeline(row, submission, 'submitted')
    db.session.commit()
    from services.identity import get_current_user

    cu = get_current_user()
    return {'comment': _comment_to_dict(row, current_user=cu)}, 201


def update_reader_comment(
    draft_ref: str,
    comment_id: str,
    *,
    author_user_id: str,
    text: str,
) -> Tuple[dict, int]:
    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return {'error': err}, 404 if err == 'Document not found' else 400
    comment = Comment.query.filter_by(id=comment_id).first()
    if not comment or not comment_query_for_draft_ref(draft_ref).filter(
        Comment.id == comment_id
    ).first():
        return {'error': 'Comment not found'}, 404
    user = {'id': author_user_id}
    urow = User.query.get(author_user_id)
    if urow:
        user['name'] = _author_display(urow)
    perms = comment_edit_permissions(comment, user)
    if not perms['can_edit']:
        return {'error': f'Comments can only be edited within {COMMENT_EDIT_WINDOW_MINUTES} minutes by their author'}, 403
    body = (text or '').strip()
    if not body:
        return {'error': 'Comment text is required'}, 400
    if len(body) > 8000:
        return {'error': 'Comment is too long (max 8000 characters)'}, 400
    if not comment.original_text:
        comment.original_text = comment.text
    comment.text = body
    comment.edited_at = datetime.utcnow()
    db.session.commit()
    from services.identity import get_current_user

    return {'comment': _comment_to_dict(comment, current_user=get_current_user())}, 200


def delete_reader_comment(
    draft_ref: str,
    comment_id: str,
    *,
    author_user_id: str,
) -> Tuple[dict, int]:
    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return {'error': err}, 404 if err == 'Document not found' else 400
    comment = Comment.query.filter_by(id=comment_id).first()
    if not comment or not comment_query_for_draft_ref(draft_ref).filter(
        Comment.id == comment_id
    ).first():
        return {'error': 'Comment not found'}, 404
    user = {'id': author_user_id}
    urow = User.query.get(author_user_id)
    if urow:
        user['name'] = _author_display(urow)
    perms = comment_edit_permissions(comment, user)
    if not perms['can_delete']:
        return {'error': f'Comments can only be deleted within {COMMENT_EDIT_WINDOW_MINUTES} minutes by their author'}, 403
    comment.is_deleted = True
    comment.text = '[Deleted]'
    db.session.commit()
    return {'ok': True}, 200


def list_reader_comments_for_draft(
    draft_ref: str,
    *,
    current_user: Optional[dict] = None,
) -> Tuple[dict, int]:
    submission, err = resolve_submission_for_proposals(draft_ref)
    if err:
        return {'error': err}, 404 if err == 'Document not found' else 400
    if submission.status != 'approved':
        return {'error': 'Comments are only available on approved documents'}, 400
    canonical = resolve_canonical_submission(submission) or submission
    if current_user is None:
        from services.identity import get_current_user

        current_user = get_current_user()
    return {
        'submission_id': canonical.id,
        'draft_ref': draft_ref,
        'edit_window_minutes': COMMENT_EDIT_WINDOW_MINUTES,
        'comments': list_reader_comments_for_draft_ref(draft_ref, current_user=current_user),
    }, 200
