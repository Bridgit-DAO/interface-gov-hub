"""DP Proposal business logic: permissions, anchors, validation, dashboard aggregates."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from extensions import db
from models import DpProposal, Submission, User, Workgroup, WorkingGroupChair
from services.coordination import is_layer_admin, is_site_moderation_staff
from services.submissions import get_submission_by_ref
from services.workgroup_links import extract_dp_number_from_title, is_dp_workgroup
from services.workgroup_positions import NOMINATION_STATUS_APPROVED

_NBSP_RE = re.compile('\u00a0')


def normalize_proposal_text(text: str) -> str:
    """Match Canopi normalizeForMatch baseline for anchor hashing."""
    if not text:
        return ''
    return _NBSP_RE.sub(' ', str(text)).replace('\r\n', '\n').strip()


def compute_anchor_hash(
    submission_id: str,
    content_hash: Optional[str],
    exact_text: str,
) -> str:
    norm = normalize_proposal_text(exact_text)
    payload = f'{submission_id}\0{content_hash or ""}\0{norm}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def is_dp_submission(submission: Optional[Submission]) -> bool:
    if not submission:
        return False
    group = (submission.group or '').strip()
    if group:
        wg = Workgroup.query.filter_by(acronym=group).first()
        if wg and is_dp_workgroup(wg):
            return True
    return extract_dp_number_from_title(submission.title or '') is not None


def workgroup_for_submission(submission: Submission) -> Optional[Workgroup]:
    group = (submission.group or '').strip()
    if group:
        wg = Workgroup.query.filter_by(acronym=group).first()
        if wg:
            return wg
    dp_num = extract_dp_number_from_title(submission.title or '')
    if dp_num is None:
        return None
    from services.groups import extract_dp_number

    for wg in Workgroup.query.all():
        if extract_dp_number(wg.acronym or '') == dp_num:
            return wg
    return None


def can_manage_amendments(user: Optional[dict], workgroup: Optional[Workgroup]) -> bool:
    """Chair/coordinator (and admins) may accept or decline DP Proposals."""
    if not user:
        return False
    if is_site_moderation_staff(user):
        return True
    if not workgroup:
        return False
    if workgroup.layer_id and workgroup.layer:
        if is_layer_admin(workgroup.layer, user):
            return True
    uid = user.get('id')
    if uid and workgroup.coordinator_id == uid:
        return True
    if not workgroup.acronym or not uid:
        return False
    approved_chair = WorkingGroupChair.query.filter(
        WorkingGroupChair.group_acronym == workgroup.acronym,
        WorkingGroupChair.position_key == 'chair',
        WorkingGroupChair.user_id == uid,
        db.or_(
            WorkingGroupChair.status == NOMINATION_STATUS_APPROVED,
            WorkingGroupChair.approved.is_(True),
        ),
    ).first()
    return approved_chair is not None


def require_dp_proposals_enabled() -> Optional[Tuple[dict, int]]:
    from flask import jsonify

    from services.product_rollout import is_feature_enabled

    if not is_feature_enabled('dp_proposals'):
        return jsonify({
            'error': 'DP Proposals are not enabled.',
            'error_code': 'FEATURE_DISABLED',
            'feature': 'dp_proposals',
        }), 403
    return None


def resolve_submission_for_proposals(draft_ref: str) -> Tuple[Optional[Submission], Optional[str]]:
    submission = get_submission_by_ref(draft_ref)
    if not submission:
        return None, 'Document not found'
    if (submission.status or '').lower() != 'approved':
        return None, 'Proposals are only allowed on approved documents'
    if not is_dp_submission(submission):
        return None, 'DP Proposals are only supported for Desirable Property documents'
    return submission, None


def validate_create_payload(data: Any) -> Tuple[Optional[dict], Optional[str]]:
    if not isinstance(data, dict):
        return None, 'JSON body required'
    original = normalize_proposal_text(data.get('original_text') or '')
    proposed = normalize_proposal_text(data.get('proposed_text') or '')
    if not original:
        return None, 'original_text is required'
    if not proposed:
        return None, 'proposed_text is required'
    if original == proposed:
        return None, 'proposed_text must differ from original_text'
    context_anchor = data.get('context_anchor')
    if context_anchor is not None and not isinstance(context_anchor, (dict, str)):
        return None, 'context_anchor must be a JSON object or string'
    scope = (data.get('scope') or 'dp').strip().lower()
    if scope not in ('dp', 'document'):
        return None, 'scope must be dp or document'
    return {
        'original_text': original,
        'proposed_text': proposed,
        'context_anchor': context_anchor,
        'scope': scope,
    }, None


def serialize_context_anchor(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, str):
        trimmed = raw.strip()
        if not trimmed:
            return None
        try:
            json.loads(trimmed)
        except json.JSONDecodeError:
            return None
        return trimmed
    if isinstance(raw, dict):
        return json.dumps(raw, sort_keys=True)
    return None


def list_proposals_for_submission(submission_id: str) -> List[DpProposal]:
    return (
        DpProposal.query.filter_by(submission_id=submission_id)
        .order_by(DpProposal.created_at.desc())
        .all()
    )


def proposal_counts(proposals: List[DpProposal]) -> Dict[str, Any]:
    by_status: Dict[str, int] = {}
    by_anchor: Dict[str, int] = {}
    for row in proposals:
        st = row.status or 'pending'
        by_status[st] = by_status.get(st, 0) + 1
        ah = row.anchor_hash or ''
        if ah:
            by_anchor[ah] = by_anchor.get(ah, 0) + 1
    return {
        'by_status': by_status,
        'by_anchor': by_anchor,
        'total': len(proposals),
    }


def create_dp_proposal(
    submission: Submission,
    *,
    author_user_id: str,
    original_text: str,
    proposed_text: str,
    context_anchor: Any = None,
    scope: str = 'dp',
) -> DpProposal:
    anchor_hash = compute_anchor_hash(
        submission.id,
        submission.content_hash,
        original_text,
    )
    row = DpProposal(
        submission_id=submission.id,
        scope=scope,
        status='pending',
        anchor_hash=anchor_hash,
        context_anchor=serialize_context_anchor(context_anchor),
        original_text=original_text,
        proposed_text=proposed_text,
        content_hash_at_create=submission.content_hash,
        author_user_id=author_user_id,
    )
    db.session.add(row)
    return row


def accept_proposal(proposal: DpProposal, reviewer_user_id: str) -> DpProposal:
    proposal.status = 'accepted'
    proposal.reviewed_by_user_id = reviewer_user_id
    proposal.reviewed_at = datetime.utcnow()
    return proposal


def decline_proposal(proposal: DpProposal, reviewer_user_id: str) -> DpProposal:
    proposal.status = 'declined'
    proposal.reviewed_by_user_id = reviewer_user_id
    proposal.reviewed_at = datetime.utcnow()
    return proposal


def dashboard_dp_activity(limit: int = 100) -> List[dict]:
    """Rows for /admin/dp-proposals/ sorted by recent activity (most active first)."""
    from sqlalchemy import case, func

    activity_expr = func.max(DpProposal.created_at)
    rows = (
        db.session.query(
            DpProposal.submission_id,
            func.count(DpProposal.id).label('total'),
            func.sum(case((DpProposal.status == 'pending', 1), else_=0)).label('pending'),
            func.sum(case((DpProposal.status == 'accepted', 1), else_=0)).label('accepted'),
            func.sum(case((DpProposal.status == 'declined', 1), else_=0)).label('declined'),
            func.sum(case((DpProposal.status == 'incorporated', 1), else_=0)).label('incorporated'),
            func.sum(case((DpProposal.status == 'orphaned', 1), else_=0)).label('orphaned'),
            activity_expr.label('last_activity'),
        )
        .group_by(DpProposal.submission_id)
        .order_by(activity_expr.desc())
        .limit(limit)
        .all()
    )
    out: List[dict] = []
    for row in rows:
        submission = Submission.query.get(row.submission_id)
        wg = workgroup_for_submission(submission) if submission else None
        out.append({
            'submission_id': row.submission_id,
            'title': submission.title if submission else None,
            'ml_number': submission.ml_number if submission else None,
            'workgroup_acronym': wg.acronym if wg else (submission.group if submission else None),
            'workgroup_name': wg.name if wg else None,
            'counts': {
                'total': int(row.total or 0),
                'pending': int(row.pending or 0),
                'accepted': int(row.accepted or 0),
                'declined': int(row.declined or 0),
                'incorporated': int(row.incorporated or 0),
                'orphaned': int(row.orphaned or 0),
            },
            'last_activity': row.last_activity.isoformat() if row.last_activity else None,
        })
    return out


def user_from_session(current_user: dict) -> Optional[User]:
    uid = current_user.get('id')
    if uid:
        return User.query.get(uid)
    username = current_user.get('username')
    if username:
        return User.query.filter_by(username=username).first()
    return None
