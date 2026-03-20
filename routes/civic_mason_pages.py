"""Civic Mason page: global brick wall. Badge-gated placement."""
from flask import Blueprint, request, session, url_for
from services.identity import get_current_user
from services.rendering import generate_user_menu, render_page

bp = Blueprint('civic_mason_pages', __name__, url_prefix='')

_CM_LOCALES = frozenset({'en', 'ar'})


def _get_imports():
    from services.rendering import generate_user_menu, render_page
    return generate_user_menu, render_page


@bp.route('/civic-mason/')
def civic_mason_page():
    """Global Civic Mason wall: half-offset grid, badge-gated placement."""
    generate_user_menu, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    mural_url = url_for('static', filename='images/civicmason-mural.png')

    lang = (request.args.get('lang') or '').strip().lower()[:5]
    if lang in _CM_LOCALES:
        session['cm_locale'] = lang
        session.modified = True
    locale = session.get('cm_locale') or 'en'
    if locale not in _CM_LOCALES:
        locale = 'en'

    cm_i18n_js = url_for('static', filename='js/cm-i18n.js')
    _cm_json = url_for('static', filename='i18n/civic-mason/en.json')
    cm_i18n_json_base = _cm_json.rsplit('/', 1)[0] + '/'

    content = """
    <script src="CM_I18N_JS_PLACEHOLDER"></script>
    <script>
    window.__CM_LOCALE__ = "CM_LOCALE_PLACEHOLDER";
    window.__CM_I18N_JSON_BASE__ = "CM_I18N_JSON_BASE_PLACEHOLDER";
    </script>
    <div id="civic-mason-page" class="civic-mason-fullpage">
        <div class="civic-mason-header">
            <nav aria-label="breadcrumb">
                <ol class="breadcrumb mb-0">
                    <li class="breadcrumb-item"><a href="/" data-cm-i18n="page.breadcrumb.home">Home</a></li>
                    <li class="breadcrumb-item"><a href="/badges/" data-cm-i18n="page.breadcrumb.recognition">Recognition</a></li>
                    <li class="breadcrumb-item active" data-cm-i18n="page.breadcrumb.active">Civic Mason</li>
                </ol>
            </nav>
            <div class="d-flex align-items-center gap-2 mt-1">
                <h1 class="mb-0 me-auto"><i class="fas fa-th-large me-2"></i><span data-cm-i18n="page.title">Civic Mason</span></h1>
                <p class="mb-0 opacity-75 d-none d-md-block small" data-cm-i18n="page.tagline">Contributors with Civic Mason badges leave a brick on the wall.</p>
            </div>
            <div id="cm-dev-mode-bar" class="d-none w-100 mt-2 py-2 px-3 rounded cm-dev-bar">
                <div class="d-flex align-items-center justify-content-between flex-wrap gap-2">
                    <span class="small mb-0"><i class="fas fa-flask me-1 text-warning"></i><span data-cm-i18n="dev.label">Dev only: Civic Mason rules</span></span>
                    <div class="form-check form-switch mb-0">
                        <input class="form-check-input" type="checkbox" id="cm-demo-toggle" role="switch" data-cm-i18n-aria="a11y.demoMode">
                        <label class="form-check-label small" for="cm-demo-toggle" data-cm-i18n="dev.demoSwitch">Demo mode — no badge required, unlimited placements</label>
                    </div>
                </div>
            </div>
        </div>

        <!-- Floating brick (eligible users only, shown via JS) -->
        <div id="floating-brick" class="floating-brick" aria-hidden="true"></div>

        <!-- Ineligible info card (shown via JS when user cannot place bricks) -->
        <div id="ineligible-card" class="ineligible-card d-none">
            <i class="fas fa-th-large fa-2x mb-3 opacity-50"></i>
            <h6 class="mb-2" id="ineligible-title">Earn the Civic Mason Badge</h6>
            <p class="small opacity-75 mb-3" id="ineligible-body">
                Place a permanent brick on this wall by earning a Civic Mason&#8209;eligible badge
                through civic participation.
            </p>
            <a href="/badges/" class="btn btn-outline-light btn-sm" id="ineligible-btn" data-cm-i18n="ineligible.badgeButton">View Badges &amp; How to Earn</a>
        </div>

        <div class="civic-mason-mural-wrap">
            <div class="civic-mason-mural-inner">
                <img src="MURAL_URL_PLACEHOLDER" class="civic-mason-mural-img" id="civic-mason-mural-img" alt="" />
                <div id="civic-mason-grid" class="civic-mason-grid-container">
                    <div class="text-center py-5 text-white-50">
                        <div class="spinner-border" role="status"><span class="visually-hidden" data-cm-i18n="a11y.loading">Loading…</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Config modal: pre-placement color + message -->
    <div class="modal fade" id="configBrickModal" tabindex="-1" aria-hidden="true" aria-labelledby="configModalLabel">
        <div class="modal-dialog modal-sm">
            <div class="modal-content bg-dark text-white border border-secondary">
                <div class="modal-header border-0 pb-1">
                    <h6 class="modal-title" id="configModalLabel"><i class="fas fa-paint-brush me-2 opacity-75"></i><span data-cm-i18n="config.title">Configure Brick</span></h6>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" data-cm-i18n-aria="a11y.close"></button>
                </div>
                <div class="modal-body pt-1">
                    <p class="small text-white-50 mb-2" data-cm-i18n="config.hint">Choose a color — double-click to select &amp; close.</p>
                    <div class="d-flex flex-wrap gap-2 mb-3" id="config-palette" role="group" data-cm-i18n-aria="a11y.brickColors"></div>
                    <label for="config-msg" class="form-label small mb-1"><span data-cm-i18n="config.message">Message</span> <span class="opacity-50" data-cm-i18n="config.optional">(optional)</span></label>
                    <textarea class="form-control form-control-sm bg-dark text-white border-secondary" id="config-msg" rows="2" maxlength="200" data-cm-i18n-placeholder="config.placeholder"></textarea>
                    <div class="text-end mt-1"><small class="opacity-50"><span id="config-msg-count">0</span>/<span data-cm-max-label>200</span></small></div>
                </div>
            </div>
        </div>
    </div>

    <!-- Edit modal: post-placement edit or cancel -->
    <div class="modal fade" id="editBrickModal" tabindex="-1" aria-hidden="true" aria-labelledby="editModalLabel">
        <div class="modal-dialog modal-sm">
            <div class="modal-content bg-dark text-white border border-secondary">
                <div class="modal-header border-0 pb-1">
                    <h6 class="modal-title" id="editModalLabel"><i class="fas fa-edit me-2 opacity-75"></i><span data-cm-i18n="edit.title">Edit Brick</span></h6>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" data-cm-i18n-aria="a11y.close"></button>
                </div>
                <div class="modal-body pt-1">
                    <p class="small text-white-50 mb-2" data-cm-i18n="edit.hint">Update color or message, then Accept — or cancel this placement.</p>
                    <div class="d-flex flex-wrap gap-2 mb-3" id="edit-palette" role="group" data-cm-i18n-aria="a11y.brickColors"></div>
                    <label for="edit-msg" class="form-label small mb-1"><span data-cm-i18n="config.message">Message</span> <span class="opacity-50" data-cm-i18n="config.optional">(optional)</span></label>
                    <textarea class="form-control form-control-sm bg-dark text-white border-secondary" id="edit-msg" rows="2" maxlength="200"></textarea>
                    <div class="text-end mt-1"><small class="opacity-50"><span id="edit-msg-count">0</span>/<span data-cm-max-label>200</span></small></div>
                </div>
                <div class="modal-footer border-0 pt-0 gap-2">
                    <button type="button" class="btn btn-outline-danger btn-sm" id="edit-cancel-placement-btn" data-cm-i18n="edit.cancelPlacement">Cancel Placement</button>
                    <button type="button" class="btn btn-primary btn-sm" id="edit-accept-btn" data-cm-i18n="edit.accept">Accept</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    (async function () {
        'use strict';

        await CMI18n.init(window.__CM_LOCALE__ || 'en', window.__CM_I18N_JSON_BASE__ || '/static/i18n/civic-mason/');
        document.querySelectorAll('[data-cm-max-label]').forEach(function (el) {
            el.textContent = CMI18n.formatNumber(200);
        });
        var muralImgEl = document.getElementById('civic-mason-mural-img');
        if (muralImgEl) muralImgEl.setAttribute('alt', CMI18n.t('a11y.muralAlt'));

        /* ── Constants ────────────────────────────────────────────────────── */
        const GAP              = 3;
        const BASE_BRICK_W     = 36;
        const BASE_BRICK_H     = 18;
        const MIN_COLS         = 25;
        const MOVE_THRESH      = 6;   // px  – movement to trigger drag
        const SNAP_DIST        = 320; // px  – generous snap radius
        const MURAL_PALETTE    = ['#c4543d','#a84832','#8b3a28','#d4735a','#b85a42','#9d4830','#7a3620'];
        const YEAR_COLORS      = {2024:'#e74c3c',2025:'#3498db',2026:'#2ecc71',2027:'#f39c12',2028:'#9b59b6',2029:'#1abc9c',2030:'#e67e22'};
        const DEFAULT_COLOR    = '#c95a3d';

        /* ── DOM refs ─────────────────────────────────────────────────────── */
        const gridEl         = document.getElementById('civic-mason-grid');
        const floatingBrick  = document.getElementById('floating-brick');
        const ineligibleCard = document.getElementById('ineligible-card');
        const ineligibleTitle = document.getElementById('ineligible-title');
        const ineligibleBody  = document.getElementById('ineligible-body');
        const ineligibleBtn   = document.getElementById('ineligible-btn');
        const devModeBar      = document.getElementById('cm-dev-mode-bar');
        const demoToggle      = document.getElementById('cm-demo-toggle');

        /* ── Mutable state ────────────────────────────────────────────────── */
        let bricks            = [];
        let occupied          = {};
        let cols              = MIN_COLS;
        let brickW            = BASE_BRICK_W;
        let brickH            = BASE_BRICK_H;
        let yMax              = 5;

        let eligible          = false;
        let brickShown        = false;
        let selectedColorIdx  = 0;
        let brickMessage      = '';

        // Drag state
        let isDragging        = false;
        let mdX = 0, mdY = 0; // mousedown position
        let snapSlot          = null;

        // Edit-window state
        let ewTimer     = null;
        let ewBrickId   = null;
        let ewBrickEl   = null;
        let ewBadgeEl   = null;

        /* ── Helpers ──────────────────────────────────────────────────────── */
        function esc(s) {
            if (!s) return '';
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }

        function getColor(year) {
            if (year >= 2031 && year < 2031 + MURAL_PALETTE.length) return MURAL_PALETTE[year - 2031];
            return YEAR_COLORS[year] || DEFAULT_COLOR;
        }

        function currentColor() { return MURAL_PALETTE[selectedColorIdx] || DEFAULT_COLOR; }

        function hasSupport(x, y) {
            if (y <= 0) return true;
            const l = (x - 0.5).toFixed(1), r = (x + 0.5).toFixed(1);
            const yb = (y - 1).toFixed(1);
            return !!(occupied[l + ',' + yb] || occupied[r + ',' + yb]);
        }

        /* ── Grid dimensions ──────────────────────────────────────────────── */
        function calcDimensions() {
            const img = document.getElementById('civic-mason-mural-img');
            const wrap = gridEl.closest('.civic-mason-mural-inner') || gridEl.parentElement;
            const cw = (img && img.offsetWidth > 0 ? img.offsetWidth : (wrap && wrap.offsetWidth)) || 400;
            cols   = Math.max(MIN_COLS, Math.floor(cw / (BASE_BRICK_W + GAP))) + 1;
            brickW = Math.max(10, Math.floor((cw - (cols - 1) * GAP) / cols));
            brickH = Math.max(8,  Math.floor(brickW / 2));
            // Keep floating brick proportional to grid bricks (3× scale for ergonomics)
            const fb = document.getElementById('floating-brick');
            if (fb) {
                const fw = Math.max(48, brickW * 3);
                const fh = Math.max(24, brickH * 3);
                fb.style.width  = fw + 'px';
                fb.style.height = fh + 'px';
                fb._fw = fw;
                fb._fh = fh;
            }
        }

        /* ── Grid render ──────────────────────────────────────────────────── */
        function renderGrid() {
            calcDimensions();
            occupied = {};
            bricks.forEach(b => {
                occupied[parseFloat(b.grid_x).toFixed(1) + ',' + parseFloat(b.grid_y).toFixed(1)] = b;
            });
            const wallW = cols * (brickW + GAP) - GAP;
            const wallH = (yMax + 1) * (brickH + GAP) - GAP;

            let html = '<div class="cm-wall" style="position:relative;width:' + wallW + 'px;height:' + wallH + 'px;">';

            for (let y = 0; y <= yMax; y++) {
                const half = (y % 2 === 1);
                for (let xi = 0; xi < cols; xi++) {
                    const xv  = xi + (half ? 0.5 : 0);
                    const key = xv.toFixed(1) + ',' + y.toFixed(1);
                    const b   = occupied[key];
                    const lx  = Math.round(xv * (brickW + GAP));
                    const ty  = Math.round((yMax - y) * (brickH + GAP));

                    if (b) {
                        const color = getColor(b.year);
                        const msg   = esc((b.message || '').slice(0, 200));
                        const rawN  = (b.user_display_name || '').trim();
                        let dispN   = rawN;
                        if (!rawN || rawN === 'Anonymous') dispN = CMI18n.t('brick.anonymous');
                        else if (rawN === 'Unknown') dispN = CMI18n.t('brick.unknown');
                        const name  = esc(dispN);
                        const tip   = name + (msg ? ': ' + msg : '');
                        html += '<div class="cm-brick" style="left:' + lx + 'px;top:' + ty + 'px;'
                              + 'width:' + brickW + 'px;height:' + brickH + 'px;background-color:' + color + ';"'
                              + ' title="' + tip + '" data-bs-toggle="tooltip" data-bs-placement="top"'
                              + ' data-x="' + xv + '" data-y="' + y + '" data-bid="' + b.id + '"></div>';
                    } else if (hasSupport(xv, y)) {
                        const dzOp = eligible ? '0.40' : '0';
                        html += '<div class="cm-dz" style="left:' + lx + 'px;top:' + ty + 'px;'
                              + 'width:' + brickW + 'px;height:' + brickH + 'px;opacity:' + dzOp + ';"'
                              + ' data-x="' + xv + '" data-y="' + y + '"></div>';
                    }
                }
            }
            html += '</div>';
            gridEl.innerHTML = html;

            gridEl.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
                try { new bootstrap.Tooltip(el); } catch (_) {}
            });

            // Reattach edit-window click if brick still on board
            if (ewBrickId) {
                ewBrickEl = gridEl.querySelector('[data-bid="' + ewBrickId + '"]');
                if (ewBrickEl) {
                    ewBrickEl.classList.add('cm-ew-pending');
                    attachEwClick(ewBrickEl);
                } else {
                    clearEditWindow(); // brick gone
                }
            }
        }

        /* ── Floating brick ───────────────────────────────────────────────── */
        function updateBrickColor() {
            floatingBrick.style.setProperty('--fc', currentColor());
        }

        function showBrick() {
            if (brickShown || !eligible || suppressFloatingBrick) return;
            brickShown = true;
            floatingBrick.classList.add('visible');
            floatingBrick.style.left = '50%';
            floatingBrick.style.top  = '50%';
            floatingBrick.style.pointerEvents = 'auto';
            updateBrickColor();
        }

        function hideBrick() {
            if (isDragging) return;
            hideFloatingBrickVisual();
        }

        /** Always hide floating brick (e.g. when a modal is open). Ignores drag state. */
        function hideFloatingBrickVisual() {
            brickShown = false;
            floatingBrick.classList.remove('visible');
            floatingBrick.style.setProperty('--glow', 0);
            floatingBrick.style.pointerEvents = 'none';
        }

        /* True while any Civic Mason modal is open — keeps floating brick off and below modal stack */
        let suppressFloatingBrick = false;

        /* ── Mouse proximity + drag ───────────────────────────────────────── */
        let hasMovedMouse = false;
        document.addEventListener('mousemove', function onProximity(e) {
            if (!eligible || suppressFloatingBrick) return;
            hasMovedMouse = true;
            if (!brickShown && !isDragging) showBrick();
            if (isDragging) return; // handled by onDragMove

            const r   = floatingBrick.getBoundingClientRect();
            const cx  = r.left + r.width  / 2;
            const cy  = r.top  + r.height / 2;
            const d   = Math.hypot(e.clientX - cx, e.clientY - cy);
            const g   = Math.max(0, Math.min(1, 1 - d / 280));
            floatingBrick.style.setProperty('--glow', g);
            floatingBrick.style.pointerEvents = d < 100 ? 'auto' : 'none';
        });

        document.addEventListener('mouseleave', function(e) {
            if (!e.relatedTarget) hideBrick();
        });

        /* Drag detect and drag move ─────────────────────────────────────── */
        function onDragDetect(e) {
            if (Math.hypot(e.clientX - mdX, e.clientY - mdY) >= MOVE_THRESH) {
                document.removeEventListener('mousemove', onDragDetect);
                startDragMode(e);
            }
        }

        function startDragMode(e) {
            isDragging = true;
            floatingBrick.style.pointerEvents = 'none';
            floatingBrick.style.left = e.clientX + 'px';
            floatingBrick.style.top  = e.clientY + 'px';
            floatingBrick.classList.add('dragging');
            // Make every drop zone clearly visible while dragging
            gridEl.querySelectorAll('.cm-dz').forEach(z => { z.style.opacity = '0.75'; });
            document.addEventListener('mousemove', onDragMove);
        }

        function onDragMove(e) {
            const nearest = findNearestSlot(e.clientX, e.clientY);
            if (nearest) {
                // Visually snap the floating brick to the slot center
                const r  = nearest.getBoundingClientRect();
                const sx = r.left + r.width  / 2;
                const sy = r.top  + r.height / 2;
                floatingBrick.style.left = sx + 'px';
                floatingBrick.style.top  = sy + 'px';
                // Scale the floating brick to match the slot dimensions exactly
                const fw = floatingBrick._fw || 64;
                const fh = floatingBrick._fh || 32;
                const scx = (r.width  / fw).toFixed(4);
                const scy = (r.height / fh).toFixed(4);
                floatingBrick.style.transform = 'translate(-50%,-50%) scale(' + scx + ',' + scy + ')';
            } else {
                floatingBrick.style.left = e.clientX + 'px';
                floatingBrick.style.top  = e.clientY + 'px';
                floatingBrick.style.transform = 'translate(-50%,-50%) scale(1.1)';
            }
            updateSnap(nearest);
            snapSlot = nearest;
        }

        function findNearestSlot(cx, cy) {
            let best = null, bestD = SNAP_DIST;
            // ONLY search drop zones (.cm-dz), never bricks (.cm-brick)
            gridEl.querySelectorAll('.cm-dz').forEach(z => {
                const r = z.getBoundingClientRect();
                // Distance to nearest edge of the slot rect
                const closestX = Math.max(r.left, Math.min(cx, r.right));
                const closestY = Math.max(r.top,  Math.min(cy, r.bottom));
                const d = Math.hypot(cx - closestX, cy - closestY);
                if (d < bestD) { bestD = d; best = z; }
            });
            return best;
        }

        function updateSnap(slot) {
            gridEl.querySelectorAll('.cm-dz.snap').forEach(z => z.classList.remove('snap'));
            if (slot) slot.classList.add('snap');
        }

        /* Mouse down on floating brick ──────────────────────────────────── */
        floatingBrick.addEventListener('mousedown', function(e) {
            if (!eligible) return;
            e.preventDefault();
            e.stopPropagation();
            mdX = e.clientX;
            mdY = e.clientY;
            document.addEventListener('mousemove', onDragDetect);
            document.addEventListener('mouseup', onMouseUp, { once: true });
        });

        function onMouseUp(e) {
            document.removeEventListener('mousemove', onDragDetect);
            document.removeEventListener('mousemove', onDragMove);

            const moved = Math.hypot(e.clientX - mdX, e.clientY - mdY);

            if (isDragging) {
                isDragging = false;
                // Restore drop zone base opacity
                gridEl.querySelectorAll('.cm-dz').forEach(z => {
                    z.style.opacity = eligible ? '0.40' : '0';
                    z.classList.remove('snap');
                });
                
                floatingBrick.classList.remove('dragging');
                
                if (snapSlot) {
                    const gx = parseFloat(snapSlot.dataset.x);
                    const gy = parseFloat(snapSlot.dataset.y);
                    snapSlot = null;
                    // Hide the floating brick immediately after placement
                    hideBrick();
                    placeBrickAt(gx, gy);
                } else {
                    // No snap — restore to center
                    floatingBrick.style.left      = '50%';
                    floatingBrick.style.top       = '50%';
                    floatingBrick.style.transform = 'translate(-50%,-50%) scale(1)';
                    floatingBrick.style.pointerEvents = 'none';
                    snapSlot = null;
                }
            } else if (moved < MOVE_THRESH) {
                // Quick tap → open config modal
                openConfigModal();
            }
        }

        /* ── Placement ────────────────────────────────────────────────────── */
        async function placeBrickAt(gx, gy) {
            try {
                const res  = await fetch('/api/civic-mason/bricks/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ grid_x: gx, grid_y: gy, message: brickMessage, color_index: selectedColorIdx })
                });
                const data = await res.json();
                if (res.ok) {
                    await loadBricks(false); // no auto-scroll — we handle it below
                    const el = gridEl.querySelector('[data-bid="' + data.brick.id + '"]');
                    if (el) {
                        // Scroll the new brick into view, then start the edit window
                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        showToast(CMI18n.t('toast.placed'), 'success');
                        setTimeout(function () { startEditWindow(data.brick.id, el); }, 300);
                    } else {
                        // Fallback: just scroll to the grid
                        gridEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
                        showToast(CMI18n.t('toast.placedAt', { x: CMI18n.formatNumber(gx), y: CMI18n.formatNumber(gy) }), 'success');
                    }
                } else {
                    showToast(CMI18n.apiErrorMessage(data || {}), 'danger');
                }
            } catch (err) {
                console.error(err);
                showToast(CMI18n.t('toast.failedPlace'), 'danger');
            }
        }

        /* ── Edit window (5-second cancel) ───────────────────────────────── */
        function startEditWindow(brickId, el) {
            clearEditWindow();
            ewBrickId = brickId;
            ewBrickEl = el;

            el.classList.add('cm-ew-pending');

            const badge = document.createElement('span');
            badge.className = 'cm-ew-badge';
            badge.textContent = '5';
            el.appendChild(badge);
            ewBadgeEl = badge;

            let n = 5;
            ewTimer = setInterval(() => {
                n--;
                badge.textContent = n;
                if (n <= 0) clearEditWindow(); // permanent, no action needed
            }, 1000);

            attachEwClick(el);
        }

        function attachEwClick(el) {
            el._ewHandler = function onEwClick(e) {
                e.stopPropagation();
                const id = ewBrickId;
                clearEditWindow();
                openEditModal(id);
            };
            el.addEventListener('click', el._ewHandler, { once: true });
        }

        function clearEditWindow() {
            if (ewTimer) { clearInterval(ewTimer); ewTimer = null; }
            if (ewBadgeEl) { try { ewBadgeEl.remove(); } catch (_) {} ewBadgeEl = null; }
            if (ewBrickEl) {
                ewBrickEl.classList.remove('cm-ew-pending');
                if (ewBrickEl._ewHandler) {
                    ewBrickEl.removeEventListener('click', ewBrickEl._ewHandler);
                    ewBrickEl._ewHandler = null;
                }
            }
            ewBrickId = null;
            ewBrickEl = null;
        }

        /* ── Config modal (pre-placement) ────────────────────────────────── */
        function openConfigModal() {
            suppressFloatingBrick = true;
            hideFloatingBrickVisual();
            buildPalette(document.getElementById('config-palette'), selectedColorIdx, false);
            const msgEl = document.getElementById('config-msg');
            msgEl.value = brickMessage;
            document.getElementById('config-msg-count').textContent = CMI18n.formatNumber(brickMessage.length);
            bootstrap.Modal.getOrCreateInstance(document.getElementById('configBrickModal')).show();
        }

        document.getElementById('config-msg').addEventListener('input', function () {
            brickMessage = this.value.slice(0, 200);
            document.getElementById('config-msg-count').textContent = CMI18n.formatNumber(brickMessage.length);
        });

        /* ── Edit modal (post-placement) ─────────────────────────────────── */
        function openEditModal(brickId) {
            suppressFloatingBrick = true;
            hideFloatingBrickVisual();
            buildPalette(document.getElementById('edit-palette'), selectedColorIdx, false);
            const msgEl = document.getElementById('edit-msg');
            msgEl.value = brickMessage;
            document.getElementById('edit-msg-count').textContent = CMI18n.formatNumber(brickMessage.length);

            const modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('editBrickModal'));
            modal.show();

            document.getElementById('edit-accept-btn').onclick = async () => {
                const msg = document.getElementById('edit-msg').value.slice(0, 200);
                brickMessage = msg;
                modal.hide();
                try {
                    const res = await fetch('/api/civic-mason/bricks/' + brickId, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'same-origin',
                        body: JSON.stringify({ color_index: selectedColorIdx, message: msg })
                    });
                    if (res.ok) {
                        await loadBricks(false);
                        showToast(CMI18n.t('toast.updated'), 'success');
                    }
                } catch (err) { console.error(err); }
            };

            document.getElementById('edit-cancel-placement-btn').onclick = async () => {
                modal.hide();
                try {
                    const res = await fetch('/api/civic-mason/bricks/' + brickId, { method: 'DELETE', credentials: 'same-origin' });
                    if (res.ok) {
                        await loadBricks(false);
                        showToast(CMI18n.t('toast.removed'), 'info');
                    } else {
                        var delData = {};
                        try { delData = await res.json(); } catch (_) {}
                        showToast(CMI18n.apiErrorMessage(delData), 'danger');
                    }
                } catch (err) { 
                    console.error('DELETE error:', err);
                    showToast(CMI18n.t('toast.removeError'), 'danger');
                }
            };
        }

        document.getElementById('edit-msg').addEventListener('input', function () {
            document.getElementById('edit-msg-count').textContent = CMI18n.formatNumber((this.value || '').length);
        });

        ['configBrickModal', 'editBrickModal'].forEach(function (mid) {
            var m = document.getElementById(mid);
            if (!m) return;
            m.addEventListener('show.bs.modal', function () {
                suppressFloatingBrick = true;
                hideFloatingBrickVisual();
            });
            m.addEventListener('hidden.bs.modal', function () {
                suppressFloatingBrick = false;
            });
        });

        /* ── Color palette builder ────────────────────────────────────────── */
        function buildPalette(container, activeIdx, forEdit) {
            container.innerHTML = '';
            MURAL_PALETTE.forEach(function (c, i) {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'cm-swatch' + (i === activeIdx ? ' active' : '');
                btn.style.background = c;
                btn.dataset.idx = i;
                btn.setAttribute('aria-label', CMI18n.t('palette.colorN', { n: CMI18n.formatNumber(i + 1) }));

                btn.addEventListener('click', function () {
                    container.querySelectorAll('.cm-swatch').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    selectedColorIdx = i;
                    updateBrickColor();
                });

                btn.addEventListener('dblclick', function () {
                    container.querySelectorAll('.cm-swatch').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    selectedColorIdx = i;
                    updateBrickColor();
                    // Double-click closes the config modal only (not edit modal)
                    const cfgModal = bootstrap.Modal.getInstance(document.getElementById('configBrickModal'));
                    if (cfgModal) cfgModal.hide();
                });

                container.appendChild(btn);
            });
        }

        /* ── Load bricks ──────────────────────────────────────────────────── */
        async function loadBricks(scrollAfter) {
            try {
                const res  = await fetch('/api/civic-mason/bricks/', { credentials: 'same-origin' });
                const data = await res.json();
                if (!res.ok) {
                    gridEl.innerHTML = '<p class="text-white-50 text-center py-4">' + esc(CMI18n.t('grid.loadError')) + '</p>';
                    return;
                }
                bricks = data.bricks || [];
                calcDimensions();
                yMax = bricks.length === 0 ? 5 : Math.max(5, Math.max(...bricks.map(b => b.grid_y)) + 1);
                renderGrid();
                if (scrollAfter) {
                    // Scroll to the grid (bottom of mural) to show the active area
                    setTimeout(function () {
                        gridEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
                    }, 120);
                }
            } catch (err) {
                console.error('loadBricks:', err);
                gridEl.innerHTML = '<p class="text-white-50 text-center py-4">' + esc(CMI18n.t('grid.loadError')) + '</p>';
            }
        }

        /* ── Eligibility check ────────────────────────────────────────────── */
        async function checkEligible() {
            try {
                const res  = await fetch('/api/civic-mason/eligible/', { credentials: 'same-origin' });
                if (res.status === 401) {
                    if (devModeBar) devModeBar.classList.add('d-none');
                    ineligibleTitle.textContent = CMI18n.t('ineligible.loginTitle');
                    ineligibleBody.textContent = CMI18n.t('ineligible.loginBody');
                    ineligibleBtn.classList.add('d-none');
                    ineligibleCard.classList.remove('d-none');
                    return;
                }
                const data = await res.json();
                eligible = !!data.eligible;

                if (data.dev_tools && devModeBar && demoToggle) {
                    devModeBar.classList.remove('d-none');
                    demoToggle.checked = !!data.demo_mode;
                    if (!demoToggle._cmBound) {
                        demoToggle._cmBound = true;
                        demoToggle.addEventListener('change', async function () {
                            try {
                                await fetch('/api/civic-mason/demo-mode/', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    credentials: 'same-origin',
                                    body: JSON.stringify({ enabled: demoToggle.checked })
                                });
                                await checkEligible();
                                await loadBricks(false);
                            } catch (e) { console.error(e); }
                        });
                    }
                } else if (devModeBar) {
                    devModeBar.classList.add('d-none');
                }

                ineligibleCard.classList.add('d-none');
                if (!eligible) {
                    if (data.reason === 'already_placed_this_year') {
                        var uy = new Date().getUTCFullYear();
                        ineligibleTitle.textContent = CMI18n.t('ineligible.yearTitle');
                        ineligibleBody.textContent = CMI18n.t('ineligible.yearBody', {
                            year: CMI18n.formatYearUtc(uy),
                            nextYear: CMI18n.formatYearUtc(uy + 1)
                        });
                        ineligibleBtn.classList.add('d-none');
                    } else {
                        ineligibleTitle.textContent = CMI18n.t('ineligible.badgeTitle');
                        ineligibleBody.textContent = CMI18n.t('ineligible.badgeBody');
                        ineligibleBtn.classList.remove('d-none');
                    }
                    ineligibleCard.classList.remove('d-none');
                }
            } catch (_) {
                if (devModeBar) devModeBar.classList.add('d-none');
                ineligibleCard.classList.remove('d-none');
            }
        }

        /* ── Toast ────────────────────────────────────────────────────────── */
        function showToast(msg, type) {
            const wrap = document.createElement('div');
            wrap.className = 'position-fixed bottom-0 end-0 p-3';
            wrap.style.zIndex = 9999;
            wrap.innerHTML = '<div class="alert alert-' + type + ' alert-dismissible fade show mb-0 shadow" role="alert">'
                           + esc(msg) + '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>';
            document.body.appendChild(wrap);
            setTimeout(() => wrap.remove(), 4500);
        }

        /* ── Init ─────────────────────────────────────────────────────────── */
        (async function init() {
            await checkEligible();
            await loadBricks(false); // don't auto-scroll yet
            // After a brief delay, scroll to the bottom where the bricks are
            setTimeout(function() {
                const wall = gridEl.querySelector('.cm-wall');
                if (wall) {
                    wall.scrollIntoView({ behavior: 'smooth', block: 'end' });
                }
            }, 500);
        })();

        // Re-render on mural image load and resize
        const muralImg = document.getElementById('civic-mason-mural-img');
        if (muralImg) {
            if (muralImg.complete && muralImg.naturalWidth > 0) {
                calcDimensions();
            }
            muralImg.addEventListener('load', function () {
                calcDimensions();
                renderGrid();
            });
        }
        if (window.ResizeObserver && muralImg) {
            let roInit = true;
            new ResizeObserver(function () {
                calcDimensions();
                renderGrid();
                // On first fire (image just loaded/sized), scroll to grid
                if (roInit && bricks.length === 0) {
                    roInit = false;
                    setTimeout(function () {
                        gridEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
                    }, 200);
                } else {
                    roInit = false;
                }
            }).observe(muralImg);
        } else {
            window.addEventListener('resize', function () { calcDimensions(); renderGrid(); });
        }
    })();
    </script>

    <style>
    /* ── Page layout ──────────────────────────────────────────────────────── */
    .civic-mason-fullpage {
        background: #1a1510;
        min-height: 100vh;
    }
    .civic-mason-header {
        position: sticky;
        top: 0;
        z-index: 20;
        padding: 0.85rem 1.5rem;
        background: rgba(20,15,10,0.92);
        backdrop-filter: blur(10px);
        color: #fff;
        border-bottom: 1px solid rgba(255,255,255,0.07);
    }
    .civic-mason-header .breadcrumb-item a { color: rgba(255,255,255,0.85); }
    .civic-mason-header .breadcrumb-item.active { color: rgba(255,255,255,0.55); }
    .cm-dev-bar {
        background: rgba(255,193,7,0.12);
        border: 1px solid rgba(255,193,7,0.35);
        color: #fff;
    }
    .cm-dev-bar .form-check-input { cursor: pointer; }

    /* ── Mural area ───────────────────────────────────────────────────────── */
    .civic-mason-mural-wrap {
        display: flex;
        justify-content: center;
    }
    .civic-mason-mural-inner {
        position: relative;
        display: block;
        width: 100%;
        max-width: 1400px;
    }
    .civic-mason-mural-img {
        display: block;
        width: 100%;
        height: auto;
        vertical-align: bottom;
    }
    .civic-mason-grid-container {
        position: absolute;
        bottom: 0; left: 0; right: 0;
        z-index: 2;
        display: flex;
        justify-content: center;
        align-items: flex-end;
        width: 100%;
        box-sizing: border-box;
    }

    /* ── Bricks and drop zones ────────────────────────────────────────────── */
    .cm-wall  { background: transparent; margin: 0 auto; }
    .cm-brick {
        position: absolute;
        border-radius: 1px;
        box-sizing: border-box;
        border: 1px solid rgba(0,0,0,0.4);
        cursor: help;
    }
    .cm-dz {
        position: absolute;
        border: 2px dashed rgba(255,255,255,0.35);
        border-radius: 2px;
        box-sizing: border-box;
        background: rgba(255,255,255,0.03);
        transition: opacity 0.12s, background 0.1s, box-shadow 0.1s, transform 0.1s;
    }
    .cm-dz.snap {
        opacity: 1 !important;
        background: rgba(255,200,70,0.45) !important;
        border: 2px solid rgba(255,225,90,1) !important;
        box-shadow: 0 0 14px 5px rgba(255,190,50,0.60) !important;
    }

    /* ── Edit-window pending state ────────────────────────────────────────── */
    .cm-brick.cm-ew-pending {
        cursor: pointer;
        animation: ew-pulse 0.85s ease-in-out infinite;
        position: absolute; /* already set inline; needed for badge stacking context */
        z-index: 3;
    }
    @keyframes ew-pulse {
        0%,100% { box-shadow: 0 0 0 0 rgba(255,215,80,0); }
        50%      { box-shadow: 0 0 0 5px rgba(255,215,80,0.6); }
    }
    .cm-ew-badge {
        position: absolute;
        top: -10px; right: -10px;
        width: 20px; height: 20px;
        border-radius: 50%;
        background: rgba(255,215,60,0.95);
        color: #222;
        font-size: 11px;
        font-weight: 800;
        line-height: 20px;
        text-align: center;
        pointer-events: none;
        z-index: 4;
        box-shadow: 0 0 6px 2px rgba(255,200,50,0.6);
    }

    /* ── Floating brick ───────────────────────────────────────────────────── */
    .floating-brick {
        position: fixed;
        left: 50%; top: 50%;
        /* width/height set dynamically by calcDimensions() */
        width: 64px; height: 32px;
        border-radius: 3px;
        background: var(--fc, #c95a3d);
        box-shadow:
            0 0 calc(var(--glow, 0) * 52px) calc(var(--glow, 0) * 18px) rgba(255,150,70,calc(var(--glow,0)*0.75)),
            0 3px 12px rgba(0,0,0,0.55);
        transform: translate(-50%, -50%) scale(0.6);
        opacity: 0;
        pointer-events: none;
        /* Below Bootstrap modal (1055) and backdrop (1050) so modals always win */
        z-index: 1030;
        cursor: pointer;
        /* two transitions: appearance vs drag (no transition during drag for tight tracking) */
        transition: opacity 0.22s ease, transform 0.22s ease, box-shadow 0.08s ease;
    }
    .floating-brick::before {
        content: '';
        position: absolute;
        inset: 20% 25%;
        background: rgba(255,255,255,0.12);
        border-radius: 1px;
    }
    .floating-brick::after {
        content: '';
        position: absolute;
        left: 8%; right: 8%; top: 50%;
        height: 1px;
        background: rgba(0,0,0,0.22);
    }
    .floating-brick.visible {
        opacity: 1;
        transform: translate(-50%, -50%) scale(1);
    }
    .floating-brick.dragging {
        /* Remove CSS transitions so brick tracks cursor instantly */
        transition: none;
    }

    /* ── Color swatches ───────────────────────────────────────────────────── */
    .cm-swatch {
        width: 34px; height: 34px;
        border: 3px solid transparent;
        border-radius: 5px;
        padding: 0;
        cursor: pointer;
        transition: border-color 0.12s, transform 0.12s;
    }
    .cm-swatch:hover  { transform: scale(1.12); border-color: rgba(255,255,255,0.5); }
    .cm-swatch.active { border-color: #fff; transform: scale(1.12); }

    /* ── Ineligible card ──────────────────────────────────────────────────── */
    .ineligible-card {
        position: fixed;
        bottom: 2rem; left: 50%;
        transform: translateX(-50%);
        background: rgba(30,25,20,0.88);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 12px;
        padding: 1.5rem 2rem;
        max-width: 340px;
        width: calc(100% - 2rem);
        text-align: center;
        color: #fff;
        z-index: 100;
    }
    </style>
    """

    content = content.replace('MURAL_URL_PLACEHOLDER', mural_url)
    content = content.replace('CM_I18N_JS_PLACEHOLDER', cm_i18n_js)
    content = content.replace('CM_LOCALE_PLACEHOLDER', locale)
    content = content.replace('CM_I18N_JSON_BASE_PLACEHOLDER', cm_i18n_json_base)
    return render_page(
        title='Civic Mason',
        content=content,
        user_menu=user_menu,
        theme=current_theme,
    )
