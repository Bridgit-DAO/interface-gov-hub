"""Workgroup page routes: /workgroups/<workgroup_slug>/."""
from flask import Blueprint, session

from services.identity import get_current_user

bp = Blueprint('workgroups_pages', __name__, url_prefix='')


def _get_imports():
    """Late imports from main app to avoid circular imports."""
    from services.rendering import render_page, generate_user_menu
    return render_page, generate_user_menu


@bp.route('/workgroups/<workgroup_slug>/')
def workgroup_detail(workgroup_slug):
    """Workgroup detail page"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    content = f"""
    <div class="gh-page container mt-4">
        <div id="workgroup-header" class="gh-detail-hero mb-0">
            <div class="d-flex justify-content-center py-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>

        <div class="gh-detail-layout mt-4">
            <div class="gh-detail-main">
                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-align-left"></i></div>
                        <h5 class="living-module-title">About</h5>
                    </div>
                    <div class="living-module-body" id="workgroup-about">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-star"></i></div>
                        <h5 class="living-module-title">Chairs / Coordinators</h5>
                        {'<button class="btn btn-sm btn-success ms-auto" onclick="nominateForChair()" id="nominate-btn" style="display:none;"><i class="fas fa-star me-1"></i>Nominate</button>' if current_user else ''}
                    </div>
                    <div class="living-module-body" id="workgroup-chairs">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-users"></i></div>
                        <h5 class="living-module-title">Members</h5>
                        {'<button class="btn btn-sm btn-primary ms-auto" onclick="joinWorkgroup()" id="join-btn" style="display:none;"><i class="fas fa-user-plus me-1"></i>Join</button>' if current_user else ''}
                    </div>
                    <div class="living-module-body" id="workgroup-members">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>
            </div>

            <div class="gh-detail-sidebar">
                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-info-circle"></i></div>
                        <h5 class="living-module-title">Details</h5>
                    </div>
                    <div class="living-module-body" id="workgroup-details">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="living-module">
                    <div class="living-module-header">
                        <div class="living-module-icon"><i class="fas fa-scroll"></i></div>
                        <h5 class="living-module-title">Charter & Goals</h5>
                    </div>
                    <div class="living-module-body" id="workgroup-charter">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Chair Nomination Modal -->
    <div class="modal fade" id="nominateChairModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Nominate for Chair/Coordinator</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="nominateChairForm">
                        <div class="mb-3">
                            <label class="form-label">Workgroup</label>
                            <p class="form-control-plaintext" id="modal-workgroup-name"></p>
                        </div>
                        <div class="mb-3">
                            <label for="nomination-statement" class="form-label">Statement <span class="text-danger">*</span></label>
                            <textarea
                                class="form-control"
                                id="nomination-statement"
                                rows="4"
                                required
                                placeholder="Explain why you would be a good chair/coordinator for this workgroup..."
                            ></textarea>
                            <div class="form-text">Share your relevant experience, vision, and commitment to leading this workgroup.</div>
                        </div>
                        <div class="alert alert-info">
                            <i class="fas fa-info-circle me-2"></i>
                            Your nomination will be reviewed by layer administrators and workgroup coordinators.
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-success" onclick="submitChairNomination()">
                        <i class="fas fa-paper-plane me-2"></i>Submit Nomination
                    </button>
                </div>
            </div>
        </div>
    </div>

    <script>
    let workgroup = null;
    let project = null;
    const workgroupSlug = '{workgroup_slug}';
    const isAuthenticated = {'true' if current_user else 'false'};

    async function loadWorkgroup() {{
        try {{
            // Load all projects first to find the workgroup
            const projectsResp = await fetch('/api/layers/');
            const projectsData = await projectsResp.json();

            // Search for workgroup across all projects
            for (const proj of projectsData.layers) {{
                const wgResp = await fetch(`/api/layers/${{proj.id}}/workgroups/`);
                const wgData = await wgResp.json();
                const found = wgData.workgroups.find(wg => wg.slug === workgroupSlug);

                if (found) {{
                    workgroup = found;
                    project = proj;
                    break;
                }}
            }}

            if (!workgroup) {{
                document.getElementById('workgroup-header').innerHTML = '<div class="alert alert-danger">Workgroup not found</div>';
                return;
            }}

            // Load full workgroup details
            const detailResp = await fetch(`/api/workgroups/${{workgroup.id}}/`);
            workgroup = await detailResp.json();

            displayWorkgroupHeader();
            displayWorkgroupAbout();
            displayWorkgroupCharter();
            displayWorkgroupDetails();
            loadChairs();
            loadMembers();
        }} catch (error) {{
            console.error('Error loading workgroup:', error);
            document.getElementById('workgroup-header').innerHTML = '<div class="alert alert-danger">Error loading workgroup</div>';
        }}
    }}

    function displayWorkgroupHeader() {{
        const statusBadge = getStatusBadge(workgroup.status);
        const approvalBadge = getApprovalBadge(workgroup.approval_status);
        const projectSlug = project ? project.slug : '';
        const projectName = project ? project.name : (workgroup.layer_name || 'Layer');
        const bc = '<nav aria-label="breadcrumb" class="gh-detail-breadcrumb"><ol class="breadcrumb">' +
            '<li class="breadcrumb-item"><a href="/layers/">Layers</a></li>' +
            (projectSlug ? '<li class="breadcrumb-item"><a href="/layers/' + projectSlug + '/">' + projectName + '</a></li>' : '<li class="breadcrumb-item">' + projectName + '</li>') +
            '<li class="breadcrumb-item active">' + (workgroup.name || '') + '</li></ol></nav>';
        const mediaHtml = workgroup.image_url
            ? '<div class="gh-detail-hero-media"><img src="' + workgroup.image_url + '" alt=""></div>'
            : '<div class="gh-detail-hero-media"><i class="fas fa-users-cog fa-2x text-muted opacity-50"></i></div>';
        const backBtn = projectSlug
            ? '<a href="/layers/' + projectSlug + '/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-2"></i>Back</a>'
            : '<a href="/workgroups/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-arrow-left me-2"></i>Back</a>';
        document.getElementById('workgroup-header').innerHTML =
            '<div class="gh-detail-hero-inner">' +
                mediaHtml +
                '<div class="gh-detail-hero-body flex-grow-1">' +
                    bc +
                    '<h1>' + (workgroup.name || '') + '</h1>' +
                    '<div class="mb-0">' + statusBadge + ' ' + approvalBadge + '</div>' +
                '</div>' +
                '<div class="gh-detail-hero-actions">' +
                    (workgroup.can_edit ? '<button type="button" class="btn btn-secondary btn-sm" onclick="editWorkgroup()"><i class="fas fa-edit me-2"></i>Edit</button>' : '') +
                    backBtn +
                '</div>' +
            '</div>';
    }}

    function displayWorkgroupAbout() {{
        document.getElementById('workgroup-about').innerHTML = `
            <p>${{workgroup.description || 'No description provided'}}</p>
        `;
    }}

    function displayWorkgroupCharter() {{
        let html = '';
        if (workgroup.charter) {{
            html = `<p>${{workgroup.charter}}</p>`;
        }} else {{
            html = '<p class="text-muted">No charter defined yet</p>';
        }}

        if (workgroup.goals) {{
            html += '<h6 class="mt-3">Goals</h6>';
            html += `<p>${{workgroup.goals}}</p>`;
        }}

        document.getElementById('workgroup-charter').innerHTML = html;
    }}

    function displayWorkgroupDetails() {{
        const projectSlug = project ? project.slug : '';
        const projectName = project ? project.name : (workgroup.layer_name || 'Unknown Project');

        document.getElementById('workgroup-details').innerHTML = `
            <p><strong>Layer:</strong> ${{projectSlug ? `<a href="/layers/${{projectSlug}}/">${{projectName}}</a>` : projectName}}</p>
            <p><strong>Status:</strong> ${{workgroup.status}}</p>
            <p><strong>Approval:</strong> ${{workgroup.approval_status}}</p>
            <p><strong>Created:</strong> ${{new Date(workgroup.created_at).toLocaleDateString()}}</p>
            ${{workgroup.coordinator_name ? `<p><strong>Coordinator:</strong> ${{workgroup.coordinator_name}}</p>` : ''}}
        `;
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

    async function loadChairs() {{
        try {{
            // Load chairs from working_group_chair table using acronym
            const response = await fetch(`/api/workgroups/${{workgroup.id}}/chairs/`);
            const data = await response.json();

            // Check if current user is already a chair
            const currentUserId = {current_user['id'] if current_user else 'null'};
            let isCurrentUserChair = false;
            if (isAuthenticated && data.chairs) {{
                isCurrentUserChair = data.chairs.some(c => c.user_id === currentUserId);
            }}

            // Show/hide nominate button (only if user is a member and not already a chair)
            const nominateBtn = document.getElementById('nominate-btn');
            if (nominateBtn) {{
                // We'll check membership status from the members list
                if (isAuthenticated && !isCurrentUserChair && workgroup.approval_status === 'approved') {{
                    nominateBtn.style.display = 'block';
                }} else {{
                    nominateBtn.style.display = 'none';
                }}
            }}

            let html = '';
            if (data.chairs && data.chairs.length > 0) {{
                html = '<div class="list-group">';
                data.chairs.forEach(chair => {{
                    html += `
                        <div class="list-group-item">
                            <div class="d-flex justify-content-between align-items-center">
                                <div>
                                    <strong>${{chair.chair_name}}</strong>
                                    ${{chair.approved ? '<span class="badge bg-success ms-2">Approved</span>' : '<span class="badge bg-warning ms-2">Pending</span>'}}
                                </div>
                            </div>
                        </div>
                    `;
                }});
                html += '</div>';
            }} else {{
                html = '<p class="text-muted">No chairs assigned yet</p>';
            }}

            document.getElementById('workgroup-chairs').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading chairs:', error);
            document.getElementById('workgroup-chairs').innerHTML = '<p class="text-muted">No chairs assigned yet</p>';
        }}
    }}

    async function loadMembers() {{
        try {{
            // Load members from working_group_member table using acronym
            const response = await fetch(`/api/workgroups/${{workgroup.id}}/members/`);
            const data = await response.json();

            // Check if current user is already a member
            const currentUserId = {current_user['id'] if current_user else 'null'};
            let isCurrentUserMember = false;
            if (isAuthenticated && data.members) {{
                isCurrentUserMember = data.members.some(m => m.user_id === currentUserId);
            }}

            // Show/hide join button
            const joinBtn = document.getElementById('join-btn');
            if (joinBtn) {{
                if (isAuthenticated && !isCurrentUserMember && workgroup.approval_status === 'approved') {{
                    joinBtn.style.display = 'block';
                }} else {{
                    joinBtn.style.display = 'none';
                }}
            }}

            let html = '';
            if (data.members && data.members.length > 0) {{
                html = `<p class="text-muted mb-2">${{data.members.length}} member(s)</p>`;
                html += '<div class="list-group">';
                data.members.forEach(member => {{
                    html += `
                        <div class="list-group-item">
                            <strong>${{member.user_name}}</strong>
                            <small class="text-muted d-block">Joined: ${{new Date(member.joined_at).toLocaleDateString()}}</small>
                        </div>
                    `;
                }});
                html += '</div>';
            }} else {{
                html = '<p class="text-muted">No members yet</p>';
            }}

            document.getElementById('workgroup-members').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading members:', error);
            document.getElementById('workgroup-members').innerHTML = '<p class="text-muted">No members yet</p>';
        }}
    }}

    async function joinWorkgroup() {{
        if (!isAuthenticated) {{
            alert('Please sign in to join this workgroup');
            return;
        }}

        if (!confirm('Join this workgroup?')) {{
            return;
        }}

        try {{
            const response = await fetch(`/api/workgroups/${{workgroup.id}}/join/`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }}
            }});

            const data = await response.json();

            if (response.ok) {{
                alert('Successfully joined workgroup!');
                loadMembers(); // Reload members list
            }} else {{
                alert(data.error || 'Failed to join workgroup');
            }}
        }} catch (error) {{
            console.error('Error joining workgroup:', error);
            alert('Failed to join workgroup');
        }}
    }}

    function nominateForChair() {{
        if (!isAuthenticated) {{
            alert('Please sign in to nominate yourself for chair');
            return;
        }}

        // Populate modal
        document.getElementById('modal-workgroup-name').textContent = workgroup.name;
        document.getElementById('nomination-statement').value = '';

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('nominateChairModal'));
        modal.show();
    }}

    async function submitChairNomination() {{
        const statement = document.getElementById('nomination-statement').value.trim();

        if (!statement) {{
            alert('Please provide a statement for your nomination');
            return;
        }}

        try {{
            const response = await fetch(`/api/workgroups/${{workgroup.id}}/nominate-chair/`, {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ statement: statement }})
            }});

            const data = await response.json();

            if (response.ok) {{
                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('nominateChairModal'));
                modal.hide();

                alert('Chair nomination submitted! It will require approval.');
                loadChairs(); // Reload chairs list
            }} else {{
                alert(data.error || 'Failed to nominate for chair');
            }}
        }} catch (error) {{
            console.error('Error nominating for chair:', error);
            alert('Failed to nominate for chair');
        }}
    }}

    async function uploadWorkgroupImage() {{
        const fileInput = document.getElementById('edit-wg-image-file');
        const statusEl = document.getElementById('edit-wg-image-upload-status');
        const urlInput = document.getElementById('edit-wg-image-url');

        if (!fileInput.files || !fileInput.files[0]) {{
            statusEl.innerHTML = '<small class="text-danger">Please select a file first</small>';
            return;
        }}

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('entity_type', 'workgroup');

        statusEl.innerHTML = '<small class="text-info"><i class="fas fa-spinner fa-spin"></i> Uploading...</small>';

        try {{
            const response = await fetch('/api/upload/entity-image', {{
                method: 'POST',
                credentials: 'include',
                body: formData
            }});

            const data = await response.json();

            if (response.ok && data.image_url) {{
                urlInput.value = data.image_url;
                statusEl.innerHTML = '<small class="text-success"><i class="fas fa-check"></i> Uploaded successfully</small>';
                fileInput.value = '';
            }} else {{
                statusEl.innerHTML = `<small class="text-danger">${{data.error || 'Upload failed'}}</small>`;
            }}
        }} catch (error) {{
            console.error('Upload error:', error);
            statusEl.innerHTML = '<small class="text-danger">Upload failed. Please try again.</small>';
        }}
    }}

    function editWorkgroup() {{
        const modalHtml = `
            <div class="modal fade" id="editWorkgroupModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Edit Workgroup</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="edit-workgroup-alert-container"></div>
                            <form id="editWorkgroupForm">
                                <div class="mb-3">
                                    <label for="edit-wg-name" class="form-label">Name *</label>
                                    <input type="text" class="form-control" id="edit-wg-name" required>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-description" class="form-label">Description</label>
                                    <textarea class="form-control" id="edit-wg-description" rows="3"></textarea>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-image-url" class="form-label">Image (optional)</label>
                                    <input type="url" class="form-control mb-2" id="edit-wg-image-url" placeholder="https://example.com/image.png or upload below">
                                    <div class="input-group">
                                        <input type="file" class="form-control" id="edit-wg-image-file" accept="image/*">
                                        <button class="btn btn-outline-primary" type="button" onclick="uploadWorkgroupImage()">
                                            <i class="fas fa-upload"></i> Upload
                                        </button>
                                    </div>
                                    <div class="form-text">Workgroup logo or banner. Max 600×600px, 5MB. Upload or paste URL above.</div>
                                    <div id="edit-wg-image-upload-status" class="mt-1"></div>
                                </div>
                                <div class="mb-3">
                                    <label for="edit-wg-status" class="form-label">Status</label>
                                    <select class="form-select" id="edit-wg-status">
                                        <option value="active">Active</option>
                                        <option value="inactive">Inactive</option>
                                        <option value="completed">Completed</option>
                                        <option value="archived">Archived</option>
                                    </select>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="editWorkgroupSubmitBtn">
                                <i class="fas fa-save me-2"></i>Save Changes
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        if (!document.getElementById('editWorkgroupModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        document.getElementById('edit-wg-name').value = workgroup.name || '';
        document.getElementById('edit-wg-description').value = workgroup.description || '';
        const wgImgEl = document.getElementById('edit-wg-image-url');
        if (wgImgEl) wgImgEl.value = workgroup.image_url || '';
        const wgImgFileEl = document.getElementById('edit-wg-image-file');
        if (wgImgFileEl) wgImgFileEl.value = '';
        const wgImgStatusEl = document.getElementById('edit-wg-image-upload-status');
        if (wgImgStatusEl) wgImgStatusEl.innerHTML = '';
        document.getElementById('edit-wg-status').value = workgroup.status || 'active';
        document.getElementById('edit-workgroup-alert-container').innerHTML = '';
        const modal = new bootstrap.Modal(document.getElementById('editWorkgroupModal'));
        modal.show();
        document.getElementById('editWorkgroupSubmitBtn').onclick = async () => {{
            const name = document.getElementById('edit-wg-name').value.trim();
            const description = document.getElementById('edit-wg-description').value.trim();
            const image_url = document.getElementById('edit-wg-image-url') ? document.getElementById('edit-wg-image-url').value.trim() : '';
            const status = document.getElementById('edit-wg-status').value;
            if (!name) {{
                document.getElementById('edit-workgroup-alert-container').innerHTML = '<div class="alert alert-danger">Name is required.</div>';
                return;
            }}
            const btn = document.getElementById('editWorkgroupSubmitBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
            try {{
                const response = await fetch(`/api/workgroups/${{workgroup.id}}/`, {{
                    method: 'PATCH',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ name, description, image_url: image_url || null, status }})
                }});
                if (!response.ok) {{
                    const data = await response.json();
                    throw new Error(data.error || 'Failed to update workgroup');
                }}
                const data = await response.json();
                workgroup.name = data.workgroup.name;
                workgroup.description = data.workgroup.description;
                workgroup.image_url = data.workgroup.image_url || null;
                workgroup.status = data.workgroup.status;
                modal.hide();
                displayWorkgroupHeader();
                displayWorkgroupAbout();
                displayWorkgroupDetails();
            }} catch (err) {{
                document.getElementById('edit-workgroup-alert-container').innerHTML = '<div class="alert alert-danger">' + (err.message || 'Failed to update workgroup') + '</div>';
            }}
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-save me-2"></i>Save Changes';
        }};
    }}

    // Load workgroup on page load
    loadWorkgroup();
    </script>
    """

    return render_page(f"Workgroup: {workgroup_slug} - MLGH", content, theme=current_theme, user_menu=user_menu)
