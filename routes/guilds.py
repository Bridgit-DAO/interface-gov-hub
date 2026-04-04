"""Guilds API: guild CRUD, members, invitations."""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from uuid import uuid4

from extensions import db
from models import (
    Artifact,
    Guild,
    GuildArtifactLink,
    GuildInvitation,
    GuildLayerLink,
    GuildMembership,
    Layer,
    User,
)
from services.events import emit_event
from services.guild_phase1 import (
    GUILD_ARTIFACT_LINK_TYPES,
    can_manage_guild_artifact_link,
    can_manage_guild_layer_link,
)
from services.identity import get_current_user, require_auth
from services.avatar import get_avatar_url
from services.utils import create_slug, generate_guild_id, generate_invitation_token

bp = Blueprint('guilds', __name__, url_prefix='/api/guilds')


def _guild_detail(guild_id):
    """Shared implementation for guild detail with members."""
    guild = Guild.query.get_or_404(guild_id)
    memberships = GuildMembership.query.filter_by(guild_id=guild_id).all()
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
    query = query.order_by(Guild.created_at.desc())
    guilds = query.all()
    result = []
    for g in guilds:
        d = g.to_dict()
        d['members_count'] = GuildMembership.query.filter_by(guild_id=g.id).count()
        result.append(d)
    return jsonify({'guilds': result, 'count': len(result)})


@bp.route('/', methods=['POST'])
@require_auth
def create_guild():
    """Create a new guild (instant registration)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json()
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
        status='active'
    )
    membership = GuildMembership(
        guild_id=guild_id,
        user_id=current_user['id'],
        role='initiator'
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

    invitation_link = f"https://rfc.themetalayer.org/guilds/invite/{token}/"

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
