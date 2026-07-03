"""Pages routes: home, profile, my-layers, short UUID redirects."""
import json
from datetime import datetime

from flask import Blueprint, request, redirect, url_for, flash, session, g, render_template_string, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models import User, Submission, Layer, Vote, Role, Claim, Badge, EmailUnsubscribe
from services.identity import get_current_user, require_auth
from services.utils import _is_uuid_like
from services.email import verify_unsubscribe_token
from services.directory_ui import gh_page_header, gh_breadcrumb, gh_filter_row, gh_filter_col, gh_directory_grid, gh_directory_toolbar, gh_living_module

bp = Blueprint('pages', __name__, url_prefix='')


def _get_imports():
    """Late imports to avoid circular imports."""
    from services.rendering import (
        _format_base_template,
        generate_user_menu,
        build_home_hub_cards_html,
        build_home_hero_subtitle,
    )
    from config import BUILD_NUMBER
    from services.documents import DRAFTS
    from services.groups import GROUPS
    from templates.html_templates import PROFILE_TEMPLATE
    return (
        _format_base_template,
        generate_user_menu,
        BUILD_NUMBER,
        DRAFTS,
        GROUPS,
        PROFILE_TEMPLATE,
        build_home_hub_cards_html,
        build_home_hero_subtitle,
    )


@bp.route('/')
def home():
    """Home page."""
    (
        _format_base_template,
        generate_user_menu,
        BUILD_NUMBER,
        DRAFTS,
        GROUPS,
        _,
        build_home_hub_cards_html,
        build_home_hero_subtitle,
    ) = _get_imports()
    from services.platform_activity import (
        build_home_activity_rotator_html,
        get_platform_activity_items,
    )

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
    hub_cards_html = build_home_hub_cards_html()
    hero_subtitle = build_home_hero_subtitle()
    activity_html = build_home_activity_rotator_html(get_platform_activity_items(7))

    return _format_base_template(
        title="Gov Hub",
        theme=current_theme,
        user_menu=user_menu,
        content=f"""
    <div class="gh-page container mt-4">
        <div class="gh-home-hero gh-home-hero--visual">
            <div class="gh-home-hero-banner">
                <img
                    src="/static/images/gov-hub-home-hero.png"
                    alt="Gov Hub — Interface Governance Hub"
                    width="1600"
                    height="900"
                    loading="eager"
                    decoding="async"
                    class="gh-home-hero-img"
                />
            </div>
        </div>
        <div class="gh-home-hero-tagline-box">
            <p class="gh-home-hero-tagline">{hero_subtitle}</p>
        </div>
        {activity_html}
        <div class="row g-4">
            <div class="col-lg-8">
                <div class="gh-home-hub">
                    {hub_cards_html}
                </div>
            </div>
            <div class="col-lg-4">
                <div class="gh-home-stats">
                    <h2>Quick stats</h2>
                    <p class="mb-2"><strong>Documents:</strong> {doc_count}</p>
                    <p class="mb-2"><strong>Workgroups:</strong> {len(GROUPS)}</p>
                    <p class="mb-0 text-muted small"><strong>Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                </div>
            </div>
        </div>
    </div>
    """,
        build_number=BUILD_NUMBER,
    )


@bp.route('/api/platform/activity/')
def platform_activity_api():
    """Recent platform activity for home rotator (JSON)."""
    limit = request.args.get('limit', 7, type=int)
    from services.platform_activity import get_platform_activity_items

    return jsonify({'items': get_platform_activity_items(limit)})


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
    if request.method == 'GET':
        current_user = get_current_user()
        if current_user:
            user = User.query.get(current_user['id'])
            if user and user.username:
                return redirect(url_for('profile_pages.user_profile', username=user.username))
        return redirect(url_for('pages.home'))

    _format_base_template, generate_user_menu, BUILD_NUMBER, _, _, PROFILE_TEMPLATE, _, _ = _get_imports()

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
    <div class="gh-page container mt-4">
        {gh_page_header('Workgroups', f'Workgroups in {layer_name_esc}', 'fa-users-cog', actions_html=f'<a href="/layer/{project.slug}/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-1"></i>Layer</a>', breadcrumb_html=f'<nav aria-label="breadcrumb" class="gh-detail-breadcrumb"><ol class="breadcrumb"><li class="breadcrumb-item"><a href="/layer/{project.slug}/">{layer_name_esc}</a></li><li class="breadcrumb-item active">Workgroups</li></ol></nav>')}
        {gh_filter_row(
            gh_filter_col('Status', '<select id="status-filter" class="form-select" onchange="loadWorkgroups()"><option value="">All Statuses</option><option value="active" selected>Active</option><option value="inactive">Inactive</option><option value="completed">Completed</option><option value="archived">Archived</option></select>', 'col-md-3')
            + gh_directory_toolbar(search_placeholder='Search workgroups…', search_col='col-md-5', sort_col='col-md-2', sort_default='name-asc')
        )}
        <div id="workgroups-container" class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3">
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
            filterWorkgroups();
        }} catch (e) {{
            document.getElementById("workgroups-container").innerHTML = '<div class="col-12"><div class="alert alert-danger">Error loading workgroups</div></div>';
        }}
    }}
    function filterWorkgroups() {{
        const items = GhDirectory.filterAndSort(allWorkgroups, {{
            searchTerm: GhDirectory.getSearchValue('search-input'),
            sort: GhDirectory.getSortValue('sort-filter') || 'name-asc',
            searchFields: ['name', 'description', 'acronym', 'slug'],
            nameKey: 'name',
            dateKeys: ['updated_at', 'created_at'],
        }});
        displayWorkgroups(items);
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
    GhDirectory.bindControls('search-input', 'sort-filter', filterWorkgroups);
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
    <div class="gh-page container mt-4">
        {gh_page_header('Roles', f'Roles in {layer_name_esc}', 'fa-user-tag', actions_html=f'<a href="/layer/{project.slug}/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-1"></i>Layer</a>', breadcrumb_html=f'<nav aria-label="breadcrumb" class="gh-detail-breadcrumb"><ol class="breadcrumb"><li class="breadcrumb-item"><a href="/layer/{project.slug}/">{layer_name_esc}</a></li><li class="breadcrumb-item active">Roles</li></ol></nav>')}
        {gh_filter_row(
            gh_filter_col('Status', '<select id="status-filter" class="form-select" onchange="loadRoles()"><option value="">All</option><option value="approved" selected>Active</option><option value="draft">Draft</option></select>', 'col-md-3')
            + gh_directory_toolbar(search_placeholder='Search roles…', search_col='col-md-5', sort_col='col-md-2')
        )}
        <div id="roles-container" class="row row-cols-1 row-cols-md-2 row-cols-lg-3 g-3">
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
            filterRoles();
        }} catch (e) {{
            document.getElementById("roles-container").innerHTML = '<div class="col-12"><div class="alert alert-danger">Error loading roles</div></div>';
        }}
    }}
    function filterRoles() {{
        const items = GhDirectory.filterAndSort(allRoles, {{
            searchTerm: GhDirectory.getSearchValue('search-input'),
            sort: GhDirectory.getSortValue('sort-filter'),
            searchFields: ['title_guild', 'title_operational', 'description', 'slug'],
            nameKey: 'title_guild',
            dateKeys: ['updated_at', 'created_at'],
        }});
        displayRoles(items);
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
    GhDirectory.bindControls('search-input', 'sort-filter', filterRoles);
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
    <div class="gh-page container mt-4">
        {gh_page_header(section_title, f'View full {section} in MLGH', 'fa-compass', actions_html=f'<a href="/layers/{project.slug}/#{section}" class="btn btn-primary btn-sm me-1"><i class="fas fa-external-link-alt me-1"></i>View in MLGH</a><a href="/layer/{project.slug}/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-1"></i>Layer</a>', breadcrumb_html=f'<nav aria-label="breadcrumb" class="gh-detail-breadcrumb"><ol class="breadcrumb"><li class="breadcrumb-item"><a href="/layer/{project.slug}/">{layer_name_esc}</a></li><li class="breadcrumb-item active">{section_title}</li></ol></nav>')}
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
    from services.layer_features import is_feature_enabled_for_layer, require_layer_feature

    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()

    require_layer_feature('waitlists', project)
    if not is_feature_enabled_for_layer('layers', project):
        from flask import abort
        abort(404)

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
    <div class="gh-page container mt-4">
        {gh_page_header(f'About {html_mod.escape(project.name or project.slug)}', '', 'fa-info-circle', actions_html=f'<a href="/layer/{project.slug}/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-1"></i>Layer</a>', breadcrumb_html=f'<nav aria-label="breadcrumb" class="gh-detail-breadcrumb"><ol class="breadcrumb"><li class="breadcrumb-item"><a href="/layer/{project.slug}/">{html_mod.escape(project.name or project.slug)}</a></li><li class="breadcrumb-item active">About</li></ol></nav>')}
        <div class="living-module">
            <div class="living-module-body about-content" style="max-width: 720px;">
            {html_content}
            </div>
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
        <p><a href="/">Return to Gov Hub</a></p></body></html>""", 400

    scope_type, scope_id_val, user_id_or_email = decoded
    scope_name = 'this community'
    if scope_type == 'layer':
        project = Layer.query.get(scope_id_val)
        if not project:
            return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Unsubscribe</title></head><body style="font-family:sans-serif;max-width:500px;margin:40px auto;padding:20px;">
        <h2>Layer not found</h2>
        <p><a href="/">Return to Gov Hub</a></p></body></html>""", 404
        scope_name = project.name
        filter_kwargs = {'layer_id': scope_id_val}
    else:
        from models import Guild
        guild = Guild.query.get(scope_id_val)
        if not guild:
            return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Unsubscribe</title></head><body style="font-family:sans-serif;max-width:500px;margin:40px auto;padding:20px;">
        <h2>Guild not found</h2>
        <p><a href="/">Return to Gov Hub</a></p></body></html>""", 404
        scope_name = guild.name
        filter_kwargs = {'guild_id': scope_id_val}

    if user_id_or_email and len(str(user_id_or_email)) == 36 and '-' in str(user_id_or_email):
        uid = str(user_id_or_email)
        existing = EmailUnsubscribe.query.filter_by(**filter_kwargs, user_id=uid).first()
        if not existing:
            db.session.add(EmailUnsubscribe(user_id=uid, email=None, **filter_kwargs))
            db.session.commit()
    elif user_id_or_email and str(user_id_or_email).isdigit():
        try:
            uid = str(user_id_or_email)
            existing = EmailUnsubscribe.query.filter_by(**filter_kwargs, user_id=uid).first()
            if not existing:
                db.session.add(EmailUnsubscribe(user_id=uid, email=None, **filter_kwargs))
                db.session.commit()
        except Exception:
            pass
    else:
        email = user_id_or_email.lower() if user_id_or_email else ''
        existing = EmailUnsubscribe.query.filter_by(**filter_kwargs, email=email).first()
        if not existing:
            db.session.add(EmailUnsubscribe(user_id=None, email=email, **filter_kwargs))
            db.session.commit()

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Unsubscribed</title></head><body style="font-family:sans-serif;max-width:500px;margin:40px auto;padding:20px;">
    <h2 style="color:#00ba7c;">You've been unsubscribed</h2>
    <p>You will no longer receive emails from <strong>{scope_name}</strong> on Gov Hub.</p>
    <p><a href="/">Return to Gov Hub</a></p></body></html>""", 200
