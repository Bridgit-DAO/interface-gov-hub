"""Pages routes: home, profile, my-layers, short UUID redirects."""
import json
from datetime import datetime

from flask import Blueprint, request, redirect, url_for, flash, session, g, render_template_string
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User, Submission, Layer, Vote, Role, Claim, Badge, EmailUnsubscribe
from services.identity import get_current_user, require_auth
from services.utils import _is_uuid_like
from services.email import verify_unsubscribe_token

bp = Blueprint('pages', __name__, url_prefix='')


def _get_imports():
    """Late imports to avoid circular imports."""
    from services.rendering import _format_base_template, generate_user_menu
    from config import BUILD_NUMBER
    from services.documents import DRAFTS
    from services.groups import GROUPS
    from templates.html_templates import PROFILE_TEMPLATE
    return _format_base_template, generate_user_menu, BUILD_NUMBER, DRAFTS, GROUPS, PROFILE_TEMPLATE


@bp.route('/')
def home():
    """Home page."""
    _format_base_template, generate_user_menu, BUILD_NUMBER, DRAFTS, GROUPS, _ = _get_imports()

    if getattr(g, 'layer', None):
        path = url_for('layers_pages.layer_detail', layer_slug=g.layer.slug)
        prefix = request.headers.get('X-Forwarded-Prefix', '').rstrip('/')
        return redirect((prefix + path) if prefix else path)

    current_user = get_current_user()
    current_theme = current_user.get('theme', 'dark') if current_user else 'dark'
    user_menu = generate_user_menu()

    doc_count = len(DRAFTS) + Submission.query.filter(
        Submission.status.in_(['approved', 'published'])
    ).count()

    return _format_base_template(
        title="MLGH",
        theme=current_theme,
        user_menu=user_menu,
        content=f"""
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-8">
                <p class="lead">Welcome to the Governance Hub for the Meta-Layer!</p>

                <div class="row">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-project-diagram me-2"></i>Layers</h5>
                            </div>
                            <div class="card-body">
                                <p>Browse and discover MLTF layers and their workgroups.</p>
                                <a href="/layers/" class="btn btn-primary">View Layers</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-users me-2"></i>Workgroups</h5>
                            </div>
                            <div class="card-body">
                                <p>Browse workgroups across all projects and their activities.</p>
                                <a href="/workgroups/" class="btn btn-primary">View Workgroups</a>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row mt-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-shield-alt me-2"></i>Guilds</h5>
                            </div>
                            <div class="card-body">
                                <p>Cross-project collaboration groups and communities.</p>
                                <a href="/guilds/" class="btn btn-primary">View Guilds</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-user-tag me-2"></i>Roles</h5>
                            </div>
                            <div class="card-body">
                                <p>Explore and claim roles across all projects.</p>
                                <a href="/roles/" class="btn btn-primary">Browse Roles</a>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row mt-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-user-friends me-2"></i>People</h5>
                            </div>
                            <div class="card-body">
                                <p>Directory of Meta-Layer participants and contributors.</p>
                                <a href="/person/" class="btn btn-primary">View People</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-file-alt me-2"></i>Documents</h5>
                            </div>
                            <div class="card-body">
                                <p>View the latest Meta-Layer documents including drafts and RFCs.</p>
                                <a href="/doc/all/" class="btn btn-primary">View All Documents</a>
                            </div>
                        </div>
                    </div>
                </div>

                <div class="row mt-4">
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-medal me-2"></i>Badges</h5>
                            </div>
                            <div class="card-body">
                                <p>Browse and vote on visual representations for roles across all projects.</p>
                                <a href="/badges/" class="btn btn-primary">View Badges</a>
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card">
                            <div class="card-header">
                                <h5><i class="fas fa-list-ol me-2"></i>Waitlists</h5>
                            </div>
                            <div class="card-body">
                                <p>Join waitlists for upcoming projects, features, and opportunities.</p>
                                <a href="/waitlists/" class="btn btn-primary">View Waitlists</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card">
                    <div class="card-header">
                        <h5>Quick Stats</h5>
                    </div>
                    <div class="card-body">
                        <p><strong>Documents:</strong> {doc_count}</p>
                        <p><strong>Workgroups:</strong> {len(GROUPS)}</p>
                        <p><strong>Last Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """,
        build_number=BUILD_NUMBER,
        hypothesis_config="",
    )


@bp.route('/my-layers/')
@require_auth
def my_projects():
    """Redirect to current user's profile with My Projects tab active."""
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('pages.home'))
    user = User.query.get(current_user['id'])
    if not user:
        return redirect(url_for('pages.home'))
    return redirect(f'/profile/{user.username}/#my-projects')


@bp.route('/profile/', methods=['GET', 'POST'])
@require_auth
def profile():
    """User profile management."""
    _format_base_template, generate_user_menu, BUILD_NUMBER, _, _, PROFILE_TEMPLATE = _get_imports()

    if request.method == 'GET':
        return redirect(url_for('profile_edit'))

    current_user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action')
        user = User.query.filter_by(username=session['user']).first()

        if action == 'update_password':
            old_password = request.form.get('old_password', '').strip()
            new_password = request.form.get('new_password', '').strip()

            if check_password_hash(user.password_hash, old_password):
                if len(new_password) >= 6:
                    user.password_hash = generate_password_hash(new_password)
                    db.session.commit()
                    flash('Password updated successfully!', 'success')
                else:
                    flash('New password must be at least 6 characters.', 'error')
            else:
                flash('Current password is incorrect.', 'error')

        elif action == 'update_profile':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()

            existing_email = User.query.filter(
                User.email == email, User.username != session['user']
            ).first()
            if existing_email:
                flash('Email already registered to another account.', 'error')
            else:
                if name:
                    user.name = name
                if email:
                    user.email = email
                db.session.commit()
                flash('Profile updated successfully!', 'success')

        elif action == 'update_theme':
            theme = request.form.get('theme', 'dark').strip()
            if theme in ['light', 'dark', 'auto']:
                user.theme = theme
                db.session.commit()
                session['theme'] = theme
                flash('Theme preference updated successfully!', 'success')
            else:
                flash('Invalid theme selection.', 'error')

    user_menu = generate_user_menu()
    current_theme = current_user.get('theme', 'dark')
    light_selected = 'selected' if current_theme == 'light' else ''
    dark_selected = 'selected' if current_theme == 'dark' else ''
    auto_selected = 'selected' if current_theme == 'auto' else ''

    profile_content = PROFILE_TEMPLATE.format(
        current_user_name=current_user['name'],
        current_user_email=current_user['email'],
        current_user_theme=current_theme,
        light_selected=light_selected,
        dark_selected=dark_selected,
        auto_selected=auto_selected,
        session_user=session['user']
    )
    return render_template_string(_format_base_template(
        title="Profile - MLGH",
        theme=current_theme,
        user_menu=user_menu,
        content=profile_content,
        build_number=BUILD_NUMBER,
        hypothesis_config=""
    ))


# UUID-based canonical redirect routes
@bp.route('/p/<public_id>')
def person_by_public_id(public_id):
    """Resolve person by public_id UUID."""
    user = User.query.filter_by(public_id=public_id).first_or_404()
    return redirect(url_for('user_profile', username=user.username or user.handle))


@bp.route('/layer/<layer_ref>')
@bp.route('/layer/<layer_ref>/')
def layer_standalone(layer_ref):
    """Standalone layer view: layer branding, tabs as nav, Overview as home. Resolves by slug or public_id (UUID)."""
    from routes.layer_detail_render import _render_layer_standalone
    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()
    return _render_layer_standalone(project.slug)


@bp.route('/layer/<layer_ref>/workgroups/')
def layer_standalone_workgroups(layer_ref):
    """Layer-scoped workgroups page. Stays in layer view."""
    from services.rendering import render_layer_standalone_page, generate_user_menu
    from services.utils import _is_uuid_like

    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()

    import html as html_mod
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    layer_name_esc = html_mod.escape(project.name or project.slug)

    content = f'''
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/layer/{project.slug}/">{layer_name_esc}</a></li>
                <li class="breadcrumb-item active">Workgroups</li>
            </ol>
        </nav>
        <div class="row mb-4">
            <div class="col-md-8">
                <h1>Workgroups</h1>
                <p class="lead">Workgroups in {layer_name_esc}</p>
            </div>
            <div class="col-md-4 text-end">
                <a href="/layer/{project.slug}/" class="btn btn-secondary mb-2 w-100"><i class="fas fa-arrow-left me-2"></i>Back to Layer</a>
            </div>
        </div>
        <div class="row mb-4">
            <div class="col-md-6">
                <label for="status-filter" class="form-label">Status:</label>
                <select id="status-filter" class="form-select" onchange="loadWorkgroups()">
                    <option value="">All Statuses</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="completed">Completed</option>
                    <option value="archived">Archived</option>
                </select>
            </div>
            <div class="col-md-6">
                <label for="search-input" class="form-label">Search:</label>
                <input type="text" id="search-input" class="form-control" placeholder="Search workgroups..." onkeyup="filterWorkgroups()">
            </div>
        </div>
        <div id="workgroups-container" class="row">
            <div class="col-12 text-center py-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>
        </div>
    </div>
    <script>
    const layerId = "{project.id}";
    let allWorkgroups = [];
    const allProjects = [{{ id: "{project.id}", name: {json.dumps(project.name or project.slug)} }}];
    async function loadWorkgroups() {{
        const statusFilter = document.getElementById("status-filter").value;
        try {{
            let url = "/api/layers/" + layerId + "/workgroups/";
            if (statusFilter) url += "?status=" + statusFilter;
            const res = await fetch(url);
            const data = await res.json();
            allWorkgroups = data.workgroups || [];
            displayWorkgroups(allWorkgroups);
        }} catch (e) {{
            document.getElementById("workgroups-container").innerHTML = '<div class="col-12"><div class="alert alert-danger">Error loading workgroups</div></div>';
        }}
    }}
    function filterWorkgroups() {{
        const term = (document.getElementById("search-input").value || "").toLowerCase();
        const filtered = allWorkgroups.filter(w => (w.name || "").toLowerCase().includes(term) || (w.description || "").toLowerCase().includes(term));
        displayWorkgroups(filtered);
    }}
    function displayWorkgroups(workgroups) {{
        const c = document.getElementById("workgroups-container");
        if (!workgroups.length) {{ c.innerHTML = '<div class="col-12"><div class="alert alert-info">No workgroups yet.</div></div>'; return; }}
        let html = "";
        workgroups.forEach(wg => {{
            const statusBadge = wg.status === "active" ? '<span class="badge bg-success">Active</span>' : wg.status === "inactive" ? '<span class="badge bg-warning">Inactive</span>' : wg.status === "completed" ? '<span class="badge bg-primary">Completed</span>' : '<span class="badge bg-secondary">Archived</span>';
            const approvalBadge = wg.approval_status === "pending" ? '<span class="badge bg-warning">Pending</span>' : wg.approval_status === "approved" ? '<span class="badge bg-success">Approved</span>' : wg.approval_status === "rejected" ? '<span class="badge bg-danger">Rejected</span>' : "";
            html += '<div class="col-md-6 col-lg-4 mb-4"><div class="card h-100"><div class="card-body"><h5 class="card-title"><a href="/workgroups/' + (wg.slug || wg.id) + '/">' + (wg.name || "Unnamed").replace(/</g, "&lt;").replace(/>/g, "&gt;") + '</a></h5><div class="mb-2">' + statusBadge + " " + approvalBadge + '</div><p class="card-text text-muted">' + (wg.description || "No description").replace(/</g, "&lt;").replace(/>/g, "&gt;").slice(0, 120) + '</p></div></div></div>';
        }});
        c.innerHTML = html;
    }}
    loadWorkgroups();
    </script>
    '''
    return render_layer_standalone_page(
        f"{project.name or project.slug} - Workgroups",
        content,
        layer_name=project.name or project.slug,
        layer_slug=project.slug,
        layer_image_url=project.image_url,
        theme=current_theme,
        user_menu=user_menu,
    )


@bp.route('/layer/<layer_ref>/roles/')
def layer_standalone_roles(layer_ref):
    """Layer-scoped roles page. Lists roles for this layer."""
    from services.rendering import render_layer_standalone_page, generate_user_menu
    from services.utils import _is_uuid_like

    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()

    import html as html_mod
    layer_name_esc = html_mod.escape(project.name or project.slug)
    content = f'''
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/layer/{project.slug}/">{layer_name_esc}</a></li>
                <li class="breadcrumb-item active">Roles</li>
            </ol>
        </nav>
        <div class="row mb-4">
            <div class="col-md-8">
                <h1>Roles</h1>
                <p class="lead">Roles in {layer_name_esc}</p>
            </div>
            <div class="col-md-4 text-end">
                <a href="/layer/{project.slug}/" class="btn btn-secondary mb-2 w-100"><i class="fas fa-arrow-left me-2"></i>Back to Layer</a>
            </div>
        </div>
        <div class="row mb-4">
            <div class="col-md-6">
                <label for="status-filter" class="form-label">Status:</label>
                <select id="status-filter" class="form-select" onchange="loadRoles()">
                    <option value="">All</option>
                    <option value="approved">Approved</option>
                    <option value="draft">Draft</option>
                </select>
            </div>
            <div class="col-md-6">
                <label for="search-input" class="form-label">Search:</label>
                <input type="text" id="search-input" class="form-control" placeholder="Search roles..." onkeyup="filterRoles()">
            </div>
        </div>
        <div id="roles-container" class="row">
            <div class="col-12 text-center py-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>
        </div>
    </div>
    <script>
    const layerId = "{project.id}";
    const layerSlug = {json.dumps(project.slug)};
    let allRoles = [];
    async function loadRoles() {{
        const statusFilter = document.getElementById("status-filter").value;
        try {{
            let url = "/api/layers/" + layerId + "/roles/";
            if (statusFilter) url += "?status=" + statusFilter;
            const res = await fetch(url);
            const data = await res.json();
            allRoles = data.roles || [];
            displayRoles(allRoles);
        }} catch (e) {{
            document.getElementById("roles-container").innerHTML = '<div class="col-12"><div class="alert alert-danger">Error loading roles</div></div>';
        }}
    }}
    function filterRoles() {{
        const term = (document.getElementById("search-input").value || "").toLowerCase();
        const filtered = allRoles.filter(r =>
            (r.title_guild || "").toLowerCase().includes(term) ||
            (r.title_operational || "").toLowerCase().includes(term) ||
            (r.description || "").toLowerCase().includes(term)
        );
        displayRoles(filtered);
    }}
    function displayRoles(roles) {{
        const c = document.getElementById("roles-container");
        if (!roles.length) {{ c.innerHTML = '<div class="col-12"><div class="alert alert-info">No roles yet.</div></div>'; return; }}
        let html = "";
        roles.forEach(r => {{
            const slug = r.role_slug || r.slug || r.id;
            const title = (r.title_guild || r.title_operational || "Role").replace(/</g, "&lt;").replace(/>/g, "&gt;");
            const desc = (r.description || "").replace(/</g, "&lt;").replace(/>/g, "&gt;").slice(0, 150) + (r.description && r.description.length > 150 ? "…" : "");
            const statusCls = r.status === "approved" ? "success" : "secondary";
            html += '<div class="col-md-6 col-lg-4 mb-4"><div class="card h-100"><div class="card-body"><h5 class="card-title"><a href="/layer/' + layerSlug + '/roles/' + slug + '/">' + title + '</a></h5><p class="card-text text-muted small">' + desc + '</p><span class="badge bg-' + statusCls + '">' + (r.status || "draft") + '</span></div></div></div>';
        }});
        c.innerHTML = html;
    }}
    loadRoles();
    </script>
    '''
    return render_layer_standalone_page(
        f"{project.name or project.slug} - Roles",
        content,
        layer_name=project.name or project.slug,
        layer_slug=project.slug,
        layer_image_url=project.image_url,
    )


@bp.route('/layer/<layer_ref>/votes/')
@bp.route('/layer/<layer_ref>/artifacts/')
@bp.route('/layer/<layer_ref>/opportunities/')
def layer_standalone_section(layer_ref):
    """Layer-scoped section placeholder. Links to full view in MLGH."""
    from services.rendering import render_layer_standalone_page, generate_user_menu
    from services.utils import _is_uuid_like

    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()

    section = request.path.rstrip('/').split('/')[-1]
    section_title = section.replace('-', ' ').title()
    import html as html_mod
    layer_name_esc = html_mod.escape(project.name or project.slug)
    content = f'''
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/layer/{project.slug}/">{layer_name_esc}</a></li>
                <li class="breadcrumb-item active">{section_title}</li>
            </ol>
        </nav>
        <h1 class="mb-3">{section_title}</h1>
        <p class="text-muted mb-4">View full {section} in MLGH.</p>
        <a href="/layers/{project.slug}/#{section}" class="btn btn-primary"><i class="fas fa-external-link-alt me-2"></i>View in MLGH</a>
        <a href="/layer/{project.slug}/" class="btn btn-outline-secondary ms-2"><i class="fas fa-arrow-left me-2"></i>Back to Layer</a>
    </div>
    '''
    return render_layer_standalone_page(
        f"{project.name or project.slug} - {section_title}",
        content,
        layer_name=project.name or project.slug,
        layer_slug=project.slug,
        layer_image_url=project.image_url,
    )


@bp.route('/layer/<layer_ref>/waitlists/')
def layer_standalone_waitlists(layer_ref):
    """Layer-scoped waitlists. Stays in layer view."""
    from services.rendering import render_layer_standalone_page, generate_user_menu
    from routes.directory import build_waitlists_content

    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()

    content = build_waitlists_content(project.slug)
    return render_layer_standalone_page(
        f"{project.name or project.slug} - Waitlists",
        content,
        layer_name=project.name or project.slug,
        layer_slug=project.slug,
        layer_image_url=project.image_url,
    )


@bp.route('/layer/<layer_ref>/submit/')
@bp.route('/layer/<layer_ref>/submit/immortalize/')
def layer_standalone_submit(layer_ref):
    """Redirect to submit with layer param. Immortalize uses tab=immortalize."""
    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()
    tab = 'immortalize' if '/immortalize' in request.path else None
    params = f"?layer={project.slug}" + (f"&tab={tab}" if tab else "")
    return redirect(f"/submit/{params}")


@bp.route('/layer/<layer_ref>/person/')
def layer_standalone_person(layer_ref):
    """Redirect to people directory with layer param."""
    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()
    return redirect(f"/person/?layer={project.slug}")


@bp.route('/layer/<layer_ref>/guilds/')
def layer_standalone_guilds(layer_ref):
    """Redirect to guilds directory with layer param."""
    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()
    return redirect(f"/guilds/?layer={project.slug}")


@bp.route('/layer/<layer_ref>/artifacts/<artifact_id>/')
def layer_standalone_artifact(layer_ref, artifact_id):
    """Redirect to artifact detail in full MLGH view."""
    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()
    return redirect(f"/layers/{project.slug}/artifacts/{artifact_id}/")


@bp.route('/layer/<layer_ref>/quests/<quest_id>/')
def layer_standalone_quest(layer_ref, quest_id):
    """Redirect to quest detail in full MLGH view (no layer-scoped quest page yet)."""
    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()
    return redirect(f"/layers/{project.slug}/quests/{quest_id}/")


@bp.route('/layer/<layer_ref>/badges/')
def layer_standalone_badges(layer_ref):
    """Redirect to badges directory with layer param."""
    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()
    return redirect(f"/badges/?layer={project.slug}")


@bp.route('/layer/<layer_ref>/doc/', defaults={'doc_path': 'all'})
@bp.route('/layer/<layer_ref>/doc/<path:doc_path>')
def layer_standalone_doc(layer_ref, doc_path):
    """Redirect to docs with layer param."""
    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()
    return redirect(f"/doc/{doc_path}?layer={project.slug}")


@bp.route('/layer/<layer_ref>/about/')
def layer_standalone_about(layer_ref):
    """Standalone layer about page."""
    from services.rendering import render_layer_standalone_page, generate_user_menu
    from services.ordinals import process_ordinal_markdown

    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()

    import html as html_mod
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    raw = (project.about_content or '').strip()
    html_content = process_ordinal_markdown(raw) if raw else '<p class="text-muted">No about content yet.</p>'

    content = f'''
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/layer/{project.slug}/">{html_mod.escape(project.name or project.slug)}</a></li>
                <li class="breadcrumb-item active">About</li>
            </ol>
        </nav>
        <h1 class="mb-4">About {html_mod.escape(project.name or project.slug)}</h1>
        <div class="about-content" style="max-width: 720px;">
            {html_content}
        </div>
    </div>
    '''
    return render_layer_standalone_page(
        f"{project.name or project.slug} Gov-Hub - About",
        content,
        layer_name=project.name or project.slug,
        layer_slug=project.slug,
        layer_image_url=project.image_url,
        theme=current_theme,
        user_menu=user_menu,
    )


@bp.route('/draft/<public_id>')
def draft_by_public_id(public_id):
    """Resolve draft/submission by public_id UUID."""
    submission = Submission.query.filter_by(public_id=public_id).first_or_404()
    draft_name = submission.draft_name or submission.id
    return redirect(url_for('documents.draft_detail', draft_name=draft_name))


@bp.route('/vote/<public_id>')
def vote_by_public_id_redirect(public_id):
    """Resolve vote by public_id UUID - redirect to detail page."""
    vote = Vote.query.filter_by(public_id=public_id).first_or_404()
    return redirect(url_for('votes_pages.vote_detail', vote_public_id=vote.public_id))


@bp.route('/role/<public_id>')
def role_by_public_id(public_id):
    """Resolve role by public_id UUID."""
    role = Role.query.filter_by(public_id=public_id).first_or_404()
    return redirect(url_for('role_detail', role_slug=role.role_slug))


@bp.route('/claim/<public_id>')
def claim_by_public_id(public_id):
    """Resolve claim by public_id UUID - redirect to role page."""
    claim = Claim.query.filter_by(public_id=public_id).first_or_404()
    role = Role.query.get_or_404(claim.role_id)
    return redirect(url_for('role_detail', role_slug=role.role_slug))


@bp.route('/badge/<public_id>')
def badge_by_public_id(public_id):
    """Resolve badge by public_id UUID - redirect to role page."""
    badge = Badge.query.filter_by(public_id=public_id).first_or_404()
    claim = Claim.query.get_or_404(badge.claim_id)
    role = Role.query.get_or_404(claim.role_id)
    return redirect(url_for('role_detail', role_slug=role.role_slug))


@bp.route('/unsubscribe')
def unsubscribe_from_project():
    """Handle unsubscribe link. Token encodes layer_id and user_id/email."""
    token = request.args.get('token', '')
    if not token:
        return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Unsubscribe</title></head><body style="font-family:sans-serif;max-width:500px;margin:40px auto;padding:20px;">
        <h2>Invalid link</h2>
        <p>This unsubscribe link is invalid.</p>
        <p><a href="/">Return to MLGH</a></p></body></html>""", 400

    decoded = verify_unsubscribe_token(token)
    if not decoded:
        return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Unsubscribe</title></head><body style="font-family:sans-serif;max-width:500px;margin:40px auto;padding:20px;">
        <h2>Invalid link</h2>
        <p>This unsubscribe link is invalid or expired.</p>
        <p><a href="/">Return to MLGH</a></p></body></html>""", 400

    layer_id_val, user_id_or_email = decoded
    project = Layer.query.get(layer_id_val)
    if not project:
        return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Unsubscribe</title></head><body style="font-family:sans-serif;max-width:500px;margin:40px auto;padding:20px;">
        <h2>Layer not found</h2>
        <p><a href="/">Return to MLGH</a></p></body></html>""", 404

    if user_id_or_email and len(str(user_id_or_email)) == 36 and '-' in str(user_id_or_email):
        uid = str(user_id_or_email)
        existing = EmailUnsubscribe.query.filter_by(layer_id=layer_id_val, user_id=uid).first()
        if not existing:
            db.session.add(EmailUnsubscribe(layer_id=layer_id_val, user_id=uid, email=None))
            db.session.commit()
    elif user_id_or_email and str(user_id_or_email).isdigit():
        try:
            uid = str(user_id_or_email)
            existing = EmailUnsubscribe.query.filter_by(layer_id=layer_id_val, user_id=uid).first()
            if not existing:
                db.session.add(EmailUnsubscribe(layer_id=layer_id_val, user_id=uid, email=None))
                db.session.commit()
        except Exception:
            pass
    else:
        email = user_id_or_email.lower() if user_id_or_email else ''
        existing = EmailUnsubscribe.query.filter_by(layer_id=layer_id_val, email=email).first()
        if not existing:
            db.session.add(EmailUnsubscribe(layer_id=layer_id_val, user_id=None, email=email))
            db.session.commit()

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Unsubscribed</title></head><body style="font-family:sans-serif;max-width:500px;margin:40px auto;padding:20px;">
    <h2 style="color:#00ba7c;">You've been unsubscribed</h2>
    <p>You will no longer receive project emails from <strong>{project.name}</strong>.</p>
    <p><a href="/">Return to MLGH</a></p></body></html>""", 200
