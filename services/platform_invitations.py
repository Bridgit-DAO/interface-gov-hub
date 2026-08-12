"""Unified platform invitations: create, preview, accept, decline."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from extensions import db
from models import (
    Layer,
    LayerAdmin,
    PlatformInvitation,
    PlatformInvitationAcceptance,
    Submission,
    User,
    Workgroup,
)
from services.invitation_binding import (
    BINDING_PRIVATE,
    BINDING_SHAREABLE,
    platform_invitation_is_shareable,
    resolve_platform_binding_mode,
)
from services.dp_proposals import (
    resolve_submission_for_proposals,
    submission_draft_ref,
)
from services.platform_invitation_mail import send_platform_invitation_email
from services.proposal_modes import is_mode_enabled, proposal_mode_for_submission
from services.dp_public_urls import (
    workgroup_invite_landing_path,
    workgroup_invite_landing_url,
    workgroup_post_accept_path,
)
from services.public_urls import public_base_url
from services.utils import generate_invitation_token
from services.workgroup_authority import can_invite_workgroup_member, is_workgroup_member
from services.workgroup_membership import (
    emit_workgroup_invite_event,
    join_or_request_workgroup_membership,
    workgroup_invite_event_payload,
)

_INVITE_TTL_DAYS = 7
_STANDARD_DAILY_LIMIT = 10
_ELEVATED_DAILY_LIMIT = 100
# Bridgit DAO staff / org accounts (elevated invite quota).
_BRIDGITDAO_EMAIL_SUFFIXES = ('@bridgit.io', '@bridgitdao.com', '@bridgitdao.io')
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

PARTICIPATION_TYPES = frozenset({'participate_dp'})
STANDARD_TYPES = frozenset({
    'edit_document',
    'edit_document_passage',
    'review_document',
    'join_workgroup',
})


def normalize_invitee_email(email: str) -> str:
    return (email or '').strip().lower()


def parse_invitee_email_list(raw: Any) -> list:
    """Split comma/newline/semicolon-separated emails; dedupe preserving order."""
    if raw is None:
        return []
    if isinstance(raw, list):
        parts = raw
    else:
        parts = re.split(r'[\s,;]+', str(raw))
    seen = set()
    out = []
    for part in parts:
        email = normalize_invitee_email(part)
        if not email or email in seen:
            continue
        if validate_invitee_email(email):
            seen.add(email)
            out.append(email)
    return out


def validate_invitee_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(normalize_invitee_email(email)))


def lookup_prior_workgroup_invitations(email: str, *, limit: int = 10) -> list:
    """Prior join_workgroup invitations for an email (any workgroup)."""
    norm = normalize_invitee_email(email)
    if not norm:
        return []
    rows = (
        PlatformInvitation.query.filter_by(
            invite_type='join_workgroup',
            invitee_email=norm,
        )
        .order_by(PlatformInvitation.created_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for inv in rows:
        try:
            target = json.loads(inv.target_json or '{}')
        except json.JSONDecodeError:
            target = {}
        out.append({
            'id': inv.id,
            'status': inv.status,
            'created_at': inv.created_at.isoformat() if inv.created_at else None,
            'workgroup_name': target.get('workgroup_name') or target.get('workgroup_slug') or '',
            'workgroup_id': target.get('workgroup_id') or '',
            'message_preview': (inv.message or '')[:120],
        })
    return out


def _utc_day_start() -> datetime:
    now = datetime.utcnow()
    return datetime(now.year, now.month, now.day)


def count_standard_invites_today(inviter_id: str) -> int:
    since = _utc_day_start()
    return PlatformInvitation.query.filter(
        PlatformInvitation.inviter_id == inviter_id,
        PlatformInvitation.rate_category == 'standard',
        PlatformInvitation.created_at >= since,
    ).count()


def _is_bridgitdao_user(user: User) -> bool:
    """Site admins and Bridgit DAO org email addresses."""
    if (user.role or '').lower() == 'admin':
        return True
    email = normalize_invitee_email(user.email or '')
    return any(email.endswith(suffix) for suffix in _BRIDGITDAO_EMAIL_SUFFIXES)


def _is_any_layer_admin(user: User) -> bool:
    """Layer owner, assigned layer admin, or site admin."""
    if (user.role or '').lower() == 'admin':
        return True
    if Layer.query.filter_by(initiator_id=user.id).first():
        return True
    return LayerAdmin.query.filter_by(user_id=user.id).first() is not None


def inviter_daily_limit(inviter_id: str) -> int:
    user = User.query.get(inviter_id)
    if not user:
        return _STANDARD_DAILY_LIMIT
    if _is_bridgitdao_user(user) or _is_any_layer_admin(user):
        return _ELEVATED_DAILY_LIMIT
    return _STANDARD_DAILY_LIMIT


def check_rate_limit(inviter_id: str, rate_category: str) -> Optional[str]:
    if rate_category == 'participation':
        return None
    limit = inviter_daily_limit(inviter_id)
    if count_standard_invites_today(inviter_id) >= limit:
        return f'Invitation limit reached for today ({limit}). Try again tomorrow.'
    return None


def _parse_target(raw: Any) -> Tuple[Optional[dict], Optional[str]]:
    if not isinstance(raw, dict):
        return None, 'target must be a JSON object'
    return raw, None


def _dump_target(target: dict) -> str:
    return json.dumps(target, sort_keys=True)


def _load_target(inv: PlatformInvitation) -> dict:
    try:
        data = json.loads(inv.target_json or '{}')
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _submission_from_target(target: dict) -> Tuple[Optional[Submission], Optional[str]]:
    submission_id = (target.get('submission_id') or '').strip()
    draft_ref = (target.get('draft_ref') or '').strip()
    if submission_id:
        sub = Submission.query.get(submission_id)
        if sub:
            return sub, None
    if draft_ref:
        sub, err = resolve_submission_for_proposals(draft_ref)
        if err:
            return None, err
        return sub, None
    return None, 'submission_id or draft_ref required'


def _resolve_document_invite_type(submission: Submission, requested: str) -> str:
    mode = proposal_mode_for_submission(submission)
    if is_mode_enabled(mode):
        return requested if requested in ('edit_document', 'edit_document_passage') else 'edit_document'
    return 'review_document'


def can_invite(inviter_id: str, invite_type: str, target: dict) -> Tuple[bool, str]:
    from models.platform_invitation import INVITE_TYPES
    if invite_type not in INVITE_TYPES:
        return False, 'Invalid invitation type'

    inviter = User.query.get(inviter_id)
    if not inviter:
        return False, 'Inviter not found'

    if invite_type == 'participate_dp':
        return True, ''

    if invite_type in ('edit_document', 'edit_document_passage', 'review_document'):
        sub, err = _submission_from_target(target)
        if err or not sub:
            return False, err or 'Document not found'
        if sub.status != 'approved':
            return False, 'Document must be approved'
        return True, ''

    if invite_type == 'join_workgroup':
        wg_id = (target.get('workgroup_id') or '').strip()
        if not wg_id:
            return False, 'workgroup_id required'
        wg = Workgroup.query.get(wg_id)
        if not wg:
            return False, 'Workgroup not found'
        if can_invite_workgroup_member(wg, {
            'id': inviter.id,
            'role': inviter.role,
        }):
            return True, ''
        return False, 'Only workgroup members, layer admins, or site staff can invite'

    return False, 'Unsupported invitation type'


def strip_invite_query_params(path: str) -> str:
    """Remove invite flow query params after accept so the landing modal does not re-open."""
    if not path or not path.startswith('/'):
        return path or '/'
    parsed = urlparse(path)
    if not parsed.query:
        return path
    query = parse_qs(parsed.query, keep_blank_values=True)
    for key in ('invite', 'welcome', 'compose'):
        query.pop(key, None)
    flat = []
    for key, values in query.items():
        for value in values:
            flat.append((key, value))
    new_query = urlencode(flat)
    return urlunparse(parsed._replace(query=new_query)) or path


def build_post_accept_redirect(inv: PlatformInvitation) -> str:
    if inv.invite_type == 'join_workgroup':
        target = _load_target(inv)
        slug = (target.get('workgroup_slug') or '').strip()
        return workgroup_post_accept_path(slug)
    return strip_invite_query_params(build_landing_path(inv))


def invitation_landing_url(inv: PlatformInvitation) -> str:
    """Full URL for emails and share links (DP for workgroup invites)."""
    if inv.invite_type == 'join_workgroup':
        return workgroup_invite_landing_url(inv)
    return public_base_url() + build_landing_path(inv)


def invitation_landing_path(inv: PlatformInvitation) -> str:
    """Path portion of invitation_landing_url (DP-relative for workgroup invites)."""
    if inv.invite_type == 'join_workgroup':
        return workgroup_invite_landing_path(inv)
    return build_landing_path(inv)


def build_landing_path(inv: PlatformInvitation) -> str:
    target = _load_target(inv)
    token_q = f'invite={inv.token}'
    if inv.invite_type == 'participate_dp':
        return f'/dp-challenge/?{token_q}'
    if inv.invite_type == 'join_workgroup':
        slug = (target.get('workgroup_slug') or '').strip()
        if slug:
            return f'/workgroups/{slug}/?{token_q}'
        return f'/workgroups/?{token_q}'
    draft_ref = (target.get('draft_ref') or '').strip()
    if not draft_ref and target.get('submission_id'):
        sub = Submission.query.get(target['submission_id'])
        if sub:
            draft_ref = submission_draft_ref(sub)
    if draft_ref:
        path = f'/doc/draft/{draft_ref}/read/?{token_q}'
        if inv.invite_type == 'edit_document_passage':
            path += '&compose=1'
        elif inv.invite_type == 'edit_document':
            path += '&welcome=1'
        return path
    return f'/?{token_q}'


def _target_title(inv: PlatformInvitation) -> str:
    target = _load_target(inv)
    if inv.invite_type == 'participate_dp':
        return 'DP Challenge'
    if inv.invite_type == 'join_workgroup':
        return (target.get('workgroup_name') or 'Workgroup').strip()
    sub, _ = _submission_from_target(target)
    if sub:
        return (sub.title or submission_draft_ref(sub) or 'Document').strip()
    return 'Document'


def _invitation_response(inv: PlatformInvitation, *, email_sent: bool = False) -> dict:
    inviter = User.query.get(inv.inviter_id)
    path = invitation_landing_path(inv)
    shareable = platform_invitation_is_shareable(inv)
    return {
        'success': True,
        'email_sent': email_sent,
        'shareable': shareable,
        'binding_mode': getattr(inv, 'binding_mode', None) or ('shareable' if shareable else 'private'),
        'invitation': inv.to_dict(),
        'invite_path': path,
        'landing_url': invitation_landing_url(inv),
        'inviter_name': (inviter.displayName or inviter.username) if inviter else None,
        'target_title': _target_title(inv),
    }


def _invitation_is_revoked(inv: PlatformInvitation) -> bool:
    return bool(getattr(inv, 'revoked_at', None))


def _find_shareable_platform_campaign(
    invite_type: str,
    inviter_id: str,
    target_key: str,
) -> Optional[PlatformInvitation]:
    return PlatformInvitation.query.filter_by(
        invite_type=invite_type,
        inviter_id=inviter_id,
        target_json=target_key,
        binding_mode=BINDING_SHAREABLE,
        status='pending',
    ).filter(PlatformInvitation.revoked_at.is_(None)).first()


def get_or_create_shareable_platform_invitation(
    *,
    invite_type: str,
    inviter_id: str,
    target: dict,
    message: Optional[str] = None,
) -> Tuple[PlatformInvitation, bool]:
    """Return (invitation, created). Reuses one pending shareable row per inviter+type+target."""
    target_key = _dump_target(target)
    existing = _find_shareable_platform_campaign(invite_type, inviter_id, target_key)
    now = datetime.utcnow()
    if existing:
        existing.inviter_id = inviter_id
        if (message or '').strip():
            existing.message = (message or '').strip()
        existing.expires_at = None
        db.session.commit()
        return existing, False

    inv = PlatformInvitation(
        invite_type=invite_type,
        rate_category='participation' if invite_type in PARTICIPATION_TYPES else 'standard',
        inviter_id=inviter_id,
        invitee_email='',
        message=(message or '').strip() or None,
        target_json=target_key,
        status='pending',
        binding_mode=BINDING_SHAREABLE,
        token=generate_invitation_token(),
        expires_at=None,
    )
    db.session.add(inv)
    db.session.commit()
    return inv, True


def get_shareable_platform_campaign(
    *,
    invite_type: str,
    inviter_id: str,
    target: Optional[dict] = None,
    message: Optional[str] = None,
) -> Tuple[dict, int]:
    """Ensure a shareable campaign exists and return its link (no email required)."""
    target = target if isinstance(target, dict) else {}
    ok, err = can_invite(inviter_id, invite_type, target)
    if not ok:
        return {'error': err}, 403
    if resolve_platform_binding_mode(invite_type, target) != BINDING_SHAREABLE:
        return {'error': 'This invitation type is not shareable'}, 400

    if invite_type in ('edit_document', 'edit_document_passage'):
        sub, err = _submission_from_target(target)
        if err or not sub:
            return {'error': err or 'Document not found'}, 404
        invite_type = _resolve_document_invite_type(sub, invite_type)
        target = dict(target)
        target['submission_id'] = sub.id
        target['draft_ref'] = submission_draft_ref(sub)
    if invite_type == 'participate_dp':
        target = {}
    if invite_type == 'join_workgroup':
        wg_id = (target.get('workgroup_id') or '').strip()
        wg = Workgroup.query.get(wg_id)
        if not wg:
            return {'error': 'Workgroup not found'}, 404
        target = {
            'workgroup_id': wg.id,
            'workgroup_slug': wg.slug or wg.acronym,
            'workgroup_name': wg.name,
            'workgroup_acronym': wg.acronym,
            'layer_id': wg.layer_id,
        }

    inv, _created = get_or_create_shareable_platform_invitation(
        invite_type=invite_type,
        inviter_id=inviter_id,
        target=target,
        message=message,
    )
    body = _invitation_response(inv)
    return body, 200


def _record_shareable_acceptance(inv: PlatformInvitation, user: User) -> None:
    existing = PlatformInvitationAcceptance.query.filter_by(
        invitation_id=inv.id,
        user_id=user.id,
    ).first()
    if not existing:
        db.session.add(
            PlatformInvitationAcceptance(
                invitation_id=inv.id,
                user_id=user.id,
            )
        )
        db.session.commit()


def _workgroup_from_target(target: dict) -> Optional[Workgroup]:
    if not isinstance(target, dict):
        return None
    wg_id = (target.get('workgroup_id') or '').strip()
    if wg_id:
        wg = Workgroup.query.get(wg_id)
        if wg:
            return wg
    acronym = (target.get('workgroup_acronym') or '').strip()
    if acronym:
        return Workgroup.query.filter_by(acronym=acronym).first()
    return None


def _emit_workgroup_invite_sent(
    inv: PlatformInvitation,
    inviter: User,
    workgroup: Workgroup,
) -> None:
    emit_workgroup_invite_event(
        'workgroup_invite_sent',
        workgroup=workgroup,
        actor_user_id=inviter.id,
        subject_type='platform_invitation',
        subject_id=inv.id,
        payload=workgroup_invite_event_payload(
            workgroup,
            invitee_email=inv.invitee_email or '',
            invitation_id=inv.id,
        ),
    )


def _emit_workgroup_invite_accepted(
    inv: PlatformInvitation,
    user: User,
    workgroup: Workgroup,
) -> None:
    emit_workgroup_invite_event(
        'workgroup_invite_accepted',
        workgroup=workgroup,
        actor_user_id=user.id,
        subject_type='platform_invitation',
        subject_id=inv.id,
        payload=workgroup_invite_event_payload(
            workgroup,
            invitee_email=inv.invitee_email or user.email or '',
            invitee_name=(user.displayName or user.username or '').strip(),
            invitation_id=inv.id,
        ),
    )


def create_invitation(
    *,
    invite_type: str,
    inviter_id: str,
    invitee_email: str,
    message: Optional[str] = None,
    target: Optional[dict] = None,
) -> Tuple[dict, int]:
    """Create or refresh a pending invitation."""
    from models.platform_invitation import INVITE_TYPES

    invite_type = (invite_type or '').strip()
    if invite_type not in INVITE_TYPES:
        return {'error': 'Invalid invitation type'}, 400

    target = target if isinstance(target, dict) else {}
    ok, err = can_invite(inviter_id, invite_type, target)
    if not ok:
        return {'error': err}, 403

    if resolve_platform_binding_mode(invite_type, target) == BINDING_SHAREABLE:
        return _create_shareable_platform_invitation(
            invite_type=invite_type,
            inviter_id=inviter_id,
            invitee_email=invitee_email,
            message=message,
            target=target,
        )

    email = normalize_invitee_email(invitee_email)
    if not validate_invitee_email(email):
        return {'error': 'Valid email address is required'}, 400

    rate_category = 'participation' if invite_type in PARTICIPATION_TYPES else 'standard'
    rate_err = check_rate_limit(inviter_id, rate_category)
    if rate_err:
        return {'error': rate_err}, 429

    inviter = User.query.get(inviter_id)
    if not inviter:
        return {'error': 'Inviter not found'}, 404
    if (inviter.email or '').strip().lower() == email:
        return {'error': 'You cannot invite yourself'}, 400

    # Normalize document invite types
    if invite_type in ('edit_document', 'edit_document_passage'):
        sub, err = _submission_from_target(target)
        if err or not sub:
            return {'error': err or 'Document not found'}, 404
        invite_type = _resolve_document_invite_type(sub, invite_type)
        target = dict(target)
        target['submission_id'] = sub.id
        target['draft_ref'] = submission_draft_ref(sub)

    if invite_type == 'join_workgroup':
        wg_id = (target.get('workgroup_id') or '').strip()
        wg = Workgroup.query.get(wg_id)
        if not wg:
            return {'error': 'Workgroup not found'}, 404
        target = {
            'workgroup_id': wg.id,
            'workgroup_slug': wg.slug or wg.acronym,
            'workgroup_name': wg.name,
            'workgroup_acronym': wg.acronym,
            'layer_id': wg.layer_id,
        }
        invitee = User.query.filter(db.func.lower(User.email) == email).first()
        if invitee and is_workgroup_member(wg.acronym, invitee.id):
            now = datetime.utcnow()
            inv = PlatformInvitation(
                invite_type=invite_type,
                rate_category=rate_category,
                inviter_id=inviter_id,
                invitee_email=email,
                invitee_id=invitee.id,
                message=(message or '').strip() or None,
                target_json=_dump_target(target),
                status='duplicate',
                outcome_note='Already a member',
                token=generate_invitation_token(),
                expires_at=now + timedelta(days=_INVITE_TTL_DAYS),
                responded_at=now,
            )
            db.session.add(inv)
            db.session.commit()
            body = _invitation_response(inv)
            body['duplicate'] = True
            body['message'] = f'{email} is already a member of this workgroup.'
            return body, 200

    if invite_type == 'participate_dp':
        target = {}

    now = datetime.utcnow()
    invitee = User.query.filter(db.func.lower(User.email) == email).first()

    target_key = _dump_target(target)
    pending = PlatformInvitation.query.filter_by(
        invite_type=invite_type,
        invitee_email=email,
        status='pending',
    ).all()
    pending_match = None
    for row in pending:
        if row.expires_at and row.expires_at < now:
            row.status = 'expired'
            continue
        if row.target_json == target_key:
            pending_match = row
            break

    if pending_match:
        pending_match.inviter_id = inviter_id
        pending_match.message = (message or '').strip() or pending_match.message
        pending_match.expires_at = now + timedelta(days=_INVITE_TTL_DAYS)
        if invitee:
            pending_match.invitee_id = invitee.id
        db.session.flush()
        if invite_type == 'join_workgroup':
            wg = _workgroup_from_target(target)
            if wg:
                _emit_workgroup_invite_sent(pending_match, inviter, wg)
        db.session.commit()
        sent = send_platform_invitation_email(
            invitation=pending_match,
            inviter=inviter,
            invitee_email=email,
            landing_url=invitation_landing_url(pending_match),
            target_title=_target_title(pending_match),
        )
        body = _invitation_response(pending_match, email_sent=sent)
        body['resent'] = True
        return body, 200

    token = generate_invitation_token()
    inv = PlatformInvitation(
        invite_type=invite_type,
        rate_category=rate_category,
        inviter_id=inviter_id,
        invitee_email=email,
        invitee_id=invitee.id if invitee else None,
        message=(message or '').strip() or None,
        target_json=_dump_target(target),
        status='pending',
        binding_mode=BINDING_PRIVATE,
        token=token,
        expires_at=now + timedelta(days=_INVITE_TTL_DAYS),
    )
    db.session.add(inv)
    db.session.flush()
    if invite_type == 'join_workgroup':
        wg = _workgroup_from_target(target)
        if wg:
            _emit_workgroup_invite_sent(inv, inviter, wg)
    db.session.commit()

    sent = send_platform_invitation_email(
        invitation=inv,
        inviter=inviter,
        invitee_email=email,
        landing_url=invitation_landing_url(inv),
        target_title=_target_title(inv),
    )
    body = _invitation_response(inv, email_sent=sent)
    return body, 201


def _create_shareable_platform_invitation(
    *,
    invite_type: str,
    inviter_id: str,
    invitee_email: str,
    message: Optional[str],
    target: dict,
) -> Tuple[dict, int]:
    """One shareable link per campaign; optional email only delivers that link."""
    if invite_type in ('edit_document', 'edit_document_passage'):
        sub, err = _submission_from_target(target)
        if err or not sub:
            return {'error': err or 'Document not found'}, 404
        invite_type = _resolve_document_invite_type(sub, invite_type)
        target = dict(target)
        target['submission_id'] = sub.id
        target['draft_ref'] = submission_draft_ref(sub)

    if invite_type == 'join_workgroup':
        wg_id = (target.get('workgroup_id') or '').strip()
        wg = Workgroup.query.get(wg_id)
        if not wg:
            return {'error': 'Workgroup not found'}, 404
        target = {
            'workgroup_id': wg.id,
            'workgroup_slug': wg.slug or wg.acronym,
            'workgroup_name': wg.name,
            'workgroup_acronym': wg.acronym,
            'layer_id': wg.layer_id,
        }

    if invite_type == 'participate_dp':
        target = {}

    inviter = User.query.get(inviter_id)
    if not inviter:
        return {'error': 'Inviter not found'}, 404

    inv, _created = get_or_create_shareable_platform_invitation(
        invite_type=invite_type,
        inviter_id=inviter_id,
        target=target,
        message=message,
    )

    if invite_type == 'join_workgroup' and _created:
        wg = _workgroup_from_target(target)
        if wg:
            db.session.flush()
            _emit_workgroup_invite_sent(inv, inviter, wg)
            db.session.commit()

    email = normalize_invitee_email(invitee_email)
    sent = False
    if email:
        if not validate_invitee_email(email):
            return {'error': 'Valid email address is required'}, 400
        if (inviter.email or '').strip().lower() == email:
            return {'error': 'You cannot invite yourself'}, 400
        rate_category = 'participation' if invite_type in PARTICIPATION_TYPES else 'standard'
        rate_err = check_rate_limit(inviter_id, rate_category)
        if rate_err:
            return {'error': rate_err}, 429
        sent = send_platform_invitation_email(
            invitation=inv,
            inviter=inviter,
            invitee_email=email,
            landing_url=invitation_landing_url(inv),
            target_title=_target_title(inv),
        )

    body = _invitation_response(inv, email_sent=sent)
    return body, 201 if _created else 200


def create_invitations_bulk(
    *,
    invite_type: str,
    inviter_id: str,
    emails: Optional[list] = None,
    invitee_user_ids: Optional[list] = None,
    message: Optional[str] = None,
    target: Optional[dict] = None,
) -> Tuple[dict, int]:
    """Create invitations for many emails and/or Gov Hub users (by user id)."""
    import logging

    logger = logging.getLogger(__name__)
    parsed_emails = list(parse_invitee_email_list(emails or []))
    targets = list(parsed_emails)
    user_ids_requested = 0
    user_ids_resolved = 0
    user_ids_skipped_no_email = 0
    for uid in invitee_user_ids or []:
        uid = (uid or '').strip()
        if not uid:
            continue
        user_ids_requested += 1
        user = User.query.get(uid)
        if not user or not user.email:
            user_ids_skipped_no_email += 1
            logger.warning(
                'invite batch: skip user_id=%s (missing user or email)', uid
            )
            continue
        user_ids_resolved += 1
        email = normalize_invitee_email(user.email)
        if email and email not in targets:
            targets.append(email)
    if not targets:
        return {'error': 'At least one valid email or Gov Hub user is required'}, 400
    if len(targets) > 25:
        return {'error': 'Maximum 25 invitations per batch'}, 400

    if resolve_platform_binding_mode(invite_type, target if isinstance(target, dict) else {}) == BINDING_SHAREABLE:
        return _create_shareable_platform_batch(
            invite_type=invite_type,
            inviter_id=inviter_id,
            emails=targets,
            message=message,
            target=target if isinstance(target, dict) else {},
        )

    logger.info(
        'invite batch inviter=%s type=%s emails_parsed=%d user_ids_requested=%d '
        'user_ids_resolved=%d user_ids_skipped=%d unique_recipients=%d',
        inviter_id,
        invite_type,
        len(parsed_emails),
        user_ids_requested,
        user_ids_resolved,
        user_ids_skipped_no_email,
        len(targets),
    )

    results = []
    sent_count = 0
    error_count = 0
    for email in targets:
        body, status = create_invitation(
            invite_type=invite_type,
            inviter_id=inviter_id,
            invitee_email=email,
            message=message,
            target=target,
        )
        entry = {
            'email': email,
            'ok': 200 <= status < 300,
            'status': status,
            'duplicate': bool(body.get('duplicate')),
        }
        if entry['ok']:
            if body.get('email_sent'):
                sent_count += 1
            entry['invite_path'] = body.get('invite_path')
        else:
            error_count += 1
            entry['error'] = body.get('error') or 'Failed'
        results.append(entry)

    return {
        'success': error_count == 0,
        'count': len(results),
        'sent_email_count': sent_count,
        'error_count': error_count,
        'stats': {
            'emails_parsed': len(parsed_emails),
            'user_ids_requested': user_ids_requested,
            'user_ids_resolved': user_ids_resolved,
            'user_ids_skipped_no_email': user_ids_skipped_no_email,
            'unique_recipients': len(targets),
        },
        'results': results,
    }, 200 if error_count == 0 else 207


def _create_shareable_platform_batch(
    *,
    invite_type: str,
    inviter_id: str,
    emails: list,
    message: Optional[str],
    target: dict,
) -> Tuple[dict, int]:
    """Send many emails pointing at the same shareable campaign link."""
    body, status = _create_shareable_platform_invitation(
        invite_type=invite_type,
        inviter_id=inviter_id,
        invitee_email='',
        message=message,
        target=target,
    )
    if status >= 400:
        return body, status

    inv_token = (body.get('invite_path') or '').split('invite=')[-1].split('&')[0]
    inv = PlatformInvitation.query.filter_by(token=inv_token).first() if inv_token else None
    if not inv:
        return body, status

    inviter = User.query.get(inviter_id)
    share_path = body.get('invite_path') or invitation_landing_path(inv)
    landing_url = (
        workgroup_invite_landing_url(inv)
        if inv.invite_type == 'join_workgroup'
        else public_base_url() + share_path
    )
    results = []
    sent_count = 0
    error_count = 0
    for email in emails:
        try:
            sent = send_platform_invitation_email(
                invitation=inv,
                inviter=inviter,
                invitee_email=email,
                landing_url=landing_url,
                target_title=_target_title(inv),
            )
            if sent:
                sent_count += 1
            results.append({
                'email': email,
                'ok': True,
                'status': 200,
                'duplicate': False,
                'invite_path': share_path,
            })
        except Exception:
            error_count += 1
            results.append({
                'email': email,
                'ok': False,
                'status': 500,
                'error': 'Failed to send email',
            })

    return {
        'success': error_count == 0,
        'count': len(results),
        'sent_email_count': sent_count,
        'error_count': error_count,
        'shareable': True,
        'invite_path': share_path,
        'results': results,
    }, 200 if error_count == 0 else 207


def _passage_excerpt_from_target(target: dict) -> str:
    if not isinstance(target, dict):
        return ''
    anchor = target.get('context_anchor')
    if not isinstance(anchor, dict):
        return ''
    text_quote = anchor.get('textQuote')
    if not isinstance(text_quote, dict):
        return ''
    exact = (text_quote.get('exact') or '').strip()
    if len(exact) > 500:
        return exact[:497] + '…'
    return exact


def _document_abstract_from_target(target: dict) -> str:
    sub, _ = _submission_from_target(target if isinstance(target, dict) else {})
    if not sub:
        return ''
    abstract = (sub.abstract or '').strip()
    if not abstract:
        return ''
    if len(abstract) > 600:
        return abstract[:597] + '…'
    return abstract


def preview_invitation(token: str) -> Tuple[dict, int]:
    from flask import session

    inv = PlatformInvitation.query.filter_by(token=token.strip()).first()
    if not inv:
        return {'error': 'Invalid invitation'}, 404
    if _invitation_is_revoked(inv):
        return {'error': 'This invitation has been revoked'}, 410
    if inv.status == 'duplicate':
        return {'error': inv.outcome_note or 'Invitation duplicate'}, 409
    if inv.status == 'revoked' or _invitation_is_revoked(inv):
        return {'error': 'This invitation has been revoked'}, 410
    if inv.status != 'pending':
        return {'error': f'Invitation is {inv.status}'}, 404
    shareable = platform_invitation_is_shareable(inv)
    if not shareable and inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return {'error': 'Invitation expired'}, 410

    inviter = User.query.get(inv.inviter_id)
    email = inv.invitee_email or ''
    masked = ''
    if email and '@' in email:
        masked = email[:2] + '***' + email[email.index('@'):]
    target = _load_target(inv)
    body: Dict[str, Any] = {
        'valid': True,
        'invite_type': inv.invite_type,
        'shareable': shareable,
        'binding_mode': getattr(inv, 'binding_mode', None) or ('shareable' if shareable else 'private'),
        'inviter_name': (inviter.displayName or inviter.username) if inviter else None,
        'message': inv.message,
        'target_title': _target_title(inv),
        'landing_path': invitation_landing_path(inv),
        'landing_url': invitation_landing_url(inv),
        'target': target,
        'authenticated': 'user' in session,
    }
    if not shareable:
        body['invitee_email_masked'] = masked
        body['invitee_email'] = email
    if inv.invite_type == 'edit_document_passage':
        excerpt = _passage_excerpt_from_target(target)
        if excerpt:
            body['passage_excerpt'] = excerpt
    if inv.invite_type in ('edit_document', 'edit_document_passage', 'review_document'):
        abstract = _document_abstract_from_target(target)
        if abstract:
            body['document_abstract'] = abstract
    return body, 200


def _email_matches_invite(inv: PlatformInvitation, user: User) -> bool:
    if not user or not user.email:
        return False
    if inv.invitee_id and inv.invitee_id == user.id:
        return True
    return normalize_invitee_email(inv.invitee_email) == normalize_invitee_email(user.email)


def _accept_participate_dp(inv: PlatformInvitation, user: User, *, finalize_invite: bool = True) -> Tuple[dict, int]:
    if finalize_invite:
        inv.status = 'accepted'
        inv.responded_at = datetime.utcnow()
        inv.invitee_id = user.id
        db.session.commit()
    return {
        'success': True,
        'invite_type': inv.invite_type,
        'redirect_path': build_post_accept_redirect(inv),
    }, 200


def _accept_document(inv: PlatformInvitation, user: User, *, finalize_invite: bool = True) -> Tuple[dict, int]:
    if finalize_invite:
        inv.status = 'accepted'
        inv.responded_at = datetime.utcnow()
        inv.invitee_id = user.id
        db.session.commit()
    return {
        'success': True,
        'invite_type': inv.invite_type,
        'redirect_path': build_post_accept_redirect(inv),
        'target': _load_target(inv),
    }, 200


def _accept_join_workgroup(inv: PlatformInvitation, user: User, *, finalize_invite: bool = True) -> Tuple[dict, int]:
    target = _load_target(inv)
    acronym = (target.get('workgroup_acronym') or '').strip()
    slug = (target.get('workgroup_slug') or '').strip()
    if not acronym:
        return {'error': 'Invalid invitation target'}, 400

    if is_workgroup_member(acronym, user.id):
        if finalize_invite:
            inv.status = 'duplicate'
            inv.outcome_note = 'Already a member'
            inv.responded_at = datetime.utcnow()
            inv.invitee_id = user.id
            db.session.commit()
        return {
            'success': True,
            'duplicate': True,
            'redirect_path': workgroup_post_accept_path(slug),
        }, 200

    result = join_or_request_workgroup_membership(
        acronym=acronym,
        user=user,
        invited_by_user_id=inv.inviter_id,
        invitation=inv,
    )
    if not result.get('ok'):
        return {'error': result.get('error') or 'Could not join workgroup'}, 400

    workgroup = Workgroup.query.filter_by(acronym=acronym).first()
    if workgroup:
        _emit_workgroup_invite_accepted(inv, user, workgroup)

    if finalize_invite:
        inv.status = 'accepted'
        inv.responded_at = datetime.utcnow()
        inv.invitee_id = user.id
        db.session.commit()
    else:
        db.session.commit()
    return {
        'success': True,
        'redirect_path': workgroup_post_accept_path(slug),
        'pending_approval': bool(result.get('pending_approval')),
    }, 200


def accept_invitation(token: str, user_id: str) -> Tuple[dict, int]:
    inv = PlatformInvitation.query.filter_by(token=token.strip()).first()
    if not inv:
        return {'error': 'Invalid invitation'}, 404
    if _invitation_is_revoked(inv):
        return {'error': 'This invitation has been revoked'}, 410
    if inv.status != 'pending':
        return {'error': f'Invitation is {inv.status}'}, 404

    shareable = platform_invitation_is_shareable(inv)
    if not shareable and inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return {'error': 'Invitation expired'}, 410

    user = User.query.get(user_id)
    if not user:
        return {'error': 'User not found'}, 404
    if not user.email:
        return {'error': 'Sign in with an account that has an email address on file'}, 400

    if shareable:
        _record_shareable_acceptance(inv, user)
        finalize = False
    else:
        # join_workgroup: token is the trust boundary; invitee may sign in with any email.
        if inv.invite_type != 'join_workgroup' and not _email_matches_invite(inv, user):
            return {'error': 'This invitation was sent to a different email address'}, 403
        finalize = True

    if inv.invite_type == 'participate_dp':
        return _accept_participate_dp(inv, user, finalize_invite=finalize)
    if inv.invite_type in ('edit_document', 'edit_document_passage', 'review_document'):
        return _accept_document(inv, user, finalize_invite=finalize)
    if inv.invite_type == 'join_workgroup':
        return _accept_join_workgroup(inv, user, finalize_invite=finalize)
    return {'error': 'Unsupported invitation type'}, 400


def decline_invitation(token: str, user_id: str) -> Tuple[dict, int]:
    inv = PlatformInvitation.query.filter_by(token=token.strip()).first()
    if not inv or inv.status != 'pending':
        return {'error': 'Invalid invitation'}, 404
    if _invitation_is_revoked(inv):
        return {'error': 'This invitation has been revoked'}, 410

    shareable = platform_invitation_is_shareable(inv)
    if not shareable and inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return {'error': 'Invitation expired'}, 410

    user = User.query.get(user_id)
    if not user:
        return {'error': 'User not found'}, 404

    if shareable:
        return {'success': True, 'note': 'Shareable invitation remains active for others'}, 200

    if not _email_matches_invite(inv, user):
        return {'error': 'This invitation was sent to a different email address'}, 403

    inv.status = 'declined'
    inv.responded_at = datetime.utcnow()
    inv.invitee_id = user.id
    db.session.commit()
    return {'success': True}, 200


def revoke_invitation(token: str, user_id: str) -> Tuple[dict, int]:
    """Revoke a pending invitation (inviter or site admin)."""
    inv = PlatformInvitation.query.filter_by(token=token.strip()).first()
    if not inv:
        return {'error': 'Invalid invitation'}, 404
    if inv.status != 'pending':
        return {'error': f'Cannot revoke invitation in status {inv.status}'}, 400
    if _invitation_is_revoked(inv):
        return {'success': True, 'already_revoked': True}, 200

    user = User.query.get(user_id)
    if not user:
        return {'error': 'User not found'}, 404
    is_admin = (user.role or '').lower() == 'admin'
    if inv.inviter_id != user_id and not is_admin:
        return {'error': 'Only the inviter or a site admin can revoke this link'}, 403

    inv.revoked_at = datetime.utcnow()
    inv.status = 'revoked'
    db.session.commit()
    return {'success': True, 'revoked': True}, 200
