"""DP Challenge workgroup welcome delivery (Message A / A+B combined)."""
from __future__ import annotations

import os
import re
from typing import Literal, Optional

from uuid import uuid4

from extensions import db
from models import User, UserNotification, Workgroup, WorkingGroupChair, WorkingGroupMember
from services.workgroup_authority import is_workgroup_member
from services.workgroup_links import is_dp_workgroup
from services.workgroup_positions import position_label

DP_CHALLENGE_SITE_BASE = os.environ.get(
    'DP_CHALLENGE_SITE_BASE', 'https://desirableproperties.org'
).rstrip('/')

WelcomeVariant = Literal['member', 'lead']

_LEAD_POSITION_KEYS = frozenset({'chair', 'co_lead'})

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
_WELCOME_LINK_PREFIX = f'{DP_CHALLENGE_SITE_BASE}/welcome/'


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
    path = 'lead' if variant == 'lead' else 'member'
    slug = (workgroup_slug or '').strip()
    return f'{DP_CHALLENGE_SITE_BASE}/welcome/{path}?wg={slug}'


def ensure_nomination_membership(nomination: WorkingGroupChair) -> bool:
    """Create WorkingGroupMember for an approved nominee when user_id is known."""
    if not nomination.user_id:
        return False
    acronym = nomination.group_acronym
    if not acronym or is_workgroup_member(acronym, nomination.user_id):
        return False
    user = User.query.get(nomination.user_id)
    display_name = (
        nomination.chair_name
        or (user.displayName if user else '')
        or (user.username if user else '')
    )
    db.session.add(WorkingGroupMember(
        id=str(uuid4()),
        group_acronym=acronym,
        user_id=nomination.user_id,
        user_name=display_name,
    ))
    db.session.flush()
    return True


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
    """Create an in-app notification pointing at the DP welcome page. Returns the URL."""
    if not is_dp_workgroup(workgroup):
        return None
    slug = workgroup.slug or workgroup.acronym or ''
    url = dp_welcome_page_url(slug, variant)
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


def list_dp_welcome_notifications(user_id: str, *, limit: int = 10) -> list[dict]:
    """Recent DP welcome notifications for profile dropdown / API consumers."""
    rows = (
        UserNotification.query.filter_by(user_id=user_id)
        .filter(UserNotification.link_url.like(f'{_WELCOME_LINK_PREFIX}%'))
        .order_by(UserNotification.created_at.desc())
        .limit(limit)
        .all()
    )
    welcomes = []
    for row in rows:
        link = row.link_url or ''
        variant = 'lead' if '/welcome/lead' in link else 'member'
        welcomes.append({
            'id': row.id,
            'title': row.title,
            'body': row.body,
            'link_url': link,
            'variant': variant,
            'read_at': row.read_at.isoformat() if row.read_at else None,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        })
    return welcomes
