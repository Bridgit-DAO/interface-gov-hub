"""Shared workgroup membership join/request behavior."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Tuple
from uuid import uuid4

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from extensions import db
from models import (
    PlatformInvitation,
    User,
    Workgroup,
    WorkingGroupChair,
    WorkingGroupMember,
    WorkgroupMemberRequest,
)
from services.workgroup_authority import is_workgroup_member


def workgroup_membership_event_payload(workgroup: Workgroup, user: User) -> dict:
    """Canonical payload for workgroup_member_joined / workgroup_member_left."""
    display_name = (
        (getattr(user, 'displayName', None) or '')
        or (getattr(user, 'username', None) or '')
        or (getattr(user, 'email', None) or '')
    ).strip() or None
    slug = (workgroup.slug or workgroup.acronym or '').strip()
    return {
        'workgroup_id': workgroup.id,
        'slug': slug,
        'name': workgroup.name,
        'acronym': workgroup.acronym,
        # Aliases used by existing challenge-site activity formatters.
        'workgroup_slug': slug,
        'workgroup_name': workgroup.name,
        'user_id': user.id,
        'display_name': display_name,
    }


def emit_workgroup_membership_event(
    event_type: str,
    *,
    workgroup: Workgroup,
    user: User,
) -> None:
    from services.events import emit_event

    emit_event(
        event_type,
        actor_type='user',
        actor_id=user.id,
        subject_type='workgroup',
        subject_id=workgroup.id,
        layer_id=workgroup.layer_id,
        payload=workgroup_membership_event_payload(workgroup, user),
    )


def _workgroup_for_acronym(acronym: str) -> Optional[Workgroup]:
    if not acronym:
        return None
    return Workgroup.query.filter_by(acronym=acronym).first()


def find_workgroup_membership(acronym: str, user_id: str) -> Optional[WorkingGroupMember]:
    if not acronym or not user_id:
        return None
    return WorkingGroupMember.query.filter_by(
        group_acronym=acronym,
        user_id=user_id,
    ).first()


def ensure_workgroup_membership(
    *,
    acronym: str,
    user_id: str,
    display_name: str = '',
) -> Tuple[Optional[WorkingGroupMember], bool]:
    """Idempotently ensure a membership row exists. Returns (row, created).

    Losing the race against a concurrent join must not abort the caller's
    transaction, because callers commit the membership together with the welcome
    notification. The insert therefore lets the database absorb a
    ``uq_wgm_group_user`` conflict (``ON CONFLICT DO NOTHING``) instead of
    raising, and the winning row is re-read and returned. A SAVEPOINT is
    deliberately not used: pysqlite releases a savepoint by committing the
    surrounding transaction, which would publish a membership before its
    welcome notification exists.
    """
    if not acronym or not user_id:
        return None, False

    existing = find_workgroup_membership(acronym, user_id)
    if existing:
        return existing, False

    # No conflict target: the statement then absorbs any uniqueness violation,
    # so it behaves identically on a database that has not yet applied
    # migrate_workgroup_member_unique_v1. NOT NULL/foreign-key problems still
    # raise, and the re-read below catches an insert that did nothing.
    statement = sqlite_insert(WorkingGroupMember).values(
        id=str(uuid4()),
        group_acronym=acronym,
        user_id=user_id,
        user_name=display_name or '',
        joined_at=datetime.utcnow(),
    ).on_conflict_do_nothing()
    created = db.session.execute(statement).rowcount == 1

    member = find_workgroup_membership(acronym, user_id)
    if member is None:
        # The insert was absorbed but no row is visible: the state is not what
        # the caller asked for, so fail loudly instead of reporting success.
        raise RuntimeError(
            f'Membership for {user_id} in {acronym} could not be created or found'
        )
    return member, created


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

    _member, created = ensure_workgroup_membership(
        acronym=acronym,
        user_id=user.id,
        display_name=display_name,
    )
    if not created:
        return {'ok': True, 'duplicate': True, 'status': 'already_member'}

    workgroup = _workgroup_for_acronym(acronym)
    if workgroup:
        emit_workgroup_membership_event(
            'workgroup_member_joined',
            workgroup=workgroup,
            user=user,
        )
    return {'ok': True, 'joined': True, 'status': 'joined'}


def leave_workgroup_membership(
    *,
    workgroup: Workgroup,
    user: User,
) -> dict[str, Any]:
    """Remove membership and cancel any pending join request. Caller commits.

    Returns a result dict with ok/error and status_code for HTTP mapping.
    Emits ``workgroup_member_left`` when a membership row is removed.
    """
    if not workgroup or not getattr(workgroup, 'acronym', None):
        return {'ok': False, 'error': 'Invalid workgroup', 'status_code': 400}
    if not user or not user.id:
        return {'ok': False, 'error': 'User not found', 'status_code': 404}

    acronym = workgroup.acronym
    membership = find_workgroup_membership(acronym, user.id)
    pending = WorkgroupMemberRequest.query.filter_by(
        group_acronym=acronym,
        user_id=user.id,
        status='pending',
    ).first()

    if not membership and not pending:
        return {
            'ok': False,
            'error': 'Not a member of this workgroup',
            'status_code': 404,
        }

    left = False
    cancelled_request = False

    if membership:
        db.session.delete(membership)
        left = True

    if pending:
        pending.status = 'cancelled'
        pending.reviewed_at = datetime.utcnow()
        reviewer = (
            (getattr(user, 'displayName', None) or '')
            or (getattr(user, 'username', None) or '')
            or 'self'
        )
        pending.reviewed_by = reviewer[:100]
        cancelled_request = True

    db.session.flush()

    if left:
        from services.dp_welcome import (
            invalidate_dp_welcomes_for_workgroup,
            stale_member_welcome_variants,
        )

        stale = stale_member_welcome_variants(user_id=user.id, workgroup=workgroup)
        if stale:
            invalidate_dp_welcomes_for_workgroup(
                user_id=user.id,
                workgroup=workgroup,
                variants=stale,
            )
        emit_workgroup_membership_event(
            'workgroup_member_left',
            workgroup=workgroup,
            user=user,
        )

    return {
        'ok': True,
        'left': left,
        'cancelled_request': cancelled_request,
        'status': 'left' if left else 'request_cancelled',
    }


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
