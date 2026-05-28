"""Unified platform invitations: create, preview, accept, decline."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from uuid import uuid4

from extensions import db
from models import (
    PlatformInvitation,
    Submission,
    User,
    Workgroup,
    WorkingGroupMember,
    WorkgroupMemberRequest,
)
from services.coordination import is_layer_admin
from services.dp_proposals import (
    resolve_submission_for_proposals,
    submission_draft_ref,
)
from services.platform_invitation_mail import send_platform_invitation_email
from services.proposal_modes import is_mode_enabled, proposal_mode_for_submission
from services.utils import generate_invitation_token

_INVITE_TTL_DAYS = 7
_STANDARD_DAILY_LIMIT = 10
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


def validate_invitee_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(normalize_invitee_email(email)))


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


def check_rate_limit(inviter_id: str, rate_category: str) -> Optional[str]:
    if rate_category == 'participation':
        return None
    if count_standard_invites_today(inviter_id) >= _STANDARD_DAILY_LIMIT:
        return 'Invitation limit reached for today (10). Try again tomorrow.'
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
        if _is_workgroup_member(wg.acronym, inviter_id):
            return True, ''
        layer = wg.layer
        if layer and is_layer_admin(layer, {'id': inviter.id, 'role': inviter.role}):
            return True, ''
        return False, 'Only workgroup members or layer admins can invite'

    return False, 'Unsupported invitation type'


def _is_workgroup_member(group_acronym: str, user_id: str) -> bool:
    if not group_acronym or not user_id:
        return False
    return WorkingGroupMember.query.filter_by(
        group_acronym=group_acronym,
        user_id=user_id,
    ).first() is not None


def _workgroup_requires_approval(acronym: str) -> bool:
    from services.groups import load_group_data
    for g in load_group_data():
        if g.get('acronym') == acronym:
            return bool(g.get('members_require_approval'))
    return False


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
    return strip_invite_query_params(build_landing_path(inv))


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
    path = build_landing_path(inv)
    return {
        'success': True,
        'email_sent': email_sent,
        'invitation': inv.to_dict(),
        'invite_path': path,
        'landing_url': None,  # filled by route with origin if needed
        'inviter_name': (inviter.displayName or inviter.username) if inviter else None,
        'target_title': _target_title(inv),
    }


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
        if invitee and _is_workgroup_member(wg.acronym, invitee.id):
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
        db.session.commit()
        sent = send_platform_invitation_email(
            invitation=pending_match,
            inviter=inviter,
            invitee_email=email,
            landing_url=_public_base_url() + build_landing_path(pending_match),
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
        token=token,
        expires_at=now + timedelta(days=_INVITE_TTL_DAYS),
    )
    db.session.add(inv)
    db.session.commit()

    sent = send_platform_invitation_email(
        invitation=inv,
        inviter=inviter,
        invitee_email=email,
        landing_url=_public_base_url() + build_landing_path(inv),
        target_title=_target_title(inv),
    )
    body = _invitation_response(inv, email_sent=sent)
    return body, 201


def _public_base_url() -> str:
    from flask import current_app
    from config import PUBLIC_BASE_URL
    return (current_app.config.get('PUBLIC_BASE_URL') or PUBLIC_BASE_URL).rstrip('/')


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
    if inv.status == 'duplicate':
        return {'error': inv.outcome_note or 'Invitation duplicate'}, 409
    if inv.status != 'pending':
        return {'error': f'Invitation is {inv.status}'}, 404
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return {'error': 'Invitation expired'}, 410

    inviter = User.query.get(inv.inviter_id)
    email = inv.invitee_email or ''
    masked = email[:2] + '***' + email[email.index('@'):] if '@' in email else '***'
    target = _load_target(inv)
    body: Dict[str, Any] = {
        'valid': True,
        'invite_type': inv.invite_type,
        'inviter_name': (inviter.displayName or inviter.username) if inviter else None,
        'invitee_email_masked': masked,
        'invitee_email': email,
        'message': inv.message,
        'target_title': _target_title(inv),
        'landing_path': build_landing_path(inv),
        'target': target,
        'authenticated': 'user' in session,
    }
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


def _accept_participate_dp(inv: PlatformInvitation, user: User) -> Tuple[dict, int]:
    inv.status = 'accepted'
    inv.responded_at = datetime.utcnow()
    inv.invitee_id = user.id
    db.session.commit()
    return {
        'success': True,
        'invite_type': inv.invite_type,
        'redirect_path': build_post_accept_redirect(inv),
    }, 200


def _accept_document(inv: PlatformInvitation, user: User) -> Tuple[dict, int]:
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


def _accept_join_workgroup(inv: PlatformInvitation, user: User) -> Tuple[dict, int]:
    target = _load_target(inv)
    acronym = (target.get('workgroup_acronym') or '').strip()
    slug = (target.get('workgroup_slug') or '').strip()
    if not acronym:
        return {'error': 'Invalid invitation target'}, 400

    if _is_workgroup_member(acronym, user.id):
        inv.status = 'duplicate'
        inv.outcome_note = 'Already a member'
        inv.responded_at = datetime.utcnow()
        inv.invitee_id = user.id
        db.session.commit()
        return {
            'success': True,
            'duplicate': True,
            'redirect_path': f'/workgroups/{slug}/' if slug else '/workgroups/',
        }, 200

    if _workgroup_requires_approval(acronym):
        pending = WorkgroupMemberRequest.query.filter_by(
            group_acronym=acronym,
            user_id=user.id,
            status='pending',
        ).first()
        if not pending:
            req = WorkgroupMemberRequest(
                group_acronym=acronym,
                user_id=user.id,
                user_name=user.displayName or user.username,
                status='pending',
                invited_by_user_id=inv.inviter_id,
                platform_invitation_id=inv.id,
            )
            db.session.add(req)
    else:
        db.session.add(WorkingGroupMember(
            id=str(uuid4()),
            group_acronym=acronym,
            user_id=user.id,
            user_name=user.displayName or user.username,
        ))

    inv.status = 'accepted'
    inv.responded_at = datetime.utcnow()
    inv.invitee_id = user.id
    db.session.commit()
    return {
        'success': True,
        'redirect_path': f'/workgroups/{slug}/' if slug else '/workgroups/',
        'pending_approval': _workgroup_requires_approval(acronym),
    }, 200


def accept_invitation(token: str, user_id: str) -> Tuple[dict, int]:
    inv = PlatformInvitation.query.filter_by(token=token.strip()).first()
    if not inv:
        return {'error': 'Invalid invitation'}, 404
    if inv.status != 'pending':
        return {'error': f'Invitation is {inv.status}'}, 404
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return {'error': 'Invitation expired'}, 410

    user = User.query.get(user_id)
    if not user:
        return {'error': 'User not found'}, 404
    if not _email_matches_invite(inv, user):
        return {'error': 'This invitation was sent to a different email address'}, 403

    if inv.invite_type == 'participate_dp':
        return _accept_participate_dp(inv, user)
    if inv.invite_type in ('edit_document', 'edit_document_passage', 'review_document'):
        return _accept_document(inv, user)
    if inv.invite_type == 'join_workgroup':
        return _accept_join_workgroup(inv, user)
    return {'error': 'Unsupported invitation type'}, 400


def decline_invitation(token: str, user_id: str) -> Tuple[dict, int]:
    inv = PlatformInvitation.query.filter_by(token=token.strip()).first()
    if not inv or inv.status != 'pending':
        return {'error': 'Invalid invitation'}, 404
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return {'error': 'Invitation expired'}, 410

    user = User.query.get(user_id)
    if not user or not _email_matches_invite(inv, user):
        return {'error': 'This invitation was sent to a different email address'}, 403

    inv.status = 'declined'
    inv.responded_at = datetime.utcnow()
    inv.invitee_id = user.id
    db.session.commit()
    return {'success': True}, 200
