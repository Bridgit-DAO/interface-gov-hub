"""Role page routes: /roles/, /badges/, /roles/<slug>/, /roles/<slug>/claim/, /roles/<slug>/images/."""
import json as _json

from flask import Blueprint, session, redirect, url_for, flash

from models import Layer, Role, RoleImage, RoleImageVote
from services.identity import get_current_user, require_auth
from services.coordination import is_layer_admin
from services.utils import _is_uuid_like
from services.directory_ui import (
    gh_page_open,
    gh_page_close,
    gh_page_header,
    gh_filter_row,
    gh_filter_col,
    gh_directory_grid,
    gh_directory_toolbar,
    gh_breadcrumb,
    gh_living_module,
)

bp = Blueprint('roles_pages', __name__, url_prefix='')


def _get_imports():
    """Late imports from main app to avoid circular imports."""
    from services.rendering import render_page, generate_user_menu
    return render_page, generate_user_menu


# ============================================================================
# Roles Directory
# ============================================================================

@bp.route('/roles/')
def roles_directory():
    """Roles directory page - browse all roles across projects"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    from services.page_heroes import render_page_hero_html

    content = f"""
    {gh_page_open()}
    {render_page_hero_html('roles')}
    {gh_page_header('Roles Directory', 'Browse and claim roles across all layers', 'fa-user-tag')}
    {gh_filter_row(
        gh_filter_col('Layer', '<select id="project-filter" class="form-select" onchange="loadRoles()"><option value="">All Layers</option></select>', 'col-md-3')
        + gh_filter_col('Status', '<select id="status-filter" class="form-select" onchange="loadRoles()"><option value="">All Statuses</option><option value="approved" selected>Active</option><option value="draft">Draft</option><option value="deprecated">Deprecated</option></select>', 'col-md-3')
        + gh_directory_toolbar(search_placeholder='Search roles…', search_col='col-md-4', sort_col='col-md-2')
    )}
    {gh_directory_grid('roles-container')}
    {gh_page_close()}

    <script>
    let allRoles = [];
    let allProjects = [];

    async function loadProjects() {{
        try {{
            const response = await fetch('/api/layers/?approval_status=approved');
            const data = await response.json();
            allProjects = data.layers;

            const select = document.getElementById('project-filter');
            allProjects.forEach(project => {{
                const option = document.createElement('option');
                option.value = project.id;
                option.textContent = project.name;
                select.appendChild(option);
            }});
        }} catch (error) {{
            console.error('Error loading projects:', error);
        }}
    }}

    async function loadRoles() {{
        const projectFilter = document.getElementById('project-filter').value;
        const statusFilter = document.getElementById('status-filter').value;

        try {{
            allRoles = [];

            if (projectFilter) {{
                let url = `/api/layers/${{projectFilter}}/roles/`;
                if (statusFilter) url += `?status=${{statusFilter}}`;

                const response = await fetch(url);
                const data = await response.json();
                allRoles = (response.ok && data.roles) ? data.roles : [];
            }} else {{
                for (const project of allProjects) {{
                    let url = `/api/layers/${{project.id}}/roles/`;
                    if (statusFilter) url += `?status=${{statusFilter}}`;

                    const response = await fetch(url);
                    const data = await response.json();
                    const roles = (response.ok && Array.isArray(data.roles)) ? data.roles : [];
                    allRoles = allRoles.concat(roles.map(r => ({{...r, layer_name: project.name, layer_slug: project.slug}})));
                }}
            }}

            filterRoles();
        }} catch (error) {{
            console.error('Error loading roles:', error);
            document.getElementById('roles-container').innerHTML = GhDirectory.emptyState('Error loading roles', 'danger');
        }}
    }}

    function filterRoles() {{
        const items = GhDirectory.filterAndSort(allRoles, {{
            searchTerm: GhDirectory.getSearchValue('search-input'),
            sort: GhDirectory.getSortValue('sort-filter'),
            searchFields: ['title_guild', 'title_operational', 'description', 'slug', 'layer_name'],
            nameKey: 'title_guild',
            dateKeys: ['updated_at', 'created_at'],
        }});
        displayRoles(items);
    }}

    function displayRoles(roles) {{
        const container = document.getElementById('roles-container');

        if (roles.length === 0) {{
            container.innerHTML = GhDirectory.emptyState('No roles found');
            return;
        }}

        let html = '';
        roles.forEach(role => {{
            const statusBadge = role.status === 'approved'
                ? '<span class="badge bg-success">Approved</span>'
                : role.status === 'draft'
                ? '<span class="badge bg-warning">Draft</span>'
                : '<span class="badge bg-secondary">Deprecated</span>';

            const claimBadge = role.claim_requires_approval
                ? '<span class="badge bg-info"><i class="fas fa-check-circle me-1"></i>Approval Required</span>'
                : '<span class="badge bg-success"><i class="fas fa-bolt me-1"></i>Instant Claim</span>';

            const desc = role.description ? role.description.substring(0, 160) : '';
            html += GhDirectory.tile({{
                href: '/roles/' + role.slug + '/',
                title: role.title_guild,
                description: desc,
                icon: 'fa-user-tag',
                pulse: role.status === 'approved' ? 'Open' : '',
                badgesHtml: statusBadge + claimBadge,
                metaHtml: '<i class="fas fa-layer-group me-1"></i>' + GhDirectory.esc(role.layer_name || 'Unknown Layer'),
                footerHtml: '<i class="fas fa-hand-paper me-1"></i>' + (role.claims_count || 0) + ' claims'
            }});
        }});

        container.innerHTML = html;
    }}

    loadProjects().then(() => {{
        loadRoles();
        GhDirectory.bindControls('search-input', 'sort-filter', filterRoles);
    }});
    </script>
    """

    return render_page("Roles Directory - GovHub", content, theme=current_theme, user_menu=user_menu)


# ============================================================================
# Badges / Role Images Directory
# ============================================================================

@bp.route('/badges/')
@bp.route('/role-images/')
def role_images_directory():
    """Badges directory – design galleries for roles, workgroups, one-time badges"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    from services.nav_pills import get_effective_nav_pill_settings, nav_pills_container_attrs

    badge_nav = get_effective_nav_pill_settings(page='badges')
    nav_pill_attrs = nav_pills_container_attrs(badge_nav, context_id='badges')

    content = f"""
    {gh_page_open()}
    {gh_page_header('Badges', 'Design galleries for roles and workgroups across all layers', 'fa-medal')}
    <div class="gh-detail-layout">
        <div class="gh-detail-main">
            <ul class="nav gh-badge-tabs gh-nav-pills flex-wrap"{nav_pill_attrs} id="badgeTabs">
                <li class="nav-item"><button class="nav-link gh-nav-pill" data-tab="all" data-gh-pill-id="all" data-gh-pill-tip="Browse every badge in the directory." onclick="switchTab('all',this)">All</button></li>
                <li class="nav-item"><button class="nav-link gh-nav-pill" data-tab="upcoming" data-gh-pill-id="upcoming" data-gh-pill-tip="Badges scheduled for an upcoming cycle." onclick="switchTab('upcoming',this)">Upcoming</button></li>
                <li class="nav-item"><button class="nav-link gh-nav-pill active" data-tab="current" data-gh-pill-id="current" data-gh-pill-tip="Badges in the current active cycle." onclick="switchTab('current',this)">Active</button></li>
                <li class="nav-item"><button class="nav-link gh-nav-pill" data-tab="past" data-gh-pill-id="past" data-gh-pill-tip="Badges from completed past cycles." onclick="switchTab('past',this)">Past</button></li>
            </ul>
            {gh_filter_row(
                gh_filter_col('Layer', '<select id="project-filter" class="form-select form-select-sm" onchange="filterAndDisplay()"><option value="">All Layers</option></select>', 'col-md-4')
                + gh_directory_toolbar(search_placeholder='Search badges…', search_col='col-md-5', sort_col='col-md-3')
            )}
            {gh_directory_grid('badges-container')}
        </div>
        <div class="gh-detail-sidebar">
            <div class="living-module">
                <div class="living-module-header">
                    <div class="living-module-icon"><i class="fas fa-bolt"></i></div>
                    <h5 class="living-module-title">Actions</h5>
                </div>
                <div class="living-module-body">
                    <a href="#" class="btn btn-primary w-100 mb-2" data-bs-toggle="modal" data-bs-target="#addDesignModal">
                        <i class="fas fa-plus me-2"></i>Submit Design
                    </a>
                    <a href="/badges/one-time/" class="btn btn-outline-secondary w-100 btn-sm">
                        <i class="fas fa-star me-1"></i>One-Time Badges
                    </a>
                </div>
            </div>
        </div>
    </div>
    {gh_page_close()}

    <div class="modal fade" id="addDesignModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Submit Design</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="addDesignForm">
                        <div class="mb-3">
                            <label class="form-label">Layer</label>
                            <select id="add-image-project" class="form-select" onchange="loadAddImageTargets()">
                                <option value="">Select layer...</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Type</label>
                            <select id="add-image-type" class="form-select" onchange="loadAddImageTargets()">
                                <option value="role">Role</option>
                                <option value="workgroup">Workgroup</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label" id="add-target-label">Role</label>
                            <select id="add-image-role" class="form-select">
                                <option value="">Select...</option>
                            </select>
                        </div>
                        <hr>
                        <div class="mb-3">
                            <label class="form-label">Source</label>
                            <select class="form-select" id="addSourceType" onchange="toggleAddSourceFields()">
                                <option value="upload">Upload File</option>
                                <option value="url">Image URL</option>
                            </select>
                        </div>
                        <div id="addUploadField" class="mb-3">
                            <label class="form-label">File</label>
                            <input type="file" class="form-control" id="addImageFile" accept="image/*" onchange="openRoleImageCrop(this)">
                            <small class="text-muted">Upload any size — we'll let you crop and zoom to fit a 600×600 square. PNG/JPG/GIF/WebP/SVG, up to 5MB.</small>
                        </div>
                        <div id="addUrlField" class="mb-3" style="display:none;">
                            <label class="form-label">Image URL</label>
                            <input type="url" class="form-control" id="addImageUrl" placeholder="https://...">
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="submitAddImage()"><i class="fas fa-upload me-1"></i>Submit</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    let allRoles = [];
    let allProjects = [];
    const BADGE_TAB_KEY = 'badges-tab';
    const VALID_TABS = ['all','upcoming','current','past'];
    let currentTab = (function() {{
        const saved = sessionStorage.getItem(BADGE_TAB_KEY);
        return (saved && VALID_TABS.includes(saved)) ? saved : 'current';
    }})();
    const now = new Date();

    (function initBadgeTabs() {{
        document.querySelectorAll('#badgeTabs .nav-link').forEach(btn => {{
            btn.classList.toggle('active', btn.getAttribute('data-tab') === currentTab);
        }});
    }})();

    function switchTab(tab, btn) {{
        currentTab = tab;
        sessionStorage.setItem(BADGE_TAB_KEY, tab);
        document.querySelectorAll('#badgeTabs .nav-link').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filterAndDisplay();
    }}

    function badgePhase(role) {{
        if (!role.badge_enabled) return 'none';
        const earliest = role.badge_earliest_start ? new Date(role.badge_earliest_start) : null;
        if (earliest && earliest > now) return 'upcoming';
        if (role.image_count > 0) return 'current';
        return 'none';
    }}

    async function loadProjects() {{
        try {{
            const response = await fetch('/api/layers/');
            const data = await response.json();
            allProjects = data.layers;
            const select = document.getElementById('project-filter');
            const addSelect = document.getElementById('add-image-project');
            allProjects.forEach(project => {{
                const opt = document.createElement('option');
                opt.value = project.id; opt.textContent = project.name;
                select.appendChild(opt);
                const addOpt = opt.cloneNode(true);
                addSelect.appendChild(addOpt);
            }});
        }} catch (error) {{ console.error('Error loading projects:', error); }}
    }}

    async function loadAllBadges() {{
        document.getElementById('badges-container').innerHTML = '<div class="col-12 text-center py-5"><div class="spinner-border text-primary" role="status"></div></div>';
        try {{
            let url = '/api/role-images/roles-with-stats/';
            const pf = document.getElementById('project-filter').value;
            if (pf) url += '?layer_id=' + encodeURIComponent(pf);
            const response = await fetch(url);
            const data = await response.json();
            allRoles = data.roles || [];
            filterAndDisplay();
        }} catch (error) {{
            document.getElementById('badges-container').innerHTML = GhDirectory.emptyState('Error loading badges', 'danger');
        }}
    }}

    function filterAndDisplay() {{
        const search = GhDirectory.getSearchValue('search-input');
        const sort = GhDirectory.getSortValue('sort-filter');
        let filtered = GhDirectory.filterAndSort(allRoles, {{
            searchTerm: search,
            sort: sort,
            searchFields: ['title_guild', 'title_operational', 'description', 'layer_name'],
            nameKey: 'title_guild',
            dateKeys: ['badge_earliest_start', 'updated_at', 'created_at'],
        }});
        filtered = filtered.filter(role => {{
            const phase = badgePhase(role);
            return currentTab === 'all' || phase === currentTab;
        }});
        displayBadges(filtered);
    }}

    function displayBadges(roles) {{
        const container = document.getElementById('badges-container');
        if (roles.length === 0) {{
            container.innerHTML = GhDirectory.emptyState('No badge designs found for this filter.');
            return;
        }}
        let html = '';
        roles.forEach(role => {{
            const projectName = role.layer_name || '';
            const roleSlug = role.role_slug || role.slug || '';
            const designCount = role.image_count || 0;
            const voteCount = role.vote_count || 0;
            const earliest = role.badge_earliest_start;
            const phase = badgePhase(role);

            let phaseBadge = '';
            let phaseInfo = '';
            let pulse = '';
            if (phase === 'upcoming' && earliest) {{
                const diff = Math.ceil((new Date(earliest) - now) / 86400000);
                phaseBadge = '<span class="badge bg-info me-1">Upcoming</span>';
                phaseInfo = 'Opens in ' + diff + ' day' + (diff !== 1 ? 's' : '');
                pulse = 'Soon';
            }} else if (phase === 'current') {{
                phaseBadge = '<span class="badge bg-success me-1">Active</span>';
                pulse = 'Active';
            }}

            html += GhDirectory.tile({{
                href: '/roles/' + roleSlug + '/images/',
                title: role.title_guild,
                description: (role.title_operational ? role.title_operational + '. ' : '') + (role.description || ''),
                icon: 'fa-medal',
                pulse: pulse,
                badgesHtml: phaseBadge,
                metaHtml: '<i class="fas fa-layer-group me-1"></i>' + GhDirectory.esc(projectName),
                footerHtml: (phaseInfo ? phaseInfo + ' · ' : '') + designCount + ' design' + (designCount !== 1 ? 's' : '') + ' · ' + voteCount + ' vote' + (voteCount !== 1 ? 's' : '')
            }});
        }});
        container.innerHTML = html;
    }}

    async function loadAddImageTargets() {{
        const projectId = document.getElementById('add-image-project').value;
        const type = document.getElementById('add-image-type').value;
        const roleSelect = document.getElementById('add-image-role');
        const label = document.getElementById('add-target-label');
        label.textContent = type === 'workgroup' ? 'Workgroup' : 'Role';
        roleSelect.innerHTML = '<option value="">Select...</option>';
        if (!projectId) return;
        try {{
            const url = type === 'workgroup'
                ? '/api/layers/' + projectId + '/workgroups/'
                : '/api/layers/' + projectId + '/roles/';
            const response = await fetch(url);
            const data = await response.json();
            const items = type === 'workgroup' ? (data.workgroups || []) : (data.roles || []);
            items.forEach(item => {{
                const opt = document.createElement('option');
                opt.value = item.slug || item.role_slug || item.id;
                opt.textContent = item.name || item.title_guild;
                roleSelect.appendChild(opt);
            }});
        }} catch (e) {{ console.error('Error loading targets:', e); }}
    }}

    document.getElementById('addDesignModal').addEventListener('show.bs.modal', function() {{
        document.getElementById('addDesignForm').reset();
        toggleAddSourceFields();
    }});

    function toggleAddSourceFields() {{
        const t = document.getElementById('addSourceType').value;
        document.getElementById('addUploadField').style.display = t === 'upload' ? 'block' : 'none';
        document.getElementById('addUrlField').style.display = t === 'url' ? 'block' : 'none';
    }}

    function openRoleImageCrop(input) {{
        const file = input.files && input.files[0];
        if (!file) return;
        if (typeof window.GhImageCrop !== 'object') {{
            await GhDialog.alert({{ title: 'Notice', message: ('Image cropper is still loading. Please try again in a moment.'), variant: 'info' }});
            input.value = '';
            return;
        }}
        window.GhImageCrop.open(file, {{
            outputSize: 600,
            aspectRatio: 1,
            title: 'Crop Role Image',
            onConfirm: function(blob) {{
                const mime = blob.type || 'image/jpeg';
                const ext = (typeof window.GhImageCrop.extensionForMime === 'function')
                    ? window.GhImageCrop.extensionForMime(mime)
                    : (mime.indexOf('png') >= 0 ? 'png' : (mime.indexOf('webp') >= 0 ? 'webp' : 'jpg'));
                const file = new File([blob], 'role-image.' + ext, {{ type: mime }});
                const dt = new DataTransfer();
                dt.items.add(file);
                input.files = dt.files;
                submitAddImage();
            }},
            onCancel: function() {{ input.value = ''; }},
        }});
    }}

    async function submitAddImage() {{
        const slug = document.getElementById('add-image-role').value;
        const type = document.getElementById('add-image-type').value;
        if (!slug) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please select a ' + (type === 'workgroup' ? 'workgroup' : 'role')), variant: 'info' }}); return; }}
        const sourceType = document.getElementById('addSourceType').value;
        const formData = new FormData();
        formData.append('source_type', sourceType);
        if (sourceType === 'upload') {{
            const file = document.getElementById('addImageFile').files[0];
            if (!file) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please select an image file'), variant: 'info' }}); return; }}
            formData.append('file', file);
        }} else {{
            const url = document.getElementById('addImageUrl').value.trim();
            if (!url) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please enter an image URL'), variant: 'info' }}); return; }}
            formData.append('image_url', url);
        }}
        try {{
            const response = await fetch('/api/roles/' + encodeURIComponent(slug) + '/images/', {{
                method: 'POST', credentials: 'include', body: formData
            }});
            const data = await response.json();
            if (response.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('addDesignModal')).hide();
                window.location.href = '/roles/' + slug + '/images/';
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Upload failed'), variant: 'info' }});
            }}
        }} catch (e) {{ await GhDialog.alert({{ title: 'Notice', message: ('Upload failed'), variant: 'info' }}); }}
    }}

    document.getElementById('project-filter').addEventListener('change', loadAllBadges);
    loadProjects().then(() => {{
        loadAllBadges();
        GhDirectory.bindControls('search-input', 'sort-filter', filterAndDisplay);
    }});
    </script>
    """

    return render_page("Badges - GovHub", content, theme=current_theme, user_menu=user_menu)


# ============================================================================
# One-Time Badges
# ============================================================================

@bp.route('/badges/one-time/')
@require_auth
def one_time_badges_page():
    """One-time badge management page"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    content = f"""
    {gh_page_open()}
    {gh_page_header('One-Time Badges', 'Badges for specific tasks or milestones, awarded once.', 'fa-star')}
    <div class="gh-detail-layout">
        <div class="gh-detail-main">
            {gh_filter_row(
                gh_filter_col('Layer', '<select id="otb-project-filter" class="form-select form-select-sm" onchange="loadOTBs()"><option value="">All Layers</option></select>', 'col-md-6')
                + gh_filter_col('Status', '<select id="otb-status-filter" class="form-select form-select-sm" onchange="loadOTBs()"><option value="">All Statuses</option><option value="draft">Draft</option><option value="upcoming">Upcoming</option><option value="submission">Submission open</option><option value="delay">Delay</option><option value="voting">Voting</option><option value="completed">Completed</option></select>', 'col-md-6')
            )}
            <div class="living-module">
                <div class="living-module-header">
                    <div class="living-module-icon"><i class="fas fa-list"></i></div>
                    <h5 class="living-module-title">Badge campaigns</h5>
                </div>
                <div class="living-module-body" id="otb-list"></div>
            </div>
        </div>
        <div class="gh-detail-sidebar">
            <div class="living-module">
                <div class="living-module-header">
                    <div class="living-module-icon"><i class="fas fa-bolt"></i></div>
                    <h5 class="living-module-title">Actions</h5>
                </div>
                <div class="living-module-body">
                    <button class="btn btn-primary w-100 mb-2" data-bs-toggle="modal" data-bs-target="#createOTBModal">
                        <i class="fas fa-plus me-2"></i>Create One-Time Badge
                    </button>
                    <a href="/badges/" class="btn btn-outline-secondary w-100 btn-sm">
                        <i class="fas fa-arrow-left me-1"></i>Back to Badges
                    </a>
                </div>
            </div>
        </div>
    </div>
    {gh_page_close()}

    <div class="modal fade" id="createOTBModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Create One-Time Badge</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="otb-create-alert"></div>
                    <form id="createOTBForm">
                        <div class="row g-2 mb-2">
                            <div class="col-md-6">
                                <label class="form-label">Layer *</label>
                                <select id="otb-project" class="form-select"></select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label">Title *</label>
                                <input type="text" class="form-control" id="otb-title" placeholder="e.g. Launch Day Contributor">
                            </div>
                        </div>
                        <div class="mb-2">
                            <label class="form-label">Description</label>
                            <textarea class="form-control" id="otb-description" rows="2"></textarea>
                        </div>
                        <div class="row g-2 mb-2">
                            <div class="col-md-4">
                                <label class="form-label">Earliest start *</label>
                                <input type="date" class="form-control" id="otb-earliest-start">
                            </div>
                            <div class="col-md-4">
                                <label class="form-label"># of badges</label>
                                <input type="number" class="form-control" id="otb-quantity" value="1" min="1">
                            </div>
                        </div>
                        <div class="row g-2 mb-2">
                            <div class="col-4">
                                <label class="form-label small">Submission days</label>
                                <input type="number" class="form-control form-control-sm" id="otb-submission-days" value="14" min="1">
                            </div>
                            <div class="col-4">
                                <label class="form-label small">Delay days</label>
                                <input type="number" class="form-control form-control-sm" id="otb-delay-days" value="2" min="0">
                            </div>
                            <div class="col-4">
                                <label class="form-label small">Voting days</label>
                                <input type="number" class="form-control form-control-sm" id="otb-voting-days" value="7" min="1">
                            </div>
                        </div>
                        <label class="form-label small mb-1">Voting types</label>
                        <div class="d-flex gap-3 mb-2">
                            <div class="form-check"><input class="form-check-input" type="checkbox" id="otb-vote-regular" checked disabled><label class="form-check-label small">Regular</label></div>
                            <div class="form-check"><input class="form-check-input" type="checkbox" id="otb-vote-tw"><label class="form-check-label small">Time-weighted</label></div>
                            <div class="form-check"><input class="form-check-input" type="checkbox" id="otb-vote-quad"><label class="form-check-label small">Quadratic</label></div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="submitCreateOTB()">
                        <i class="fas fa-save me-1"></i>Create
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
    let allProjects = [];
    const STATUS_COLORS = {{ draft: 'secondary', upcoming: 'info', submission: 'primary', delay: 'warning', voting: 'success', completed: 'dark' }};
    async function loadProjects() {{ const r = await fetch('/api/layers/'); const d = await r.json(); allProjects = d.layers || [];
        const pf = document.getElementById('otb-project-filter'); const ps = document.getElementById('otb-project');
        allProjects.forEach(p => {{ const o1 = new Option(p.name, p.id); const o2 = new Option(p.name, p.id); pf.appendChild(o1); ps.appendChild(o2); }});
    }}
    async function loadOTBs() {{ const projectId = document.getElementById('otb-project-filter').value; const status = document.getElementById('otb-status-filter').value;
        let url = '/api/one-time-badges/'; if (projectId) url += '?layer_id=' + encodeURIComponent(projectId);
        const r = await fetch(url); const d = await r.json(); let badges = d.badges || []; if (status) badges = badges.filter(b => b.status === status); renderOTBs(badges);
    }}
    function renderOTBs(badges) {{ const el = document.getElementById('otb-list');
        if (!badges.length) {{ el.innerHTML = '<div class="alert alert-info">No one-time badges found.</div>'; return; }}
        const now = new Date();
        el.innerHTML = badges.map(b => {{ const earliest = b.earliest_start ? new Date(b.earliest_start) : null; const color = STATUS_COLORS[b.status] || 'secondary';
            let timeInfo = ''; if (b.status === 'upcoming' && earliest) {{ const days = Math.ceil((earliest - now) / 86400000); timeInfo = `<small class="text-muted">Opens in ${{days}} day${{days !== 1 ? 's' : ''}} &middot; </small>`; }} else if (b.submission_ends_at) {{ timeInfo = `<small class="text-muted">Submissions close ${{new Date(b.submission_ends_at).toLocaleDateString()}} &middot; </small>`; }};
            const proj = allProjects.find(p => p.id === b.layer_id);
            return `<div class="card mb-2"><div class="card-body py-2"><div class="d-flex justify-content-between align-items-start"><div><h6 class="mb-0">${{b.title}}</h6><small class="text-muted">${{proj ? proj.name : b.layer_id}}</small></div><span class="badge bg-${{color}}">${{b.status}}</span></div>${{b.description ? `<p class="small mt-1 mb-1">${{b.description}}</p>` : ''}}<div class="mt-1">${{timeInfo}}<small class="text-muted">${{b.quantity}} badge${{b.quantity !== 1 ? 's' : ''}} &middot; ${{b.submission_days}}d sub / ${{b.delay_days}}d delay / ${{b.voting_days}}d vote</small></div><div class="mt-2 d-flex gap-2"><button class="btn btn-outline-primary btn-sm" onclick="openEditOTB('${{b.id}}')"><i class="fas fa-edit me-1"></i>Edit</button><button class="btn btn-outline-danger btn-sm" onclick="deleteOTB('${{b.id}}', '${{b.title}}')"><i class="fas fa-trash me-1"></i>Delete</button></div></div></div>`;
        }}).join('');
    }}
    async function submitCreateOTB() {{ const projectId = document.getElementById('otb-project').value; const title = document.getElementById('otb-title').value.trim(); const earliest = document.getElementById('otb-earliest-start').value;
        if (!projectId || !title || !earliest) {{ document.getElementById('otb-create-alert').innerHTML = '<div class="alert alert-danger py-1">Layer, title, and earliest start are required.</div>'; return; }}
        const payload = {{ layer_id: projectId, title, description: document.getElementById('otb-description').value.trim(), earliest_start: earliest, quantity: parseInt(document.getElementById('otb-quantity').value) || 1, submission_days: parseInt(document.getElementById('otb-submission-days').value) || 14, delay_days: parseInt(document.getElementById('otb-delay-days').value) || 2, voting_days: parseInt(document.getElementById('otb-voting-days').value) || 7, voting_time_weighted: document.getElementById('otb-vote-tw').checked, voting_quadratic: document.getElementById('otb-vote-quad').checked }};
        const r = await fetch('/api/one-time-badges/', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, credentials: 'include', body: JSON.stringify(payload) }});
        const d = await r.json(); if (r.ok) {{ bootstrap.Modal.getInstance(document.getElementById('createOTBModal')).hide(); document.getElementById('createOTBForm').reset(); document.getElementById('otb-create-alert').innerHTML = ''; loadOTBs(); }} else {{ document.getElementById('otb-create-alert').innerHTML = `<div class="alert alert-danger py-1">${{d.error || 'Failed'}}</div>`; }}
    }}
    async function openEditOTB(badgeId) {{ const r = await fetch('/api/one-time-badges/' + badgeId + '/'); const d = await r.json(); const b = d.badge;
        const html = `<div class="modal fade" id="editOTBModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Edit One-Time Badge</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div id="otb-edit-alert"></div><div class="mb-2"><label class="form-label small">Title</label><input class="form-control" id="otb-edit-title" value="${{b.title}}"></div><div class="mb-2"><label class="form-label small">Description</label><textarea class="form-control" id="otb-edit-desc" rows="2">${{b.description || ''}}</textarea></div><div class="row g-2 mb-2"><div class="col-6"><label class="form-label small">Earliest start</label><input type="date" class="form-control" id="otb-edit-earliest" value="${{b.earliest_start || ''}}"></div><div class="col-6"><label class="form-label small">Quantity</label><input type="number" class="form-control" id="otb-edit-qty" value="${{b.quantity}}" min="1"></div></div><div class="row g-2 mb-2"><div class="col-4"><label class="form-label small">Sub days</label><input type="number" class="form-control form-control-sm" id="otb-edit-sub" value="${{b.submission_days}}" min="1"></div><div class="col-4"><label class="form-label small">Delay days</label><input type="number" class="form-control form-control-sm" id="otb-edit-delay" value="${{b.delay_days}}" min="0"></div><div class="col-4"><label class="form-label small">Vote days</label><input type="number" class="form-control form-control-sm" id="otb-edit-vote" value="${{b.voting_days}}" min="1"></div></div><div class="mb-2"><label class="form-label small">Status</label><select class="form-select form-select-sm" id="otb-edit-status">${{['draft','upcoming','submission','delay','voting','completed'].map(s => `<option value="${{s}}"${{b.status===s?' selected':''}}>${{s}}</option>`).join('')}}</select></div></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button type="button" class="btn btn-primary" onclick="saveEditOTB('${{b.id}}')">Save</button></div></div></div></div>`;
        document.getElementById('editOTBModal')?.remove(); document.body.insertAdjacentHTML('beforeend', html); new bootstrap.Modal(document.getElementById('editOTBModal')).show();
    }}
    async function saveEditOTB(badgeId) {{ const payload = {{ title: document.getElementById('otb-edit-title').value.trim(), description: document.getElementById('otb-edit-desc').value.trim(), earliest_start: document.getElementById('otb-edit-earliest').value || null, quantity: parseInt(document.getElementById('otb-edit-qty').value) || 1, submission_days: parseInt(document.getElementById('otb-edit-sub').value) || 14, delay_days: parseInt(document.getElementById('otb-edit-delay').value) || 2, voting_days: parseInt(document.getElementById('otb-edit-vote').value) || 7, status: document.getElementById('otb-edit-status').value }};
        const r = await fetch('/api/one-time-badges/' + badgeId + '/', {{ method: 'PATCH', headers: {{'Content-Type': 'application/json'}}, credentials: 'include', body: JSON.stringify(payload) }}); const d = await r.json();
        if (r.ok) {{ bootstrap.Modal.getInstance(document.getElementById('editOTBModal')).hide(); loadOTBs(); }} else {{ document.getElementById('otb-edit-alert').innerHTML = `<div class="alert alert-danger py-1">${{d.error || 'Failed'}}</div>`; }}
    }}
    async function deleteOTB(badgeId, title) {{ if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Delete "' + title + '"? This cannot be undone.'), variant: 'warning', confirmLabel: 'Confirm' }})) return; const r = await fetch('/api/one-time-badges/' + badgeId + '/', {{ method: 'DELETE', credentials: 'include' }}); if (r.ok) loadOTBs(); else await GhDialog.alert({{ title: 'Notice', message: ('Delete failed'), variant: 'info' }}); }}
    loadProjects().then(() => loadOTBs());
    </script>
    """
    return render_page("One-Time Badges - GovHub", content, theme=current_theme, user_menu=user_menu)


# ============================================================================
# Role Detail & Claim
# ============================================================================

@bp.route('/layer/<layer_ref>/roles/<role_slug>/')
def layer_role_detail(layer_ref, role_slug):
    """Layer-scoped role detail - preserves layer context in URL and breadcrumbs."""
    if _is_uuid_like(layer_ref):
        project = Layer.query.filter_by(public_id=layer_ref).first_or_404()
    else:
        project = Layer.query.filter_by(slug=layer_ref).first_or_404()
    Role.query.filter_by(layer_id=project.id, role_slug=role_slug).first_or_404()
    return _render_role_detail(
        role_slug,
        layer_slug=project.slug,
        layer_id=project.id,
        use_layer_standalone=True,
        layer_name=project.name or project.slug,
        layer_image_url=project.image_url,
    )


@bp.route('/roles/<role_slug>/')
def role_detail(role_slug):
    """Role detail page (flat URL - for direct links, global directory)."""
    return _render_role_detail(role_slug)


def _render_role_detail(role_slug, layer_slug=None, layer_id=None, use_layer_standalone=False, layer_name=None, layer_image_url=None):
    """Build role detail content. When layer_slug/layer_id set, use layer-centric breadcrumbs and optimized load."""
    render_page, generate_user_menu = _get_imports()
    from services.rendering import render_layer_standalone_page
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    layer_js = f"const layerSlug = {_json.dumps(layer_slug)}; const layerId = {_json.dumps(layer_id)};" if layer_slug and layer_id else "const layerSlug = null; const layerId = null;"

    content = f"""
    <div class="gh-page container mt-4">
        <div id="role-header" class="gh-detail-hero mb-0">
            <div class="d-flex justify-content-center py-4"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>
        </div>
        <div class="gh-detail-layout mt-4">
            <div class="gh-detail-main">
                <div class="living-module">
                    <div class="living-module-header"><div class="living-module-icon"><i class="fas fa-align-left"></i></div><h5 class="living-module-title">Description</h5></div>
                    <div class="living-module-body" id="role-description"><div class="spinner-border spinner-border-sm text-primary"></div></div>
                </div>
                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-hand-paper"></i></div>
                        <h5 class="living-module-title">Active claims</h5>
                        <span id="role-claim-btn-placeholder" class="ms-auto"></span>
                    </div>
                    <div class="living-module-body" id="role-claims"><div class="spinner-border spinner-border-sm text-primary"></div></div>
                </div>
            </div>
            <div class="gh-detail-sidebar">
                <div class="living-module">
                    <div class="living-module-header"><div class="living-module-icon"><i class="fas fa-info-circle"></i></div><h5 class="living-module-title">Role details</h5></div>
                    <div class="living-module-body" id="role-details"><div class="spinner-border spinner-border-sm text-primary"></div></div>
                </div>
                <div class="living-module">
                    <div class="living-module-header"><div class="living-module-icon"><i class="fas fa-cog"></i></div><h5 class="living-module-title">Configuration</h5></div>
                    <div class="living-module-body" id="role-config"><div class="spinner-border spinner-border-sm text-primary"></div></div>
                </div>
            </div>
        </div>
    </div>
    <script>
    let role = null; let project = null; const roleSlug = {_json.dumps(role_slug)}; {layer_js} const isAuthenticated = {'true' if current_user else 'false'}; const currentUserId = {_json.dumps(current_user['id'] if current_user else None)};
    async function loadRole() {{ try {{
        {"if (layerId) { const rolesResp = await fetch(`/api/layers/${layerId}/roles/`); const rolesData = await rolesResp.json(); const found = (rolesData.roles || []).find(r => r.slug === roleSlug); if (found) { role = found; const layerResp = await fetch('/api/layers/by-slug/' + layerSlug + '/'); const layerData = await layerResp.json(); project = { id: layerId, slug: layerSlug, name: layerData.name || layerSlug }; } } " if layer_slug and layer_id else ""}
        {"if (!role) { " if layer_slug and layer_id else ""}const projectsResp = await fetch('/api/layers/'); const projectsData = await projectsResp.json();
        for (const proj of projectsData.layers) {{ const rolesResp = await fetch(`/api/layers/${{proj.id}}/roles/`); const rolesData = await rolesResp.json(); const found = rolesData.roles.find(r => r.slug === roleSlug);
            if (found) {{ role = found; project = proj; break; }} }}
        {"} " if layer_slug and layer_id else ""}if (!role) {{ document.getElementById('role-header').innerHTML = '<div class="alert alert-danger">Role not found</div>'; return; }}
        const detailResp = await fetch(`/api/roles/${{role.id}}/`);
        if (!detailResp.ok) {{ document.getElementById('role-header').innerHTML = '<div class="alert alert-danger">Role not found</div>'; return; }}
        role = await detailResp.json();
        displayRoleHeader(); displayRoleDescription(); displayRoleDetails(); displayRoleConfig(); loadClaims();
    }} catch (error) {{ console.error('Error loading role:', error); document.getElementById('role-header').innerHTML = '<div class="alert alert-danger">Error loading role</div>'; }} }}
    function displayRoleHeader() {{ const statusBadge = getStatusBadge(role.status); const editBtn = (role.can_edit) ? '<button type="button" class="btn btn-secondary btn-sm" onclick="editRole()"><i class="fas fa-edit me-2"></i>Edit</button>' : '';
        const bc = layerSlug ? '<nav aria-label="breadcrumb" class="gh-detail-breadcrumb"><ol class="breadcrumb"><li class="breadcrumb-item"><a href="/layer/' + layerSlug + '/">Layer</a></li><li class="breadcrumb-item"><a href="/layer/' + layerSlug + '/roles/">Roles</a></li><li class="breadcrumb-item active">' + role.title_guild + '</li></ol></nav>' : '<nav aria-label="breadcrumb" class="gh-detail-breadcrumb"><ol class="breadcrumb"><li class="breadcrumb-item"><a href="/layers/">Layers</a></li><li class="breadcrumb-item"><a href="/layers/' + project.slug + '/">' + project.name + '</a></li><li class="breadcrumb-item active">' + role.title_guild + '</li></ol></nav>';
        const mediaHtml = role.image_url ? '<div class="gh-detail-hero-media"><img src="' + role.image_url + '" alt=""></div>' : '<div class="gh-detail-hero-media"><i class="fas fa-user-tag fa-2x text-muted opacity-50"></i></div>';
        document.getElementById('role-header').innerHTML = '<div class="gh-detail-hero-inner">' + mediaHtml + '<div class="gh-detail-hero-body flex-grow-1">' + bc + '<h1>' + role.title_guild + '</h1>' + (role.title_operational ? '<p class="text-muted mb-2">' + role.title_operational + '</p>' : '') + '<div class="mb-0">' + statusBadge + (role.public_visible ? '<span class="badge bg-info ms-2">Public</span>' : '') + '</div></div><div class="gh-detail-hero-actions">' + editBtn + '<a href="/roles/' + roleSlug + '/images/" class="btn btn-outline-primary btn-sm"><i class="fas fa-images me-2"></i>Images</a></div></div>'; }}
    function displayRoleDescription() {{ document.getElementById('role-description').innerHTML = `<p>${{role.description}}</p>`; }}
    function displayRoleDetails() {{ const layerHref = layerSlug ? '/layer/' + layerSlug + '/' : '/layers/' + project.slug + '/'; const clusterLine = role.cluster_name ? `<p><strong>Cluster:</strong> <a href="${{layerHref}}#clusters">${{role.cluster_name}}</a></p>` : (role.cluster_id ? '<p><strong>Cluster:</strong> <span class="text-muted">—</span></p>' : ''); const imageHtml = role.image_url ? `<div class="mb-3 text-center"><img src="${{role.image_url}}" alt="${{role.title_guild}}" class="img-fluid gh-entity-thumb" style="max-height: 200px;"></div>` : ''; document.getElementById('role-details').innerHTML = `${{imageHtml}}<p><strong>Layer:</strong> <a href="${{layerHref}}">${{project.name}}</a></p>${{clusterLine}}<p><strong>Status:</strong> ${{role.status}}</p><p><strong>Visibility:</strong> ${{role.public_visible ? 'Public' : 'Private'}}</p><p><strong>Active Claims:</strong> ${{role.active_claims_count || 0}}</p><p><strong>Created:</strong> ${{new Date(role.created_at).toLocaleDateString()}}</p>`; }}
    function displayRoleConfig() {{ document.getElementById('role-config').innerHTML = `<p><strong>Claim Approval:</strong> ${{role.claim_requires_approval ? 'Required' : 'Not Required'}}</p><p><strong>Badges:</strong> ${{role.badge_enabled ? 'Enabled' : 'Disabled'}}</p>${{role.badge_enabled ? `<p><strong>Badge Approval:</strong> ${{role.badge_requires_approval ? 'Required' : 'Not Required'}}</p>` : ''}}`; }}
    function getClaimPopoverContent(claim) {{ const intent = claim.intent ? '<p class="mb-2"><strong>Intent:</strong><br><span style="white-space: pre-wrap; word-wrap: break-word;">' + (claim.intent || '').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</span></p>' : ''; const links = (claim.evidence_links || []).filter(u => u && u.trim()); const evidenceHtml = links.length ? links.map(u => '<a href="' + u + '" target="_blank" rel="noopener">' + u + '</a>').join('<br>') : '<span class="text-muted">No evidence yet</span>'; const termStr = claim.term_duration_days ? (claim.term_duration_days + ' days' + (claim.term_end ? ', until ' + new Date(claim.term_end).toLocaleDateString() : '')) : 'Indefinite'; return '<div class="text-start" style="min-width: 280px; max-width: 480px; white-space: normal; word-wrap: break-word;">' + intent + '<p class="mb-2"><strong>Supporting work:</strong><br>' + evidenceHtml + '</p>' + '<p class="mb-2"><strong>Term:</strong> ' + termStr + '</p>' + '<p class="mb-0 small text-muted">Claimed: ' + new Date(claim.created_at).toLocaleDateString() + '</p></div>'; }}
    async function loadClaims() {{ const container = document.getElementById('role-claims'); const btnPlaceholder = document.getElementById('role-claim-btn-placeholder');
        if (!role.public_visible) {{ if (btnPlaceholder) btnPlaceholder.innerHTML = ''; container.innerHTML = '<p class="text-muted">Claims are only visible for public roles.</p>'; return; }}
        try {{ const response = await fetch(`/api/roles/${{role.id}}/claims/`); const data = await response.json(); const claimsData = data.claims || []; const activeClaims = claimsData.filter(c => c.status === 'active' || c.status === 'pending_approval'); const hasClaimed = isAuthenticated && claimsData.some(c => Number(c.claimant_id) === Number(currentUserId));
            if (btnPlaceholder) {{ if (role.requires_election) {{ if (hasClaimed) {{ btnPlaceholder.innerHTML = ''; }} else if (role.active_election && isAuthenticated) {{ btnPlaceholder.innerHTML = '<a href="/votes/' + role.active_election.public_id + '/" class="btn btn-sm btn-primary"><i class="fas fa-user-plus me-2"></i>Run for this Role</a>'; }} else if (role.active_election && !isAuthenticated) {{ btnPlaceholder.innerHTML = '<a href="/login/" class="btn btn-sm btn-primary">Login to Run</a>'; }} else {{ btnPlaceholder.innerHTML = '<span class="text-muted small">This role is filled by election. No election is currently open.</span>'; }} }} else if (hasClaimed) {{ btnPlaceholder.innerHTML = ''; }} else if (isAuthenticated) {{ btnPlaceholder.innerHTML = '<button class="btn btn-sm btn-primary" onclick="claimRole()"><i class="fas fa-hand-paper me-2"></i>Claim This Role</button>'; }} else {{ btnPlaceholder.innerHTML = '<a href="/login/" class="btn btn-sm btn-primary">Login to Claim</a>'; }} }}
            if (activeClaims.length === 0) {{ container.innerHTML = '<p class="text-muted">No active claims yet</p>'; return; }}
            const claimsDataDisplay = activeClaims; let html = '<div class="list-group">'; claimsDataDisplay.forEach((claim, idx) => {{ const claimantName = claim.claimant_name || ('User #' + claim.claimant_id); const claimantUsername = claim.claimant_username || ''; const profileLink = claimantUsername ? '/profile/' + claimantUsername + '/' : '#'; const nameDisplay = profileLink !== '#' ? '<a href="' + profileLink + '" class="text-decoration-none">' + claimantName + '</a>' : claimantName; html += `<div class="list-group-item claim-list-item" data-claim-index="${{idx}}"><div class="d-flex justify-content-between align-items-center"><h6 class="mb-0">${{nameDisplay}}</h6><span class="badge bg-success">Active</span></div><small class="text-muted">Claimed: ${{new Date(claim.created_at).toLocaleDateString()}}</small></div>`; }}); html += '</div>'; container.innerHTML = html; container.querySelectorAll('.claim-list-item').forEach(el => {{ const idx = parseInt(el.getAttribute('data-claim-index'), 10); const claim = claimsDataDisplay[idx]; new bootstrap.Popover(el, {{ content: getClaimPopoverContent(claim), html: true, trigger: 'hover focus', placement: 'auto', container: 'body' }}); }});
        }} catch (error) {{ console.error('Error loading claims:', error); container.innerHTML = '<div class="alert alert-danger">Error loading claims</div>'; }} }}
    function getStatusBadge(status) {{ const badges = {{ 'draft': '<span class="badge bg-secondary">Draft</span>', 'approved': '<span class="badge bg-success">Approved</span>', 'deprecated': '<span class="badge bg-warning">Deprecated</span>', 'archived': '<span class="badge bg-dark">Archived</span>' }}; return badges[status] || ''; }}
    function claimRole() {{ if (role.status !== 'approved') {{ await GhDialog.alert({{ title: 'Notice', message: ('This role must be approved before it can be claimed'), variant: 'info' }}); return; }} window.location.href = `/roles/${{roleSlug}}/claim/`; }}
    function editRole() {{ const modalHtml = `<div class="modal fade" id="editRoleModal" tabindex="-1"><div class="modal-dialog modal-lg"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Edit Role</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div id="edit-role-alert-container"></div><form id="editRoleForm"><div class="mb-3"><label for="edit-role-title-guild" class="form-label">Guild Title *</label><input type="text" class="form-control" id="edit-role-title-guild" required></div><div class="mb-3"><label for="edit-role-title-operational" class="form-label">Operational Title</label><input type="text" class="form-control" id="edit-role-title-operational"></div><div class="mb-3"><label for="edit-role-description" class="form-label">About / Description *</label><textarea class="form-control" id="edit-role-description" rows="5" required></textarea></div><div class="mb-3"><label for="edit-role-cluster" class="form-label">Cluster</label><select class="form-select" id="edit-role-cluster"><option value="">No cluster</option></select></div><hr><h6 class="mb-3"><i class="fas fa-medal me-2"></i>Badge Settings</h6><div class="row g-2 mb-2"><div class="col-6"><div class="form-check"><input class="form-check-input" type="checkbox" id="edit-role-badge-enabled"><label class="form-check-label" for="edit-role-badge-enabled">Badge enabled</label></div></div><div class="col-6"><div class="form-check"><input class="form-check-input" type="checkbox" id="edit-role-badge-approval"><label class="form-check-label" for="edit-role-badge-approval">Require approval</label></div></div></div><div id="role-badge-fields" class="border rounded p-2 bg-light bg-opacity-10"><div class="row g-2 mb-2"><div class="col-4"><label class="form-label small mb-0">Submission days</label><input type="number" class="form-control form-control-sm" id="edit-role-badge-submission-days" min="1"></div><div class="col-4"><label class="form-label small mb-0">Delay days</label><input type="number" class="form-control form-control-sm" id="edit-role-badge-delay-days" min="0"></div><div class="col-4"><label class="form-label small mb-0">Voting days</label><input type="number" class="form-control form-control-sm" id="edit-role-badge-voting-days" min="1"></div></div><div class="row g-2 mb-2"><div class="col-6"><label class="form-label small mb-0">Earliest start date</label><input type="date" class="form-control form-control-sm" id="edit-role-badge-earliest-start"></div><div class="col-6"><label class="form-label small mb-0">Min. days between cycles</label><input type="number" class="form-control form-control-sm" id="edit-role-badge-cycle-spacing" min="1"></div></div><div class="row g-2 mb-2"><div class="col-6"><label class="form-label small mb-0">End date (optional)</label><input type="date" class="form-control form-control-sm" id="edit-role-badge-end-date"></div><div class="col-6 d-flex align-items-end"><div class="form-check"><input class="form-check-input" type="checkbox" id="edit-role-badge-end-next"><label class="form-check-label small" for="edit-role-badge-end-next">End at next closing</label></div></div></div><label class="form-label small mb-1">Voting types</label><div class="d-flex gap-3 flex-wrap"><div class="form-check"><input class="form-check-input" type="checkbox" id="edit-role-vote-regular" checked disabled><label class="form-check-label small" for="edit-role-vote-regular">Regular</label></div><div class="form-check"><input class="form-check-input" type="checkbox" id="edit-role-vote-tw"><label class="form-check-label small" for="edit-role-vote-tw">Time-weighted</label></div><div class="form-check"><input class="form-check-input" type="checkbox" id="edit-role-vote-quad"><label class="form-check-label small" for="edit-role-vote-quad">Quadratic</label></div></div></div></form></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button type="button" class="btn btn-primary" id="editRoleSubmitBtn"><i class="fas fa-save me-2"></i>Save Changes</button></div></div></div></div>`;
        if (!document.getElementById('editRoleModal')) {{ document.body.insertAdjacentHTML('beforeend', modalHtml); }}
        document.getElementById('edit-role-title-guild').value = role.title_guild || ''; document.getElementById('edit-role-title-operational').value = role.title_operational || ''; document.getElementById('edit-role-description').value = role.description || ''; document.getElementById('edit-role-alert-container').innerHTML = '';
        document.getElementById('edit-role-badge-enabled').checked = !!role.badge_enabled; document.getElementById('edit-role-badge-approval').checked = !!role.badge_requires_approval; document.getElementById('edit-role-badge-submission-days').value = role.badge_submission_days ?? 14; document.getElementById('edit-role-badge-delay-days').value = role.badge_delay_days ?? 2; document.getElementById('edit-role-badge-voting-days').value = role.badge_voting_days ?? 7; document.getElementById('edit-role-badge-earliest-start').value = role.badge_earliest_start || ''; document.getElementById('edit-role-badge-cycle-spacing').value = role.badge_cycle_spacing_days ?? 365; document.getElementById('edit-role-badge-end-date').value = role.badge_end_date || ''; document.getElementById('edit-role-badge-end-next').checked = !!role.badge_end_at_next_closing; document.getElementById('edit-role-vote-tw').checked = !!role.badge_voting_time_weighted; document.getElementById('edit-role-vote-quad').checked = !!role.badge_voting_quadratic;
        const clusterSelect = document.getElementById('edit-role-cluster'); clusterSelect.innerHTML = '<option value="">No cluster</option>'; fetch(`/api/layers/${{project.id}}/clusters/`).then(r => r.json()).then(d => {{ (d.clusters || []).forEach(c => {{ const opt = document.createElement('option'); opt.value = c.id || ''; opt.textContent = (c.name != null && c.name !== '') ? c.name : 'Unnamed'; clusterSelect.appendChild(opt); }}); clusterSelect.value = role.cluster_id || ''; }});
        const modal = new bootstrap.Modal(document.getElementById('editRoleModal')); modal.show();
        document.getElementById('editRoleSubmitBtn').onclick = async () => {{ const titleGuild = document.getElementById('edit-role-title-guild').value.trim(); const titleOperational = document.getElementById('edit-role-title-operational').value.trim(); const description = document.getElementById('edit-role-description').value.trim(); const clusterId = document.getElementById('edit-role-cluster').value || null; if (!titleGuild || !description) {{ document.getElementById('edit-role-alert-container').innerHTML = '<div class="alert alert-danger">Guild title and description are required.</div>'; return; }} const btn = document.getElementById('editRoleSubmitBtn'); btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...'; const badgePayload = {{ badge_enabled: document.getElementById('edit-role-badge-enabled').checked, badge_requires_approval: document.getElementById('edit-role-badge-approval').checked, badge_submission_days: parseInt(document.getElementById('edit-role-badge-submission-days').value) || 14, badge_delay_days: parseInt(document.getElementById('edit-role-badge-delay-days').value) || 2, badge_voting_days: parseInt(document.getElementById('edit-role-badge-voting-days').value) || 7, badge_earliest_start: document.getElementById('edit-role-badge-earliest-start').value || null, badge_cycle_spacing_days: parseInt(document.getElementById('edit-role-badge-cycle-spacing').value) || 365, badge_end_date: document.getElementById('edit-role-badge-end-date').value || null, badge_end_at_next_closing: document.getElementById('edit-role-badge-end-next').checked, badge_voting_regular: true, badge_voting_time_weighted: document.getElementById('edit-role-vote-tw').checked, badge_voting_quadratic: document.getElementById('edit-role-vote-quad').checked }}; try {{ const response = await fetch(`/api/roles/${{role.id}}/`, {{ method: 'PATCH', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ title_guild: titleGuild, title_operational: titleOperational || null, description, cluster_id: clusterId, ...badgePayload }}) }}); if (!response.ok) {{ const data = await response.json(); throw new Error(data.error || 'Failed to update role'); }} role.title_guild = titleGuild; role.title_operational = titleOperational || null; role.description = description; role.cluster_id = clusterId; role.cluster_name = clusterId ? clusterSelect.options[clusterSelect.selectedIndex].text : null; Object.assign(role, badgePayload); modal.hide(); displayRoleHeader(); displayRoleDescription(); displayRoleDetails(); }} catch (err) {{ document.getElementById('edit-role-alert-container').innerHTML = '<div class="alert alert-danger">' + (err.message || 'Failed to update role') + '</div>'; }} btn.disabled = false; btn.innerHTML = '<i class="fas fa-save me-2"></i>Save Changes'; }};
    }}
    loadRole();
    </script>
    """
    title = f"Role: {role_slug} - GovHub"
    if use_layer_standalone and layer_slug:
        return render_layer_standalone_page(
            title, content,
            layer_name=layer_name or layer_slug,
            layer_slug=layer_slug,
            layer_image_url=layer_image_url,
            theme=current_theme,
            user_menu=user_menu,
        )
    return render_page(title, content, theme=current_theme, user_menu=user_menu)


@bp.route('/roles/<role_slug>/claim/')
@require_auth
def claim_role_page(role_slug):
    """Claim role form page"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    content = f"""
    <div class="gh-page container mt-4">
        <div class="gh-detail-layout">
            <div class="gh-detail-main mx-auto" style="max-width: 720px;">
                <div id="role-header" class="gh-detail-hero mb-4">
                    <div class="living-module-body text-center py-4" id="role-info">
                        <div class="spinner-border text-primary"></div>
                    </div>
                </div>
                <div id="alert-container" class="mb-3"></div>
                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-hand-paper"></i></div>
                        <h5 class="living-module-title">Claim this role</h5>
                    </div>
                    <div class="living-module-body">
                        <form id="claimRoleForm" style="display: none;">
                            <div class="mb-3"><label for="intent" class="form-label">Intent Statement</label><textarea class="form-control" id="intent" rows="4" placeholder="Describe your intent in claiming this role and how you plan to contribute..."></textarea><div class="form-text">Optional: Explain your motivation and plans</div></div>
                            <div class="mb-3"><label for="evidence_links" class="form-label">Supporting work</label><textarea class="form-control" id="evidence_links" rows="3" placeholder="https://example.com/my-work&#10;https://github.com/username/project"></textarea><div class="form-text">Optional: Links to relevant work or contributions (one per line)</div></div>
                            <div class="mb-3"><label for="term_duration_months" class="form-label">Term duration (months)</label><select class="form-select" id="term_duration_months"><option value="1">1 month</option><option value="3" selected>3 months</option><option value="6">6 months</option><option value="12">12 months</option></select><div class="form-text">Time limit for this claim</div></div>
                            <div id="approval-notice" class="alert alert-warning" style="display: none;"><i class="fas fa-exclamation-triangle me-2"></i><strong>Note:</strong> This role requires approval. Your claim will be pending until reviewed by a layer admin.</div>
                            <div class="d-flex gap-2"><button type="submit" class="btn btn-primary" id="submitBtn"><i class="fas fa-hand-paper me-2"></i>Submit Claim</button><a href="/roles/{role_slug}/" class="btn btn-secondary">Cancel</a></div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
    let role = null; let project = null; const roleSlug = {_json.dumps(role_slug)};
    async function loadRole() {{ try {{ const projectsResp = await fetch('/api/layers/'); const projectsData = await projectsResp.json(); for (const proj of projectsData.layers) {{ const rolesResp = await fetch(`/api/layers/${{proj.id}}/roles/`); const rolesData = await rolesResp.json(); const found = rolesData.roles.find(r => r.slug === roleSlug); if (found) {{ role = found; project = proj; break; }} }} if (!role) {{ document.getElementById('alert-container').innerHTML = '<div class="alert alert-danger">Role not found</div>'; return; }} const detailResp = await fetch(`/api/roles/${{role.id}}/`); if (!detailResp.ok) {{ document.getElementById('alert-container').innerHTML = '<div class="alert alert-danger">Role not found</div>'; return; }} role = await detailResp.json(); displayRoleInfo(); if (role.claim_requires_approval) {{ document.getElementById('approval-notice').style.display = 'block'; }} document.getElementById('claimRoleForm').style.display = 'block'; }} catch (error) {{ document.getElementById('alert-container').innerHTML = '<div class="alert alert-danger">Error loading role</div>'; }} }}
    function displayRoleInfo() {{ const mediaHtml = role.image_url ? '<div class="gh-detail-hero-media"><img src="' + role.image_url + '" alt=""></div>' : '<div class="gh-detail-hero-media"><i class="fas fa-user-tag fa-2x text-muted opacity-50"></i></div>';
        document.getElementById('role-info').innerHTML = '<div class="gh-detail-hero-inner">' + mediaHtml + '<div class="gh-detail-hero-body flex-grow-1"><h1>' + role.title_guild + '</h1>' + (role.title_operational ? '<p class="text-muted mb-2">' + role.title_operational + '</p>' : '') + '<p class="mb-2">' + role.description + '</p><p class="mb-0 small"><strong>Layer:</strong> <a href="/layers/' + project.slug + '/">' + project.name + '</a></p></div></div>'; }}
    document.getElementById('claimRoleForm').addEventListener('submit', async (e) => {{ e.preventDefault(); const submitBtn = document.getElementById('submitBtn'); submitBtn.disabled = true; submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...'; const evidenceText = document.getElementById('evidence_links').value.trim(); const evidenceLinks = evidenceText ? evidenceText.split('\\n').filter(l => l.trim()) : []; const termEl = document.getElementById('term_duration_months'); const termVal = (termEl && termEl.value !== undefined && termEl.value !== '') ? termEl.value : '3'; const termMonths = parseInt(termVal, 10) || 3; const formData = {{ intent: document.getElementById('intent').value.trim() || null, evidence_links: evidenceLinks, term_duration_months: termMonths }}; try {{ const response = await fetch(`/api/roles/${{role.id}}/claims/`, {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify(formData) }}); const data = await response.json(); if (response.ok) {{ const statusMsg = role.claim_requires_approval ? 'Your claim has been submitted and is pending approval.' : 'Your claim has been submitted successfully!'; document.getElementById('alert-container').innerHTML = `<div class="alert alert-success"><i class="fas fa-check-circle me-2"></i>${{statusMsg}} Redirecting...</div>`; setTimeout(() => {{ window.location.href = `/roles/${{roleSlug}}/`; }}, 2000); }} else {{ throw new Error(data.error || 'Failed to submit claim'); }} }} catch (error) {{ document.getElementById('alert-container').innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>${{error.message}}</div>`; submitBtn.disabled = false; submitBtn.innerHTML = '<i class="fas fa-hand-paper me-2"></i>Submit Claim'; }} }});
    loadRole();
    </script>
    """
    return render_page(f"Claim Role: {role_slug} - GovHub", content, theme=current_theme, user_menu=user_menu)


# ============================================================================
# Role Images Gallery (per-role)
# ============================================================================

@bp.route('/roles/<role_slug>/images/')
def role_images_gallery(role_slug):
    """Gallery of role image proposals with voting"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    is_global_admin = current_user and current_user.get('role') == 'admin'

    # Load role for display name and link back to role
    role = Role.query.filter_by(role_slug=role_slug).first()
    role_title = role.title_guild if role else role_slug

    role_badge_json = 'null'
    role_id_js = 'null'
    is_project_admin_flag = False
    if role:
        role_dict = role.to_dict()
        project = Layer.query.get(role.layer_id)
        is_project_admin_flag = bool(project and current_user and is_layer_admin(project, current_user))
        role_dict['can_manage'] = is_project_admin_flag
        role_badge_json = _json.dumps(role_dict)
        role_id_js = _json.dumps(role.id)

    content = f"""
    {gh_page_open()}
    {gh_page_header(f'Designs: {role_title}', 'Community-submitted badge designs for this role', 'fa-palette', actions_html=f'<a href="/roles/{role_slug}/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-user-tag me-1"></i>Role</a>')}
    <div class="gh-detail-layout">
        <div class="gh-detail-main">
            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                <select id="sort-select" class="form-select form-select-sm w-auto" onchange="loadImages()">
                    <option value="net_score">Net Score</option>
                    <option value="upvotes">Most Upvotes</option>
                    <option value="date">Most Recent</option>
                </select>
                {'<button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#submitImageModal"><i class="fas fa-plus me-1"></i>Submit Design</button>' if current_user else '<a href="/login/" class="btn btn-primary btn-sm"><i class="fas fa-sign-in-alt me-1"></i>Login to Submit</a>'}
            </div>
            <div id="images-container" class="row row-cols-1 row-cols-md-2 g-3">
                <div class="col-12 text-center py-5">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        </div>
        <div class="gh-detail-sidebar">
            <div class="living-module mb-3" id="cycle-card">
                <div class="living-module-header">
                    <div class="living-module-icon"><i class="fas fa-clock"></i></div>
                    <h5 class="living-module-title">Badge cycle</h5>
                </div>
                <div class="living-module-body small" id="cycle-body">
                    <div class="text-muted">Loading…</div>
                </div>
            </div>
            <div class="living-module mb-3">
                <div class="living-module-header">
                    <div class="living-module-icon"><i class="fas fa-palette"></i></div>
                    <h5 class="living-module-title">Badge skin</h5>
                </div>
                <div class="living-module-body py-2">
                    <p class="small text-muted mb-2">Preview designs in each layout skin{'. Admins can select the active skin.' if is_project_admin_flag else '.'}</p>
                    <div id="skin-list" class="d-flex flex-column gap-2">
                        <div class="text-muted small">Loading skins…</div>
                    </div>
                </div>
            </div>
            <a href="/badges/" class="btn btn-outline-secondary btn-sm w-100">
                <i class="fas fa-arrow-left me-1"></i>All Badges
            </a>
        </div>
    </div>
    {gh_page_close()}

    <!-- Submit Image Modal -->
    <div class="modal fade" id="submitImageModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Submit Role Design</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="submitImageForm">
                        <div class="mb-3">
                            <label class="form-label">Source Type</label>
                            <select class="form-select" id="sourceType" onchange="toggleSourceFields()">
                                <option value="upload">Upload Image File</option>
                                <option value="url">Image URL</option>
                                <option value="ordinal">Bitcoin Ordinal</option>
                            </select>
                        </div>

                        <div id="uploadField" class="mb-3">
                            <label for="imageFile" class="form-label">Image File</label>
                            <input type="file" class="form-control" id="imageFile" accept="image/*">
                            <small class="text-muted">Max 600×600 px, 5MB. Formats: PNG, JPG, GIF, WebP, SVG</small>
                        </div>

                        <div id="urlField" class="mb-3" style="display:none;">
                            <label for="imageUrl" class="form-label">Image URL</label>
                            <input type="url" class="form-control" id="imageUrl" placeholder="https://example.com/image.png">
                        </div>

                        <div id="ordinalFields" style="display:none;">
                            <div class="mb-3">
                                <label for="inscriptionId" class="form-label">Inscription ID</label>
                                <input type="text" class="form-control" id="inscriptionId" placeholder="a455e1c4...e9aa72i0">
                            </div>
                            <div class="mb-3">
                                <label for="contentType" class="form-label">Content Type</label>
                                <input type="text" class="form-control" id="contentType" value="image/png">
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" onclick="submitImage()">Submit</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    const roleSlug = {_json.dumps(role_slug)};
    const roleId = {role_id_js};
    const isAdmin = {'true' if is_global_admin else 'false'};
    const roleData = {role_badge_json};
    const canManage = {'true' if is_project_admin_flag else 'false'};
    let allSkins = [];
    let activeSkinId = roleData ? roleData.badge_skin_id : null;
    let previewImageSrc = null;
    let cycleData = null;

    // ── Helpers ──────────────────────────────────────────────────────
    function fmtDate(iso) {{
        if (!iso) return '—';
        return new Date(iso + (iso.includes('T') ? '' : 'T00:00:00')).toLocaleDateString(undefined, {{month:'short',day:'numeric',year:'numeric'}});
    }}
    function daysUntil(iso) {{
        if (!iso) return null;
        const d = new Date(iso + (iso.includes('T') ? '' : 'T00:00:00'));
        return Math.ceil((d - Date.now()) / 86400000);
    }}

    // ── Cycle timeline ───────────────────────────────────────────────
    async function loadCycleCard() {{
        const el = document.getElementById('cycle-body');
        try {{
            const r = await fetch(`/api/roles/${{roleSlug}}/badge-cycle/`);
            cycleData = await r.json();
            renderCycleCard();
        }} catch(e) {{
            el.innerHTML = '<span class="text-danger small">Could not load cycle data.</span>';
        }}
    }}

    function renderCycleCard() {{
        const el = document.getElementById('cycle-body');
        if (!cycleData) {{ el.innerHTML = '<span class="text-muted">No data.</span>'; return; }}
        if (!cycleData.badge_enabled) {{
            el.innerHTML = '<span class="text-muted">Badges not enabled for this role.</span>';
            return;
        }}

        const cycle = cycleData.cycle;
        const up = cycleData.upcoming;
        let html = '';

        if (cycle && cycle.status !== 'completed') {{
            // ── Active cycle ──
            const statusColors = {{ submission: 'success', delay: 'warning', voting: 'primary' }};
            const statusLabels = {{ submission: 'Submission Open', delay: 'Delay Period', voting: 'Voting Open' }};
            const color = statusColors[cycle.status] || 'secondary';
            const label = statusLabels[cycle.status] || cycle.status;
            html += `<div class="mb-2"><span class="badge bg-${{color}}">${{label}}</span></div>`;
            html += renderTimeline([
                {{ label: 'First submission', date: cycle.first_submission_at, active: true }},
                {{ label: 'Submission closes', date: cycle.submission_ends_at, active: cycle.status === 'delay' || cycle.status === 'voting' }},
                {{ label: 'Voting opens', date: cycle.voting_starts_at, active: cycle.status === 'voting' }},
                {{ label: 'Voting closes', date: cycle.voting_ends_at, active: false }},
            ]);
            if (cycle.status === 'submission') {{
                const d = daysUntil(cycle.submission_ends_at);
                if (d !== null) html += `<div class="mt-2 text-muted small">Submission closes in <strong>${{d}}</strong> day${{d===1?'':'s'}}</div>`;
            }} else if (cycle.status === 'voting') {{
                const d = daysUntil(cycle.voting_ends_at);
                if (d !== null) html += `<div class="mt-2 text-muted small">Voting closes in <strong>${{d}}</strong> day${{d===1?'':'s'}}</div>`;
            }}
        }} else if (cycle && cycle.status === 'completed') {{
            // ── Most recent completed cycle ──
            html += `<div class="mb-2"><span class="badge bg-secondary">Last Cycle (Completed)</span></div>`;
            html += renderTimeline([
                {{ label: 'First submission', date: cycle.first_submission_at, active: false }},
                {{ label: 'Submission closed', date: cycle.submission_ends_at, active: false }},
                {{ label: 'Voting opened', date: cycle.voting_starts_at, active: false }},
                {{ label: 'Voting closed', date: cycle.voting_ends_at, active: false }},
            ]);
            html += '<hr class="my-2">';
            // fall through to show upcoming projections below
            if (up) html += renderUpcoming(up);
            if (cycleData.can_manage) {{
                html += `<button class="btn btn-sm btn-outline-success w-100 mt-2" onclick="startCycle()"><i class="fas fa-play me-1"></i>Start New Cycle</button>`;
            }}
        }} else {{
            // ── No cycle yet ──
            if (up) html += renderUpcoming(up);
            if (cycleData.can_manage) {{
                const canStart = !up || !up.days_until_start || up.days_until_start <= 0;
                if (canStart) {{
                    html += `<button class="btn btn-sm btn-success w-100 mt-2" onclick="startCycle()"><i class="fas fa-play me-1"></i>Start Cycle</button>`;
                }} else {{
                    html += `<div class="mt-2 text-muted small">Can start in ${{up.days_until_start}} day${{up.days_until_start===1?'':'s'}}</div>`;
                }}
            }}
        }}

        el.innerHTML = html;
    }}

    function renderTimeline(steps) {{
        const rows = steps.map(s => {{
            const cls = s.active ? 'text-success fw-semibold' : 'text-muted';
            const icon = s.active ? '●' : '○';
            return `<div class="d-flex justify-content-between gap-2 ${{cls}}">
                <span>${{icon}} ${{s.label}}</span><span>${{fmtDate(s.date)}}</span>
            </div>`;
        }});
        return `<div class="d-flex flex-column gap-1" style="font-size:0.78rem">${{rows.join('')}}</div>`;
    }}

    function renderUpcoming(up) {{
        let html = `<div class="small mb-1 text-muted">Projected dates (based on settings):</div>`;
        html += renderTimeline([
            {{ label: 'Earliest open', date: up.badge_earliest_start, active: !up.days_until_start || up.days_until_start <= 0 }},
            {{ label: 'Submission closes', date: up.estimated_submission_end, active: false }},
            {{ label: 'Voting opens', date: up.estimated_voting_start, active: false }},
            {{ label: 'Voting closes', date: up.estimated_voting_end, active: false }},
        ]);
        const vtypes = [];
        if (up.voting_regular !== false) vtypes.push('Regular');
        if (up.voting_time_weighted) vtypes.push('Time-weighted');
        if (up.voting_quadratic) vtypes.push('Quadratic');
        html += `<div class="d-flex justify-content-between mt-1" style="font-size:0.75rem">
            <span class="text-muted">Voting</span><span>${{vtypes.join(', ')}}</span></div>`;
        if (up.days_until_start > 0) {{
            html += `<div class="mt-1 text-info small">Opens in <strong>${{up.days_until_start}}</strong> day${{up.days_until_start===1?'':'s'}}</div>`;
        }}
        if (up.badge_end_date) {{
            html += `<div class="text-warning small mt-1">Ends ${{fmtDate(up.badge_end_date)}}</div>`;
        }}
        return html;
    }}

    async function startCycle() {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Start a new badge cycle now?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;
        try {{
            const r = await fetch(`/api/roles/${{roleSlug}}/badge-cycle/start/`, {{method:'POST'}});
            const d = await r.json();
            if (r.ok) {{
                await loadCycleCard();
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: (d.error || 'Could not start cycle'), variant: 'info' }});
            }}
        }} catch(e) {{ await GhDialog.alert({{ title: 'Notice', message: ('Error starting cycle'), variant: 'info' }}); }}
    }}

    // ── Skin picker ──────────────────────────────────────────────────
    async function loadSkins() {{
        try {{
            const r = await fetch('/api/badge-skins/');
            const d = await r.json();
            allSkins = d.skins || [];
            renderSkinList();
        }} catch(e) {{
            document.getElementById('skin-list').innerHTML = '<small class="text-danger">Could not load skins.</small>';
        }}
    }}

    function renderSkinList() {{
        const el = document.getElementById('skin-list');
        if (!allSkins.length) {{ el.innerHTML = '<small class="text-muted">No skins available.</small>'; return; }}
        el.innerHTML = allSkins.map(s => {{
            const isSelected = activeSkinId && (s.id === activeSkinId || s.slug === activeSkinId);
            const isPreview = previewSkinSlug === s.slug;
            let borderCls = '';
            if (isSelected) borderCls = 'border-success';
            else if (isPreview) borderCls = 'border-primary';
            return `
            <div class="skin-option border rounded p-2 ${{borderCls}} ${{isSelected ? 'bg-success bg-opacity-10' : isPreview ? 'bg-primary bg-opacity-10' : ''}}"
                 style="cursor:pointer" onclick="previewSkin('${{s.slug}}')">
                <div class="d-flex align-items-center gap-2">
                    <div style="width:36px;height:36px;background:#444;border-radius:4px;flex-shrink:0;display:flex;align-items:center;justify-content:center;">
                        ${{s.preview_image_url
                            ? `<img src="${{s.preview_image_url}}" style="width:36px;height:36px;object-fit:cover;border-radius:4px;">`
                            : `<i class="fas fa-layer-group text-muted small"></i>`}}
                    </div>
                    <div class="flex-grow-1 min-width-0">
                        <div class="fw-semibold small d-flex align-items-center gap-1">
                            ${{s.name}}
                            ${{isSelected ? '<span class="badge bg-success" style="font-size:0.6rem">Active</span>' : ''}}
                        </div>
                        <div class="text-muted" style="font-size:0.72rem">${{s.description || ''}}</div>
                    </div>
                    ${{isPreview ? '<i class="fas fa-eye text-primary"></i>' : ''}}
                </div>
                ${{canManage ? `
                <div class="mt-1 pt-1 border-top d-flex gap-1">
                    ${{isSelected
                        ? `<button class="btn btn-outline-danger btn-sm flex-fill" style="font-size:0.7rem;padding:2px 6px"
                               onclick="event.stopPropagation();saveSkin(null)">Remove</button>`
                        : `<button class="btn btn-outline-success btn-sm flex-fill" style="font-size:0.7rem;padding:2px 6px"
                               onclick="event.stopPropagation();saveSkin('${{s.id}}')">Select</button>`}}
                </div>` : ''}}
            </div>`;
        }}).join('');
    }}

    let previewSkinSlug = null;

    function previewSkin(slug) {{
        previewSkinSlug = previewSkinSlug === slug ? null : slug;
        renderSkinList();
        if (previewImageSrc && previewSkinSlug) renderSkinPreview();
        else {{
            const prev = document.getElementById('skin-preview-area');
            if (prev && !previewSkinSlug) prev.remove();
        }}
    }}

    async function saveSkin(skinId) {{
        if (!roleId) {{ await GhDialog.alert({{ title: 'Notice', message: ('Role ID not available'), variant: 'info' }}); return; }}
        try {{
            const r = await fetch(`/api/roles/${{roleId}}/`, {{
                method: 'PATCH',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{badge_skin_id: skinId}})
            }});
            const d = await r.json();
            if (r.ok) {{
                activeSkinId = d.role ? d.role.badge_skin_id : skinId;
                renderSkinList();
            }} else {{
                await GhDialog.alert({{ title: 'Notice', message: (d.error || 'Failed to save skin'), variant: 'info' }});
            }}
        }} catch(e) {{ await GhDialog.alert({{ title: 'Notice', message: ('Error saving skin'), variant: 'info' }}); }}
    }}

    function renderSkinPreview() {{
        const skin = allSkins.find(s => s.slug === previewSkinSlug);
        if (!skin || !previewImageSrc) return;
        const spec = skin.layout_spec || {{}};
        const imageRegion = (spec.regions || []).find(r => r.id === 'image') || {{}};
        const isCircle = imageRegion.size === 'circle';
        const isLeft = imageRegion.placement === 'left';
        const html = `
        <div style="max-width:300px;margin:0.75rem auto;border:1px solid #444;border-radius:8px;overflow:hidden;background:#1a1a2e;">
            <div style="display:flex;flex-direction:${{isLeft ? 'row' : 'column'}};align-items:center;padding:12px;gap:10px;">
                <img src="${{previewImageSrc}}" style="width:${{isLeft ? '60px' : isCircle ? '80px' : '100%%'}};height:${{isLeft ? '60px' : 'auto'}};
                    object-fit:cover;border-radius:${{isCircle ? '50%%' : '6px'}};flex-shrink:0;">
                <div>
                    <div style="font-weight:bold;color:#fff;">${{roleData ? roleData.title_guild : roleSlug}}</div>
                    <div style="font-size:0.8rem;color:#aaa;">Claimant Name</div>
                </div>
            </div>
            <div style="background:#111;padding:4px 12px;font-size:0.7rem;color:#666;text-align:center;">
                ${{skin.name}} skin preview
            </div>
        </div>`;
        let preview = document.getElementById('skin-preview-area');
        if (!preview) {{
            preview = document.createElement('div');
            preview.id = 'skin-preview-area';
            document.getElementById('skin-list').after(preview);
        }}
        preview.innerHTML = html;
    }}

    // ── Design cards ─────────────────────────────────────────────────
    function toggleSourceFields() {{
        const sourceType = document.getElementById('sourceType').value;
        document.getElementById('uploadField').style.display = sourceType === 'upload' ? 'block' : 'none';
        document.getElementById('urlField').style.display = sourceType === 'url' ? 'block' : 'none';
        document.getElementById('ordinalFields').style.display = sourceType === 'ordinal' ? 'block' : 'none';
    }}

    async function loadImages() {{
        const sortBy = document.getElementById('sort-select').value;
        const container = document.getElementById('images-container');
        try {{
            const response = await fetch(`/api/roles/${{roleSlug}}/images/?sort=${{sortBy}}`);
            const data = await response.json();
            if (data.images.length === 0) {{
                container.innerHTML = '<div class="col-12 text-center py-5"><p class="text-muted">No designs yet. Be the first to submit one!</p></div>';
                return;
            }}
            container.innerHTML = data.images.map(img => {{
                let imgSrc = img.image_url;
                if (img.source_type === 'upload' && img.file_path) {{
                    imgSrc = `/uploads/role_images/${{img.file_path.split('/').pop()}}`;
                }} else if (img.source_type === 'ordinal') {{
                    imgSrc = `https://ordinals.com/content/${{img.inscription_id}}`;
                }}
                const fallbackSvg = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Crect fill='%23ddd' width='200' height='200'/%3E%3Ctext fill='%23999' x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-family='sans-serif' font-size='16'%3ENo image%3C/text%3E%3C/svg%3E";
                return `
                <div class="col-md-6 mb-3">
                    <div class="card h-100">
                        <a href="/roles/${{roleSlug}}/images/${{img.id}}/" class="d-block gh-role-design-link"
                           onclick="previewImageSrc='${{imgSrc}}'; if(previewSkinSlug) {{ event.preventDefault(); renderSkinPreview(); }}">
                            <img src="${{imgSrc}}" class="card-img-top" alt="Design" style="width:100%;height:auto;display:block;object-fit:contain;"
                                 onerror="this.src='${{fallbackSvg}}'">
                        </a>
                        <div class="card-body py-2">
                            ${{img.is_primary ? '<span class="badge bg-success mb-1">Primary</span> ' : ''}}
                            ${{img.is_hidden && isAdmin ? '<span class="badge bg-warning mb-1">Hidden</span> ' : ''}}
                            <p class="small text-muted mb-1">By ${{img.submitted_by_name}} · ${{new Date(img.submitted_at).toLocaleDateString()}}</p>
                            <div class="d-flex justify-content-between align-items-center gap-1">
                                <div class="btn-group btn-group-sm">
                                    <button class="btn ${{img.user_vote === 1 ? 'btn-success' : 'btn-outline-success'}}" onclick="vote('${{img.id}}', 1, event)">
                                        <i class="fas fa-thumbs-up"></i> ${{img.upvotes}}
                                    </button>
                                    <button class="btn ${{img.user_vote === -1 ? 'btn-danger' : 'btn-outline-danger'}}" onclick="vote('${{img.id}}', -1, event)">
                                        <i class="fas fa-thumbs-down"></i> ${{img.downvotes}}
                                    </button>
                                </div>
                                <span class="badge bg-primary">${{img.net_score}}</span>
                                <button class="btn btn-outline-secondary btn-sm" title="Preview with skin"
                                    onclick="previewImageSrc='${{imgSrc}}'; if(previewSkinSlug) renderSkinPreview(); else document.getElementById('skin-list').scrollIntoView({{behavior:'smooth'}})">
                                    <i class="fas fa-palette"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>`;
            }}).join('');
        }} catch (error) {{
            container.innerHTML = '<div class="col-12 text-center py-5"><p class="text-danger">Error loading designs</p></div>';
        }}
    }}

    async function vote(imageId, value, event) {{
        event.preventDefault(); event.stopPropagation();
        try {{
            const response = await fetch(`/api/role-images/${{imageId}}/vote/`, {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{value}})
            }});
            if (response.ok) {{ loadImages(); }}
            else {{ const d = await response.json(); await GhDialog.alert({{ title: 'Notice', message: (d.error || 'Failed to vote'), variant: 'info' }}); }}
        }} catch (error) {{ await GhDialog.alert({{ title: 'Notice', message: ('Error voting'), variant: 'info' }}); }}
    }}

    async function submitImage() {{
        const sourceType = document.getElementById('sourceType').value;
        const formData = new FormData();
        formData.append('source_type', sourceType);
        if (sourceType === 'upload') {{
            const file = document.getElementById('imageFile').files[0];
            if (!file) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please select a file'), variant: 'info' }}); return; }}
            formData.append('file', file);
        }} else if (sourceType === 'url') {{
            const url = document.getElementById('imageUrl').value;
            if (!url) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please enter an image URL'), variant: 'info' }}); return; }}
            formData.append('image_url', url);
        }} else if (sourceType === 'ordinal') {{
            const inscriptionId = document.getElementById('inscriptionId').value;
            if (!inscriptionId) {{ await GhDialog.alert({{ title: 'Notice', message: ('Please enter an inscription ID'), variant: 'info' }}); return; }}
            formData.append('inscription_id', inscriptionId);
            formData.append('content_type', document.getElementById('contentType').value);
            formData.append('chain', 'bitcoin');
        }}
        try {{
            const response = await fetch(`/api/roles/${{roleSlug}}/images/`, {{ method: 'POST', body: formData }});
            if (response.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('submitImageModal')).hide();
                document.getElementById('submitImageForm').reset();
                loadImages();
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to submit design'), variant: 'info' }});
            }}
        }} catch (error) {{ await GhDialog.alert({{ title: 'Notice', message: ('Error submitting design'), variant: 'info' }}); }}
    }}

    loadCycleCard();
    loadSkins();
    loadImages();
    </script>
    """

    return render_page(f"Designs: {role_title} - GovHub", content, theme=current_theme, user_menu=user_menu)


@bp.route('/roles/<role_slug>/images/<image_id>/')
def role_image_detail(role_slug, image_id):
    """Detailed view of a single role image proposal"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    is_admin = current_user and current_user.get('role') == 'admin'

    # Fetch image
    image = RoleImage.query.get_or_404(image_id)

    # Check if hidden
    if image.is_hidden and not is_admin:
        flash('Image not found', 'error')
        return redirect(url_for('roles_pages.role_images_gallery', role_slug=role_slug))

    # Get user's vote
    user_vote = None
    if current_user:
        vote = RoleImageVote.query.filter_by(
            image_id=image_id,
            user_id=current_user['id']
        ).first()
        user_vote = vote.value if vote else None

    content = f"""
    <div class="gh-page container mt-4">
        {gh_page_header('Role Image', f'Proposal for {role_slug}', 'fa-image', actions_html=f'<a href="/roles/{role_slug}/images/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-1"></i>Gallery</a>', breadcrumb_html=gh_breadcrumb([('Roles', '/roles/'), (role_slug, f'/roles/{role_slug}/'), ('Images', f'/roles/{role_slug}/images/'), ('Image', None)]))}
        <div class="gh-detail-layout">
        <div class="row">
            <div class="col-md-8">
                <div class="living-module mb-4">
                    <div class="living-module-body">
                        <h2 class="h4 mb-3">
                            Role Image for {role_slug}
                            {f'<span class="badge bg-success ms-2">Primary</span>' if image.is_primary else ''}
                            {f'<span class="badge bg-warning ms-2">Hidden</span>' if image.is_hidden and is_admin else ''}
                        </h2>

                        <div class="mb-4">
                            {'<iframe src="' + image.image_url + '" style="width: 100%; height: 500px; border: none;"></iframe>' if image.source_type == 'ordinal' and image.content_type and 'html' in (image.content_type or '').lower() else '<img src="' + image.image_url + '" class="img-fluid" alt="Role image" style="width:100%;height:auto;display:block;object-fit:contain;">'}
                        </div>

                        <div class="d-flex justify-content-between align-items-center mb-4">
                            <div class="btn-group" role="group">
                                <button class="btn {'btn-success' if user_vote == 1 else 'btn-outline-success'}" onclick="vote(1)" {'disabled' if not current_user else ''}>
                                    <i class="fas fa-thumbs-up"></i> Upvote ({image.upvotes})
                                </button>
                                <button class="btn {'btn-danger' if user_vote == -1 else 'btn-outline-danger'}" onclick="vote(-1)" {'disabled' if not current_user else ''}>
                                    <i class="fas fa-thumbs-down"></i> Downvote ({image.downvotes})
                                </button>
                                {f'<button class="btn btn-outline-secondary" onclick="removeVote()">Remove Vote</button>' if user_vote and current_user else ''}
                            </div>
                            <div>
                                <h4 class="mb-0">
                                    <span class="badge bg-primary">Net Score: {image.net_score}</span>
                                </h4>
                            </div>
                        </div>

                        {'<div class="alert alert-info"><i class="fas fa-info-circle me-2"></i>Please <a href="/login/">login</a> to vote on images.</div>' if not current_user else ''}
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card mb-3">
                    <div class="card-header">
                        <h5 class="mb-0">Image Details</h5>
                    </div>
                    <div class="card-body">
                        <dl class="row mb-0">
                            <dt class="col-sm-5">Submitted by:</dt>
                            <dd class="col-sm-7">{image.submitted_by.displayName or image.submitted_by.username if image.submitted_by else 'Unknown'}</dd>

                            <dt class="col-sm-5">Submitted:</dt>
                            <dd class="col-sm-7">{image.submitted_at.strftime('%Y-%m-%d %H:%M') if image.submitted_at else 'Unknown'}</dd>

                            <dt class="col-sm-5">Source:</dt>
                            <dd class="col-sm-7"><span class="badge bg-info">{image.source_type}</span></dd>

                            {f'<dt class="col-sm-5">Chain:</dt><dd class="col-sm-7">{image.chain}</dd>' if image.chain else ''}

                            {f'<dt class="col-sm-5">Inscription ID:</dt><dd class="col-sm-7"><a href="https://ordinals.com/inscription/{image.inscription_id}" target="_blank" class="text-break small">{image.inscription_id[:20]}...</a></dd>' if image.inscription_id else ''}

                            {f'<dt class="col-sm-5">Content Type:</dt><dd class="col-sm-7">{image.content_type}</dd>' if image.content_type else ''}

                            {f'<dt class="col-sm-5">Promoted by:</dt><dd class="col-sm-7">{image.promoted_by.displayName or image.promoted_by.username if image.promoted_by else "N/A"}</dd>' if image.is_primary else ''}

                            {f'<dt class="col-sm-5">Promoted at:</dt><dd class="col-sm-7">{image.promoted_at.strftime("%Y-%m-%d %H:%M") if image.promoted_at else "N/A"}</dd>' if image.is_primary else ''}
                        </dl>
                    </div>
                </div>

                {f'''<div class="card mb-3">
                    <div class="card-header bg-danger text-white">
                        <h5 class="mb-0">Admin Actions</h5>
                    </div>
                    <div class="card-body">
                        {f'<button class="btn btn-success w-100 mb-2" onclick="promoteImage()"><i class="fas fa-star me-2"></i>Promote to Primary</button>' if not image.is_primary else '<button class="btn btn-warning w-100 mb-2" onclick="demoteImage()"><i class="fas fa-star-half-alt me-2"></i>Demote from Primary</button>'}

                        {f'<button class="btn btn-warning w-100 mb-2" onclick="hideImage()"><i class="fas fa-eye-slash me-2"></i>Hide Image</button>' if not image.is_hidden else '<button class="btn btn-info w-100 mb-2" onclick="unhideImage()"><i class="fas fa-eye me-2"></i>Unhide Image</button>'}

                        <button class="btn btn-danger w-100 mb-3" onclick="deleteImage()">
                            <i class="fas fa-trash me-2"></i>Delete Image
                        </button>

                        <hr>

                        <div class="mb-2">
                            <label for="adminNote" class="form-label">Admin Note:</label>
                            <textarea class="form-control" id="adminNote" rows="3">{image.admin_note or ''}</textarea>
                        </div>
                        <button class="btn btn-primary w-100" onclick="saveNote()">
                            <i class="fas fa-save me-2"></i>Save Note
                        </button>
                    </div>
                </div>''' if is_admin else ''}
            </div>
        </div>
        </div>
    </div>

    <script>
    const imageId = {_json.dumps(image_id)};
    const roleSlug = {_json.dumps(role_slug)};

    async function vote(value) {{
        try {{
            const response = await fetch(`/api/role-images/${{imageId}}/vote/`, {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{value}})
            }});

            if (response.ok) {{
                location.reload();
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to vote'), variant: 'info' }});
            }}
        }} catch (error) {{
            console.error('Error voting:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error voting on image'), variant: 'info' }});
        }}
    }}

    async function removeVote() {{
        try {{
            const response = await fetch(`/api/role-images/${{imageId}}/vote/`, {{
                method: 'DELETE'
            }});

            if (response.ok) {{
                location.reload();
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to remove vote'), variant: 'info' }});
            }}
        }} catch (error) {{
            console.error('Error removing vote:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error removing vote'), variant: 'info' }});
        }}
    }}

    async function promoteImage() {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Promote this image to primary role image?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;

        try {{
            const response = await fetch(`/api/role-images/${{imageId}}/promote/`, {{
                method: 'POST'
            }});

            if (response.ok) {{
                location.reload();
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to promote image'), variant: 'info' }});
            }}
        }} catch (error) {{
            console.error('Error promoting image:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error promoting image'), variant: 'info' }});
        }}
    }}

    async function demoteImage() {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Demote this image from primary?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;

        try {{
            const response = await fetch(`/api/role-images/${{imageId}}/promote/`, {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{demote: true}})
            }});

            if (response.ok) {{
                location.reload();
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to demote image'), variant: 'info' }});
            }}
        }} catch (error) {{
            console.error('Error demoting image:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error demoting image'), variant: 'info' }});
        }}
    }}

    async function hideImage() {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Hide this image from public view?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;

        try {{
            const response = await fetch(`/api/role-images/${{imageId}}/hide/`, {{
                method: 'POST'
            }});

            if (response.ok) {{
                location.reload();
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to hide image'), variant: 'info' }});
            }}
        }} catch (error) {{
            console.error('Error hiding image:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error hiding image'), variant: 'info' }});
        }}
    }}

    async function unhideImage() {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Unhide this image?'), variant: 'warning', confirmLabel: 'Confirm' }})) return;

        try {{
            const response = await fetch(`/api/role-images/${{imageId}}/unhide/`, {{
                method: 'POST'
            }});

            if (response.ok) {{
                location.reload();
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to unhide image'), variant: 'info' }});
            }}
        }} catch (error) {{
            console.error('Error unhiding image:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error unhiding image'), variant: 'info' }});
        }}
    }}

    async function deleteImage() {{
        if (!await GhDialog.confirm({{ title: 'Confirm', message: ('Permanently delete this image? This cannot be undone.'), variant: 'warning', confirmLabel: 'Confirm' }})) return;

        try {{
            const response = await fetch(`/api/role-images/${{imageId}}/`, {{
                method: 'DELETE'
            }});

            if (response.ok) {{
                window.location.href = `/roles/${{roleSlug}}/images/`;
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to delete image'), variant: 'info' }});
            }}
        }} catch (error) {{
            console.error('Error deleting image:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error deleting image'), variant: 'info' }});
        }}
    }}

    async function saveNote() {{
        const note = document.getElementById('adminNote').value;

        try {{
            const response = await fetch(`/api/role-images/${{imageId}}/note/`, {{
                method: 'PATCH',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{admin_note: note}})
            }});

            if (response.ok) {{
                await GhDialog.alert({{ title: 'Notice', message: ('Note saved successfully'), variant: 'info' }});
            }} else {{
                const data = await response.json();
                await GhDialog.alert({{ title: 'Notice', message: (data.error || 'Failed to save note'), variant: 'info' }});
            }}
        }} catch (error) {{
            console.error('Error saving note:', error);
            await GhDialog.alert({{ title: 'Notice', message: ('Error saving note'), variant: 'info' }});
        }}
    }}
    </script>
    """

    return render_page(f"Image Detail: {role_slug} - GovHub", content, theme=current_theme, user_menu=user_menu)
