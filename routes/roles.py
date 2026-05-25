"""Roles API: clusters, roles, claims, badges, badge-skins, badge-cycle, one-time-badges, role-images."""
import os
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request, send_from_directory, current_app, abort
from sqlalchemy import func

from extensions import db
from models import (
    Layer, User, Role, Cluster, Claim, Badge, BadgeSkin, BadgeCycle, OneTimeBadge,
    RoleImage, RoleImageVote, StatusChange, Vote,
)
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin
from services.events import emit_event
from services.utils import (
    create_slug, _is_uuid_like,
    generate_cluster_id, generate_role_id, generate_claim_id, generate_badge_id, generate_role_image_id,
)
from services.images import upload_image_600x600, update_image_vote_counts

bp = Blueprint('roles', __name__, url_prefix='/api')


def _resolve_claim(claim_id):
    """Resolve claim by id or public_id UUID."""
    if _is_uuid_like(claim_id):
        return Claim.query.filter_by(public_id=claim_id).first_or_404()
    return Claim.query.get_or_404(claim_id)


def _role_image_upload_folder():
    return current_app.config.get('ROLE_IMAGE_UPLOAD_FOLDER', '/home/ubuntu/data-tracker/uploads/role_images')


# ============================================================================
# Badge Skins
# ============================================================================

@bp.route('/badge-skins/', methods=['GET'])
def list_badge_skins():
    """List all available badge skins."""
    skins = BadgeSkin.query.order_by(BadgeSkin.name).all()
    return jsonify({'skins': [s.to_dict() for s in skins]})


# ============================================================================
# BadgeCycle
# ============================================================================

@bp.route('/roles/<role_slug>/badge-cycle/', methods=['GET'])
def get_role_badge_cycle(role_slug):
    """Return the active or most-recent BadgeCycle for a role, plus computed upcoming dates."""
    role = Role.query.filter_by(role_slug=role_slug).first_or_404()
    cycle = (BadgeCycle.query
             .filter_by(entity_type='role', entity_id=role_slug)
             .order_by(BadgeCycle.created_at.desc())
             .first())
    today = date.today()
    earliest = role.badge_earliest_start
    sub_days = role.badge_submission_days or 14
    delay_days = role.badge_delay_days or 2
    vote_days = role.badge_voting_days or 7
    upcoming = None
    if role.badge_enabled:
        proj_start = earliest if (earliest and earliest > today) else today
        days_until = (earliest - today).days if (earliest and earliest > today) else 0
        proj_sub_end = proj_start + timedelta(days=sub_days)
        proj_vote_start = proj_sub_end + timedelta(days=delay_days)
        proj_vote_end = proj_vote_start + timedelta(days=vote_days)
        upcoming = {
            'badge_earliest_start': earliest.isoformat() if earliest else None,
            'days_until_start': days_until,
            'badge_submission_days': sub_days,
            'badge_delay_days': delay_days,
            'badge_voting_days': vote_days,
            'estimated_first_submission': proj_start.isoformat(),
            'estimated_submission_end': proj_sub_end.isoformat(),
            'estimated_voting_start': proj_vote_start.isoformat(),
            'estimated_voting_end': proj_vote_end.isoformat(),
            'badge_cycle_spacing_days': role.badge_cycle_spacing_days or 365,
            'badge_end_date': role.badge_end_date.isoformat() if role.badge_end_date else None,
            'badge_end_at_next_closing': role.badge_end_at_next_closing,
            'voting_regular': role.badge_voting_regular,
            'voting_time_weighted': role.badge_voting_time_weighted,
            'voting_quadratic': role.badge_voting_quadratic,
        }
    current_user = get_current_user()
    project = Layer.query.get(role.layer_id)
    can_manage = bool(project and current_user and is_layer_admin(project, current_user))
    return jsonify({
        'badge_enabled': role.badge_enabled,
        'role_id': role.id,
        'cycle': cycle.to_dict() if cycle else None,
        'upcoming': upcoming,
        'can_manage': can_manage,
    })


@bp.route('/roles/<role_slug>/badge-cycle/start/', methods=['POST'])
@require_auth
def start_role_badge_cycle(role_slug):
    """Create a new BadgeCycle for a role (project admin only)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    role = Role.query.filter_by(role_slug=role_slug).first_or_404()
    project = Layer.query.get_or_404(role.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Layer admin access required'}), 403
    if not role.badge_enabled:
        return jsonify({'error': 'Badges are not enabled for this role'}), 400
    active = (BadgeCycle.query
              .filter_by(entity_type='role', entity_id=role_slug)
              .filter(BadgeCycle.status.in_(['submission', 'delay', 'voting']))
              .first())
    if active:
        return jsonify({'error': 'An active cycle already exists', 'cycle': active.to_dict()}), 409
    today = date.today()
    earliest = role.badge_earliest_start
    if earliest and earliest > today:
        return jsonify({'error': f'Badge cycle cannot start before {earliest.isoformat()}'}), 400
    sub_days = role.badge_submission_days or 14
    delay_days = role.badge_delay_days or 2
    vote_days = role.badge_voting_days or 7
    now_dt = datetime.utcnow()
    sub_end = now_dt + timedelta(days=sub_days)
    vote_start = sub_end + timedelta(days=delay_days)
    vote_end = vote_start + timedelta(days=vote_days)
    cycle = BadgeCycle(
        entity_type='role',
        entity_id=role_slug,
        layer_id=role.layer_id,
        first_submission_at=now_dt,
        submission_ends_at=sub_end,
        voting_starts_at=vote_start,
        voting_ends_at=vote_end,
        status='submission',
    )
    db.session.add(cycle)
    db.session.commit()
    return jsonify({'success': True, 'cycle': cycle.to_dict()}), 201


# ============================================================================
# One-Time Badges
# ============================================================================

@bp.route('/one-time-badges/', methods=['GET'])
def list_one_time_badges():
    """List one-time badges, optionally filtered by layer."""
    layer_id = request.args.get('layer_id') or request.args.get('project_id')
    q = OneTimeBadge.query
    if layer_id:
        q = q.filter_by(layer_id=layer_id)
    badges = q.order_by(OneTimeBadge.earliest_start.asc()).all()
    return jsonify({'badges': [b.to_dict() for b in badges]})


@bp.route('/one-time-badges/', methods=['POST'])
@require_auth
def create_one_time_badge():
    """Create a new one-time badge (project admin only)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    data = request.get_json() or {}
    layer_id_val = (data.get('layer_id') or data.get('project_id') or '').strip()
    if not layer_id_val:
        return jsonify({'error': 'layer_id required'}), 400
    project = Layer.query.get(layer_id_val)
    if not project:
        return jsonify({'error': 'Layer not found'}), 404
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Layer admin required'}), 403
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'title required'}), 400
    earliest_raw = data.get('earliest_start')
    try:
        earliest = date.fromisoformat(earliest_raw) if earliest_raw else date.today()
    except ValueError:
        return jsonify({'error': 'Invalid earliest_start date'}), 400
    otb = OneTimeBadge(
        layer_id=layer_id_val,
        title=title,
        description=data.get('description', ''),
        earliest_start=earliest,
        quantity=int(data.get('quantity', 1)),
        submission_days=int(data.get('submission_days', 14)),
        delay_days=int(data.get('delay_days', 2)),
        voting_days=int(data.get('voting_days', 7)),
        voting_regular=True,
        voting_time_weighted=bool(data.get('voting_time_weighted', False)),
        voting_quadratic=bool(data.get('voting_quadratic', False)),
        badge_skin_id=data.get('badge_skin_id') or None,
        status='draft',
        created_by_id=current_user['id'],
    )
    db.session.add(otb)
    db.session.commit()
    return jsonify({'success': True, 'badge': otb.to_dict()}), 201


@bp.route('/one-time-badges/<badge_id>/', methods=['GET'])
def get_one_time_badge(badge_id):
    otb = OneTimeBadge.query.get_or_404(badge_id)
    return jsonify({'badge': otb.to_dict()})


@bp.route('/one-time-badges/<badge_id>/', methods=['PATCH'])
@require_auth
def update_one_time_badge(badge_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    otb = OneTimeBadge.query.get_or_404(badge_id)
    project = Layer.query.get(otb.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Layer admin required'}), 403
    data = request.get_json() or {}
    for f in ['title', 'description', 'status']:
        if f in data:
            setattr(otb, f, data[f])
    for f in ['quantity', 'submission_days', 'delay_days', 'voting_days']:
        if f in data and data[f] is not None:
            setattr(otb, f, int(data[f]))
    for f in ['voting_time_weighted', 'voting_quadratic']:
        if f in data:
            setattr(otb, f, bool(data[f]))
    if 'earliest_start' in data:
        val = data['earliest_start']
        if val:
            try:
                otb.earliest_start = date.fromisoformat(val)
            except ValueError:
                return jsonify({'error': 'Invalid earliest_start'}), 400
    if 'badge_skin_id' in data:
        otb.badge_skin_id = data['badge_skin_id'] or None
    db.session.commit()
    return jsonify({'success': True, 'badge': otb.to_dict()})


@bp.route('/one-time-badges/<badge_id>/', methods=['DELETE'])
@require_auth
def delete_one_time_badge(badge_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    otb = OneTimeBadge.query.get_or_404(badge_id)
    project = Layer.query.get(otb.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Layer admin required'}), 403
    db.session.delete(otb)
    db.session.commit()
    return jsonify({'success': True})


# ============================================================================
# Role Images
# ============================================================================

@bp.route('/role-images/roles-with-stats/', methods=['GET'])
def role_images_roles_with_stats():
    """List roles with image count and vote count for role-images gallery page."""
    layer_id = request.args.get('layer_id') or request.args.get('project_id')
    stats_subq = db.session.query(
        RoleImage.role_slug,
        func.count(RoleImage.id).label('image_count'),
        func.coalesce(func.sum(RoleImage.upvotes + RoleImage.downvotes), 0).label('vote_count')
    ).group_by(RoleImage.role_slug).subquery()
    query = db.session.query(
        Role,
        stats_subq.c.image_count,
        stats_subq.c.vote_count
    ).outerjoin(stats_subq, Role.role_slug == stats_subq.c.role_slug)
    if layer_id:
        query = query.filter(Role.layer_id == layer_id)
    query = query.order_by(Role.layer_id, Role.order, Role.title_guild)
    rows = query.all()
    result = []
    for row in rows:
        role, image_count, vote_count = row
        d = role.to_dict()
        d['image_count'] = image_count or 0
        d['vote_count'] = int(vote_count or 0)
        d['layer_name'] = role.layer.name if role.layer else None
        d['layer_slug'] = role.layer.slug if role.layer else None
        result.append(d)
    return jsonify({'roles': result, 'count': len(result)})


@bp.route('/roles/<role_slug>/images/', methods=['GET'])
def list_role_images(role_slug):
    """List role image proposals with vote counts."""
    sort_by = request.args.get('sort', 'net_score')
    include_hidden = request.args.get('include_hidden', 'false').lower() == 'true'
    query = RoleImage.query.filter_by(role_slug=role_slug)
    current_user = get_current_user()
    if not (current_user and current_user.get('role') == 'admin') and not include_hidden:
        query = query.filter_by(is_hidden=False)
    if sort_by == 'date':
        query = query.order_by(RoleImage.submitted_at.desc())
    elif sort_by == 'upvotes':
        query = query.order_by(RoleImage.upvotes.desc())
    else:
        query = query.order_by(RoleImage.net_score.desc(), RoleImage.submitted_at.desc())
    images = query.all()
    result = []
    for img in images:
        img_dict = img.to_dict()
        if current_user:
            vote = RoleImageVote.query.filter_by(image_id=img.id, user_id=current_user['id']).first()
            img_dict['user_vote'] = vote.value if vote else None
        else:
            img_dict['user_vote'] = None
        result.append(img_dict)
    return jsonify({'images': result, 'count': len(result)})


@bp.route('/roles/<role_slug>/images/', methods=['POST'])
@require_auth
def submit_role_image(role_slug):
    """Submit a role image proposal."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    recent_submissions = RoleImage.query.filter(
        RoleImage.submitted_by_id == current_user['id'],
        RoleImage.submitted_at >= datetime.utcnow() - timedelta(days=1)
    ).count()
    if recent_submissions >= 10:
        return jsonify({'error': 'Rate limit exceeded. Maximum 10 image proposals per day.'}), 429
    source_type = request.form.get('source_type')
    if not source_type or source_type not in ['upload', 'url', 'ordinal']:
        return jsonify({'error': 'Invalid source_type. Must be upload, url, or ordinal.'}), 400
    image_id = generate_role_image_id()
    image = RoleImage(
        id=image_id,
        role_slug=role_slug,
        source_type=source_type,
        submitted_by_id=current_user['id']
    )
    upload_folder = _role_image_upload_folder()
    if source_type == 'upload':
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        file = request.files['file']
        image_url, err = upload_image_600x600(
            file, upload_folder, '/uploads/role_images', filename_prefix=image_id
        )
        if err:
            return jsonify({'error': err}), 400
        image.file_path = os.path.join(upload_folder, image_url.split('/')[-1])
        image.image_url = image_url
    elif source_type == 'url':
        image_url = request.form.get('image_url')
        if not image_url:
            return jsonify({'error': 'image_url required for url source type'}), 400
        image.image_url = image_url
    elif source_type == 'ordinal':
        inscription_id = request.form.get('inscription_id')
        if not inscription_id:
            return jsonify({'error': 'inscription_id required for ordinal source type'}), 400
        image.chain = request.form.get('chain', 'bitcoin')
        image.inscription_id = inscription_id
        image.content_type = request.form.get('content_type', 'image/png')
        image.image_url = f"https://ordinals.com/content/{inscription_id}"
    db.session.add(image)
    db.session.commit()
    return jsonify({'success': True, 'image': image.to_dict()}), 201


@bp.route('/role-images/<image_id>/', methods=['GET'])
def get_role_image(image_id):
    image = RoleImage.query.get_or_404(image_id)
    current_user = get_current_user()
    if image.is_hidden and not (current_user and current_user.get('role') == 'admin'):
        return jsonify({'error': 'Image not found'}), 404
    img_dict = image.to_dict()
    if current_user:
        vote = RoleImageVote.query.filter_by(image_id=image.id, user_id=current_user['id']).first()
        img_dict['user_vote'] = vote.value if vote else None
    else:
        img_dict['user_vote'] = None
    return jsonify(img_dict)


@bp.route('/role-images/<image_id>/vote/', methods=['POST'])
@require_auth
def vote_role_image(image_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    image = RoleImage.query.get_or_404(image_id)
    data = request.get_json()
    vote_value = data.get('value')
    if vote_value not in [1, -1]:
        return jsonify({'error': 'Invalid vote value. Must be 1 (upvote) or -1 (downvote).'}), 400
    existing_vote = RoleImageVote.query.filter_by(image_id=image_id, user_id=current_user['id']).first()
    if existing_vote:
        existing_vote.value = vote_value
        existing_vote.updated_at = datetime.utcnow()
    else:
        vote = RoleImageVote(image_id=image_id, user_id=current_user['id'], value=vote_value)
        db.session.add(vote)
    db.session.commit()
    update_image_vote_counts(image_id)
    image = RoleImage.query.get(image_id)
    return jsonify({'success': True, 'image': image.to_dict()})


@bp.route('/role-images/<image_id>/vote/', methods=['DELETE'])
@require_auth
def remove_vote_role_image(image_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    vote = RoleImageVote.query.filter_by(image_id=image_id, user_id=current_user['id']).first()
    if not vote:
        return jsonify({'error': 'No vote found'}), 404
    db.session.delete(vote)
    db.session.commit()
    update_image_vote_counts(image_id)
    image = RoleImage.query.get(image_id)
    return jsonify({'success': True, 'image': image.to_dict()})


@bp.route('/role-images/<image_id>/promote/', methods=['POST'])
@require_auth
def promote_role_image(image_id):
    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    image = RoleImage.query.get_or_404(image_id)
    RoleImage.query.filter_by(role_slug=image.role_slug, is_primary=True).update({'is_primary': False})
    image.is_primary = True
    image.promoted_by_id = current_user['id']
    image.promoted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'success': True, 'image': image.to_dict()})


@bp.route('/role-images/<image_id>/hide/', methods=['POST'])
@require_auth
def hide_role_image(image_id):
    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    image = RoleImage.query.get_or_404(image_id)
    image.is_hidden = True
    db.session.commit()
    return jsonify({'success': True, 'image': image.to_dict()})


@bp.route('/role-images/<image_id>/unhide/', methods=['POST'])
@require_auth
def unhide_role_image(image_id):
    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    image = RoleImage.query.get_or_404(image_id)
    image.is_hidden = False
    db.session.commit()
    return jsonify({'success': True, 'image': image.to_dict()})


@bp.route('/role-images/<image_id>/', methods=['DELETE'])
@require_auth
def delete_role_image(image_id):
    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    image = RoleImage.query.get_or_404(image_id)
    RoleImageVote.query.filter_by(image_id=image_id).delete()
    if image.file_path and os.path.exists(image.file_path):
        try:
            os.remove(image.file_path)
        except Exception as e:
            current_app.logger.error(f"Failed to delete file {image.file_path}: {e}")
    db.session.delete(image)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/role-images/<image_id>/note/', methods=['PATCH'])
@require_auth
def update_role_image_note(image_id):
    current_user = get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        return jsonify({'error': 'Admin access required'}), 403
    image = RoleImage.query.get_or_404(image_id)
    data = request.get_json()
    image.admin_note = data.get('admin_note', '')
    db.session.commit()
    return jsonify({'success': True, 'image': image.to_dict()})


# Separate blueprint for /uploads/role_images (no /api prefix)
bp_uploads = Blueprint('roles_uploads', __name__, url_prefix='')


@bp_uploads.route('/uploads/role_images/<filename>')
def serve_role_image(filename):
    """Serve uploaded role images."""
    folder = current_app.config.get('ROLE_IMAGE_UPLOAD_FOLDER', '/home/ubuntu/data-tracker/uploads/role_images')
    return send_from_directory(folder, filename)


# ============================================================================
# Clusters
# ============================================================================

@bp.route('/layers/<layer_id>/clusters/', methods=['GET'])
def list_clusters(layer_id):
    Layer.query.get_or_404(layer_id)
    status = request.args.get('status')
    include_roles = request.args.get('include_roles', '').lower() in ('1', 'true', 'yes')
    query = Cluster.query.filter_by(layer_id=layer_id)
    if status:
        query = query.filter_by(status=status)
    else:
        query = query.filter(Cluster.status != 'archived')
    clusters = query.order_by(Cluster.order, Cluster.name).all()
    result = []
    for c in clusters:
        d = c.to_dict()
        if include_roles:
            roles = Role.query.filter_by(cluster_id=c.id).order_by(Role.order, Role.title_guild).all()
            d['roles'] = [r.to_dict() for r in roles]
        result.append(d)
    return jsonify({'clusters': result, 'count': len(result)})


@bp.route('/layers/<layer_id>/clusters/', methods=['POST'])
@require_auth
def create_cluster(layer_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    project = Layer.query.get_or_404(layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project initiator or admins can create clusters'}), 403
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    order = data.get('order', 0)
    if not name:
        return jsonify({'error': 'Cluster name is required'}), 400
    cluster_slug = create_slug(name)
    existing = Cluster.query.filter_by(layer_id=layer_id, cluster_slug=cluster_slug).first()
    if existing:
        counter = 1
        while existing:
            cluster_slug = f"{create_slug(name)}-{counter}"
            existing = Cluster.query.filter_by(layer_id=layer_id, cluster_slug=cluster_slug).first()
            counter += 1
    cluster_id = generate_cluster_id()
    cluster = Cluster(
        id=cluster_id,
        layer_id=layer_id,
        cluster_slug=cluster_slug,
        name=name,
        description=description if description else None,
        order=order,
        created_by_id=current_user['id']
    )
    db.session.add(cluster)
    db.session.commit()
    return jsonify({'success': True, 'cluster': cluster.to_dict()}), 201


@bp.route('/clusters/<cluster_id>/', methods=['GET'])
def get_cluster(cluster_id):
    cluster = Cluster.query.get_or_404(cluster_id)
    d = cluster.to_dict()
    d['roles_count'] = Role.query.filter_by(cluster_id=cluster_id).count()
    return jsonify({'cluster': d})


@bp.route('/clusters/<cluster_id>/', methods=['PATCH'])
@require_auth
def update_cluster(cluster_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    cluster = Cluster.query.get_or_404(cluster_id)
    project = Layer.query.get_or_404(cluster.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project initiator or admins can update clusters'}), 403
    data = request.get_json()
    if 'name' in data:
        name = data['name'].strip()
        if name:
            cluster.name = name
            new_slug = create_slug(name)
            if new_slug != cluster.cluster_slug:
                existing = Cluster.query.filter_by(layer_id=cluster.layer_id, cluster_slug=new_slug).filter(Cluster.id != cluster_id).first()
                if not existing:
                    cluster.cluster_slug = new_slug
    if 'description' in data:
        cluster.description = data['description'].strip() if data['description'] else None
    if 'order' in data:
        cluster.order = data['order']
    if 'status' in data and data['status'] in ['active', 'archived']:
        old_status = cluster.status
        cluster.status = data['status']
        if old_status != cluster.status:
            db.session.add(StatusChange(
                entity_type='cluster', entity_id=cluster_id, field_name='status',
                from_value=old_status, to_value=cluster.status, changed_by_id=current_user['id']
            ))
    db.session.commit()
    return jsonify({'success': True, 'cluster': cluster.to_dict()})


@bp.route('/clusters/<cluster_id>/', methods=['DELETE'])
@require_auth
def delete_cluster(cluster_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    cluster = Cluster.query.get_or_404(cluster_id)
    project = Layer.query.get_or_404(cluster.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project initiator or admins can archive clusters'}), 403
    old_status = cluster.status
    cluster.status = 'archived'
    db.session.add(StatusChange(
        entity_type='cluster', entity_id=cluster_id, field_name='status',
        from_value=old_status, to_value='archived', changed_by_id=current_user['id']
    ))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Cluster archived'})


@bp.route('/clusters/<cluster_id>/roles/', methods=['GET'])
def list_cluster_roles(cluster_id):
    Cluster.query.get_or_404(cluster_id)
    status = request.args.get('status')
    query = Role.query.filter_by(cluster_id=cluster_id)
    if status:
        query = query.filter_by(status=status)
    roles = query.order_by(Role.order, Role.title_guild).all()
    return jsonify({'roles': [r.to_dict() for r in roles], 'count': len(roles)})


# ============================================================================
# Roles
# ============================================================================

@bp.route('/layers/<layer_id>/roles/', methods=['GET'])
def list_roles(layer_id):
    Layer.query.get_or_404(layer_id)
    status = request.args.get('status')
    cluster_id = request.args.get('cluster_id')
    public_only = request.args.get('public_only', 'false').lower() == 'true'
    query = Role.query.filter_by(layer_id=layer_id)
    if status:
        query = query.filter_by(status=status)
    if cluster_id:
        query = query.filter_by(cluster_id=cluster_id)
    if public_only:
        query = query.filter_by(public_visible=True)
    roles = query.order_by(Role.order, Role.title_guild).all()
    return jsonify({'roles': [r.to_dict() for r in roles], 'count': len(roles)})


@bp.route('/layers/<layer_id>/roles/', methods=['POST'])
@require_auth
def create_role(layer_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    project = Layer.query.get_or_404(layer_id)
    data = request.get_json()
    title_guild = data.get('title_guild', '').strip()
    title_operational = data.get('title_operational', '').strip()
    description = data.get('description', '').strip()
    cluster_id = data.get('cluster_id')
    image_url = data.get('image_url', '').strip()
    order = data.get('order', 0)
    if not title_guild:
        return jsonify({'error': 'Guild title is required'}), 400
    if not description:
        return jsonify({'error': 'Description is required'}), 400
    if cluster_id:
        cluster = Cluster.query.filter_by(id=cluster_id, layer_id=layer_id).first()
        if not cluster:
            return jsonify({'error': 'Invalid cluster for this project'}), 400
    role_slug = create_slug(title_guild)
    existing = Role.query.filter_by(layer_id=layer_id, role_slug=role_slug).first()
    if existing:
        counter = 1
        while existing:
            role_slug = f"{create_slug(title_guild)}-{counter}"
            existing = Role.query.filter_by(layer_id=layer_id, role_slug=role_slug).first()
            counter += 1
    role_id = generate_role_id()
    role = Role(
        id=role_id,
        layer_id=layer_id,
        role_slug=role_slug,
        title_guild=title_guild,
        title_operational=title_operational if title_operational else None,
        description=description,
        image_url=image_url if image_url else None,
        cluster_id=cluster_id if cluster_id else None,
        order=order,
        status='draft',
        created_by_id=current_user['id']
    )
    for f in ['claim_requires_approval', 'requires_election', 'badge_enabled', 'badge_requires_approval', 'public_visible']:
        if f in data:
            setattr(role, f, data[f])
    db.session.add(role)
    db.session.commit()
    return jsonify({'success': True, 'role': role.to_dict()}), 201


@bp.route('/layers/<layer_id>/roles/import/', methods=['POST'])
@require_auth
def import_roles(layer_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    project = Layer.query.get_or_404(layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project initiator or admins can import roles'}), 403
    data = request.get_json()
    roles_data = data.get('roles', [])
    if not roles_data or not isinstance(roles_data, list):
        return jsonify({'error': 'Invalid roles data'}), 400
    imported_roles = []
    errors = []
    for idx, role_data in enumerate(roles_data):
        try:
            title_guild = role_data.get('title_guild', '').strip()
            description = role_data.get('description', '').strip()
            if not title_guild or not description:
                errors.append(f"Role {idx}: Missing title_guild or description")
                continue
            role_slug = create_slug(title_guild)
            existing = Role.query.filter_by(layer_id=layer_id, role_slug=role_slug).first()
            if existing:
                counter = 1
                while existing:
                    role_slug = f"{create_slug(title_guild)}-{counter}"
                    existing = Role.query.filter_by(layer_id=layer_id, role_slug=role_slug).first()
                    counter += 1
            role_id = generate_role_id()
            role = Role(
                id=role_id,
                layer_id=layer_id,
                role_slug=role_slug,
                title_guild=title_guild,
                title_operational=role_data.get('title_operational'),
                description=description,
                image_url=role_data.get('image_url'),
                cluster_id=role_data.get('cluster_id'),
                order=role_data.get('order', 0),
                status='draft',
                created_by_id=current_user['id']
            )
            db.session.add(role)
            imported_roles.append(role)
        except Exception as e:
            errors.append(f"Role {idx}: {str(e)}")
    db.session.commit()
    return jsonify({'success': True, 'imported_count': len(imported_roles), 'roles': [r.to_dict() for r in imported_roles], 'errors': errors}), 201


@bp.route('/roles/<role_id>/', methods=['GET'])
def get_role(role_id):
    if _is_uuid_like(role_id):
        role = Role.query.filter_by(id=role_id).first() or Role.query.filter_by(public_id=role_id).first()
        if not role:
            abort(404)
    else:
        role = Role.query.get_or_404(role_id)
    role_dict = role.to_dict()
    role_dict['active_claims_count'] = Claim.query.filter_by(role_id=role.id, status='active').count()
    role_dict['cluster_name'] = role.cluster.name if role.cluster_id and role.cluster else None
    current_user = get_current_user()
    project = Layer.query.get(role.layer_id)
    role_dict['can_edit'] = bool(project and current_user and is_layer_admin(project, current_user))
    if getattr(role, 'requires_election', False):
        active_vote = Vote.query.filter_by(role_id=role.id, vote_type='election').filter(Vote.status.in_(['scheduled', 'active'])).first()
        role_dict['active_election'] = {'vote_id': active_vote.id, 'public_id': active_vote.public_id, 'title': active_vote.title} if active_vote else None
    else:
        role_dict['active_election'] = None
    return jsonify(role_dict)


@bp.route('/roles/<role_id>/', methods=['PATCH'])
@require_auth
def update_role(role_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    role = Role.query.get_or_404(role_id)
    project = Layer.query.get_or_404(role.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project initiator or admins can update roles'}), 403
    data = request.get_json()
    if 'title_guild' in data:
        t = data['title_guild'].strip()
        if t:
            role.title_guild = t
    if 'title_operational' in data:
        role.title_operational = data['title_operational'].strip() if data['title_operational'] else None
    if 'description' in data:
        d = data['description'].strip()
        if d:
            role.description = d
    if 'image_url' in data:
        role.image_url = data['image_url'].strip() if data['image_url'] else None
    if 'cluster_id' in data:
        if data['cluster_id']:
            cluster = Cluster.query.filter_by(id=data['cluster_id'], layer_id=role.layer_id).first()
            if cluster:
                role.cluster_id = data['cluster_id']
        else:
            role.cluster_id = None
    for f in ['order', 'public_visible', 'claim_requires_approval', 'requires_election', 'badge_enabled', 'badge_requires_approval']:
        if f in data:
            setattr(role, f, data[f])
    for f in ['badge_submission_days', 'badge_voting_days', 'badge_delay_days', 'badge_cycle_spacing_days']:
        if f in data:
            setattr(role, f, int(data[f]) if data[f] is not None else None)
    for f in ['badge_earliest_start', 'badge_end_date']:
        if f in data:
            val = data[f]
            if val:
                try:
                    setattr(role, f, date.fromisoformat(val))
                except (ValueError, TypeError):
                    pass
            else:
                setattr(role, f, None)
    for f in ['badge_end_at_next_closing', 'badge_voting_regular', 'badge_voting_time_weighted', 'badge_voting_quadratic']:
        if f in data:
            setattr(role, f, bool(data[f]))
    if 'badge_skin_id' in data:
        role.badge_skin_id = data['badge_skin_id'] or None
    db.session.commit()
    return jsonify({'success': True, 'role': role.to_dict()})


@bp.route('/roles/<role_id>/approve/', methods=['POST'])
@require_auth
def approve_role(role_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    if current_user.get('role') not in ['admin', 'editor']:
        return jsonify({'error': 'Admin access required'}), 403
    role = Role.query.get_or_404(role_id)
    data = request.get_json()
    approve = data.get('approve', True)
    old_status = role.status
    if approve:
        role.status = 'approved'
        role.approved_by_id = current_user['id']
        role.approved_at = datetime.utcnow()
    else:
        role.status = 'draft'
        role.approved_by_id = None
        role.approved_at = None
    db.session.add(StatusChange(
        entity_type='role', entity_id=role_id, field_name='status',
        from_value=old_status, to_value=role.status, note=data.get('note'), changed_by_id=current_user['id']
    ))
    db.session.commit()
    return jsonify({'success': True, 'role': role.to_dict()})


@bp.route('/roles/<role_id>/status/', methods=['POST'])
@require_auth
def change_role_status(role_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    role = Role.query.get_or_404(role_id)
    project = Layer.query.get_or_404(role.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project initiator or admins can change role status'}), 403
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['draft', 'approved', 'deprecated', 'archived']:
        return jsonify({'error': 'Invalid status'}), 400
    old_status = role.status
    role.status = new_status
    db.session.add(StatusChange(
        entity_type='role', entity_id=role_id, field_name='status',
        from_value=old_status, to_value=new_status, note=data.get('note'), changed_by_id=current_user['id']
    ))
    db.session.commit()
    return jsonify({'success': True, 'role': role.to_dict()})


@bp.route('/roles/<role_id>/claims/', methods=['GET'])
def list_role_claims(role_id):
    Role.query.get_or_404(role_id)
    status = request.args.get('status')
    query = Claim.query.filter_by(role_id=role_id)
    if status:
        query = query.filter_by(status=status)
    claims = query.order_by(Claim.created_at.desc()).all()
    result = []
    for c in claims:
        d = c.to_dict()
        if c.claimant:
            d['claimant_name'] = c.claimant.displayName or c.claimant.username or c.claimant.name
            d['claimant_username'] = c.claimant.username
        else:
            d['claimant_name'] = d['claimant_username'] = None
        result.append(d)
    return jsonify({'claims': result, 'count': len(result)})


# ============================================================================
# Claims
# ============================================================================

@bp.route('/layers/<layer_id>/claims/', methods=['GET'])
def list_claims(layer_id):
    Layer.query.get_or_404(layer_id)
    status = request.args.get('status')
    role_id = request.args.get('role_id')
    claimant_id = request.args.get('claimant_id')
    query = Claim.query.filter_by(layer_id=layer_id)
    if status:
        query = query.filter_by(status=status)
    if role_id:
        query = query.filter_by(role_id=role_id)
    if claimant_id:
        query = query.filter_by(claimant_id=str(claimant_id))
    claims = query.order_by(Claim.created_at.desc()).all()
    result = []
    for c in claims:
        d = c.to_dict()
        if c.role:
            d['role_name'] = c.role.title_operational or c.role.title_guild
            d['role_slug'] = c.role.role_slug
        else:
            d['role_name'] = d['role_slug'] = None
        if c.claimant:
            d['claimant_name'] = c.claimant.displayName or c.claimant.username or getattr(c.claimant, 'name', None)
            d['claimant_username'] = c.claimant.username
        else:
            d['claimant_name'] = d['claimant_username'] = None
        result.append(d)
    return jsonify({'claims': result, 'count': len(result)})


@bp.route('/roles/<role_id>/claims/', methods=['POST'])
@require_auth
def create_claim(role_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    role = Role.query.get_or_404(role_id)
    if role.status != 'approved':
        return jsonify({'error': 'Can only claim approved roles'}), 400
    data = request.get_json()
    intent = data.get('intent', '').strip()
    evidence_links = data.get('evidence_links', [])
    term_duration_months = data.get('term_duration_months')
    if term_duration_months is not None:
        months = max(1, min(12, int(term_duration_months) if term_duration_months else 3))
        term_duration_days = {1: 30, 3: 90, 6: 182, 12: 365}.get(months, months * 30)
    else:
        term_duration_days = data.get('term_duration_days')
    existing_claim = Claim.query.filter_by(role_id=role_id, claimant_id=current_user['id'], status='active').first()
    if existing_claim:
        return jsonify({'error': 'You already have an active claim for this role'}), 400
    claim_id = generate_claim_id()
    approval_required = role.claim_requires_approval
    initial_status = 'pending_approval' if approval_required else 'active'
    claim = Claim(
        id=claim_id,
        layer_id=role.layer_id,
        role_id=role_id,
        claimant_id=current_user['id'],
        intent=intent if intent else None,
        evidence_links=evidence_links,
        status=initial_status,
        approval_required=approval_required
    )
    if term_duration_days:
        claim.term_start = datetime.utcnow().date()
        claim.term_duration_days = term_duration_days
        claim.term_end = claim.term_start + timedelta(days=term_duration_days)
        claim.term_status = 'active'
    db.session.add(claim)
    emit_event('role_claimed', actor_type='user', actor_id=current_user['id'],
               subject_type='claim', subject_id=claim.id, layer_id=role.layer_id,
               payload={'role_id': role_id, 'status': initial_status})
    db.session.commit()
    return jsonify({'success': True, 'claim': claim.to_dict()}), 201


@bp.route('/claims/<claim_id>/', methods=['GET'])
def get_claim(claim_id):
    claim = _resolve_claim(claim_id)
    d = claim.to_dict()
    role = Role.query.get(claim.role_id)
    if role:
        d['role'] = {'id': role.id, 'title_guild': role.title_guild, 'title_operational': role.title_operational}
    claimant = User.query.get(claim.claimant_id)
    if claimant:
        d['claimant'] = {'id': claimant.id, 'username': claimant.username, 'name': claimant.name}
    return jsonify(d)


@bp.route('/claims/<claim_id>/', methods=['PATCH'])
@require_auth
def update_claim(claim_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    claim = _resolve_claim(claim_id)
    if claim.claimant_id != current_user['id']:
        return jsonify({'error': 'Only the claimant can update this claim'}), 403
    data = request.get_json()
    if 'intent' in data:
        claim.intent = data['intent'].strip() if data['intent'] else None
    if 'evidence_links' in data:
        claim.evidence_links = data['evidence_links']
    db.session.commit()
    return jsonify({'success': True, 'claim': claim.to_dict()})


@bp.route('/claims/<claim_id>/approve/', methods=['POST'])
@require_auth
def approve_claim(claim_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    claim = _resolve_claim(claim_id)
    project = Layer.query.get_or_404(claim.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project initiator or admins can approve claims'}), 403
    data = request.get_json()
    approve = data.get('approve', True)
    old_status = claim.status
    if approve:
        claim.status = 'active'
        claim.approved_by_id = current_user['id']
        claim.approved_at = datetime.utcnow()
    else:
        claim.status = 'revoked'
    db.session.add(StatusChange(
        entity_type='claim', entity_id=claim.id, field_name='status',
        from_value=old_status, to_value=claim.status, note=data.get('note'), changed_by_id=current_user['id']
    ))
    if approve:
        emit_event('role_claimed', actor_type='user', actor_id=current_user['id'],
                   subject_type='claim', subject_id=claim.id, layer_id=claim.layer_id, payload={'approved': True})
    db.session.commit()
    return jsonify({'success': True, 'claim': claim.to_dict()})


@bp.route('/claims/<claim_id>/status/', methods=['POST'])
@require_auth
def change_claim_status(claim_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    claim = _resolve_claim(claim_id)
    project = Layer.query.get_or_404(claim.layer_id)
    is_claimant = claim.claimant_id == current_user['id']
    is_padmin = is_layer_admin(project, current_user)
    if not (is_claimant or is_padmin):
        return jsonify({'error': 'Permission denied'}), 403
    data = request.get_json()
    new_status = data.get('status')
    if new_status not in ['active', 'pending_approval', 'paused', 'expired', 'revoked']:
        return jsonify({'error': 'Invalid status'}), 400
    if is_claimant and not is_padmin and new_status not in ['paused', 'active']:
        return jsonify({'error': 'You can only pause or reactivate your claim'}), 403
    old_status = claim.status
    claim.status = new_status
    db.session.add(StatusChange(
        entity_type='claim', entity_id=claim.id, field_name='status',
        from_value=old_status, to_value=new_status, note=data.get('note'), changed_by_id=current_user['id']
    ))
    db.session.commit()
    return jsonify({'success': True, 'claim': claim.to_dict()})


# ============================================================================
# Badges
# ============================================================================

@bp.route('/layers/<layer_id>/badges/', methods=['GET'])
def list_badges(layer_id):
    Layer.query.get_or_404(layer_id)
    status = request.args.get('status')
    claim_id = request.args.get('claim_id')
    claimant_id = request.args.get('claimant_id')
    query = Badge.query.filter_by(layer_id=layer_id)
    if status:
        query = query.filter_by(status=status)
    if claim_id:
        query = query.filter_by(claim_id=claim_id)
    if claimant_id:
        query = query.filter_by(claimant_id=str(claimant_id))
    badges = query.order_by(Badge.created_at.desc()).all()
    return jsonify({'badges': [b.to_dict() for b in badges], 'count': len(badges)})


@bp.route('/claims/<claim_id>/badges/', methods=['GET'])
def list_claim_badges(claim_id):
    claim = _resolve_claim(claim_id)
    badges = Badge.query.filter_by(claim_id=claim_id).order_by(Badge.created_at.desc()).all()
    return jsonify({'badges': [b.to_dict() for b in badges], 'count': len(badges)})


@bp.route('/claims/<claim_id>/badges/', methods=['POST'])
@require_auth
def request_badge(claim_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    claim = _resolve_claim(claim_id)
    role = Role.query.get_or_404(claim.role_id)
    if not role.badge_enabled:
        return jsonify({'error': 'Badges are not enabled for this role'}), 400
    if claim.status != 'active':
        return jsonify({'error': 'Can only request badges for active claims'}), 400
    project = Layer.query.get_or_404(claim.layer_id)
    is_claimant = claim.claimant_id == current_user['id']
    is_padmin = is_layer_admin(project, current_user)
    if not (is_claimant or is_padmin):
        return jsonify({'error': 'Only the claimant or project admins can request badges'}), 403
    data = request.get_json()
    badge_type = data.get('badge_type', 'role_badge')
    evidence_links = data.get('evidence_links', [])
    custody_mode = data.get('custody_mode', 'user_wallet')
    btc_taproot_address = data.get('btc_taproot_address', '').strip()
    if badge_type not in ['role_badge', 'founding_wave_badge', 'term_renewal_marker']:
        return jsonify({'error': 'Invalid badge type'}), 400
    if custody_mode not in ['user_wallet', 'overweb_treasury']:
        return jsonify({'error': 'Invalid custody mode'}), 400
    if custody_mode == 'user_wallet' and not btc_taproot_address:
        return jsonify({'error': 'BTC Taproot address is required for user wallet custody'}), 400
    badge_id = generate_badge_id()
    initial_status = 'requested' if role.badge_requires_approval else 'approved'
    badge = Badge(
        id=badge_id,
        layer_id=claim.layer_id,
        claim_id=claim_id,
        role_id=claim.role_id,
        claimant_id=claim.claimant_id,
        requested_by_id=current_user['id'],
        badge_type=badge_type,
        status=initial_status,
        evidence_links=evidence_links,
        custody_mode=custody_mode,
        btc_taproot_address=btc_taproot_address if btc_taproot_address else None
    )
    if initial_status == 'approved':
        badge.approved_by_id = current_user['id']
        badge.approved_at = datetime.utcnow()
    db.session.add(badge)
    evt_type = 'badge_approved' if initial_status == 'approved' else 'badge_nominated'
    emit_event(evt_type, actor_type='user', actor_id=current_user['id'],
               subject_type='badge', subject_id=badge.id, layer_id=claim.layer_id, payload={'badge_type': badge_type})
    db.session.commit()
    return jsonify({'success': True, 'badge': badge.to_dict()}), 201


@bp.route('/badges/<badge_id>/', methods=['GET'])
def get_badge(badge_id):
    if _is_uuid_like(badge_id):
        badge = Badge.query.filter_by(public_id=badge_id).first_or_404()
    else:
        badge = Badge.query.get_or_404(badge_id)
    d = badge.to_dict()
    role = Role.query.get(badge.role_id)
    if role:
        d['role'] = {'id': role.id, 'title_guild': role.title_guild, 'title_operational': role.title_operational}
    claimant = User.query.get(badge.claimant_id)
    if claimant:
        d['claimant'] = {'id': claimant.id, 'username': claimant.username, 'name': claimant.name}
    return jsonify(d)


@bp.route('/badges/<badge_id>/approve/', methods=['POST'])
@require_auth
def approve_badge(badge_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    badge = Badge.query.get_or_404(badge_id)
    project = Layer.query.get_or_404(badge.layer_id)
    if not is_layer_admin(project, current_user):
        return jsonify({'error': 'Only project initiator or admins can approve badges'}), 403
    data = request.get_json()
    approve = data.get('approve', True)
    approval_note = data.get('approval_note', '').strip()
    old_status = badge.status
    if approve:
        badge.status = 'approved'
        badge.approved_by_id = current_user['id']
        badge.approved_at = datetime.utcnow()
        badge.approval_note = approval_note if approval_note else None
    else:
        badge.status = 'denied'
        badge.approval_note = approval_note if approval_note else None
    db.session.add(StatusChange(
        entity_type='badge', entity_id=badge_id, field_name='status',
        from_value=old_status, to_value=badge.status, note=approval_note, changed_by_id=current_user['id']
    ))
    evt_type = 'badge_approved' if approve else 'badge_rejected'
    emit_event(evt_type, actor_type='user', actor_id=current_user['id'],
               subject_type='badge', subject_id=badge.id, layer_id=badge.layer_id, payload={'approve': approve})
    db.session.commit()
    return jsonify({'success': True, 'badge': badge.to_dict()})


@bp.route('/badges/<badge_id>/issue/', methods=['POST'])
@require_auth
def issue_badge(badge_id):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401
    if current_user.get('role') not in ['admin', 'editor']:
        return jsonify({'error': 'Admin access required'}), 403
    badge = Badge.query.get_or_404(badge_id)
    if badge.status != 'approved':
        return jsonify({'error': 'Badge must be approved before issuance'}), 400
    data = request.get_json()
    inscription_id = data.get('inscription_id', '').strip()
    tx_ref = data.get('tx_ref', '').strip()
    chain = data.get('chain', 'bitcoin').strip()
    if not inscription_id:
        return jsonify({'error': 'Inscription ID is required'}), 400
    old_status = badge.status
    badge.status = 'issued'
    badge.issuance_kind = 'ordinal'
    badge.inscription_id = inscription_id
    badge.tx_ref = tx_ref if tx_ref else None
    badge.chain = chain
    db.session.add(StatusChange(
        entity_type='badge', entity_id=badge_id, field_name='status',
        from_value=old_status, to_value='issued', note=f"Issued with inscription {inscription_id}",
        changed_by_id=current_user['id']
    ))
    db.session.commit()
    return jsonify({'success': True, 'badge': badge.to_dict()})
