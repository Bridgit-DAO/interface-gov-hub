"""Bridges pages: list, create. Web2 bridges between content."""
from flask import Blueprint, session, request
from services.identity import get_current_user, require_auth

bp = Blueprint('bridges_pages', __name__, url_prefix='')


def _get_imports():
    from services.rendering import generate_user_menu, render_page
    return generate_user_menu, render_page


@bp.route('/bridges/')
def bridges_list():
    """Bridge list page: filter by relationship, inscribed; link to create."""
    generate_user_menu, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')

    content = """
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item active">Bridges</li>
            </ol>
        </nav>
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h1 class="mb-1">Bridges</h1>
                <p class="text-muted mb-0">Links between content (URL + text/image/video/audio). Optionally inscribed to Bitcoin Ordinals.</p>
            </div>
            <a href="/bridges/create/" class="btn btn-primary"><i class="fas fa-link me-2"></i>Create Bridge</a>
        </div>

        <div class="row mb-4">
            <div class="col-md-4">
                <label for="relationship-filter" class="form-label">Relationship</label>
                <select id="relationship-filter" class="form-select" onchange="loadBridges()">
                    <option value="">All</option>
                    <option value="cites">cites</option>
                    <option value="contradicts">contradicts</option>
                    <option value="supports">supports</option>
                    <option value="extends">extends</option>
                    <option value="timeline">timeline</option>
                    <option value="related">related</option>
                </select>
            </div>
            <div class="col-md-4">
                <label for="inscribed-filter" class="form-label">Inscribed</label>
                <select id="inscribed-filter" class="form-select" onchange="loadBridges()">
                    <option value="">All</option>
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                </select>
            </div>
        </div>

        <div id="bridges-container">
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            </div>
        </div>
    </div>

    <script>
    async function loadBridges() {
        const rel = document.getElementById('relationship-filter').value;
        const inscribed = document.getElementById('inscribed-filter').value;
        let url = '/api/bridges/?';
        if (rel) url += 'relationship=' + encodeURIComponent(rel) + '&';
        if (inscribed) url += 'inscribed=' + encodeURIComponent(inscribed) + '&';

        try {
            const res = await fetch(url, { credentials: 'same-origin' });
            const data = await res.json();
            const container = document.getElementById('bridges-container');

            if (!data.bridges || data.bridges.length === 0) {
                container.innerHTML = '<div class="alert alert-info">No bridges yet. <a href="/bridges/create/">Create one</a>.</div>';
                return;
            }

            let html = '<div class="list-group">';
            for (const b of data.bridges) {
                const inscr = b.inscription_id ? '<span class="badge bg-success ms-2">Inscribed</span>' : '';
                html += `
                <div class="list-group-item list-group-item-action">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${escapeHtml(b.name)} ${inscr}</h6>
                        <small class="text-muted">${escapeHtml(b.relationship)}</small>
                    </div>
                    <p class="mb-1 small">
                        <a href="${escapeAttr(b.source?.url || '#')}" target="_blank" rel="noopener">${escapeHtml((b.source?.name || b.source?.url || 'Source').substring(0, 60))}</a>
                        <i class="fas fa-arrow-right mx-2"></i>
                        <a href="${escapeAttr(b.target?.url || '#')}" target="_blank" rel="noopener">${escapeHtml((b.target?.name || b.target?.url || 'Target').substring(0, 60))}</a>
                    </p>
                    ${b.explanation ? '<p class="mb-0 small text-muted">' + escapeHtml(b.explanation.substring(0, 120)) + '</p>' : ''}
                </div>`;
            }
            html += '</div>';
            container.innerHTML = html;
        } catch (e) {
            document.getElementById('bridges-container').innerHTML =
                '<div class="alert alert-danger">Failed to load bridges: ' + escapeHtml(String(e)) + '</div>';
        }
    }
    function escapeHtml(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
    function escapeAttr(s) { return (s || '').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
    loadBridges();
    </script>
    """
    return render_page("Bridges - Gov-Hub", content, theme=current_theme, user_menu=user_menu)


@bp.route('/bridges/create/')
@require_auth
def bridges_create():
    """Bridge create form. Pre-fill from session or query params (source=, target=)."""
    generate_user_menu, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark'))

    # Pre-fill from query params (escape for HTML attr)
    source_url = (request.args.get('source', '') or '').replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')
    target_url = (request.args.get('target', '') or '').replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')

    content = """
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/bridges/">Bridges</a></li>
                <li class="breadcrumb-item active">Create</li>
            </ol>
        </nav>
        <h1 class="mb-4">Create Bridge</h1>

        <div id="alert-container"></div>
        <div id="session-prefill" class="alert alert-info d-none">
            <i class="fas fa-info-circle me-2"></i>
            <span id="session-prefill-msg">Source and target from your active session will be loaded.</span>
        </div>

        <form id="bridgeForm">
            <div class="mb-3">
                <label for="name" class="form-label">Name *</label>
                <input type="text" class="form-control" id="name" required placeholder="Short label for this bridge">
            </div>

            <div class="card mb-3">
                <div class="card-header">Source</div>
                <div class="card-body">
                    <div class="mb-2">
                        <label for="source_url" class="form-label">URL *</label>
                        <input type="url" class="form-control" id="source_url" required placeholder="https://..." value="SOURCE_URL_PLACEHOLDER">
                    </div>
                    <div class="row">
                        <div class="col-md-6 mb-2">
                            <label for="source_content_type" class="form-label">Content type</label>
                            <select class="form-select" id="source_content_type">
                                <option value="text">text</option>
                                <option value="image">image</option>
                                <option value="video">video</option>
                                <option value="audio">audio</option>
                            </select>
                        </div>
                        <div class="col-md-6 mb-2">
                            <label for="source_name" class="form-label">Label</label>
                            <input type="text" class="form-control" id="source_name" placeholder="Short label">
                        </div>
                    </div>
                    <div class="mb-2">
                        <label for="source_text_excerpt" class="form-label">Text excerpt (if text)</label>
                        <textarea class="form-control" id="source_text_excerpt" rows="2" placeholder="Quoted text..."></textarea>
                    </div>
                </div>
            </div>

            <div class="card mb-3">
                <div class="card-header">Target</div>
                <div class="card-body">
                    <div class="mb-2">
                        <label for="target_url" class="form-label">URL *</label>
                        <input type="url" class="form-control" id="target_url" required placeholder="https://..." value="TARGET_URL_PLACEHOLDER">
                    </div>
                    <div class="row">
                        <div class="col-md-6 mb-2">
                            <label for="target_content_type" class="form-label">Content type</label>
                            <select class="form-select" id="target_content_type">
                                <option value="text">text</option>
                                <option value="image">image</option>
                                <option value="video">video</option>
                                <option value="audio">audio</option>
                            </select>
                        </div>
                        <div class="col-md-6 mb-2">
                            <label for="target_name" class="form-label">Label</label>
                            <input type="text" class="form-control" id="target_name" placeholder="Short label">
                        </div>
                    </div>
                    <div class="mb-2">
                        <label for="target_text_excerpt" class="form-label">Text excerpt (if text)</label>
                        <textarea class="form-control" id="target_text_excerpt" rows="2" placeholder="Quoted text..."></textarea>
                    </div>
                </div>
            </div>

            <div class="mb-3">
                <label for="relationship" class="form-label">Relationship *</label>
                <select class="form-select" id="relationship" required>
                    <option value="cites">cites</option>
                    <option value="contradicts">contradicts</option>
                    <option value="supports">supports</option>
                    <option value="extends">extends</option>
                    <option value="timeline">timeline</option>
                    <option value="related" selected>related</option>
                </select>
            </div>

            <div class="mb-3">
                <label for="explanation" class="form-label">Explanation</label>
                <textarea class="form-control" id="explanation" rows="3" placeholder="Optional human-readable description"></textarea>
            </div>

            <div class="d-flex gap-2">
                <button type="submit" class="btn btn-primary" id="submitBtn">
                    <i class="fas fa-save me-2"></i>Save Bridge
                </button>
                <a href="/bridges/" class="btn btn-secondary">Cancel</a>
            </div>
        </form>
    </div>

    <script>
    (async function() {
        // Try to get active session and prefill
        try {
            const sessRes = await fetch('/api/bridges/sessions/', { credentials: 'same-origin' });
            const sessData = await sessRes.json();
            if (sessRes.ok && sessData.sessions && sessData.sessions.length > 0) {
                const s = sessData.sessions[0];
                if (s.source_content) {
                    document.getElementById('source_url').value = s.source_content.url || '';
                    document.getElementById('source_content_type').value = s.source_content.content_type || 'text';
                    document.getElementById('source_name').value = s.source_content.name || '';
                    document.getElementById('source_text_excerpt').value = s.source_content.text_excerpt || '';
                }
                if (s.target_content) {
                    document.getElementById('target_url').value = s.target_content.url || '';
                    document.getElementById('target_content_type').value = s.target_content.content_type || 'text';
                    document.getElementById('target_name').value = s.target_content.name || '';
                    document.getElementById('target_text_excerpt').value = s.target_content.text_excerpt || '';
                }
                if (s.source_content || s.target_content) {
                    document.getElementById('session-prefill').classList.remove('d-none');
                }
            }
        } catch (_) {}

        document.getElementById('bridgeForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';

            const payload = {
                name: document.getElementById('name').value.trim(),
                source: {
                    url: document.getElementById('source_url').value.trim(),
                    content_type: document.getElementById('source_content_type').value,
                    name: document.getElementById('source_name').value.trim() || null,
                    text_excerpt: document.getElementById('source_text_excerpt').value.trim() || null
                },
                target: {
                    url: document.getElementById('target_url').value.trim(),
                    content_type: document.getElementById('target_content_type').value,
                    name: document.getElementById('target_name').value.trim() || null,
                    text_excerpt: document.getElementById('target_text_excerpt').value.trim() || null
                },
                relationship: document.getElementById('relationship').value,
                explanation: document.getElementById('explanation').value.trim() || null
            };

            try {
                const res = await fetch('/api/bridges/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    credentials: 'same-origin'
                });
                const data = await res.json();

                if (res.ok) {
                    document.getElementById('alert-container').innerHTML =
                        '<div class="alert alert-success"><i class="fas fa-check-circle me-2"></i>Bridge created! <a href="/bridges/">View all bridges</a></div>';
                    setTimeout(function() { window.location.href = '/bridges/'; }, 1500);
                } else {
                    throw new Error(data.error || 'Failed to create bridge');
                }
            } catch (err) {
                document.getElementById('alert-container').innerHTML =
                    '<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>' + (err.message || 'Error') + '</div>';
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-save me-2"></i>Save Bridge';
            }
        });
    })();
    </script>
    """.replace('SOURCE_URL_PLACEHOLDER', source_url).replace('TARGET_URL_PLACEHOLDER', target_url)
    return render_page("Create Bridge - Gov-Hub", content, theme=current_theme, user_menu=user_menu)
