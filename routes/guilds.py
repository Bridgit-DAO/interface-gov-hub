"""Guilds API: guild CRUD, members, invitations."""
from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, request

from uuid import uuid4

from extensions import db
from models import (
    Artifact,
    Guild,
    GuildArtifactLink,
    GuildInvitation,
    GuildLayerLink,
    GuildMembership,
    GuildQuestLink,
    Layer,
    Quest,
    User,
)
from services.events import emit_event
from services.guild_phase1 import (
    GUILD_ARTIFACT_LINK_TYPES,
    GUILD_QUEST_LINK_TYPES,
    can_manage_guild_artifact_link,
    can_manage_guild_layer_link,
    can_manage_guild_quest_link,
    is_guild_officer,
)
from services.access_policy import (
    guild_listing_visible,
    normalize_join_policy_layer_guild,
    normalize_listing_visibility,
)
from services.identity import get_current_user, require_auth
from services.avatar import get_avatar_url
from services.utils import create_slug, generate_guild_id, generate_invitation_token

bp = Blueprint('guilds', __name__, url_prefix='/api/guilds')


def _guild_detail(guild_id):
    """Shared implementation for guild detail with members."""
    guild = Guild.query.get_or_404(guild_id)
    if not guild_listing_visible(guild, get_current_user()):
        abort(404)
    mq = GuildMembership.query.filter_by(guild_id=guild_id)
    mq = mq.filter(GuildMembership.membership_state == 'active')
    memberships = mq.all()
    members = []
    for m in memberships:
        if m.user:
            members.append({
                'user_id': m.user_id,
                'username': m.user.username,
                'display_name': m.user.displayName or m.user.username,
                'name': m.user.displayName or m.user.username,
                'profile_image': get_avatar_url(m.user, 32),
                'role': m.role,
                'membership_state': getattr(m, 'membership_state', 'active'),
                'joined_at': m.joined_at.isoformat() if m.joined_at else None
            })
    guild_dict = guild.to_dict()
    guild_dict['members'] = members
    guild_dict['member_count'] = len(members)
    return jsonify(guild_dict)


@bp.route('/', methods=['GET'])
def list_guilds():
    """List all guilds."""
    status = request.args.get('status')
    query = Guild.query.filter_by(status=status) if status else Guild.query
    query = query.order_by(Guild.name.asc())
    guilds = query.all()
    viewer = get_current_user()
    result = []
    for g in guilds:
        if not guild_listing_visible(g, viewer):
            continue
        d = g.to_dict()
        d['members_count'] = GuildMembership.query.filter_by(
            guild_id=g.id, membership_state='active'
        ).count()
        result.append(d)
    return jsonify({'guilds': result, 'count': len(result)})


@bp.route('/', methods=['POST'])
@require_auth
def create_guild():
    """Create a new guild (instant registration)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json() or {}
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not name:
        return jsonify({'error': 'Guild name is required'}), 400

    existing = Guild.query.filter_by(name=name).first()
    if existing:
        return jsonify({'error': 'Guild name already exists'}), 400

    guild_id = generate_guild_id()
    slug = create_slug(name)
    counter = 1
    original_slug = slug
    while Guild.query.filter_by(slug=slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1

    guild = Guild(
        id=guild_id,
        name=name,
        slug=slug,
        initiator_id=current_user['id'],
        description=description,
        status='active',
        listing_visibility=normalize_listing_visibility(data.get('listing_visibility')),
        join_policy=normalize_join_policy_layer_guild(data.get('join_policy')),
    )
    membership = GuildMembership(
        guild_id=guild_id,
        user_id=current_user['id'],
        role='initiator',
        membership_state='active',
    )
    db.session.add(guild)
    db.session.add(membership)
    db.session.commit()

    return jsonify({'success': True, 'guild': guild.to_dict()}), 201


@bp.route('/by-slug/<slug>/', methods=['GET'])
def get_guild_by_slug(slug):
    """Get guild details by slug."""
    guild = Guild.query.filter_by(slug=slug).first()
    if not guild:
        return jsonify({'error': 'Guild not found'}), 404
    return _guild_detail(guild.id)


@bp.route('/invitations/by-token/<token>/', methods=['GET'])
def guild_invitation_preview(token):
    """Public preview for invite acceptance page."""
    inv = GuildInvitation.query.filter_by(token=token).first()
    if not inv or inv.status != 'pending':
        return jsonify({'error': 'Invalid or expired invitation'}), 404
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        return jsonify({'error': 'Invitation expired'}), 410
    g = Guild.query.get(inv.guild_id)
    if not g:
        return jsonify({'error': 'Guild not found'}), 404
    email = inv.invitee_email or ''
    masked = email[:2] + '***' + email[email.index('@') :] if '@' in email else '***'
    return jsonify({
        'valid': True,
        'guild': {'id': g.id, 'name': g.name, 'slug': g.slug},
        'invitee_email_masked': masked,
    }), 200


@bp.route('/invitations/by-token/<token>/accept/', methods=['POST'])
@require_auth
def guild_invitation_accept(token):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    inv = GuildInvitation.query.filter_by(token=token).first()
    if not inv or inv.status != 'pending':
        return jsonify({'error': 'Invalid or expired invitation'}), 404
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        inv.status = 'expired'
        db.session.commit()
        return jsonify({'error': 'Invitation expired'}), 410
    user = User.query.get(current_user['id'])
    if not user or not user.email:
        return jsonify({'error': 'Account has no email'}), 400
    ok = (
        (inv.invitee_id and inv.invitee_id == user.id)
        or (inv.invitee_email and inv.invitee_email.strip().lower() == (user.email or '').strip().lower())
    )
    if not ok:
        return jsonify({'error': 'This invitation was sent to a different email'}), 403
    if GuildMembership.query.filter_by(guild_id=inv.guild_id, user_id=user.id).first():
        inv.status = 'accepted'
        inv.responded_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'success': True, 'already_member': True}), 200
    m = GuildMembership(
        id=str(uuid4()),
        guild_id=inv.guild_id,
        user_id=user.id,
        role='member',
        membership_state='active',
    )
    db.session.add(m)
    inv.status = 'accepted'
    inv.responded_at = datetime.utcnow()
    inv.invitee_id = user.id
    db.session.commit()
    return jsonify({'success': True, 'guild_id': inv.guild_id}), 200


@bp.route('/<guild_id>/', methods=['GET'])
def get_guild(guild_id):
    """Get guild details with members."""
    guild = Guild.query.get_or_404(guild_id)
    return _guild_detail(guild_id)


@bp.route('/<guild_id>/', methods=['PATCH'])
@require_auth
def update_guild(guild_id):
    """Update guild details (initiator/admin only)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    guild = Guild.query.get_or_404(guild_id)
    membership = GuildMembership.query.filter_by(guild_id=guild_id, user_id=current_user['id']).first()
    if not membership or membership.role not in ['initiator', 'admin']:
        return jsonify({'error': 'Only guild admins can edit'}), 403

    data = request.get_json()
    if 'name' in data and data['name']:
        name = data['name'].strip()
        if name != guild.name and Guild.query.filter_by(name=name).first():
            return jsonify({'error': 'A guild with this name already exists'}), 400
        guild.name = name
        guild.slug = create_slug(name)
    if 'description' in data:
        guild.description = data['description']
    if 'image_url' in data:
        guild.image_url = data['image_url'].strip() if data['image_url'] else None
    if 'status' in data and data['status'] in ['active', 'archived']:
        guild.status = data['status']
    if 'listing_visibility' in data:
        guild.listing_visibility = normalize_listing_visibility(data.get('listing_visibility'))
    if 'join_policy' in data:
        guild.join_policy = normalize_join_policy_layer_guild(data.get('join_policy'))

    guild.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'guild': guild.to_dict()})


@bp.route('/<guild_id>/invite/', methods=['POST'])
@require_auth
def invite_to_guild(guild_id):
    """Invite user to guild (admin/initiator only)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    guild = Guild.query.get_or_404(guild_id)
    membership = GuildMembership.query.filter_by(
        guild_id=guild_id,
        user_id=current_user['id']
    ).first()

    if not membership or membership.role not in ['initiator', 'admin']:
        return jsonify({'error': 'Only guild admins can invite members'}), 403

    data = request.get_json()
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    invitee = User.query.filter_by(email=email).first()
    if invitee:
        existing_membership = GuildMembership.query.filter_by(
            guild_id=guild_id,
            user_id=invitee.id
        ).first()
        if existing_membership:
            return jsonify({'error': 'User is already a member'}), 400

    token = generate_invitation_token()
    invitation = GuildInvitation(
        guild_id=guild_id,
        inviter_id=current_user['id'],
        invitee_email=email,
        invitee_id=invitee.id if invitee else None,
        token=token,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(invitation)
    db.session.commit()

    invitation_link = f"/guilds/invite/{token}/"

    return jsonify({
        'success': True,
        'invitation_id': invitation.id,
        'invitation_link': invitation_link,
        'expires_at': invitation.expires_at.isoformat()
    }), 201


def _resolve_layer(layer_id):
    p = Layer.query.get(layer_id)
    if not p:
        p = Layer.query.filter_by(slug=layer_id).first()
    return p


@bp.route('/<guild_id>/layers/', methods=['GET'])
def list_guild_layer_links(guild_id):
    """Layers linked to this guild."""
    guild = Guild.query.get_or_404(guild_id)
    links = GuildLayerLink.query.filter_by(guild_id=guild.id).all()
    out = []
    for ln in links:
        layer = ln.layer
        d = ln.to_dict()
        if layer:
            d['layer'] = {
                'id': layer.id,
                'name': layer.name,
                'slug': layer.slug,
            }
        out.append(d)
    return jsonify({'links': out, 'count': len(out)}), 200


@bp.route('/<guild_id>/layers/', methods=['POST'])
@require_auth
def guild_attach_layer(guild_id):
    """Link guild to layer (same rules as POST /api/layers/.../guilds/)."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    guild = Guild.query.get_or_404(guild_id)
    data = request.get_json(silent=True) or {}
    lid = data.get('layer_id')
    if not lid:
        return jsonify({'error': 'layer_id required'}), 400
    project = _resolve_layer(lid)
    if not project:
        return jsonify({'error': 'Layer not found'}), 404
    if not can_manage_guild_layer_link(user, guild, project):
        return jsonify({'error': 'Forbidden'}), 403
    if GuildLayerLink.query.filter_by(guild_id=guild.id, layer_id=project.id).first():
        return jsonify({'error': 'Link already exists'}), 400
    link = GuildLayerLink(
        id=str(uuid4()),
        guild_id=guild.id,
        layer_id=project.id,
        created_by_user_id=user['id'],
    )
    db.session.add(link)
    emit_event(
        'guild_layer_linked',
        actor_type='user',
        actor_id=user['id'],
        subject_type='guild_layer_link',
        subject_id=link.id,
        layer_id=project.id,
        payload={
            'guild_id': guild.id,
            'guild_name': guild.name,
            'layer_id': project.id,
            'layer_slug': project.slug,
        },
    )
    db.session.commit()
    return jsonify({'success': True, 'link': link.to_dict()}), 201


@bp.route('/<guild_id>/layers/<layer_id>/', methods=['DELETE'])
@require_auth
def guild_detach_layer(guild_id, layer_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    guild = Guild.query.get_or_404(guild_id)
    project = _resolve_layer(layer_id)
    if not project:
        return jsonify({'error': 'Layer not found'}), 404
    if not can_manage_guild_layer_link(user, guild, project):
        return jsonify({'error': 'Forbidden'}), 403
    link = GuildLayerLink.query.filter_by(guild_id=guild.id, layer_id=project.id).first()
    if not link:
        return jsonify({'error': 'Link not found'}), 404
    lid = link.id
    db.session.delete(link)
    emit_event(
        'guild_layer_unlinked',
        actor_type='user',
        actor_id=user['id'],
        subject_type='guild_layer_link',
        subject_id=lid,
        layer_id=project.id,
        payload={'guild_id': guild.id, 'guild_name': guild.name, 'layer_id': project.id},
    )
    db.session.commit()
    return jsonify({'success': True}), 200


@bp.route('/<guild_id>/artifact-links/', methods=['GET'])
def list_guild_artifact_links(guild_id):
    guild = Guild.query.get_or_404(guild_id)
    rows = GuildArtifactLink.query.filter_by(guild_id=guild.id).all()
    out = []
    for row in rows:
        d = row.to_dict()
        art = row.artifact
        if art:
            d['artifact'] = {
                'id': art.id,
                'public_ref': art.public_ref,
                'title': art.title,
                'layer_id': art.layer_id,
            }
        out.append(d)
    return jsonify({'links': out, 'count': len(out)}), 200


@bp.route('/<guild_id>/artifact-links/', methods=['POST'])
@require_auth
def guild_add_artifact_link(guild_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    guild = Guild.query.get_or_404(guild_id)
    data = request.get_json(silent=True) or {}
    aid = data.get('artifact_id')
    link_type = (data.get('link_type') or '').strip().lower()
    if not aid or not link_type:
        return jsonify({'error': 'artifact_id and link_type required'}), 400
    if link_type not in GUILD_ARTIFACT_LINK_TYPES:
        return jsonify({'error': 'Invalid link_type', 'allowed': sorted(GUILD_ARTIFACT_LINK_TYPES)}), 400
    art = Artifact.query.get(aid)
    if not art:
        return jsonify({'error': 'Artifact not found'}), 404
    if not can_manage_guild_artifact_link(user, guild, art):
        return jsonify({'error': 'Forbidden'}), 403
    if GuildArtifactLink.query.filter_by(
        guild_id=guild.id, artifact_id=art.id, link_type=link_type
    ).first():
        return jsonify({'error': 'Link already exists'}), 400
    row = GuildArtifactLink(
        id=str(uuid4()),
        guild_id=guild.id,
        artifact_id=art.id,
        link_type=link_type,
        created_by_user_id=user['id'],
    )
    db.session.add(row)
    emit_event(
        'guild_artifact_linked',
        actor_type='user',
        actor_id=user['id'],
        subject_type='guild_artifact_link',
        subject_id=row.id,
        layer_id=art.layer_id,
        payload={
            'guild_id': guild.id,
            'guild_name': guild.name,
            'artifact_id': art.id,
            'link_type': link_type,
        },
    )
    db.session.commit()
    return jsonify({'success': True, 'link': row.to_dict()}), 201


@bp.route('/<guild_id>/artifact-links/<artifact_id>/', methods=['DELETE'])
@require_auth
def guild_remove_artifact_link(guild_id, artifact_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    guild = Guild.query.get_or_404(guild_id)
    art = Artifact.query.get(artifact_id)
    if not art:
        return jsonify({'error': 'Artifact not found'}), 404
    if not can_manage_guild_artifact_link(user, guild, art):
        return jsonify({'error': 'Forbidden'}), 403
    link_type = (request.args.get('link_type') or '').strip().lower()
    if not link_type or link_type not in GUILD_ARTIFACT_LINK_TYPES:
        return jsonify({'error': 'link_type query param required', 'allowed': sorted(GUILD_ARTIFACT_LINK_TYPES)}), 400
    row = GuildArtifactLink.query.filter_by(
        guild_id=guild.id, artifact_id=art.id, link_type=link_type
    ).first()
    if not row:
        return jsonify({'error': 'Link not found'}), 404
    rid = row.id
    db.session.delete(row)
    emit_event(
        'guild_artifact_unlinked',
        actor_type='user',
        actor_id=user['id'],
        subject_type='guild_artifact_link',
        subject_id=rid,
        layer_id=art.layer_id,
        payload={
            'guild_id': guild.id,
            'artifact_id': art.id,
            'link_type': link_type,
        },
    )
    db.session.commit()
    return jsonify({'success': True}), 200


@bp.route('/<guild_id>/members/<member_user_id>/', methods=['PATCH'])
@require_auth
def patch_guild_member_state(guild_id, member_user_id):
    """membership_state: self may set inactive only; officers may set any member (not initiator to inactive)."""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    Guild.query.get_or_404(guild_id)
    data = request.get_json(silent=True) or {}
    state = (data.get('membership_state') or '').strip().lower()
    if state not in ('active', 'inactive'):
        return jsonify({'error': 'membership_state must be active or inactive'}), 400
    m = GuildMembership.query.filter_by(guild_id=guild_id, user_id=member_user_id).first()
    if not m:
        return jsonify({'error': 'Member not found'}), 404
    if m.role == 'initiator' and state == 'inactive':
        return jsonify({'error': 'Cannot deactivate guild initiator'}), 400
    if member_user_id == user['id']:
        if state != 'inactive':
            return jsonify({'error': 'You can only set your own membership to inactive'}), 400
    elif not is_guild_officer(guild_id, user['id']):
        return jsonify({'error': 'Forbidden'}), 403
    m.membership_state = state
    db.session.commit()
    return jsonify({
        'success': True,
        'member': {'user_id': m.user_id, 'membership_state': m.membership_state},
    }), 200


@bp.route('/<guild_id>/quest-links/', methods=['GET'])
def list_guild_quest_links(guild_id):
    guild = Guild.query.get_or_404(guild_id)
    rows = GuildQuestLink.query.filter_by(guild_id=guild.id).all()
    out = []
    for row in rows:
        d = row.to_dict()
        q = row.quest
        if q:
            d['quest'] = {
                'id': q.id,
                'title': q.title,
                'layer_id': q.layer_id,
                'status': q.status,
            }
        out.append(d)
    return jsonify({'links': out, 'count': len(out)}), 200


@bp.route('/<guild_id>/quest-links/', methods=['POST'])
@require_auth
def guild_add_quest_link(guild_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    guild = Guild.query.get_or_404(guild_id)
    data = request.get_json(silent=True) or {}
    qid = data.get('quest_id')
    link_type = (data.get('link_type') or '').strip().lower()
    if not qid or not link_type:
        return jsonify({'error': 'quest_id and link_type required'}), 400
    if link_type not in GUILD_QUEST_LINK_TYPES:
        return jsonify({'error': 'Invalid link_type', 'allowed': sorted(GUILD_QUEST_LINK_TYPES)}), 400
    quest = Quest.query.get(qid)
    if not quest:
        return jsonify({'error': 'Quest not found'}), 404
    if not can_manage_guild_quest_link(user, guild, quest):
        return jsonify({'error': 'Forbidden'}), 403
    if GuildQuestLink.query.filter_by(
        guild_id=guild.id, quest_id=quest.id, link_type=link_type
    ).first():
        return jsonify({'error': 'Link already exists'}), 400
    row = GuildQuestLink(
        id=str(uuid4()),
        guild_id=guild.id,
        quest_id=quest.id,
        link_type=link_type,
        created_by_user_id=user['id'],
    )
    db.session.add(row)
    emit_event(
        'guild_quest_linked',
        actor_type='user',
        actor_id=user['id'],
        subject_type='guild_quest_link',
        subject_id=row.id,
        layer_id=quest.layer_id,
        payload={
            'guild_id': guild.id,
            'guild_name': guild.name,
            'quest_id': quest.id,
            'link_type': link_type,
        },
    )
    db.session.commit()
    return jsonify({'success': True, 'link': row.to_dict()}), 201


@bp.route('/<guild_id>/quest-links/<quest_id>/', methods=['DELETE'])
@require_auth
def guild_remove_quest_link(guild_id, quest_id):
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Authentication required'}), 401
    guild = Guild.query.get_or_404(guild_id)
    quest = Quest.query.get(quest_id)
    if not quest:
        return jsonify({'error': 'Quest not found'}), 404
    if not can_manage_guild_quest_link(user, guild, quest):
        return jsonify({'error': 'Forbidden'}), 403
    link_type = (request.args.get('link_type') or '').strip().lower()
    if not link_type or link_type not in GUILD_QUEST_LINK_TYPES:
        return jsonify({'error': 'link_type query param required', 'allowed': sorted(GUILD_QUEST_LINK_TYPES)}), 400
    row = GuildQuestLink.query.filter_by(
        guild_id=guild.id, quest_id=quest.id, link_type=link_type
    ).first()
    if not row:
        return jsonify({'error': 'Link not found'}), 404
    rid = row.id
    lid = quest.layer_id
    db.session.delete(row)
    emit_event(
        'guild_quest_unlinked',
        actor_type='user',
        actor_id=user['id'],
        subject_type='guild_quest_link',
        subject_id=rid,
        layer_id=lid,
        payload={'guild_id': guild.id, 'quest_id': quest.id, 'link_type': link_type},
    )
    db.session.commit()
    return jsonify({'success': True}), 200
