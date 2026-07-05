"""
User event subscriptions: pattern (exact event_type) × subject × channel.

Draft notifications: one row per (user, event_type, draft); UI uses a matrix of
in-app / email toggles (draft detail + /notifications hub).
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import func

from extensions import db
from models import UserEventSubscription

# Ordered rows for subscription UI (event_type, short label)
DRAFT_SUBSCRIPTION_ROWS: Tuple[Tuple[str, str], ...] = (
    ('draft_comment_added', 'Comments & replies'),
    ('draft_submission_approved', 'Draft approved (first approval)'),
    ('draft_revision_approved', 'Revision approved'),
    ('draft_published_as_rfc', 'Published as RFC'),
)

# UI labels for the follow form
NOTIFICATION_LEVELS = {
    'all': 'All changes and comments',
    'significant': 'Only significant changes (state changes, new revisions)',
    'major': 'Only major changes (IESG actions, RFC publication)',
    'comments': 'Only comments',
    'none': 'No notifications (just tracking)',
}

DRAFT_EVENT_TYPES = frozenset({
    'draft_comment_added',
    'draft_submission_approved',
    'draft_revision_approved',
    'draft_published_as_rfc',
})

# Maps former notification_level -> exact EventLog event_type strings for subject_type=draft
LEVEL_TO_EVENT_TYPES = {
    'none': [],
    'comments': ['draft_comment_added'],
    'major': ['draft_published_as_rfc'],
    'significant': [
        'draft_revision_approved',
        'draft_submission_approved',
        'draft_published_as_rfc',
    ],
    'all': sorted(DRAFT_EVENT_TYPES),
}


def event_types_for_level(level: str) -> List[str]:
    return list(LEVEL_TO_EVENT_TYPES.get(level, LEVEL_TO_EVENT_TYPES['all']))


def get_draft_subscription_matrix(user_id: str, draft_name: str) -> Dict[str, Tuple[bool, bool]]:
    """event_type -> (deliver_in_app, deliver_email) for known draft event types."""
    rows = UserEventSubscription.query.filter_by(
        user_id=user_id,
        subject_type='draft',
        subject_id=draft_name,
    ).all()
    by_et = {r.event_type: r for r in rows}
    out: Dict[str, Tuple[bool, bool]] = {}
    for et, _label in DRAFT_SUBSCRIPTION_ROWS:
        if et in by_et:
            r = by_et[et]
            out[et] = (bool(r.deliver_in_app), bool(r.deliver_email))
        else:
            out[et] = (False, False)
    return out


def replace_draft_subscriptions_matrix(
    user_id: str,
    draft_name: str,
    matrix: Dict[str, Tuple[bool, bool]],
) -> None:
    """Replace draft-scoped subscriptions from per-event (in_app, email) pairs."""
    UserEventSubscription.query.filter_by(
        user_id=user_id,
        subject_type='draft',
        subject_id=draft_name,
    ).delete(synchronize_session=False)
    for et, (ia, em) in matrix.items():
        if et not in DRAFT_EVENT_TYPES:
            continue
        if not ia and not em:
            continue
        db.session.add(
            UserEventSubscription(
                id=str(uuid4()),
                user_id=user_id,
                event_type=et,
                subject_type='draft',
                subject_id=draft_name,
                deliver_in_app=ia,
                deliver_email=em,
                created_at=datetime.utcnow(),
            )
        )


def matrix_from_subscription_post(form) -> Dict[str, Tuple[bool, bool]]:
    """Parse POST body: checkboxes named in_app_<event_type> and email_<event_type> (value 1)."""
    out: Dict[str, Tuple[bool, bool]] = {}
    for et, _ in DRAFT_SUBSCRIPTION_ROWS:
        ia = form.get(f'in_app_{et}', '') in ('1', 'on', 'true', True)
        em = form.get(f'email_{et}', '') in ('1', 'on', 'true', True)
        if ia or em:
            out[et] = (ia, em)
    return out


def list_user_draft_subjects(user_id: str) -> List[str]:
    """Distinct draft names the user has any subscription row for."""
    q = (
        db.session.query(UserEventSubscription.subject_id)
        .filter(
            UserEventSubscription.user_id == user_id,
            UserEventSubscription.subject_type == 'draft',
        )
        .distinct()
        .order_by(UserEventSubscription.subject_id)
    )
    return [row[0] for row in q.all()]


def replace_draft_subscriptions(user_id: str, draft_name: str, level: str) -> None:
    """Replace all draft-scoped subscriptions for this user with the set implied by level."""
    UserEventSubscription.query.filter_by(
        user_id=user_id,
        subject_type='draft',
        subject_id=draft_name,
    ).delete(synchronize_session=False)
    if level == 'none' or not event_types_for_level(level):
        return
    for et in event_types_for_level(level):
        db.session.add(
            UserEventSubscription(
                id=str(uuid4()),
                user_id=user_id,
                event_type=et,
                subject_type='draft',
                subject_id=draft_name,
                deliver_in_app=True,
                deliver_email=True,
                created_at=datetime.utcnow(),
            )
        )


def infer_draft_notification_level(user_id: str, draft_name: str) -> Optional[str]:
    """Infer UI level from subscription rows; None if not following."""
    rows = UserEventSubscription.query.filter_by(
        user_id=user_id,
        subject_type='draft',
        subject_id=draft_name,
    ).all()
    types = {r.event_type for r in rows}
    if not types:
        return None
    if types == DRAFT_EVENT_TYPES:
        return 'all'
    if types == {'draft_comment_added'}:
        return 'comments'
    if types == {'draft_published_as_rfc'}:
        return 'major'
    sig = {'draft_revision_approved', 'draft_submission_approved', 'draft_published_as_rfc'}
    if types == sig:
        return 'significant'
    # Partial/custom set – default UI to 'all' so user can reset
    return 'all'


def user_follows_draft(user_id: str, draft_name: str) -> bool:
    return (
        UserEventSubscription.query.filter_by(
            user_id=user_id,
            subject_type='draft',
            subject_id=draft_name,
        ).first()
        is not None
    )


def count_distinct_drafts_followed(user_id: str) -> int:
    return (
        db.session.query(func.count(func.distinct(UserEventSubscription.subject_id)))
        .filter(
            UserEventSubscription.user_id == user_id,
            UserEventSubscription.subject_type == 'draft',
        )
        .scalar()
        or 0
    )
