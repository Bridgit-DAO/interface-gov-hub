"""DP Challenge workgroup welcome delivery (Message A / A+B combined).

Two welcomes exist, and each is delivered exactly once per person per
workgroup:

* ``member`` – Message A, for someone who joined a DP workgroup directly.
* ``lead`` – the combined Message A + B, for someone whose lead/co-lead
  nomination was approved.

A welcome notification is only meaningful while the underlying grant is still
valid, so :func:`list_dp_welcome_notifications` re-checks membership / approved
position at read time and :func:`invalidate_dp_welcomes_for_workgroup` archives
the notification when someone leaves.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Literal, Optional
from urllib.parse import quote, unquote_plus, urlencode

from extensions import db
from models import UserNotification, Workgroup, WorkingGroupChair
from services.workgroup_authority import is_workgroup_member, user_has_approved_workgroup_position
from services.workgroup_links import is_dp_workgroup
from services.workgroup_positions import position_label

DP_CHALLENGE_SITE_BASE = os.environ.get(
    'DP_CHALLENGE_SITE_BASE', 'https://desirableproperties.org'
).rstrip('/')

WelcomeVariant = Literal['member', 'lead']

_LEAD_POSITION_KEYS = frozenset({'chair', 'co_lead'})

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_WELCOME_LINK_PREFIX = f'{DP_CHALLENGE_SITE_BASE}/welcome/'
_WG_QUERY_RE = re.compile(r'[?&]wg=([^&#]*)')


def is_valid_nominee_email(email: Optional[str]) -> bool:
    return bool(_EMAIL_RE.match((email or '').strip()))


def require_nominee_email(nomination: WorkingGroupChair) -> Optional[str]:
    """Return an error message when nominee_email is missing or invalid."""
    if not is_valid_nominee_email(nomination.nominee_email):
        return (
            'This nomination is missing a valid nominee email. '
            'Contact a layer administrator.'
        )
    return None


def dp_welcome_page_url(workgroup_slug: str, variant: WelcomeVariant) -> str:
    """Welcome page URL. The slug is URL-encoded (it reaches us from user data)."""
    path = 'lead' if variant == 'lead' else 'member'
    slug = (workgroup_slug or '').strip()
    query = urlencode({'wg': slug})
    return f'{DP_CHALLENGE_SITE_BASE}/welcome/{quote(path)}?{query}'


def welcome_slug_from_link(link_url: Optional[str]) -> str:
    """Recover the ``?wg=`` slug from a stored welcome link."""
    match = _WG_QUERY_RE.search(link_url or '')
    return unquote_plus(match.group(1)) if match else ''


def nomination_welcome_variant(position_key: Optional[str]) -> WelcomeVariant:
    key = (position_key or 'chair').strip().lower()
    return 'lead' if key in _LEAD_POSITION_KEYS else 'member'


def deliver_dp_welcome(
    *,
    user_id: str,
    workgroup: Workgroup,
    variant: WelcomeVariant,
    position_key: Optional[str] = None,
) -> Optional[str]:
    """Create an in-app notification pointing at the DP welcome page.

    Idempotent per (user, workgroup, variant): a repeated call — a retried
    approval, a rejoin, a replayed request — returns the same URL without adding
    a second notification. Caller commits.
    """
    if not is_dp_workgroup(workgroup) or not user_id:
        return None
    slug = workgroup.slug or workgroup.acronym or ''
    url = dp_welcome_page_url(slug, variant)

    existing = UserNotification.query.filter_by(
        user_id=user_id,
        link_url=url[:500],
    ).first()
    if existing:
        if existing.archived_at is not None:
            # Person previously left and has now come back: revive the welcome.
            existing.archived_at = None
            existing.created_at = datetime.utcnow()
            existing.read_at = None
            db.session.flush()
        return url

    if variant == 'lead':
        pos = position_label(position_key or 'chair')
        title = f'Welcome — {pos} for {workgroup.name}'
        body = f"You're approved as workgroup {pos.lower()}. Open your combined welcome guide."
    else:
        title = f'Welcome to {workgroup.name}'
        body = (
            'You joined a Desirable Properties workgroup. '
            'Open your welcome guide to get started.'
        )
    db.session.add(UserNotification(
        user_id=user_id,
        title=title[:255],
        body=body,
        link_url=url[:500],
    ))
    db.session.flush()
    return url


def welcome_is_still_valid(user_id: str, variant: str, workgroup_slug: str) -> bool:
    """A welcome is valid only while its grant is: membership, or approved role."""
    if not user_id:
        return False
    if not workgroup_slug:
        # Legacy notification without a resolvable workgroup: keep showing it
        # rather than hiding a link the person may still need.
        return True
    workgroup = Workgroup.query.filter_by(slug=workgroup_slug).first()
    if not workgroup:
        workgroup = Workgroup.query.filter_by(acronym=workgroup_slug).first()
    if not workgroup:
        return True
    if variant == 'lead':
        return user_has_approved_workgroup_position(workgroup, user_id)
    return is_workgroup_member(workgroup.acronym, user_id)


def list_dp_welcome_notifications(user_id: str, *, limit: int = 10) -> list[dict]:
    """Recent, still-valid DP welcome notifications (profile dropdown / API)."""
    rows = (
        UserNotification.query.filter_by(user_id=user_id)
        .filter(UserNotification.link_url.like(f'{_WELCOME_LINK_PREFIX}%'))
        .filter(UserNotification.archived_at.is_(None))
        .order_by(UserNotification.created_at.desc())
        .limit(max(limit * 4, limit))
        .all()
    )
    welcomes = []
    for row in rows:
        link = row.link_url or ''
        variant = 'lead' if '/welcome/lead' in link else 'member'
        if not welcome_is_still_valid(user_id, variant, welcome_slug_from_link(link)):
            continue
        welcomes.append({
            'id': row.id,
            'title': row.title,
            'body': row.body,
            'link_url': link,
            'variant': variant,
            'read_at': row.read_at.isoformat() if row.read_at else None,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        })
        if len(welcomes) >= limit:
            break
    return welcomes


def invalidate_dp_welcomes_for_workgroup(
    *,
    user_id: str,
    workgroup: Optional[Workgroup],
    variants: Optional[tuple] = None,
) -> int:
    """Archive welcome notifications whose grant no longer exists.

    Used when someone leaves a workgroup: the stale "welcome, you joined"
    notification must stop appearing, but it is archived (kept for history)
    rather than deleted, and a later rejoin revives it. Caller commits.
    """
    if not user_id or not workgroup:
        return 0
    slug = workgroup.slug or workgroup.acronym or ''
    targets = variants or ('member', 'lead')
    now = datetime.utcnow()
    archived = 0
    for variant in targets:
        url = dp_welcome_page_url(slug, variant)[:500]
        rows = UserNotification.query.filter_by(
            user_id=user_id,
            link_url=url,
            archived_at=None,
        ).all()
        for row in rows:
            row.archived_at = now
            archived += 1
    if archived:
        db.session.flush()
    return archived


def stale_member_welcome_variants(
    *,
    user_id: str,
    workgroup: Optional[Workgroup],
) -> tuple:
    """Variants whose grant is gone for this user (used after membership change)."""
    if not user_id or not workgroup:
        return ()
    stale = []
    if not is_workgroup_member(workgroup.acronym, user_id):
        stale.append('member')
    if not user_has_approved_workgroup_position(workgroup, user_id):
        stale.append('lead')
    return tuple(stale)
