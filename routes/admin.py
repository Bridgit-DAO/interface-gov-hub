"""Admin routes: dashboard, users, analytics, chairs, layers, workgroups, roles, badges, member requests."""
import html as html_mod
import json
from datetime import datetime, timedelta
from urllib.parse import urlencode

from flask import Blueprint, request, redirect, flash, session, jsonify, current_app

from extensions import db
from models import (
    User, Submission, Layer, Workgroup, Guild, Role, Claim, Badge,
    WorkingGroupChair, CoordinatorRequest, WorkgroupMemberRequest, WorkingGroupMember,
    PlatformInvitation, PlatformInvitationAcceptance, Comment,
)
from services.identity import get_current_user, require_auth, require_role
from services.avatar import avatar_url
from services.submissions import add_to_document_history
from services.directory_ui import gh_page_header, gh_breadcrumb, gh_living_module
from services.utils import coerce_storage_bool
from services.workgroup_positions import (
    NOMINATION_STATUS_NOMINEE_ACCEPTED,
    NOMINATION_STATUS_APPROVED,
    NOMINATION_STATUS_REJECTED,
    position_label,
    status_label,
)
from services.workgroup_nomination_mail import send_admin_decision
from services.events import emit_event
from services.dp_badges import dp_contributor_badge_status
from services.workgroup_links import is_dp_workgroup

bp = Blueprint('admin', __name__, url_prefix='')


def _get_imports():
    """Late imports to avoid circular imports."""
    from services.rendering import _format_base_template, generate_user_menu, render_page
    from services.identity import get_current_user
    from config import BUILD_NUMBER
    from services.groups import GROUPS
    return _format_base_template, generate_user_menu, get_current_user, BUILD_NUMBER, GROUPS, render_page


@bp.route('/admin/')
@require_role('admin')
def admin_dashboard():
    _format_base_template, generate_user_menu, get_current_user, BUILD_NUMBER, GROUPS, _ = _get_imports()
    user_menu = generate_user_menu()

    total_users = User.query.count()
    total_groups = len(GROUPS)
    total_submissions = Submission.query.count()
    approved_drafts = Submission.query.filter(Submission.status.in_(['approved', 'published'])).count()
    pending_chairs = WorkingGroupChair.query.filter(
        WorkingGroupChair.approved.is_(False),
        WorkingGroupChair.status == NOMINATION_STATUS_NOMINEE_ACCEPTED,
    ).count()

    total_projects = Layer.query.count()
    pending_projects = Layer.query.filter_by(approval_status='pending').count()
    active_display_layers = Layer.query.filter_by(display_status='active').count()
    pending_display_layers = Layer.query.filter_by(display_status='pending').count()
    total_workgroups = Workgroup.query.count()
    pending_workgroups = Workgroup.query.filter_by(approval_status='pending').count()
    total_guilds = Guild.query.count()
    total_roles = Role.query.count()
    pending_roles = Role.query.filter_by(status='draft').count()
    total_claims = Claim.query.count()
    pending_claims = Claim.query.filter_by(status='pending_approval').count()
    total_badges = Badge.query.count()
    pending_badges = Badge.query.filter_by(status='requested').count()

    pending_submissions = Submission.query.filter_by(status='submitted').count()
    recent_submissions = Submission.query.order_by(Submission.submitted_at.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    active_drafts = Submission.query.order_by(Submission.submitted_at.desc()).limit(10).all()
    active_users = User.query.order_by(User.last_login.desc()).limit(10).all()

    activity_html = ""
    for submission in recent_submissions[:3]:
        activity_html += f"""
        <div class="activity-item mb-2">
            <small class="text-muted">
                <i class="fas fa-file-alt me-1"></i>
                New submission: <strong>{submission.title[:50]}...</strong>
                by {submission.submitted_by}
                <span class="float-end">{submission.submitted_at.strftime('%m/%d %H:%M')}</span>
            </small>
        </div>
        """

    for user in recent_users[:2]:
        activity_html += f"""
        <div class="activity-item mb-2">
            <small class="text-muted">
                <i class="fas fa-user-plus me-1"></i>
                New user: <strong>{user.name}</strong> ({user.email})
                <span class="float-end">{user.created_at.strftime('%m/%d %H:%M')}</span>
            </small>
        </div>
        """

    alerts_html = ""
    if pending_submissions > 0:
        alerts_html += f"""
        <div class="alert alert-warning alert-dismissible fade show" role="alert">
            <i class="fas fa-exclamation-triangle me-2"></i>
            <strong>{pending_submissions}</strong> draft submission(s) pending review
            <a href="/admin/submissions/" class="alert-link">Review now</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    if pending_chairs > 0:
        alerts_html += f"""
        <div class="alert alert-info alert-dismissible fade show" role="alert">
            <i class="fas fa-users me-2"></i>
            <strong>{pending_chairs}</strong> position nomination(s) ready for approval
            <a href="/admin/chair-nominations/" class="alert-link">Review nominations</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    if pending_projects > 0:
        alerts_html += f"""
        <div class="alert alert-primary alert-dismissible fade show" role="alert">
            <i class="fas fa-project-diagram me-2"></i>
            <strong>{pending_projects}</strong> layer(s) pending approval
            <a href="/admin/layers/" class="alert-link">Review now</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    if pending_workgroups > 0:
        alerts_html += f"""
        <div class="alert alert-warning alert-dismissible fade show" role="alert">
            <i class="fas fa-users me-2"></i>
            <strong>{pending_workgroups}</strong> workgroup(s) pending approval
            <a href="/admin/workgroups/" class="alert-link">Review now</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    if pending_roles > 0:
        alerts_html += f"""
        <div class="alert alert-secondary alert-dismissible fade show" role="alert">
            <i class="fas fa-user-tag me-2"></i>
            <strong>{pending_roles}</strong> role(s) pending approval
            <a href="/admin/roles/" class="alert-link">Review now</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    if pending_badges > 0:
        alerts_html += f"""
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            <i class="fas fa-award me-2"></i>
            <strong>{pending_badges}</strong> badge(s) pending issuance
            <a href="/admin/badges/" class="alert-link">Issue now</a>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
        """

    content = f"""
    <div class="gh-page container mt-4 gh-admin-page">
        <div id="admin-alerts" class="mb-4">
            {alerts_html}
        </div>

        {gh_page_header('Admin Dashboard', 'Site administration and moderation', 'fa-shield-alt', actions_html=(
            '<a href="/admin/users/" class="btn btn-outline-primary btn-sm me-1"><i class="fas fa-users me-1"></i>Users</a>'
            '<a href="/admin/submissions/" class="btn btn-outline-success btn-sm me-1"><i class="fas fa-file-alt me-1"></i>Submissions</a>'
            '<a href="/admin/posts/" class="btn btn-outline-danger btn-sm me-1"><i class="fas fa-comments me-1"></i>Posts</a>'
            '<a href="/admin/layers/" class="btn btn-outline-info btn-sm me-1"><i class="fas fa-project-diagram me-1"></i>Layers</a>'
            '<a href="/admin/product-rollout/" class="btn btn-dark btn-sm me-1"><i class="fas fa-toggle-on me-1"></i>Rollout</a>'
            '<a href="/admin/nav-pills/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-circle-notch me-1"></i>Nav pills</a>'
        ))}

        <div class="row">
            <div class="col-12">
                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-primary mb-1">{total_users}</h4>
                                <p class="mb-0 small">Total Users</p>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-info mb-1">{total_projects}</h4>
                                <p class="mb-0 small">Layers</p>
                                {f'<small class="text-warning">({pending_projects} pending approval)</small>' if pending_projects > 0 else ''}
                                <div class="small text-muted mt-1">
                                    <span class="badge bg-success">{active_display_layers} active</span>
                                    <span class="badge bg-warning text-dark">{pending_display_layers} pending display</span>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-success mb-1">{total_workgroups}</h4>
                                <p class="mb-0 small">Workgroups</p>
                                {f'<small class="text-warning">({pending_workgroups} pending)</small>' if pending_workgroups > 0 else ''}
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-secondary mb-1">{total_roles}</h4>
                                <p class="mb-0 small">Roles</p>
                                {f'<small class="text-warning">({pending_roles} pending)</small>' if pending_roles > 0 else ''}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row mb-4">
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-warning mb-1">{total_submissions}</h4>
                                <p class="mb-0 small">Submissions</p>
                                {f'<small class="text-danger">({pending_submissions} pending)</small>' if pending_submissions > 0 else ''}
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-primary mb-1">{total_badges}</h4>
                                <p class="mb-0 small">Badges</p>
                                {f'<small class="text-warning">({pending_badges} pending)</small>' if pending_badges > 0 else ''}
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-success mb-1">{total_claims}</h4>
                                <p class="mb-0 small">Claims</p>
                                {f'<small class="text-warning">({pending_claims} pending)</small>' if pending_claims > 0 else ''}
                            </div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="card h-100">
                            <div class="card-body text-center">
                                <h4 class="text-info mb-1">{total_guilds}</h4>
                                <p class="mb-0 small">Guilds</p>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header d-flex justify-content-between align-items-center">
                                <h5 class="mb-0">Recent Activity</h5>
                                <span class="badge bg-primary">Live</span>
                            </div>
                            <div class="card-body">
                                {activity_html}
                                <hr>
                                <a href="/admin/activity/" class="btn btn-sm btn-outline-primary">View All Activity</a>
                            </div>
                        </div>
                    </div>

                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Quick Actions</h5>
                            </div>
                            <div class="card-body">
                                <div class="d-grid gap-2">
                                    <a href="/admin/submissions/" class="btn btn-success">
                                        <i class="fas fa-check-circle me-2"></i>Review Submissions ({pending_submissions} pending)
                                    </a>
                                    <a href="/admin/users/" class="btn btn-primary">
                                        <i class="fas fa-users me-2"></i>Manage Users ({total_users} total)
                                    </a>
                                    <a href="/admin/posts/" class="btn btn-danger">
                                        <i class="fas fa-comments me-2"></i>Moderate Posts
                                    </a>
                                    <a href="/group/" class="btn btn-info">
                                        <i class="fas fa-users-cog me-2"></i>Manage Workgroups ({pending_chairs} pending coordinators)
                                    </a>
                                    <a href="/admin/analytics/" class="btn btn-secondary">
                                        <i class="fas fa-chart-bar me-2"></i>View Analytics
                                    </a>
                                    <a href="/admin/product-rollout/" class="btn btn-dark">
                                        <i class="fas fa-toggle-on me-2"></i>Product rollout
                                    </a>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row mt-4">
                    <div class="col-12">
                        <h3 class="mb-3">Content Management</h3>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Recent Draft Submissions</h5>
                            </div>
                            <div class="card-body">
                                <div class="list-group list-group-flush">
                                    {"".join([f'''
                                    <a href="/doc/draft/{draft.id}/" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                                        <div>
                                            <strong>{draft.title[:40]}...</strong>
                                            <br><small class="text-muted">by {draft.submitted_by} • {draft.submitted_at.strftime('%m/%d')}</small>
                                        </div>
                                        <span class="badge bg-{'warning' if draft.status == 'submitted' else 'success'}">{draft.status}</span>
                                    </a>
                                    ''' for draft in active_drafts[:5]])}
                                </div>
                            </div>
                        </div>
                    </div>

                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5>Recent User Activity</h5>
                            </div>
                            <div class="card-body">
                                <div class="list-group list-group-flush">
                                    {"".join([f'''
                                    <div class="list-group-item d-flex justify-content-between align-items-center">
                                        <div>
                                            <strong>{user.name}</strong>
                                            <br><small class="text-muted">{user.email} • {user.role}</small>
                                        </div>
                                        <small class="text-muted">
                                            {user.last_login.strftime('%m/%d %H:%M') if user.last_login else 'Never logged in'}
                                        </small>
                                    </div>
                                    ''' for user in active_users[:5]])}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """

    return _format_base_template(
        title="Admin Dashboard - GovHub",
        theme=get_current_user().get('theme', 'dark'),
        content=content,
        user_menu=user_menu, build_number=BUILD_NUMBER)


@bp.route('/admin/users/')
@require_role('admin')
def admin_users():
    _format_base_template, generate_user_menu, get_current_user, BUILD_NUMBER, _, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')

    page = request.args.get('page', 1, type=int)
    per_page = 20
    search = request.args.get('search', '').strip()
    role_filter = request.args.get('role', '')

    query = User.query

    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.name.contains(search),
                User.email.contains(search)
            )
        )

    if role_filter:
        query = query.filter_by(role=role_filter)

    users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    total_users = query.count()

    user_rows = ""
    for user in users.items:
        role_badge = {
            'admin': 'badge bg-danger',
            'editor': 'badge bg-warning',
            'user': 'badge bg-secondary'
        }.get(user.role, 'badge bg-secondary')

        last_login = user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'

        user_rows += f"""
        <tr>
            <td>
                <strong>{user.name}</strong><br>
                <small class="text-muted">@{user.username}</small>
            </td>
            <td>{user.email}</td>
            <td><span class="{role_badge}">{user.role.title()}</span></td>
            <td>{user.theme.title()}</td>
            <td>{user.created_at.strftime('%Y-%m-%d')}</td>
            <td>{last_login}</td>
            <td>
                <div class="btn-group btn-group-sm" role="group">
                    <div class="dropdown">
                        <button class="btn btn-outline-primary btn-sm dropdown-toggle" type="button" id="roleDropdown{user.username}" data-bs-toggle="dropdown" aria-expanded="false" data-bs-offset="0,4">
                            <i class="fas fa-user-edit"></i>
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end" aria-labelledby="roleDropdown{user.username}">
                            <li><a class="dropdown-item" href="#" onclick="changeRole('{user.username}', 'user'); return false;">Participant</a></li>
                            <li><a class="dropdown-item" href="#" onclick="changeRole('{user.username}', 'editor'); return false;">Editor</a></li>
                            <li><a class="dropdown-item" href="#" onclick="changeRole('{user.username}', 'admin'); return false;">Admin</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="/admin/users/{user.id}/add-coordinator"><i class="fas fa-user-tie me-1"></i>Add as coordinator</a></li>
                        </ul>
                    </div>
                    <button class="btn btn-outline-danger btn-sm ms-1" onclick="deleteUser('{user.username}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
        """

    role_options = f"""
    <option value="">All Roles</option>
    <option value="admin" {'selected' if role_filter == 'admin' else ''}>Admin</option>
    <option value="editor" {'selected' if role_filter == 'editor' else ''}>Editor</option>
    <option value="user" {'selected' if role_filter == 'user' else ''}>Participant</option>
    """

    content = f"""
    <div class="gh-page container mt-4 gh-admin-page">
        {gh_page_header('User Management', f'{total_users} users total', 'fa-users', actions_html=f'<span class="badge bg-info">Total: {total_users}</span>', breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('User Management', None)]))}

        <div class="living-module mb-4">
            <div class="living-module-body">
                <form method="GET" class="row g-3">
                    <div class="col-md-6">
                        <label for="search" class="form-label">Search Users</label>
                        <input type="text" class="form-control" id="search" name="search"
                               value="{search}" placeholder="Name, username, or email">
                    </div>
                    <div class="col-md-4">
                        <label for="role" class="form-label">Filter by Role</label>
                        <select class="form-select" id="role" name="role">
                            {role_options}
                        </select>
                    </div>
                    <div class="col-md-2 d-flex align-items-end">
                        <button type="submit" class="btn btn-primary me-2">
                            <i class="fas fa-search me-1"></i>Filter
                        </button>
                        <a href="/admin/users/" class="btn btn-outline-secondary">
                            <i class="fas fa-times"></i>
                        </a>
                    </div>
                </form>
            </div>
        </div>

        <div class="living-module">
            <div class="living-module-header">
                <div class="living-module-icon"><i class="fas fa-users"></i></div>
                <h5 class="living-module-title">Users ({users.total} total)</h5>
            </div>
            <div class="living-module-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover mb-0">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Role</th>
                                <th>Theme</th>
                                <th>Joined</th>
                                <th>Last Login</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {user_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        {f'''
        <nav aria-label="User pagination" class="mt-4">
            <ul class="pagination justify-content-center">
                {f'<li class="page-item {"disabled" if not users.has_prev else ""}"><a class="page-link" href="?page={users.prev_num}&search={search}&role={role_filter}">Previous</a></li>' if users.has_prev else ''}
                {''.join([f'<li class="page-item {"active" if i == users.page else ""}"><a class="page-link" href="?page={i}&search={search}&role={role_filter}">{i}</a></li>' for i in users.iter_pages()])}
                {f'<li class="page-item {"disabled" if not users.has_next else ""}"><a class="page-link" href="?page={users.next_num}&search={search}&role={role_filter}">Next</a></li>' if users.has_next else ''}
            </ul>
        </nav>
        ''' if users.pages > 1 else ''}
        </div>

    <script>
        function changeRole(username, newRole) {{
            fetch('/admin/users/' + username + '/role', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ role: newRole }})
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    location.reload();
                }} else {{
                    await GhDialog.alert({{ title: 'Notice', message: ('Error: ' + (data.message || 'Unknown error')), variant: 'info' }});
                }}
            }})
            .catch(error => {{
                await GhDialog.alert({{ title: 'Notice', message: ('Error updating role: ' + error.message), variant: 'info' }});
            }});
        }}

        async function deleteUser(username) {{
            if (!(await GhDialog.confirm({{ title: 'Delete user', message: "Are you sure you want to delete user " + username + "? This action cannot be undone.", variant: 'warning' }}))) return;
            try {{
                const r = await fetch('/admin/users/' + username + '/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                const data = await r.json();
                if (data.success) {{
                    location.reload();
                }} else {{
                    await GhDialog.alert({{ title: 'Delete failed', message: ('Error: ' + (data.message || 'Unknown error')), variant: 'danger' }});
                }}
            }} catch (error) {{
                await GhDialog.alert({{ title: 'Delete failed', message: ('Error deleting user: ' + error.message), variant: 'danger' }});
            }}
        }}
    </script>
    """

    return _format_base_template(
        title="User Management - GovHub",
        theme=current_theme,
        user_menu=user_menu,
        content=content, build_number=BUILD_NUMBER)


def _comment_page_label(comment):
    """Human label for the document/page a comment belongs to."""
    submission = None
    if comment.submission_id:
        submission = Submission.query.get(comment.submission_id)
    if not submission and comment.draft_name:
        submission = Submission.query.filter(
            db.or_(
                Submission.draft_name == comment.draft_name,
                Submission.ml_number == comment.draft_name,
                Submission.id == comment.draft_name,
            )
        ).first()
    if submission:
        ref = submission.ml_number or submission.draft_name or submission.public_id or submission.id
        return submission.title or 'Untitled document', ref
    ref = comment.draft_name or comment.submission_id or 'Unknown page'
    return ref, ref


def _comment_author_label(comment):
    if comment.author_user_id:
        user = User.query.get(comment.author_user_id)
        if user:
            return user.displayName or user.name or user.oauthName or user.username or user.email or 'User'
    return comment.author or 'Unknown user'


def _emit_comment_moderation_event(action, comment, admin_user, *, old_text=None, new_text=None):
    title, ref = _comment_page_label(comment)
    emit_event(
        f'comment_moderation_{action}',
        actor_type='user',
        actor_id=admin_user.get('id'),
        subject_type='comment',
        subject_id=comment.id,
        payload={
            'action': action,
            'draft_name': comment.draft_name,
            'submission_id': comment.submission_id,
            'page_title': title,
            'page_ref': ref,
            'author': _comment_author_label(comment),
            'author_user_id': comment.author_user_id,
            'old_text': old_text,
            'new_text': new_text,
        },
    )


def _is_strict_admin(current_user):
    return bool(current_user and current_user.get('role') == 'admin')


@bp.route('/admin/posts/')
@require_role('admin')
def admin_posts():
    _format_base_template, generate_user_menu, get_current_user, BUILD_NUMBER, _, _ = _get_imports()
    current_user = get_current_user()
    if not _is_strict_admin(current_user):
        return "Access denied: Admin role required", 403
    user_menu = generate_user_menu()
    current_theme = current_user.get('theme', 'dark')

    page_num = request.args.get('page', 1, type=int)
    per_page = 25
    user_filter = request.args.get('user', '').strip()
    page_filter = request.args.get('page_ref', '').strip()
    text_filter = request.args.get('text', '').strip()
    include_deleted = request.args.get('include_deleted') == '1'

    query = Comment.query
    if not include_deleted:
        query = query.filter(Comment.is_deleted == False)  # noqa: E712

    if user_filter:
        like = f'%{user_filter}%'
        matching_user_ids = [
            row.id for row in User.query.filter(
                db.or_(
                    User.username.ilike(like),
                    User.name.ilike(like),
                    User.displayName.ilike(like),
                    User.oauthName.ilike(like),
                    User.email.ilike(like),
                )
            ).limit(500).all()
        ]
        user_clauses = [Comment.author.ilike(like)]
        if matching_user_ids:
            user_clauses.append(Comment.author_user_id.in_(matching_user_ids))
        query = query.filter(db.or_(*user_clauses))

    if page_filter:
        like = f'%{page_filter}%'
        matching_submission_ids = [
            row.id for row in Submission.query.filter(
                db.or_(
                    Submission.title.ilike(like),
                    Submission.draft_name.ilike(like),
                    Submission.ml_number.ilike(like),
                    Submission.public_id.ilike(like),
                )
            ).limit(500).all()
        ]
        page_clauses = [Comment.draft_name.ilike(like)]
        if matching_submission_ids:
            page_clauses.append(Comment.submission_id.in_(matching_submission_ids))
        query = query.filter(db.or_(*page_clauses))

    if text_filter:
        like = f'%{text_filter}%'
        query = query.filter(
            db.or_(
                Comment.text.ilike(like),
                Comment.original_text.ilike(like),
                Comment.passage_excerpt.ilike(like),
            )
        )

    comments = query.order_by(Comment.timestamp.desc()).paginate(
        page=page_num, per_page=per_page, error_out=False
    )
    total_posts = query.count()

    rows = []
    for comment in comments.items:
        title, ref = _comment_page_label(comment)
        author = _comment_author_label(comment)
        posted_at = comment.timestamp.strftime('%Y-%m-%d %H:%M') if comment.timestamp else ''
        edited_at = comment.edited_at.strftime('%Y-%m-%d %H:%M') if comment.edited_at else ''
        deleted = bool(comment.is_deleted)
        badge = '<span class="badge bg-danger">Deleted</span>' if deleted else '<span class="badge bg-success">Live</span>'
        passage = html_mod.escape(comment.passage_excerpt or '')
        comment_id = html_mod.escape(comment.id)
        disabled = 'disabled' if deleted else ''
        rows.append(f"""
        <tr id="post-row-{comment_id}">
            <td>
                <div class="fw-semibold">{html_mod.escape(author)}</div>
                <small class="text-muted">{html_mod.escape(comment.author_user_id or comment.author or '')}</small>
            </td>
            <td>
                <div class="fw-semibold">{html_mod.escape(title)}</div>
                <small class="text-muted">{html_mod.escape(ref or '')}</small>
            </td>
            <td>
                {badge}
                <div class="small text-muted mt-1">{posted_at}</div>
                {f'<div class="small text-muted">Edited {edited_at}</div>' if edited_at else ''}
            </td>
            <td style="min-width: 320px;">
                {f'<div class="small text-muted mb-2"><strong>Passage:</strong> {passage}</div>' if passage else ''}
                <textarea class="form-control form-control-sm" id="post-text-{comment_id}" rows="4" {disabled}>{html_mod.escape(comment.text or '')}</textarea>
            </td>
            <td class="text-nowrap">
                <button type="button" class="btn btn-sm btn-outline-primary me-1" onclick="savePost('{comment_id}')" {disabled}>
                    <i class="fas fa-save me-1"></i>Save
                </button>
                <button type="button" class="btn btn-sm btn-outline-danger" onclick="deletePost('{comment_id}')" {disabled}>
                    <i class="fas fa-trash me-1"></i>Delete
                </button>
            </td>
        </tr>
        """)

    base_args = {
        'user': user_filter,
        'page_ref': page_filter,
        'text': text_filter,
        'include_deleted': '1' if include_deleted else '0',
    }
    pagination = ''
    if comments.pages > 1:
        page_links = []
        for i in comments.iter_pages():
            if not i:
                continue
            page_args = dict(base_args, page=i)
            active = 'active' if i == comments.page else ''
            page_links.append(
                f'<li class="page-item {active}"><a class="page-link" href="?{urlencode(page_args)}">{i}</a></li>'
            )
        prev_link = ''
        if comments.has_prev:
            prev_link = f'<li class="page-item"><a class="page-link" href="?{urlencode(dict(base_args, page=comments.prev_num))}">Previous</a></li>'
        next_link = ''
        if comments.has_next:
            next_link = f'<li class="page-item"><a class="page-link" href="?{urlencode(dict(base_args, page=comments.next_num))}">Next</a></li>'
        pagination = f"""
        <nav aria-label="Post pagination" class="mt-4">
            <ul class="pagination justify-content-center">
                {prev_link}
                {''.join(page_links)}
                {next_link}
            </ul>
        </nav>
        """

    content = f"""
    <div class="gh-page container mt-4 gh-admin-page">
        {gh_page_header('Post Moderation', f'{total_posts} matching posts', 'fa-comments', breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Post Moderation', None)]))}

        <div class="alert alert-info">
            Edits and deletions are recorded in the append-only event log as moderation events.
        </div>

        <div class="living-module mb-4">
            <div class="living-module-body">
                <form method="GET" class="row g-3">
                    <div class="col-md-3">
                        <label for="user" class="form-label">User</label>
                        <input type="text" class="form-control" id="user" name="user" value="{html_mod.escape(user_filter, quote=True)}" placeholder="Name, username, email">
                    </div>
                    <div class="col-md-3">
                        <label for="page_ref" class="form-label">Page</label>
                        <input type="text" class="form-control" id="page_ref" name="page_ref" value="{html_mod.escape(page_filter, quote=True)}" placeholder="Title, ML number, draft">
                    </div>
                    <div class="col-md-3">
                        <label for="text" class="form-label">Text in post</label>
                        <input type="text" class="form-control" id="text" name="text" value="{html_mod.escape(text_filter, quote=True)}" placeholder="Search comment text">
                    </div>
                    <div class="col-md-2 d-flex align-items-end">
                        <div class="form-check mb-2">
                            <input class="form-check-input" type="checkbox" id="include_deleted" name="include_deleted" value="1" {'checked' if include_deleted else ''}>
                            <label class="form-check-label" for="include_deleted">Include deleted</label>
                        </div>
                    </div>
                    <div class="col-md-1 d-flex align-items-end">
                        <button type="submit" class="btn btn-primary w-100"><i class="fas fa-search"></i></button>
                    </div>
                </form>
            </div>
        </div>

        <div class="living-module">
            <div class="living-module-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead>
                            <tr>
                                <th>User</th>
                                <th>Page</th>
                                <th>Status</th>
                                <th>Post</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {''.join(rows) if rows else '<tr><td colspan="5" class="text-center text-muted py-4">No posts found.</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        {pagination}
    </div>
    <script>
        async function savePost(commentId) {{
            const textarea = document.getElementById('post-text-' + commentId);
            const text = textarea ? textarea.value.trim() : '';
            if (!text) {{
                await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Post text required', message: 'Enter post text before saving.', variant: 'warning' }}), variant: 'info' }});
                return;
            }}
            const response = await fetch('/admin/posts/' + commentId + '/edit', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ text }})
            }});
            const data = await response.json();
            if (!response.ok || !data.success) {{
                await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Save failed', message: data.message || 'Could not save post.', variant: 'danger' }}), variant: 'info' }});
                return;
            }}
            await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Post updated', message: 'The edit was recorded in the moderation event log.', variant: 'success' }}), variant: 'info' }});
            location.reload();
        }}

        async function deletePost(commentId) {{
            const ok = await GhDialog.confirm({{
                title: 'Delete post',
                message: 'Delete this post? The original text will be retained in the moderation event log.',
                variant: 'danger',
                confirmLabel: 'Delete post'
            }});
            if (!ok) return;
            const response = await fetch('/admin/posts/' + commentId + '/delete', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }}
            }});
            const data = await response.json();
            if (!response.ok || !data.success) {{
                await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Delete failed', message: data.message || 'Could not delete post.', variant: 'danger' }}), variant: 'info' }});
                return;
            }}
            await GhDialog.await GhDialog.alert({{ title: 'Notice', message: ({{ title: 'Post deleted', message: 'The deletion was recorded in the moderation event log.', variant: 'success' }}), variant: 'info' }});
            location.reload();
        }}
    </script>
    """

    return _format_base_template(
        title="Post Moderation - GovHub",
        theme=current_theme,
        user_menu=user_menu,
        content=content,
        build_number=BUILD_NUMBER,
    )


@bp.route('/admin/posts/<comment_id>/edit', methods=['POST'])
@require_role('admin')
def admin_edit_post(comment_id):
    _, _, get_current_user, _, _, _ = _get_imports()
    admin_user = get_current_user()
    if not _is_strict_admin(admin_user):
        return jsonify({'success': False, 'message': 'Admin role required'}), 403
    data = request.get_json(silent=True) or {}
    new_text = (data.get('text') or '').strip()
    if not new_text:
        return jsonify({'success': False, 'message': 'Post text is required'}), 400
    if len(new_text) > 8000:
        return jsonify({'success': False, 'message': 'Post text is too long'}), 400
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'success': False, 'message': 'Post not found'}), 404
    if comment.is_deleted:
        return jsonify({'success': False, 'message': 'Deleted posts cannot be edited'}), 400
    old_text = comment.text or ''
    if old_text == new_text:
        return jsonify({'success': True, 'message': 'No changes'})
    if not comment.original_text:
        comment.original_text = old_text
    comment.text = new_text
    comment.edited_at = datetime.utcnow()
    _emit_comment_moderation_event('edit', comment, admin_user, old_text=old_text, new_text=new_text)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Post updated'})


@bp.route('/admin/posts/<comment_id>/delete', methods=['POST'])
@require_role('admin')
def admin_delete_post(comment_id):
    _, _, get_current_user, _, _, _ = _get_imports()
    admin_user = get_current_user()
    if not _is_strict_admin(admin_user):
        return jsonify({'success': False, 'message': 'Admin role required'}), 403
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'success': False, 'message': 'Post not found'}), 404
    if comment.is_deleted:
        return jsonify({'success': True, 'message': 'Post already deleted'})
    old_text = comment.text or ''
    if not comment.original_text:
        comment.original_text = old_text
    comment.is_deleted = True
    comment.text = '[Deleted]'
    comment.edited_at = datetime.utcnow()
    _emit_comment_moderation_event('delete', comment, admin_user, old_text=old_text, new_text='[Deleted]')
    db.session.commit()
    return jsonify({'success': True, 'message': 'Post deleted'})


@bp.route('/admin/users/<username>/role', methods=['POST'])
@require_role('admin')
def change_user_role(username):
    _, _, get_current_user, _, _, _ = _get_imports()
    data = request.get_json()
    new_role = data.get('role', '')

    if new_role not in ['user', 'editor', 'admin']:
        return jsonify({'success': False, 'message': 'Invalid role'}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    current_admin = get_current_user()
    if user.id == current_admin['id'] and new_role != 'admin':
        return jsonify({'success': False, 'message': 'Cannot change your own admin role'}), 400

    user.role = new_role
    db.session.commit()

    add_to_document_history(f"user-{user.id}", "role_changed", current_admin['name'],
                           f"Changed {user.name}'s role to {new_role}")

    return jsonify({'success': True, 'message': f'Role changed to {new_role}'})


@bp.route('/admin/users/<username>/delete', methods=['POST'])
@require_role('admin')
def delete_user(username):
    _, _, get_current_user, _, _, _ = _get_imports()
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'success': False, 'message': 'User not found'}), 404

    current_admin = get_current_user()
    if user.id == current_admin['id']:
        return jsonify({'success': False, 'message': 'Cannot delete your own account'}), 400

    add_to_document_history(f"user-{user.id}", "user_deleted", current_admin['name'],
                           f"Deleted user {user.name} ({user.email})")

    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True, 'message': 'User deleted successfully'})


@bp.route('/admin/analytics/')
@require_role('admin')
def admin_analytics():
    _format_base_template, generate_user_menu, get_current_user, BUILD_NUMBER, _, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')

    active_drafts = Submission.query.order_by(Submission.submitted_at.desc()).limit(20).all()
    active_users = User.query.order_by(User.last_login.desc()).limit(20).all()

    role_stats = db.session.query(User.role, db.func.count(User.id)).group_by(User.role).all()
    role_data = {role: count for role, count in role_stats}

    status_stats = db.session.query(Submission.status, db.func.count(Submission.id)).group_by(Submission.status).all()
    status_data = {status: count for status, count in status_stats}

    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_users_count = User.query.filter(User.created_at >= thirty_days_ago).count()
    recent_submissions = Submission.query.filter(Submission.submitted_at >= thirty_days_ago).count()

    draft_rows = ""
    for i, draft in enumerate(active_drafts, 1):
        draft_rows += f"""
        <tr>
            <td>{i}</td>
            <td>
                <a href="/doc/draft/{draft.id}/" class="text-decoration-none">
                    {draft.title[:60]}{'...' if len(draft.title) > 60 else ''}
                </a>
            </td>
            <td>{', '.join(draft.authors[:2])}{'...' if len(draft.authors) > 2 else ''}</td>
            <td>{draft.group or 'None'}</td>
            <td>{draft.submitted_at.strftime('%Y-%m-%d')}</td>
            <td><span class="badge bg-{ 'warning' if draft.status == 'submitted' else 'success' if draft.status == 'approved' else 'danger' if draft.status == 'rejected' else 'info'}">{draft.status}</span></td>
        </tr>
        """

    user_rows = ""
    for i, user in enumerate(active_users, 1):
        user_rows += f"""
        <tr>
            <td>{i}</td>
            <td>
                <strong>{user.name}</strong><br>
                <small class="text-muted">@{user.username}</small>
            </td>
            <td>{user.email}</td>
            <td><span class="badge bg-{ 'danger' if user.role == 'admin' else 'warning' if user.role == 'editor' else 'secondary'}">{user.role.title()}</span></td>
            <td>{user.created_at.strftime('%Y-%m-%d')}</td>
            <td>{user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'}</td>
        </tr>
        """

    content = f"""
    <div class="gh-page container mt-4 gh-admin-page">
        {gh_page_header('Analytics Dashboard', 'Site usage and activity metrics', 'fa-chart-line', breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Analytics', None)]))}

        <div class="row mb-4">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-info">{recent_users_count}</h4>
                        <p class="mb-0 small">New Users (30 days)</p>
        </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{recent_submissions}</h4>
                        <p class="mb-0 small">New Submissions (30 days)</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-primary">{len(active_drafts)}</h4>
                        <p class="mb-0 small">Total Submissions</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{len(active_users)}</h4>
                        <p class="mb-0 small">Registered Users</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Most Active Drafts</h5>
                        <small class="text-muted">Recent submissions and activity</small>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th>#</th>
                                        <th>Title</th>
                                        <th>Authors</th>
                                        <th>Group</th>
                                        <th>Date</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {draft_rows}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Most Active Users</h5>
                        <small class="text-muted">Users by recent login activity</small>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-hover mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th>#</th>
                                        <th>Name</th>
                                        <th>Email</th>
                                        <th>Role</th>
                                        <th>Joined</th>
                                        <th>Last Login</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {user_rows}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>User Role Distribution</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <strong>Admin:</strong> {role_data.get('admin', 0)} users
                            <div class="progress mb-2">
                                <div class="progress-bar bg-danger" style="width: {(role_data.get('admin', 0) / max(1, sum(role_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Editor:</strong> {role_data.get('editor', 0)} users
                            <div class="progress mb-2">
                                <div class="progress-bar bg-warning" style="width: {(role_data.get('editor', 0) / max(1, sum(role_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>User:</strong> {role_data.get('user', 0)} users
                            <div class="progress mb-2">
                                <div class="progress-bar bg-secondary" style="width: {(role_data.get('user', 0) / max(1, sum(role_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Submission Status Distribution</h5>
                    </div>
                    <div class="card-body">
                        <div class="mb-3">
                            <strong>Submitted:</strong> {status_data.get('submitted', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-warning" style="width: {(status_data.get('submitted', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Approved:</strong> {status_data.get('approved', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-success" style="width: {(status_data.get('approved', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Published:</strong> {status_data.get('published', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-info" style="width: {(status_data.get('published', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                        <div class="mb-3">
                            <strong>Rejected:</strong> {status_data.get('rejected', 0)}
                            <div class="progress mb-2">
                                <div class="progress-bar bg-danger" style="width: {(status_data.get('rejected', 0) / max(1, sum(status_data.values()))) * 100:.1f}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        </div>
        """

    return _format_base_template(
        title="Analytics - GovHub",
        theme=current_theme,
        user_menu=user_menu,
        content=content, build_number=BUILD_NUMBER)


@bp.route('/admin/chairs/')
@require_role('admin')
def admin_chairs():
    _format_base_template, generate_user_menu, get_current_user, BUILD_NUMBER, _, _ = _get_imports()
    current_theme = session.get('theme', 'dark')
    user_menu = generate_user_menu()

    all_chairs = WorkingGroupChair.query.all()
    total_chairs = len(all_chairs)
    approved_chairs = sum(1 for c in all_chairs if c.approved)
    pending_chairs = total_chairs - approved_chairs

    chair_list = ""
    for chair in all_chairs:
        status_badge = 'success' if chair.approved else 'warning'
        status_text = 'Active' if chair.approved else 'Pending'
        set_at_str = chair.set_at.strftime('%Y-%m-%d') if chair.set_at else 'N/A'
        if chair.approved:
            actions = (
                f'<form method="POST" action="/admin/chairs/{chair.id}/delete" class="d-inline">'
                f'<button type="submit" class="btn btn-sm btn-outline-danger" '
                f"onclick=\"(async()=>{{if(!(await GhDialog.confirm({{title:'Remove coordinator',message:'Remove this coordinator?',variant:'warning',confirmLabel:'Remove'}})))return false;return true;}})()\">Delete</button></form>"
            )
        else:
            actions = (
                f'<form method="POST" action="/admin/chairs/{chair.id}/approve" class="d-inline me-1">'
                f'<button type="submit" class="btn btn-sm btn-outline-success" '
                f"onclick=\"(async()=>{{if(!(await GhDialog.confirm({{title:'Approve coordinator',message:'Approve this coordinator?',variant:'warning',confirmLabel:'Approve'}})))return false;return true;}})()\">Approve</button></form>"
                f'<form method="POST" action="/admin/chairs/{chair.id}/delete" class="d-inline">'
                f'<button type="submit" class="btn btn-sm btn-outline-danger" '
                f"onclick=\"(async()=>{{if(!(await GhDialog.confirm({{title:'Delete coordinator',message:'Delete this coordinator?',variant:'warning',confirmLabel:'Delete'}})))return false;return true;}})()\">Delete</button></form>"
            )
        chair_list += f"""
        <tr>
            <td>{chair.chair_name}</td>
            <td>N/A</td>
            <td><code>{chair.group_acronym}</code></td>
            <td><span class="badge bg-{status_badge}">{status_text}</span></td>
            <td>{set_at_str}</td>
            <td>{actions}</td>
        </tr>
        """

    pending_coord_requests = CoordinatorRequest.query.filter_by(status='pending').order_by(CoordinatorRequest.requested_at.desc()).all()
    coord_request_rows = ""
    for req in pending_coord_requests:
        req_at = req.requested_at.strftime('%Y-%m-%d %H:%M') if req.requested_at else ''
        coord_request_rows += f"""
        <tr>
            <td>{req.display_name or req.username}</td>
            <td><code>{req.username}</code></td>
            <td><code>{req.group_acronym}</code></td>
            <td>{req_at}</td>
            <td>
                <form method="POST" action="/admin/coordinator_requests/{req.id}/approve" class="d-inline me-1">
                    <button type="submit" class="btn btn-sm btn-success">Approve</button>
                </form>
                <form method="POST" action="/admin/coordinator_requests/{req.id}/reject" class="d-inline">
                    <button type="submit" class="btn btn-sm btn-outline-danger" onclick="(async()=>{{if(!(await GhDialog.confirm({{title:'Reject request',message:'Reject this request?',variant:'warning',confirmLabel:'Reject'}})))return false;return true;}})()">Reject</button>
                </form>
            </td>
        </tr>
        """
    if not coord_request_rows:
        coord_request_rows = '<tr><td colspan="5" class="text-center text-muted py-3">No pending coordinator requests.</td></tr>'

    content = f"""
    <div class="gh-page container mt-4 gh-admin-page">
        {gh_page_header('Coordinator Management', 'Manage workgroup coordinators – add from User Management or People', 'fa-user-tie', breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Coordinator Management', None)]))}

        <div class="row mb-4">
            <div class="col-md-4">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-primary">{total_chairs}</h4>
                        <small class="text-muted">Total Coordinators</small>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-success">{approved_chairs}</h4>
                        <small class="text-muted">Active Coordinators</small>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card text-center">
                    <div class="card-body">
                        <h4 class="text-warning">{pending_chairs}</h4>
                        <small class="text-muted">Pending Approval</small>
                    </div>
                </div>
            </div>
        </div>

        <div class="card mb-4">
            <div class="card-header">
                <h5 class="mb-0">Pending coordinator requests</h5>
                <small class="text-muted">Users requested coordinator role; approve to grant.</small>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>Display name</th>
                                <th>Username (id)</th>
                                <th>Workgroup</th>
                                <th>Requested</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {coord_request_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-header">
                <h5 class="mb-0">Workgroup Coordinators</h5>
            </div>
            <div class="card-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>Name</th>
                                <th>Email</th>
                                <th>Group</th>
                                <th>Status</th>
                                <th>Added</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {chair_list if chair_list else '<tr><td colspan="6" class="text-center text-muted py-4">No coordinators yet. Add from User Management or People (admin).</td></tr>'}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="mt-4">
            <a href="/admin/member_requests/" class="btn btn-outline-primary">View member requests</a>
        </div>
    </div>
    """

    return _format_base_template(
        title="Coordinator Management - GovHub",
        theme=current_theme,
        user_menu=user_menu,
        content=content, build_number=BUILD_NUMBER)


@bp.route('/admin/users/<user_id>/add-coordinator', methods=['GET', 'POST'])
@require_role('admin')
def add_coordinator_for_user(user_id):
    _, generate_user_menu, get_current_user, _, GROUPS, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = get_current_user().get('theme', 'dark')
    target = User.query.get(user_id)
    if not target:
        flash('User not found', 'error')
        return redirect('/admin/users/')
    display_name = target.name or getattr(target, 'displayName', None) or getattr(target, 'oauthName', None) or target.username

    if request.method == 'POST':
        group_acronym = request.form.get('group_acronym', '').strip()
        if not group_acronym:
            flash('Please select a workgroup', 'error')
        else:
            if not any(g['acronym'] == group_acronym for g in GROUPS):
                flash('Invalid workgroup', 'error')
            else:
                existing = WorkingGroupChair.query.filter_by(
                    group_acronym=group_acronym,
                    user_id=user_id
                ).first()
                if existing:
                    flash(f'{display_name} is already a coordinator for {group_acronym}', 'error')
                else:
                    chair = WorkingGroupChair(
                        group_acronym=group_acronym,
                        chair_name=display_name,
                        user_id=user_id,
                        approved=True
                    )
                    db.session.add(chair)
                    db.session.commit()
                    flash(f'Added {display_name} as coordinator for {group_acronym}', 'success')
                    return redirect('/admin/chairs/')

    group_options = ''.join(
        f'<option value="{g["acronym"]}">{g["acronym"]} – {g.get("name", g["acronym"])}</option>'
        for g in GROUPS
    )
    content = f"""
    <div class="gh-page container mt-4 gh-admin-page">
        {gh_page_header('Add as coordinator', f'User: {display_name} (@{target.username})', 'fa-user-plus', breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('User Management', '/admin/users/'), ('Coordinator Management', '/admin/chairs/'), ('Add as coordinator', None)]))}
        <div class="row justify-content-center">
            <div class="col-md-6">
                {gh_living_module('Workgroup assignment', f'''
                        <form method="POST">
                            <div class="mb-3">
                                <label for="group_acronym" class="form-label">Workgroup *</label>
                                <select class="form-select" id="group_acronym" name="group_acronym" required>
                                    <option value="">Select workgroup</option>
                                    {group_options}
                                </select>
                            </div>
                            <div class="d-flex gap-2">
                                <button type="submit" class="btn btn-primary">Add as coordinator</button>
                                <a href="/admin/users/" class="btn btn-secondary">Cancel</a>
                            </div>
                        </form>
                ''', 'fa-users-cog')}
            </div>
        </div>
    </div>
    """
    return render_page("Add as coordinator - GovHub", content, theme=current_theme, user_menu=user_menu)


@bp.route('/admin/coordinator_requests/<req_id>/approve', methods=['POST'])
@require_role('admin')
def approve_coordinator_request(req_id):
    _, _, get_current_user, _, _, _ = _get_imports()
    req = CoordinatorRequest.query.get(req_id)
    if not req or req.status != 'pending':
        flash('Request not found or already handled', 'error')
        return redirect('/admin/chairs/')
    admin_user = get_current_user()
    chair = WorkingGroupChair(
        group_acronym=req.group_acronym,
        chair_name=req.display_name or req.username,
        user_id=req.user_id,
        approved=True
    )
    db.session.add(chair)
    req.status = 'approved'
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by = admin_user.get('name') or admin_user.get('username')
    db.session.commit()
    flash(f'Coordinator request approved: {req.display_name or req.username} for {req.group_acronym}', 'success')
    return redirect('/admin/chairs/')


@bp.route('/admin/coordinator_requests/<req_id>/reject', methods=['POST'])
@require_role('admin')
def reject_coordinator_request(req_id):
    _, _, get_current_user, _, _, _ = _get_imports()
    req = CoordinatorRequest.query.get(req_id)
    if not req or req.status != 'pending':
        flash('Request not found or already handled', 'error')
        return redirect('/admin/chairs/')
    admin_user = get_current_user()
    req.status = 'rejected'
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by = admin_user.get('name') or admin_user.get('username')
    db.session.commit()
    flash(f'Coordinator request rejected: {req.display_name or req.username}', 'warning')
    return redirect('/admin/chairs/')


@bp.route('/admin/chairs/<chair_id>/approve', methods=['POST'])
@require_role('admin')
def approve_chair(chair_id):
    chair = WorkingGroupChair.query.get(chair_id)
    if chair:
        chair.approved = True
        db.session.commit()
        flash('Coordinator approved successfully', 'success')
    else:
        flash('Coordinator not found', 'error')
    return redirect('/admin/chairs/')


@bp.route('/admin/chairs/<chair_id>/delete', methods=['POST'])
@require_role('admin')
def delete_chair(chair_id):
    chair = WorkingGroupChair.query.get(chair_id)
    if chair:
        db.session.delete(chair)
        db.session.commit()
        flash('Coordinator deleted successfully', 'success')
    else:
        flash('Coordinator not found', 'error')
    return redirect('/admin/chairs/')


# ============================================================================
# Admin Dashboards for Projects/Workgroups/Guilds/Roles/Badges
# ============================================================================

@bp.route('/admin/layers/')
@require_role('admin')
def admin_projects():
    """Admin dashboard for managing projects"""
    _, generate_user_menu, _, _, _, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    # Use same DB counts as admin dashboard so badge matches "Review now" alert
    pending_projects = (
        Layer.query.filter_by(approval_status='pending')
        .group_by(Layer.name)
        .order_by(Layer.last_activity.desc())
        .all()
    )
    approved_projects = (
        Layer.query.filter_by(approval_status='approved')
        .group_by(Layer.name)
        .order_by(Layer.last_activity.desc())
        .all()
    )
    rejected_projects = (
        Layer.query.filter_by(approval_status='rejected')
        .group_by(Layer.name)
        .order_by(Layer.last_activity.desc())
        .all()
    )
    pending_count = len(pending_projects)
    approved_count = len(approved_projects)
    rejected_count = len(rejected_projects)

    def _escape(s):
        if not s:
            return ''
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')

    def _project_row_html(p, show_actions=False):
        mission = ('<p class="mb-2">' + _escape(p.mission) + '</p>') if p.mission else ''
        wg_count = Workgroup.query.filter_by(layer_id=p.id).count()
        created = p.created_at.strftime('%x') if p.created_at else ''
        safe_id = str(p.id).replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
        actions = ''
        if show_actions:
            actions = '''
                <div class="btn-group-vertical ms-3">
                    <button type="button" class="btn btn-sm btn-success btn-approve-project" data-project-id="''' + safe_id + '''">
                        <i class="fas fa-check me-1"></i>Approve
                    </button>
                    <button type="button" class="btn btn-sm btn-danger btn-reject-project" data-project-id="''' + safe_id + '''">
                        <i class="fas fa-times me-1"></i>Reject
                    </button>
                </div>
            '''
        display_status = getattr(p, 'display_status', 'pending') or 'pending'
        display_badge_class = 'bg-success' if display_status == 'active' else 'bg-warning text-dark'
        display_label = 'Active' if display_status == 'active' else 'Pending'
        return '''
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-start">
                    <div class="flex-grow-1">
                        <h5><a href="/layers/''' + (p.slug or '') + '''/" target="_blank">''' + _escape(p.name) + '''</a>
                            <span class="badge ''' + display_badge_class + ''' ms-2" title="Public visibility (controlled by layer admins)">Display: ''' + display_label + '''</span>
                        </h5>
                        ''' + mission + '''
                        <p class="mb-2">''' + _escape(p.description or 'No description') + '''</p>
                        <small class="text-muted">
                            Created: ''' + created + ''' | Status: ''' + _escape(p.status) + ''' | Workgroups: ''' + str(wg_count) + '''
                        </small>
                    </div>
                    ''' + actions + '''
                </div>
            </div>
        '''

    def _list_html(projects, show_actions=False):
        if not projects:
            return '<div class="alert alert-info">No projects in this category</div>'
        parts = ['<div class="list-group">']
        for p in projects:
            parts.append(_project_row_html(p, show_actions))
        parts.append('</div>')
        return ''.join(parts)

    _layers_admin_header = gh_page_header(
        'Manage Layers',
        'Approve and review layer submissions',
        'fa-project-diagram',
        breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Manage Layers', None)]),
    )
    content = """
    <div class="gh-page container mt-4 gh-admin-page" id="manage-projects-container" data-server-pending=""" + str(pending_count) + """ data-server-approved=""" + str(approved_count) + """ data-server-rejected=""" + str(rejected_count) + """>
        """ + _layers_admin_header + """
        <div id="project-load-error" class="alert alert-danger d-none" role="alert"></div>

        <ul class="nav nav-tabs mb-4" id="projectTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="pending-tab" data-bs-toggle="tab" data-bs-target="#pending" type="button">
                    Pending Approval <span class="badge bg-warning ms-2" id="pending-count">""" + str(pending_count) + """</span>
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="approved-tab" data-bs-toggle="tab" data-bs-target="#approved" type="button">
                    Approved <span class="badge bg-success ms-2" id="approved-count">""" + str(approved_count) + """</span>
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="rejected-tab" data-bs-toggle="tab" data-bs-target="#rejected" type="button">
                    Rejected <span class="badge bg-danger ms-2" id="rejected-count">""" + str(rejected_count) + """</span>
                </button>
            </li>
        </ul>

        <div class="tab-content" id="projectTabContent">
            <div class="tab-pane fade show active" id="pending">
                <div id="pending-projects">""" + _list_html(pending_projects, show_actions=True) + """</div>
            </div>
            <div class="tab-pane fade" id="approved">
                <div id="approved-projects">""" + _list_html(approved_projects, show_actions=False) + """</div>
            </div>
            <div class="tab-pane fade" id="rejected">
                <div id="rejected-projects">""" + _list_html(rejected_projects, show_actions=False) + """</div>
            </div>
        </div>
    </div>

    <script>
    async function loadProjects() {
        const errEl = document.getElementById('project-load-error');
        const container = document.getElementById('manage-projects-container');
        const serverPending = container ? parseInt(container.getAttribute('data-server-pending') || '0', 10) : 0;
        try {
            const response = await fetch('/api/layers/?_t=' + Date.now(), { credentials: 'include', cache: 'no-store' });
            if (!response.ok) {
                throw new Error('API returned ' + response.status);
            }
            const data = await response.json();
            const projects = Array.isArray(data.layers) ? data.layers : [];
            function approvalStatus(p) { return (p && p.approval_status != null) ? String(p.approval_status).toLowerCase() : ''; }
            const pending = projects.filter(p => approvalStatus(p) === 'pending');
            const approved = projects.filter(p => approvalStatus(p) === 'approved');
            const rejected = projects.filter(p => approvalStatus(p) === 'rejected');

            document.getElementById('pending-count').textContent = pending.length;
            document.getElementById('approved-count').textContent = approved.length;
            document.getElementById('rejected-count').textContent = rejected.length;

            if (serverPending > 0 && pending.length === 0) {
                document.getElementById('pending-projects').innerHTML =
                    '<div class="alert alert-warning">The list from the server did not load. Showing server-rendered list below. <a href="#" onclick="loadProjects(); return false;">Refresh the list</a>.</div>' +
                    document.getElementById('pending-projects').innerHTML;
            } else {
                displayProjects('pending-projects', pending, true);
            }
            displayProjects('approved-projects', approved, false);
            displayProjects('rejected-projects', rejected, false);
            if (errEl) { errEl.classList.add('d-none'); errEl.textContent = ''; }
        } catch (error) {
            console.error('Error loading projects:', error);
            const msg = 'Failed to load projects: ' + (error.message || 'Please refresh or check console.');
            const pendingEl = document.getElementById('pending-projects');
            if (pendingEl) {
                pendingEl.innerHTML = '<div class="alert alert-danger">' + msg + (serverPending > 0 ? ' The server reports ' + serverPending + ' pending project(s).' : '') + ' <a href="#" onclick="loadProjects(); return false;">Try again</a> or reload the page.</div>';
            }
            if (errEl) {
                errEl.textContent = msg;
                errEl.classList.remove('d-none');
            }
        }
    }

    function displayProjects(containerId, projects, showActions) {
        const container = document.getElementById(containerId);

        if (projects.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No projects in this category</div>';
            return;
        }

        function escapeHtml(text) {
            if (!text) return '';
            return String(text).replace(/&/g, '&amp;').replace(new RegExp('<','g'), '&lt;').replace(/>/g, '&gt;').replace(/\\n/g, '<br>');
        }

        let html = '<div class="list-group">';
        projects.forEach(project => {
            const missionHtml = project.mission ? '<p class="mb-2">' + escapeHtml(project.mission) + '</p>' : '';
            const descHtml = '<p class="mb-2">' + escapeHtml(project.description || 'No description') + '</p>';
            const actionsHtml = showActions ?
                '<div class="btn-group-vertical ms-3">' +
                    '<button type="button" class="btn btn-sm btn-success btn-approve-project" data-project-id="' + project.id + '">' +
                        '<i class="fas fa-check me-1"></i>Approve' +
                    '</button>' +
                    '<button type="button" class="btn btn-sm btn-danger btn-reject-project" data-project-id="' + project.id + '">' +
                        '<i class="fas fa-times me-1"></i>Reject' +
                    '</button>' +
                '</div>' : '';

            html += '<div class="list-group-item">' +
                '<div class="d-flex justify-content-between align-items-start">' +
                    '<div class="flex-grow-1">' +
                        '<h5><a href="/layers/' + project.slug + '/" target="_blank">' + escapeHtml(project.name) + '</a></h5>' +
                        missionHtml +
                        descHtml +
                        '<small class="text-muted">' +
                            'Created: ' + new Date(project.created_at).toLocaleDateString() + ' | ' +
                            'Status: ' + project.status + ' | ' +
                            'Workgroups: ' + (project.workgroups_count || 0) +
                        '</small>' +
                    '</div>' +
                    actionsHtml +
                '</div>' +
            '</div>';
        });
        html += '</div>';

        container.innerHTML = html;
    }

    async function approveProject(projectId) {
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Approve this project?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;

        try {
            const response = await fetch(`/api/layers/${projectId}/approve/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({action: 'approve'})
            });

            if (response.ok) {
                await GhDialog.alert({{ title: 'Notice', message: ('Layer approved successfully'), variant: 'info' }});
                window.location.reload();
            } else {
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: ('Error: ' + (data.error || 'Failed to approve')), variant: 'info' }});
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error approving project'), variant: 'info' }});
        }
    }

    async function rejectProject(projectId) {
        const note = (await GhDialog.prompt({{ title: 'Enter value', message: 'Reason for rejection (optional):', variant: 'info' }}));
        if (note === null) return;

        try {
            const response = await fetch(`/api/layers/${projectId}/approve/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                credentials: 'include',
                body: JSON.stringify({action: 'reject', note: note})
            });

            if (response.ok) {
                await GhDialog.alert({{ title: 'Notice', message: ('Layer rejected'), variant: 'info' }});
                window.location.reload();
            } else {
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: ('Error: ' + (data.error || 'Failed to reject')), variant: 'info' }});
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error rejecting project'), variant: 'info' }});
        }
    }

    // Projects are server-rendered; no API load on page init
    // Event delegation for approve/reject buttons
    const manageContainer = document.getElementById('manage-projects-container');
    if (manageContainer) {
        manageContainer.addEventListener('click', function(e) {
            const approveBtn = e.target.closest('.btn-approve-project');
            const rejectBtn = e.target.closest('.btn-reject-project');
            if (approveBtn) {
                e.preventDefault();
                approveProject(approveBtn.getAttribute('data-project-id'));
            }
            if (rejectBtn) {
                e.preventDefault();
                rejectProject(rejectBtn.getAttribute('data-project-id'));
            }
        });
    }
    </script>
    """

    return render_page("Admin: Manage Layers - GovHub", content, theme=current_theme, user_menu=user_menu)


@bp.route('/admin/workgroups/')
@require_role('admin')
def admin_workgroups():
    """Admin dashboard for managing workgroups"""
    _, generate_user_menu, _, _, _, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    _wg_admin_header = gh_page_header(
        'Manage Workgroups',
        'Review and approve workgroup submissions across layers',
        'fa-users-cog',
        breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Manage Workgroups', None)]),
    )
    content = """
    <div class="gh-page container mt-4 gh-admin-page">
        """ + _wg_admin_header + """

        <ul class="nav nav-tabs mb-4" id="workgroupTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="pending-tab" data-bs-toggle="tab" data-bs-target="#pending" type="button">
                    Pending Approval <span class="badge bg-warning ms-2" id="pending-count">0</span>
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="approved-tab" data-bs-toggle="tab" data-bs-target="#approved" type="button">
                    Approved <span class="badge bg-success ms-2" id="approved-count">0</span>
                </button>
            </li>
        </ul>

        <div class="tab-content" id="workgroupTabContent">
            <div class="tab-pane fade show active" id="pending">
                <div id="pending-workgroups"></div>
            </div>
            <div class="tab-pane fade" id="approved">
                <div id="approved-workgroups"></div>
            </div>
        </div>
    </div>

    <script>
    async function loadWorkgroups() {
        let loadError = '';
        try {
            // Load all projects first
            const projectsResp = await fetch('/api/layers/');
            const projectsData = await projectsResp.json();

            let allWorkgroups = [];

            // Load workgroups from each project. One failing layer must not
            // abort the entire load (which would leave the panel empty while
            // the badge counter was never refreshed), so fan out in parallel
            // and skip individual failures.
            const perLayer = await Promise.allSettled(
                (projectsData.layers || []).map(async (project) => {
                    const wgResp = await fetch(`/api/layers/${project.id}/workgroups/`);
                    if (!wgResp.ok) throw new Error(`HTTP ${wgResp.status} for ${project.slug}`);
                    const wgData = await wgResp.json();
                    wgData.workgroups.forEach(wg => {
                        wg.layer_name = project.name;
                        wg.layer_slug = project.slug;
                        allWorkgroups.push(wg);
                    });
                })
            );
            const failures = perLayer.filter(r => r.status === 'rejected');
            if (failures.length) {
                loadError = failures.map(f => f.reason && f.reason.message).join('; ');
                console.error('Some layers failed to load:', failures);
            }

            const pending = allWorkgroups.filter(wg => wg.approval_status === 'pending');
            const approved = allWorkgroups.filter(wg => wg.approval_status === 'approved');

            document.getElementById('pending-count').textContent = pending.length;
            document.getElementById('approved-count').textContent = approved.length;

            displayWorkgroups('pending-workgroups', pending, true);
            displayWorkgroups('approved-workgroups', approved, false);
        } catch (error) {
            loadError = (loadError ? loadError + ' | ' : '') + (error.message || String(error));
            console.error('Error loading workgroups:', error);
        }
        // Surface diagnostic info inside the panel area so an empty queue
        // is never silently empty.
        if (loadError) {
            const pe = document.getElementById('pending-workgroups');
            if (pe && pe.querySelector('.alert-info')) {
                pe.innerHTML = `<div class="alert alert-warning">Some layers failed to load: ${loadError}</div>`;
            }
        }
    }

    function displayWorkgroups(containerId, workgroups, showActions) {
        const container = document.getElementById(containerId);

        if (!container) return;

        if (workgroups.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No workgroups in this category</div>';
            return;
        }

        let html = '<div class="list-group">';
        workgroups.forEach(wg => {
            const desc = (wg.description || 'No description').replace(/[&<>"']/g, c => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
            }[c]));
            const layerName = (wg.layer_name || '').replace(/[&<>"']/g, c => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
            }[c]));
            const wgName = (wg.name || '').replace(/[&<>"']/g, c => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
            }[c]));
            let created = '';
            try { created = new Date(wg.created_at).toLocaleDateString(); }
            catch (_e) { created = wg.created_at || ''; }
            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h5><a href="/workgroups/${wg.slug}/" target="_blank">${wgName}</a></h5>
                            <p class="mb-2">${desc}</p>
                            <small class="text-muted">
                                Layer: <a href="/layers/${wg.layer_slug}/" target="_blank">${layerName}</a> |
                                Created: ${created} |
                                Status: ${wg.status}
                            </small>
                        </div>
                        ${showActions ? `
                            <div class="btn-group-vertical ms-3">
                                <button class="btn btn-sm btn-success" onclick="approveWorkgroup('${wg.id}')">
                                    <i class="fas fa-check me-1"></i>Approve
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="rejectWorkgroup('${wg.id}')">
                                    <i class="fas fa-times me-1"></i>Reject
                                </button>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';

        container.innerHTML = html;
    }

    async function approveWorkgroup(workgroupId) {
        const confirmed = await GhDialog.confirm({
            title: 'Approve workgroup',
            message: 'Approve this workgroup?',
            variant: 'warning',
        });
        if (!confirmed) return;

        try {
            const response = await fetch(`/api/workgroups/${workgroupId}/approve/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'approve'})
            });

            if (response.ok) {
                await GhDialog.alert({
                    title: 'Approved',
                    message: 'Workgroup approved successfully.',
                    variant: 'success',
                });
                loadWorkgroups();
            } else {
                const data = await response.json();
                await GhDialog.alert({
                    title: 'Could not approve',
                    message: data.error || 'Failed to approve',
                    variant: 'danger',
                });
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({
                title: 'Error',
                message: 'Error approving workgroup.',
                variant: 'danger',
            });
        }
    }

    async function rejectWorkgroup(workgroupId) {
        const note = (await GhDialog.prompt({{ title: 'Enter value', message: 'Reason for rejection (optional):', variant: 'info' }}));
        if (note === null) return;

        try {
            const response = await fetch(`/api/workgroups/${workgroupId}/approve/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'reject', note: note})
            });

            if (response.ok) {
                await GhDialog.alert({
                    title: 'Rejected',
                    message: 'Workgroup rejected.',
                    variant: 'success',
                });
                loadWorkgroups();
            } else {
                const data = await response.json();
                await GhDialog.alert({
                    title: 'Could not reject',
                    message: data.error || 'Failed to reject',
                    variant: 'danger',
                });
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({
                title: 'Error',
                message: 'Error rejecting workgroup.',
                variant: 'danger',
            });
        }
    }

    // Load workgroups on page load
    loadWorkgroups();
    </script>
    """

    return render_page("Admin: Manage Workgroups - GovHub", content, theme=current_theme, user_menu=user_menu)


# ============================================================================
# Chair nominations API (used by admin chair-nominations page)
# ============================================================================

@bp.route('/api/admin/chair-nominations/', methods=['GET'])
@require_role('admin')
def api_admin_get_chair_nominations():
    """Get all chair nominations with full details for admin dashboard"""
    from sqlalchemy import text

    query = text("""
        SELECT
            wgc.id,
            wgc.chair_name,
            wgc.approved,
            wgc.set_at,
            wgc.statement,
            wgc.is_self_nomination,
            wgc.nominee_email,
            wgc.nominee_profile_url,
            wgc.position_key,
            wgc.status,
            wgc.group_acronym,
            wg.name as workgroup_name,
            wg.slug as workgroup_slug,
            p.name as layer_name,
            p.slug as layer_slug,
            u.id as nominee_id,
            u.username as nominee_username,
            u.profileImage as nominee_profile_image,
            nominator.id as nominator_id,
            nominator.username as nominator_username,
            nominator.displayName as nominator_name
        FROM working_group_chair wgc
        LEFT JOIN working_group wg ON wgc.group_acronym = wg.acronym
        LEFT JOIN layer p ON wg.layer_id = p.id
        LEFT JOIN user u ON wgc.user_id = u.id
        LEFT JOIN user nominator ON wgc.nominated_by_user_id = nominator.id
        ORDER BY wgc.approved ASC, wgc.set_at DESC
    """)

    results = db.session.execute(query).fetchall()

    nominations = []
    for row in results:
        nominations.append({
            'id': row[0],
            'chair_name': row[1],
            'approved': coerce_storage_bool(row[2]),
            'set_at': row[3],
            'statement': row[4],
            'is_self_nomination': coerce_storage_bool(row[5]),
            'nominee_email': row[6],
            'nominee_profile_url': row[7],
            'position_key': row[8] or 'chair',
            'position_label': position_label(row[8] or 'chair'),
            'status': row[9] or NOMINATION_STATUS_NOMINEE_ACCEPTED,
            'status_label': status_label(row[9] or NOMINATION_STATUS_NOMINEE_ACCEPTED),
            'workgroup_acronym': row[10],
            'workgroup_name': row[11],
            'workgroup_slug': row[12],
            'layer_name': row[13],
            'layer_slug': row[14],
            'nominee_id': row[15],
            'nominee_username': row[16],
            'nominee_profile_image': avatar_url(row[17], 48) if row[17] else '/static/images/default-avatar.png',
            'nominator_id': row[18],
            'nominator_username': row[19],
            'nominator_name': row[20]
        })

    return jsonify({'nominations': nominations, 'count': len(nominations)})


@bp.route('/api/admin/chair-nominations/<nomination_id>/approve/', methods=['POST'])
@require_role('admin')
def api_admin_approve_chair_nomination(nomination_id):
    """Approve a position nomination (nominee must have accepted first)."""
    nomination = WorkingGroupChair.query.get(nomination_id)
    if not nomination:
        return jsonify({'error': 'Nomination not found'}), 404
    if nomination.status != NOMINATION_STATUS_NOMINEE_ACCEPTED:
        return jsonify({'error': 'Nominee must accept before admin approval'}), 400

    nomination.approved = True
    nomination.status = NOMINATION_STATUS_APPROVED
    db.session.commit()
    send_admin_decision(nomination, approved=True)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Nomination approved'})


@bp.route('/api/admin/chair-nominations/<nomination_id>/reject/', methods=['POST'])
@require_role('admin')
def api_admin_reject_chair_nomination(nomination_id):
    """Reject a position nomination."""
    nomination = WorkingGroupChair.query.get(nomination_id)
    if not nomination:
        return jsonify({'error': 'Nomination not found'}), 404

    nomination.approved = False
    nomination.status = NOMINATION_STATUS_REJECTED
    db.session.commit()
    send_admin_decision(nomination, approved=False)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Nomination rejected'})


@bp.route('/admin/chair-nominations/')
@require_role('admin')
def admin_chair_nominations():
    """Admin dashboard for managing chair nominations"""
    _, generate_user_menu, _, _, _, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    _chair_admin_header = gh_page_header(
        'Position Nominations',
        'Review nominations after nominees accept',
        'fa-user-check',
        breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Position Nominations', None)]),
    )
    content = """
    <div class="gh-page container mt-4 gh-admin-page">
        """ + _chair_admin_header + """

        <ul class="nav nav-tabs mb-4" id="chairTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="pending-tab" data-bs-toggle="tab" data-bs-target="#pending" type="button">
                    Pending <span class="badge bg-warning ms-2" id="pending-count">0</span>
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="approved-tab" data-bs-toggle="tab" data-bs-target="#approved" type="button">
                    Approved <span class="badge bg-success ms-2" id="approved-count">0</span>
                </button>
            </li>
        </ul>

        <div class="tab-content" id="chairTabContent">
            <div class="tab-pane fade show active" id="pending">
                <div id="pending-nominations"></div>
            </div>
            <div class="tab-pane fade" id="approved">
                <div id="approved-nominations"></div>
            </div>
        </div>
    </div>

    <script>
    async function loadNominations() {
        try {
            const response = await fetch('/api/admin/chair-nominations/');
            const data = await response.json();

            // Count nominations by status
            const pendingNoms = data.nominations.filter(n => n.status === 'nominee_accepted' && !n.approved);
            const approvedNoms = data.nominations.filter(n => n.approved || n.status === 'approved');
            const awaitingNominee = data.nominations.filter(n => n.status === 'pending_nominee');

            document.getElementById('pending-count').textContent = pendingNoms.length;
            document.getElementById('approved-count').textContent = approvedNoms.length;

            // Render pending nominations
            let pendingHtml = '';
            if (pendingNoms.length > 0) {
                pendingHtml = '<div class="row">';
                pendingNoms.forEach(nom => {
                    pendingHtml += renderNominationCard(nom, 'pending');
                });
                pendingHtml += '</div>';
            } else {
                pendingHtml = '<div class="alert alert-info">No nominations ready for admin approval.</div>';
            }
            if (awaitingNominee.length > 0) {
                pendingHtml += '<h6 class="mt-4 text-muted">Awaiting nominee response (' + awaitingNominee.length + ')</h6><div class="row">';
                awaitingNominee.forEach(nom => {
                    pendingHtml += renderNominationCard(nom, 'awaiting');
                });
                pendingHtml += '</div>';
            }
            document.getElementById('pending-nominations').innerHTML = pendingHtml;

            // Render approved nominations
            let approvedHtml = '';
            if (approvedNoms.length > 0) {
                approvedHtml = '<div class="row">';
                approvedNoms.forEach(nom => {
                    approvedHtml += renderNominationCard(nom, 'approved');
                });
                approvedHtml += '</div>';
            } else {
                approvedHtml = '<div class="alert alert-info">No approved chair nominations</div>';
            }
            document.getElementById('approved-nominations').innerHTML = approvedHtml;

        } catch (error) {
            console.error('Error loading nominations:', error);
            document.getElementById('pending-nominations').innerHTML = '<div class="alert alert-danger">Error loading nominations</div>';
        }
    }

    function renderNominationCard(nom, status) {
        const selfNomBadge = nom.is_self_nomination ? '<span class="badge bg-info ms-2">Self</span>' : '';
        const statusBadge = nom.approved ? '<span class="badge bg-success">Approved</span>' : `<span class="badge bg-secondary">${nom.status_label || 'Pending'}</span>`;
        const posBadge = `<span class="badge bg-primary me-2">${nom.position_label || 'Chair'}</span>`;

        return `
            <div class="col-md-6 mb-4">
                <div class="card">
                    <div class="card-header">
                        <div class="d-flex justify-content-between align-items-center">
                            <h5 class="mb-0">${posBadge}${nom.workgroup_name}</h5>
                            ${statusBadge}
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-3">
                            <img
                                src="${nom.nominee_profile_image || '/static/images/default-avatar.png'}"
                                class="rounded-circle me-3"
                                style="width: 60px; height: 60px; object-fit: cover;"
                                onerror="this.src='/static/images/default-avatar.png'"
                            >
                            <div>
                                <h6 class="mb-0">
                                    ${nom.nominee_username ? `<a href="/profile/${nom.nominee_username}/" target="_blank">${nom.chair_name}</a>` : nom.chair_name}
                                    ${selfNomBadge}
                                </h6>
                                <small class="text-muted">Nominated ${new Date(nom.set_at).toLocaleDateString()}</small>
                            </div>
                        </div>

                        ${nom.nominator_name && !nom.is_self_nomination ? `
                            <p class="mb-2"><small><strong>Nominated by:</strong>
                                <a href="/profile/${nom.nominator_username}/" target="_blank">${nom.nominator_name}</a>
                            </small></p>
                        ` : ''}

                        ${nom.nominee_email ? `
                            <p class="mb-2"><small><strong>Email:</strong>
                                <a href="mailto:${nom.nominee_email}">${nom.nominee_email}</a>
                            </small></p>
                        ` : ''}

                        ${nom.nominee_profile_url ? `
                            <p class="mb-2"><small><strong>CV / LinkedIn:</strong>
                                <a href="${nom.nominee_profile_url}" target="_blank" rel="noopener noreferrer">View profile</a>
                            </small></p>
                        ` : ''}

                        <div class="mb-3">
                            <strong>Statement:</strong>
                            <p class="mt-1">${nom.statement || 'No statement provided'}</p>
                        </div>

                        <div class="mb-2">
                            <strong>Workgroup:</strong>
                            <a href="/workgroups/${nom.workgroup_slug}/" target="_blank">${nom.workgroup_name}</a>
                        </div>

                        <div class="mb-3">
                            <strong>Layer:</strong>
                            <a href="/layers/${nom.layer_slug}/" target="_blank">${nom.layer_name}</a>
                        </div>

                        ${status === 'pending' ? `
                            <div class="d-flex gap-2">
                                <button class="btn btn-success flex-fill" onclick="approveNomination('${nom.id}')">
                                    <i class="fas fa-check me-2"></i>Approve
                                </button>
                                <button class="btn btn-danger flex-fill" onclick="rejectNomination('${nom.id}')">
                                    <i class="fas fa-times me-2"></i>Reject
                                </button>
                            </div>
                        ` : (status === 'awaiting' ? '<p class="small text-muted mb-0">Nominee has not accepted yet.</p>' : '')}
                    </div>
                </div>
            </div>
        `;
    }

    async function approveNomination(nominationId) {
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Approve this chair nomination?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;

        try {
            const response = await fetch(`/api/admin/chair-nominations/${nominationId}/approve/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            const data = await response.json();
            if (response.ok) {
                await GhDialog.alert({{ title: 'Notice', message: ('Nomination approved!'), variant: 'info' }});
                loadNominations();
            } else {
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to approve nomination'), variant: 'info' }});
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Failed to approve nomination'), variant: 'info' }});
        }
    }

    async function rejectNomination(nominationId) {
        const reason = (await GhDialog.prompt({{ title: 'Enter value', message: 'Reason for rejection (optional):', variant: 'info' }}));
        if (reason === null) return; // User cancelled

        try {
            const response = await fetch(`/api/admin/chair-nominations/${nominationId}/reject/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason: reason })
            });

            const data = await response.json();
            if (response.ok) {
                await GhDialog.alert({{ title: 'Notice', message: ('Nomination rejected'), variant: 'info' }});
                loadNominations();
            } else {
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to reject nomination'), variant: 'info' }});
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Failed to reject nomination'), variant: 'info' }});
        }
    }

    // Load nominations on page load
    loadNominations();
    </script>
    """

    return render_page("Admin: Chair Nominations - GovHub", content, theme=current_theme, user_menu=user_menu)


@bp.route('/admin/roles/')
@require_role('admin')
def admin_roles():
    """Admin dashboard for managing roles"""
    _, generate_user_menu, _, _, _, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    _roles_admin_header = gh_page_header(
        'Manage Roles',
        'Review draft and approved roles across all layers',
        'fa-user-tag',
        breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Manage Roles', None)]),
    )
    content = """
    <div class="gh-page container mt-4 gh-admin-page">
        """ + _roles_admin_header + """

        <ul class="nav nav-tabs mb-4" id="roleTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="draft-tab" data-bs-toggle="tab" data-bs-target="#draft" type="button">
                    Draft <span class="badge bg-secondary ms-2" id="draft-count">0</span>
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="approved-tab" data-bs-toggle="tab" data-bs-target="#approved" type="button">
                    Approved <span class="badge bg-success ms-2" id="approved-count">0</span>
                </button>
            </li>
        </ul>

        <div class="tab-content" id="roleTabContent">
            <div class="tab-pane fade show active" id="draft">
                <div id="draft-roles"></div>
            </div>
            <div class="tab-pane fade" id="approved">
                <div id="approved-roles"></div>
            </div>
        </div>
    </div>

    <script>
    async function loadRoles() {
        try {
            // Load all projects first
            const projectsResp = await fetch('/api/layers/');
            const projectsData = await projectsResp.json();

            let allRoles = [];

            // Load roles from all projects
            for (const project of projectsData.layers) {
                const rolesResp = await fetch(`/api/layers/${project.id}/roles/`);
                const rolesData = await rolesResp.json();

                // Add project info to each role
                rolesData.roles.forEach(role => {
                    role.layer_name = project.name;
                    role.layer_slug = project.slug;
                    allRoles.push(role);
                });
            }

            const draft = allRoles.filter(r => r.status === 'draft');
            const approved = allRoles.filter(r => r.status === 'approved');

            document.getElementById('draft-count').textContent = draft.length;
            document.getElementById('approved-count').textContent = approved.length;

            displayRoles('draft-roles', draft, true);
            displayRoles('approved-roles', approved, false);
        } catch (error) {
            console.error('Error loading roles:', error);
        }
    }

    function displayRoles(containerId, roles, showActions) {
        const container = document.getElementById(containerId);

        if (roles.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No roles in this category</div>';
            return;
        }

        let html = '<div class="list-group">';
        roles.forEach(role => {
            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h5>${role.title_guild}</h5>
                            ${role.title_operational ? `<h6 class="text-muted">${role.title_operational}</h6>` : ''}
                            <p class="mb-2">${(role.description || '').substring(0, 200)}...</p>
                            <small class="text-muted">
                                Layer: <a href="/layers/${role.layer_slug}/" target="_blank">${role.layer_name}</a> |
                                Created: ${new Date(role.created_at).toLocaleDateString()} |
                                Public: ${role.public_visible ? 'Yes' : 'No'}
                            </small>
                        </div>
                        ${showActions ? `
                            <div class="btn-group-vertical ms-3">
                                <button class="btn btn-sm btn-success" onclick="approveRole('${role.id}')">
                                    <i class="fas fa-check me-1"></i>Approve
                                </button>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';

        container.innerHTML = html;
    }

    async function approveRole(roleId) {
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Approve this role?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;

        try {
            const response = await fetch(`/api/roles/${roleId}/approve/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'approve'})
            });

            if (response.ok) {
                await GhDialog.alert({{ title: 'Notice', message: ('Role approved successfully'), variant: 'info' }});
                loadRoles();
            } else {
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: ('Error: ' + (data.error || 'Failed to approve')), variant: 'info' }});
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error approving role'), variant: 'info' }});
        }
    }

    // Load roles on page load
    loadRoles();
    </script>
    """

    return render_page("Admin: Manage Roles - GovHub", content, theme=current_theme, user_menu=user_menu)


@bp.route('/admin/badges/')
@require_role('admin')
def admin_badges():
    """Admin dashboard for managing and issuing badges"""
    _, generate_user_menu, _, _, _, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')

    _badges_admin_header = gh_page_header(
        'Manage Badges',
        'Review badge requests and issue badges',
        'fa-award',
        breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Manage Badges', None)]),
    )
    content = """
    <div class="gh-page container mt-4 gh-admin-page">
        """ + _badges_admin_header + """

        <ul class="nav nav-tabs mb-4" id="badgeTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="requested-tab" data-bs-toggle="tab" data-bs-target="#requested" type="button">
                    Requested <span class="badge bg-warning ms-2" id="requested-count">0</span>
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="approved-tab" data-bs-toggle="tab" data-bs-target="#approved" type="button">
                    Approved <span class="badge bg-success ms-2" id="approved-count">0</span>
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="issued-tab" data-bs-toggle="tab" data-bs-target="#issued" type="button">
                    Issued <span class="badge bg-primary ms-2" id="issued-count">0</span>
                </button>
            </li>
        </ul>

        <div class="tab-content" id="badgeTabContent">
            <div class="tab-pane fade show active" id="requested">
                <div id="requested-badges"></div>
            </div>
            <div class="tab-pane fade" id="approved">
                <div id="approved-badges"></div>
            </div>
            <div class="tab-pane fade" id="issued">
                <div id="issued-badges"></div>
            </div>
        </div>
    </div>

    <script>
    async function loadBadges() {
        try {
            // Load all projects first
            const projectsResp = await fetch('/api/layers/');
            const projectsData = await projectsResp.json();

            let allBadges = [];

            // Load badges from all projects
            for (const project of projectsData.layers) {
                const badgesResp = await fetch(`/api/layers/${project.id}/badges/`);
                const badgesData = await badgesResp.json();

                // Add project info to each badge
                badgesData.badges.forEach(badge => {
                    badge.layer_name = project.name;
                    badge.layer_slug = project.slug;
                    allBadges.push(badge);
                });
            }

            const requested = allBadges.filter(b => b.status === 'requested');
            const approved = allBadges.filter(b => b.status === 'approved');
            const issued = allBadges.filter(b => b.status === 'issued');

            document.getElementById('requested-count').textContent = requested.length;
            document.getElementById('approved-count').textContent = approved.length;
            document.getElementById('issued-count').textContent = issued.length;

            displayBadges('requested-badges', requested, 'approve');
            displayBadges('approved-badges', approved, 'issue');
            displayBadges('issued-badges', issued, 'none');
        } catch (error) {
            console.error('Error loading badges:', error);
        }
    }

    function displayBadges(containerId, badges, actionType) {
        const container = document.getElementById(containerId);

        if (badges.length === 0) {
            container.innerHTML = '<div class="alert alert-info">No badges in this category</div>';
            return;
        }

        let html = '<div class="list-group">';
        badges.forEach(badge => {
            html += `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <h5>Badge: ${badge.badge_type}</h5>
                            <p class="mb-2">
                                <strong>Claim ID:</strong> ${badge.claim_id}<br>
                                <strong>Claimant ID:</strong> ${badge.claimant_id}<br>
                                <strong>Custody:</strong> ${badge.custody_mode}<br>
                                ${badge.btc_taproot_address ? `<strong>BTC Address:</strong> ${badge.btc_taproot_address}<br>` : ''}
                                ${badge.inscription_id ? `<strong>Inscription:</strong> ${badge.inscription_id}<br>` : ''}
                            </p>
                            <small class="text-muted">
                                Layer: <a href="/layers/${badge.layer_slug}/" target="_blank">${badge.layer_name}</a> |
                                Created: ${new Date(badge.created_at).toLocaleDateString()}
                            </small>
                        </div>
                        ${actionType === 'approve' ? `
                            <div class="btn-group-vertical ms-3">
                                <button class="btn btn-sm btn-success" onclick="approveBadge('${badge.id}')">
                                    <i class="fas fa-check me-1"></i>Approve
                                </button>
                                <button class="btn btn-sm btn-danger" onclick="denyBadge('${badge.id}')">
                                    <i class="fas fa-times me-1"></i>Deny
                                </button>
                            </div>
                        ` : actionType === 'issue' ? `
                            <div class="btn-group-vertical ms-3">
                                <button class="btn btn-sm btn-primary" onclick="issueBadge('${badge.id}')">
                                    <i class="fas fa-certificate me-1"></i>Issue
                                </button>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });
        html += '</div>';

        container.innerHTML = html;
    }

    async function approveBadge(badgeId) {
        const note = (await GhDialog.prompt({{ title: 'Enter value', message: 'Approval note (optional):', variant: 'info' }}));
        if (note === null) return;

        try {
            const response = await fetch(`/api/badges/${badgeId}/approve/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: 'approve', approval_note: note})
            });

            if (response.ok) {
                await GhDialog.alert({{ title: 'Notice', message: ('Badge approved successfully'), variant: 'info' }});
                loadBadges();
            } else {
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: ('Error: ' + (data.error || 'Failed to approve')), variant: 'info' }});
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error approving badge'), variant: 'info' }});
        }
    }

    async function denyBadge(badgeId) {
        const note = (await GhDialog.prompt({{ title: 'Enter value', message: 'Reason for denial:', variant: 'info' }}));
        if (!note) return;

        try {
            const response = await fetch(`/api/badges/${badgeId}/approve/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({approve: false, approval_note: note})
            });

            if (response.ok) {
                await GhDialog.alert({{ title: 'Notice', message: ('Badge denied'), variant: 'info' }});
                loadBadges();
            } else {
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: ('Error: ' + (data.error || 'Failed to deny')), variant: 'info' }});
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error denying badge'), variant: 'info' }});
        }
    }

    async function issueBadge(badgeId) {
        const inscriptionId = (await GhDialog.prompt({{ title: 'Enter value', message: 'Enter inscription ID:', variant: 'info' }}));
        if (!inscriptionId) return;

        const txRef = (await GhDialog.prompt({{ title: 'Enter value', message: 'Enter transaction reference (optional):', variant: 'info' }}));

        try {
            const response = await fetch(`/api/badges/${badgeId}/issue/`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    inscription_id: inscriptionId,
                    tx_ref: txRef || null,
                    chain: 'bitcoin'
                })
            });

            if (response.ok) {
                await GhDialog.alert({{ title: 'Notice', message: ('Badge issued successfully'), variant: 'info' }});
                loadBadges();
            } else {
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: ('Error: ' + (data.error || 'Failed to issue')), variant: 'info' }});
            }
        } catch (error) {
            console.error('Error:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error issuing badge'), variant: 'info' }});
        }
    }

    // Load badges on page load
    loadBadges();
    </script>
    """

    return render_page("Admin: Manage Badges - GovHub", content, theme=current_theme, user_menu=user_menu)


def _load_platform_invite_target(invitation):
    try:
        target = json.loads(invitation.target_json or '{}')
        return target if isinstance(target, dict) else {}
    except json.JSONDecodeError:
        return {}


def _workgroup_invitation_counts(workgroup):
    invitations = PlatformInvitation.query.filter_by(invite_type='join_workgroup').all()
    matching = []
    for inv in invitations:
        target = _load_platform_invite_target(inv)
        if (
            target.get('workgroup_id') == workgroup.id
            or target.get('workgroup_acronym') == workgroup.acronym
        ):
            matching.append(inv)
    sent = len([inv for inv in matching if inv.status != 'revoked'])
    private_accepted = len([inv for inv in matching if inv.status == 'accepted'])
    shareable_ids = [inv.id for inv in matching if getattr(inv, 'binding_mode', None) == 'shareable']
    shareable_accepted = 0
    if shareable_ids:
        shareable_accepted = PlatformInvitationAcceptance.query.filter(
            PlatformInvitationAcceptance.invitation_id.in_(shareable_ids)
        ).count()
    return sent, private_accepted + shareable_accepted


def _approved_position_names(workgroup, position_key):
    rows = WorkingGroupChair.query.filter(
        WorkingGroupChair.group_acronym == workgroup.acronym,
        WorkingGroupChair.position_key == position_key,
        db.or_(
            WorkingGroupChair.status == NOMINATION_STATUS_APPROVED,
            WorkingGroupChair.approved.is_(True),
        ),
    ).order_by(WorkingGroupChair.set_at.asc()).all()
    return [row.chair_name for row in rows if row.chair_name]


@bp.route('/admin/dp-readiness/')
@require_role('admin')
def admin_dp_readiness():
    """Recruitment readiness snapshot for DP Challenge workgroups."""
    _format_base_template, generate_user_menu, _, BUILD_NUMBER, _, _ = _get_imports()
    current_theme = session.get('theme', 'dark')
    user_menu = generate_user_menu()

    rows_html = []
    workgroups = [wg for wg in Workgroup.query.order_by(Workgroup.name.asc()).all() if is_dp_workgroup(wg)]
    for wg in workgroups:
        lead_names = []
        if wg.coordinator:
            lead_names.append(wg.coordinator.displayName or wg.coordinator.username)
        lead_names.extend(_approved_position_names(wg, 'chair'))
        co_leads = _approved_position_names(wg, 'co_lead')
        member_count = WorkingGroupMember.query.filter_by(group_acronym=wg.acronym).count()
        pending_members = WorkgroupMemberRequest.query.filter_by(
            group_acronym=wg.acronym,
            status='pending',
        ).count()
        invites_sent, invites_accepted = _workgroup_invitation_counts(wg)
        badge = dp_contributor_badge_status(wg)
        badge_class = 'success' if badge['ready'] else 'warning'
        rows_html.append(f"""
        <tr>
            <td>
                <a href="/workgroups/{html_mod.escape(wg.slug or wg.acronym)}/">{html_mod.escape(wg.name)}</a>
                <div class="small text-muted"><code>{html_mod.escape(wg.acronym or '')}</code></div>
            </td>
            <td>{html_mod.escape(', '.join(dict.fromkeys(lead_names)) or 'Unassigned')}</td>
            <td>{html_mod.escape(', '.join(dict.fromkeys(co_leads)) or 'None')}</td>
            <td class="text-end">{member_count}</td>
            <td class="text-end">{invites_sent}</td>
            <td class="text-end">{invites_accepted}</td>
            <td class="text-end">{pending_members}</td>
            <td>
                <span class="badge bg-{badge_class}">{'Ready' if badge['ready'] else 'Needs setup'}</span>
                <div class="small text-muted">{html_mod.escape(badge['note'])}</div>
            </td>
        </tr>
        """)

    if not rows_html:
        rows_html.append(
            '<tr><td colspan="8" class="text-center text-muted py-4">No DP workgroups found yet.</td></tr>'
        )

    content = f"""
    <div class="gh-page container mt-4 gh-admin-page">
        {gh_page_header('DP Challenge readiness', 'Recruitment operations for July 1-15 workgroup launch', 'fa-clipboard-check', actions_html='<a href="/admin/member_requests/" class="btn btn-outline-secondary btn-sm">Member Requests</a>', breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('DP Challenge readiness', None)]))}
        <div class="alert alert-info">
            <strong>Permissions:</strong> leads and co-leads can edit workgroups and invite members; members can participate after joining. Contributor badges are off-chain for now and may be preserved on Inscription Day in a future operations step.
        </div>
        <div class="living-module">
            <div class="living-module-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="table-light">
                            <tr>
                                <th>Workgroup</th>
                                <th>Lead</th>
                                <th>Co-leads</th>
                                <th class="text-end">Members</th>
                                <th class="text-end">Invites sent</th>
                                <th class="text-end">Accepted</th>
                                <th class="text-end">Pending approvals</th>
                                <th>Badge readiness</th>
                            </tr>
                        </thead>
                        <tbody>{''.join(rows_html)}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    """
    return _format_base_template(title="DP Challenge readiness - GovHub", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER)


@bp.route('/admin/member_requests/')
@require_role('admin')
def admin_member_requests():
    """List pending workgroup member requests (when workgroup has members_require_approval=True). Default: no approval."""
    _format_base_template, generate_user_menu, _, BUILD_NUMBER, _, _ = _get_imports()
    current_theme = session.get('theme', 'dark')
    user_menu = generate_user_menu()

    pending = WorkgroupMemberRequest.query.filter_by(status='pending').order_by(WorkgroupMemberRequest.requested_at.desc()).all()
    rows = ""
    for req in pending:
        req_at = req.requested_at.strftime('%Y-%m-%d %H:%M') if req.requested_at else ''
        rows += f"""
        <tr>
            <td>{req.user_name}</td>
            <td><code>{req.group_acronym}</code></td>
            <td>{req_at}</td>
            <td>
                <a href="/admin/member_requests/{req.id}/approve" class="btn btn-sm btn-success">Approve</a>
                <a href="/admin/member_requests/{req.id}/reject" class="btn btn-sm btn-outline-danger">Reject</a>
            </td>
        </tr>
        """
    if not rows:
        rows = '<tr><td colspan="4" class="text-center text-muted py-4">No pending member requests. (Default is no approval; join is instant.)</td></tr>'

    content = f"""
    <div class="gh-page container mt-4 gh-admin-page">
        {gh_page_header('Member requests', 'When a workgroup requires approval, join requests appear here', 'fa-user-plus', actions_html='<a href="/admin/chairs/" class="btn btn-outline-secondary btn-sm">Coordinator Management</a>', breadcrumb_html=gh_breadcrumb([('Admin Dashboard', '/admin/'), ('Coordinator Management', '/admin/chairs/'), ('Member requests', None)]))}
        <div class="living-module">
            <div class="living-module-body p-0">
                <div class="table-responsive">
                    <table class="table table-hover mb-0">
                        <thead class="table-light">
                            <tr><th>User</th><th>Workgroup</th><th>Requested</th><th>Actions</th></tr>
                        </thead>
                        <tbody>{rows}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    """
    return _format_base_template(title="Member requests - GovHub", theme=current_theme, user_menu=user_menu, content=content, build_number=BUILD_NUMBER)


@bp.route('/admin/member_requests/<req_id>/approve')
@require_role('admin')
def approve_member_request(req_id):
    req = WorkgroupMemberRequest.query.get(req_id)
    if not req or req.status != 'pending':
        flash('Request not found or already handled', 'error')
        return redirect('/admin/member_requests/')
    # Membership is by user_id only; avoid duplicate
    if req.user_id:
        existing = WorkingGroupMember.query.filter_by(group_acronym=req.group_acronym, user_id=req.user_id).first()
        if not existing:
            membership = WorkingGroupMember(
                group_acronym=req.group_acronym,
                user_id=req.user_id,
                user_name=req.user_name or ''
            )
            db.session.add(membership)
    req.status = 'approved'
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by = get_current_user().get('name') or get_current_user().get('username')
    db.session.commit()
    flash(f'Member approved: {req.user_name} for {req.group_acronym}', 'success')
    return redirect('/admin/member_requests/')


@bp.route('/admin/member_requests/<req_id>/reject')
@require_role('admin')
def reject_member_request(req_id):
    req = WorkgroupMemberRequest.query.get(req_id)
    if not req or req.status != 'pending':
        flash('Request not found or already handled', 'error')
        return redirect('/admin/member_requests/')
    req.status = 'rejected'
    req.reviewed_at = datetime.utcnow()
    req.reviewed_by = get_current_user().get('name') or get_current_user().get('username')
    db.session.commit()
    flash(f'Member request rejected: {req.user_name}', 'warning')
    return redirect('/admin/member_requests/')
