"""Workgroup leadership and permission helpers."""
from __future__ import annotations

from typing import Optional

from extensions import db
from models import Layer, Workgroup, WorkingGroupChair, WorkingGroupMember
from config import DP_ADMIN_EMAILS
from services.coordination import is_layer_admin
from services.workgroup_links import is_dp_workgroup
from services.workgroup_positions import NOMINATION_STATUS_APPROVED

WORKGROUP_LEAD_POSITION = 'chair'
WORKGROUP_CO_LEAD_POSITION = 'co_lead'
WORKGROUP_LEADERSHIP_POSITIONS = frozenset({
    WORKGROUP_LEAD_POSITION,
    WORKGROUP_CO_LEAD_POSITION,
})


def _user_id(user_or_id) -> Optional[str]:
    if isinstance(user_or_id, str):
        return user_or_id
    if isinstance(user_or_id, dict):
        return user_or_id.get('id')
    return getattr(user_or_id, 'id', None)


def is_site_moderation_staff(user: Optional[dict]) -> bool:
    return bool(user and user.get('role') in ('admin', 'editor'))


def is_dp_site_admin(user: Optional[dict]) -> bool:
    """True when the signed-in user's email is a Desirable Properties site admin."""
    if not user:
        return False
    email = (user.get('email') or '').strip().lower()
    if not email:
        return False
    return email in DP_ADMIN_EMAILS


def is_workgroup_member(group_acronym: str, user_or_id) -> bool:
    uid = _user_id(user_or_id)
    if not group_acronym or not uid:
        return False
    return WorkingGroupMember.query.filter_by(
        group_acronym=group_acronym,
        user_id=uid,
    ).first() is not None


def user_has_approved_workgroup_position(
    workgroup: Optional[Workgroup],
    user_or_id,
    *,
    positions=WORKGROUP_LEADERSHIP_POSITIONS,
) -> bool:
    uid = _user_id(user_or_id)
    if not workgroup or not workgroup.acronym or not uid:
        return False
    return WorkingGroupChair.query.filter(
        WorkingGroupChair.group_acronym == workgroup.acronym,
        WorkingGroupChair.user_id == uid,
        WorkingGroupChair.position_key.in_(list(positions)),
        db.or_(
            WorkingGroupChair.status == NOMINATION_STATUS_APPROVED,
            WorkingGroupChair.approved.is_(True),
        ),
    ).first() is not None


def is_workgroup_leadership(workgroup: Optional[Workgroup], user_or_id) -> bool:
    uid = _user_id(user_or_id)
    if not workgroup or not uid:
        return False
    if workgroup.coordinator_id == uid:
        return True
    return user_has_approved_workgroup_position(workgroup, uid)


def user_is_dp_coordinator(user_or_id) -> bool:
    """True when the user holds an approved coordinator role on any DP workgroup."""
    uid = _user_id(user_or_id)
    if not uid:
        return False
    from services.workgroup_links import is_dp_workgroup

    rows = (
        Workgroup.query.filter(Workgroup.approval_status == 'approved')
        .all()
    )
    for workgroup in rows:
        if not is_dp_workgroup(workgroup):
            continue
        if is_workgroup_leadership(workgroup, uid):
            return True
    return False


def can_manage_workgroup(workgroup: Optional[Workgroup], user: Optional[dict]) -> bool:
    if not workgroup or not user:
        return False
    if is_site_moderation_staff(user):
        return True
    project = Layer.query.get(workgroup.layer_id) if workgroup.layer_id else None
    if project and is_layer_admin(project, user):
        return True
    return is_workgroup_leadership(workgroup, user)


def can_invite_workgroup_member(workgroup: Optional[Workgroup], user: Optional[dict]) -> bool:
    """Any active member, layer admins, site staff, and DP site admins can recruit members."""
    if not workgroup or not user:
        return False
    if can_manage_workgroup(workgroup, user):
        return True
    if is_dp_site_admin(user) and is_dp_workgroup(workgroup):
        return True
    return is_workgroup_member(workgroup.acronym, user)
