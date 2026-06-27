"""Workgroup leadership and permission helpers."""
from __future__ import annotations

from typing import Optional

from extensions import db
from models import Layer, Workgroup, WorkingGroupChair, WorkingGroupMember
from services.coordination import is_layer_admin
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
    """Leads/co-leads, layer admins, and site staff can recruit members."""
    return can_manage_workgroup(workgroup, user)
