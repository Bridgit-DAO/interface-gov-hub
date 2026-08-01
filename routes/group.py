"""Group routes: /group/ workgroup pages (GROUPS-based, join/leave, coordinator)."""
from flask import Blueprint, jsonify, request, session

from extensions import db
from models import (
    User, Workgroup, WorkingGroupChair, WorkingGroupMember, WorkgroupMemberRequest,
    CoordinatorRequest,
)
from services.identity import get_current_user, require_auth, require_role
from services.directory_ui import gh_page_header, gh_breadcrumb, gh_living_module
from services.workgroup_membership import join_or_request_workgroup_membership
from services.dp_welcome import (
    invalidate_dp_welcomes_for_workgroup,
    stale_member_welcome_variants,
)

bp = Blueprint('group', __name__, url_prefix='')


def _get_imports():
    """Late imports to avoid circular imports."""
    from services.rendering import _format_base_template, generate_user_menu
    from config import BUILD_NUMBER
    from services.groups import GROUPS
    return _format_base_template, generate_user_menu, BUILD_NUMBER, GROUPS


def _resolve_full_acronym(acronym):
    """Resolve short form (e.g. dp1) to full acronym from GROUPS."""
    for g in _get_imports()[3]:  # GROUPS
        if g['acronym'] == acronym:
            return g['acronym']
        if acronym.lower().startswith('dp') and g['acronym'].startswith(acronym.lower() + '-'):
            return g['acronym']
    return acronym


@bp.route('/group/')
def groups():
    _format_base_template, generate_user_menu, BUILD_NUMBER, GROUPS = _get_imports()
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark') if get_current_user() else 'light'
    groups_html = ""
    for group in GROUPS:
        all_chairs = WorkingGroupChair.query.filter_by(group_acronym=group['acronym']).all()
        if all_chairs:
            chair_names = []
            for chair in all_chairs:
                chair_name = chair.chair_name
                if not chair.approved:
                    chair_name += " (Pending)"
                chair_names.append(chair_name)
            chair_display = ", ".join(chair_names)
        else:
            chair_display = "TBD"

        groups_html += f"""
        <div class="col-md-6">
            <div class="card mb-3">
                <div class="card-body">
                    <h5 class="card-title">
                        <a href="/group/{group['acronym']}/">{group['name']}</a>
                    </h5>
                    <p class="card-text text-muted small">{group['acronym']}</p>
                    <div class="document-meta">
                        <span class="badge bg-primary">{group['type']}</span>
                        <span class="badge bg-success ms-2">{group['state']}</span>
                    </div>
                    <div class="mt-2">
                        <small class="text-muted">
                            Coordinator: {chair_display}<br>
                            {group['description']}
                        </small>
                    </div>
                </div>
            </div>
        </div>
        """

    current_theme = session.get('theme', 'dark')
    content = f"""
    <div class="gh-page container mt-4">
        {gh_page_header('Workgroups', 'Browse the Meta-Layer Desirable Properties workgroups', 'fa-users-cog', breadcrumb_html=gh_breadcrumb([('Home', '/'), ('Workgroups', None)]))}
        <div class="row row-cols-1 row-cols-md-2 g-3">
                    {groups_html}
        </div>
    </div>
    """
    return _format_base_template(
        title="Workgroups - GovHub",
        theme=current_theme,
        content=content,
        user_menu=user_menu, build_number=BUILD_NUMBER)


@bp.route('/group/<acronym>/')
def group_detail(acronym):
    """Display individual workgroup details."""
    _, _, _, GROUPS = _get_imports()
    group = None
    full_acronym = acronym

    for g in GROUPS:
        if g['acronym'] == acronym:
            group = g
            full_acronym = g['acronym']
            break
        if acronym.lower().startswith('dp') and g['acronym'].startswith(acronym.lower() + '-'):
            group = g
            full_acronym = g['acronym']
            break

    if not group:
        return f"Workgroup '{acronym}' not found. Available: {[g['acronym'] for g in GROUPS]}", 404

    _format_base_template, generate_user_menu, BUILD_NUMBER, _ = _get_imports()
    user_menu = generate_user_menu()
    current_user = get_current_user()

    is_member = False
    pending_member_request = False
    if current_user and current_user.get('id'):
        membership = WorkingGroupMember.query.filter_by(
            group_acronym=full_acronym,
            user_id=current_user['id']
        ).first()
        is_member = membership is not None
        if not is_member:
            req = WorkgroupMemberRequest.query.filter_by(
                group_acronym=full_acronym,
                user_id=current_user['id'],
                status='pending'
            ).first()
            pending_member_request = req is not None

    all_chairs = WorkingGroupChair.query.filter_by(group_acronym=full_acronym).all()
    is_coordinator = False
    has_pending_coord_request = False
    if current_user and current_user.get('id') and all_chairs:
        for chair in all_chairs:
            if chair.user_id == current_user['id']:
                is_coordinator = True
                break
    if current_user and current_user.get('id') and not is_coordinator:
        cr = CoordinatorRequest.query.filter_by(
            group_acronym=full_acronym,
            user_id=current_user['id'],
            status='pending'
        ).first()
        has_pending_coord_request = cr is not None

    if all_chairs:
        approved_chairs = [chair.chair_name for chair in all_chairs if chair.approved]
        pending_chairs = [chair.chair_name for chair in all_chairs if not chair.approved]
        if approved_chairs:
            chair_name = ", ".join(approved_chairs)
            if pending_chairs:
                chair_name += f" (Pending: {', '.join(pending_chairs)})"
        else:
            chair_name = f"Pending: {', '.join(pending_chairs)}"
        chair_approved = len(approved_chairs) > 0
    else:
        chair_name = "TBD"
        chair_approved = False

    join_button = ""
    if current_user and pending_member_request:
        join_button = '<span class="badge bg-warning">Membership request pending</span>'
    elif current_user and not is_member:
        join_button = f'<button class="btn btn-primary" onclick="joinGroup(\'{full_acronym}\')">Join Workgroup</button>'
    elif current_user and is_member:
        join_button = f'<span class="badge bg-success">Member</span> <button class="btn btn-outline-danger btn-sm ms-2" onclick="leaveGroup(\'{full_acronym}\')">Leave</button>'

    coord_request_ui = ""
    if current_user and current_user.get('id'):
        if is_coordinator:
            coord_request_ui = '<span class="badge bg-primary ms-2">Coordinator</span>'
        elif has_pending_coord_request:
            coord_request_ui = '<span class="badge bg-warning ms-2">Coordinator request pending</span>'
        else:
            coord_request_ui = f'<button class="btn btn-outline-secondary btn-sm ms-2" onclick="requestCoordinator(\'{full_acronym}\')">Request coordinator role</button>'

    current_theme = session.get('theme', current_user.get('theme', 'dark') if current_user else 'dark')

    leadership_pending = '<span class="badge bg-warning ms-2">Pending Approval</span>' if not chair_approved and chair_name != "TBD" else ''
    content = f"""
    <div class="gh-page container mt-4">
        {gh_page_header(group['name'], group['acronym'].upper(), 'fa-users', actions_html=f'{join_button} {coord_request_ui}', breadcrumb_html=gh_breadcrumb([('Home', '/'), ('Workgroups', '/group/'), (group['name'], None)]))}
        <div class="gh-detail-layout">
        <div class="row g-3">
            <div class="col-md-8">
                {gh_living_module('About', f'<p class="mb-0">{group.get("about", group["description"])}</p>', 'fa-info-circle')}
            </div>
            <div class="col-md-4">
                {gh_living_module('Leadership', f'<p class="mb-2"><strong>Coordinator:</strong> {chair_name}</p>{leadership_pending}', 'fa-user-tie')}
                {gh_living_module('Details', f'<p class="mb-2"><strong>State:</strong> <span class="badge bg-success">{group["state"]}</span></p><p class="mb-0 text-muted small">{group["description"]}</p>', 'fa-clipboard-list', extra_class='mt-3')}
            </div>
        </div>
        </div>
    </div>
    <script>
    async function showGroupError(message) {{
        if (window.GhDialog) {{
            await GhDialog.alert({{
                title: 'Workgroup action failed',
                message: message || 'Request failed',
                variant: 'danger',
            }});
        }}
    }}
    async function joinGroup(acronym) {{
        fetch(`/group/${{acronym}}/join`, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }} }})
        .then(r => r.json()).then(d => {{ if (d.success) location.reload(); else showGroupError(d.message); }})
        .catch(() => showGroupError('Error joining group'));
    }}
    async function leaveGroup(acronym) {{
        fetch(`/group/${{acronym}}/leave`, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }} }})
        .then(r => r.json()).then(d => {{ if (d.success) location.reload(); else showGroupError(d.message); }})
        .catch(() => showGroupError('Error leaving group'));
    }}
    async function requestCoordinator(acronym) {{
        fetch(`/group/${{acronym}}/request_coordinator`, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }} }})
        .then(r => r.json()).then(d => {{ if (d.success) location.reload(); else showGroupError(d.message || 'Request failed'); }})
        .catch(() => showGroupError('Request failed'));
    }}
    async function addChair(acronym) {{
        const input = document.getElementById(`new-chair-input-${{acronym}}`);
        const chairName = input?.value?.trim();
        if (!chairName) {{
            await GhDialog.alert({{ title: 'Missing name', message: 'Please enter a chair name.', variant: 'warning' }});
            return;
        }}
        fetch(`/group/${{acronym}}/add_chair`, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ chair_name: chairName }}) }})
        .then(r => r.json()).then(d => {{ if (d.success) location.reload(); else showGroupError(d.message); }})
        .catch(() => showGroupError('Error adding chair'));
    }}
    async function updateChairs(acronym) {{
        const select = document.getElementById(`chair-select-${{acronym}}`);
        const chairIds = Array.from(select?.selectedOptions || []).map(o => parseInt(o.value));
        fetch(`/group/${{acronym}}/update_chairs`, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ chair_ids: chairIds }}) }})
        .then(r => r.json()).then(d => {{ if (d.success) location.reload(); else showGroupError(d.message); }})
        .catch(() => showGroupError('Error updating chairs'));
    }}
    async function removeChair(acronym) {{
        const select = document.getElementById(`chair-select-${{acronym}}`);
        const selected = Array.from(select?.selectedOptions || []);
        if (!selected.length) {{
            await GhDialog.alert({{ title: 'Select chairs', message: 'Please select chairs to remove.', variant: 'warning' }});
            return;
        }}
        const ok = await GhDialog.confirm({{ title: 'Remove chairs', message: 'Remove ' + selected.length + ' chair(s)?', variant: 'warning', confirmLabel: 'Remove' }});
        if (ok) {{
            const chairIds = selected.map(o => parseInt(o.value));
            fetch(`/group/${{acronym}}/remove_chairs`, {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify({{ chair_ids: chairIds }}) }})
            .then(r => r.json()).then(d => {{ if (d.success) location.reload(); else showGroupError(d.message); }})
            .catch(() => showGroupError('Error removing chairs'));
        }}
    }}
    </script>
    """
    return _format_base_template(
        title=f"{group['name']} - GovHub",
        theme=current_theme,
        content=content,
        user_menu=user_menu, build_number=BUILD_NUMBER)


@bp.route('/group/<acronym>/join', methods=['POST'])
@require_auth
def join_group(acronym):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    _, _, _, GROUPS = _get_imports()
    full_acronym = _resolve_full_acronym(acronym)
    group = next((g for g in GROUPS if g['acronym'] == full_acronym), None)

    user_id = current_user.get('id')
    if not user_id:
        return jsonify({'success': False, 'message': 'You must be logged in to join'}), 400
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    existing = WorkingGroupMember.query.filter_by(
        group_acronym=full_acronym,
        user_id=user_id
    ).first()
    if existing:
        return jsonify({'success': False, 'message': 'Already a member'}), 400

    require_approval = group.get('members_require_approval', False) if group else False
    result = join_or_request_workgroup_membership(
        acronym=full_acronym,
        user=user,
        require_approval=require_approval,
    )
    if result.get('status') == 'already_pending':
        return jsonify({'success': False, 'message': 'Membership request already pending'}), 400
    db.session.commit()
    if result.get('pending_approval'):
        return jsonify({'success': True, 'message': 'Membership requested; pending approval'})
    return jsonify({'success': True, 'message': 'Joined successfully'})


@bp.route('/group/<acronym>/leave', methods=['POST'])
@require_auth
def leave_group(acronym):
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    full_acronym = _resolve_full_acronym(acronym)
    user_id = current_user.get('id')
    if not user_id:
        return jsonify({'success': False, 'message': 'You must be logged in to leave'}), 400

    membership = WorkingGroupMember.query.filter_by(
        group_acronym=full_acronym,
        user_id=user_id
    ).first()
    if not membership:
        return jsonify({'success': False, 'message': f'Not a member (user_id={user_id}, group={full_acronym})'}), 400

    db.session.delete(membership)
    db.session.flush()

    # A welcome guide is only valid while its grant is. Archive the member
    # welcome now that membership is gone; an approved lead role (and its
    # combined welcome) is untouched because leaving does not revoke a role.
    workgroup = Workgroup.query.filter_by(acronym=full_acronym).first()
    stale = stale_member_welcome_variants(user_id=user_id, workgroup=workgroup)
    if stale:
        invalidate_dp_welcomes_for_workgroup(
            user_id=user_id,
            workgroup=workgroup,
            variants=stale,
        )
    db.session.commit()
    return jsonify({'success': True, 'message': 'Left successfully'})


@bp.route('/group/<acronym>/request_coordinator', methods=['POST'])
@require_auth
def request_coordinator(acronym):
    """User requests coordinator role; creates pending request."""
    current_user = get_current_user()
    if not current_user:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401

    full_acronym = _resolve_full_acronym(acronym)

    existing_chair = WorkingGroupChair.query.filter_by(
        group_acronym=full_acronym,
        user_id=current_user['id']
    ).first()
    if existing_chair:
        return jsonify({'success': False, 'message': 'You are already a coordinator'}), 400

    existing = CoordinatorRequest.query.filter_by(
        group_acronym=full_acronym,
        user_id=current_user['id'],
        status='pending'
    ).first()
    if existing:
        return jsonify({'success': False, 'message': 'You already have a pending request'}), 400

    req = CoordinatorRequest(
        group_acronym=full_acronym,
        user_id=current_user['id'],
        username=current_user.get('username', ''),
        display_name=current_user.get('name') or current_user.get('displayName') or current_user.get('username', ''),
        status='pending'
    )
    db.session.add(req)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Coordinator role requested; pending approval'})


@bp.route('/group/<acronym>/add_chair', methods=['POST'])
@require_role('admin')
def add_group_chair(acronym):
    full_acronym = _resolve_full_acronym(acronym)
    data = request.get_json() or {}
    chair_name = data.get('chair_name', '').strip()
    if not chair_name:
        return jsonify({'success': False, 'message': 'Coordinator name required'}), 400

    existing = WorkingGroupChair.query.filter_by(group_acronym=full_acronym, chair_name=chair_name).first()
    if existing:
        return jsonify({'success': False, 'message': 'Coordinator already exists'}), 400

    chair = WorkingGroupChair(
        group_acronym=full_acronym,
        chair_name=chair_name,
        approved=False
    )
    db.session.add(chair)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Coordinator added successfully'})


@bp.route('/group/<acronym>/update_chairs', methods=['POST'])
@require_role('admin')
def update_group_chairs(acronym):
    full_acronym = _resolve_full_acronym(acronym)
    data = request.get_json() or {}
    chair_ids = data.get('chair_ids', [])

    WorkingGroupChair.query.filter_by(group_acronym=full_acronym).update({'approved': False})
    if chair_ids:
        WorkingGroupChair.query.filter(
            WorkingGroupChair.group_acronym == full_acronym,
            WorkingGroupChair.id.in_(chair_ids)
        ).update({'approved': True})
    db.session.commit()
    return jsonify({'success': True, 'message': 'Coordinators updated successfully'})


@bp.route('/group/<acronym>/remove_chairs', methods=['POST'])
@require_role('admin')
def remove_group_chairs(acronym):
    full_acronym = _resolve_full_acronym(acronym)
    data = request.get_json() or {}
    chair_ids = data.get('chair_ids', [])

    if not chair_ids:
        return jsonify({'success': False, 'message': 'No chairs selected'}), 400

    WorkingGroupChair.query.filter(
        WorkingGroupChair.group_acronym == full_acronym,
        WorkingGroupChair.id.in_(chair_ids)
    ).delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Coordinators removed successfully'})
