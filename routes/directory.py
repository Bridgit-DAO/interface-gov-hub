"""Directory pages: person, meeting, layers, workgroups, waitlists, guilds."""
import html as html_mod
import json
from flask import Blueprint, redirect, request, session

from models import User, Layer
from services.identity import get_current_user
from services.directory_ui import (
    gh_page_open,
    gh_page_close,
    gh_page_header,
    gh_filter_row,
    gh_filter_col,
    gh_directory_grid,
    gh_directory_toolbar,
)
from services.people_directory import (
    build_people_lookup_tables,
    build_person_row,
    workgroup_filter_options,
)

bp = Blueprint('directory', __name__, url_prefix='')


def _get_imports():
    """Late imports to avoid circular imports."""
    from services.rendering import generate_user_menu, render_page
    from services.groups import GROUPS
    return generate_user_menu, render_page, GROUPS


@bp.route('/person/')
def people():
    """People directory: discover participants, layers, workgroups, and activity."""
    generate_user_menu, render_page, _GROUPS = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    is_admin = current_user and current_user.get('role') == 'admin'

    lookup = build_people_lookup_tables()
    users = User.query.order_by(User.username).all()
    wg_options = ''.join(
        f'<option value="{html_mod.escape(ac)}">{html_mod.escape(label)}</option>'
        for ac, label in workgroup_filter_options(lookup)
    )
    rows = [
        build_person_row(u, lookup, show_admin_actions=is_admin)['row_html']
        for u in users
    ]
    num_cols = 6 + (1 if is_admin else 0)
    table_rows = (
        ''.join(rows)
        if rows
        else f'<tr><td colspan="{num_cols}" class="text-center text-muted py-4">No participants yet.</td></tr>'
    )
    actions_th = '<th></th>' if is_admin else ''
    sort_options = (
        ('last-active', 'Last active'),
        ('submissions', 'Submissions'),
        ('activity', 'Activity'),
        ('name-asc', 'Name A–Z'),
        ('name-desc', 'Name Z–A'),
        ('workgroup', 'Workgroup'),
        ('role', 'Site role'),
    )
    sort_opts_html = ''.join(
        f'<option value="{v}"{" selected" if v == "last-active" else ""}>{label}</option>'
        for v, label in sort_options
    )
    content = f"""
    {gh_page_open()}
    {gh_page_header('People', 'Discover who is active — roles, layers, workgroups, and contributions.', 'fa-user-friends')}
    {gh_filter_row(
        gh_filter_col('Search', '<input type="search" id="people-search" class="form-control" placeholder="Name or username…" autocomplete="off">', 'col-md-5')
        + gh_filter_col('Workgroup', f'<select id="people-workgroup" class="form-select"><option value="">All workgroups</option>{wg_options}</select>', 'col-md-4')
        + gh_filter_col('Sort', f'<select id="people-sort" class="form-select">{sort_opts_html}</select>', 'col-md-3')
    )}
    <div class="gh-people-table-wrap">
        <table class="table table-hover mb-0" id="people-table">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Roles</th>
                    <th>Layers</th>
                    <th>Workgroups</th>
                    <th>Last active</th>
                    <th>Activity</th>
                    {actions_th}
                </tr>
            </thead>
            <tbody>{table_rows}</tbody>
        </table>
    </div>
    {gh_page_close()}
    <script>
    (function() {{
        var searchEl = document.getElementById('people-search');
        var workgroupEl = document.getElementById('people-workgroup');
        var sortEl = document.getElementById('people-sort');
        var tbody = document.querySelector('#people-table tbody');
        function compareRows(a, b, sort) {{
            if (sort === 'name-asc') {{
                return (a.getAttribute('data-name') || '').localeCompare(b.getAttribute('data-name') || '', undefined, {{ numeric: true, sensitivity: 'base' }});
            }}
            if (sort === 'name-desc') {{
                return (b.getAttribute('data-name') || '').localeCompare(a.getAttribute('data-name') || '', undefined, {{ numeric: true, sensitivity: 'base' }});
            }}
            if (sort === 'submissions') {{
                return (parseInt(b.getAttribute('data-submissions'), 10) || 0) - (parseInt(a.getAttribute('data-submissions'), 10) || 0);
            }}
            if (sort === 'activity') {{
                return (parseInt(b.getAttribute('data-activity'), 10) || 0) - (parseInt(a.getAttribute('data-activity'), 10) || 0);
            }}
            if (sort === 'workgroup') {{
                return (a.getAttribute('data-workgroup') || '').localeCompare(b.getAttribute('data-workgroup') || '', undefined, {{ numeric: true, sensitivity: 'base' }});
            }}
            if (sort === 'role') {{
                return (a.getAttribute('data-role') || '').localeCompare(b.getAttribute('data-role') || '', undefined, {{ numeric: true, sensitivity: 'base' }});
            }}
            return (parseInt(b.getAttribute('data-last-active'), 10) || 0) - (parseInt(a.getAttribute('data-last-active'), 10) || 0);
        }}
        function applyPeopleView() {{
            if (!tbody) return;
            var q = (searchEl && searchEl.value) ? searchEl.value.toLowerCase().trim() : '';
            var group = (workgroupEl && workgroupEl.value) ? workgroupEl.value.trim() : '';
            var sort = (sortEl && sortEl.value) ? sortEl.value : 'last-active';
            var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr[data-search]'));
            rows.forEach(function(tr) {{
                var show = true;
                if (q && (tr.getAttribute('data-search') || '').indexOf(q) === -1) show = false;
                if (group) {{
                    var groups = (tr.getAttribute('data-groups') || '').split(/\\s+/).filter(Boolean);
                    if (groups.indexOf(group) === -1) show = false;
                }}
                tr.style.display = show ? '' : 'none';
            }});
            var visible = rows.filter(function(tr) {{ return tr.style.display !== 'none'; }});
            visible.sort(function(a, b) {{ return compareRows(a, b, sort); }});
            visible.forEach(function(tr) {{ tbody.appendChild(tr); }});
        }}
        if (searchEl) searchEl.addEventListener('input', applyPeopleView);
        if (workgroupEl) workgroupEl.addEventListener('change', applyPeopleView);
        if (sortEl) sortEl.addEventListener('change', applyPeopleView);
        applyPeopleView();
    }})();
    </script>
    """
    return render_page("People - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/meeting/')
def meetings():
    """Meetings - coming soon"""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()

    content = f"""
    {gh_page_open()}
    {gh_page_header('Meetings', 'Upcoming MLGH meetings and sessions — coming soon', 'fa-calendar', actions_html='<a href="/" class="btn btn-outline-secondary btn-sm">Home</a>')}
    <div class="living-module">
        <div class="living-module-body text-center py-5">
            <i class="fas fa-calendar fa-3x text-muted mb-3"></i>
            <p class="text-muted mb-0">Information about upcoming MLGH meetings will be available here.</p>
        </div>
    </div>
    {gh_page_close()}
    """
    return render_page("Meetings - MLGH", content, theme=session.get('theme', 'dark'), user_menu=user_menu)


@bp.route('/layers/')
def projects_directory():
    """Projects directory page"""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    create_btn = (
        '<a href="/layers/create/" class="btn btn-primary"><i class="fas fa-plus me-2"></i>Create Layer</a>'
        if current_user
        else '<a href="/login/" class="btn btn-primary"><i class="fas fa-sign-in-alt me-2"></i>Login to Create</a>'
    )
    content = f"""
    {gh_page_open()}
    {gh_page_header('Layers Map', 'Discover layers — status, activity, and community at a glance', 'fa-layer-group', create_btn)}
    {gh_filter_row(
        gh_filter_col('Status', '<select id="status-filter" class="form-select" onchange="loadProjects()"><option value="">All Statuses</option><option value="active" selected>Active</option><option value="proposed">Proposed</option><option value="stabilizing">Stabilizing</option><option value="maintaining">Maintaining</option><option value="dormant">Dormant</option><option value="concluded">Concluded</option><option value="archived">Archived</option></select>')
        + gh_filter_col('Approval', '<select id="approval-filter" class="form-select" onchange="loadProjects()"><option value="active" selected>Active</option><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select>')
        + gh_directory_toolbar(search_placeholder='Search layers…', search_col='col-md-4', sort_col='col-md-2')
    )}
    {gh_directory_grid('projects-container', 'row row-cols-2 row-cols-sm-3 row-cols-md-3 row-cols-lg-4 g-3')}
    {gh_page_close()}
    <script>
    let allProjects = [];
    function layersApiUrl(extra) {{
        const params = new URLSearchParams();
        const statusFilter = document.getElementById('status-filter').value;
        if (statusFilter) params.append('status', statusFilter);
        if (extra) Object.entries(extra).forEach(([k, v]) => params.append(k, v));
        const qs = params.toString();
        return '/api/layers/' + (qs ? '?' + qs : '');
    }}
    function orderProjectsByApproval(projects, approvalFilter) {{
        if (approvalFilter !== 'active') return projects;
        const rank = {{ approved: 0, pending: 1 }};
        return projects.slice().sort((a, b) =>
            (rank[a.approval_status] ?? 9) - (rank[b.approval_status] ?? 9)
        );
    }}
    async function loadProjects() {{
        const approvalFilter = document.getElementById('approval-filter').value;
        try {{
            if (approvalFilter === 'active') {{
                const [approvedRes, pendingRes] = await Promise.all([
                    fetch(layersApiUrl({{ approval_status: 'approved' }})),
                    fetch(layersApiUrl({{ approval_status: 'pending' }})),
                ]);
                const approvedData = await approvedRes.json();
                const pendingData = await pendingRes.json();
                allProjects = orderProjectsByApproval(
                    [...(approvedData.layers || []), ...(pendingData.layers || [])],
                    'active'
                );
            }} else {{
                const response = await fetch(layersApiUrl(
                    approvalFilter ? {{ approval_status: approvalFilter }} : {{}}
                ));
                const data = await response.json();
                allProjects = data.layers || [];
            }}
            filterProjects();
        }} catch (error) {{
            console.error('Error loading projects:', error);
            document.getElementById('projects-container').innerHTML = GhDirectory.emptyState('Error loading layers', 'danger');
        }}
    }}
    function filterProjects() {{
        const items = GhDirectory.filterAndSort(allProjects, {{
            searchTerm: GhDirectory.getSearchValue('search-input'),
            sort: GhDirectory.getSortValue('sort-filter'),
            searchFields: ['name', 'description', 'mission', 'slug'],
            nameKey: 'name',
            dateKeys: ['last_activity_at', 'updated_at', 'created_at'],
        }});
        displayProjects(items);
    }}
    function layerCardImageUrl(project) {{
        if (!project || !project.image_url) return '';
        const v = project.updated_at || project.id || '';
        const sep = project.image_url.indexOf('?') >= 0 ? '&' : '?';
        return project.image_url + sep + 'v=' + encodeURIComponent(String(v));
    }}
    function displayProjects(projects) {{
        const container = document.getElementById('projects-container');
        if (projects.length === 0) {{
            container.innerHTML = GhDirectory.emptyState('No layers found');
            return;
        }}
        let html = '';
        projects.forEach(project => {{
            const statusMap = {{'proposed':'<span class="badge bg-info">Proposed</span>','active':'<span class="badge bg-success">Active</span>','stabilizing':'<span class="badge bg-primary">Stabilizing</span>','maintaining':'<span class="badge bg-secondary">Maintaining</span>','dormant':'<span class="badge bg-warning">Dormant</span>','concluded':'<span class="badge bg-dark">Concluded</span>','archived':'<span class="badge bg-secondary">Archived</span>'}};
            const approvalMap = {{'pending':'<span class="badge bg-warning">Pending Approval</span>','approved':'<span class="badge bg-success">Approved</span>','rejected':'<span class="badge bg-danger">Rejected</span>'}};
            const statusBadge = (project.approval_status === 'approved' && project.status === 'proposed') ? '' : (statusMap[project.status] || '');
            const approvalBadge = approvalMap[project.approval_status] || '';
            const nameEsc = (project.name || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            const descRaw = (project.mission || project.description || '').trim();
            const descEsc = descRaw.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            const imgSrc = layerCardImageUrl(project);
            const pulseLabel = project.status === 'active' ? 'Active' : (project.last_activity_at ? 'Recent' : 'Layer');
            const visualHtml = imgSrc
                ? `<div class="layer-map-tile-visual"><img src="${{imgSrc}}" alt="${{nameEsc}}"><span class="layer-map-tile-pulse">${{pulseLabel}}</span></div>`
                : `<div class="layer-map-tile-visual"><span class="layer-map-placeholder"><i class="fas fa-layer-group"></i></span><span class="layer-map-tile-pulse">${{pulseLabel}}</span></div>`;
            const wgCount = project.workgroups_count || 0;
            const wgLabel = wgCount === 1 ? '1 workgroup' : wgCount + ' workgroups';
            const descBlock = descEsc ? `<p class="layer-map-tile-desc">${{descEsc}}</p>` : '';
            html += `<div class="col d-flex"><div class="layer-map-tile">${{visualHtml}}` +
                `<div class="layer-map-tile-body">` +
                `<h6 class="layer-map-tile-title"><a href="/layers/${{project.slug}}/">${{nameEsc}}</a></h6>` +
                descBlock +
                `<div class="layer-map-tile-footer">` +
                `<div class="layer-map-tile-badges">${{statusBadge}}${{approvalBadge}}</div>` +
                `<span class="layer-map-tile-meta"><i class="fas fa-users me-1"></i>${{wgLabel}}</span>` +
                `</div></div></div></div>`;
        }});
        container.innerHTML = html;
    }}
    loadProjects();
    GhDirectory.bindControls('search-input', 'sort-filter', filterProjects);
    </script>
    """
    return render_page("Layers Directory - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/workgroups/')
def workgroups_directory():
    """Workgroups directory page"""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    
    wg_create = (
        '<button class="btn btn-primary" onclick="showCreateWorkgroupModal()"><i class="fas fa-plus me-2"></i>Create Workgroup</button>'
        if current_user else ''
    )
    wg_actions = (
        '<a href="/layers/" class="btn btn-outline-secondary"><i class="fas fa-arrow-left me-2"></i>Layers</a>'
        + wg_create
    )
    content = f"""
    {gh_page_open()}
    {gh_page_header('Workgroups Directory', 'Browse workgroups across all layers', 'fa-users-cog', wg_actions)}
    {gh_filter_row(
        gh_directory_toolbar(
            search_placeholder='Search workgroups…',
            extra_cols=(
                gh_filter_col('Layer', '<select id="project-filter" class="form-select" onchange="loadWorkgroups()"><option value="">All Layers</option></select>')
                + gh_filter_col('Status', '<select id="status-filter" class="form-select" onchange="loadWorkgroups()"><option value="">All Statuses</option><option value="active" selected>Active</option><option value="inactive">Inactive</option><option value="completed">Completed</option><option value="archived">Archived</option></select>', 'col-md-2')
            ),
        )
    )}
    {gh_directory_grid('workgroups-container')}
    {gh_page_close()}
    
    <script>
    let allWorkgroups = [];
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
    
    async function loadWorkgroups() {{
        const projectFilter = document.getElementById('project-filter').value;
        const statusFilter = document.getElementById('status-filter').value;
        
        try {{
            allWorkgroups = [];
            
            if (projectFilter) {{
                // Load workgroups for specific project
                let url = `/api/layers/${{projectFilter}}/workgroups/`;
                if (statusFilter) url += `?status=${{statusFilter}}`;
                
                const response = await fetch(url);
                const data = await response.json();
                allWorkgroups = (response.ok && data.workgroups) ? data.workgroups.map(wg => ({{...wg, layer_name: (allProjects.find(p => p.id === wg.layer_id) || {{}}).name || ''}})) : [];
            }} else {{
                // Load workgroups from all projects
                for (const project of allProjects) {{
                    let url = `/api/layers/${{project.id}}/workgroups/`;
                    if (statusFilter) url += `?status=${{statusFilter}}`;
                    
                    const response = await fetch(url);
                    const data = await response.json();
                    const wgs = (response.ok && Array.isArray(data.workgroups)) ? data.workgroups : [];
                    allWorkgroups = allWorkgroups.concat(wgs.map(wg => ({{...wg, layer_name: project.name}})));
                }}
            }}
            allWorkgroups = GhDirectory.dedupeById(allWorkgroups, 'id');
            
            filterWorkgroups();
        }} catch (error) {{
            console.error('Error loading workgroups:', error);
            document.getElementById('workgroups-container').innerHTML = GhDirectory.emptyState('Error loading workgroups', 'danger');
        }}
    }}
    
    function filterWorkgroups() {{
        const items = GhDirectory.filterAndSort(allWorkgroups, {{
            searchTerm: GhDirectory.getSearchValue('search-input'),
            sort: GhDirectory.getSortValue('sort-filter'),
            searchFields: ['name', 'description', 'acronym', 'slug', 'layer_name'],
            nameKey: 'name',
            dateKeys: ['updated_at', 'created_at'],
        }});
        displayWorkgroups(items);
    }}
    
    function displayWorkgroups(workgroups) {{
        const container = document.getElementById('workgroups-container');
        
        if (workgroups.length === 0) {{
            container.innerHTML = GhDirectory.emptyState('No workgroups found');
            return;
        }}
        
        let html = '';
        workgroups.forEach(wg => {{
            const statusBadge = getStatusBadge(wg.status);
            const approvalBadge = getApprovalBadge(wg.approval_status);
            const project = allProjects.find(p => p.id === wg.layer_id);
            html += GhDirectory.tile({{
                href: '/workgroups/' + wg.slug + '/',
                title: wg.name,
                description: wg.description || 'No description',
                imageUrl: wg.image_url || '',
                icon: 'fa-users-cog',
                pulse: wg.status === 'active' ? 'Active' : '',
                badgesHtml: statusBadge + approvalBadge,
                metaHtml: project ? '<i class="fas fa-layer-group me-1"></i>' + GhDirectory.esc(project.name) : '',
                footerHtml: 'Created ' + new Date(wg.created_at).toLocaleDateString()
            }});
        }});
        
        container.innerHTML = html;
    }}
    
    function getStatusBadge(status) {{
        const badges = {{
            'active': '<span class="badge bg-success">Active</span>',
            'inactive': '<span class="badge bg-warning">Inactive</span>',
            'completed': '<span class="badge bg-primary">Completed</span>',
            'archived': '<span class="badge bg-secondary">Archived</span>'
        }};
        return badges[status] || '';
    }}
    
    function getApprovalBadge(approval) {{
        const badges = {{
            'pending': '<span class="badge bg-warning">Pending Approval</span>',
            'approved': '<span class="badge bg-success">Approved</span>',
            'rejected': '<span class="badge bg-danger">Rejected</span>'
        }};
        return badges[approval] || '';
    }}
    
    // Load data on page load
    function showCreateWorkgroupModal() {{
        const modalHtml = `
            <div class="modal fade" id="createWorkgroupModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Create New Workgroup</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="wg-alert-container"></div>
                            
                            <form id="createWorkgroupForm">
                                <div class="mb-3">
                                    <label for="wg-project" class="form-label">Layer *</label>
                                    <select class="form-select" id="wg-project" required>
                                        <option value="">Select a project...</option>
                                    </select>
                                    <div class="form-text">Select the project this workgroup belongs to</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="wg-name" class="form-label">Workgroup Name *</label>
                                    <input type="text" class="form-control" id="wg-name" required>
                                    <div class="form-text">A clear, descriptive name for the workgroup</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="wg-description" class="form-label">Description *</label>
                                    <textarea class="form-control" id="wg-description" rows="4" required></textarea>
                                    <div class="form-text">Describe the workgroup's purpose and goals</div>
                                </div>
                                
                                <div class="alert alert-info">
                                    <i class="fas fa-info-circle me-2"></i>
                                    <strong>Note:</strong> New workgroups require approval from the layer admin before becoming active.
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="submitWorkgroupBtn">
                                <i class="fas fa-plus me-2"></i>Create Workgroup
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        if (!document.getElementById('createWorkgroupModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        
        // Populate project dropdown
        const select = document.getElementById('wg-project');
        select.innerHTML = '<option value="">Select a project...</option>';
        allProjects.forEach(project => {{
            const option = document.createElement('option');
            option.value = project.id;
            option.textContent = project.name;
            select.appendChild(option);
        }});
        
        const modal = new bootstrap.Modal(document.getElementById('createWorkgroupModal'));
        modal.show();
        
        document.getElementById('submitWorkgroupBtn').onclick = async () => {{
            const projectId = document.getElementById('wg-project').value;
            const name = document.getElementById('wg-name').value.trim();
            const description = document.getElementById('wg-description').value.trim();
            
            if (!projectId) {{
                document.getElementById('wg-alert-container').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Please select a project
                    </div>
                `;
                return;
            }}
            
            if (!name || !description) {{
                document.getElementById('wg-alert-container').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Name and description are required
                    </div>
                `;
                return;
            }}
            
            const submitBtn = document.getElementById('submitWorkgroupBtn');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
            
            try {{
                const response = await fetch(`/api/layers/${{projectId}}/workgroups/`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ name, description }})
                }});
                
                const data = await response.json();
                
                if (response.ok) {{
                    modal.hide();
                    loadWorkgroups();
                    alert('Workgroup created successfully! It will be visible once approved by the layer admin.');
                }} else {{
                    throw new Error(data.error || 'Failed to create workgroup');
                }}
            }} catch (error) {{
                document.getElementById('wg-alert-container').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        ${{error.message}}
                    </div>
                `;
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Workgroup';
            }}
        }};
    }}
    
    loadProjects().then(() => {{
        loadWorkgroups();
        GhDirectory.bindControls('search-input', 'sort-filter', filterWorkgroups);
    }});
    </script>
    """
    
    return render_page("Workgroups Directory - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/votes/')
def votes_directory():
    """Votes directory: browse layers to find votes."""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    content = f"""
    {gh_page_open()}
    {gh_page_header('Votes', 'Votes and elections are organized by layer', 'fa-vote-yea', actions_html='<a href="/layers/" class="btn btn-primary btn-sm"><i class="fas fa-layer-group me-1"></i>Browse Layers</a>')}
    {gh_page_close()}
    """
    return render_page("Votes - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/artifacts/')
def artifacts_directory():
    """Artifacts directory: browse layers to find artifacts."""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    content = f"""
    {gh_page_open()}
    {gh_page_header('Artifacts', 'Proposals, evidence, and submissions organized by layer', 'fa-cube', actions_html='<a href="/layers/" class="btn btn-primary btn-sm"><i class="fas fa-layer-group me-1"></i>Browse Layers</a>')}
    {gh_page_close()}
    """
    return render_page("Artifacts - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/opportunities/')
def opportunities_directory():
    """Opportunities directory: browse layers to find opportunities."""
    from services.product_rollout import is_feature_enabled

    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    opp_blurb = (
        'Drafts needing support or opposition, open quests, and ways to contribute are organized by layer.'
        if is_feature_enabled('quests')
        else 'Drafts needing support or opposition and ways to contribute are organized by layer.'
    )
    content = f"""
    {gh_page_open()}
    {gh_page_header('Opportunities', opp_blurb + ' Browse layers to find opportunities.', 'fa-bullseye', '<a href="/layers/" class="btn btn-primary"><i class="fas fa-layer-group me-2"></i>Browse Layers</a>')}
    {gh_page_close()}
    """
    return render_page("Opportunities - MLGH", content, theme=current_theme, user_menu=user_menu)


def build_waitlists_content(layer_slug=None):
    """Build waitlists directory HTML content. layer_slug: when set, show only that layer's waitlists and hide layer filter."""
    layer_obj = None
    if layer_slug:
        layer_obj = Layer.query.filter_by(slug=layer_slug).first()
    
    layer_scoped = layer_obj is not None
    layer_id_js = json.dumps(str(layer_obj.id)) if layer_obj else 'null'
    layer_name_esc = (layer_obj.name or layer_slug).replace("'", "\\'").replace('"', '&quot;') if layer_obj else ''
    
    layer_filter_html = '' if layer_scoped else gh_filter_col(
        'Layer',
        '<select id="project-filter" class="form-select" onchange="loadWaitlists()"><option value="">All Layers</option></select>',
    )
    
    layer_title_html = ''
    if layer_scoped:
        name_esc = (layer_obj.name or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        layer_title_html = f'<nav aria-label="breadcrumb"><ol class="breadcrumb mb-2"><li class="breadcrumb-item"><a href="/layer/{layer_obj.slug}/">{name_esc}</a></li><li class="breadcrumb-item active">Waitlists</li></ol></nav>'
    
    return f"""
    {gh_page_open()}
    {gh_page_header('Waitlists Directory', 'Join waitlists for upcoming projects, features, and opportunities', 'fa-list-alt', breadcrumb_html=layer_title_html)}
    {gh_filter_row(
        (layer_filter_html or '')
        + gh_filter_col('Status', '<select id="status-filter" class="form-select" onchange="loadWaitlists()"><option value="active" selected>Active</option><option value="">All</option><option value="upcoming">Upcoming</option><option value="closed">Closed</option></select>', 'col-md-3')
        + gh_directory_toolbar(search_placeholder='Search waitlists…', search_col='col-md-4', sort_col='col-md-2')
    )}
    {gh_directory_grid('waitlists-container')}
    {gh_page_close()}
    
    <script>
    let allWaitlists = [];
    let allProjects = [];
    const layerScopedId = {layer_id_js};
    
    async function loadProjects() {{
        if (layerScopedId) return;
        try {{
            const response = await fetch('/api/layers/?approval_status=approved');
            const data = await response.json();
            allProjects = data.layers || [];
            
            const select = document.getElementById('project-filter');
            if (select) {{
                allProjects.forEach(project => {{
                    const option = document.createElement('option');
                    option.value = project.id;
                    option.textContent = project.name;
                    select.appendChild(option);
                }});
            }}
        }} catch (error) {{
            console.error('Error loading projects:', error);
        }}
    }}
    
    function waitlistStatusFilter() {{
        const el = document.getElementById('status-filter');
        return el ? el.value : 'active';
    }}

    async function loadWaitlists() {{
        const projectFilter = layerScopedId ? layerScopedId : (document.getElementById('project-filter') ? document.getElementById('project-filter').value : '');
        const statusFilter = waitlistStatusFilter();
        
        try {{
            allWaitlists = [];
            
            if (projectFilter) {{
                const response = await fetch(`/api/layers/${{projectFilter}}/waitlists/`);
                const data = await response.json();
                allWaitlists = (data.waitlists || []).map(wl => ({{...wl, layer_name: (allProjects.find(p => p.id === wl.layer_id) || {{}}).name || ''}}));
            }} else {{
                for (const project of allProjects) {{
                    const response = await fetch(`/api/layers/${{project.id}}/waitlists/`);
                    const data = await response.json();
                    if (data.waitlists) {{
                        allWaitlists = allWaitlists.concat(data.waitlists.map(wl => ({{...wl, layer_name: project.name}})));
                    }}
                }}
            }}
            
            if (statusFilter) {{
                const now = new Date();
                allWaitlists = allWaitlists.filter(wl => {{
                    const startDate = new Date(wl.start_date);
                    const closingDate = wl.closing_date ? new Date(wl.closing_date) : null;
                    const isFull = wl.full === true || (wl.max_number && wl.count >= wl.max_number);
                    
                    if (statusFilter === 'active') {{
                        return wl.active && !wl.archived && wl.started !== false && wl.closed !== true && !isFull;
                    }} else if (statusFilter === 'upcoming') {{
                        return wl.active && !wl.archived && wl.started === false;
                    }} else if (statusFilter === 'closed') {{
                        return wl.closed === true || wl.archived || !wl.active;
                    }}
                    return true;
                }});
            }}
            
            if (layerScopedId && allProjects.length === 0) {{
                allProjects = [{{ id: layerScopedId, slug: {json.dumps(layer_obj.slug if layer_obj else "")}, name: {json.dumps(layer_name_esc)} }}];
            }}
            filterWaitlists();
        }} catch (error) {{
            console.error('Error loading waitlists:', error);
            document.getElementById('waitlists-container').innerHTML = GhDirectory.emptyState('Error loading waitlists', 'danger');
        }}
    }}
    
    function filterWaitlists() {{
        const items = GhDirectory.filterAndSort(allWaitlists, {{
            searchTerm: GhDirectory.getSearchValue('search-input'),
            sort: GhDirectory.getSortValue('sort-filter'),
            searchFields: ['name', 'description', 'slug', 'layer_name'],
            nameKey: 'name',
            dateKeys: ['created_at', 'start_date', 'updated_at'],
        }});
        displayWaitlists(items);
    }}
    
    function displayWaitlists(waitlists) {{
        const container = document.getElementById('waitlists-container');
        
        if (waitlists.length === 0) {{
            container.innerHTML = GhDirectory.emptyState('No waitlists found');
            return;
        }}
        
        let html = '';
        waitlists.forEach(wl => {{
            const project = allProjects.find(p => p.id === wl.layer_id) || (layerScopedId ? allProjects[0] : null);
            const startDate = wl.start_date ? new Date(wl.start_date) : null;
            const closingDate = wl.closing_date ? new Date(wl.closing_date) : null;
            const isFull = wl.full === true;
            const isUpcoming = wl.started === false;
            const isClosed = wl.closed === true || wl.archived || !wl.active;
            
            let statusBadge = '';
            let statusText = '';
            
            if (isClosed && !isFull) {{
                statusBadge = '<span class="badge bg-secondary">Closed</span>';
                statusText = wl.archived ? 'Archived' : (!wl.active ? 'Inactive' : (closingDate ? 'Closed ' + closingDate.toLocaleDateString() : 'This waitlist is closed'));
            }} else if (isUpcoming) {{
                statusBadge = '<span class="badge bg-info">Upcoming</span>';
                statusText = startDate ? ('Opens ' + startDate.toLocaleDateString()) : 'Not open yet';
            }} else if (isFull) {{
                statusBadge = '<span class="badge bg-warning">Full</span>';
                statusText = wl.max_number ? (wl.count + ' / ' + wl.max_number + ' spots filled') : (wl.count + ' members');
            }} else {{
                statusBadge = '<span class="badge bg-success">Active</span>';
                if (wl.max_number) {{
                    statusText = wl.count + ' / ' + wl.max_number + ' spots filled';
                }} else {{
                    statusText = wl.count + ' member' + (wl.count !== 1 ? 's' : '');
                }}
            }}
            const extraBadges = (wl.referrals ? '<span class="badge bg-primary ms-1"><i class="fas fa-users"></i> Referrals</span>' : '')
                + (wl.milestones ? '<span class="badge bg-info ms-1"><i class="fas fa-flag"></i> Milestones</span>' : '');
            const layerName = project ? project.name : 'Unknown Layer';
            html += GhDirectory.tile({{
                href: '/waitlists/' + wl.id + '/',
                title: wl.name,
                description: wl.description || 'No description',
                imageUrl: wl.image_url || '',
                icon: 'fa-list-alt',
                pulse: isClosed ? 'Closed' : (isUpcoming ? 'Upcoming' : (isFull ? 'Full' : 'Open')),
                badgesHtml: statusBadge + extraBadges,
                metaHtml: '<i class="fas fa-layer-group me-1"></i>' + GhDirectory.esc(layerName),
                footerHtml: statusText + ' · Created ' + new Date(wl.created_at).toLocaleDateString()
            }});
        }});
        
        container.innerHTML = html;
    }}
    
    (function initWaitlistStatusDefault() {{
        const statusEl = document.getElementById('status-filter');
        if (statusEl && !statusEl.value) statusEl.value = 'active';
    }})();

    loadProjects().then(() => {{
        loadWaitlists();
        GhDirectory.bindControls('search-input', 'sort-filter', filterWaitlists);
    }});
    </script>
    """


@bp.route('/waitlists/')
def waitlists_directory():
    """Waitlists directory page. When ?layer=slug, redirect to /layer/<slug>/waitlists/ for layer-centric nav."""
    from services.product_rollout import is_feature_enabled

    if not is_feature_enabled('waitlists'):
        from flask import abort
        abort(404)

    layer_slug = (request.args.get('layer') or '').strip()
    if layer_slug and Layer.query.filter_by(slug=layer_slug).first():
        return redirect(f"/layer/{layer_slug}/waitlists/")

    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    content = build_waitlists_content(None)
    return render_page("Waitlists Directory - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/guilds/')
def guilds_directory():
    """Guilds directory page"""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    
    guild_create = (
        '<a href="/guilds/create/" class="btn btn-primary"><i class="fas fa-plus me-2"></i>Create Guild</a>'
        if current_user
        else '<a href="/login/" class="btn btn-primary"><i class="fas fa-sign-in-alt me-2"></i>Login to Create</a>'
    )
    content = f"""
    {gh_page_open()}
    {gh_page_header('Guilds Directory', 'Cross-project collaboration groups', 'fa-shield-halved', guild_create)}
    {gh_filter_row(
        gh_filter_col('Status', '<select id="status-filter" class="form-select" onchange="loadGuilds()"><option value="">All Statuses</option><option value="active" selected>Active</option><option value="archived">Archived</option></select>', 'col-md-3')
        + gh_directory_toolbar(search_placeholder='Search guilds…', search_col='col-md-5', sort_col='col-md-2')
    )}
    {gh_directory_grid('guilds-container')}
    {gh_page_close()}
    
    <script>
    let allGuilds = [];
    
    async function loadGuilds() {{
        const statusFilter = document.getElementById('status-filter').value;
        
        let url = '/api/guilds/';
        if (statusFilter) url += `?status=${{statusFilter}}`;
        
        try {{
            const response = await fetch(url);
            const data = await response.json();
            allGuilds = data.guilds;
            filterGuilds();
        }} catch (error) {{
            console.error('Error loading guilds:', error);
            document.getElementById('guilds-container').innerHTML = GhDirectory.emptyState('Error loading guilds', 'danger');
        }}
    }}
    
    function filterGuilds() {{
        const items = GhDirectory.filterAndSort(allGuilds, {{
            searchTerm: GhDirectory.getSearchValue('search-input'),
            sort: GhDirectory.getSortValue('sort-filter'),
            searchFields: ['name', 'description', 'slug'],
            nameKey: 'name',
            dateKeys: ['updated_at', 'created_at'],
        }});
        displayGuilds(items);
    }}
    
    function displayGuilds(guilds) {{
        const container = document.getElementById('guilds-container');
        
        if (guilds.length === 0) {{
            container.innerHTML = GhDirectory.emptyState('No guilds found');
            return;
        }}
        
        let html = '';
        guilds.forEach(guild => {{
            const statusBadge = guild.status === 'active'
                ? '<span class="badge bg-success">Active</span>'
                : '<span class="badge bg-secondary">Archived</span>';
            html += GhDirectory.tile({{
                href: '/guilds/' + guild.slug + '/',
                title: guild.name,
                description: guild.description || 'No description',
                imageUrl: guild.image_url || '',
                icon: 'fa-shield-halved',
                pulse: guild.status === 'active' ? 'Active' : 'Archived',
                badgesHtml: statusBadge,
                metaHtml: '<i class="fas fa-users me-1"></i>' + (guild.members_count || 0) + ' members',
                footerHtml: 'Created ' + new Date(guild.created_at).toLocaleDateString()
            }});
        }});
        
        container.innerHTML = html;
    }}
    
    // Load guilds on page load
    loadGuilds();
    GhDirectory.bindControls('search-input', 'sort-filter', filterGuilds);
    </script>
    """
    return render_page("Guilds Directory - MLGH", content, theme=current_theme, user_menu=user_menu)
