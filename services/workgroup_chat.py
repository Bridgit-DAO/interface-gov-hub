"""Workgroup member chat: list (teaser/full) and post."""
from __future__ import annotations

from typing import Optional

from extensions import db
from models import User, Workgroup, WorkgroupMessage
from services.events import emit_event
from services.workgroup_authority import is_workgroup_member

TEASER_LIMIT = 5
TEASER_BODY_MAX = 180
FULL_LIMIT = 200


def _author_name(user: Optional[User]) -> str:
    if not user:
        return 'Member'
    return (user.displayName or user.username or 'Member').strip()


def _visible_query(workgroup_id: str):
    return WorkgroupMessage.query.filter_by(workgroup_id=workgroup_id).filter(
        WorkgroupMessage.deleted_at.is_(None),
    )


def list_workgroup_messages(
    workgroup: Workgroup,
    *,
    viewer: Optional[dict],
    full: bool = False,
) -> dict:
    is_member = bool(viewer and is_workgroup_member(workgroup.acronym, viewer))
    use_full = full and is_member
    limit = FULL_LIMIT if use_full else TEASER_LIMIT

    rows = (
        _visible_query(workgroup.id)
        .order_by(WorkgroupMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    rows = list(reversed(rows))

    author_ids = {r.author_user_id for r in rows}
    users = {}
    if author_ids:
        for u in User.query.filter(User.id.in_(list(author_ids))).all():
            users[u.id] = u

    messages = []
    for row in rows:
        body = row.body or ''
        if not use_full and len(body) > TEASER_BODY_MAX:
            body = body[: TEASER_BODY_MAX - 1].rstrip() + '…'
        messages.append(
            row.to_dict(author_name=_author_name(users.get(row.author_user_id))),
        )

    return {
        'messages': messages,
        'is_member': is_member,
        'can_post': is_member,
        'teaser': not use_full,
        'count': len(messages),
    }


def create_workgroup_message(workgroup: Workgroup, user: dict, body: str) -> tuple[dict, int]:
    if not is_workgroup_member(workgroup.acronym, user):
        return {'error': 'Only workgroup members can post messages'}, 403

    text = (body or '').strip()
    if not text:
        return {'error': 'Message body is required'}, 400
    if len(text) > 8000:
        return {'error': 'Message is too long (max 8000 characters)'}, 400

    author = User.query.get(user['id'])
    if not author:
        return {'error': 'User not found'}, 404

    msg = WorkgroupMessage(
        workgroup_id=workgroup.id,
        author_user_id=author.id,
        body=text,
    )
    db.session.add(msg)
    db.session.flush()

    emit_event(
        'workgroup_message_posted',
        actor_type='user',
        actor_id=author.id,
        subject_type='workgroup_message',
        subject_id=msg.id,
        layer_id=workgroup.layer_id,
        payload={
            'workgroup_id': workgroup.id,
            'workgroup_slug': workgroup.slug or workgroup.acronym,
            'workgroup_name': workgroup.name,
            'body_preview': text[:200],
        },
    )
    db.session.commit()

    return {
        'success': True,
        'message': msg.to_dict(author_name=_author_name(author)),
    }, 201
