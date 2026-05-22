"""Directory pages: person, meeting, layers, workgroups, waitlists, guilds."""
import json
from flask import Blueprint, redirect, request, session

from models import (
    User, Submission, Comment, Layer,
    WorkingGroupChair, WorkingGroupMember,
)
from services.identity import get_current_user
from services.avatar import get_avatar_url
from services.event_subscriptions import count_distinct_drafts_followed

bp = Blueprint('directory', __name__, url_prefix='')


def _get_imports():
    """Late imports to avoid circular imports."""
    from services.rendering import generate_user_menu, render_page
    from services.groups import GROUPS
    return generate_user_menu, render_page, GROUPS


@bp.route('/person/')
def people():
    """People directory: list users; admins get Add as coordinator and other actions."""
    generate_user_menu, render_page, GROUPS = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    is_admin = current_user and current_user.get('role') == 'admin'
    is_editor_or_admin = current_user and current_user.get('role') in ('admin', 'editor')

    users = User.query.order_by(User.username).all()
    group_options = ''.join(
        f'<option value="{g["acronym"]}">{g["acronym"]}</option>' for g in GROUPS
    )
    rows = []
    for u in users:
        display = u.name or u.displayName or u.oauthName or u.username
        coord_groups = WorkingGroupChair.query.filter_by(user_id=u.id).all()
        coord_acronyms = ' '.join(c.group_acronym for c in coord_groups)
        coord_badges = ' '.join(
            f'<span class="badge bg-secondary me-1">{c.group_acronym}</span>'
            for c in coord_groups
        ) if coord_groups else '<span class="text-muted">—</span>'
        member_groups = WorkingGroupMember.query.filter_by(user_id=u.id).all()
        member_acronyms = ' '.join(m.group_acronym for m in member_groups)
        member_badges = ' '.join(
            f'<span class="badge bg-info me-1">{m.group_acronym}</span>'
            for m in member_groups
        ) if member_groups else '<span class="text-muted">—</span>'
        all_groups = (member_acronyms + ' ' + coord_acronyms).strip() or ''
        role_badge = f'<span class="badge bg-{"danger" if u.role == "admin" else "warning" if u.role == "editor" else "secondary"}">{u.role or "user"}</span>'
        if u.last_login:
            last_active = u.last_login.strftime('%Y-%m-%d')
        else:
            last_active = '<span class="text-muted">Never</span>'
        name_variants = [x for x in (u.name, u.displayName, u.oauthName, u.username) if x]
        submissions_count = Submission.query.filter(Submission.submitted_by.in_(name_variants)).count() if name_variants else 0
        follows_count = count_distinct_drafts_followed(u.id)
        comments_count = Comment.query.filter(Comment.author.in_(name_variants)).count() if name_variants else 0
        if is_admin:
            actions_td = f'<td><a href="/admin/users/{u.id}/add-coordinator" class="btn btn-outline-primary btn-sm">Add as coordinator</a></td>'
        else:
            actions_td = ''
        search_text = f"{display} {u.username}".lower()
        role_td = f'<td>{role_badge}</td>' if is_editor_or_admin else ''
        avatar_src = get_avatar_url(u, 36)
        avatar_html = f'<img src="{avatar_src}" alt="" class="rounded-circle me-2" style="width:36px;height:36px;object-fit:cover" onerror="this.onerror=null;this.src=\'/static/images/default-avatar.png\'">'
        profile_link = f'/profile/{u.username}/'
        rows.append(f"""
        <tr data-search="{search_text}" data-groups="{all_groups}">
            <td><div class="d-flex align-items-center">{avatar_html}<div><a href="{profile_link}" class="fw-bold text-decoration-none">{display}</a><br><small class="text-muted">@{u.username}</small></div></div></td>
            {role_td}
            <td>{member_badges}</td>
            <td>{coord_badges}</td>
            <td>{last_active}</td>
            <td>{submissions_count}</td>
            <td>{follows_count}</td>
            <td>{comments_count}</td>
            {actions_td}
        </tr>
        """)

    num_cols = 7 + (1 if is_editor_or_admin else 0) + (1 if is_admin else 0)
    table_rows = ''.join(rows) if rows else f'<tr><td colspan="{num_cols}" class="text-center text-muted py-4">No users yet.</td></tr>'
    role_th = '<th>Role</th>' if is_editor_or_admin else ''
    actions_th = '<th>Actions</th>' if is_admin else ''
    content = f"""
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item active">People</li>
            </ol>
        </nav>
        <h1 class="mb-2">People</h1>
        <p class="text-muted mb-4">Directory of MLGH participants. Member and coordinator workgroups and activity at a glance.</p>
        <div class="card">
            <div class="card-body">
                <div class="row g-2 mb-3">
                    <div class="col-md-6">
                        <label class="form-label small text-muted mb-0">Search</label>
                        <input type="text" id="people-search" class="form-control" placeholder="Type to search by name or username..." autocomplete="off">
                    </div>
                    <div class="col-md-4">
                        <label class="form-label small text-muted mb-0">Workgroup</label>
                        <select id="people-workgroup" class="form-select">
                            <option value="">All workgroups</option>
                            {group_options}
                        </select>
                    </div>
                </div>
            </div>
            <div class="card-body p-0 pt-0">
                <div class="table-responsive">
                    <table class="table table-hover mb-0" id="people-table">
                        <thead class="table-light">
                            <tr>
                                <th>Name</th>
                                {role_th}
                                <th>Member</th>
                                <th>Coordinator</th>
                                <th>Last active</th>
                                <th>Submissions</th>
                                <th>Documents followed</th>
                                <th>Comments</th>
                                {actions_th}
                            </tr>
                        </thead>
                        <tbody>{table_rows}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    <script>
    (function() {{
        var searchEl = document.getElementById('people-search');
        var workgroupEl = document.getElementById('people-workgroup');
        var rows = document.querySelectorAll('#people-table tbody tr[data-search]');
        function filterPeople() {{
            var q = (searchEl && searchEl.value) ? searchEl.value.toLowerCase().trim() : '';
            var group = (workgroupEl && workgroupEl.value) ? workgroupEl.value.trim() : '';
            rows.forEach(function(tr) {{
                var show = true;
                if (q && tr.getAttribute('data-search').indexOf(q) === -1) show = false;
                if (group) {{
                    var groups = (tr.getAttribute('data-groups') || '').split(/\\s+/).filter(Boolean);
                    if (groups.indexOf(group) === -1) show = false;
                }}
                tr.style.display = show ? '' : 'none';
            }});
        }}
        if (searchEl) searchEl.addEventListener('input', filterPeople);
        if (searchEl) searchEl.addEventListener('keyup', filterPeople);
        if (workgroupEl) workgroupEl.addEventListener('change', filterPeople);
    }})();
    </script>
    """
    return render_page("People - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/meeting/')
def meetings():
    """Meetings - coming soon"""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()

    content = """
    <div class="container mt-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="text-center">
                    <i class="fas fa-calendar fa-4x text-muted mb-4"></i>
                    <h1 class="mb-3">Meetings</h1>
                    <p class="lead text-muted mb-4">Coming Soon</p>
                    <p class="mb-4">Information about upcoming MLGH meetings and sessions will be available here. Stay tuned for announcements about our first events.</p>
                    <a href="/" class="btn btn-primary">Return to Home</a>
                </div>
            </div>
        </div>
    </div>
    """
    return render_page("Meetings - MLGH", content, theme=session.get('theme', 'dark'), user_menu=user_menu)


@bp.route('/layers/')
def projects_directory():
    """Projects directory page"""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    content = f"""
    <div class="container-fluid container-lg mt-3 mt-md-4 px-3 px-md-4">
        <div class="row mb-3 mb-md-4 align-items-center">
            <div class="col-12 col-md-8 mb-2 mb-md-0">
                <h1 class="h4 h2-md mb-1">Layers Map</h1>
                <p class="lead mb-0 small text-muted">Discover layers — status, activity, and community at a glance</p>
            </div>
            <div class="col-12 col-md-4 text-md-end">
                {'<a href="/layers/create/" class="btn btn-primary w-100 w-md-auto"><i class="fas fa-plus me-2"></i>Create Layer</a>' if current_user else '<a href="/login/" class="btn btn-primary w-100 w-md-auto"><i class="fas fa-sign-in-alt me-2"></i>Login to Create</a>'}
            </div>
        </div>
        <div class="row g-3 mb-4">
            <div class="col-12 col-sm-6 col-lg-4">
                <label for="status-filter" class="form-label">Status:</label>
                <select id="status-filter" class="form-select" onchange="loadProjects()">
                    <option value="">All Statuses</option>
                    <option value="proposed">Proposed</option>
                    <option value="active">Active</option>
                    <option value="stabilizing">Stabilizing</option>
                    <option value="maintaining">Maintaining</option>
                    <option value="dormant">Dormant</option>
                    <option value="concluded">Concluded</option>
                    <option value="archived">Archived</option>
                </select>
            </div>
            <div class="col-md-4">
                <label for="approval-filter" class="form-label">Approval:</label>
                <select id="approval-filter" class="form-select" onchange="loadProjects()">
                    <option value="">All</option>
                    <option value="pending">Pending</option>
                    <option value="approved">Approved</option>
                    <option value="rejected">Rejected</option>
                </select>
            </div>
            <div class="col-md-4">
                <label for="search-input" class="form-label">Search:</label>
                <input type="text" id="search-input" class="form-control" placeholder="Search layers..." onkeyup="filterProjects()">
            </div>
        </div>
        <div id="projects-container" class="row row-cols-2 row-cols-sm-3 row-cols-md-4 row-cols-lg-5 row-cols-xl-6 g-3">
            <div class="col-12 text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>
    </div>
    <script>
    let allProjects = [];
    async function loadProjects() {{
        const statusFilter = document.getElementById('status-filter').value;
        const approvalFilter = document.getElementById('approval-filter').value;
        let url = '/api/layers/';
        const params = new URLSearchParams();
        if (statusFilter) params.append('status', statusFilter);
        if (approvalFilter) params.append('approval_status', approvalFilter);
        if (params.toString()) url += '?' + params.toString();
        try {{
            const response = await fetch(url);
            const data = await response.json();
            allProjects = data.layers;
            displayProjects(allProjects);
        }} catch (error) {{
            console.error('Error loading projects:', error);
            document.getElementById('projects-container').innerHTML = '<div class="col-12"><div class="alert alert-danger">Error loading projects</div></div>';
        }}
    }}
    function filterProjects() {{
        const searchTerm = document.getElementById('search-input').value.toLowerCase();
        const filtered = allProjects.filter(p => {{
            const blob = (p.name + ' ' + (p.description || '') + ' ' + (p.mission || '')).toLowerCase();
            return blob.includes(searchTerm);
        }});
        displayProjects(filtered);
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
            container.innerHTML = '<div class="col-12"><div class="alert alert-info">No projects found</div></div>';
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
    
    content = f"""
    <div class="container mt-4">
        <div class="row mb-4">
            <div class="col-md-8">
                <h1>Workgroups Directory</h1>
                <p class="lead">Browse workgroups across all projects</p>
            </div>
            <div class="col-md-4 text-end">
                <a href="/layers/" class="btn btn-secondary mb-2 w-100"><i class="fas fa-arrow-left me-2"></i>Back to Layers</a>
                {'<button class="btn btn-primary w-100" onclick="showCreateWorkgroupModal()"><i class="fas fa-plus me-2"></i>Create Workgroup</button>' if current_user else ''}
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-md-4">
                <label for="project-filter" class="form-label">Layer:</label>
                <select id="project-filter" class="form-select" onchange="loadWorkgroups()">
                    <option value="">All Layers</option>
                </select>
            </div>
            <div class="col-md-4">
                <label for="status-filter" class="form-label">Status:</label>
                <select id="status-filter" class="form-select" onchange="loadWorkgroups()">
                    <option value="">All Statuses</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="completed">Completed</option>
                    <option value="archived">Archived</option>
                </select>
            </div>
            <div class="col-md-4">
                <label for="search-input" class="form-label">Search:</label>
                <input type="text" id="search-input" class="form-control" placeholder="Search workgroups..." onkeyup="filterWorkgroups()">
            </div>
        </div>
        
        <div id="workgroups-container" class="row">
            <div class="col-12 text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>
    </div>
    
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
                allWorkgroups = data.workgroups;
            }} else {{
                // Load workgroups from all projects
                for (const project of allProjects) {{
                    let url = `/api/layers/${{project.id}}/workgroups/`;
                    if (statusFilter) url += `?status=${{statusFilter}}`;
                    
                    const response = await fetch(url);
                    const data = await response.json();
                    allWorkgroups = allWorkgroups.concat(data.workgroups);
                }}
            }}
            
            displayWorkgroups(allWorkgroups);
        }} catch (error) {{
            console.error('Error loading workgroups:', error);
            document.getElementById('workgroups-container').innerHTML = '<div class="col-12"><div class="alert alert-danger">Error loading workgroups</div></div>';
        }}
    }}
    
    function filterWorkgroups() {{
        const searchTerm = document.getElementById('search-input').value.toLowerCase();
        const filtered = allWorkgroups.filter(wg => 
            wg.name.toLowerCase().includes(searchTerm) ||
            (wg.description && wg.description.toLowerCase().includes(searchTerm))
        );
        displayWorkgroups(filtered);
    }}
    
    function displayWorkgroups(workgroups) {{
        const container = document.getElementById('workgroups-container');
        
        if (workgroups.length === 0) {{
            container.innerHTML = '<div class="col-12"><div class="alert alert-info">No workgroups found</div></div>';
            return;
        }}
        
        let html = '';
        workgroups.forEach(wg => {{
            const statusBadge = getStatusBadge(wg.status);
            const approvalBadge = getApprovalBadge(wg.approval_status);
            const project = allProjects.find(p => p.id === wg.layer_id);
            
            const wgImgHtml = wg.image_url ? `<div class="card-img-top overflow-hidden" style="height: 140px; background: var(--bg-secondary, #f8f9fa);"><img src="${{wg.image_url}}" alt="${{wg.name}}" class="w-100 h-100 object-fit-cover"></div>` : '';
            html += `
                <div class="col-md-6 col-lg-4 mb-4">
                    <div class="card h-100">
                        ${{wgImgHtml}}
                        <div class="card-body">
                            <h5 class="card-title">
                                <a href="/workgroups/${{wg.slug}}/">${{wg.name}}</a>
                            </h5>
                            <div class="mb-2">
                                ${{statusBadge}}
                                ${{approvalBadge}}
                            </div>
                            <p class="card-text text-muted">${{wg.description || 'No description'}}</p>
                            ${{project ? `<div class="mt-2"><small class="text-muted"><i class="fas fa-project-diagram me-1"></i> ${{project.name}}</small></div>` : ''}}
                        </div>
                        <div class="card-footer">
                            <small class="text-muted">Created ${{new Date(wg.created_at).toLocaleDateString()}}</small>
                        </div>
                    </div>
                </div>
            `;
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
    
    loadProjects().then(() => loadWorkgroups());
    </script>
    """
    
    return render_page("Workgroups Directory - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/votes/')
def votes_directory():
    """Votes directory: browse layers to find votes."""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    content = """
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item active">Votes</li>
            </ol>
        </nav>
        <h1 class="mb-2">Votes</h1>
        <p class="text-muted mb-4">Votes and elections are organized by layer. Browse layers to find active votes, ballots, and elections.</p>
        <a href="/layers/" class="btn btn-primary"><i class="fas fa-layer-group me-2"></i>Browse Layers</a>
    </div>
    """
    return render_page("Votes - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/artifacts/')
def artifacts_directory():
    """Artifacts directory: browse layers to find artifacts."""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    content = """
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item active">Artifacts</li>
            </ol>
        </nav>
        <h1 class="mb-2">Artifacts</h1>
        <p class="text-muted mb-4">Artifacts (proposals, evidence, submissions) are organized by layer. Browse layers to find artifacts.</p>
        <a href="/layers/" class="btn btn-primary"><i class="fas fa-layer-group me-2"></i>Browse Layers</a>
    </div>
    """
    return render_page("Artifacts - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/opportunities/')
def opportunities_directory():
    """Opportunities directory: browse layers to find opportunities."""
    generate_user_menu, render_page, _ = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    content = """
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item active">Opportunities</li>
            </ol>
        </nav>
        <h1 class="mb-2">Opportunities</h1>
        <p class="text-muted mb-4">Drafts needing support or opposition, open quests, and ways to contribute are organized by layer. Browse layers to find opportunities.</p>
        <a href="/layers/" class="btn btn-primary"><i class="fas fa-layer-group me-2"></i>Browse Layers</a>
    </div>
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
    
    layer_filter_html = '' if layer_scoped else """
            <div class="col-md-4">
                <label for="project-filter" class="form-label">Layer:</label>
                <select id="project-filter" class="form-select" onchange="loadWaitlists()">
                    <option value="">All Layers</option>
                </select>
            </div>"""
    
    layer_title_html = ''
    if layer_scoped:
        name_esc = (layer_obj.name or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
        layer_title_html = f'<nav aria-label="breadcrumb"><ol class="breadcrumb mb-2"><li class="breadcrumb-item"><a href="/layer/{layer_obj.slug}/">{name_esc}</a></li><li class="breadcrumb-item active">Waitlists</li></ol></nav>'
    
    return f"""
    <div class="container mt-4">
        <div class="row mb-4">
            <div class="col-md-8">
                {layer_title_html}
                <h1>Waitlists Directory</h1>
                <p class="lead">Join waitlists for upcoming projects, features, and opportunities</p>
            </div>
        </div>
        
        <div class="row mb-4">
            {layer_filter_html}
            <div class="col-md-4">
                <label for="status-filter" class="form-label">Status:</label>
                <select id="status-filter" class="form-select" onchange="loadWaitlists()">
                    <option value="">All</option>
                    <option value="active">Active</option>
                    <option value="upcoming">Upcoming</option>
                    <option value="closed">Closed</option>
                </select>
            </div>
            <div class="col-md-4">
                <label for="search-input" class="form-label">Search:</label>
                <input type="text" id="search-input" class="form-control" placeholder="Search waitlists..." onkeyup="filterWaitlists()">
            </div>
        </div>
        
        <div id="waitlists-container" class="row">
            <div class="col-12 text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>
    </div>
    
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
    
    async function loadWaitlists() {{
        const projectFilter = layerScopedId ? layerScopedId : (document.getElementById('project-filter') ? document.getElementById('project-filter').value : '');
        const statusFilter = document.getElementById('status-filter').value;
        
        try {{
            allWaitlists = [];
            
            if (projectFilter) {{
                const response = await fetch(`/api/layers/${{projectFilter}}/waitlists/`);
                const data = await response.json();
                allWaitlists = data.waitlists || [];
            }} else {{
                for (const project of allProjects) {{
                    const response = await fetch(`/api/layers/${{project.id}}/waitlists/`);
                    const data = await response.json();
                    if (data.waitlists) {{
                        allWaitlists = allWaitlists.concat(data.waitlists);
                    }}
                }}
            }}
            
            if (statusFilter) {{
                const now = new Date();
                allWaitlists = allWaitlists.filter(wl => {{
                    const startDate = new Date(wl.start_date);
                    const closingDate = wl.closing_date ? new Date(wl.closing_date) : null;
                    const isFull = wl.max_number && wl.entry_count >= wl.max_number;
                    
                    if (statusFilter === 'active') {{
                        return wl.active && !wl.archived && now >= startDate && (!closingDate || now <= closingDate) && !isFull;
                    }} else if (statusFilter === 'upcoming') {{
                        return wl.active && !wl.archived && now < startDate;
                    }} else if (statusFilter === 'closed') {{
                        return wl.archived || !wl.active || (closingDate && now > closingDate) || isFull;
                    }}
                    return true;
                }});
            }}
            
            if (layerScopedId && allProjects.length === 0) {{
                allProjects = [{{ id: layerScopedId, slug: {json.dumps(layer_obj.slug if layer_obj else "")}, name: {json.dumps(layer_name_esc)} }}];
            }}
            displayWaitlists(allWaitlists);
        }} catch (error) {{
            console.error('Error loading waitlists:', error);
            document.getElementById('waitlists-container').innerHTML = '<div class="col-12"><div class="alert alert-danger">Error loading waitlists</div></div>';
        }}
    }}
    
    function filterWaitlists() {{
        const searchTerm = document.getElementById('search-input').value.toLowerCase();
        const filtered = allWaitlists.filter(wl => 
            wl.name.toLowerCase().includes(searchTerm) ||
            (wl.description && wl.description.toLowerCase().includes(searchTerm))
        );
        displayWaitlists(filtered);
    }}
    
    function displayWaitlists(waitlists) {{
        const container = document.getElementById('waitlists-container');
        
        if (waitlists.length === 0) {{
            container.innerHTML = '<div class="col-12"><div class="alert alert-info">No waitlists found</div></div>';
            return;
        }}
        
        let html = '';
        waitlists.forEach(wl => {{
            const project = allProjects.find(p => p.id === wl.layer_id) || (layerScopedId ? allProjects[0] : null);
            const now = new Date();
            const startDate = new Date(wl.start_date);
            const closingDate = wl.closing_date ? new Date(wl.closing_date) : null;
            const isFull = wl.max_number && wl.count >= wl.max_number;
            
            let statusBadge = '';
            let statusText = '';
            
            if (!wl.active || wl.archived) {{
                statusBadge = '<span class="badge bg-secondary">Closed</span>';
                statusText = 'This waitlist is closed';
            }} else if (now < startDate) {{
                statusBadge = '<span class="badge bg-info">Upcoming</span>';
                statusText = `Opens ${{startDate.toLocaleDateString()}}`;
            }} else if (isFull) {{
                statusBadge = '<span class="badge bg-warning">Full</span>';
                statusText = `${{wl.count}} / ${{wl.max_number}} spots filled`;
            }} else if (closingDate && now > closingDate) {{
                statusBadge = '<span class="badge bg-secondary">Closed</span>';
                statusText = `Closed ${{closingDate.toLocaleDateString()}}`;
            }} else {{
                statusBadge = '<span class="badge bg-success">Active</span>';
                if (wl.max_number) {{
                    statusText = `${{wl.count}} / ${{wl.max_number}} spots filled`;
                }} else {{
                    statusText = `${{wl.count}} member${{wl.count !== 1 ? 's' : ''}}`;
                }}
            }}
            
            const imgHtml = wl.image_url ? `<div class="card-img-top overflow-hidden" style="height: 140px; background: var(--bg-secondary, #f8f9fa);"><img src="${{wl.image_url}}" alt="${{wl.name}}" class="w-100 h-100 object-fit-cover"></div>` : '';
            const layerLink = layerScopedId ? '<a href="/layer/{layer_obj.slug if layer_obj else ""}/">' + (project ? project.name : 'Layer') + '</a>' : '<a href="/layers/' + (project ? project.slug : wl.layer_id) + '/">' + (project ? project.name : 'Unknown Layer') + '</a>';
            html += `
                <div class="col-md-6 col-lg-4 mb-4">
                    <div class="card h-100">
                        ${{imgHtml}}
                        <div class="card-body">
                            <h5 class="card-title">
                                <a href="/waitlists/${{wl.id}}/">${{wl.name}}</a>
                            </h5>
                            <div class="mb-2">
                                ${{statusBadge}}
                                ${{wl.referrals ? '<span class="badge bg-primary ms-1"><i class="fas fa-users"></i> Referrals</span>' : ''}}
                                ${{wl.milestones ? '<span class="badge bg-info ms-1"><i class="fas fa-flag"></i> Milestones</span>' : ''}}
                            </div>
                            <p class="card-text text-muted small mb-2">
                                <i class="fas fa-project-diagram me-1"></i>
                                ${{layerLink}}
                            </p>
                            <p class="card-text">${{wl.description || 'No description'}}</p>
                            <div class="mt-3">
                                <small class="text-muted">${{statusText}}</small>
                            </div>
                        </div>
                        <div class="card-footer">
                            <small class="text-muted">Created ${{new Date(wl.created_at).toLocaleDateString()}}</small>
                        </div>
                    </div>
                </div>
            `;
        }});
        
        container.innerHTML = html;
    }}
    
    loadProjects().then(() => loadWaitlists());
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
    
    content = f"""
    <div class="container mt-4">
        <div class="row mb-4">
            <div class="col-md-8">
                <h1>Guilds Directory</h1>
                <p class="lead">Cross-project collaboration groups</p>
            </div>
            <div class="col-md-4 text-end">
                {'<a href="/guilds/create/" class="btn btn-primary"><i class="fas fa-plus me-2"></i>Create Guild</a>' if current_user else '<a href="/login/" class="btn btn-primary"><i class="fas fa-sign-in-alt me-2"></i>Login to Create</a>'}
            </div>
        </div>
        
        <div class="row mb-4">
            <div class="col-md-6">
                <label for="status-filter" class="form-label">Status:</label>
                <select id="status-filter" class="form-select" onchange="loadGuilds()">
                    <option value="">All Statuses</option>
                    <option value="active">Active</option>
                    <option value="archived">Archived</option>
                </select>
            </div>
            <div class="col-md-6">
                <label for="search-input" class="form-label">Search:</label>
                <input type="text" id="search-input" class="form-control" placeholder="Search guilds..." onkeyup="filterGuilds()">
            </div>
        </div>
        
        <div id="guilds-container" class="row">
            <div class="col-12 text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>
    </div>
    
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
            displayGuilds(allGuilds);
        }} catch (error) {{
            console.error('Error loading guilds:', error);
            document.getElementById('guilds-container').innerHTML = '<div class="col-12"><div class="alert alert-danger">Error loading guilds</div></div>';
        }}
    }}
    
    function filterGuilds() {{
        const searchTerm = document.getElementById('search-input').value.toLowerCase();
        const filtered = allGuilds.filter(g => 
            g.name.toLowerCase().includes(searchTerm) ||
            (g.description && g.description.toLowerCase().includes(searchTerm))
        );
        displayGuilds(filtered);
    }}
    
    function displayGuilds(guilds) {{
        const container = document.getElementById('guilds-container');
        
        if (guilds.length === 0) {{
            container.innerHTML = '<div class="col-12"><div class="alert alert-info">No guilds found</div></div>';
            return;
        }}
        
        let html = '';
        guilds.forEach(guild => {{
            const statusBadge = guild.status === 'active' 
                ? '<span class="badge bg-success">Active</span>' 
                : '<span class="badge bg-secondary">Archived</span>';
            
            const guildImgHtml = guild.image_url ? `<div class="card-img-top overflow-hidden" style="height: 140px; background: var(--bg-secondary, #f8f9fa);"><img src="${{guild.image_url}}" alt="${{guild.name}}" class="w-100 h-100 object-fit-cover"></div>` : '';
            html += `
                <div class="col-md-6 col-lg-4 mb-4">
                    <div class="card h-100">
                        ${{guildImgHtml}}
                        <div class="card-body">
                            <h5 class="card-title">
                                <a href="/guilds/${{guild.slug}}/">${{guild.name}}</a>
                            </h5>
                            <div class="mb-2">
                                ${{statusBadge}}
                            </div>
                            <p class="card-text text-muted">${{guild.description || 'No description'}}</p>
                            <div class="mt-3">
                                <small class="text-muted">
                                    <i class="fas fa-users me-1"></i> ${{guild.members_count || 0}} members
                                </small>
                            </div>
                        </div>
                        <div class="card-footer">
                            <small class="text-muted">Created ${{new Date(guild.created_at).toLocaleDateString()}}</small>
                        </div>
                    </div>
                </div>
            `;
        }});
        
        container.innerHTML = html;
    }}
    
    // Load guilds on page load
    loadGuilds();
    </script>
    """
    return render_page("Guilds Directory - MLGH", content, theme=current_theme, user_menu=user_menu)
