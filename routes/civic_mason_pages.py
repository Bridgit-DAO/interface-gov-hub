"""Civic Mason page: global brick wall. Badge-gated placement."""
from flask import Blueprint, session
from services.identity import get_current_user
from services.rendering import generate_user_menu, render_page

bp = Blueprint('civic_mason_pages', __name__, url_prefix='')


def _get_imports():
    from services.rendering import generate_user_menu, render_page
    return generate_user_menu, render_page


@bp.route('/civic-mason/')
def civic_mason_page():
    """Global Civic Mason wall: half-offset grid, badge-gated placement."""
    generate_user_menu, render_page = _get_imports()
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')

    content = """
    <div class="container mt-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item"><a href="/">Home</a></li>
                <li class="breadcrumb-item"><a href="/badges/">Recognition</a></li>
                <li class="breadcrumb-item active">Civic Mason</li>
            </ol>
        </nav>
        <div class="d-flex justify-content-between align-items-center mb-4">
            <div>
                <h1 class="mb-1"><i class="fas fa-th-large me-2"></i>Civic Mason</h1>
                <p class="text-muted mb-0">A symbolic wall where contributors with Civic Mason–eligible badges place bricks. Drag a brick to a slot, then confirm.</p>
            </div>
            <div id="brick-drag-source" class="d-none" style="cursor:grab;">
                <div class="border rounded d-inline-block p-2 text-center" style="width:48px;height:48px;background:var(--bs-primary);color:white;" draggable="true" title="Drag to grid">
                    <i class="fas fa-th-large"></i>
                </div>
                <small class="d-block text-muted mt-1">Drag to grid</small>
            </div>
            <button type="button" class="btn btn-primary" id="place-brick-btn" style="display:none"><i class="fas fa-plus me-2"></i>Place Brick</button>
        </div>

        <div id="civic-mason-grid" class="mb-4">
            <div class="text-center py-5">
                <div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="placeBrickConfirmModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title"><i class="fas fa-th-large me-2"></i>Confirm Placement</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" id="confirm-cancel-close"></button>
                </div>
                <div class="modal-body">
                    <p class="mb-2">Place brick at (<span id="confirm-grid-pos">0, 0</span>)?</p>
                    <div class="mb-3">
                        <label for="confirm-brick-message" class="form-label">Message (optional, max 200)</label>
                        <textarea class="form-control" id="confirm-brick-message" rows="2" maxlength="200" placeholder="Your message..."></textarea>
                        <small class="text-muted"><span id="confirm-msg-count">0</span>/200</small>
                    </div>
                    <div class="countdown-overlay bg-light rounded p-3 text-center">
                        <p class="mb-0">Confirming in <strong id="countdown-num">5</strong> seconds...</p>
                        <p class="small text-muted mb-0 mt-1">Click Cancel to abort</p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" id="confirm-cancel-btn-footer">Cancel</button>
                </div>
            </div>
        </div>
    </div>

    <script>
    (function() {
        const gridEl = document.getElementById('civic-mason-grid');
        const placeBtn = document.getElementById('place-brick-btn');
        const dragSource = document.getElementById('brick-drag-source');
        const dragBrick = dragSource ? dragSource.querySelector('[draggable="true"]') : null;

        const BRICK_SIZE = 40;
        const GAP = 4;
        const YEAR_COLORS = {
            2024: '#e74c3c', 2025: '#3498db', 2026: '#2ecc71', 2027: '#f39c12',
            2028: '#9b59b6', 2029: '#1abc9c', 2030: '#e67e22'
        };
        const DEFAULT_COLOR = '#34495e';

        let bricks = [];
        let occupied = {};
        let xMin = 0, xMax = 6, yMin = 0, yMax = 6;
        let countdownTimer = null;
        let pendingDrop = null;

        function esc(s) {
            if (!s) return '';
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        }

        function getColor(year) {
            return YEAR_COLORS[year] || DEFAULT_COLOR;
        }

        function hasSupport(x, y) {
            if (y <= 0) return true;
            const left = (x - 0.5).toFixed(1), right = (x + 0.5).toFixed(1);
            const yBelow = (y - 1).toFixed(1);
            return occupied[left + ',' + yBelow] || occupied[right + ',' + yBelow];
        }

        function renderGrid() {
            occupied = {};
            bricks.forEach(b => {
                const k = parseFloat(b.grid_x).toFixed(1) + ',' + parseFloat(b.grid_y).toFixed(1);
                occupied[k] = b;
            });
            const w = (xMax - xMin + 2) * (BRICK_SIZE + GAP);
            const h = (yMax - yMin + 2) * (BRICK_SIZE + GAP);
            let html = '';
            if (bricks.length === 0) {
                html += '<p class="text-muted small mb-2">No bricks yet. Drag a brick from above to a slot below.</p>';
            }
            html += '<div class="civic-mason-wall" style="position:relative;width:' + w + 'px;height:' + h + 'px;">';
            for (let y = yMin; y <= yMax; y++) {
                const isHalfRow = (y % 2 === 1);
                for (let xi = 0; xi <= xMax - xMin + 1; xi++) {
                    const xVal = xMin + xi + (isHalfRow ? 0.5 : 0);
                    const key = xVal.toFixed(1) + ',' + y;
                    const b = occupied[key];
                    const left = (xVal - xMin) * (BRICK_SIZE + GAP);
                    const top = (y - yMin) * (BRICK_SIZE + GAP);
                    if (b) {
                        const color = getColor(b.year);
                        const msg = esc((b.message || '').slice(0, 200));
                        const name = esc(b.user_display_name || 'Anonymous');
                        html += '<div class="brick-cell border rounded" style="position:absolute;left:' + left + 'px;top:' + top + 'px;width:' + BRICK_SIZE + 'px;height:' + BRICK_SIZE + 'px;background:' + color + ';" title="' + name + (msg ? ': ' + msg : '') + '" data-bs-toggle="tooltip" data-x="' + xVal + '" data-y="' + y + '"></div>';
                    } else if (hasSupport(xVal, y)) {
                        html += '<div class="drop-zone border border-2 border-dashed rounded" style="position:absolute;left:' + left + 'px;top:' + top + 'px;width:' + BRICK_SIZE + 'px;height:' + BRICK_SIZE + 'px;background:rgba(0,0,0,0.05);" data-x="' + xVal + '" data-y="' + y + '" data-droppable="true"></div>';
                    }
                }
            }
            html += '</div>';
            gridEl.innerHTML = html;
            [].forEach.call(gridEl.querySelectorAll('[data-bs-toggle="tooltip"]'), el => new bootstrap.Tooltip(el));
            gridEl.querySelectorAll('.drop-zone').forEach(el => {
                el.addEventListener('dragover', onDragOver);
                el.addEventListener('drop', onDrop);
                el.addEventListener('dragenter', function(e) { if (e.dataTransfer.types.indexOf('text/plain') >= 0) el.classList.add('drop-hover'); });
                el.addEventListener('dragleave', function() { el.classList.remove('drop-hover'); });
            });
        }

        function onDragOver(e) {
            if (e.dataTransfer.types.indexOf('text/plain') >= 0) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'copy';
            }
        }

        function onDrop(e) {
            e.preventDefault();
            e.currentTarget.classList.remove('drop-hover');
            const x = parseFloat(e.currentTarget.dataset.x);
            const y = parseFloat(e.currentTarget.dataset.y);
            showConfirmModal(x, y);
        }

        function showConfirmModal(gridX, gridY) {
            pendingDrop = { grid_x: gridX, grid_y: gridY };
            document.getElementById('confirm-grid-pos').textContent = gridX + ', ' + gridY;
            document.getElementById('confirm-brick-message').value = '';
            document.getElementById('confirm-msg-count').textContent = '0';
            document.getElementById('countdown-num').textContent = '5';
            const modal = document.getElementById('placeBrickConfirmModal');
            bootstrap.Modal.getOrCreateInstance(modal).show();
            let sec = 5;
            if (countdownTimer) clearInterval(countdownTimer);
            countdownTimer = setInterval(function() {
                sec--;
                document.getElementById('countdown-num').textContent = sec;
                if (sec <= 0) {
                    clearInterval(countdownTimer);
                    countdownTimer = null;
                    confirmPlacement();
                }
            }, 1000);
        }

        function cancelConfirm() {
            if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
            pendingDrop = null;
            bootstrap.Modal.getInstance(document.getElementById('placeBrickConfirmModal')).hide();
        }

        async function confirmPlacement() {
            if (!pendingDrop) return;
            const message = (document.getElementById('confirm-brick-message').value || '').trim().slice(0, 200);
            cancelConfirm();
            try {
                const res = await fetch('/api/civic-mason/bricks/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'same-origin',
                    body: JSON.stringify({ grid_x: pendingDrop.grid_x, grid_y: pendingDrop.grid_y, message: message })
                });
                const data = await res.json();
                if (res.ok) {
                    loadBricks();
                } else {
                    alert(data.error || 'Failed to place brick');
                }
            } catch (e) {
                console.error(e);
                alert('Failed to place brick');
            }
        }

        async function loadBricks() {
            try {
                const res = await fetch('/api/civic-mason/bricks/', { credentials: 'same-origin' });
                const data = await res.json();
                if (!res.ok) {
                    gridEl.innerHTML = '<p class="text-muted">Unable to load bricks.</p>';
                    return;
                }
                bricks = data.bricks || [];
                if (bricks.length === 0) {
                    xMin = 0; xMax = 6; yMin = 0; yMax = 6;
                } else {
                    const xs = bricks.map(b => b.grid_x);
                    const ys = bricks.map(b => b.grid_y);
                    xMin = Math.min(0, ...xs) - 1;
                    xMax = Math.max(6, ...xs) + 1;
                    yMin = Math.min(0, ...ys) - 1;
                    yMax = Math.max(6, ...ys) + 1;
                }
                renderGrid();
            } catch (err) {
                console.error('loadBricks:', err);
                gridEl.innerHTML = '<p class="text-muted">Unable to load bricks.</p>';
            }
        }

        async function checkEligible() {
            try {
                const res = await fetch('/api/civic-mason/eligible/', { credentials: 'same-origin' });
                const data = await res.json();
                if (data.eligible) {
                    if (placeBtn) placeBtn.style.display = 'inline-block';
                    if (dragSource) { dragSource.classList.remove('d-none'); dragSource.classList.add('d-flex', 'flex-column', 'align-items-center'); }
                }
            } catch (e) {}
        }

        if (dragBrick) {
            dragBrick.addEventListener('dragstart', function(e) {
                e.dataTransfer.setData('text/plain', 'brick');
                e.dataTransfer.effectAllowed = 'copy';
                dragBrick.style.opacity = '0.5';
            });
            dragBrick.addEventListener('dragend', function() { dragBrick.style.opacity = '1'; });
        }

        placeBtn.addEventListener('click', function() {
            if (dragSource) dragSource.scrollIntoView({ behavior: 'smooth' });
        });

        document.getElementById('confirm-cancel-close').addEventListener('click', cancelConfirm);
        document.getElementById('confirm-cancel-btn-footer').addEventListener('click', cancelConfirm);
        document.getElementById('placeBrickConfirmModal').addEventListener('hidden.bs.modal', cancelConfirm);

        document.getElementById('confirm-brick-message').addEventListener('input', function() {
            document.getElementById('confirm-msg-count').textContent = (this.value || '').length;
        });

        loadBricks();
        checkEligible();
    })();
    </script>
    <style>
    .drop-zone.drop-hover { background: rgba(var(--bs-primary-rgb), 0.2) !important; }
    </style>
    """

    return render_page(
        title='Civic Mason',
        content=content,
        user_menu=user_menu,
        theme=current_theme,
    )
