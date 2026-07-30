"""Shared workgroup membership join/request behavior."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple
from uuid import uuid4

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from extensions import db
from models import PlatformInvitation, User, WorkingGroupMember, WorkgroupMemberRequest
from services.workgroup_authority import is_workgroup_member


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
    return {'ok': True, 'joined': True, 'status': 'joined'}
