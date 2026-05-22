"""Guild page routes: /guilds/<guild_slug>/, /guilds/create/."""
import json

from flask import Blueprint, session

from services.identity import get_current_user, require_auth

bp = Blueprint('guilds_pages', __name__, url_prefix='')


def _get_imports():
    """Late imports from main app to avoid circular imports."""
    from services.rendering import render_page, generate_user_menu
    return render_page, generate_user_menu


@bp.route('/guilds/<guild_slug>/')
def guild_detail(guild_slug):
    """Guild detail page with members"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    content = f"""
    <div class="container mt-4">
        <div id="guild-header" class="mb-4">
            <div class="d-flex justify-content-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-8">
                <div class="card mb-4">
                    <div class="card-header"><h5>About</h5></div>
                    <div class="card-body" id="guild-about">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="card mb-4">
                    <div class="card-header"><h5>Members</h5></div>
                    <div class="card-body" id="guild-members">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="card mb-4">
                    <div class="card-header"><h5>Linked layers</h5></div>
                    <div class="card-body" id="guild-layer-links">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="card mb-4">
                    <div class="card-header"><h5>Linked quests</h5></div>
                    <div class="card-body" id="guild-quest-links">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="card mb-4">
                    <div class="card-header"><h5>Linked artifacts</h5></div>
                    <div class="card-body" id="guild-artifact-links">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>
            </div>

            <div class="col-md-4">
                <div class="card mb-4">
                    <div class="card-header"><h5>Quick Actions</h5></div>
                    <div class="card-body" id="guild-actions">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-header"><h5>Statistics</h5></div>
                    <div class="card-body" id="guild-stats">
                        <div class="spinner-border spinner-border-sm text-primary"></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
    let guild = null;
    const guildSlug = '{guild_slug}';
    const isAuthenticated = {'true' if current_user else 'false'};
    const currentUserId = {current_user['id'] if current_user else 'null'};

    async function loadGuild() {{
        try {{
            const response = await fetch('/api/guilds/by-slug/' + encodeURIComponent(guildSlug) + '/');
            if (!response.ok) {{
                document.getElementById('guild-header').innerHTML = '<div class="alert alert-danger">Guild not found</div>';
                return;
            }}
            guild = await response.json();

            displayGuildHeader();
            displayGuildAbout();
            displayGuildMembers();
            displayGuildActions();
            displayGuildStats();
            loadGuildAffiliations();
        }} catch (error) {{
            console.error('Error loading guild:', error);
            document.getElementById('guild-header').innerHTML = '<div class="alert alert-danger">Error loading guild</div>';
        }}
    }}

    function displayGuildHeader() {{
        const statusBadge = guild.status === 'active'
            ? '<span class="badge bg-success">Active</span>'
            : '<span class="badge bg-secondary">Archived</span>';

        const isInitiator = isAuthenticated && guild.initiator_id === currentUserId;

        document.getElementById('guild-header').innerHTML =
            '<div class="row">' +
                '<div class="col-md-8">' +
                    '<h1>' + (guild.name || '') + '</h1>' +
                    '<div class="mb-3">' + statusBadge + '</div>' +
                '</div>' +
                '<div class="col-md-4 text-end">' +
                    (isInitiator ? '<button class="btn btn-secondary me-2" onclick="editGuild()"><i class="fas fa-edit me-2"></i>Edit</button>' : '') +
                    '<a href="/guilds/" class="btn btn-outline-secondary"><i class="fas fa-arrow-left me-2"></i>Back</a>' +
                '</div>' +
            '</div>';
    }}

    function displayGuildAbout() {{
        document.getElementById('guild-about').innerHTML = `
            <p>${{guild.description || 'No description provided'}}</p>
            <hr>
            <p><strong>Created:</strong> ${{new Date(guild.created_at).toLocaleDateString()}}</p>
            <p><strong>Last Updated:</strong> ${{guild.updated_at ? new Date(guild.updated_at).toLocaleDateString() : 'Never'}}</p>
        `;
    }}

    function displayGuildMembers() {{
        if (!guild.members || guild.members.length === 0) {{
            document.getElementById('guild-members').innerHTML = '<p class="text-muted">No members yet</p>';
            return;
        }}

        let html = '<div class="list-group">';
        guild.members.forEach(member => {{
            const roleClass = member.role === 'initiator' ? 'primary' : member.role === 'admin' ? 'success' : 'secondary';
            const mstate = member.membership_state || 'active';
            const stateBadge = mstate !== 'active' ? '<span class="badge bg-secondary ms-1">inactive</span>' : '';
            const displayName = member.display_name || member.name || member.username;
            const avatarHtml = member.profile_image
                ? `<img src="${{member.profile_image}}" alt="" class="rounded-circle me-2" style="width:32px;height:32px;object-fit:cover">`
                : `<span class="rounded-circle me-2 d-inline-flex align-items-center justify-content-center bg-secondary text-white" style="width:32px;height:32px;font-size:0.85rem">${{(displayName || '?').charAt(0).toUpperCase()}}</span>`;
            const profileLink = `/profile/${{member.username}}/`;
            html += `
                <div class="list-group-item d-flex justify-content-between align-items-center">
                    <div class="d-flex align-items-center">
                        ${{avatarHtml}}
                        <div>
                            <a href="${{profileLink}}" class="fw-bold text-decoration-none">${{displayName}}</a>
                            ${{displayName !== member.username ? `<br><small class="text-muted">@${{member.username}}</small>` : ''}}
                        </div>
                    </div>
                    <span class="badge bg-${{roleClass}}">${{member.role}}</span>${{stateBadge}}
                </div>
            `;
        }});
        html += '</div>';

        document.getElementById('guild-members').innerHTML = html;
    }}

    function displayGuildActions() {{
        const userMembership = guild.members ? guild.members.find(m => m.user_id === currentUserId) : null;
        const isAdmin = userMembership && (userMembership.role === 'initiator' || userMembership.role === 'admin');

        let html = '';

        // Add image at the top if available
        if (guild.image_url) {{
            html += '<div class="mb-3 text-center"><img src="' + guild.image_url + '" alt="' + (guild.name || '') + '" class="img-fluid rounded" style="max-height: 180px;"></div>';
        }}

        if (!isAuthenticated) {{
            html += '<a href="/login/" class="btn btn-primary w-100 mb-2"><i class="fas fa-sign-in-alt me-2"></i>Login to Join</a>';
        }} else if (!userMembership) {{
            html += '<p class="text-muted">Request an invitation from a guild admin to join</p>';
        }} else {{
            if (isAdmin) {{
                html += '<button class="btn btn-primary w-100 mb-2" onclick="inviteMember()"><i class="fas fa-user-plus me-2"></i>Invite Member</button>';
                html += '<button class="btn btn-secondary w-100 mb-2" onclick="manageGuild()"><i class="fas fa-cog me-2"></i>Manage Guild</button>';
            }}
            const ms = userMembership.membership_state || 'active';
            if (ms === 'active' && userMembership.role !== 'initiator') {{
                html += '<button type="button" class="btn btn-outline-warning w-100 mb-2" onclick="guildSetMyMembershipInactive()"><i class="fas fa-user-minus me-2"></i>Step back (mark inactive)</button>';
            }}
            html += '<p class="text-muted mt-2">Your role: <strong>' + userMembership.role + '</strong>' +
                (ms !== 'active' ? ' · <span class="badge bg-secondary">inactive</span>' : '') + '</p>';
        }}

        document.getElementById('guild-actions').innerHTML = html;
    }}

    function displayGuildStats() {{
        const memberCount = guild.members ? guild.members.length : 0;
        const adminCount = guild.members ? guild.members.filter(m => m.role === 'admin' || m.role === 'initiator').length : 0;

        document.getElementById('guild-stats').innerHTML = `
            <p><strong>Total Members:</strong> ${{memberCount}}</p>
            <p><strong>Admins:</strong> ${{adminCount}}</p>
            <p><strong>Status:</strong> ${{guild.status}}</p>
        `;
    }}

    function guildIsOfficerFn() {{
        const um = guild.members ? guild.members.find(m => m.user_id === currentUserId) : null;
        return um && (um.role === 'initiator' || um.role === 'admin');
    }}

    async function loadGuildAffiliations() {{
        const elL = document.getElementById('guild-layer-links');
        const elQ = document.getElementById('guild-quest-links');
        const elA = document.getElementById('guild-artifact-links');
        if (!guild || !elL) return;
        const officer = guildIsOfficerFn();
        try {{
            const [lr, qr, ar] = await Promise.all([
                fetch('/api/guilds/' + guild.id + '/layers/', {{ credentials: 'same-origin' }}),
                fetch('/api/guilds/' + guild.id + '/quest-links/', {{ credentials: 'same-origin' }}),
                fetch('/api/guilds/' + guild.id + '/artifact-links/', {{ credentials: 'same-origin' }})
            ]);
            const ld = lr.ok ? await lr.json() : {{ links: [] }};
            const qd = qr.ok ? await qr.json() : {{ links: [] }};
            const ad = ar.ok ? await ar.json() : {{ links: [] }};

            let hL = '';
            if ((ld.links || []).length === 0) hL += '<p class="text-muted small mb-2">No layers linked.</p>';
            else {{
                hL += '<ul class="list-group list-group-flush mb-2">';
                ld.links.forEach(lnk => {{
                    const L = lnk.layer || {{}};
                    const lid = L.id || lnk.layer_id;
                    const slug = L.slug || '';
                    const name = (L.name || lid || '').replace(/</g, '');
                    hL += '<li class="list-group-item d-flex justify-content-between align-items-center"><span>' +
                        (slug ? '<a href="/layers/' + slug + '/">' + name + '</a>' : name) + '</span>' +
                        (officer ? '<button type="button" class="btn btn-sm btn-outline-danger" onclick="guildDetachLayer(\\'' + String(lid).replace(/'/g, '') + '\\')">Remove</button>' : '') + '</li>';
                }});
                hL += '</ul>';
            }}
            if (officer) {{
                hL += '<div class="border-top pt-2"><label class="form-label small mb-1">Attach layer (UUID)</label><div class="input-group input-group-sm">' +
                    '<input type="text" class="form-control" id="guild-attach-layer-id" placeholder="layer id">' +
                    '<button class="btn btn-primary" type="button" onclick="guildAttachLayer()">Attach</button></div>' +
                    '<p class="small mb-0 mt-1" id="guild-attach-layer-msg"></p></div>';
            }}
            elL.innerHTML = hL;

            let hQ = '';
            if ((qd.links || []).length === 0) hQ += '<p class="text-muted small mb-2">No quest links.</p>';
            else {{
                hQ += '<ul class="list-group list-group-flush mb-2">';
                qd.links.forEach(lnk => {{
                    const q = lnk.quest || {{}};
                    const qid = q.id || lnk.quest_id;
                    const title = (q.title || qid || '').replace(/</g, '');
                    const lt = (lnk.link_type || '').replace(/_/g, ' ');
                    hQ += '<li class="list-group-item d-flex justify-content-between align-items-center"><span><strong>' + lt + '</strong> · ' + title + '</span>' +
                        (officer ? '<button type="button" class="btn btn-sm btn-outline-danger" onclick="guildDetachQuest(\\'' + String(qid).replace(/'/g, '') + '\\', \\'' + (lnk.link_type || '').replace(/'/g, '') + '\\')">Remove</button>' : '') + '</li>';
                }});
                hQ += '</ul>';
            }}
            if (officer) {{
                hQ += '<div class="border-top pt-2"><label class="form-label small mb-1">Quest id</label><input type="text" class="form-control form-control-sm mb-1" id="guild-attach-quest-id" placeholder="quest UUID">' +
                    '<label class="form-label small mb-1">Link type</label><select class="form-select form-select-sm mb-1" id="guild-attach-quest-type"><option value="sponsor">sponsor</option><option value="steward">steward</option><option value="review">review</option></select>' +
                    '<button class="btn btn-primary btn-sm" type="button" onclick="guildAttachQuest()">Attach quest</button><p class="small mb-0 mt-1" id="guild-attach-quest-msg"></p></div>';
            }}
            elQ.innerHTML = hQ;

            let hA = '';
            if ((ad.links || []).length === 0) hA += '<p class="text-muted small mb-2">No artifact links.</p>';
            else {{
                hA += '<ul class="list-group list-group-flush mb-2">';
                ad.links.forEach(lnk => {{
                    const a = lnk.artifact || {{}};
                    const aid = a.id || lnk.artifact_id;
                    const ref = a.public_ref || aid || '';
                    const title = (a.title || ref || '').replace(/</g, '');
                    const lt = (lnk.link_type || '').replace(/_/g, ' ');
                    hA += '<li class="list-group-item d-flex justify-content-between align-items-center"><span><strong>' + lt + '</strong> · ' + title + '</span>' +
                        (officer ? '<button type="button" class="btn btn-sm btn-outline-danger" onclick="guildDetachArtifact(\\'' + String(aid).replace(/'/g, '') + '\\', \\'' + (lnk.link_type || '').replace(/'/g, '') + '\\')">Remove</button>' : '') + '</li>';
                }});
                hA += '</ul>';
            }}
            if (officer) {{
                hA += '<div class="border-top pt-2"><label class="form-label small mb-1">Artifact id</label><input type="text" class="form-control form-control-sm mb-1" id="guild-attach-artifact-id" placeholder="artifact UUID">' +
                    '<label class="form-label small mb-1">Link type</label><select class="form-select form-select-sm mb-1" id="guild-attach-artifact-type"><option value="sponsor">sponsor</option><option value="co_author">co_author</option><option value="review">review</option></select>' +
                    '<button class="btn btn-primary btn-sm" type="button" onclick="guildAttachArtifact()">Attach artifact</button><p class="small mb-0 mt-1" id="guild-attach-artifact-msg"></p></div>';
            }}
            elA.innerHTML = hA;
        }} catch (e) {{
            elL.innerHTML = '<p class="text-danger small">Failed to load affiliations</p>';
            elQ.innerHTML = '';
            elA.innerHTML = '';
        }}
    }}

    async function guildAttachLayer() {{
        const inp = document.getElementById('guild-attach-layer-id');
        const msg = document.getElementById('guild-attach-layer-msg');
        if (!inp || !guild) return;
        const lid = inp.value.trim();
        if (!lid) {{ if (msg) msg.textContent = 'Enter layer id'; return; }}
        try {{
            const r = await fetch('/api/guilds/' + guild.id + '/layers/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'same-origin',
                body: JSON.stringify({{ layer_id: lid }})
            }});
            const d = await r.json().catch(() => ({{}}));
            if (r.ok) {{ inp.value = ''; if (msg) msg.textContent = ''; loadGuildAffiliations(); }}
            else {{ if (msg) {{ msg.textContent = d.error || 'Failed'; msg.className = 'small text-danger mb-0 mt-1'; }} }}
        }} catch (e) {{ if (msg) msg.textContent = e.message; }}
    }}

    async function guildDetachLayer(layerId) {{
        if (!guild || !layerId || !confirm('Remove layer link?')) return;
        const r = await fetch('/api/guilds/' + guild.id + '/layers/' + encodeURIComponent(layerId) + '/', {{ method: 'DELETE', credentials: 'same-origin' }});
        if (r.ok) loadGuildAffiliations(); else {{ const d = await r.json().catch(() => ({{}})); alert(d.error || 'Failed'); }}
    }}

    async function guildAttachQuest() {{
        const qid = (document.getElementById('guild-attach-quest-id') || {{}}).value.trim();
        const lt = (document.getElementById('guild-attach-quest-type') || {{}}).value;
        const msg = document.getElementById('guild-attach-quest-msg');
        if (!qid || !guild) return;
        try {{
            const r = await fetch('/api/guilds/' + guild.id + '/quest-links/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'same-origin',
                body: JSON.stringify({{ quest_id: qid, link_type: lt }})
            }});
            const d = await r.json().catch(() => ({{}}));
            if (r.ok) {{ loadGuildAffiliations(); if (msg) msg.textContent = ''; }}
            else {{ if (msg) msg.textContent = d.error || 'Failed'; }}
        }} catch (e) {{ if (msg) msg.textContent = e.message; }}
    }}

    async function guildDetachQuest(questId, linkType) {{
        if (!guild || !questId || !confirm('Remove quest link?')) return;
        const r = await fetch('/api/guilds/' + guild.id + '/quest-links/' + encodeURIComponent(questId) + '/?link_type=' + encodeURIComponent(linkType), {{ method: 'DELETE', credentials: 'same-origin' }});
        if (r.ok) loadGuildAffiliations(); else {{ const d = await r.json().catch(() => ({{}})); alert(d.error || 'Failed'); }}
    }}

    async function guildAttachArtifact() {{
        const aid = (document.getElementById('guild-attach-artifact-id') || {{}}).value.trim();
        const lt = (document.getElementById('guild-attach-artifact-type') || {{}}).value;
        const msg = document.getElementById('guild-attach-artifact-msg');
        if (!aid || !guild) return;
        try {{
            const r = await fetch('/api/guilds/' + guild.id + '/artifact-links/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'same-origin',
                body: JSON.stringify({{ artifact_id: aid, link_type: lt }})
            }});
            const d = await r.json().catch(() => ({{}}));
            if (r.ok) {{ loadGuildAffiliations(); if (msg) msg.textContent = ''; }}
            else {{ if (msg) msg.textContent = d.error || 'Failed'; }}
        }} catch (e) {{ if (msg) msg.textContent = e.message; }}
    }}

    async function guildDetachArtifact(artifactId, linkType) {{
        if (!guild || !artifactId || !confirm('Remove artifact link?')) return;
        const r = await fetch('/api/guilds/' + guild.id + '/artifact-links/' + encodeURIComponent(artifactId) + '/?link_type=' + encodeURIComponent(linkType), {{ method: 'DELETE', credentials: 'same-origin' }});
        if (r.ok) loadGuildAffiliations(); else {{ const d = await r.json().catch(() => ({{}})); alert(d.error || 'Failed'); }}
    }}

    async function guildSetMyMembershipInactive() {{
        if (!guild || !currentUserId || !confirm('Step back from this guild? You can ask an admin to reactivate you.')) return;
        const r = await fetch('/api/guilds/' + guild.id + '/members/' + encodeURIComponent(currentUserId) + '/', {{
            method: 'PATCH',
            headers: {{ 'Content-Type': 'application/json' }},
            credentials: 'same-origin',
            body: JSON.stringify({{ membership_state: 'inactive' }})
        }});
        const d = await r.json().catch(() => ({{}}));
        if (r.ok) location.reload();
        else alert(d.error || 'Failed');
    }}

    function inviteMember() {{
        const email = prompt('Enter email address to invite:');
        if (!email) return;

        fetch(`/api/guilds/${{guild.id}}/invite/`, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            credentials: 'same-origin',
            body: JSON.stringify({{email: email}})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                alert(`Invitation sent! Link: ${{data.invitation_link}}`);
            }} else {{
                alert('Error: ' + (data.error || 'Failed to send invitation'));
            }}
        }})
        .catch(error => {{
            console.error('Error:', error);
            alert('Error sending invitation');
        }});
    }}

    function manageGuild() {{
        alert('Guild management functionality coming soon');
    }}

    // Load guild on page load
    async function uploadGuildImage() {{
        const fileInput = document.getElementById('edit-guild-image-file');
        const statusEl = document.getElementById('edit-guild-image-upload-status');
        const urlInput = document.getElementById('edit-guild-image-url');

        if (!fileInput.files || !fileInput.files[0]) {{
            statusEl.innerHTML = '<small class="text-danger">Please select a file first</small>';
            return;
        }}

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('entity_type', 'guild');

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

    function editGuild() {{
        const modalHtml = `
            <div class="modal fade" id="editGuildModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Edit Guild</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="edit-guild-alert-container"></div>

                            <form id="editGuildForm">
                                <div class="mb-3">
                                    <label for="edit-guild-name" class="form-label">Guild Name *</label>
                                    <input type="text" class="form-control" id="edit-guild-name" value="${{guild.name}}" required>
                                </div>

                                <div class="mb-3">
                                    <label for="edit-guild-description" class="form-label">Description *</label>
                                    <textarea class="form-control" id="edit-guild-description" rows="4" required>${{guild.description}}</textarea>
                                </div>

                                <div class="mb-3">
                                    <label for="edit-guild-image-url" class="form-label">Image (optional)</label>
                                    <input type="url" class="form-control mb-2" id="edit-guild-image-url" value="${{guild.image_url || ''}}" placeholder="https://example.com/image.png or upload below">
                                    <div class="input-group">
                                        <input type="file" class="form-control" id="edit-guild-image-file" accept="image/*">
                                        <button class="btn btn-outline-primary" type="button" onclick="uploadGuildImage()">
                                            <i class="fas fa-upload"></i> Upload
                                        </button>
                                    </div>
                                    <div class="form-text">Guild logo or banner. Max 600×600px, 5MB. Upload or paste URL above.</div>
                                    <div id="edit-guild-image-upload-status" class="mt-1"></div>
                                </div>

                                <div class="mb-3">
                                    <label for="edit-guild-status" class="form-label">Status</label>
                                    <select class="form-select" id="edit-guild-status">
                                        <option value="active" ${{guild.status === 'active' ? 'selected' : ''}}>Active</option>
                                        <option value="archived" ${{guild.status === 'archived' ? 'selected' : ''}}>Archived</option>
                                    </select>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="updateGuildBtn">
                                <i class="fas fa-save me-2"></i>Save Changes
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        if (document.getElementById('editGuildModal')) {{
            document.getElementById('editGuildModal').remove();
        }}
        document.body.insertAdjacentHTML('beforeend', modalHtml);

        const modal = new bootstrap.Modal(document.getElementById('editGuildModal'));
        modal.show();

        document.getElementById('updateGuildBtn').onclick = async () => {{
            const name = document.getElementById('edit-guild-name').value.trim();
            const description = document.getElementById('edit-guild-description').value.trim();
            const image_url = document.getElementById('edit-guild-image-url') ? document.getElementById('edit-guild-image-url').value.trim() : '';
            const status = document.getElementById('edit-guild-status').value;

            if (!name || !description) {{
                document.getElementById('edit-guild-alert-container').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Name and description are required
                    </div>
                `;
                return;
            }}

            const submitBtn = document.getElementById('updateGuildBtn');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';

            try {{
                const response = await fetch(`/api/guilds/${{guild.id}}/`, {{
                    method: 'PATCH',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ name, description, image_url: image_url || null, status }})
                }});

                const data = await response.json();

                if (response.ok) {{
                    modal.hide();
                    loadGuild(); // Reload guild
                    alert('Guild updated successfully!');
                }} else {{
                    throw new Error(data.error || 'Failed to update guild');
                }}
            }} catch (error) {{
                document.getElementById('edit-guild-alert-container').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        ${{error.message}}
                    </div>
                `;
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-save me-2"></i>Save Changes';
            }}
        }};
    }}

    loadGuild();
    </script>
    """

    return render_page(f"Guild: {guild_slug} - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/guilds/invite/<path:invite_token>/')
def guild_invite_landing(invite_token):
    """Accept a guild invitation (token from email/link)."""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    tok = invite_token.strip('/')
    content = f"""
    <div class="container mt-4">
        <div class="col-md-8 mx-auto">
            <h1 class="h3 mb-3">Guild invitation</h1>
            <div id="invite-status" class="mb-3"><div class="spinner-border spinner-border-sm"></div> Loading…</div>
            <div id="invite-actions" class="d-none">
                <a href="/login/" class="btn btn-primary me-2" id="invite-login-btn">Log in to accept</a>
                <button type="button" class="btn btn-success d-none" id="invite-accept-btn">Accept invitation</button>
                <a href="/guilds/" class="btn btn-outline-secondary">Guild directory</a>
            </div>
        </div>
    </div>
    <script>
    const inviteToken = {json.dumps(tok)};
    const isAuthenticated = {'true' if current_user else 'false'};
    (async function() {{
        const st = document.getElementById('invite-status');
        const act = document.getElementById('invite-actions');
        const loginBtn = document.getElementById('invite-login-btn');
        const acceptBtn = document.getElementById('invite-accept-btn');
        try {{
            const r = await fetch('/api/guilds/invitations/by-token/' + encodeURIComponent(inviteToken) + '/');
            const d = await r.json();
            if (!r.ok) {{
                st.innerHTML = '<div class="alert alert-warning">' + (d.error || 'Invalid invitation') + '</div>';
                act.classList.remove('d-none');
                loginBtn.classList.add('d-none');
                return;
            }}
            const g = d.guild || {{}};
            st.innerHTML = '<p>You have been invited to join <strong>' + (g.name || 'a guild') + '</strong>.</p>' +
                '<p class="text-muted small">Sent to: ' + (d.invitee_email_masked || '') + '</p>';
            act.classList.remove('d-none');
            if (isAuthenticated) {{
                loginBtn.classList.add('d-none');
                acceptBtn.classList.remove('d-none');
            }} else {{
                loginBtn.href = '/login/?next=' + encodeURIComponent('/guilds/invite/' + inviteToken + '/');
            }}
            acceptBtn.addEventListener('click', async function() {{
                acceptBtn.disabled = true;
                try {{
                    const ar = await fetch('/api/guilds/invitations/by-token/' + encodeURIComponent(inviteToken) + '/accept/', {{
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: '{{}}'
                    }});
                    const ad = await ar.json();
                    if (ar.ok) {{
                        st.innerHTML = '<div class="alert alert-success">You are now a member. <a href="/guilds/' + (g.slug || '') + '/">Open guild</a></div>';
                        act.classList.add('d-none');
                    }} else {{
                        st.innerHTML = '<div class="alert alert-danger">' + (ad.error || 'Failed') + '</div>';
                        acceptBtn.disabled = false;
                    }}
                }} catch (e) {{
                    st.innerHTML = '<div class="alert alert-danger">' + e.message + '</div>';
                    acceptBtn.disabled = false;
                }}
            }});
        }} catch (e) {{
            st.innerHTML = '<div class="alert alert-danger">Could not load invitation.</div>';
            act.classList.remove('d-none');
        }}
    }})();
    </script>
    """
    return render_page("Guild invitation - MLGH", content, theme=current_theme, user_menu=user_menu)


@bp.route('/guilds/create/')
@require_auth
def create_guild_page():
    """Create guild form page"""
    render_page, generate_user_menu = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()

    content = """
    <div class="container mt-4">
        <div class="row">
            <div class="col-md-8 offset-md-2">
                <h1 class="mb-4">Create New Guild</h1>

                <div id="alert-container"></div>

                <form id="createGuildForm">
                    <div class="mb-3">
                        <label for="name" class="form-label">Guild Name *</label>
                        <input type="text" class="form-control" id="name" required>
                        <div class="form-text">A clear, descriptive name for your guild</div>
                    </div>

                    <div class="mb-3">
                        <label for="description" class="form-label">Description *</label>
                        <textarea class="form-control" id="description" rows="4" required></textarea>
                        <div class="form-text">Explain what this guild is about and its purpose</div>
                    </div>

                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        <strong>Note:</strong> Guilds are instantly created with no approval required. You will automatically become the guild initiator and admin.
                    </div>

                    <div class="d-flex gap-2">
                        <button type="submit" class="btn btn-primary" id="submitBtn">
                            <i class="fas fa-plus me-2"></i>Create Guild
                        </button>
                        <a href="/guilds/" class="btn btn-secondary">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <script>
    document.getElementById('createGuildForm').addEventListener('submit', async (e) => {
        e.preventDefault();

        const submitBtn = document.getElementById('submitBtn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';

        const formData = {
            name: document.getElementById('name').value,
            description: document.getElementById('description').value
        };

        try {
            const response = await fetch('/api/guilds/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (response.ok) {
                document.getElementById('alert-container').innerHTML = `
                    <div class="alert alert-success">
                        <i class="fas fa-check-circle me-2"></i>
                        Guild created successfully! Redirecting...
                    </div>
                `;
                setTimeout(() => {
                    window.location.href = `/guilds/${data.guild.slug}/`;
                }, 1500);
            } else {
                throw new Error(data.error || 'Failed to create guild');
            }
        } catch (error) {
            document.getElementById('alert-container').innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle me-2"></i>
                    ${error.message}
                </div>
            `;
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Guild';
        }
    });
    </script>
    """

    return render_page("Create Guild - MLGH", content, theme=current_theme, user_menu=user_menu)
