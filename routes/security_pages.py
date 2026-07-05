"""Security settings page: two-factor authentication management."""
import html as html_mod

from flask import Blueprint, redirect, session

from models import User
from services.directory_ui import gh_page_close, gh_page_header, gh_page_open
from services.identity import get_current_user, require_auth

bp = Blueprint('security_pages', __name__, url_prefix='')


def _get_imports():
    from services.rendering import render_page, generate_user_menu
    return render_page, generate_user_menu


@bp.route('/profile/security/')
@require_auth
def profile_security():
    render_page, generate_user_menu = _get_imports()
    current_user_data = get_current_user()
    if not current_user_data:
        return redirect('/login/')

    user = User.query.get(current_user_data['id'])
    if not user:
        return redirect('/')

    user_menu = generate_user_menu()
    current_theme = session.get('theme', 'dark')
    account = html_mod.escape(user.email or user.username or '')

    content = f"""
    {gh_page_open()}
    {gh_page_header('Security', 'Two-factor authentication and backup codes', 'fa-shield-halved')}
    <div class="row">
        <div class="col-lg-8 mx-auto">
            <div class="living-module mb-4" id="gh-mfa-panel">
                <div class="living-module-header d-flex justify-content-between align-items-center flex-wrap gap-2">
                    <div class="d-flex align-items-center gap-2">
                        <div class="living-module-icon"><i class="fas fa-mobile-screen"></i></div>
                        <h5 class="living-module-title mb-0">Authenticator app</h5>
                    </div>
                    <span class="badge bg-secondary" id="gh-mfa-status-badge">Loading…</span>
                </div>
                <div class="living-module-body">
                    <p class="text-muted small">
                        Use Google Authenticator, 1Password, Authy, or any TOTP app.
                        Once enabled, the same factor will apply to Gov Hub sign-in
                        (Canopi and other Bridgit apps in a later release).
                    </p>
                    <p class="text-muted small mb-3">Account: <strong>{account}</strong></p>

                    <div id="gh-mfa-device-list" class="mb-3"></div>

                    <div class="d-flex flex-wrap gap-2 mb-3">
                        <button type="button" class="btn btn-primary btn-sm" id="gh-mfa-add-device-btn">
                            <i class="fas fa-plus me-1"></i>Add authenticator
                        </button>
                        <button type="button" class="btn btn-outline-secondary btn-sm d-none" id="gh-mfa-regen-codes-btn">
                            <i class="fas fa-key me-1"></i>Regenerate backup codes
                        </button>
                    </div>

                    <p class="text-muted small mb-0" id="gh-mfa-recovery-summary"></p>
                </div>
            </div>

            <div class="living-module mb-4 d-none" id="gh-mfa-enroll-panel">
                <div class="living-module-header">
                    <div class="living-module-icon"><i class="fas fa-qrcode"></i></div>
                    <h5 class="living-module-title">Set up authenticator</h5>
                </div>
                <div class="living-module-body">
                    <ol class="small text-muted mb-3">
                        <li>Scan the QR code or enter the secret key manually.</li>
                        <li>Enter the 6-digit code from your app to confirm.</li>
                        <li>Save your backup codes when shown – they are shown only once.</li>
                    </ol>
                    <div class="text-center mb-3">
                        <div id="gh-mfa-qr" class="d-inline-block p-2 bg-white rounded"></div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label small">Manual entry key</label>
                        <div class="input-group input-group-sm">
                            <input type="text" class="form-control font-monospace" id="gh-mfa-secret" readonly>
                            <button type="button" class="btn btn-outline-secondary" id="gh-mfa-copy-secret">Copy</button>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label class="form-label" for="gh-mfa-confirm-code">Verification code</label>
                        <input type="text" class="form-control" id="gh-mfa-confirm-code" inputmode="numeric"
                               autocomplete="one-time-code" maxlength="8" placeholder="000000">
                    </div>
                    <div class="d-flex gap-2">
                        <button type="button" class="btn btn-success btn-sm" id="gh-mfa-confirm-btn">Confirm</button>
                        <button type="button" class="btn btn-outline-secondary btn-sm" id="gh-mfa-cancel-enroll">Cancel</button>
                    </div>
                </div>
            </div>

            <div class="living-module mb-4 d-none" id="gh-mfa-codes-panel">
                <div class="living-module-header">
                    <div class="living-module-icon"><i class="fas fa-key"></i></div>
                    <h5 class="living-module-title">Backup codes</h5>
                </div>
                <div class="living-module-body">
                    <p class="text-warning small"><i class="fas fa-triangle-exclamation me-1"></i>
                        Copy or download these codes now. Each can be used once if you lose your authenticator.</p>
                    <ul class="list-unstyled font-monospace small mb-3" id="gh-mfa-codes-list"></ul>
                    <button type="button" class="btn btn-primary btn-sm" id="gh-mfa-codes-done">I saved my backup codes</button>
                </div>
            </div>

            <p class="text-muted small">
                <a href="/profile/edit/"><i class="fas fa-arrow-left me-1"></i>Back to profile edit</a>
            </p>
        </div>
    </div>
    {gh_page_close()}
    <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
    <script src="/static/js/gh-mfa.js"></script>
    """

    return render_page('Security - GovHub', content, theme=current_theme, user_menu=user_menu)
