"""Shared workgroup membership join/request behavior."""
from __future__ import annotations

from typing import Optional
from uuid import uuid4

from extensions import db
from models import (
    PlatformInvitation,
    User,
    WorkingGroupChair,
    WorkingGroupMember,
    WorkgroupMemberRequest,
)
from services.workgroup_authority import is_workgroup_member


def workgroup_requires_member_approval(acronym: str) -> bool:
    """Static group config controls member approval today; DB workgroups default open."""
    from services.groups import load_group_data

    for group in load_group_data():
        if group.get('acronym') == acronym:
            return bool(group.get('members_require_approval'))
    return False


def join_or_request_workgroup_membership(
    *,
    acronym: str,
    user: User,
    invited_by_user_id: Optional[str] = None,
    invitation: Optional[PlatformInvitation] = None,
    require_approval: Optional[bool] = None,
) -> dict:
    """Create membership or a pending member request; idempotent for pending requests."""
    if not acronym:
        return {'ok': False, 'error': 'Invalid workgroup'}
    if not user or not user.id:
        return {'ok': False, 'error': 'User not found'}

    if is_workgroup_member(acronym, user.id):
        return {'ok': True, 'duplicate': True, 'status': 'already_member'}

    needs_approval = (
        workgroup_requires_member_approval(acronym)
        if require_approval is None
        else bool(require_approval)
    )
    display_name = user.displayName or user.username or user.email or ''

    if needs_approval:
        pending = WorkgroupMemberRequest.query.filter_by(
            group_acronym=acronym,
            user_id=user.id,
            status='pending',
        ).first()
        if pending:
            if invited_by_user_id and not pending.invited_by_user_id:
                pending.invited_by_user_id = invited_by_user_id
            if invitation and not pending.platform_invitation_id:
                pending.platform_invitation_id = invitation.id
            db.session.flush()
            return {'ok': True, 'pending_approval': True, 'status': 'already_pending'}

        db.session.add(WorkgroupMemberRequest(
            group_acronym=acronym,
            user_id=user.id,
            user_name=display_name,
            status='pending',
            invited_by_user_id=invited_by_user_id,
            platform_invitation_id=invitation.id if invitation else None,
        ))
        db.session.flush()
        return {'ok': True, 'pending_approval': True, 'status': 'requested'}

    db.session.add(WorkingGroupMember(
        id=str(uuid4()),
        group_acronym=acronym,
        user_id=user.id,
        user_name=display_name,
    ))
    db.session.flush()
    return {'ok': True, 'joined': True, 'status': 'joined'}


def user_workgroup_status(user_id: Optional[str], acronym: str) -> dict:
    """One user's membership, held positions, and join/nominate affordances for a workgroup.

    Consolidates the member/position/pending-request checks that were
    otherwise re-derived independently in the workgroup page's client JS,
    the launch-action checker, and the people directory.
    """
    from services.workgroup_positions import WORKGROUP_POSITIONS

    if not acronym or not user_id:
        return {
            'member': False,
            'positions': [],
            'pending_request': False,
            'can_join': False,
            'can_self_nominate': False,
        }

    positions = [
        row.position_key or 'chair'
        for row in WorkingGroupChair.query.filter_by(
            group_acronym=acronym,
            user_id=user_id,
        ).all()
    ]
    is_member = bool(positions) or is_workgroup_member(acronym, user_id)

    pending_request = WorkgroupMemberRequest.query.filter_by(
        group_acronym=acronym,
        user_id=user_id,
        status='pending',
    ).first() is not None

    return {
        'member': is_member,
        'positions': sorted(set(positions)),
        'pending_request': pending_request,
        'can_join': not is_member and not pending_request,
        'can_self_nominate': len(set(positions)) < len(WORKGROUP_POSITIONS),
    }
