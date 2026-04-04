"""Guilds API: guild CRUD, members, invitations."""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from extensions import db
from models import Guild, GuildMembership, GuildInvitation, User
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
