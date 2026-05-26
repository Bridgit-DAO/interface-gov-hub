"""Layer email invitation create / accept / duplicate handling."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Optional

from extensions import db
from models import Layer, LayerInvitation, LayerMember, User
from services.coordination import is_layer_admin
from services.events import emit_event
from services.layer_invitation_mail import send_layer_invitation_email
from services.utils import check_rate_limit, generate_invitation_token

_INVITE_TTL_DAYS = 7
_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def normalize_invitee_email(email: str) -> str:
    return (email or '').strip().lower()


def validate_invitee_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(normalize_invitee_email(email)))


def active_layer_member(layer_id: str, user_id: str) -> Optional[LayerMember]:
    return LayerMember.query.filter_by(
        layer_id=layer_id,
        user_id=user_id,
        status='active',
    ).filter(LayerMember.left_at.is_(None)).first()


def is_active_layer_member(layer_id: str, user_id: str) -> bool:
    return active_layer_member(layer_id, user_id) is not None


def can_send_layer_invitations(layer_id: str, user_id: str) -> bool:
    """Active members and layer admins (owner/initiator or assigned admin) may invite."""
    if is_active_layer_member(layer_id, user_id):
        return True
    layer = Layer.query.get(layer_id)
    user = User.query.get(user_id)
    if not layer or not user:
        return False
    return is_layer_admin(layer, {'id': user.id, 'role': user.role})


def invitee_is_active_member(layer_id: str, email: str) -> bool:
    norm = normalize_invitee_email(email)
    user = User.query.filter(db.func.lower(User.email) == norm).first()
    if not user:
        return False
    return is_active_layer_member(layer_id, user.id)


def _invitation_dict(inv: LayerInvitation, layer: Optional[Layer] = None, inviter: Optional[User] = None) -> dict[str, Any]:
    d = inv.to_dict()
    if layer:
        d['layer_name'] = layer.name
        d['layer_slug'] = layer.slug
    if inviter:
        d['inviter_name'] = inviter.displayName or inviter.name or inviter.username
    return d


def create_layer_invitation(
    *,
    layer_id: str,
    inviter_id: str,
    invitee_email: str,
    message: Optional[str] = None,
) -> tuple[dict[str, Any], int]:
    """
    Create or refresh a layer invitation.
    Returns (response_body, http_status).
    """
    if not can_send_layer_invitations(layer_id, inviter_id):
        return {'error': 'Only active layer members or layer admins can send invitations'}, 403

    email = normalize_invitee_email(invitee_email)
    if not validate_invitee_email(email):
        return {'error': 'Valid email address is required'}, 400

    if not check_rate_limit(f'layer_invite:{inviter_id}:{layer_id}', max_requests=20, window_seconds=86400):
        return {'error': 'Invitation rate limit reached. Try again tomorrow.'}, 429

    layer = Layer.query.get(layer_id)
    if not layer:
        return {'error': 'Layer not found'}, 404

    inviter = User.query.get(inviter_id)
    if not inviter:
        return {'error': 'Inviter not found'}, 404

    if (inviter.email or '').strip().lower() == email:
        return {'error': 'You cannot invite yourself'}, 400

    invitee = User.query.filter(db.func.lower(User.email) == email).first()
    now = datetime.utcnow()

    if invitee and is_active_layer_member(layer_id, invitee.id):
        inv = LayerInvitation(
            layer_id=layer_id,
            inviter_id=inviter_id,
            invitee_email=email,
            invitee_id=invitee.id,
            message=(message or '').strip() or None,
            status='duplicate',
            outcome_note='Already an active member',
            token=generate_invitation_token(),
            expires_at=now + timedelta(days=_INVITE_TTL_DAYS),
            responded_at=now,
        )
        db.session.add(inv)
        db.session.commit()
        return {
            'success': True,
            'duplicate': True,
            'message': f'{email} is already a member of this layer.',
            'invitation': _invitation_dict(inv, layer, inviter),
        }, 200

    pending = LayerInvitation.query.filter_by(
        layer_id=layer_id,
        invitee_email=email,
        status='pending',
    ).first()

    if pending:
        if pending.expires_at and pending.expires_at < now:
            pending.status = 'expired'
            pending = None
        else:
            pending.inviter_id = inviter_id
            pending.message = (message or '').strip() or pending.message
            pending.expires_at = now + timedelta(days=_INVITE_TTL_DAYS)
            if invitee:
                pending.invitee_id = invitee.id
            db.session.commit()
            sent = send_layer_invitation_email(
                invitation_token=pending.token,
                layer=layer,
                inviter=inviter,
                invitee_email=email,
                message=pending.message,
            )
            return {
                'success': True,
                'resent': True,
                'email_sent': sent,
                'invitation': _invitation_dict(pending, layer, inviter),
                'invite_path': f'/layer/invite/{pending.token}/',
            }, 200

    token = generate_invitation_token()
    inv = LayerInvitation(
        layer_id=layer_id,
        inviter_id=inviter_id,
        invitee_email=email,
        invitee_id=invitee.id if invitee else None,
        message=(message or '').strip() or None,
        status='pending',
        token=token,
        expires_at=now + timedelta(days=_INVITE_TTL_DAYS),
    )
    db.session.add(inv)
    db.session.commit()

    sent = send_layer_invitation_email(
        invitation_token=token,
        layer=layer,
        inviter=inviter,
        invitee_email=email,
        message=inv.message,
    )

    return {
        'success': True,
        'duplicate': False,
        'email_sent': sent,
        'invitation': _invitation_dict(inv, layer, inviter),
        'invite_path': f'/layer/invite/{token}/',
    }, 201


def preview_layer_invitation(token: str) -> tuple[dict[str, Any], int]:
    inv = LayerInvitation.query.filter_by(token=token).first()
    if not inv:
        return {'error': 'Invalid invitation'}, 404
    if inv.status == 'duplicate':
        return {'error': 'This person was already a member when invited'}, 409
    if inv.status != 'pending':
        return {'error': f'Invitation is {inv.status}'}, 404
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return {'error': 'Invitation expired'}, 410

    layer = Layer.query.get(inv.layer_id)
    if not layer:
        return {'error': 'Layer not found'}, 404

    email = inv.invitee_email or ''
    masked = email[:2] + '***' + email[email.index('@'):] if '@' in email else '***'
    inviter = User.query.get(inv.inviter_id)
    return {
        'valid': True,
        'layer': {
            'id': layer.id,
            'name': layer.name,
            'slug': layer.slug,
            'mission': layer.mission,
            'description': layer.description,
        },
        'inviter_name': (inviter.displayName or inviter.name or inviter.username) if inviter else None,
        'invitee_email_masked': masked,
        'message': inv.message,
    }, 200


def accept_layer_invitation(token: str, user_id: str) -> tuple[dict[str, Any], int]:
    inv = LayerInvitation.query.filter_by(token=token).first()
    if not inv:
        return {'error': 'Invalid invitation'}, 404
    if inv.status == 'duplicate':
        return {'error': 'Invitation was marked duplicate (already a member)'}, 409
    if inv.status != 'pending':
        return {'error': f'Invitation is {inv.status}'}, 404
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return {'error': 'Invitation expired'}, 410

    user = User.query.get(user_id)
    if not user or not user.email:
        return {'error': 'Account has no email on file'}, 400

    ok = (
        (inv.invitee_id and inv.invitee_id == user.id)
        or normalize_invitee_email(inv.invitee_email) == normalize_invitee_email(user.email)
    )
    if not ok:
        return {'error': 'This invitation was sent to a different email address'}, 403

    layer = Layer.query.get(inv.layer_id)
    if not layer:
        return {'error': 'Layer not found'}, 404

    existing = LayerMember.query.filter_by(layer_id=inv.layer_id, user_id=user.id).first()
    now = datetime.utcnow()

    if existing and existing.status == 'active' and existing.left_at is None:
        inv.status = 'duplicate'
        inv.outcome_note = 'Already an active member'
        inv.responded_at = now
        inv.invitee_id = user.id
        db.session.commit()
        return {
            'success': True,
            'duplicate': True,
            'already_member': True,
            'layer_id': inv.layer_id,
            'layer_slug': layer.slug,
        }, 200

    referral_code = f'invite:{inv.token}'
    if existing:
        existing.status = 'active'
        existing.left_at = None
        existing.joined_at = now
        if inv.inviter_id and not existing.referred_by_id:
            existing.referred_by_id = inv.inviter_id
            existing.referral_code = referral_code
        member = existing
    else:
        member = LayerMember(
            layer_id=inv.layer_id,
            user_id=user.id,
            referred_by_id=inv.inviter_id,
            referral_code=referral_code,
            role='contributor',
        )
        db.session.add(member)

    inv.status = 'accepted'
    inv.responded_at = now
    inv.invitee_id = user.id

    emit_event(
        'member_joined',
        actor_type='user',
        actor_id=user.id,
        subject_type='layer_member',
        subject_id=member.id,
        layer_id=inv.layer_id,
        payload={
            'user_id': user.id,
            'role': member.role,
            'via': 'layer_invitation',
            'inviter_id': inv.inviter_id,
        },
    )
    db.session.commit()

    return {
        'success': True,
        'layer_id': inv.layer_id,
        'layer_slug': layer.slug,
        'member_id': member.id,
    }, 200


def decline_layer_invitation(token: str, user_id: str) -> tuple[dict[str, Any], int]:
    inv = LayerInvitation.query.filter_by(token=token).first()
    if not inv or inv.status != 'pending':
        return {'error': 'Invalid invitation'}, 404
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return {'error': 'Invitation expired'}, 410

    user = User.query.get(user_id)
    if not user:
        return {'error': 'Authentication required'}, 401
    ok = (
        (inv.invitee_id and inv.invitee_id == user.id)
        or normalize_invitee_email(inv.invitee_email) == normalize_invitee_email(user.email or '')
    )
    if not ok:
        return {'error': 'This invitation was sent to a different email address'}, 403

    inv.status = 'declined'
    inv.responded_at = datetime.utcnow()
    inv.invitee_id = user.id
    db.session.commit()
    return {'success': True}, 200


def list_layer_invitations(layer_id: str, user_id: str) -> tuple[dict[str, Any], int]:
    if not can_send_layer_invitations(layer_id, user_id):
        return {'error': 'Only active layer members or layer admins can view invitations'}, 403

    rows = (
        LayerInvitation.query.filter_by(layer_id=layer_id)
        .order_by(LayerInvitation.created_at.desc())
        .limit(100)
        .all()
    )
    inviter_ids = {r.inviter_id for r in rows}
    inviters = {u.id: u for u in User.query.filter(User.id.in_(inviter_ids)).all()} if inviter_ids else {}
    layer = Layer.query.get(layer_id)
    return {
        'invitations': [
            _invitation_dict(r, layer, inviters.get(r.inviter_id))
            for r in rows
        ],
    }, 200
