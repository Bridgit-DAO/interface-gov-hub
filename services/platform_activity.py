"""Platform-wide recent activity for the home page rotator."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import not_

from extensions import db
from models import EventLog, Layer, Submission, User
from services.event_registry import EXCLUDED_FROM_ACTIVITY_FEED
from services.submissions import get_submission_by_ref

# Home rotator: high-signal governance events (global, not per-layer).
PLATFORM_HOME_ACTIVITY_TYPES = frozenset({
    'draft_comment_added',
    'draft_comment_liked',
    'draft_created',
    'draft_revision_approved',
    'draft_published_as_rfc',
    'dp_proposal_submitted',
    'dp_proposal_accepted',
    'dp_proposal_declined',
    'member_joined',
    'role_claimed',
    'badge_nominated',
    'badge_approved',
    'artifact_created',
    'artifact_commented',
    'quest_created',
    'monument_created',
    'vote_started',
    'vote_closed',
    'guild_layer_linked',
    'brick_placed',
})

DRAFT_REF_EVENT_TYPES = frozenset({
    'draft_comment_added',
    'draft_comment_liked',
    'draft_created',
    'draft_submission_approved',
    'draft_revision_approved',
    'draft_published_as_rfc',
    'dp_proposal_submitted',
    'dp_proposal_accepted',
    'dp_proposal_declined',
})


def _parse_event_payload(ev: EventLog) -> dict:
    try:
        p = json.loads(ev.payload_json) if ev.payload_json else {}
    except (TypeError, json.JSONDecodeError):
        p = {}
    return p if isinstance(p, dict) else {}


def _submission_href_and_label(sub: Submission) -> tuple[str, str]:
    """Canonical /doc/draft/<ref>/ path and display label."""
    href_ref = (sub.ml_number or sub.draft_name or sub.id or '').strip()
    label = (sub.ml_number or sub.title or sub.draft_name or sub.id or 'document').strip()
    return f'/doc/draft/{href_ref}/', label


def _index_submissions(subs: List[Submission]) -> Dict[str, Submission]:
    out: Dict[str, Submission] = {}
    for sub in subs:
        for key in (sub.id, sub.draft_name, sub.ml_number, sub.public_id):
            if key:
                out[str(key).strip()] = sub
    return out


def _load_submissions_for_refs(refs: set[str]) -> Dict[str, Submission]:
    if not refs:
        return {}
    refs_list = [r for r in refs if r]
    subs: List[Submission] = []
    for chunk_start in range(0, len(refs_list), 50):
        chunk = refs_list[chunk_start:chunk_start + 50]
        subs.extend(
            Submission.query.filter(
                (Submission.id.in_(chunk))
                | (Submission.draft_name.in_(chunk))
                | (Submission.ml_number.in_(chunk))
                | (Submission.public_id.in_(chunk))
            ).all()
        )
    return _index_submissions(subs)


def _event_should_skip(ev: EventLog, submissions: Dict[str, Submission]) -> bool:
    """Drop test noise and events pointing at deleted/unknown drafts."""
    p = _parse_event_payload(ev)
    preview = (p.get('preview') or '').strip().lower()
    if preview.startswith('automated test'):
        return True

    if ev.event_type not in DRAFT_REF_EVENT_TYPES:
        return False

    ref = (p.get('draft_name') or p.get('ml_number') or '').strip()
    if not ref:
        return True
    if ref in submissions:
        return False
    return get_submission_by_ref(ref) is None


def _link(href: str, label: str) -> str:
    return f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'


def _actor_name(ev: EventLog, users: Dict[str, User]) -> str:
    if ev.actor_type == 'user' and ev.actor_id:
        u = users.get(str(ev.actor_id))
        if u:
            return escape(u.displayName or u.username or 'A member')
    if ev.actor_type == 'email':
        return 'Someone'
    if ev.actor_type == 'system':
        return 'System'
    return 'A member'


def _submitter_who(
    ev: EventLog,
    submissions: Dict[str, Submission],
    users: Dict[str, User],
) -> str:
    """Display name of draft submitter (for mis-tagged approval events)."""
    sub = None
    if ev.subject_type == 'submission' and ev.subject_id:
        sub = submissions.get(str(ev.subject_id))
    if not sub:
        return ''
    name = (sub.submitted_by or '').strip()
    if not name:
        return ''
    for u in users.values():
        if (u.displayName or '').strip() == name or (u.username or '').strip() == name:
            return escape(u.displayName or u.username or name)
    return escape(name)


def _home_feed_dedupe_key(ev: EventLog) -> Optional[tuple]:
    """Key for collapsing duplicate-looking rotator lines (keep newest)."""
    try:
        p = json.loads(ev.payload_json) if ev.payload_json else {}
    except (TypeError, json.JSONDecodeError):
        p = {}
    if not isinstance(p, dict):
        p = {}

    et = ev.event_type
    actor = str(ev.actor_id or '')
    layer = str(ev.layer_id or '')

    if et == 'draft_comment_added':
        return (et, actor, (p.get('draft_name') or '').strip(), (p.get('preview') or '').strip()[:100])
    if et == 'draft_comment_liked':
        return (et, actor, (p.get('draft_name') or '').strip(), str(p.get('comment_id') or ''))
    if et in ('draft_created', 'draft_submission_approved'):
        return (et, actor, (p.get('ml_number') or p.get('draft_name') or '').strip())
    if et == 'draft_revision_approved':
        rev = (p.get('revision_number') or '').strip()
        if not rev:
            return ('draft_created', actor, (p.get('ml_number') or p.get('draft_name') or '').strip())
        return (et, actor, (p.get('ml_number') or '').strip(), rev)
    if et == 'member_joined':
        return (et, actor, layer, (p.get('role') or 'contributor').strip())
    if et == 'member_removed':
        return (et, actor, layer)
    if et.startswith('dp_proposal_'):
        return (et, actor, str(p.get('proposal_id') or ''), (p.get('draft_name') or '').strip())
    if et in ('vote_started', 'vote_closed'):
        return (et, layer, (p.get('title') or p.get('vote_id') or '').strip())
    if et == 'role_claimed':
        return (et, actor, layer, str(p.get('role_id') or ''))
    if et in ('badge_nominated', 'badge_approved', 'badge_rejected'):
        return (et, actor, layer, str(p.get('badge_type') or ''))
    if et in ('guild_layer_linked', 'guild_layer_unlinked'):
        return (et, actor, layer, str(p.get('guild_id') or p.get('guild_name') or ''))
    return None


def _draft_link(payload: dict, submissions: Dict[str, Submission]) -> tuple[str, str]:
    ref = (payload.get('draft_name') or payload.get('ml_number') or payload.get('submission_id') or '').strip()
    sub = submissions.get(ref) if ref else None
    if not sub and ref:
        sub = get_submission_by_ref(ref)
    if sub:
        href, label = _submission_href_and_label(sub)
        if payload.get('is_reply'):
            href = f'{href.rstrip("/")}/comments/'
        return href, label
    label = ref or 'a document'
    href = f'/doc/draft/{ref}/' if ref else '/doc/all/'
    if payload.get('is_reply') and ref:
        href = f'/doc/draft/{ref}/comments/'
    return href, label


def format_platform_activity_event(
    ev: EventLog,
    *,
    users: Dict[str, User],
    layers: Dict[str, Layer],
    submissions: Dict[str, Submission],
) -> Dict[str, Any]:
    """Return {id, html, created_at} for one EventLog row."""
    who = _actor_name(ev, users)
    p = _parse_event_payload(ev)
    layer = layers.get(str(ev.layer_id)) if ev.layer_id else None
    layer_href = f'/layers/{layer.slug}/' if layer and layer.slug else None
    layer_label = escape(layer.name) if layer and layer.name else 'a layer'

    html = ''
    et = ev.event_type

    if et == 'draft_comment_added':
        href, label = _draft_link(p, submissions)
        html = f'{who} commented on {_link(href, label)}'
    elif et == 'draft_comment_liked':
        href, label = _draft_link(p, submissions)
        comments_href = f'{href.rstrip("/")}/comments/' if href.endswith('/') else f'{href}/comments/'
        html = f'{who} liked a comment on {_link(comments_href, label)}'
    elif et == 'draft_created':
        href, label = _draft_link(p, submissions)
        ml = (p.get('ml_number') or '').strip()
        display = ml or label
        html = f'{who} created draft {_link(href, display)}'
    elif et == 'draft_submission_approved':
        href, label = _draft_link(p, submissions)
        html = f'{who} — draft approved: {_link(href, label)}'
    elif et == 'draft_revision_approved':
        href, label = _draft_link(p, submissions)
        rev = p.get('revision_number')
        if rev:
            html = f'{who} — revision approved (rev {rev}): {_link(href, label)}'
        else:
            who = _submitter_who(ev, submissions, users) or who
            ml = (p.get('ml_number') or '').strip() or label
            html = f'{who} created draft {_link(href, ml)}'
    elif et == 'draft_published_as_rfc':
        href, label = _draft_link(p, submissions)
        rfc = p.get('rfc_number')
        rfc_s = f' as RFC {rfc}' if rfc else ''
        html = f'Document published{rfc_s}: {_link(href, label)}'
    elif et == 'dp_proposal_submitted':
        href, label = _draft_link(p, submissions)
        scope = (p.get('scope') or 'dp').strip().lower()
        if scope == 'document':
            html = f'{who} suggested an edit on {_link(href, label)}'
        else:
            html = f'{who} submitted a DP proposal on {_link(href, label)}'
    elif et == 'dp_proposal_accepted':
        href, label = _draft_link(p, submissions)
        scope = (p.get('scope') or 'dp').strip().lower()
        if scope == 'document':
            html = f'{who} accepted a suggested edit on {_link(href, label)}'
        else:
            html = f'{who} accepted a DP proposal on {_link(href, label)}'
    elif et == 'dp_proposal_declined':
        href, label = _draft_link(p, submissions)
        scope = (p.get('scope') or 'dp').strip().lower()
        if scope == 'document':
            html = f'{who} declined a suggested edit on {_link(href, label)}'
        else:
            html = f'{who} declined a DP proposal on {_link(href, label)}'
    elif et == 'member_joined':
        role = escape(p.get('role') or 'contributor')
        if layer_href:
            html = f'{who} joined {_link(layer_href, layer_label)} as {role}'
        else:
            html = f'{who} joined a layer as {role}'
    elif et == 'role_claimed':
        verb = 'claimed a role' if p.get('approved') else 'submitted for a role'
        if layer_href:
            html = f'{who} {verb} on {_link(layer_href, layer_label)}'
        else:
            html = f'{who} {verb}'
    elif et == 'badge_nominated':
        bt = escape(p.get('badge_type') or 'a badge')
        if layer_href:
            html = f'{who} was nominated for {bt} on {_link(layer_href, layer_label)}'
        else:
            html = f'{who} was nominated for {bt}'
    elif et == 'badge_approved':
        bt = escape(p.get('badge_type') or 'a badge')
        html = f'{who} earned {bt}'
        if layer_href:
            html += f' on {_link(layer_href, layer_label)}'
    elif et == 'badge_rejected':
        html = f'A badge request was declined'
        if layer_href:
            html += f' on {_link(layer_href, layer_label)}'
    elif et == 'vote_started':
        title = escape(p.get('title') or 'a vote')
        if layer_href:
            html = f'Vote started: {_link(layer_href + "#votes", title)}'
        else:
            html = f'Vote started: {title}'
    elif et == 'vote_closed':
        result = p.get('result')
        suffix = f' ({escape(str(result))})' if result else ''
        if layer_href:
            html = f'Vote closed{suffix} on {_link(layer_href, layer_label)}'
        else:
            html = f'Vote closed{suffix}'
    elif et == 'artifact_created':
        at = p.get('artifact_type')
        if at == 'submission':
            html = f'A new draft was submitted'
        elif layer_href:
            html = f'{who} added an artifact on {_link(layer_href, layer_label)}'
        else:
            html = f'{who} created an artifact'
    elif et == 'artifact_commented':
        if layer_href:
            html = f'{who} commented on an artifact on {_link(layer_href, layer_label)}'
        else:
            html = f'{who} commented on an artifact'
    elif et == 'quest_created':
        if layer_href:
            html = f'{who} created a quest on {_link(layer_href, layer_label)}'
        else:
            html = f'{who} created a quest'
    elif et == 'monument_created':
        if layer_href:
            html = f'{who} created a monument on {_link(layer_href, layer_label)}'
        else:
            html = f'{who} created a monument'
    elif et == 'guild_layer_linked':
        gname = escape(p.get('guild_name') or 'a guild')
        if layer_href:
            html = f'{who} linked guild “{gname}” to {_link(layer_href, layer_label)}'
        else:
            html = f'{who} linked a guild to a layer'
    elif et == 'brick_placed':
        html = f'{who} placed a brick on Civic Mason'
    else:
        label = et.replace('_', ' ')
        html = f'{who} — {escape(label)}'

    created = ev.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        'id': ev.id,
        'html': html,
        'created_at': created.isoformat() if created else None,
    }


def get_platform_activity_items(limit: int = 7) -> List[Dict[str, Any]]:
    """Last N platform-wide meaningful events for the home rotator."""
    limit = max(1, min(int(limit), 7))
    q = EventLog.query.filter(EventLog.event_type.in_(PLATFORM_HOME_ACTIVITY_TYPES))
    q = q.filter(not_(EventLog.event_type.in_(EXCLUDED_FROM_ACTIVITY_FEED)))
    raw = q.order_by(EventLog.created_at.desc()).limit(limit * 12).all()

    draft_refs: set[str] = set()
    for ev in raw:
        p = _parse_event_payload(ev)
        for key in ('draft_name', 'ml_number', 'submission_id'):
            val = (p.get(key) or '').strip()
            if val:
                draft_refs.add(val)
        if ev.subject_type == 'submission' and ev.subject_id:
            draft_refs.add(str(ev.subject_id))

    submissions = _load_submissions_for_refs(draft_refs)

    events: List[EventLog] = []
    seen_keys: set[Tuple] = set()
    for ev in raw:
        if _event_should_skip(ev, submissions):
            continue
        dkey = _home_feed_dedupe_key(ev)
        if dkey is not None:
            if dkey in seen_keys:
                continue
            seen_keys.add(dkey)
        events.append(ev)
        if len(events) >= limit:
            break

    actor_ids = {str(e.actor_id) for e in events if e.actor_type == 'user' and e.actor_id}
    layer_ids = {str(e.layer_id) for e in events if e.layer_id}

    users: Dict[str, User] = {}
    if actor_ids:
        for u in User.query.filter(User.id.in_(list(actor_ids))).all():
            users[str(u.id)] = u

    layers: Dict[str, Layer] = {}
    if layer_ids:
        for layer in Layer.query.filter(Layer.id.in_(list(layer_ids))).all():
            layers[str(layer.id)] = layer

    return [
        format_platform_activity_event(ev, users=users, layers=layers, submissions=submissions)
        for ev in events
    ]


def build_home_activity_rotator_html(initial_items: List[Dict[str, Any]]) -> str:
    """One-row activity rotator with chevrons (no section label)."""
    import json as _json

    items_json = _json.dumps(initial_items).replace('</', '<\\/')
    empty_msg = 'Nothing recent yet — comments, proposals, and layer activity will show here.'
    return f"""
        <div class="gh-home-activity" id="gh-home-activity" aria-label="Recent platform activity">
            <button type="button" class="gh-home-activity-nav gh-home-activity-prev" aria-label="Previous activity" title="Previous">
                <i class="fas fa-chevron-left" aria-hidden="true"></i>
            </button>
            <div class="gh-home-activity-viewport">
                <p class="gh-home-activity-line mb-0" id="gh-home-activity-line"></p>
            </div>
            <div class="gh-home-activity-dots" id="gh-home-activity-dots" aria-hidden="true"></div>
            <button type="button" class="gh-home-activity-nav gh-home-activity-next" aria-label="Next activity" title="Next">
                <i class="fas fa-chevron-right" aria-hidden="true"></i>
            </button>
        </div>
        <script>
        window.__GH_HOME_ACTIVITY__ = {items_json};
        window.__GH_HOME_ACTIVITY_EMPTY__ = {_json.dumps(empty_msg)};
        </script>
        <script src="/static/js/gh-home-activity.js?v=20260528" defer></script>
    """
