"""Layer detail page renderer."""
import json
from flask import session, current_app, make_response, request

from models import Layer
from services.identity import get_current_user
from services.coordination import is_layer_admin


def _render_layer_standalone(project_slug, waitlist_id=None):
    """Standalone layer view: layer branding, tabs as nav, Overview as home."""
    return _render_project_detail(project_slug, waitlist_id=waitlist_id, standalone=True)


def _render_project_detail(project_slug, waitlist_id=None, standalone=False):
    """Shared logic for project detail page. waitlist_id when from /layers/<slug>/waitlist/<id>/.
    standalone=True: layer branding (logo, name), View in MLGH button."""
    from services.rendering import render_page, render_layer_standalone_page, generate_user_menu

    current_app.logger.info(f"[LAYER] _render_project_detail: project_slug={project_slug!r} waitlist_id={waitlist_id}")
    user_menu = generate_user_menu(layer_slug=project_slug if not standalone else None)
    current_theme = session.get('theme', 'dark')
    current_user = get_current_user()
    
    project_obj = Layer.query.filter_by(slug=project_slug).first()
    show_admin_tab = bool(project_obj and current_user and is_layer_admin(project_obj, current_user))
    initial_waitlist_id = str(waitlist_id) if waitlist_id else None
    
    admin_tab_html = ''
    admin_tab_pane_html = ''
    admin_tab_listener = ''
    # Layer-centric view: no Admin tab (admin via /layers/<slug>/#admin). No About|Admin row (About in Governance nav).
    if show_admin_tab and not standalone:
        admin_tab_html = '''
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="admin-tab" data-bs-toggle="tab" data-bs-target="#admin" type="button">Admin</button>
            </li>
        '''
        admin_tab_pane_html = '''
            <div class="tab-pane fade" id="admin">
                <div id="admin-content"></div>
            </div>
        '''
        admin_tab_listener = "document.getElementById('admin-tab').addEventListener('shown.bs.tab', loadAdmins);"
    
    tabs_hidden_class = ' d-none' if standalone else ''
    if standalone:
        container_html = """
    <div class="container mt-4">
        <div id="project-title" class="mb-3">
            <div class="d-flex justify-content-center py-3">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>
        <div id="project-header" class="mb-4"></div>
        <div id="overview-content"></div>
    </div>
"""
    else:
        container_html = f"""
    <div class="container mt-4">
        <div id="project-title" class="mb-3">
            <div class="d-flex justify-content-center py-3">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>
        
        <ul class="nav nav-tabs mb-4{tabs_hidden_class}" id="projectTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="overview-tab" data-bs-toggle="tab" data-bs-target="#overview" type="button">Overview</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="workgroups-tab" data-bs-toggle="tab" data-bs-target="#workgroups" type="button">Workgroups</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="clusters-tab" data-bs-toggle="tab" data-bs-target="#clusters" type="button">Clusters</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="roles-tab" data-bs-toggle="tab" data-bs-target="#roles" type="button">Roles</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="claims-tab" data-bs-toggle="tab" data-bs-target="#claims" type="button">Claims</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="votes-tab" data-bs-toggle="tab" data-bs-target="#votes" type="button">Votes</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="artifacts-tab" data-bs-toggle="tab" data-bs-target="#artifacts" type="button">Artifacts</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="opportunities-tab" data-bs-toggle="tab" data-bs-target="#opportunities" type="button">Opportunities</button>
            </li>
            {admin_tab_html}
            <li id="waitlist-tabs-marker" class="nav-item d-none"></li>
        </ul>
        
        <div class="tab-content" id="projectTabContent">
            <div class="tab-pane fade show active" id="overview">
                <div id="project-header" class="mb-4"></div>
                <div id="overview-content"></div>
            </div>
            <div class="tab-pane fade" id="workgroups">
                <div id="workgroups-content"></div>
            </div>
            <div class="tab-pane fade" id="clusters">
                <div id="clusters-content"></div>
            </div>
            <div class="tab-pane fade" id="roles">
                <div id="roles-content"></div>
            </div>
            <div class="tab-pane fade" id="claims">
                <div id="claims-content"></div>
            </div>
            <div class="tab-pane fade" id="votes">
                <div id="votes-content"></div>
            </div>
            <div class="tab-pane fade" id="artifacts">
                <div class="card mb-4">
                    <div class="card-header"><h5 class="mb-0"><i class="fas fa-cube me-2"></i>Artifacts</h5></div>
                    <div class="card-body">
                        <p class="text-muted">Knowledge objects: proposals, evidence, submissions, and their relations.</p>
                        <div id="artifacts-tab-container"><div class="text-center py-4"><div class="spinner-border spinner-border-sm text-secondary"></div> Loading...</div></div>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="opportunities">
                <div class="card mb-4">
                    <div class="card-header"><h5 class="mb-0"><i class="fas fa-bullseye me-2"></i>Opportunities</h5></div>
                    <div class="card-body">
                        <p class="text-muted">Drafts needing support or opposition, open quests, and ways to contribute.</p>
                        <div id="opportunities-tab-container"><div class="text-center py-4"><div class="spinner-border spinner-border-sm text-secondary"></div> Loading...</div></div>
                    </div>
                </div>
            </div>
            {admin_tab_pane_html}
            <div id="waitlist-panes-marker" class="d-none"></div>
        </div>
    </div>
"""
    content = f"""
    <style>
    #projectTabs .nav-link {{ padding-top: 0.3rem; padding-bottom: 0.3rem; font-size: 0.875rem; line-height: 1.2; }}
    </style>
    {container_html}
    
    <div class="modal fade" id="joinProjectModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-plus me-2"></i>Join Layer</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted mb-3">You will join this project as a contributor. Optionally add a referral code if you were invited via a link.</p>
                    <div class="mb-0">
                        <label for="join-project-referral" class="form-label">Referral code (optional)</label>
                        <input type="text" class="form-control" id="join-project-referral" placeholder="Leave blank if none">
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="join-project-confirm-btn" onclick="submitJoinProjectModal()"><i class="fas fa-check me-2"></i>Join</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="joinWaitlistModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title" id="join-waitlist-modal-title"><i class="fas fa-list-alt me-2"></i>Join Waitlist</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted mb-3" id="join-waitlist-modal-desc">Add an optional message for the waitlist owner.</p>
                    <div class="mb-0">
                        <label for="join-waitlist-message" class="form-label">Message (optional)</label>
                        <textarea class="form-control" id="join-waitlist-message" rows="3" placeholder="Leave blank to skip"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="join-waitlist-confirm-btn" onclick="submitJoinWaitlistModal()"><i class="fas fa-check me-2"></i>Join</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="addAdminModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Add layer admin</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <label class="form-label">Search by username or name</label>
                    <input type="text" class="form-control" id="add-admin-username" placeholder="Type to search..." oninput="searchUsersForAdmin()">
                    <div id="add-admin-results" class="mt-3"></div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="embedCodeModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Embed Waitlist Widget</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p class="lead" id="embed-waitlist-name"></p>
                    <a id="embed-builder-link" href="#" class="btn btn-primary mb-3"><i class="fas fa-sliders-h me-1"></i>Customize Embed (colors, options, preview)</a>
                    <p class="text-muted small">Copy and paste this code into your website. Signups are tracked with the source URL.</p>
                    
                    <div class="mb-4">
                        <label class="form-label"><strong>Embed Code (iframe)</strong></label>
                        <div class="input-group">
                            <textarea class="form-control font-monospace" id="embed-code-iframe" rows="3" readonly></textarea>
                            <button class="btn btn-outline-primary" onclick="copyEmbedCode('iframe')"><i class="fas fa-copy"></i> Copy</button>
                        </div>
                        <small class="text-muted">Recommended: Simple iframe embed with automatic sizing</small>
                    </div>
                    
                    <div class="mb-4">
                        <label class="form-label"><strong>Direct Widget URL</strong></label>
                        <div class="input-group">
                            <input type="text" class="form-control font-monospace" id="embed-url" readonly>
                            <button class="btn btn-outline-primary" onclick="copyEmbedCode('url')"><i class="fas fa-copy"></i> Copy</button>
                        </div>
                        <small class="text-muted">Use this URL to embed in an iframe or link directly</small>
                    </div>
                    
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle me-2"></i>
                        <strong>Source Tracking:</strong> All signups from the embedded widget will be tracked with the source domain and URL where the signup occurred.
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="createQuestModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-tasks me-2"></i>Create Quest</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="create-quest-alert" class="alert d-none" role="alert"></div>
                    <form id="createQuestForm">
                        <div class="mb-3">
                            <label for="quest-title" class="form-label">Title *</label>
                            <input type="text" class="form-control" id="quest-title" required placeholder="e.g. Write opposition for draft X">
                        </div>
                        <div class="mb-3">
                            <label for="quest-description" class="form-label">Description</label>
                            <textarea class="form-control" id="quest-description" rows="3" placeholder="What contribution are you looking for?"></textarea>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="quest-type" class="form-label">Type</label>
                                <select class="form-select" id="quest-type">
                                    <option value="contribution">Contribution</option>
                                    <option value="bounty">Bounty</option>
                                    <option value="review">Review</option>
                                    <option value="documentation">Documentation</option>
                                </select>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label for="quest-difficulty" class="form-label">Difficulty</label>
                                <select class="form-select" id="quest-difficulty">
                                    <option value="easy">Easy</option>
                                    <option value="medium" selected>Medium</option>
                                    <option value="hard">Hard</option>
                                </select>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label for="quest-acceptance-criteria" class="form-label">Acceptance criteria (optional)</label>
                            <textarea class="form-control" id="quest-acceptance-criteria" rows="2" placeholder="What must be done to complete this quest?"></textarea>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="create-quest-submit-btn" onclick="submitCreateQuest()"><i class="fas fa-check me-2"></i>Create Quest</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="createVoteModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-vote-yea me-2"></i>Create Vote</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="create-vote-alert" class="alert d-none" role="alert"></div>
                    <form id="createVoteForm">
                        <div class="mb-3">
                            <label class="form-label">Vote type *</label>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="vote-type" id="vote-type-approval" value="approval" checked onchange="toggleVoteTypeFields()">
                                <label class="form-check-label" for="vote-type-approval">Approval — Vote on a draft (yes/no)</label>
                            </div>
                            <div class="form-check">
                                <input class="form-check-input" type="radio" name="vote-type" id="vote-type-election" value="election" onchange="toggleVoteTypeFields()">
                                <label class="form-check-label" for="vote-type-election">Election — Vote for a role (choose among candidates)</label>
                            </div>
                        </div>
                        <div class="mb-3">
                            <label for="vote-title" class="form-label">Title *</label>
                            <input type="text" class="form-control" id="vote-title" required placeholder="e.g. Approve ML-DRAFT-001 or Election: Director">
                        </div>
                        <div class="mb-3">
                            <label for="vote-description" class="form-label">Description</label>
                            <textarea class="form-control" id="vote-description" rows="2" placeholder="What is being decided"></textarea>
                        </div>
                        <div class="mb-3" id="vote-submission-section">
                            <label for="vote-submission-id" class="form-label">Draft to vote on *</label>
                            <select class="form-select" id="vote-submission-id">
                                <option value="">Loading drafts...</option>
                            </select>
                            <div class="form-text">Select an approved draft from this layer's workgroups</div>
                        </div>
                        <div class="mb-3 d-none" id="vote-role-section">
                            <label for="vote-role-id" class="form-label">Role to elect *</label>
                            <select class="form-select" id="vote-role-id">
                                <option value="">Loading roles...</option>
                            </select>
                            <div class="form-text">Roles with "requires election" (or any role) can be filled via vote</div>
                            <div class="mt-2">
                                <label for="vote-seats" class="form-label small">Seats (winners)</label>
                                <input type="number" class="form-control form-control-sm" id="vote-seats" min="1" value="1" style="max-width:80px">
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="vote-start" class="form-label">Start (<span id="timezone-start">your local time</span>) *</label>
                                <input type="datetime-local" class="form-control" id="vote-start" required>
                            </div>
                            <div class="col-md-6 mb-3">
                                <label for="vote-end" class="form-label">End (<span id="timezone-end">your local time</span>) *</label>
                                <input type="datetime-local" class="form-control" id="vote-end" required>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-6 mb-3">
                                <label for="vote-quorum" class="form-label">Quorum (min votes) *</label>
                                <input type="number" class="form-control" id="vote-quorum" required min="1" value="1">
                            </div>
                            <div class="col-md-6 mb-3">
                                <label for="vote-threshold" class="form-label">Win threshold (0–1) *</label>
                                <input type="number" class="form-control" id="vote-threshold" required min="0" max="1" step="0.01" value="0.5" placeholder="0.5 = majority">
                            </div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="create-vote-submit-btn" onclick="submitCreateVote()"><i class="fas fa-check me-2"></i>Create Vote</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="emailModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-envelope me-2"></i>Email Recipients</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <div id="email-modal-alert" class="alert d-none" role="alert"></div>
                    <form id="emailForm">
                        <div class="mb-3">
                            <label class="form-label">Recipients (max 100)</label>
                            <div id="email-recipient-groups" class="border rounded p-3 bg-light"></div>
                            <div class="form-text">Select one or more groups. Unsubscribed users are excluded.</div>
                        </div>
                        <div class="mb-3">
                            <label for="email-from" class="form-label">From</label>
                            <select class="form-select" id="email-from"></select>
                        </div>
                        <div class="mb-3">
                            <label for="email-subject" class="form-label">Subject *</label>
                            <input type="text" class="form-control" id="email-subject" required placeholder="e.g. Layer update">
                        </div>
                        <div class="mb-3">
                            <label for="email-body" class="form-label">Message *</label>
                            <textarea class="form-control" id="email-body" rows="6" required placeholder="Your message..."></textarea>
                            <div class="form-text">An unsubscribe link is added automatically to every email.</div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="email-submit-btn" onclick="submitEmail()"><i class="fas fa-paper-plane me-2"></i>Send</button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="editProjectModal" tabindex="-1">
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Edit Layer</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
                    <div id="edit-project-alert" class="alert d-none" role="alert"></div>
                    <form id="editProjectForm">
                        <div class="card bg-secondary bg-opacity-10 mb-4">
                            <div class="card-body py-3">
                                <h6 class="card-title mb-2"><i class="fas fa-user-shield me-2"></i>Layer Admins</h6>
                                <p class="text-muted small mb-2">Admins can manage workgroups, roles, claims, and other admins. The owner cannot be removed.</p>
                                <div id="edit-modal-admins-list" class="list-group mb-3"></div>
                                <div class="mb-0">
                                    <label class="form-label small">Add admin</label>
                                    <div class="input-group input-group-sm">
                                        <input type="text" class="form-control" id="edit-modal-add-admin-q" placeholder="Search by username (min 2 chars)..." oninput="searchUsersForEditModalAdmin()">
                                        <button type="button" class="btn btn-outline-primary" onclick="searchUsersForEditModalAdmin()"><i class="fas fa-search"></i></button>
                                    </div>
                                    <div id="edit-modal-add-admin-results" class="mt-2"></div>
                                </div>
                            </div>
                        </div>
                        <hr>
                        <div class="mb-3">
                            <label for="edit-project-name" class="form-label">Layer Name *</label>
                            <input type="text" class="form-control" id="edit-project-name" required maxlength="255">
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-mission" class="form-label">Mission</label>
                            <textarea class="form-control" id="edit-project-mission" rows="3"></textarea>
                            <div class="form-text">Core purpose and values (line breaks preserved)</div>
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-description" class="form-label">Description</label>
                            <textarea class="form-control" id="edit-project-description" rows="4"></textarea>
                            <div class="form-text">Line breaks are preserved when displayed</div>
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-image-url" class="form-label">Image (optional)</label>
                            <input type="url" class="form-control mb-2" id="edit-project-image-url" placeholder="https://example.com/image.png or upload below">
                            <div class="input-group">
                                <input type="file" class="form-control" id="edit-project-image-file" accept="image/*">
                                <button class="btn btn-outline-primary" type="button" onclick="uploadProjectImage()">
                                    <i class="fas fa-upload"></i> Upload
                                </button>
                            </div>
                            <div class="form-text">Layer logo or banner image. Max 600×600px, 5MB. Upload or paste URL above.</div>
                            <div id="edit-project-image-upload-status" class="mt-1"></div>
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-status" class="form-label">Status</label>
                            <select class="form-select" id="edit-project-status">
                                <option value="proposed">Proposed</option>
                                <option value="active">Active</option>
                                <option value="stabilizing">Stabilizing</option>
                                <option value="maintaining">Maintaining</option>
                                <option value="dormant">Dormant</option>
                                <option value="concluded">Concluded</option>
                                <option value="archived">Archived</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-status-reason" class="form-label">Status Reason (optional)</label>
                            <input type="text" class="form-control" id="edit-project-status-reason" placeholder="e.g. reason for status change">
                        </div>
                        <div class="mb-3">
                            <label for="edit-project-meta-domain-inscription" class="form-label">Meta-domain inscription ID</label>
                            <input type="text" class="form-control" id="edit-project-meta-domain-inscription" placeholder="e.g. abc123...i0">
                            <div class="form-text">Ordinal inscription whose content is the meta-domain (e.g. example.com.meta). Fetched once and cached.</div>
                            <div id="edit-project-meta-domain-display" class="mt-1 text-muted small"></div>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                    <button type="button" class="btn btn-primary" id="edit-project-save-btn" onclick="saveProjectEdit()"><i class="fas fa-save me-2"></i>Save</button>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    let project = null;
    const projectSlug = {json.dumps(project_slug)};
    const initialWaitlistId = {json.dumps(initial_waitlist_id)};
    const isAuthenticated = {'true' if current_user else 'false'};
    const isAdmin = {('true' if current_user and current_user.get('is_admin') else 'false')};
    const isProjectAdmin = {'true' if show_admin_tab else 'false'};
    const showCarousel = {json.dumps(standalone)};
    const layerBase = showCarousel ? '/layer/' + projectSlug + '/' : '/layers/' + projectSlug + '/';
    let artifactKnowledgeFilter = '';
    
    const referralRef = {json.dumps(request.args.get('ref') or '')};
    
    function getProjectTabKey(buttonId) {{
        if (!buttonId) return null;
        if (buttonId === 'overview-tab') return 'overview';
        if (buttonId === 'workgroups-tab') return 'workgroups';
        if (buttonId === 'clusters-tab') return 'clusters';
        if (buttonId === 'roles-tab') return 'roles';
        if (buttonId === 'claims-tab') return 'claims';
        if (buttonId === 'votes-tab') return 'votes';
        if (buttonId === 'artifacts-tab') return 'artifacts';
        if (buttonId === 'opportunities-tab') return 'opportunities';
        if (buttonId === 'admin-tab') return 'admin';
        const m = buttonId.match(/^waitlist-tab-(\\d+)$/);
        return m ? 'waitlist-' + m[1] : null;
    }}
    
    function saveTabState(current, previous) {{
        try {{
            const key = 'projectDetailTab_' + projectSlug;
            localStorage.setItem(key + '_current', current);
            if (previous) localStorage.setItem(key + '_previous', previous);
        }} catch (e) {{ console.warn('saveTabState:', e); }}
    }}
    
    function switchToTab(tabId) {{
        const map = {{ workgroups: 'workgroups-tab', clusters: 'clusters-tab', roles: 'roles-tab', claims: 'claims-tab', votes: 'votes-tab', artifacts: 'artifacts-tab', opportunities: 'opportunities-tab', admin: 'admin-tab' }};
        const btnId = map[tabId];
        const tabEl = btnId ? document.getElementById(btnId) : null;
        if (tabEl) tabEl.click();
    }}
    
    function switchToTabFromHash() {{
        const hash = (window.location.hash || '').replace(/^#/, '');
        if (['claims', 'votes', 'admin'].includes(hash)) switchToTab(hash);
    }}
    
    function restoreTabState() {{
        try {{
            if (window.location.hash && ['claims', 'votes', 'admin'].includes(window.location.hash.replace('#', ''))) {{
                switchToTabFromHash();
                return;
            }}
            const key = 'projectDetailTab_' + projectSlug;
            const stored = localStorage.getItem(key + '_current');
            if (!stored || stored === 'overview') return;
            let tabEl = null;
            if (stored.startsWith('waitlist-')) {{
                const id = stored.replace('waitlist-', '');
                tabEl = document.getElementById('waitlist-tab-' + id);
            }} else {{
                const map = {{ workgroups: 'workgroups-tab', clusters: 'clusters-tab', roles: 'roles-tab', claims: 'claims-tab', votes: 'votes-tab', artifacts: 'artifacts-tab', opportunities: 'opportunities-tab', admin: 'admin-tab' }};
                const btnId = map[stored];
                tabEl = btnId ? document.getElementById(btnId) : null;
            }}
            if (tabEl) tabEl.click();
        }} catch (e) {{ console.warn('restoreTabState:', e); }}
    }}
    
    function escapeHtml(text) {{
        if (!text) return '';
        return String(text).split('&').join('&amp;').split('<').join('&lt;').split('>').join('&gt;').split('\\n').join('<br>');
    }}
    
    function escapeHtmlBasic(text) {{
        if (!text) return '';
        return String(text).split('&').join('&amp;').split('<').join('&lt;').split('>').join('&gt;').split('"').join('&quot;').split("'").join('&#39;').split('`').join('&#96;');
    }}
    
    function escapeForTemplate(text) {{
        if (!text) return '';
        return String(text).replace(/\\\\/g, '\\\\\\\\').replace(/`/g, '\\\\`').replace(/\\$/g, '\\\\$');
    }}
    
    function escapeForJsAttr(text) {{
        if (!text) return '';
        return String(text).replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'").replace(/"/g, '\\\\"').replace(/`/g, '\\\\`');
    }}
    
    async function loadProject() {{
        try {{
            console.log('[LAYER] loadProject called, projectSlug=', projectSlug, 'type=', typeof projectSlug);
            if (!projectSlug || typeof projectSlug !== 'string') {{
                console.error('[LAYER] loadProject: invalid projectSlug');
                document.getElementById('project-title').innerHTML = '<div class="alert alert-danger">Invalid layer URL. <a href="/layers/">Back to Layers</a></div>';
                return;
            }}
            const slug = String(projectSlug).trim();
            const url = '/api/layers/by-slug/' + encodeURIComponent(slug) + '/';
            console.log('[LAYER] loadProject fetching:', url);
            const resp = await fetch(url, {{ credentials: 'include' }});
            console.log('[LAYER] loadProject response:', resp.status, resp.statusText, 'url=', resp.url);
            if (!resp.ok) {{
                const text = await resp.text();
                console.error('[LAYER] loadProject fetch failed:', resp.status, text.substring(0, 200));
                document.getElementById('project-title').innerHTML = '<div class="alert alert-danger">Layer not found. <a href="/layers/">Back to Layers</a></div>';
                return;
            }}
            const detail = await resp.json();
            console.log('[LAYER] loadProject got project:', detail?.name, 'id=', detail?.id);
            project = detail;
            project.is_member = detail.is_member === true;
            project.member_role = detail.member_role || null;
            
            displayProjectHeader();
            loadOverview();
            const wlResp = await fetch('/api/layers/' + project.id + '/waitlists/');
            const wlData = await wlResp.json().catch(() => ({{ waitlists: [], count: 0 }}));
            const enabledWaitlists = (wlData.waitlists || []).filter(w => w.active !== false);
            buildWaitlistTabs(enabledWaitlists);
            if (initialWaitlistId) {{
                const wl = enabledWaitlists.find(w => w.id === initialWaitlistId);
                if (wl) {{
                    document.getElementById('waitlist-tab-' + wl.id)?.click();
                }} else {{
                    showWaitlistInactiveMessage(initialWaitlistId);
                }}
            }} else {{
                restoreTabState();
            }}
        }} catch (error) {{
            console.error('Error loading project:', error);
            document.getElementById('project-title').innerHTML = '<div class="alert alert-danger">Error loading project</div>';
        }}
    }}
    
    function showJoinProjectModal() {{
        if (!isAuthenticated) {{ alert('Please sign in to join this project'); return; }}
        const refInput = document.getElementById('join-project-referral');
        if (refInput) refInput.value = referralRef || '';
        const modal = new bootstrap.Modal(document.getElementById('joinProjectModal'));
        modal.show();
    }}
    
    async function submitJoinProjectModal() {{
        const refInput = document.getElementById('join-project-referral');
        const ref = refInput && refInput.value ? refInput.value.trim() : (referralRef || '');
        const body = ref ? {{ referral_code: ref }} : {{}};
        try {{
            const res = await fetch('/api/layers/' + project.id + '/join/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            const data = await res.json();
            if (res.ok) {{
                project.is_member = true;
                project.member_role = data.member && data.member.role ? data.member.role : 'contributor';
                displayProjectHeader();
                bootstrap.Modal.getInstance(document.getElementById('joinProjectModal')).hide();
            }} else {{ alert(data.error || 'Failed to join'); }}
        }} catch (e) {{ console.error(e); alert('Failed to join project'); }}
    }}
    
    async function leaveProject() {{
        if (!confirm('Leave this project?')) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/leave/', {{ method: 'POST' }});
            if (res.ok) {{
                project.is_member = false;
                project.member_role = null;
                displayProjectHeader();
            }} else {{ const d = await res.json(); alert(d.error || 'Failed to leave'); }}
        }} catch (e) {{ alert('Failed to leave project'); }}
    }}
    
    function displayProjectHeader() {{
        const statusMap = {{'proposed':'<span class="badge bg-info ms-2">Proposed</span>','active':'<span class="badge bg-success ms-2">Active</span>','stabilizing':'<span class="badge bg-primary ms-2">Stabilizing</span>','maintaining':'<span class="badge bg-secondary ms-2">Maintaining</span>','dormant':'<span class="badge bg-warning ms-2">Dormant</span>','concluded':'<span class="badge bg-dark ms-2">Concluded</span>','archived':'<span class="badge bg-secondary ms-2">Archived</span>'}};
        const approvalMap = {{'pending':'<span class="badge bg-warning ms-2">Pending Approval</span>','approved':'<span class="badge bg-success ms-2">Approved</span>','rejected':'<span class="badge bg-danger ms-2">Rejected</span>'}};
        const statusBadge = (project.approval_status === 'approved' && project.status === 'proposed') ? '' : (statusMap[project.status] || (project.status ? '<span class="badge bg-secondary ms-2">' + escapeHtml(String(project.status)) + '</span>' : ''));
        const approvalBadge = approvalMap[project.approval_status] || (project.approval_status ? '<span class="badge bg-secondary ms-2">' + escapeHtml(String(project.approval_status)) + '</span>' : '');
        const showTags = !showCarousel;
        const isJoined = project.is_member || isProjectAdmin;
        let actionsHtml = '';
        if (project.mission) {{
            actionsHtml += '<div class="mb-3"><strong>Mission</strong><p class="mb-0 small">' + escapeHtml(project.mission || '') + '</p></div>';
        }}
        if (isAuthenticated) {{
            if (isJoined) {{
                actionsHtml += '<div class="mb-3"><span class="badge bg-success">Joined</span></div>';
            }} else {{
                actionsHtml += '<div class="mb-3"><button class="btn btn-primary btn-sm w-100" onclick="showJoinProjectModal()"><i class="fas fa-plus me-2"></i>Join Layer</button></div>';
            }}
        }}
        if (isProjectAdmin) {{
            actionsHtml += '<div class="mb-3"><button class="btn btn-outline-primary btn-sm w-100" onclick="createWaitlist()"><i class="fas fa-plus me-2"></i>Create Waitlist</button></div>';
            actionsHtml += '<div class="mb-3"><button class="btn btn-outline-primary btn-sm w-100" onclick="showCreateQuestModal()"><i class="fas fa-tasks me-2"></i>Create Quest</button></div>';
            actionsHtml += '<div class="mb-3"><button class="btn btn-outline-primary btn-sm w-100" onclick="showCreateVoteModal()"><i class="fas fa-vote-yea me-2"></i>Create Vote</button></div>';
            actionsHtml += '<div class="mb-3"><button class="btn btn-outline-primary btn-sm w-100" onclick="showEmailModal()"><i class="fas fa-envelope me-2"></i>Email</button></div>';
        }}
        actionsHtml += '<div class="mb-2"><a href="' + (showCarousel ? layerBase : '/layers/') + '" class="btn btn-outline-secondary btn-sm w-100"><i class="fas fa-arrow-left me-2"></i>' + (showCarousel ? 'Back to Layer' : 'Back to Layers') + '</a></div>';
        if (isProjectAdmin) {{
            actionsHtml += '<button class="btn btn-secondary btn-sm w-100" onclick="editProject()"><i class="fas fa-edit me-2"></i>Edit</button>';
        }}
        const imageHtml = project.image_url ? '<div class="card mb-3"><div class="card-body p-2 text-center"><img src="' + project.image_url + '" alt="' + escapeHtmlBasic(project.name) + '" class="img-fluid rounded" style="max-height: 200px; max-width: 100%;"></div></div>' : '';
        document.getElementById('project-title').innerHTML = '<div class="d-flex align-items-center flex-wrap gap-2"><h1 class="mb-0 me-2">' + escapeHtml(project.name) + '</h1>' + (showTags ? (statusBadge + approvalBadge) : '') + '</div>';
        if (showCarousel) {{
            document.getElementById('project-header').innerHTML =
                '<div class="row">' +
                    '<div class="col-lg-8">' +
                        '<div id="carousel-container"></div>' +
                    '</div>' +
                    '<div class="col-lg-4">' +
                        '<div class="card">' +
                            '<div class="card-header py-2"><strong>Actions</strong></div>' +
                            '<div class="card-body py-3">' + actionsHtml + '</div>' +
                        '</div>' +
                    '</div>' +
                '</div>';
        }} else {{
            document.getElementById('project-header').innerHTML =
                '<div class="row">' +
                    '<div class="col-md-8">' +
                        '<p class="lead">' + escapeHtml(project.description || 'No description') + '</p>' +
                    '</div>' +
                    '<div class="col-md-4">' +
                        imageHtml +
                        '<div class="card">' +
                            '<div class="card-header py-2"><strong>Actions</strong></div>' +
                            '<div class="card-body py-3">' + actionsHtml + '</div>' +
                        '</div>' +
                    '</div>' +
                '</div>';
        }}
    }}
    
    function loadOverview() {{
        const statusEsc = escapeHtml(String(project.status || ''));
        const approvalEsc = escapeHtml(String(project.approval_status || ''));
        const createdStr = project.created_at ? new Date(project.created_at).toLocaleDateString() : '—';
        const lastActivityStr = project.last_activity_at ? new Date(project.last_activity_at).toLocaleDateString() : 'Never';
        const wgCount = project.workgroups_count || 0;
        const layerInfoHtml = '<div class="row"><div class="col-md-6"><div class="card mb-4"><div class="card-header"><h5>Layer Information</h5></div><div class="card-body">' +
            '<p><strong>Status:</strong> ' + statusEsc + '</p>' +
            '<p><strong>Approval:</strong> ' + approvalEsc + '</p>' +
            '<p><strong>Created:</strong> ' + createdStr + '</p>' +
            '<p><strong>Last Activity:</strong> ' + lastActivityStr + '</p>' +
            '</div></div></div>' +
            '<div class="col-md-6"><div class="card mb-4"><div class="card-header"><h5>Quick Stats</h5></div><div class="card-body">' +
            '<p><strong>Workgroups:</strong> ' + wgCount + '</p>' +
            '<p><strong>Roles:</strong> <span id="roles-count">Loading...</span></p>' +
            '<p><strong>Active Claims:</strong> <span id="claims-count">Loading...</span></p>' +
            '</div></div></div></div>' +
            '<div class="row"><div class="col-12"><div class="card mb-4"><div class="card-header"><h5 class="mb-0"><i class="fas fa-stream me-2"></i>Recent Activity</h5></div><div class="card-body">' +
            '<div id="activity-feed-container"><div class="text-center py-3"><div class="spinner-border spinner-border-sm text-secondary"></div> Loading...</div></div>' +
            '</div></div></div></div>';
        document.getElementById('overview-content').innerHTML = layerInfoHtml;
        if (showCarousel) loadCarousel();
        loadRolesCounts();
        loadActivityFeed();
    }}
    
    async function loadCarousel() {{
        const container = document.getElementById('carousel-container');
        if (!container || !project) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/carousel/');
            const data = await res.json();
            const items = data.items || [];
            if (items.length === 0) {{
                container.innerHTML = '<div class="rounded p-4 text-center text-muted" style="background: var(--bg-secondary);"><p class="mb-0">No featured items yet. Drafts, roles, and opportunities will appear here.</p></div>';
                return;
            }}
            const imgPlaceholder = 'background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--border-color) 100%); color: var(--text-muted);';
            if (showCarousel) {{
                let slidesHtml = '';
                items.forEach((it, i) => {{
                    const isDraft = it.type === 'draft';
                    const hasAbstract = isDraft && it.description;
                    let img = '';
                    if (it.image) {{
                        img = '<img src="' + escapeHtmlBasic(it.image) + '" alt="" class="w-100" style="height:200px;object-fit:cover;">';
                    }} else if (hasAbstract) {{
                        img = '';
                    }} else {{
                        img = '<div class="d-flex align-items-center justify-content-center rounded-top" style="height:160px;' + imgPlaceholder + '"><i class="fas fa-' + (it.type === 'role' ? 'user-tag' : it.type === 'opportunity' ? 'bullseye' : 'file-alt') + ' fa-3x opacity-50"></i></div>';
                    }}
                    const descLen = hasAbstract ? 800 : 200;
                    const descHtml = it.description ? '<div class="mt-2"><p class="text-muted mb-0" style="white-space:pre-wrap;line-height:1.5;">' + escapeHtmlBasic((it.description || '').slice(0, descLen)) + (it.description && it.description.length > descLen ? '…' : '') + '</p></div>' : '';
                    let href = it.link ? escapeHtmlBasic(it.link) : '';
                    if (href && href.indexOf('/layers/') === 0 && href.includes('/#')) {{ href = href.replace('/layers/', '/layer/').replace('/#', '/'); if (!href.endsWith('/')) href += '/'; }}
                    const link = href ? 'href="' + href + '" class="text-decoration-none"' : '';
                    const bodyCls = hasAbstract ? 'p-4' : 'p-4';
                    slidesHtml += '<div class="carousel-slide" data-index="' + i + '" style="display:none;width:100%;max-width:720px;margin:0 auto;">' + (link ? '<a ' + link + ' style="color:inherit;">' : '') + '<div class="card overflow-hidden" style="background:transparent;border:none;">' + img + '<div class="card-body ' + bodyCls + '"><h5 class="mb-2">' + escapeHtmlBasic((it.title || '').slice(0, 100)) + '</h5>' + descHtml + '</div></div>' + (link ? '</a>' : '') + '</div>';
                }});
                container.innerHTML = '<style>.carousel-hero .carousel-prev, .carousel-hero .carousel-next {{ opacity: 0; transition: opacity 0.2s ease; }} .carousel-hero:hover .carousel-prev, .carousel-hero:hover .carousel-next {{ opacity: 1; }}</style>' +
                    '<div class="carousel-hero position-relative rounded overflow-hidden d-flex flex-column" style="background: var(--bg-secondary); min-height: 50vh;">' +
                    '<div class="carousel-slides flex-grow-1 d-flex align-items-center px-5" style="padding-left: 56px !important; padding-right: 56px !important;">' + slidesHtml + '</div>' +
                    '<button type="button" class="carousel-prev btn btn-light position-absolute top-50 start-0 translate-middle-y ms-2 rounded-circle shadow" style="width:44px;height:44px;z-index:2;" aria-label="Previous"><i class="fas fa-chevron-left"></i></button>' +
                    '<button type="button" class="carousel-next btn btn-light position-absolute top-50 end-0 translate-middle-y me-2 rounded-circle shadow" style="width:44px;height:44px;z-index:2;" aria-label="Next"><i class="fas fa-chevron-right"></i></button>' +
                    '<div class="carousel-dots position-absolute bottom-0 start-0 end-0 py-2 d-flex justify-content-center gap-2" style="z-index:2;"></div>' +
                    '</div>';
                const slides = container.querySelectorAll('.carousel-slide');
                const dots = container.querySelector('.carousel-dots');
                items.forEach((_, i) => {{ dots.innerHTML += '<button type="button" class="carousel-dot btn btn-sm rounded-circle p-0 ' + (i === 0 ? 'bg-primary' : 'bg-secondary') + '" data-index="' + i + '" style="width:8px;height:8px;" aria-label="Slide ' + (i+1) + '"></button>'; }});
                let idx = 0;
                function showSlide(i) {{ idx = ((i % items.length) + items.length) % items.length; slides.forEach((s, j) => {{ s.style.display = j === idx ? 'block' : 'none'; }}); container.querySelectorAll('.carousel-dot').forEach((d, j) => {{ d.className = 'carousel-dot btn btn-sm rounded-circle p-0 ' + (j === idx ? 'bg-primary' : 'bg-secondary'); }}); }}
                showSlide(0);
                container.querySelector('.carousel-prev').addEventListener('click', () => showSlide(idx - 1));
                container.querySelector('.carousel-next').addEventListener('click', () => showSlide(idx + 1));
                container.querySelectorAll('.carousel-dot').forEach(d => {{ d.addEventListener('click', () => showSlide(parseInt(d.getAttribute('data-index'), 10))); }});
            }}
        }} catch (e) {{
            console.error('loadCarousel:', e);
        }}
    }}
    
    function ensureArtifactFilterBar() {{
        const container = document.getElementById('artifacts-tab-container');
        if (!container || container.dataset.klFilterBar) return;
        container.dataset.klFilterBar = '1';
        const wrap = document.createElement('div');
        wrap.className = 'mb-3 d-flex flex-wrap gap-1 align-items-center';
        const forms = ['', 'inquiry', 'principle', 'model', 'conviction', 'decision', 'gloss', 'scenario'];
        let btns = '<span class="small text-muted me-2">Contribution:</span>';
        forms.forEach(function(kf, i) {{
            const label = kf || 'All';
            btns += '<button type="button" class="btn btn-sm btn-outline-secondary artifact-kf-btn' + (i === 0 ? ' active' : '') + '" data-kf="' + kf + '">' + label + '</button>';
        }});
        wrap.innerHTML = btns;
        container.parentNode.insertBefore(wrap, container);
        wrap.querySelectorAll('.artifact-kf-btn').forEach(function(btn) {{
            btn.addEventListener('click', function() {{
                wrap.querySelectorAll('.artifact-kf-btn').forEach(function(b) {{ b.classList.remove('active'); }});
                btn.classList.add('active');
                artifactKnowledgeFilter = btn.getAttribute('data-kf') || '';
                loadArtifacts();
            }});
        }});
    }}
    
    async function loadArtifacts() {{
        const container = document.getElementById('artifacts-tab-container');
        if (!container || !project) return;
        ensureArtifactFilterBar();
        try {{
            let url = '/api/layers/' + project.id + '/artifacts/';
            if (artifactKnowledgeFilter) url += '?knowledge_form=' + encodeURIComponent(artifactKnowledgeFilter);
            const res = await fetch(url, {{ credentials: 'same-origin' }});
            const data = await res.json();
            if (!res.ok) {{
                container.innerHTML = '<p class="text-muted small">Unable to load artifacts.</p>';
                return;
            }}
            const arts = data.artifacts || [];
            if (arts.length === 0) {{
                const msg = artifactKnowledgeFilter
                    ? 'No artifacts with this contribution type.'
                    : 'No artifacts yet. Submissions and quest outputs create artifacts.';
                container.innerHTML = '<p class="text-muted small mb-0">' + msg + '</p>';
                return;
            }}
            let html = '<ul class="list-group list-group-flush">';
            arts.forEach(a => {{
                const ref = a.public_ref || a.id;
                const title = escapeHtmlBasic((a.title || a.public_ref || 'Untitled').slice(0, 60));
                const kf = a.knowledge_form;
                const kfBadge = kf ? '<span class="badge text-bg-info ms-1">' + escapeHtmlBasic(kf) + '</span>' : '';
                const statusCls = (a.status === 'approved' || a.status === 'adopted') ? 'success' : (a.status === 'submitted' ? 'info' : 'secondary');
                html += '<li class="list-group-item d-flex justify-content-between align-items-center flex-wrap gap-1"><span><a href="' + layerBase + 'artifacts/' + ref + '/" class="text-decoration-none">' + title + '</a>' + kfBadge + '</span><span class="badge bg-' + statusCls + '">' + (a.status || 'draft') + '</span></li>';
            }});
            html += '</ul>';
            container.innerHTML = html;
        }} catch (err) {{
            console.error('loadArtifacts:', err);
            container.innerHTML = '<p class="text-muted small">Unable to load artifacts.</p>';
        }}
    }}
    
    async function loadOpportunities() {{
        const container = document.getElementById('opportunities-container') || document.getElementById('opportunities-content') || document.getElementById('opportunities-tab-container');
        if (!container || !project) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/opportunities/');
            const data = await res.json();
            if (!res.ok) {{
                container.innerHTML = '<p class="text-muted small">Unable to load opportunities.</p>';
                return;
            }}
            const ms = data.missing_support || [];
            const mo = data.missing_opposition || [];
            const oq = data.open_quests || [];
            if (ms.length === 0 && mo.length === 0 && oq.length === 0) {{
                container.innerHTML = '<p class="text-muted small mb-0">All drafts have support and opposition. No open quests. Great participation!</p>';
                return;
            }}
            let html = '<div class="row">';
            if (ms.length > 0) {{
                html += '<div class="col-md-6"><h6 class="text-success"><i class="fas fa-thumbs-up me-1"></i>Drafts needing support</h6><ul class="list-unstyled small">';
                ms.slice(0, 5).forEach(a => {{
                    html += '<li class="mb-1"><a href="/doc/draft/' + (a.draft_id || a.id) + '/" class="text-decoration-none">' + escapeHtmlBasic(a.title || 'Untitled') + '</a></li>';
                }});
                if (ms.length > 5) html += '<li class="text-muted">+' + (ms.length - 5) + ' more</li>';
                html += '</ul></div>';
            }}
            if (mo.length > 0) {{
                html += '<div class="col-md-6"><h6 class="text-danger"><i class="fas fa-thumbs-down me-1"></i>Drafts needing opposition</h6><ul class="list-unstyled small">';
                mo.slice(0, 5).forEach(a => {{
                    html += '<li class="mb-1"><a href="/doc/draft/' + (a.draft_id || a.id) + '/" class="text-decoration-none">' + escapeHtmlBasic(a.title || 'Untitled') + '</a></li>';
                }});
                if (mo.length > 5) html += '<li class="text-muted">+' + (mo.length - 5) + ' more</li>';
                html += '</ul></div>';
            }}
            if (oq.length > 0) {{
                html += '<div class="col-12 mt-2"><h6 class="text-primary"><i class="fas fa-tasks me-1"></i>Open quests</h6><ul class="list-unstyled small">';
                oq.slice(0, 5).forEach(q => {{
                    html += '<li class="mb-1"><span class="badge bg-secondary me-1">' + escapeHtmlBasic(q.quest_type || 'quest') + '</span><a href="' + layerBase + 'quests/' + q.id + '/" class="text-decoration-none">' + escapeHtmlBasic(q.title || 'Untitled') + '</a></li>';
                }});
                if (oq.length > 5) html += '<li class="text-muted">+' + (oq.length - 5) + ' more</li>';
                html += '</ul></div>';
            }}
            html += '</div>';
            container.innerHTML = html;
        }} catch (err) {{
            console.error('loadOpportunities:', err);
            container.innerHTML = '<p class="text-muted small">Unable to load opportunities.</p>';
        }}
    }}
    
    function formatActivityEvent(ev) {{
        const who = ev.actor_display_name || (ev.actor_type === 'user' ? 'A member' : 'System');
        const p = ev.payload || {{}};
        const timeAgo = (d) => {{
            const s = Math.floor((Date.now() - new Date(d)) / 1000);
            if (s < 60) return 'just now';
            if (s < 3600) return Math.floor(s/60) + 'm ago';
            if (s < 86400) return Math.floor(s/3600) + 'h ago';
            if (s < 604800) return Math.floor(s/86400) + 'd ago';
            return new Date(d).toLocaleDateString();
        }};
        let text = '';
        let tabId = null;
        switch (ev.event_type) {{
            case 'member_joined': text = who + ' joined as ' + (p.role || 'contributor'); break;
            case 'member_removed': text = who + ' left the layer'; break;
            case 'role_claimed': text = who + ' claimed a role'; tabId = 'claims'; break;
            case 'badge_nominated': text = who + ' was nominated for a badge'; tabId = 'claims'; break;
            case 'badge_approved': text = who + ' received a badge'; tabId = 'claims'; break;
            case 'badge_rejected': text = 'A badge request was rejected'; break;
            case 'vote_started': text = 'Vote started: ' + (p.title || 'Vote'); tabId = 'votes'; break;
            case 'vote_closed': text = 'Vote closed' + (p.result ? ' (' + p.result + ')' : ''); tabId = 'votes'; break;
            case 'ballot_cast': text = who + ' cast a ballot'; break;
            case 'layer_config_changed': text = who + ' updated layer settings'; break;
            case 'waitlist_joined': text = (ev.actor_type === 'email' ? 'Someone' : who) + ' joined waitlist' + (p.waitlist_name ? ': ' + p.waitlist_name : ''); break;
            case 'waitlist_left': text = who + ' left waitlist' + (p.waitlist_name ? ': ' + p.waitlist_name : ''); break;
            case 'artifact_created': text = p.artifact_type === 'submission' ? 'A draft was submitted' : p.artifact_type === 'support' ? who + ' added support' : p.artifact_type === 'opposition' ? who + ' added opposition' : 'New artifact created'; tabId = 'artifacts'; break;
            case 'artifact_updated': text = who + ' updated an artifact'; tabId = 'artifacts'; break;
            case 'artifact_status_changed': text = who + ' changed artifact status: ' + (p.old_status || '') + ' → ' + (p.new_status || ''); tabId = 'artifacts'; break;
            case 'artifact_linked': text = who + ' linked artifacts' + (p.relation_type ? ' (' + p.relation_type + ')' : ''); tabId = 'artifacts'; break;
            case 'contribution_type_set': text = (p.source === 'moderation' ? who + ' set contribution type (moderation): ' : who + ' set contribution type: ') + (p.knowledge_form || ''); tabId = 'artifacts'; break;
            case 'contribution_type_cleared': text = (p.source === 'moderation' ? who + ' cleared contribution type (moderation)' : who + ' cleared contribution type'); tabId = 'artifacts'; break;
            case 'brick_placed': text = who + ' placed a brick on Civic Mason'; break;
            default: text = ev.event_type.replace(/_/g, ' ');
        }}
        return {{ text, tabId, timeAgo: timeAgo(ev.created_at) }};
    }}
    
    async function loadActivityFeed() {{
        const container = document.getElementById('activity-feed-container');
        if (!container || !project) return;
        try {{
            const res = await fetch('/api/layers/' + project.id + '/activity/?limit=15');
            const data = await res.json();
            if (!res.ok) {{
                container.innerHTML = '<p class="text-muted small">Unable to load activity.</p>';
                return;
            }}
            const events = data.events || [];
            if (events.length === 0) {{
                container.innerHTML = '<p class="text-muted small mb-0">No activity yet. Join the layer or claim a role to get started.</p>';
                return;
            }}
            let html = '<ul class="list-unstyled mb-0">';
            events.forEach(ev => {{
                const {{ text, tabId, timeAgo }} = formatActivityEvent(ev);
                html += '<li class="d-flex justify-content-between align-items-start py-2 border-bottom border-light">';
                html += '<span class="small">' + (tabId ? '<span class="text-decoration-none activity-tab-link link-primary" style="cursor:pointer" data-tab="' + tabId + '">' + escapeHtmlBasic(text) + '</span>' : escapeHtmlBasic(text)) + '</span>';
                html += '<span class="text-muted small ms-2">' + timeAgo + '</span>';
                html += '</li>';
            }});
            html += '</ul>';
            container.innerHTML = html;
            container.querySelectorAll('.activity-tab-link[data-tab]').forEach(function(el) {{
                el.addEventListener('click', function(e) {{
                    e.preventDefault();
                    const tab = this.getAttribute('data-tab');
                    if (showCarousel) {{
                        window.location.href = '/layer/' + projectSlug + '/' + tab + '/';
                    }} else {{
                        switchToTab(tab);
                    }}
                }});
            }});
        }} catch (err) {{
            console.error('loadActivityFeed:', err);
            container.innerHTML = '<p class="text-muted small">Unable to load activity.</p>';
        }}
    }}
    
    async function loadRolesCounts() {{
        try {{
            const rolesResp = await fetch('/api/layers/' + project.id + '/roles/');
            const rolesData = await rolesResp.json();
            document.getElementById('roles-count').textContent = rolesData.count;
            
            const claimsResp = await fetch('/api/layers/' + project.id + '/claims/?status=active');
            const claimsData = await claimsResp.json();
            document.getElementById('claims-count').textContent = claimsData.count;
        }} catch (error) {{
            console.error('Error loading counts:', error);
        }}
    }}
    
    async function loadVotes() {{
        const container = document.getElementById('votes-content');
        if (!container || !project) {{
            console.log('loadVotes: container or project missing', {{container: !!container, project: !!project}});
            return;
        }}
        container.innerHTML = '<div class="py-4 text-center"><div class="spinner-border text-primary"></div></div>';
        try {{
            console.log('loadVotes: fetching from /api/layers/' + project.id + '/votes/');
            const res = await fetch('/api/layers/' + project.id + '/votes/');
            console.log('loadVotes: response status', res.status, res.ok);
            
            const data = await res.json();
            console.log('loadVotes: received data', data);
            
            if (!res.ok) {{
                console.error('loadVotes: API error', res.status, data.error || 'Unknown error');
                container.innerHTML = '<div class="alert alert-danger">Error loading votes: ' + (data.error || 'HTTP ' + res.status) + '</div>';
                return;
            }}
            const votes = data.votes || [];
            if (votes.length === 0) {{
                container.innerHTML = '<div class="alert alert-info">No votes yet. Layer admins can create a vote using the Create Vote button above.</div>';
                return;
            }}
            let html = '<div class="list-group">';
            votes.forEach(v => {{
                const statusBadge = v.status === 'active' ? '<span class="badge bg-success">Active</span>' : v.status === 'closed' ? '<span class="badge bg-secondary">Closed</span>' : v.status === 'scheduled' ? '<span class="badge bg-info">Scheduled</span>' : '<span class="badge bg-warning">' + (v.status || '') + '</span>';
                const resultBadge = v.result ? '<span class="badge bg-' + (v.result === 'passed' ? 'success' : v.result === 'failed' ? 'danger' : v.result === 'no_quorum' ? 'warning' : 'secondary') + ' ms-1">' + v.result + '</span>' : '';
                html += '<a href="/votes/' + v.public_id + '/" class="list-group-item list-group-item-action">';
                html += '<div class="d-flex w-100 justify-content-between"><h6 class="mb-1">' + escapeHtmlBasic(v.title) + '</h6>' + statusBadge + resultBadge + '</div>';
                html += '<p class="mb-1 small text-muted">' + escapeHtmlBasic(v.description || '') + '</p>';
                html += '<small>Start: ' + new Date(v.start_at).toLocaleString() + ' &middot; End: ' + new Date(v.end_at).toLocaleString() + '</small>';
                html += '</a>';
            }});
            html += '</div>';
            container.innerHTML = html;
        }} catch (error) {{
            console.error('Error loading votes:', error);
            container.innerHTML = '<div class="alert alert-danger">Error loading votes: ' + error.message + '</div>';
        }}
    }}
    
    function toggleVoteTypeFields() {{
        const isElection = document.getElementById('vote-type-election')?.checked;
        const subSec = document.getElementById('vote-submission-section');
        const roleSec = document.getElementById('vote-role-section');
        const subSelect = document.getElementById('vote-submission-id');
        if (subSec) subSec.classList.toggle('d-none', !!isElection);
        if (roleSec) roleSec.classList.toggle('d-none', !isElection);
        if (subSelect) subSelect.required = !isElection;
    }}
    
    async function showCreateVoteModal() {{
        document.getElementById('create-vote-alert').classList.add('d-none');
        document.getElementById('createVoteForm').reset();
        document.getElementById('vote-type-approval').checked = true;
        toggleVoteTypeFields();
        
        // Set timezone labels (handle both modal variants)
        const tzAbbr = new Date().toLocaleTimeString('en-us', {{timeZoneName:'short'}}).split(' ').pop();
        const startLabel = document.getElementById('timezone-start') || document.getElementById('timezone-start-at');
        const endLabel = document.getElementById('timezone-end') || document.getElementById('timezone-end-at');
        if (startLabel) startLabel.textContent = tzAbbr || 'your local time';
        if (endLabel) endLabel.textContent = tzAbbr || 'your local time';
        
        // Set default times: next hour + 7 days
        const now = new Date();
        const nextHour = new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours() + 1, 0, 0);
        const sevenDaysLater = new Date(nextHour.getTime() + 7 * 24 * 60 * 60 * 1000);
        
        const formatDatetimeLocal = (d) => {{
            const pad = (n) => String(n).padStart(2, '0');
            return d.getFullYear() + '-' + pad(d.getMonth()+1) + '-' + pad(d.getDate()) + 'T' + pad(d.getHours()) + ':' + pad(d.getMinutes());
        }};
        
        // Set default times (handle both modal variants)
        const startInput = document.getElementById('vote-start') || document.getElementById('vote-start-at');
        const endInput = document.getElementById('vote-end') || document.getElementById('vote-end-at');
        if (startInput) startInput.value = formatDatetimeLocal(nextHour);
        if (endInput) endInput.value = formatDatetimeLocal(sevenDaysLater);
        document.getElementById('vote-quorum').value = '1';
        document.getElementById('vote-threshold').value = '0.5';
        
        // Load submissions for this project
        const submissionSelect = document.getElementById('vote-submission-id');
        submissionSelect.innerHTML = '<option value="">Loading...</option>';
        try {{
            const res = await fetch('/api/layers/' + project.id + '/submissions/');
            const data = await res.json();
            const submissions = data.submissions || [];
            if (submissions.length === 0) {{
                submissionSelect.innerHTML = '<option value="">No approved drafts available</option>';
            }} else {{
                submissionSelect.innerHTML = '<option value="">Select a draft...</option>';
                submissions.forEach(s => {{
                    const label = s.ml_number ? (s.ml_number + ' - ' + (s.title || '')) : ((s.title || '') + ' (' + s.id + ')');
                    submissionSelect.innerHTML += '<option value="' + escapeHtmlBasic(String(s.id)) + '">' + escapeHtmlBasic(label) + '</option>';
                }});
            }}
        }} catch (e) {{
            submissionSelect.innerHTML = '<option value="">Error loading drafts</option>';
        }}
        
        // Load roles for election
        const roleSelect = document.getElementById('vote-role-id');
        if (roleSelect) {{
            roleSelect.innerHTML = '<option value="">Loading...</option>';
            try {{
                const rRes = await fetch('/api/layers/' + project.id + '/roles/');
                const rData = await rRes.json();
                const roles = rData.roles || [];
                roleSelect.innerHTML = '<option value="">Select a role...</option>';
                roles.forEach(r => {{
                    const lab = r.requires_election ? r.title_guild + ' (requires election)' : r.title_guild;
                    roleSelect.innerHTML += '<option value="' + escapeHtmlBasic(String(r.id)) + '">' + escapeHtmlBasic(lab) + '</option>';
                }});
            }} catch (e) {{
                roleSelect.innerHTML = '<option value="">Error loading roles</option>';
            }}
        }}
        
        toggleVoteTypeFields();
        const modal = new bootstrap.Modal(document.getElementById('createVoteModal'));
        modal.show();
    }}
    
    function toggleVoteTypeFields() {{
        const isElection = document.getElementById('vote-type-election')?.checked;
        const subSec = document.getElementById('vote-submission-section');
        const roleSec = document.getElementById('vote-role-section');
        const subSel = document.getElementById('vote-submission-id');
        if (subSec) subSec.classList.toggle('d-none', !!isElection);
        if (roleSec) roleSec.classList.toggle('d-none', !isElection);
        if (subSel) subSel.required = !isElection;
        const roleSel = document.getElementById('vote-role-id');
        if (roleSel) roleSel.required = !!isElection;
    }}
    
    async function showEmailModal() {{
        document.getElementById('email-modal-alert').classList.add('d-none');
        document.getElementById('emailForm').reset();
        const groupsEl = document.getElementById('email-recipient-groups');
        const fromEl = document.getElementById('email-from');
        groupsEl.innerHTML = '<div class="text-muted"><span class="spinner-border spinner-border-sm me-2"></span>Loading...</div>';
        fromEl.innerHTML = '<option>Loading...</option>';
        try {{
            const res = await fetch('/api/layers/' + project.id + '/email-recipients/');
            const data = await res.json();
            if (!res.ok) {{
                groupsEl.innerHTML = '<div class="text-danger">' + (data.error || 'Failed to load') + '</div>';
                return;
            }}
            const groups = data.groups || {{}};
            let html = '';
            for (const [key, info] of Object.entries(groups)) {{
                const count = info.count || 0;
                const label = info.label || key;
                html += '<div class="form-check"><input class="form-check-input" type="checkbox" value="' + escapeHtmlBasic(key) + '" id="email-grp-' + escapeHtmlBasic(key) + '"><label class="form-check-label" for="email-grp-' + escapeHtmlBasic(key) + '">' + escapeHtml(label) + ' (' + count + ')</label></div>';
            }}
            groupsEl.innerHTML = html || '<p class="text-muted mb-0">No recipient groups available.</p>';
            const fromOpts = data.from_options || [];
            fromEl.innerHTML = fromOpts.map(o => '<option value="' + escapeHtmlBasic(o.value) + '">' + escapeHtml(o.label) + '</option>').join('');
            const modal = new bootstrap.Modal(document.getElementById('emailModal'));
            modal.show();
        }} catch (e) {{
            groupsEl.innerHTML = '<div class="text-danger">Error: ' + escapeHtml(e.message) + '</div>';
        }}
    }}
    
    async function submitEmail() {{
        const groups = Array.from(document.querySelectorAll('#email-recipient-groups input:checked')).map(cb => cb.value);
        const fromAddr = document.getElementById('email-from').value;
        const subject = document.getElementById('email-subject').value.trim();
        const body = document.getElementById('email-body').value.trim();
        const alertEl = document.getElementById('email-modal-alert');
        alertEl.classList.add('d-none');
        if (!groups.length) {{
            alertEl.textContent = 'Select at least one recipient group';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        if (!subject || !body) {{
            alertEl.textContent = 'Subject and message are required';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        const btn = document.getElementById('email-submit-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';
        try {{
            const res = await fetch('/api/layers/' + project.id + '/send-email/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ groups: groups, subject: subject, body: body, from: fromAddr }})
            }});
            const data = await res.json();
            if (!res.ok) {{
                alertEl.textContent = data.error || 'Failed to send';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
                return;
            }}
            alertEl.textContent = 'Sent to ' + (data.sent || 0) + ' recipient(s).';
            alertEl.className = 'alert alert-success';
            alertEl.classList.remove('d-none');
            document.getElementById('emailForm').reset();
            setTimeout(() => {{
                bootstrap.Modal.getInstance(document.getElementById('emailModal')).hide();
            }}, 1500);
        }} catch (e) {{
            alertEl.textContent = 'Error: ' + e.message;
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
        }} finally {{
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-paper-plane me-2"></i>Send';
        }}
    }}
    
    async function submitCreateVote() {{
        const title = document.getElementById('vote-title').value.trim();
        const description = document.getElementById('vote-description').value.trim();
        const submission_id = document.getElementById('vote-submission-id').value.trim();
        const role_id = document.getElementById('vote-role-id')?.value?.trim() || '';
        const seats = parseInt(document.getElementById('vote-seats')?.value || '1', 10) || 1;
        const isElection = document.getElementById('vote-type-election')?.checked;
        const vote_type = isElection ? 'election' : 'approval';
        const startVal = document.getElementById('vote-start').value;
        const endVal = document.getElementById('vote-end').value;
        const quorum = parseInt(document.getElementById('vote-quorum').value, 10);
        const threshold = parseFloat(document.getElementById('vote-threshold').value);
        
        const alertEl = document.getElementById('create-vote-alert');
        alertEl.classList.add('d-none');
        if (!title || !startVal || !endVal) {{
            alertEl.textContent = 'Title, Start, and End are required';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        if (isElection && !role_id) {{
            alertEl.textContent = 'Role is required for election votes';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        if (!isElection && !submission_id) {{
            alertEl.textContent = 'Draft is required for approval votes';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        const startAt = new Date(startVal).toISOString();
        const endAt = new Date(endVal).toISOString();
        
        const btn = document.getElementById('create-vote-submit-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
        
        try {{
            const res = await fetch('/api/layers/' + project.id + '/votes/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    title: title,
                    description: description,
                    submission_id: submission_id || null,
                    role_id: role_id || null,
                    vote_type: vote_type,
                    seats: seats,
                    start_at: startAt,
                    end_at: endAt,
                    quorum_count: quorum,
                    win_threshold: threshold
                }})
            }});
            // Read body once as text, then parse as JSON
            const rawText = await res.text();
            let data = {{}};
            try {{ data = JSON.parse(rawText); }} catch {{}}
            
            if (res.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('createVoteModal')).hide();
                document.getElementById('votes-tab').click();
                loadVotes();
            }} else {{
                const msg = data.error || rawText.slice(0, 300) || 'HTTP ' + res.status;
                alertEl.textContent = msg;
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
            }}
        }} catch (e) {{
            console.error('Create vote fetch error:', e);
            alertEl.textContent = 'Network error: ' + e.message;
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
        }}
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-check me-2"></i>Create Vote';
    }}
    
    function showCreateQuestModal() {{
        const alertEl = document.getElementById('create-quest-alert');
        if (alertEl) alertEl.classList.add('d-none');
        const form = document.getElementById('createQuestForm');
        if (form) form.reset();
        const modal = new bootstrap.Modal(document.getElementById('createQuestModal'));
        modal.show();
    }}
    
    async function submitCreateQuest() {{
        const title = document.getElementById('quest-title').value.trim();
        const description = document.getElementById('quest-description').value.trim();
        const questType = document.getElementById('quest-type').value || 'contribution';
        const difficulty = document.getElementById('quest-difficulty').value || 'medium';
        const acceptanceCriteria = document.getElementById('quest-acceptance-criteria').value.trim();
        
        const alertEl = document.getElementById('create-quest-alert');
        alertEl.classList.add('d-none');
        if (!title) {{
            alertEl.textContent = 'Title is required';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        
        const btn = document.getElementById('create-quest-submit-btn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
        
        try {{
            const res = await fetch('/api/layers/' + project.id + '/quests/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{
                    title: title,
                    description: description || null,
                    quest_type: questType,
                    difficulty: difficulty,
                    acceptance_criteria: acceptanceCriteria || null
                }})
            }});
            const data = await res.json().catch(() => ({{}}));
            
            if (res.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('createQuestModal')).hide();
                document.getElementById('opportunities-tab').click();
                loadOpportunities();
            }} else {{
                alertEl.textContent = data.error || 'Failed to create quest';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
            }}
        }} catch (e) {{
            console.error('Create quest fetch error:', e);
            alertEl.textContent = 'Network error: ' + e.message;
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
        }}
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-check me-2"></i>Create Quest';
    }}
    
    // Tab event listeners (skip when standalone - no tabs in DOM)
    if (!showCarousel) {{
        document.getElementById('workgroups-tab').addEventListener('shown.bs.tab', loadWorkgroups);
        document.getElementById('clusters-tab').addEventListener('shown.bs.tab', loadClusters);
        document.getElementById('roles-tab').addEventListener('shown.bs.tab', loadRoles);
        document.getElementById('claims-tab').addEventListener('shown.bs.tab', loadClaims);
        document.getElementById('votes-tab').addEventListener('shown.bs.tab', loadVotes);
        document.getElementById('artifacts-tab').addEventListener('shown.bs.tab', loadArtifacts);
        document.getElementById('opportunities-tab').addEventListener('shown.bs.tab', loadOpportunities);
        {admin_tab_listener}
        
        ['overview-tab','workgroups-tab','clusters-tab','roles-tab','claims-tab','votes-tab','artifacts-tab','opportunities-tab'].forEach(function(id) {{
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', function() {{ clearHashIfNeeded(getProjectTabKey(id)); }}, true);
        }});
        
        const projectTabs = document.getElementById('projectTabs');
        if (projectTabs) {{
            projectTabs.addEventListener('shown.bs.tab', function(e) {{
                const tabKey = getProjectTabKey(e.target.id);
                if (tabKey) {{
                    const prevKey = localStorage.getItem('projectDetailTab_' + projectSlug + '_current');
                    saveTabState(tabKey, (prevKey && prevKey !== tabKey) ? prevKey : 'overview');
                    clearHashIfNeeded(tabKey);
                }}
            }});
            projectTabs.addEventListener('click', function(e) {{
                const btn = e.target.closest('[id^="waitlist-tab-"]');
                if (btn && btn.id && btn.id.match(/^waitlist-tab-(\\d+)$/)) {{
                    clearHashIfNeeded('waitlist-' + btn.id.match(/^waitlist-tab-(\\d+)$/)[1]);
                }}
            }}, true);
        }}
        
        if (window.location.hash && ['claims', 'votes'].includes(window.location.hash.replace(/^#/, ''))) {{
            setTimeout(switchToTabFromHash, 50);
        }}
    }}
    
    function clearHashIfNeeded(tabKey) {{
        const nonHashTabs = ['overview', 'workgroups', 'clusters', 'roles', 'admin'];
        const isNonHash = nonHashTabs.includes(tabKey) || (tabKey && tabKey.startsWith('waitlist-'));
        if (isNonHash && window.location.hash) {{
            saveTabState(tabKey, 'claims');
            const clean = window.location.origin + window.location.pathname + window.location.search;
            try {{ history.replaceState(null, '', clean); }} catch (e) {{}}
            if (window.location.hash) window.location.replace(clean);
        }}
    }}
    
    function buildWaitlistTabs(waitlists) {{
        const marker = document.getElementById('waitlist-tabs-marker');
        const paneMarker = document.getElementById('waitlist-panes-marker');
        if (!marker || !paneMarker) return;
        while (marker.previousElementSibling && marker.previousElementSibling.id && marker.previousElementSibling.id.startsWith('waitlist-tab-li-')) {{
            marker.previousElementSibling.remove();
        }}
        document.querySelectorAll('[id^="waitlist-pane-"]').forEach(el => el.remove());
        if (waitlists.length === 0) return;
        waitlists.forEach((w, idx) => {{
            const li = document.createElement('li');
            li.className = 'nav-item';
            li.id = 'waitlist-tab-li-' + w.id;
            li.innerHTML = '<button class="nav-link" id="waitlist-tab-' + w.id + '" data-bs-toggle="tab" data-bs-target="#waitlist-pane-' + w.id + '" type="button" data-waitlist-id="' + w.id + '">' + escapeHtmlBasic(w.name || '') + '</button>';
            marker.parentNode.insertBefore(li, marker);
            const pane = document.createElement('div');
            pane.className = 'tab-pane fade' + (idx === 0 ? '' : '');
            pane.id = 'waitlist-pane-' + w.id;
            pane.dataset.waitlistId = w.id;
            pane.innerHTML = '<div class="py-4 text-center"><div class="spinner-border text-primary"></div></div>';
            paneMarker.parentNode.insertBefore(pane, paneMarker);
            li.querySelector('button').addEventListener('shown.bs.tab', () => loadWaitlistPane(w.id));
        }});
    }}
    
    function showWaitlistInactiveMessage(waitlistId) {{
        const header = document.getElementById('project-header');
        const alert = document.createElement('div');
        alert.className = 'alert alert-warning alert-dismissible fade show';
        alert.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>This waitlist is no longer active.<button type="button" class="btn-close" data-bs-dismiss="alert"></button>';
        header.insertAdjacentElement('afterend', alert);
    }}
    
    async function loadWaitlistPane(waitlistId) {{
        const pane = document.getElementById('waitlist-pane-' + waitlistId);
        if (!pane || !project) return;
        pane.innerHTML = '<div class="py-4 text-center"><div class="spinner-border text-primary"></div></div>';
        try {{
            const res = await fetch('/api/layers/' + project.id + '/waitlists/');
            const data = await res.json();
            const w = (data.waitlists || []).find(x => x.id === waitlistId);
            if (!w) {{
                pane.innerHTML = '<div class="alert alert-warning">Waitlist not found or no longer active.</div>';
                return;
            }}
            const started = w.started !== false;
            const closed = w.closed === true;
            const full = w.full === true;
            const canJoin = isAuthenticated && started && !closed && !full && !w.my_entry;
            const countStr = w.max_number != null ? (w.count + ' of ' + w.max_number) : String(w.count);
            const closingStr = w.closing_date ? new Date(w.closing_date).toLocaleDateString() : '-';
                const link = w.referral_url || (window.location.origin + '/layers/' + projectSlug + '/waitlist/' + w.id + '/');
            const wName = escapeHtmlBasic(w.name || '');
            const wDesc = escapeHtmlBasic(w.description || 'No description');
            let milestonesHtml = '';
            if (w.milestones && w.milestones.length) {{
                const items = w.milestones.map(function(m) {{
                    return '<li><strong>' + escapeHtmlBasic(m.title || '') + '</strong> at ' + m.threshold + ' - ' + escapeHtmlBasic(m.description || '') + '</li>';
                }});
                milestonesHtml = '<div class="mt-3"><h6>Milestones</h6><ul class="list-unstyled small">' + items.join('') + '</ul></div>';
            }}
            let actionHtml = '';
            if (w.my_entry) {{
                actionHtml = '<span class="badge bg-success">Joined</span><span class="text-muted">Position #' + w.my_entry.position + '</span>';
            }} else if (canJoin) {{
                const wlNameForJs = (w.name || 'Waitlist').split("\\\\").join("\\\\\\\\").split("'").join("\\\\'");
                actionHtml = '<button class="btn btn-primary btn-sm" data-waitlist-id="' + (w.id || '').replace(/"/g, '&quot;') + '" data-waitlist-name="' + wlNameForJs.replace(/"/g, '&quot;') + '" onclick="showJoinWaitlistModal(this.dataset.waitlistId, this.dataset.waitlistName)">Join</button>';
            }} else if (!started) {{
                actionHtml = '<span class="badge bg-secondary">Not started</span>';
            }} else if (full) {{
                actionHtml = '<span class="badge bg-secondary">Full</span>';
            }} else if (closed) {{
                actionHtml = '<span class="badge bg-secondary">Closed</span>';
            }} else if (!isAuthenticated) {{
                actionHtml = '<a href="/login/" class="btn btn-primary btn-sm">Sign in to join</a>';
            }}
            const leaveBtn = w.my_entry ? '<button class="btn btn-outline-danger btn-sm" data-waitlist-id="' + (w.id || '').replace(/"/g, '&quot;') + '" onclick="leaveWaitlist(this.dataset.waitlistId)">Leave</button>' : '';
            const embedBtn = isProjectAdmin ? '<button class="btn btn-outline-primary btn-sm" onclick="showEmbedCodeFromEl(this)" data-waitlist-id="' + w.id + '" data-waitlist-name="' + (w.name || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;') + '"><i class="fas fa-code me-1"></i>Embed</button>' : '';
            const detailBtn = '<a href="/waitlists/' + w.id + '/" class="btn btn-outline-secondary btn-sm"><i class="fas fa-external-link-alt me-1"></i>Detail Page</a>';
            const linkHtml = w.referrals ? 'Your referral link: <a href="' + link + '" target="_blank">' + link + '</a>' : 'Link: <a href="' + link + '">' + link + '</a>';
            const dateStarted = w.start_date ? new Date(w.start_date).toLocaleDateString() : '-';
            const visibility = w.public ? 'Public' : 'Private';
            
            const wImg = (w.image_url) ? '<div class="mb-3"><img src="' + w.image_url + '" alt="' + wName + '" class="img-fluid rounded" style="max-height: 180px;"></div>' : '';
            const html = '<div class="card mb-4"><div class="card-body">' +
                '<nav aria-label="breadcrumb"><ol class="breadcrumb mb-2"><li class="breadcrumb-item"><a href="' + (showCarousel ? layerBase : '/layers/') + '">' + (showCarousel ? escapeHtmlBasic(project.name) : 'Layers') + '</a></li>' + (showCarousel ? '' : '<li class="breadcrumb-item"><a href="/layers/' + projectSlug + '/">' + escapeHtmlBasic(project.name) + '</a></li>') + '<li class="breadcrumb-item active">' + wName + ' Waitlist</li></ol></nav>' +
                wImg +
                '<h5 class="card-title">' + wName + '</h5>' +
                '<p class="text-muted">' + wDesc + '</p>' +
                '<p class="small mb-2">Date started: ' + dateStarted + ' · ' + visibility + '</p>' +
                '<p class="small">' + linkHtml + '</p>' +
                '<div class="d-flex flex-wrap align-items-center gap-3 mt-3">' +
                actionHtml +
                embedBtn +
                detailBtn +
                '<span class="text-muted">' + countStr + ' on waitlist</span>' +
                '<span class="text-muted">Closing: ' + closingStr + '</span>' +
                leaveBtn +
                '</div>' + milestonesHtml + '</div></div>';
            pane.innerHTML = html;
        }} catch (e) {{
            console.error(e);
            pane.innerHTML = '<div class="alert alert-danger">Error loading waitlist</div>';
        }}
    }}
    
    let pendingWaitlistId = null;
    
    function showJoinWaitlistModal(waitlistId, waitlistName) {{
        if (!isAuthenticated) {{ alert('Please sign in to join this waitlist'); return; }}
        pendingWaitlistId = waitlistId;
        const titleEl = document.getElementById('join-waitlist-modal-title');
        if (titleEl) titleEl.innerHTML = '<i class="fas fa-list-alt me-2"></i>Join: ' + escapeHtmlBasic(waitlistName || 'Waitlist');
        const msgEl = document.getElementById('join-waitlist-message');
        if (msgEl) msgEl.value = '';
        const modal = new bootstrap.Modal(document.getElementById('joinWaitlistModal'));
        modal.show();
    }}
    
    async function submitJoinWaitlistModal() {{
        if (!pendingWaitlistId) return;
        const msgEl = document.getElementById('join-waitlist-message');
        const msg = msgEl ? msgEl.value : '';
        try {{
            const body = {{ message: msg || '' }};
            if (referralRef) body.referral_code = referralRef;
            const res = await fetch('/api/waitlists/' + pendingWaitlistId + '/join/', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json' }}, body: JSON.stringify(body) }});
            const data = await res.json();
            if (res.ok) {{
                loadWaitlistPane(pendingWaitlistId);
                bootstrap.Modal.getInstance(document.getElementById('joinWaitlistModal')).hide();
            }} else {{ alert(data.error || 'Failed to join'); }}
        }} catch (e) {{ alert('Failed to join'); }}
        pendingWaitlistId = null;
    }}
    
    async function leaveWaitlist(waitlistId) {{
        if (!confirm('Leave this waitlist?')) return;
        try {{
            const res = await fetch('/api/waitlists/' + waitlistId + '/leave/', {{ method: 'POST' }});
            if (res.ok) loadWaitlistPane(waitlistId); else {{ const d = await res.json(); alert(d.error || 'Failed to leave'); }}
        }} catch (e) {{ alert('Failed to leave'); }}
    }}
    
    async function loadAdmins() {{
        const container = document.getElementById('admin-content');
        if (!container) return;
        container.innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/');
            if (response.status === 403) {{
                container.innerHTML = '<div class="alert alert-warning">You do not have permission to view layer admins.</div>';
                return;
            }}
            const data = await response.json();
            
            const ownerUserEsc = escapeHtmlBasic(data.owner.username || '');
            const ownerNameEsc = escapeHtml(data.owner.display_name || '');
            let html = '<div class="d-flex justify-content-between align-items-center mb-3"><h4>Layer admins</h4><button class="btn btn-primary btn-sm" onclick="showAddAdminModal()"><i class="fas fa-plus me-2"></i>Add admin</button></div><p class="text-muted">Admins can manage workgroups, roles, claims, and other admins. The owner cannot be removed.</p><div class="list-group"><div class="list-group-item d-flex justify-content-between align-items-center"><div><a href="/profile/' + ownerUserEsc + '/" class="fw-bold text-decoration-none">' + ownerNameEsc + '</a><span class="badge bg-primary ms-2">Owner</span></div><span class="text-muted">—</span></div>';
            (data.admins || []).forEach(a => {{
                html += '<div class="list-group-item d-flex justify-content-between align-items-center"><a href="/profile/' + escapeHtmlBasic(a.username || '') + '/" class="text-decoration-none">' + escapeHtml(a.display_name || '') + '</a><button class="btn btn-outline-danger btn-sm" onclick="removeAdmin(\\'' + (a.user_id || '') + '\\', this)">Remove</button></div>';
            }});
            html += '</div>';
            
            // Add pending workgroups section for approval
            html += '<hr class="my-4"><h4 class="mb-3">Pending workgroups</h4>';
            const wgResponse = await fetch('/api/layers/' + project.id + '/workgroups/?approval_status=pending');
            const wgData = await wgResponse.json();
            if (wgData.workgroups && wgData.workgroups.length > 0) {{
                html += '<div class="list-group">';
                wgData.workgroups.forEach(wg => {{
                    const wgNameEsc = escapeHtml(wg.name || '');
                    const wgDescEsc = escapeHtml(wg.description || 'No description');
                    const wgIdEsc = escapeForJsAttr(String(wg.id || ''));
                    html += '<div class="list-group-item"><div class="d-flex justify-content-between align-items-start"><div><h6 class="mb-1">' + wgNameEsc + '</h6><p class="mb-1 text-muted small">' + wgDescEsc + '</p></div><div class="btn-group btn-group-sm"><button class="btn btn-success" onclick="approveWorkgroup(\\'' + wgIdEsc + '\\')"><i class="fas fa-check me-1"></i>Approve</button><button class="btn btn-danger" onclick="rejectWorkgroup(\\'' + wgIdEsc + '\\')"><i class="fas fa-times me-1"></i>Reject</button></div></div></div>';
                }});
                html += '</div>';
            }} else {{
                html += '<p class="text-muted">No pending workgroups</p>';
            }}
            
            // Add waitlist management section
            html += '<hr class="my-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>Waitlists</h4><button class="btn btn-primary btn-sm" onclick="createWaitlist()"><i class="fas fa-plus me-2"></i>Create Waitlist</button></div>';
            const wlResponse = await fetch('/api/layers/' + project.id + '/waitlists/');
            const wlData = await wlResponse.json();
            if (wlData.waitlists && wlData.waitlists.length > 0) {{
                html += '<div class="list-group">';
                wlData.waitlists.forEach(wl => {{
                    const statusBadge = wl.active ? '<span class="badge bg-success">Active</span>' : '<span class="badge bg-secondary">Inactive</span>';
                    const wlNameEsc = escapeHtmlBasic(wl.name || '');
                    const wlDescEsc = escapeHtmlBasic(wl.description || 'No description');
                    const wlNameAttr = (wl.name || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
                    html += '<div class="list-group-item"><div class="d-flex justify-content-between align-items-start">' +
                        '<div class="flex-grow-1">' +
                        '<h6 class="mb-1"><a href="/waitlists/' + wl.id + '/" class="text-decoration-none">' + wlNameEsc + '</a> ' + statusBadge + '</h6>' +
                        '<p class="mb-1 text-muted small">' + wlDescEsc + '</p>' +
                        '<p class="mb-0 small text-muted">Members: ' + wl.count + (wl.max_number ? ' / ' + wl.max_number : '') + '</p>' +
                        '</div><div class="btn-group btn-group-sm">' +
                        '<button class="btn btn-outline-primary" onclick="showEmbedCodeFromEl(this)" data-waitlist-id="' + wl.id + '" data-waitlist-name="' + wlNameAttr + '"><i class="fas fa-code"></i></button>' +
                        '<a href="/waitlists/' + wl.id + '/" class="btn btn-outline-secondary"><i class="fas fa-external-link-alt"></i></a>' +
                        '</div></div></div>';
                }});
                html += '</div>';
            }} else {{
                html += '<p class="text-muted">No waitlists yet. Create one to start collecting signups.</p>';
            }}
            
            // About page section
            html += '<hr class="my-4"><div class="d-flex justify-content-between align-items-center mb-3"><h4>About Page</h4><a href="' + layerBase + 'about/" class="btn btn-outline-secondary btn-sm" target="_blank">View</a></div>';
            const aboutEsc = (project.about_content || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
            html += '<p class="text-muted small mb-2">Markdown content for the layer About page. Supports images via URLs.</p>';
            html += '<textarea class="form-control font-monospace mb-2" id="about-content-edit" rows="10" placeholder="# About this layer\\n\\nWrite your layer description in markdown...">' + aboutEsc + '</textarea>';
            html += '<button class="btn btn-primary btn-sm" id="save-about-btn" onclick="saveAboutContent()"><i class="fas fa-save me-1"></i>Save About</button>';
            
            // Carousel config section
            let carouselConfig = {{ auto_items: {{ recent_drafts: true, open_roles: true, open_opportunities: true }}, custom_items: [] }};
            try {{ if (project.carousel_config) carouselConfig = JSON.parse(project.carousel_config); }} catch(e) {{}}
            const cc = carouselConfig.auto_items || carouselConfig.autoItems || {{}};
            const recentDrafts = cc.recent_drafts !== false;
            const openRoles = cc.open_roles !== false;
            const openOpps = cc.open_opportunities !== false;
            html += '<hr class="my-4"><h4 class="mb-3">Carousel</h4><p class="text-muted small mb-2">Show items in the overview carousel. Auto items are generated from layer data.</p>';
            html += '<div class="form-check form-check-inline mb-2"><input class="form-check-input" type="checkbox" id="cc-recent-drafts" ' + (recentDrafts ? 'checked' : '') + '><label class="form-check-label" for="cc-recent-drafts">Recent drafts</label></div>';
            html += '<div class="form-check form-check-inline mb-2"><input class="form-check-input" type="checkbox" id="cc-open-roles" ' + (openRoles ? 'checked' : '') + '><label class="form-check-label" for="cc-open-roles">Open roles</label></div>';
            html += '<div class="form-check form-check-inline mb-2"><input class="form-check-input" type="checkbox" id="cc-open-opportunities" ' + (openOpps ? 'checked' : '') + '><label class="form-check-label" for="cc-open-opportunities">Open opportunities</label></div>';
            html += '<div class="mt-2"><button class="btn btn-primary btn-sm" onclick="saveCarouselConfig()"><i class="fas fa-save me-1"></i>Save Carousel</button></div>';
            html += '<div class="mt-3"><h6 class="mb-2">Custom items</h6><div id="carousel-custom-items"></div><button class="btn btn-outline-primary btn-sm mt-2" onclick="addCarouselCustomItem()"><i class="fas fa-plus me-1"></i>Add custom item</button></div>';
            
            container.innerHTML = html;
            renderCarouselCustomItems(carouselConfig.custom_items || []);
        }} catch (error) {{
            console.error('Error loading admins:', error);
            container.innerHTML = '<div class="alert alert-danger">Error loading admins</div>';
        }}
    }}
    
    async function saveAboutContent() {{
        const textarea = document.getElementById('about-content-edit');
        if (!textarea || !project) return;
        const content = textarea.value;
        const btn = document.getElementById('save-about-btn');
        if (btn) {{ btn.disabled = true; btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving...'; }}
        try {{
            const res = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ about_content: content }}),
                credentials: 'include'
            }});
            const data = await res.json();
            if (res.ok) {{
                project.about_content = content;
                if (btn) {{ btn.disabled = false; btn.innerHTML = '<i class="fas fa-save me-1"></i>Save About'; }}
                alert('About page saved!');
            }} else {{
                if (btn) {{ btn.disabled = false; btn.innerHTML = '<i class="fas fa-save me-1"></i>Save About'; }}
                alert(data.error || 'Failed to save');
            }}
        }} catch (e) {{
            if (btn) {{ btn.disabled = false; btn.innerHTML = '<i class="fas fa-save me-1"></i>Save About'; }}
            alert('Failed to save');
        }}
    }}
    
    let carouselCustomItems = [];
    function renderCarouselCustomItems(items) {{
        carouselCustomItems = items || [];
        const container = document.getElementById('carousel-custom-items');
        if (!container) return;
        if (carouselCustomItems.length === 0) {{
            container.innerHTML = '<p class="text-muted small">No custom items. Add one to feature specific content.</p>';
            return;
        }}
        let html = '<div class="list-group list-group-flush">';
        carouselCustomItems.forEach((it, idx) => {{
            html += '<div class="list-group-item d-flex justify-content-between align-items-start py-2"><div><strong>' + escapeHtmlBasic((it.title || '').slice(0, 40)) + '</strong>';
            if (it.link) html += '<br><small class="text-muted">' + escapeHtmlBasic((it.link || '').slice(0, 50)) + '</small>';
            html += '</div><div><button class="btn btn-outline-danger btn-sm" onclick="removeCarouselCustomItem(' + idx + ')"><i class="fas fa-trash"></i></button></div></div>';
        }});
        html += '</div>';
        container.innerHTML = html;
    }}
    function addCarouselCustomItem() {{
        const title = prompt('Title for this carousel item:');
        if (!title) return;
        const link = prompt('Link URL (optional):', '');
        const description = prompt('Description (optional):', '');
        const image = prompt('Image URL (optional):', '');
        carouselCustomItems.push({{ title: title.trim(), link: (link || '').trim() || null, description: (description || '').trim() || null, image: (image || '').trim() || null }});
        renderCarouselCustomItems(carouselCustomItems);
    }}
    function removeCarouselCustomItem(idx) {{
        carouselCustomItems.splice(idx, 1);
        renderCarouselCustomItems(carouselCustomItems);
    }}
    async function saveCarouselConfig() {{
        if (!project) return;
        const config = {{
            auto_items: {{
                recent_drafts: document.getElementById('cc-recent-drafts').checked,
                open_roles: document.getElementById('cc-open-roles').checked,
                open_opportunities: document.getElementById('cc-open-opportunities').checked
            }},
            custom_items: carouselCustomItems
        }};
        try {{
            const res = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ carousel_config: config }}),
                credentials: 'include'
            }});
            const data = await res.json();
            if (res.ok) {{
                project.carousel_config = JSON.stringify(config);
                loadOverview();
                alert('Carousel saved!');
            }} else {{
                alert(data.error || 'Failed to save');
            }}
        }} catch (e) {{
            alert('Failed to save');
        }}
    }}
    
    async function approveWorkgroup(wgId) {{
        if (!confirm('Approve this workgroup?')) return;
        try {{
            const response = await fetch('/api/workgroups/' + wgId + '/approve/', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{action: 'approve'}})
            }});
            if (response.ok) {{
                loadAdmins();
                loadWorkgroups();
                alert('Workgroup approved!');
            }} else {{
                const data = await response.json();
                alert(data.error || 'Failed to approve workgroup');
            }}
        }} catch (e) {{
            alert('Failed to approve workgroup');
        }}
    }}
    
    async function rejectWorkgroup(wgId) {{
        if (!confirm('Reject this workgroup?')) return;
        try {{
            const response = await fetch('/api/workgroups/' + wgId + '/approve/', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{action: 'reject'}})
            }});
            if (response.ok) {{
                loadAdmins();
                loadWorkgroups();
                alert('Workgroup rejected');
            }} else {{
                const data = await response.json();
                alert(data.error || 'Failed to reject workgroup');
            }}
        }} catch (e) {{
            alert('Failed to reject workgroup');
        }}
    }}
    
    function showAddAdminModal() {{
        const modal = new bootstrap.Modal(document.getElementById('addAdminModal'));
        document.getElementById('add-admin-username').value = '';
        document.getElementById('add-admin-results').innerHTML = '';
        modal.show();
    }}
    
    async function searchUsersForAdmin() {{
        const q = document.getElementById('add-admin-username').value.trim();
        const resultsEl = document.getElementById('add-admin-results');
        if (q.length < 2) {{ resultsEl.innerHTML = ''; return; }}
        const response = await fetch('/api/users/search/?q=' + encodeURIComponent(q));
        const data = await response.json();
        if (data.users.length === 0) {{
            resultsEl.innerHTML = '<p class="text-muted small">No users found</p>';
            return;
        }}
        resultsEl.innerHTML = data.users.map(u => {{
            const uNameEsc = escapeHtml(u.display_name || '');
            const uUserEsc = escapeHtml(u.username || '');
            const uIdEsc = escapeForJsAttr(String(u.id || ''));
            return '<div class="d-flex justify-content-between align-items-center border-bottom py-2"><span>' + uNameEsc + ' <small class="text-muted">@' + uUserEsc + '</small></span><button class="btn btn-sm btn-primary" onclick="addAdmin(\\'' + uIdEsc + '\\')">Add</button></div>';
        }}).join('');
    }}
    
    async function addAdmin(userId) {{
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ user_id: userId }})
            }});
            const data = await response.json();
            if (response.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('addAdminModal')).hide();
                loadAdmins();
            }} else {{
                alert(data.error || 'Failed to add admin');
            }}
        }} catch (e) {{
            alert('Failed to add admin');
        }}
    }}
    
    async function removeAdmin(userId, btn) {{
        const displayName = (btn && btn.closest('.list-group-item')) ? btn.closest('.list-group-item').querySelector('a').textContent : 'this user';
        if (!confirm('Remove "' + displayName + '" as layer admin?')) return;
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/' + userId + '/', {{ method: 'DELETE' }});
            const data = await response.json();
            if (response.ok) {{
                loadAdmins();
            }} else {{
                alert(data.error || 'Failed to remove admin');
            }}
        }} catch (e) {{
            alert('Failed to remove admin');
        }}
    }}
    
    async function loadWorkgroups() {{
        document.getElementById('workgroups-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/workgroups/');
            const data = await response.json();
            
            const wgBtn = isAuthenticated ? '<button class="btn btn-primary btn-sm" onclick="createWorkgroup()"><i class="fas fa-plus me-2"></i>Create Workgroup</button>' : '';
            let html = '<div class="d-flex justify-content-between mb-3"><h4>Workgroups (' + (data.count || 0) + ')</h4>' + wgBtn + '</div>';
            
            if (data.workgroups.length === 0) {{
                html += '<div class="alert alert-info">No workgroups yet</div>';
            }} else {{
                html += '<div class="row">';
                data.workgroups.forEach(wg => {{
                    const approvalBadge = wg.approval_status === 'pending' ? '<span class="badge bg-warning ms-2">Pending Approval</span>' : (wg.approval_status === 'rejected' ? '<span class="badge bg-danger ms-2">Rejected</span>' : '');
                    const wgImg = wg.image_url ? '<div class="card-img-top overflow-hidden" style="height: 120px; background: var(--bg-secondary, #f8f9fa);"><img src="' + escapeHtmlBasic(wg.image_url) + '" alt="' + escapeHtmlBasic(wg.name) + '" class="w-100 h-100 object-fit-cover"></div>' : '';
                    const wgNameEsc = escapeHtml(wg.name || '');
                    const wgDescEsc = escapeHtml(wg.description || 'No description');
                    const wgSlugEsc = escapeHtmlBasic(wg.slug || '');
                    const wgStatusEsc = escapeHtml(String(wg.status || ''));
                    html += '<div class="col-md-6 mb-3"><div class="card">' + wgImg + '<div class="card-body"><h5 class="card-title"><a href="/workgroups/' + wgSlugEsc + '/">' + wgNameEsc + '</a></h5><p class="card-text text-muted">' + wgDescEsc + '</p><span class="badge bg-' + (wg.status === 'active' ? 'success' : 'secondary') + '">' + wgStatusEsc + '</span>' + approvalBadge + '</div></div></div>';
                }});
                html += '</div>';
            }}
            
            document.getElementById('workgroups-content').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading workgroups:', error);
            document.getElementById('workgroups-content').innerHTML = '<div class="alert alert-danger">Error loading workgroups</div>';
        }}
    }}
    
    async function loadClusters() {{
        document.getElementById('clusters-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/clusters/?include_roles=1');
            const data = await response.json();
            
            const clusterBtn = isProjectAdmin ? '<button class="btn btn-primary btn-sm" onclick="createCluster()"><i class="fas fa-plus me-2"></i>Create Cluster</button>' : '';
            let html = '<div class="d-flex justify-content-between mb-3"><h4>Role Clusters (' + (data.count || 0) + ')</h4>' + clusterBtn + '</div><p class="text-muted">Clusters group related roles together for better organization.</p>';
            
            const clusters = Array.isArray(data.clusters) ? data.clusters : [];
            if (clusters.length === 0) {{
                html += '<div class="alert alert-info">No clusters yet. Create one to organize your roles!</div>';
            }} else {{
                html += '<div class="row">';
                clusters.forEach(cluster => {{
                    if (!cluster) return;
                    const cName = (cluster.name != null && cluster.name !== '') ? cluster.name : 'Unnamed';
                    const cNameEsc = escapeForJsAttr(cName);
                    const cDescEsc = escapeHtml(cluster.description || 'No description');
                    const roles = cluster.roles || [];
                    const rolesHtml = roles.length
                        ? '<ul class="list-unstyled mb-0 mt-2 small">' + roles.map(r => '<li><a href="/layer/' + (project.slug || project.id || '') + '/roles/' + escapeHtmlBasic(r.role_slug || r.slug || '') + '/">' + escapeHtml(r.title_guild || r.title_operational || 'Role') + '</a></li>').join('') + '</ul>'
                        : '<p class="text-muted small mb-0 mt-2">No roles in this cluster</p>';
                    const orderStr = cluster.order != null ? cluster.order : '—';
                    const adminBtns = isProjectAdmin ? '<div class="btn-group btn-group-sm"><button class="btn btn-outline-secondary" onclick="editCluster(\\'' + (cluster.id || '') + '\\')"><i class="fas fa-edit"></i></button><button class="btn btn-outline-danger" onclick="deleteCluster(\\'' + (cluster.id || '') + '\\', \\'' + cNameEsc + '\\')"><i class="fas fa-trash"></i></button></div>' : '';
                    html += '<div class="col-md-6 mb-3"><div class="card"><div class="card-body"><div class="d-flex justify-content-between align-items-start"><div><h5 class="card-title">' + escapeHtml(cName) + '</h5><p class="card-text text-muted">' + cDescEsc + '</p><small class="text-muted">Order: ' + orderStr + '</small><div class="mt-2"><strong>Roles:</strong> ' + rolesHtml + '</div></div>' + adminBtns + '</div></div></div></div>';
                }});
                html += '</div>';
            }}
            
            document.getElementById('clusters-content').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading clusters:', error);
            document.getElementById('clusters-content').innerHTML = '<div class="alert alert-danger">Error loading clusters</div>';
        }}
    }}
    
    async function loadRoles() {{
        document.getElementById('roles-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/roles/');
            const data = await response.json();
            
            const roleBtn = isProjectAdmin ? '<button class="btn btn-primary btn-sm" onclick="createRole()"><i class="fas fa-plus me-2"></i>Create Role</button>' : '';
            let html = '<div class="d-flex justify-content-between mb-3"><h4>Roles (' + (data.count || 0) + ')</h4>' + roleBtn + '</div>';
            
            if (data.roles.length === 0) {{
                html += '<div class="alert alert-info">No roles yet</div>';
            }} else {{
                html += '<div class="row">';
                data.roles.forEach(role => {{
                    const roleSlugEsc = escapeHtmlBasic(role.role_slug || '');
                    const titleGuildEsc = escapeHtml(role.title_guild || '');
                    const titleOpEsc = role.title_operational ? '<h6 class="card-subtitle mb-2 text-muted">' + escapeHtml(role.title_operational) + '</h6>' : '';
                    const descEsc = escapeHtml((role.description || '').substring(0, 150));
                    const statusEsc = escapeHtml(String(role.status || ''));
                    const statusClass = role.status === 'approved' ? 'success' : 'warning';
                    const publicBadge = role.public_visible ? '<span class="badge bg-info ms-2">Public</span>' : '';
                    html += '<div class="col-md-6 mb-3"><div class="card"><div class="card-body"><h5 class="card-title"><a href="/layer/' + (project.slug || project.id || '') + '/roles/' + roleSlugEsc + '/">' + titleGuildEsc + '</a></h5>' + titleOpEsc + '<p class="card-text">' + descEsc + '...</p><span class="badge bg-' + statusClass + '">' + statusEsc + '</span>' + publicBadge + '</div></div></div>';
                }});
                html += '</div>';
            }}
            
            document.getElementById('roles-content').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading roles:', error);
            document.getElementById('roles-content').innerHTML = '<div class="alert alert-danger">Error loading roles</div>';
        }}
    }}
    
    async function loadClaims() {{
        document.getElementById('claims-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        
        try {{
            const response = await fetch('/api/layers/' + project.id + '/claims/');
            const data = await response.json();
            
            let html = '<h4 class="mb-3">Claims (' + (data.count || 0) + ')</h4>';
            
            if (!data.claims || data.claims.length === 0) {{
                html += '<div class="alert alert-info">No claims yet</div>';
            }} else {{
                html += '<div class="table-responsive"><table class="table table-hover"><thead><tr><th>Claim</th><th>Status</th><th>Role</th><th>User</th></tr></thead><tbody>';
                data.claims.forEach((claim, idx) => {{
                    const claimName = claim.role_name ? (claim.intent ? (claim.intent.substring(0, 40) + (claim.intent.length > 40 ? '…' : '')) : ('Claim: ' + claim.role_name)) : ('Claim #' + (claim.id || '').toString().slice(-6));
                    const roleName = claim.role_name || ('Role ' + (claim.role_id || '').toString().slice(-6));
                    const roleLink = claim.role_slug ? '/layer/' + (project.slug || project.id || '') + '/roles/' + escapeHtmlBasic(claim.role_slug) + '/' : '#';
                    const userName = claim.claimant_name || ('User #' + (claim.claimant_id || ''));
                    const userLink = claim.claimant_username ? '/profile/' + escapeHtmlBasic(claim.claimant_username) + '/' : '#';
                    const statusClass = claim.status === 'active' ? 'success' : (claim.status === 'pending_approval' ? 'warning' : 'secondary');
                    const claimNameEsc = escapeHtml(claimName);
                    const roleNameEsc = escapeHtml(roleName);
                    const userNameEsc = escapeHtml(userName);
                    const statusEsc = escapeHtml(claim.status || '—');
                    const tdRole = claim.role_slug ? '<a href="' + roleLink + '">' + roleNameEsc + '</a>' : roleNameEsc;
                    const tdUser = claim.claimant_username ? '<a href="' + userLink + '">' + userNameEsc + '</a>' : userNameEsc;
                    html += '<tr class="project-claim-row" data-claim-index="' + idx + '" tabindex="0" title="Hover for claim details"><td>' + claimNameEsc + '</td><td><span class="badge bg-' + statusClass + '">' + statusEsc + '</span></td><td>' + tdRole + '</td><td>' + tdUser + '</td></tr>';
                }});
                html += '</tbody></table></div>';
            }}
            
            document.getElementById('claims-content').innerHTML = html;
            
            // Attach claim popover (same content as role detail page) on hover
            if (data.claims && data.claims.length > 0) {{
                function getClaimPopoverContent(c) {{
                    const intent = c.intent ? '<p class="mb-2"><strong>Intent:</strong><br><span style="white-space: pre-wrap; word-wrap: break-word;">' + (c.intent || '').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</span></p>' : '';
                    const links = (c.evidence_links || []).filter(u => u && u.trim());
                    const evidenceHtml = links.length ? links.map(u => '<a href="' + u + '" target="_blank" rel="noopener">' + u + '</a>').join('<br>') : '<span class="text-muted">No evidence yet</span>';
                    const termStr = c.term_duration_days ? (c.term_duration_days + ' days' + (c.term_end ? ', until ' + new Date(c.term_end).toLocaleDateString() : '')) : 'Indefinite';
                    return '<div class="text-start" style="min-width: 280px; max-width: 480px; white-space: normal; word-wrap: break-word;">' + intent +
                        '<p class="mb-2"><strong>Supporting work:</strong><br>' + evidenceHtml + '</p>' +
                        '<p class="mb-2"><strong>Term:</strong> ' + termStr + '</p>' +
                        '<p class="mb-0 small text-muted">Claimed: ' + new Date(c.created_at).toLocaleDateString() + '</p></div>';
                }}
                document.querySelectorAll('.project-claim-row').forEach(el => {{
                    const idx = parseInt(el.getAttribute('data-claim-index'), 10);
                    const claim = data.claims[idx];
                    if (claim) {{
                        new bootstrap.Popover(el, {{ content: getClaimPopoverContent(claim), html: true, trigger: 'hover focus', placement: 'auto', container: 'body' }});
                    }}
                }});
            }}
        }} catch (error) {{
            console.error('Error loading claims:', error);
            document.getElementById('claims-content').innerHTML = '<div class="alert alert-danger">Error loading claims</div>';
        }}
    }}
    
    async function loadWaitlists() {{
        document.getElementById('waitlist-content').innerHTML = '<div class="text-center py-5"><div class="spinner-border text-primary"></div></div>';
        try {{
            const response = await fetch('/api/layers/' + project.id + '/waitlists/');
            const data = await response.json();
            
            const wlBtn = isProjectAdmin ? '<button class="btn btn-primary btn-sm" onclick="createWaitlist()"><i class="fas fa-plus me-2"></i>Create Waitlist</button>' : '';
            let html = '<div class="d-flex justify-content-between align-items-center mb-4"><h4>Waitlists (' + (data.count || 0) + ')</h4>' + wlBtn + '</div>';
            
            if (!data.waitlists || data.waitlists.length === 0) {{
                html += '<div class="alert alert-info">No waitlists yet</div>';
            }} else {{
                data.waitlists.forEach(wl => {{
                    const started = wl.started;
                    const closed = wl.closed;
                    const full = wl.full;
                    const canJoin = isAuthenticated && started && !closed && !full && !wl.my_entry;
                    const statusBadge = full ? '<span class="badge bg-danger">Full</span>' : (closed ? '<span class="badge bg-secondary">Closed</span>' : (started ? '<span class="badge bg-success">Open</span>' : '<span class="badge bg-warning">Not Started</span>'));
                    const myEntry = wl.my_entry;
                    const wlNameEsc = escapeHtml(wl.name || '');
                    const wlDescEsc = escapeHtml(wl.description || 'No description');
                    const projSlugEsc = escapeHtmlBasic(project.slug || '');
                    const startStr = new Date(wl.start_date).toLocaleDateString();
                    const visStr = wl.public ? 'Public' : 'Private (layer members or link)';
                    const refBlock = wl.referral_url && myEntry ? '<p class="mb-2"><strong>Your referral link:</strong> <code class="user-select-all">' + escapeHtmlBasic(wl.referral_url) + '</code> <button class="btn btn-sm btn-outline-primary" onclick="copyText(\\'' + escapeForJsAttr(wl.referral_url) + '\\')"><i class="fas fa-copy"></i></button></p>' : '';
                    const joinHint = !myEntry && wl.referrals ? '<p class="text-muted mb-2"><em>Join to get your referral link</em></p>' : '';
                    const milestonesHtml = wl.milestones && wl.milestones.length > 0 ? '<hr><h5 class="mt-3">Milestones</h5><ul class="list-unstyled">' + wl.milestones.map(m => '<li class="mb-2"><strong>' + escapeHtml(m.title || '') + '</strong> (at ' + m.threshold + ' members)' + (m.description ? '<br><small class="text-muted">' + escapeHtml(m.description) + '</small>' : '') + '</li>').join('') + '</ul>' : '';
                    const actionsBlock = myEntry ? '<div class="mb-3"><span class="badge bg-success fs-6">Joined</span> <span class="text-muted">#' + myEntry.position + '</span><br><button class="btn btn-outline-danger btn-sm mt-2" data-waitlist-id="' + escapeHtmlBasic(String(wl.id || '')) + '" onclick="leaveWaitlist(this.dataset.waitlistId)">Leave</button></div>' : (canJoin ? '<button class="btn btn-primary w-100 mb-3" data-waitlist-id="' + escapeHtmlBasic(String(wl.id || '')) + '" onclick="joinWaitlist(this.dataset.waitlistId)">Join Waitlist</button>' : '<p class="text-muted">' + (started ? (closed ? 'Closed' : (full ? 'Full' : 'Login to join')) : 'Not started') + '</p>');
                    const countStr = wl.count + (wl.max_number ? ' of ' + wl.max_number : '');
                    const closeStr = wl.closing_date ? '<p class="mb-2"><strong>Closes:</strong> ' + new Date(wl.closing_date).toLocaleDateString() + '</p>' : '';
                    const embedBtn = isProjectAdmin ? '<hr><p class="small text-muted mb-2">Embed this waitlist on your website:</p><button class="btn btn-outline-primary btn-sm w-100" onclick="showEmbedCodeFromEl(this)" data-waitlist-id="' + wl.id + '" data-waitlist-name="' + escapeHtmlBasic(wl.name || '') + '"><i class="fas fa-code me-2"></i>Get Embed Code</button>' : '';
                    const wlBc = showCarousel ? '<li class="breadcrumb-item"><a href="' + layerBase + '">' + escapeHtmlBasic(project.name || '') + '</a></li>' : '<li class="breadcrumb-item"><a href="/layers/' + projSlugEsc + '/">Layer</a></li>';
                    html += '<div class="card mb-4 waitlist-card" id="waitlist-' + wl.id + '" style="border-left: 4px solid var(--accent-color);"><div class="card-body"><div class="row"><div class="col-md-8"><nav aria-label="breadcrumb"><ol class="breadcrumb">' + wlBc + '<li class="breadcrumb-item active">' + wlNameEsc + ' Waitlist</li></ol></nav><h3 class="mb-3">' + wlNameEsc + '</h3><p class="lead">' + wlDescEsc + '</p><p class="text-muted mb-2"><strong>Started:</strong> ' + startStr + '</p><p class="text-muted mb-2"><strong>Visibility:</strong> ' + visStr + '</p>' + refBlock + joinHint + milestonesHtml + '</div><div class="col-md-4"><div class="card"><div class="card-body"><h5 class="card-title">Actions</h5>' + actionsBlock + '<p class="mb-2"><strong>On waitlist:</strong> ' + countStr + '</p>' + closeStr + statusBadge + embedBtn + '</div></div></div></div></div></div>';
                }});
            }}
            
            document.getElementById('waitlist-content').innerHTML = html;
        }} catch (error) {{
            console.error('Error loading waitlists:', error);
            document.getElementById('waitlist-content').innerHTML = '<div class="alert alert-danger">Error loading waitlists</div>';
        }}
    }}
    
    async function joinWaitlist(wlId) {{
        if (!isAuthenticated) {{ alert('Please sign in to join'); return; }}
        const msg = prompt('Optional message:');
        if (msg === null) return;
        try {{
            const body = {{ message: msg }};
            if (referralRef) body.referral_code = referralRef;
            const res = await fetch('/api/waitlists/' + wlId + '/join/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify(body)
            }});
            const d = await res.json();
            if (res.ok) {{
                alert('Joined! Position: #' + d.entry.position);
                loadWaitlists();
            }} else {{ alert(d.error || 'Failed to join'); }}
        }} catch (e) {{ alert('Failed to join waitlist'); }}
    }}
    
    async function leaveWaitlist(wlId) {{
        if (!confirm('Leave this waitlist?')) return;
        try {{
            const res = await fetch('/api/waitlists/' + wlId + '/leave/', {{ method: 'POST' }});
            if (res.ok) {{ loadWaitlists(); }} else {{ alert('Failed to leave'); }}
        }} catch (e) {{ alert('Failed to leave waitlist'); }}
    }}
    
    function copyText(text) {{
        navigator.clipboard.writeText(text).then(() => {{
            const btn = event.target.closest('button');
            if (btn) {{ const o = btn.innerHTML; btn.innerHTML = '<i class="fas fa-check"></i>'; setTimeout(() => btn.innerHTML = o, 1500); }}
        }});
    }}
    
    function showEmbedCodeFromEl(el) {{
        const id = el.getAttribute('data-waitlist-id');
        const name = el.getAttribute('data-waitlist-name') || '';
        showEmbedCode(parseInt(id, 10), name);
    }}
    function showEmbedCode(waitlistId, waitlistName) {{
        const baseUrl = window.location.origin;
        const embedUrl = baseUrl + '/embed/waitlist/' + waitlistId + '/';
        const iframeCode = '<iframe src="' + escapeHtmlBasic(embedUrl) + '" width="100%" height="600" frameborder="0" style="border: none; border-radius: 12px;"></iframe>';
        
        document.getElementById('embed-waitlist-name').textContent = waitlistName;
        document.getElementById('embed-builder-link').href = baseUrl + '/embed/waitlist/' + waitlistId + '/build/';
        document.getElementById('embed-url').value = embedUrl;
        document.getElementById('embed-code-iframe').value = iframeCode;
        
        const modal = new bootstrap.Modal(document.getElementById('embedCodeModal'));
        modal.show();
    }}
    
    function copyEmbedCode(type) {{
        const elementId = type === 'iframe' ? 'embed-code-iframe' : 'embed-url';
        const element = document.getElementById(elementId);
        element.select();
        navigator.clipboard.writeText(element.value).then(() => {{
            const btn = event.target.closest('button');
            if (btn) {{
                const original = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i> Copied!';
                setTimeout(() => btn.innerHTML = original, 2000);
            }}
        }});
    }}
    
    async function uploadWaitlistImage() {{
        const fileInput = document.getElementById('wl-image-file');
        const statusEl = document.getElementById('wl-image-upload-status');
        const urlInput = document.getElementById('wl-image-url');
        
        if (!fileInput.files || !fileInput.files[0]) {{
            statusEl.innerHTML = '<small class="text-danger">Please select a file first</small>';
            return;
        }}
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('entity_type', 'waitlist');
        
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
                statusEl.innerHTML = '<small class="text-danger">' + escapeHtml(data.error || 'Upload failed') + '</small>';
            }}
        }} catch (error) {{
            console.error('Upload error:', error);
            statusEl.innerHTML = '<small class="text-danger">Upload failed. Please try again.</small>';
        }}
    }}
    
    function createWaitlist() {{
        const modalHtml = `
            <div class="modal fade" id="createWaitlistModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Create Waitlist</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="wl-alert-container"></div>
                            <form id="createWaitlistForm">
                                <div class="mb-3">
                                    <label for="wl-name" class="form-label">Waitlist Name *</label>
                                    <input type="text" class="form-control" id="wl-name" required>
                                </div>
                                <div class="mb-3">
                                    <label for="wl-description" class="form-label">Description</label>
                                    <textarea class="form-control" id="wl-description" rows="3"></textarea>
                                </div>
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <label for="wl-start-date" class="form-label">Start Date *</label>
                                        <input type="date" class="form-control" id="wl-start-date" required>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label for="wl-closing-date" class="form-label">Closing Date (optional)</label>
                                        <input type="date" class="form-control" id="wl-closing-date">
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label for="wl-max-number" class="form-label">Max Number of Entries (optional)</label>
                                    <input type="number" class="form-control" id="wl-max-number" min="1">
                                </div>
                                <div class="form-check mb-3">
                                    <input class="form-check-input" type="checkbox" id="wl-public" checked>
                                    <label class="form-check-label" for="wl-public">Public (visible to all)</label>
                                </div>
                                <div class="form-check mb-3">
                                    <input class="form-check-input" type="checkbox" id="wl-referrals" checked>
                                    <label class="form-check-label" for="wl-referrals">Enable Referrals</label>
                                </div>
                                <div class="form-check mb-3">
                                    <input class="form-check-input" type="checkbox" id="wl-active" checked>
                                    <label class="form-check-label" for="wl-active">Active</label>
                                </div>
                                <div class="mb-3">
                                    <label for="wl-image-url" class="form-label">Image (optional)</label>
                                    <input type="url" class="form-control mb-2" id="wl-image-url" placeholder="https://example.com/image.png or upload below">
                                    <div class="input-group">
                                        <input type="file" class="form-control" id="wl-image-file" accept="image/*">
                                        <button class="btn btn-outline-primary" type="button" onclick="uploadWaitlistImage()">
                                            <i class="fas fa-upload"></i> Upload
                                        </button>
                                    </div>
                                    <div class="form-text">Waitlist banner or icon. Max 600×600px, 5MB. Upload or paste URL above.</div>
                                    <div id="wl-image-upload-status" class="mt-1"></div>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="submitWaitlistBtn">
                                <i class="fas fa-plus me-2"></i>Create Waitlist
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        if (!document.getElementById('createWaitlistModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        document.getElementById('wl-alert-container').innerHTML = '';
        document.getElementById('wl-name').value = '';
        document.getElementById('wl-description').value = '';
        document.getElementById('wl-image-url').value = '';
        document.getElementById('wl-start-date').value = new Date().toISOString().split('T')[0];
        document.getElementById('wl-closing-date').value = '';
        document.getElementById('wl-max-number').value = '';
        document.getElementById('wl-public').checked = true;
        document.getElementById('wl-referrals').checked = true;
        document.getElementById('wl-active').checked = true;
        if (document.getElementById('wl-image-url')) document.getElementById('wl-image-url').value = '';
        if (document.getElementById('wl-image-file')) document.getElementById('wl-image-file').value = '';
        if (document.getElementById('wl-image-upload-status')) document.getElementById('wl-image-upload-status').innerHTML = '';
        const modal = new bootstrap.Modal(document.getElementById('createWaitlistModal'));
        modal.show();
        document.getElementById('submitWaitlistBtn').onclick = async () => {{
            const name = document.getElementById('wl-name').value.trim();
            const description = document.getElementById('wl-description').value.trim();
            const image_url = document.getElementById('wl-image-url').value.trim();
            const startDate = document.getElementById('wl-start-date').value;
            const closingDate = document.getElementById('wl-closing-date').value;
            const maxNumber = document.getElementById('wl-max-number').value;
            const isPublic = document.getElementById('wl-public').checked;
            const referrals = document.getElementById('wl-referrals').checked;
            const active = document.getElementById('wl-active').checked;
            if (!name || !startDate) {{
                document.getElementById('wl-alert-container').innerHTML = '<div class="alert alert-danger">Name and start date are required.</div>';
                return;
            }}
            const btn = document.getElementById('submitWaitlistBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
            try {{
                const body = {{ name, description, image_url: image_url || null, start_date: startDate, public: isPublic, referrals, active }};
                if (closingDate) body.closing_date = closingDate;
                if (maxNumber) body.max_number = parseInt(maxNumber, 10);
                const res = await fetch('/api/layers/' + project.id + '/waitlists/', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(body)
                }});
                const d = await res.json();
                if (res.ok) {{
                    modal.hide();
                    loadWaitlists();
                }} else {{
                    document.getElementById('wl-alert-container').innerHTML = '<div class="alert alert-danger">' + (d.error || 'Failed to create waitlist') + '</div>';
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Waitlist';
                }}
            }} catch (e) {{
                document.getElementById('wl-alert-container').innerHTML = '<div class="alert alert-danger">Failed to create waitlist</div>';
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Waitlist';
            }}
        }};
    }}
    
    function getStatusBadge(status) {{
        const badges = {{
            'proposed': '<span class="badge bg-info">Proposed</span>',
            'active': '<span class="badge bg-success">Active</span>',
            'stabilizing': '<span class="badge bg-primary">Stabilizing</span>',
            'maintaining': '<span class="badge bg-secondary">Maintaining</span>',
            'dormant': '<span class="badge bg-warning">Dormant</span>',
            'concluded': '<span class="badge bg-dark">Concluded</span>',
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
    
    async function uploadProjectImage() {{
        const fileInput = document.getElementById('edit-project-image-file');
        const statusEl = document.getElementById('edit-project-image-upload-status');
        const urlInput = document.getElementById('edit-project-image-url');
        
        if (!fileInput.files || !fileInput.files[0]) {{
            statusEl.innerHTML = '<small class="text-danger">Please select a file first</small>';
            return;
        }}
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('entity_type', 'project');
        
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
                statusEl.innerHTML = '<small class="text-danger">' + escapeHtml(data.error || 'Upload failed') + '</small>';
            }}
        }} catch (error) {{
            console.error('Upload error:', error);
            statusEl.innerHTML = '<small class="text-danger">Upload failed. Please try again.</small>';
        }}
    }}
    
    function editProject() {{
        if (!project) return;
        document.getElementById('edit-project-name').value = project.name || '';
        document.getElementById('edit-project-mission').value = project.mission || '';
        document.getElementById('edit-project-description').value = project.description || '';
        document.getElementById('edit-project-image-url').value = project.image_url || '';
        document.getElementById('edit-project-image-file').value = '';
        document.getElementById('edit-project-image-upload-status').innerHTML = '';
        document.getElementById('edit-project-status').value = project.status || 'proposed';
        document.getElementById('edit-project-status-reason').value = project.status_reason || '';
        document.getElementById('edit-project-meta-domain-inscription').value = project.meta_domain_inscription_id || '';
        document.getElementById('edit-project-meta-domain-display').textContent = project.meta_domain ? 'Cached: ' + project.meta_domain : '';
        document.getElementById('edit-modal-add-admin-q').value = '';
        document.getElementById('edit-modal-add-admin-results').innerHTML = '';
        const alertEl = document.getElementById('edit-project-alert');
        alertEl.classList.add('d-none');
        alertEl.textContent = '';
        loadEditModalAdmins();
        const modal = new bootstrap.Modal(document.getElementById('editProjectModal'));
        modal.show();
    }}
    
    async function loadEditModalAdmins() {{
        const container = document.getElementById('edit-modal-admins-list');
        if (!container || !project) return;
        container.innerHTML = '<div class="list-group-item text-muted small">Loading...</div>';
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/', {{ credentials: 'include' }});
            if (response.status === 403) {{
                container.innerHTML = '<div class="list-group-item text-warning small">You need layer admin access to view or manage admins.</div>';
                return;
            }}
            if (!response.ok) {{
                container.innerHTML = '<div class="list-group-item text-danger small">Failed to load admins (status ' + response.status + '). Try refreshing.</div>';
                return;
            }}
            const data = await response.json();
            const ownerUserEsc = escapeHtmlBasic(data.owner.username || '');
            const ownerNameEsc = escapeHtml(data.owner.display_name || '');
            let html = '<div class="list-group-item d-flex justify-content-between align-items-center py-2"><div><a href="/profile/' + ownerUserEsc + '/" class="fw-bold text-decoration-none small">' + ownerNameEsc + '</a><span class="badge bg-primary ms-2">Owner</span></div><span class="text-muted small">-</span></div>';
            (data.admins || []).forEach(a => {{
                const aUserEsc = escapeHtmlBasic(a.username || '');
                const aNameEsc = escapeHtml(a.display_name || '');
                const aIdEsc = escapeForJsAttr(String(a.user_id || ''));
                html += '<div class="list-group-item d-flex justify-content-between align-items-center py-2" id="edit-modal-admin-' + (a.user_id || '') + '"><a href="/profile/' + aUserEsc + '/" class="text-decoration-none small">' + aNameEsc + '</a><button type="button" class="btn btn-outline-danger btn-sm" onclick="removeAdminFromEditModal(\\'' + aIdEsc + '\\')">Remove</button></div>';
            }});
            container.innerHTML = html || '<div class="list-group-item text-muted small">No assigned admins</div>';
        }} catch (e) {{
            console.error('loadEditModalAdmins error:', e);
            container.innerHTML = '<div class="list-group-item text-danger small">Failed to load admins. Check console for details.</div>';
        }}
    }}
    
    function searchUsersForEditModalAdmin() {{
        const q = document.getElementById('edit-modal-add-admin-q').value.trim();
        const resultsEl = document.getElementById('edit-modal-add-admin-results');
        if (q.length < 2) {{ resultsEl.innerHTML = ''; return; }}
        fetch('/api/users/search/?q=' + encodeURIComponent(q))
            .then(r => r.json())
            .then(data => {{
                if (!data.users || data.users.length === 0) {{
                    resultsEl.innerHTML = '<p class="text-muted small mb-0">No users found</p>';
                    return;
                }}
                resultsEl.innerHTML = data.users.map(u => {{
                    const uNameEsc = escapeHtml(u.display_name || '');
                    const uUserEsc = escapeHtml(u.username || '');
                    const uIdEsc = escapeForJsAttr(String(u.id || ''));
                    return '<div class="d-flex justify-content-between align-items-center border-bottom py-1 small"><span>' + uNameEsc + ' <small class="text-muted">@' + uUserEsc + '</small></span><button type="button" class="btn btn-sm btn-primary" onclick="addAdminFromEditModal(\\'' + uIdEsc + '\\')">Add</button></div>';
                }}).join('');
            }})
            .catch(() => {{ resultsEl.innerHTML = '<p class="text-danger small mb-0">Search failed</p>'; }});
    }}
    
    async function addAdminFromEditModal(userId) {{
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'include',
                body: JSON.stringify({{ user_id: userId }})
            }});
            const data = await response.json();
            if (response.ok) {{
                document.getElementById('edit-modal-add-admin-q').value = '';
                document.getElementById('edit-modal-add-admin-results').innerHTML = '';
                loadEditModalAdmins();
                if (typeof loadAdmins === 'function') loadAdmins();
            }} else {{
                alert(data.error || 'Failed to add admin');
            }}
        }} catch (e) {{
            alert('Failed to add admin');
        }}
    }}
    
    async function removeAdminFromEditModal(userId) {{
        if (!confirm('Remove this user as layer admin?')) return;
        try {{
            const response = await fetch('/api/layers/' + project.id + '/admins/' + userId + '/', {{
                method: 'DELETE',
                credentials: 'include'
            }});
            const data = await response.json();
            if (response.ok) {{
                loadEditModalAdmins();
                if (typeof loadAdmins === 'function') loadAdmins();
            }} else {{
                alert(data.error || 'Failed to remove admin');
            }}
        }} catch (e) {{
            alert('Failed to remove admin');
        }}
    }}
    
    async function saveProjectEdit() {{
        if (!project) return;
        const name = document.getElementById('edit-project-name').value.trim();
        const mission = document.getElementById('edit-project-mission').value;
        const description = document.getElementById('edit-project-description').value;
        const image_url = document.getElementById('edit-project-image-url').value.trim();
        const status = document.getElementById('edit-project-status').value;
        const status_reason = document.getElementById('edit-project-status-reason').value.trim();
        const meta_domain_inscription_id = document.getElementById('edit-project-meta-domain-inscription').value.trim();
        const alertEl = document.getElementById('edit-project-alert');
        const saveBtn = document.getElementById('edit-project-save-btn');
        
        if (!name) {{
            alertEl.textContent = 'Layer name is required.';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
            return;
        }}
        
        saveBtn.disabled = true;
        alertEl.classList.add('d-none');
        try {{
            const res = await fetch('/api/layers/' + project.id + '/', {{
                method: 'PATCH',
                headers: {{ 'Content-Type': 'application/json' }},
                credentials: 'include',
                body: JSON.stringify({{ name: name, mission: mission || null, description: description, image_url: image_url || null, status: status, status_reason: status_reason || null, meta_domain_inscription_id: meta_domain_inscription_id || null }})
            }});
            let data;
            try {{ data = await res.json(); }} catch (_) {{
                alertEl.textContent = res.status === 401 ? 'Please sign in to edit projects.' : 'Server error. Please try again.';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
                saveBtn.disabled = false;
                return;
            }}
            if (res.ok) {{
                bootstrap.Modal.getInstance(document.getElementById('editProjectModal')).hide();
                project = data.project;
                if (project.slug !== projectSlug) {{
                    window.location.href = (showCarousel ? '/layer/' : '/layers/') + project.slug + '/';
                    return;
                }}
                displayProjectHeader();
                loadOverview();
            }} else {{
                alertEl.textContent = data.error || 'Failed to update project';
                alertEl.className = 'alert alert-danger';
                alertEl.classList.remove('d-none');
            }}
        }} catch (e) {{
            alertEl.textContent = 'Network error. Please try again.';
            alertEl.className = 'alert alert-danger';
            alertEl.classList.remove('d-none');
        }}
        saveBtn.disabled = false;
    }}
    
    function createWorkgroup() {{
        const modalHtml = `
            <div class="modal fade" id="projectCreateWorkgroupModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Create Workgroup</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="project-wg-alert-container"></div>
                            <form id="projectCreateWorkgroupForm">
                                <div class="mb-3">
                                    <label for="project-wg-name" class="form-label">Workgroup Name *</label>
                                    <input type="text" class="form-control" id="project-wg-name" required>
                                </div>
                                <div class="mb-3">
                                    <label for="project-wg-description" class="form-label">Description *</label>
                                    <textarea class="form-control" id="project-wg-description" rows="3" required></textarea>
                                </div>
                                <p class="text-muted small">New workgroups require approval from the layer admin before becoming active.</p>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="projectSubmitWorkgroupBtn">
                                <i class="fas fa-plus me-2"></i>Create Workgroup
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        if (!document.getElementById('projectCreateWorkgroupModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        document.getElementById('project-wg-alert-container').innerHTML = '';
        document.getElementById('project-wg-name').value = '';
        document.getElementById('project-wg-description').value = '';
        const modal = new bootstrap.Modal(document.getElementById('projectCreateWorkgroupModal'));
        modal.show();
        document.getElementById('projectSubmitWorkgroupBtn').onclick = async () => {{
            const name = document.getElementById('project-wg-name').value.trim();
            const description = document.getElementById('project-wg-description').value.trim();
            if (!name || !description) {{
                document.getElementById('project-wg-alert-container').innerHTML = '<div class="alert alert-danger">Name and description are required.</div>';
                return;
            }}
            const btn = document.getElementById('projectSubmitWorkgroupBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
            try {{
                const response = await fetch('/api/layers/' + project.id + '/workgroups/', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ name, description }})
                }});
                const data = await response.json();
                if (response.ok) {{
                    modal.hide();
                    loadWorkgroups();
                    alert('Workgroup created! It will be visible once approved by the layer admin.');
                }} else {{
                    throw new Error(data.error || 'Failed to create workgroup');
                }}
            }} catch (err) {{
                document.getElementById('project-wg-alert-container').innerHTML = '<div class="alert alert-danger">' + (err.message || 'Failed to create workgroup') + '</div>';
            }}
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Workgroup';
        }};
    }}
    
    function createRole() {{
        // Create modal HTML
        const modalHtml = `
            <div class="modal fade" id="createRoleModal" tabindex="-1">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Create New Role</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="role-alert-container"></div>
                            
                            <form id="createRoleForm">
                                <div class="mb-3">
                                    <label for="role-title-guild" class="form-label">Guild Title *</label>
                                    <input type="text" class="form-control" id="role-title-guild" required>
                                    <div class="form-text">The formal/ceremonial title (e.g., "Keeper of the Keys")</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-title-operational" class="form-label">Operational Title</label>
                                    <input type="text" class="form-control" id="role-title-operational">
                                    <div class="form-text">Optional: The practical title (e.g., "Security Lead")</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-description" class="form-label">Description *</label>
                                    <textarea class="form-control" id="role-description" rows="4" required></textarea>
                                    <div class="form-text">Describe the role's responsibilities and purpose</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-cluster" class="form-label">Cluster</label>
                                    <select class="form-select" id="role-cluster">
                                        <option value="">No cluster</option>
                                    </select>
                                    <div class="form-text">Optional: Group this role with others</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-image-url" class="form-label">Image URL</label>
                                    <input type="url" class="form-control" id="role-image-url">
                                    <div class="form-text">Optional: URL to role image/icon</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="role-order" class="form-label">Display Order</label>
                                    <input type="number" class="form-control" id="role-order" value="0">
                                    <div class="form-text">Lower numbers appear first</div>
                                </div>
                                
                                <div class="mb-3">
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-public-visible" checked>
                                        <label class="form-check-label" for="role-public-visible">
                                            Public Visible
                                        </label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-claim-approval">
                                        <label class="form-check-label" for="role-claim-approval">
                                            Claims Require Approval
                                        </label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-requires-election">
                                        <label class="form-check-label" for="role-requires-election">
                                            Requires Election (role filled via vote)
                                        </label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-badge-enabled" checked>
                                        <label class="form-check-label" for="role-badge-enabled">
                                            Badge Enabled
                                        </label>
                                    </div>
                                    <div class="form-check">
                                        <input class="form-check-input" type="checkbox" id="role-badge-approval">
                                        <label class="form-check-label" for="role-badge-approval">
                                            Badges Require Approval
                                        </label>
                                    </div>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="submitRoleBtn">
                                <i class="fas fa-plus me-2"></i>Create Role
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to page if not exists
        if (!document.getElementById('createRoleModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        
        // Load clusters for dropdown
        fetch('/api/layers/' + project.id + '/clusters/')
            .then(r => r.json())
            .then(data => {{
                const select = document.getElementById('role-cluster');
                (data.clusters || []).forEach(cluster => {{
                    if (!cluster) return;
                    const option = document.createElement('option');
                    option.value = cluster.id || '';
                    option.textContent = (cluster.name != null && cluster.name !== '') ? cluster.name : 'Unnamed';
                    select.appendChild(option);
                }});
            }});
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('createRoleModal'));
        modal.show();
        
        // Handle form submission
        document.getElementById('submitRoleBtn').onclick = async () => {{
            const titleGuild = document.getElementById('role-title-guild').value.trim();
            const titleOperational = document.getElementById('role-title-operational').value.trim();
            const description = document.getElementById('role-description').value.trim();
            
            if (!titleGuild || !description) {{
                document.getElementById('role-alert-container').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Guild title and description are required
                    </div>
                `;
                return;
            }}
            
            const submitBtn = document.getElementById('submitRoleBtn');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
            
            const formData = {{
                title_guild: titleGuild,
                title_operational: titleOperational || null,
                description: description,
                cluster_id: document.getElementById('role-cluster').value || null,
                image_url: document.getElementById('role-image-url').value || null,
                order: parseInt(document.getElementById('role-order').value) || 0,
                public_visible: document.getElementById('role-public-visible').checked,
                claim_requires_approval: document.getElementById('role-claim-approval').checked,
                requires_election: document.getElementById('role-requires-election').checked,
                badge_enabled: document.getElementById('role-badge-enabled').checked,
                badge_requires_approval: document.getElementById('role-badge-approval').checked
            }};
            
            try {{
                const response = await fetch('/api/layers/' + project.id + '/roles/', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify(formData)
                }});
                
                const data = await response.json();
                
                if (response.ok) {{
                    modal.hide();
                    loadRoles(); // Reload roles list
                    alert('Role created successfully!');
                }} else {{
                    throw new Error(data.error || 'Failed to create role');
                }}
            }} catch (error) {{
                document.getElementById('role-alert-container').innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>' + escapeHtml(error.message || 'Unknown error') + '</div>';
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Role';
            }}
        }};
    }}
    
    function createCluster() {{
        const modalHtml = `
            <div class="modal fade" id="createClusterModal" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Create New Cluster</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div id="cluster-alert-container"></div>
                            
                            <form id="createClusterForm">
                                <div class="mb-3">
                                    <label for="cluster-name" class="form-label">Cluster Name *</label>
                                    <input type="text" class="form-control" id="cluster-name" required>
                                    <div class="form-text">A descriptive name for this role group</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="cluster-description" class="form-label">Description</label>
                                    <textarea class="form-control" id="cluster-description" rows="3"></textarea>
                                    <div class="form-text">Optional: Describe the purpose of this cluster</div>
                                </div>
                                
                                <div class="mb-3">
                                    <label for="cluster-order" class="form-label">Display Order</label>
                                    <input type="number" class="form-control" id="cluster-order" value="0">
                                    <div class="form-text">Lower numbers appear first</div>
                                </div>
                            </form>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" id="submitClusterBtn">
                                <i class="fas fa-plus me-2"></i>Create Cluster
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        if (!document.getElementById('createClusterModal')) {{
            document.body.insertAdjacentHTML('beforeend', modalHtml);
        }}
        
        // Reset form and button so each open is fresh (and not stuck from a previous submit)
        document.getElementById('cluster-name').value = '';
        document.getElementById('cluster-description').value = '';
        document.getElementById('cluster-order').value = '0';
        document.getElementById('cluster-alert-container').innerHTML = '';
        const submitClusterBtn = document.getElementById('submitClusterBtn');
        submitClusterBtn.disabled = false;
        submitClusterBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Cluster';
        
        const modal = new bootstrap.Modal(document.getElementById('createClusterModal'));
        modal.show();
        
        document.getElementById('submitClusterBtn').onclick = async () => {{
            const name = document.getElementById('cluster-name').value.trim();
            const description = document.getElementById('cluster-description').value.trim();
            const order = parseInt(document.getElementById('cluster-order').value) || 0;
            
            if (!name) {{
                document.getElementById('cluster-alert-container').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="fas fa-exclamation-circle me-2"></i>
                        Cluster name is required
                    </div>
                `;
                return;
            }}
            
            const submitBtn = document.getElementById('submitClusterBtn');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Creating...';
            
            try {{
                const response = await fetch('/api/layers/' + project.id + '/clusters/', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ name, description, order }})
                }});
                
                const data = await response.json();
                
                if (response.ok) {{
                    document.getElementById('cluster-name').value = '';
                    document.getElementById('cluster-description').value = '';
                    document.getElementById('cluster-order').value = '0';
                    document.getElementById('cluster-alert-container').innerHTML = '';
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Cluster';
                    modal.hide();
                    loadClusters();
                    alert('Cluster created successfully!');
                }} else {{
                    throw new Error(data.error || 'Failed to create cluster');
                }}
            }} catch (error) {{
                document.getElementById('cluster-alert-container').innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>' + escapeHtml(error.message || 'Unknown error') + '</div>';
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-plus me-2"></i>Create Cluster';
            }}
        }};
    }}
    
    async function editCluster(clusterId) {{
        try {{
            const response = await fetch('/api/clusters/' + clusterId + '/');
            const data = await response.json();
            const cluster = data.cluster || data;
            if (!cluster) {{
                throw new Error('Cluster not found');
            }}
            const cName = (cluster.name != null && cluster.name !== '') ? String(cluster.name) : '';
            const cDesc = (cluster.description != null) ? String(cluster.description) : '';
            const cOrder = (cluster.order != null && cluster.order !== '') ? cluster.order : 0;
            const cNameEsc = escapeHtmlBasic(cName);
            const cDescEsc = escapeHtml(cDesc);
            
            const modalHtml = '<div class="modal fade" id="editClusterModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><div class="modal-header"><h5 class="modal-title">Edit Cluster</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><div id="edit-cluster-alert-container"></div><form id="editClusterForm"><div class="mb-3"><label for="edit-cluster-name" class="form-label">Cluster Name *</label><input type="text" class="form-control" id="edit-cluster-name" value="' + cNameEsc + '" required></div><div class="mb-3"><label for="edit-cluster-description" class="form-label">Description</label><textarea class="form-control" id="edit-cluster-description" rows="3">' + cDescEsc + '</textarea></div><div class="mb-3"><label for="edit-cluster-order" class="form-label">Display Order</label><input type="number" class="form-control" id="edit-cluster-order" value="' + cOrder + '"></div></form></div><div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><button type="button" class="btn btn-primary" id="updateClusterBtn"><i class="fas fa-save me-2"></i>Save Changes</button></div></div></div></div>';
            
            if (document.getElementById('editClusterModal')) {{
                document.getElementById('editClusterModal').remove();
            }}
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            
            const modal = new bootstrap.Modal(document.getElementById('editClusterModal'));
            modal.show();
            
            document.getElementById('updateClusterBtn').onclick = async () => {{
                const name = document.getElementById('edit-cluster-name').value.trim();
                const description = document.getElementById('edit-cluster-description').value.trim();
                const order = parseInt(document.getElementById('edit-cluster-order').value) || 0;
                
                if (!name) {{
                    document.getElementById('edit-cluster-alert-container').innerHTML = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-circle me-2"></i>
                            Cluster name is required
                        </div>
                    `;
                    return;
                }}
                
                const submitBtn = document.getElementById('updateClusterBtn');
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
                
                try {{
                    const response = await fetch('/api/clusters/' + clusterId + '/', {{
                        method: 'PATCH',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{ name, description, order }})
                    }});
                    
                    const data = await response.json();
                    
                    if (response.ok) {{
                        modal.hide();
                        loadClusters();
                        alert('Cluster updated successfully!');
                    }} else {{
                        throw new Error(data.error || 'Failed to update cluster');
                    }}
                }} catch (error) {{
                    document.getElementById('edit-cluster-alert-container').innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>' + escapeHtml(error.message || 'Unknown error') + '</div>';
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-save me-2"></i>Save Changes';
                }}
            }};
        }} catch (error) {{
            alert('Error loading cluster: ' + error.message);
        }}
    }}
    
    async function deleteCluster(clusterId, clusterName) {{
        if (!confirm('Are you sure you want to delete the cluster "' + clusterName + '"? This will unassign all roles from this cluster.')) {{
            return;
        }}
        
        try {{
            const response = await fetch('/api/clusters/' + clusterId + '/', {{
                method: 'DELETE'
            }});
            
            const data = await response.json();
            
            if (response.ok) {{
                loadClusters();
                alert('Cluster deleted successfully!');
            }} else {{
                throw new Error(data.error || 'Failed to delete cluster');
            }}
        }} catch (error) {{
            alert('Error deleting cluster: ' + error.message);
        }}
    }}
    
    // Load project on page load
    loadProject();
    </script>
    """
    
    if standalone and project_obj:
        layer_name = project_obj.name or project_slug
        layer_image_url = project_obj.image_url or ''
        html = render_layer_standalone_page(
            f"{layer_name} Gov-Hub",
            content,
            layer_name=layer_name,
            layer_slug=project_slug,
            layer_image_url=layer_image_url,
            theme=current_theme,
            user_menu=user_menu,
        )
    else:
        html = render_page(f"Layer: {project_slug} - MLGH", content, theme=current_theme, user_menu=user_menu)
    resp = make_response(html)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp
