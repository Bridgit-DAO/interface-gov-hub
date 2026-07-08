"""Batch action-status checks for Metaweb Book Gov Hub blueberry observer (Phase 6a)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import or_

from models import (
    Layer,
    LayerMember,
    Submission,
    User,
    Waitlist,
    WaitlistEntry,
    Workgroup,
    WorkingGroupChair,
    WorkingGroupMember,
    WorkgroupMemberRequest,
)
from services.submission_notifications import submitter_user_id as resolve_submitter_from_name

GOVHUB_USER_ID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.I,
)

LAUNCH_ACTION_KINDS = frozenset({
    'workgroup_join',
    'workgroup_nominate_self',
    'workgroup_nominate_other',
    'draft_submit',
    'layer_join',
    'waitlist_join',
})


def _iso_z(value: Optional[datetime]) -> Optional[str]:
    if not value:
        return None
    text = value.isoformat()
    if text.endswith('Z') or '+' in text:
        return text
    return f'{text}Z'


def resolve_govhub_user(
    *,
    govhub_user_id: Optional[str] = None,
    web3auth_verifier_id: Optional[str] = None,
) -> Optional[User]:
    uid = (govhub_user_id or '').strip()
    if GOVHUB_USER_ID_RE.match(uid):
        return User.query.get(uid)
    vid = (web3auth_verifier_id or '').strip()
    if vid:
        return User.query.filter_by(web3authVerifierId=vid).first()
    return None


def _incomplete() -> Dict[str, Any]:
    return {'complete': False, 'completedAt': None, 'evidence': None}


def _complete(completed_at: Optional[datetime], evidence: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'complete': True,
        'completedAt': _iso_z(completed_at),
        'evidence': evidence,
    }


def _resolve_layer(*, layer_id: Optional[str] = None, layer_slug: Optional[str] = None) -> Optional[Layer]:
    lid = (layer_id or '').strip()
    if lid:
        layer = Layer.query.get(lid)
        if layer:
            return layer
    slug = (layer_slug or '').strip()
    if slug:
        return Layer.query.filter_by(slug=slug).first()
    return None


def _resolve_workgroup_acronym(check: dict) -> Optional[str]:
    acronyms = _resolve_workgroup_acronyms(check)
    return acronyms[0] if acronyms else None


def _resolve_workgroup_acronyms(check: dict) -> List[str]:
    """Resolve one or more workgroup acronyms from multi- or legacy single-target checks."""
    acronyms: List[str] = []

    raw_acronyms = check.get('groupAcronyms')
    if isinstance(raw_acronyms, list):
        for raw in raw_acronyms:
            acronym = str(raw or '').strip()
            if acronym:
                acronyms.append(acronym)

    raw_workgroups = check.get('workgroups')
    if isinstance(raw_workgroups, list):
        for row in raw_workgroups:
            if not isinstance(row, dict):
                continue
            acronym = str(row.get('groupAcronym') or '').strip()
            if acronym:
                acronyms.append(acronym)
                continue
            wg_id = str(row.get('workgroupId') or '').strip()
            if wg_id:
                wg = Workgroup.query.get(wg_id)
                if wg and wg.acronym:
                    acronyms.append(wg.acronym)

    wg_id = (check.get('workgroupId') or '').strip()
    if wg_id:
        wg = Workgroup.query.get(wg_id)
        if wg and wg.acronym:
            acronyms.append(wg.acronym)
    slug = (check.get('workgroupSlug') or '').strip()
    if slug:
        wg = Workgroup.query.filter(
            or_(Workgroup.slug == slug, Workgroup.acronym == slug)
        ).first()
        if wg and wg.acronym:
            acronyms.append(wg.acronym)
    acronym = (check.get('groupAcronym') or '').strip()
    if acronym:
        acronyms.append(acronym)

    deduped: List[str] = []
    seen = set()
    for item in acronyms:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _check_workgroup_membership(user_id: str, acronym: str) -> Optional[Dict[str, Any]]:
    member = WorkingGroupMember.query.filter_by(group_acronym=acronym, user_id=user_id).first()
    if member:
        return _complete(
            member.joined_at,
            {
                'actionKind': 'workgroup_join',
                'groupAcronym': acronym,
                'joinedAt': _iso_z(member.joined_at),
            },
        )
    approved_req = (
        WorkgroupMemberRequest.query.filter_by(
            group_acronym=acronym,
            user_id=user_id,
            status='approved',
        )
        .order_by(WorkgroupMemberRequest.reviewed_at.desc())
        .first()
    )
    if approved_req:
        ts = approved_req.reviewed_at or approved_req.requested_at
        return _complete(
            ts,
            {
                'actionKind': 'workgroup_join',
                'groupAcronym': acronym,
                'joinedAt': _iso_z(ts),
                'via': 'approved_request',
            },
        )
    return None


def _check_workgroup_nomination(
    user_id: str,
    acronym: str,
    *,
    self_nomination: bool,
    position_key: str,
) -> Optional[Dict[str, Any]]:
    row = (
        WorkingGroupChair.query.filter_by(
            group_acronym=acronym,
            nominated_by_user_id=user_id,
            is_self_nomination=self_nomination,
            position_key=position_key,
        )
        .order_by(WorkingGroupChair.set_at.desc())
        .first()
    )
    if not row:
        return None
    kind = 'workgroup_nominate_self' if self_nomination else 'workgroup_nominate_other'
    return _complete(
        row.set_at,
        {
            'actionKind': kind,
            'groupAcronym': acronym,
            'positionKey': position_key,
            'nominatedAt': _iso_z(row.set_at),
        },
    )


def check_layer_join(user_id: str, check: dict) -> Dict[str, Any]:
    layer = _resolve_layer(layer_id=check.get('layerId'), layer_slug=check.get('layerSlug'))
    if not layer:
        return _incomplete()
    member = (
        LayerMember.query.filter_by(layer_id=layer.id, user_id=user_id, status='active')
        .filter(LayerMember.left_at.is_(None))
        .first()
    )
    if not member:
        return _incomplete()
    return _complete(
        member.joined_at,
        {
            'actionKind': 'layer_join',
            'layerId': layer.id,
            'layerSlug': layer.slug,
            'joinedAt': _iso_z(member.joined_at),
        },
    )


def check_workgroup_join(user_id: str, check: dict) -> Dict[str, Any]:
    acronyms = _resolve_workgroup_acronyms(check)
    if not acronyms:
        return _incomplete()
    for acronym in acronyms:
        result = _check_workgroup_membership(user_id, acronym)
        if result:
            return result
    return _incomplete()


def check_workgroup_nominate(user_id: str, check: dict, *, self_nomination: bool) -> Dict[str, Any]:
    acronyms = _resolve_workgroup_acronyms(check)
    if not acronyms:
        return _incomplete()
    position_key = (check.get('positionKey') or 'chair').strip() or 'chair'
    for acronym in acronyms:
        result = _check_workgroup_nomination(
            user_id,
            acronym,
            self_nomination=self_nomination,
            position_key=position_key,
        )
        if result:
            return result
    return _incomplete()


def check_waitlist_join(user_id: str, check: dict) -> Dict[str, Any]:
    waitlist_id = (check.get('waitlistId') or '').strip()
    if not waitlist_id:
        return _incomplete()
    waitlist = Waitlist.query.get(waitlist_id)
    if not waitlist:
        return _incomplete()
    layer_id = (check.get('layerId') or '').strip()
    layer_slug = (check.get('layerSlug') or '').strip()
    if layer_id or layer_slug:
        layer = _resolve_layer(layer_id=layer_id, layer_slug=layer_slug)
        if not layer or waitlist.layer_id != layer.id:
            return _incomplete()
    entry = (
        WaitlistEntry.query.filter_by(waitlist_id=waitlist_id, user_id=user_id)
        .filter(WaitlistEntry.left_at.is_(None))
        .first()
    )
    if not entry:
        return _incomplete()
    return _complete(
        entry.joined_at,
        {
            'actionKind': 'waitlist_join',
            'waitlistId': waitlist_id,
            'joinedAt': _iso_z(entry.joined_at),
        },
    )


def _submission_matches_user(submission: Submission, user_id: str) -> bool:
    submitter_uid = getattr(submission, 'submitter_user_id', None)
    if submitter_uid:
        return str(submitter_uid) == str(user_id)
    resolved = resolve_submitter_from_name(submission)
    return resolved == str(user_id)


def check_draft_submit(user_id: str, check: dict) -> Dict[str, Any]:
    layer = _resolve_layer(layer_id=check.get('layerId'), layer_slug=check.get('layerSlug'))
    if not layer:
        return _incomplete()
    draft_completion = (check.get('draftCompletion') or 'submitted').strip().lower()
    if draft_completion not in ('submitted', 'approved'):
        draft_completion = 'submitted'
    group = (check.get('group') or '').strip() or None
    min_doc_type = (check.get('minDocType') or '').strip() or None

    q = Submission.query.filter(Submission.layer_id == layer.id)
    if group:
        q = q.filter(Submission.group == group)
    if min_doc_type:
        q = q.filter(Submission.doc_type == min_doc_type)
    if draft_completion == 'approved':
        q = q.filter(Submission.status == 'approved')
    else:
        q = q.filter(Submission.status.in_(['submitted', 'inscription_pending']))

    for sub in q.order_by(Submission.submitted_at.desc()).all():
        if _submission_matches_user(sub, user_id):
            return _complete(
                sub.submitted_at,
                {
                    'actionKind': 'draft_submit',
                    'layerId': layer.id,
                    'layerSlug': layer.slug,
                    'group': sub.group,
                    'draftName': sub.draft_name,
                    'status': sub.status,
                    'submittedAt': _iso_z(sub.submitted_at),
                },
            )
    return _incomplete()


CHECKERS = {
    'layer_join': check_layer_join,
    'workgroup_join': check_workgroup_join,
    'workgroup_nominate_self': lambda uid, c: check_workgroup_nominate(uid, c, self_nomination=True),
    'workgroup_nominate_other': lambda uid, c: check_workgroup_nominate(uid, c, self_nomination=False),
    'waitlist_join': check_waitlist_join,
    'draft_submit': check_draft_submit,
}


def evaluate_action_checks(user: User, checks: List[dict]) -> Dict[str, dict]:
    """Evaluate up to 20 launch action checks for one Gov Hub user."""
    results: Dict[str, dict] = {}
    user_id = str(user.id)
    for raw in checks[:20]:
        if not isinstance(raw, dict):
            continue
        key = (raw.get('key') or '').strip()
        if not key:
            continue
        kind = (raw.get('actionKind') or '').strip()
        if kind not in LAUNCH_ACTION_KINDS:
            results[key] = _incomplete()
            continue
        checker = CHECKERS.get(kind)
        results[key] = checker(user_id, raw) if checker else _incomplete()
    return results
