"""Workgroups API: layer workgroups, workgroup CRUD, chairs, members."""
from datetime import datetime, date

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from extensions import db
from models import Layer, Workgroup, StatusChange
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin
from services.utils import create_slug

bp = Blueprint('workgroups', __name__, url_prefix='/api')


@bp.route('/layers/<layer_id>/workgroups/', methods=['GET'])
def list_workgroups(layer_id):
    """List workgroups for a project."""
    status = request.args.get('status')
    approval_status = request.args.get('approval_status')

    query = Workgroup.query.filter_by(layer_id=layer_id)
    if status:
        query = query.filter_by(status=status)
    if approval_status:
        query = query.filter_by(approval_status=approval_status)

    query = query.order_by(Workgroup.created_at.desc())
    workgroups = query.all()

    return jsonify({'workgroups': [wg.to_dict() for wg in workgroups], 'count': len(workgroups)})


@bp.route('/layers/<layer_id>/workgroups/', methods=['POST'])
@require_auth
def create_workgroup(layer_id):
    """Create a new workgroup."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    Layer.query.get_or_404(layer_id)

    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()

    if not name:
        return jsonify({'error': 'Workgroup name is required'}), 400

    slug = create_slug(name)
    counter = 1
    original_slug = slug
    while Workgroup.query.filter_by(layer_id=layer_id, slug=slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1

    acronym = create_slug(name)
    counter = 1
    original_acronym = acronym
    while Workgroup.query.filter_by(acronym=acronym).first():
        acronym = f"{original_acronym}-{counter}"
        counter += 1

    workgroup = Workgroup(
        acronym=acronym,
        name=name,
        slug=slug,
        layer_id=layer_id,
        coordinator_id=current_user['id'],
        description=description,
        status='active',
        approval_status='pending'
    )
    db.session.add(workgroup)
    db.session.commit()

    return jsonify({'success': True, 'workgroup': workgroup.to_dict()}), 201


@bp.route('/workgroups/<workgroup_id>/', methods=['GET'])
def get_workgroup(workgroup_id):
    """Get workgroup details."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)
    d = workgroup.to_dict()
    current_user = get_current_user()
    project = Layer.query.get(workgroup.layer_id)
    d['can_edit'] = bool(
        current_user
        and (
            workgroup.coordinator_id == current_user['id']
            or (project and is_layer_admin(project, current_user))
            or current_user.get('role') == 'admin'
        )
    )
    return jsonify(d)


@bp.route('/workgroups/<workgroup_id>/', methods=['PATCH'])
@require_auth
def update_workgroup(workgroup_id):
    """Update workgroup details (coordinator, project admin, or site admin)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    workgroup = Workgroup.query.get_or_404(workgroup_id)
    project = Layer.query.get(workgroup.layer_id)

    can_edit = (
        workgroup.coordinator_id == current_user['id']
        or (project and is_layer_admin(project, current_user))
        or current_user.get('role') == 'admin'
    )
    if not can_edit:
        return jsonify({'error': 'Permission denied'}), 403

    data = request.get_json()

    if 'name' in data and data['name']:
        workgroup.name = data['name'].strip()
    if 'description' in data:
        workgroup.description = data['description']
    if 'image_url' in data:
        workgroup.image_url = data['image_url'].strip() if data['image_url'] else None
    if 'status' in data and data['status'] in ['active', 'inactive', 'completed', 'archived']:
        old_status = workgroup.status
        workgroup.status = data['status']
        if old_status != workgroup.status:
            status_change = StatusChange(
                entity_type='workgroup',
                entity_id=workgroup_id,
                field_name='status',
                from_value=old_status,
                to_value=workgroup.status,
                changed_by_id=current_user['id']
            )
            db.session.add(status_change)

    if 'badge_enabled' in data:
        workgroup.badge_enabled = bool(data['badge_enabled'])

    for field in ['badge_submission_days', 'badge_voting_days', 'badge_delay_days',
                  'badge_cycle_spacing_days']:
        if field in data:
            setattr(workgroup, field, int(data[field]) if data[field] is not None else None)

    for field in ['badge_earliest_start', 'badge_end_date']:
        if field in data:
            val = data[field]
            if val:
                try:
                    setattr(workgroup, field, date.fromisoformat(val))
                except (ValueError, TypeError):
                    pass
            else:
                setattr(workgroup, field, None)

    for field in ['badge_end_at_next_closing', 'badge_voting_regular',
                  'badge_voting_time_weighted', 'badge_voting_quadratic']:
        if field in data:
            setattr(workgroup, field, bool(data[field]))

    if 'badge_skin_id' in data:
        workgroup.badge_skin_id = data['badge_skin_id'] or None

    workgroup.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'workgroup': workgroup.to_dict()})


@bp.route('/workgroups/<workgroup_id>/approve/', methods=['POST'])
@require_auth
def approve_workgroup(workgroup_id):
    """Approve or reject a workgroup (project admin/initiator or site admin)."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    workgroup = Workgroup.query.get_or_404(workgroup_id)

    is_site_admin = current_user.get('role') in ['admin', 'editor']
    is_project_initiator = workgroup.layer and is_layer_admin(workgroup.layer, current_user)

    if not (is_site_admin or is_project_initiator):
        return jsonify({'error': 'Only project admin or site admin can approve workgroups'}), 403

    data = request.get_json()
    action = data.get('action')

    if action not in ['approve', 'reject']:
        return jsonify({'error': 'Invalid action'}), 400

    old_status = workgroup.approval_status
    workgroup.approval_status = 'approved' if action == 'approve' else 'rejected'
    workgroup.approved_by_id = current_user['id']
    workgroup.approved_at = datetime.utcnow()

    status_change = StatusChange(
        entity_type='workgroup',
        entity_id=workgroup_id,
        field_name='approval_status',
        from_value=old_status,
        to_value=workgroup.approval_status,
        note=data.get('note'),
        changed_by_id=current_user['id']
    )
    db.session.add(status_change)
    db.session.commit()

    return jsonify({'success': True, 'workgroup': workgroup.to_dict()})


@bp.route('/workgroups/<workgroup_id>/chairs/', methods=['GET'])
def list_workgroup_chairs(workgroup_id):
    """List chairs for a workgroup."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)

    chairs_query = text("""
        SELECT id, group_acronym, chair_name, approved, set_at, user_id
        FROM working_group_chair
        WHERE group_acronym = :acronym
        ORDER BY set_at DESC
    """)
    result = db.session.execute(chairs_query, {'acronym': workgroup.acronym})
    chairs = []
    for row in result:
        chairs.append({
            'id': row[0],
            'group_acronym': row[1],
            'chair_name': row[2],
            'approved': bool(row[3]),
            'set_at': row[4],
            'user_id': row[5]
        })

    return jsonify({'chairs': chairs, 'count': len(chairs)})


@bp.route('/workgroups/<workgroup_id>/members/', methods=['GET'])
def list_workgroup_members(workgroup_id):
    """List members for a workgroup."""
    workgroup = Workgroup.query.get_or_404(workgroup_id)

    members_query = text("""
        SELECT id, group_acronym, user_name, joined_at, user_id
        FROM working_group_member
        WHERE group_acronym = :acronym
        ORDER BY joined_at DESC
    """)
    result = db.session.execute(members_query, {'acronym': workgroup.acronym})
    members = []
    for row in result:
        members.append({
            'id': row[0],
            'group_acronym': row[1],
            'user_name': row[2],
            'joined_at': row[3],
            'user_id': row[4]
        })

    return jsonify({'members': members, 'count': len(members)})


@bp.route('/workgroups/<workgroup_id>/join/', methods=['POST'])
@require_auth
def join_workgroup(workgroup_id):
    """Join a workgroup as a member."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    workgroup = Workgroup.query.get_or_404(workgroup_id)

    if workgroup.approval_status != 'approved':
        return jsonify({'error': 'Workgroup must be approved before joining'}), 400

    check_query = text("""
        SELECT id FROM working_group_member
        WHERE group_acronym = :acronym AND user_id = :user_id
    """)
    existing = db.session.execute(check_query, {
        'acronym': workgroup.acronym,
        'user_id': current_user['id']
    }).fetchone()

    if existing:
        return jsonify({'error': 'You are already a member of this workgroup'}), 400

    insert_query = text("""
        INSERT INTO working_group_member (group_acronym, user_id, user_name, joined_at)
        VALUES (:acronym, :user_id, :user_name, :joined_at)
    """)
    db.session.execute(insert_query, {
        'acronym': workgroup.acronym,
        'user_id': current_user['id'],
        'user_name': current_user.get('displayName') or current_user.get('username'),
        'joined_at': datetime.utcnow()
    })
    db.session.commit()

    return jsonify({'success': True, 'message': 'Successfully joined workgroup'})


@bp.route('/workgroups/<workgroup_id>/nominate-chair/', methods=['POST'])
@require_auth
def nominate_chair(workgroup_id):
    """Nominate yourself as a chair/coordinator for a workgroup."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'error': 'Authentication required'}), 401

    data = request.get_json()
    statement = data.get('statement', '').strip()

    if not statement:
        return jsonify({'error': 'Statement is required'}), 400

    workgroup = Workgroup.query.get_or_404(workgroup_id)

    if workgroup.approval_status != 'approved':
        return jsonify({'error': 'Workgroup must be approved before nominating chairs'}), 400

    check_query = text("""
        SELECT id FROM working_group_chair
        WHERE group_acronym = :acronym AND user_id = :user_id
    """)
    existing = db.session.execute(check_query, {
        'acronym': workgroup.acronym,
        'user_id': current_user['id']
    }).fetchone()

    if existing:
        return jsonify({'error': 'You are already nominated as a chair for this workgroup'}), 400

    insert_query = text("""
        INSERT INTO working_group_chair 
        (group_acronym, user_id, chair_name, approved, set_at, statement, nominated_by_user_id, is_self_nomination)
        VALUES (:acronym, :user_id, :chair_name, :approved, :set_at, :statement, :nominated_by, :is_self)
    """)
    db.session.execute(insert_query, {
        'acronym': workgroup.acronym,
        'user_id': current_user['id'],
        'chair_name': current_user.get('displayName') or current_user.get('username'),
        'approved': False,
        'set_at': datetime.utcnow(),
        'statement': statement,
        'nominated_by': current_user['id'],
        'is_self': True
    })
    db.session.commit()

    return jsonify({'success': True, 'message': 'Chair nomination submitted for approval'})
