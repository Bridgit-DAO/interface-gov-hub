"""Auth routes: login, logout, Web3Auth, api/user/me, api/user/display-name."""
import re
from datetime import datetime
from uuid import uuid4

from flask import Blueprint, jsonify, request, session, flash, redirect, url_for

from extensions import db
from models import User
from services.utils import check_rate_limit

bp = Blueprint('auth', __name__, url_prefix='')

LOGIN_TEMPLATE = """
<div class="gh-page container mt-4 gh-auth-panel">
    <header class="gh-page-header">
        <div class="gh-page-header-main">
            <div class="gh-page-header-icon"><i class="fas fa-sign-in-alt"></i></div>
            <div><h1 class="gh-page-title">Sign In</h1><p class="gh-page-lead">Connect your account to continue</p></div>
        </div>
    </header>
    <div class="row justify-content-center">
        <div class="col-md-6 col-lg-5">
            <div class="living-module mb-0">
                <div class="living-module-body text-center py-2">
                    <div id="flash-messages"></div>
                    <p class="text-muted mb-3" id="web3auth-login-hint">Sign in with Google or email</p>
                    <div id="web3auth-social-login" class="d-grid gap-2">
                        <button type="button" class="btn btn-primary btn-lg" id="web3auth-google-btn" disabled aria-busy="true" onclick="loginWithWeb3AuthGoogle()">
                            <i class="fab fa-google me-2" aria-hidden="true"></i>
                            Continue with Google
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-lg" id="web3auth-email-btn" disabled aria-busy="true" onclick="loginWithWeb3AuthEmail()">
                            <i class="fas fa-envelope me-2" aria-hidden="true"></i>
                            Continue with email
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""

# Common mistaken paths while on /login/ (relative links or address-bar edits).
_LOGIN_ADMIN_REDIRECTS = {
    'product-rollout': '/admin/product-rollout/',
    'nav-pills': '/admin/nav-pills/',
    'admin': '/admin/',
}


@bp.route('/login/<path:tail>')
def login_admin_shortcut(tail):
    """Redirect /login/product-rollout → login with ?next=/admin/product-rollout/."""
    from services.auth_redirect import login_url

    segment = (tail or '').strip('/').split('/')[0].lower()
    target = _LOGIN_ADMIN_REDIRECTS.get(segment)
    if target:
        return redirect(login_url(target))
    from flask import abort
    abort(404)


@bp.route('/login/', methods=['GET'])
def login():
    """Show dedicated login page with Web3Auth sign-in. Use ?next= or ?redirect= to return after login."""
    from services.rendering import _format_base_template, generate_user_menu
    from services.identity import get_current_user
    from services.auth_redirect import safe_return_path
    from services.campaign_auth import (
        build_campaign_handoff_redirect,
        redirect_vanity_login_to_hub,
        safe_campaign_return_url,
    )
    from config import BUILD_NUMBER

    return_to_raw = request.args.get('next') or request.args.get('redirect')
    hub_redirect = redirect_vanity_login_to_hub(return_to_raw)
    if hub_redirect is not None:
        return hub_redirect

    return_to = safe_campaign_return_url(return_to_raw) or safe_return_path(return_to_raw)
    current = get_current_user()
    if current:
        if return_to and return_to.startswith('https://'):
            return redirect(build_campaign_handoff_redirect(return_to, current['username']))
        return redirect(return_to or url_for('pages.home'))

    user_menu = generate_user_menu()
    current_theme = session.get('theme', current.get('theme', 'dark') if current else 'dark')
    return _format_base_template(
        title="Sign In - GovHub",
        theme=current_theme,
        user_menu=user_menu,
        content=LOGIN_TEMPLATE,
        build_number=BUILD_NUMBER,
    )


@bp.route('/logout/')
def logout():
    """User logout"""
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('pages.home'))


@bp.route('/register/', methods=['GET', 'POST'])
@bp.route('/register', methods=['GET', 'POST'])
def register_disabled():
    """Public registration is disabled; accounts are created via Web3Auth sign-in."""
    flash('Registration is closed. Sign in with Web3Auth to continue.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/api/auth/web3auth', methods=['POST'])
def web3auth_login():
    """Web3Auth login – requires a verified idToken from Web3Auth getIdentityToken()."""
    from flask import current_app
    from jwt.exceptions import InvalidTokenError, PyJWKClientError
    from services.web3auth_verify import identity_from_web3auth_claims, verify_web3auth_id_token

    client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', 'unknown')
    if not check_rate_limit(f"web3auth_{client_ip}", max_requests=50, window_seconds=600):
        return jsonify({'error': 'Too many sign-in attempts. Please wait a few minutes and try again.'}), 429

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        id_token = (data.get('idToken') or data.get('id_token') or '').strip()
        if not id_token:
            return jsonify({'error': 'idToken required'}), 400

        try:
            claims = verify_web3auth_id_token(id_token)
            identity = identity_from_web3auth_claims(claims)
        except (InvalidTokenError, PyJWKClientError, ValueError) as exc:
            current_app.logger.warning('Web3Auth token rejected: %s', exc)
            return jsonify({'error': 'Invalid or expired sign-in token'}), 401

        verifier_id = identity['verifierId']
        type_of_login = identity['typeOfLogin']
        email = identity['email']
        name = identity['name']
        profile_image = identity['profileImage']
        # Wallet addresses are optional UX metadata; never used for authentication.
        evm_address = (data.get('evmAddress') or '').strip() or None
        solana_address = (data.get('solanaAddress') or '').strip() or None
        bitcoin_address = (
            (data.get('bitcoinAddress') or data.get('badgeWalletAddress') or '')
            .strip()
            or None
        )

        user = User.query.filter_by(web3authVerifierId=verifier_id).first()
        if user:
            _update_user_from_web3auth(
                user,
                type_of_login=type_of_login,
                email=email,
                name=name,
                profile_image=profile_image,
                evm_address=evm_address,
                solana_address=solana_address,
                bitcoin_address=bitcoin_address,
            )
            db.session.commit()
        else:
            email_owner = None
            if email:
                normalized = email.strip().lower()
                email_owner = User.query.filter(
                    db.func.lower(User.email) == normalized
                ).first()
            if email_owner:
                existing_verifier = (email_owner.web3authVerifierId or '').strip()
                normalized_email = (email or '').strip().lower()
                prior_is_email_verifier = bool(
                    normalized_email
                    and existing_verifier
                    and existing_verifier.lower() == normalized_email
                )
                if (
                    existing_verifier
                    and existing_verifier != verifier_id
                    and not prior_is_email_verifier
                ):
                    return jsonify({
                        'error': (
                            'This email is already linked to another account. '
                            'Sign in with the method you used originally or contact support.'
                        ),
                    }), 409
                user = email_owner
                user.web3authVerifierId = verifier_id
                _update_user_from_web3auth(
                    user,
                    type_of_login=type_of_login,
                    email=email,
                    name=name,
                    profile_image=profile_image,
                    evm_address=evm_address,
                    solana_address=solana_address,
                    bitcoin_address=bitcoin_address,
                )
                db.session.commit()
            else:
                user = _create_user_from_web3auth(
                    verifier_id=verifier_id,
                    type_of_login=type_of_login,
                    email=email,
                    name=name,
                    profile_image=profile_image,
                    evm_address=evm_address,
                    solana_address=solana_address,
                    bitcoin_address=bitcoin_address,
                )
                db.session.add(user)
                db.session.flush()
                from services.document_follow_notifications import ensure_notification_unsubscribe_token
                from services.user_wallets import ensure_user_wallet_addresses

                # Wallet rows need user.id; SQLAlchemy Column defaults are not
                # applied until INSERT. Flush first, then provision.
                ensure_user_wallet_addresses(
                    user,
                    evm_address=evm_address,
                    solana_address=solana_address,
                    bitcoin_address=bitcoin_address,
                )
                ensure_notification_unsubscribe_token(user)
                db.session.commit()

        from services.mfa import create_challenge, user_mfa_enabled

        if user_mfa_enabled(user.id):
            challenge = create_challenge(user.id, client_id='govhub')
            return jsonify({
                'success': False,
                'mfaRequired': True,
                'challengeToken': challenge.id,
            })

        session['user'] = user.username
        session['theme'] = user.theme
        session.permanent = True
        session.modified = True

        try:
            from services.auth_layer_membership import ensure_auth_layer_memberships

            ensure_auth_layer_memberships(user, type_of_login)
        except Exception as auth_layer_err:
            current_app.logger.warning(
                'Auth layer membership sync failed: %s', auth_layer_err
            )

        safe_user_data = {
            'id': user.id,
            'username': user.username,
            'displayName': user.displayName,
            'oauthName': user.oauthName,
            'email': user.email,
            'profileImage': user.profileImage,
            'evmAddress': user.evmAddress,
            'solanaAddress': user.solanaAddress,
            'bitcoinAddress': getattr(user, 'bitcoinAddress', None),
            'typeOfLogin': user.typeOfLogin,
            'theme': user.theme,
        }
        return jsonify({'success': True, 'user': safe_user_data})

    except Exception as e:
        import traceback

        from sqlalchemy.exc import IntegrityError

        db.session.rollback()
        if isinstance(e, IntegrityError):
            err_text = str(e).lower()
            if 'custodial_wallet' in err_text:
                current_app.logger.error('Web3Auth login wallet provision failed: %s', e)
                return jsonify({
                    'error': 'Could not finish creating your account. Please try again.',
                }), 500
            current_app.logger.warning('Web3Auth login email conflict: %s', e)
            return jsonify({
                'error': (
                    'This email is already linked to another account. '
                    'Sign in with the method you used originally or contact support.'
                ),
            }), 409
        current_app.logger.error("Web3Auth login error: %s\n%s", e, traceback.format_exc())
        return jsonify({'error': 'Authentication failed'}), 500


def _update_user_from_web3auth(
    user,
    *,
    type_of_login,
    email,
    name,
    profile_image,
    evm_address,
    solana_address,
    bitcoin_address=None,
):
    from services.user_wallets import ensure_user_wallet_addresses
    from services.web3auth_verify import normalize_user_email

    user.typeOfLogin = type_of_login
    user.last_login = datetime.utcnow()
    if email:
        normalized = normalize_user_email(email)
        if normalized:
            if not user.email:
                conflict = User.query.filter(
                    db.func.lower(User.email) == normalized,
                    User.id != user.id,
                ).first()
                if not conflict:
                    user.email = normalized
            elif user.email.strip().lower() == normalized:
                # Fix casing only – never reassign a different mailbox on login.
                user.email = normalized
    if name:
        user.displayName = name
        user.displayNameSetAt = datetime.utcnow()
        user.oauthName = name
    if profile_image:
        from services.avatar import is_user_uploaded_profile_image

        if not is_user_uploaded_profile_image(user.profileImage):
            user.profileImage = profile_image
    ensure_user_wallet_addresses(
        user,
        evm_address=evm_address,
        solana_address=solana_address,
        bitcoin_address=bitcoin_address,
    )


def _create_user_from_web3auth(
    *,
    verifier_id,
    type_of_login,
    email,
    name,
    profile_image,
    evm_address,
    solana_address,
    bitcoin_address=None,
):
    existing_handles = [row[0] for row in db.session.query(User.username).all()]
    if type_of_login == 'wallet' and evm_address:
        short_address = f"{evm_address[:6]}...{evm_address[-4:]}"
        handle = f"wallet_{short_address}"
        counter = 1
        while handle in existing_handles:
            handle = f"wallet_{short_address}_{counter}"
            counter += 1
    else:
        base_handle = email.split('@')[0] if email else 'user'
        base_handle = re.sub(r'[^a-zA-Z0-9_]', '', base_handle)
        if len(base_handle) < 3:
            base_handle = 'user'
        handle = base_handle
        counter = 1
        while handle in existing_handles:
            handle = f"{base_handle}{counter}"
            counter += 1

    user = User(
        id=str(uuid4()),
        public_id=str(uuid4()),
        web3authVerifierId=verifier_id,
        typeOfLogin=type_of_login,
        displayName=name if name else None,
        displayNameSetAt=datetime.utcnow() if name else None,
        oauthName=name,
        email=email,
        profileImage=profile_image,
        username=handle,
        handle=handle,
        role='user',
        theme='dark',
        last_login=datetime.utcnow(),
    )
    return user


@bp.route('/api/user/me', methods=['GET'])
def get_user_profile():
    """Get current user profile"""
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    safe_user_data = {
        'id': user.id,
        'public_id': user.public_id,
        'username': user.username,
        'displayName': user.displayName,
        'displayNameSetAt': user.displayNameSetAt.isoformat() if user.displayNameSetAt else None,
        'oauthName': user.oauthName,
        'email': user.email,
        'profileImage': user.profileImage,
        'evmAddress': user.evmAddress,
        'solanaAddress': user.solanaAddress,
        'bitcoinAddress': getattr(user, 'bitcoinAddress', None),
        'typeOfLogin': user.typeOfLogin,
        'theme': user.theme
    }
    return jsonify({'user': safe_user_data})


@bp.route('/api/user/display-name', methods=['PUT'])
def update_display_name():
    """Update user display name"""
    username = session.get('user')
    if not username:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()
    if not data or 'displayName' not in data:
        return jsonify({'error': 'Display name required'}), 400

    displayName = data['displayName'].strip()
    if not displayName:
        return jsonify({'error': 'Display name cannot be empty'}), 400
    if len(displayName) > 50:
        return jsonify({'error': 'Display name must be 50 characters or less'}), 400
    if not re.match(r'^[a-zA-Z0-9\s\-_]+$', displayName):
        return jsonify({'error': 'Display name can only contain letters, numbers, spaces, hyphens, and underscores'}), 400

    user.displayName = displayName
    user.displayNameSetAt = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'user': {
        'id': user.id,
        'displayName': user.displayName,
        'displayNameSetAt': user.displayNameSetAt.isoformat()
    }})


@bp.route('/auth/campaign-handoff/', methods=['GET'])
def campaign_handoff_complete():
    """Establish a session on a campaign vanity host after hub Web3Auth login."""
    from services.campaign_auth import (
        campaign_for_vanity_host,
        hub_login_url,
        verify_campaign_handoff_token,
        vanity_absolute_url,
    )
    from services.auth_redirect import safe_return_path

    token = (request.args.get('token') or '').strip()
    next_path = safe_return_path(request.args.get('next')) or '/'
    username = verify_campaign_handoff_token(token)
    if not username:
        flash('Sign-in link expired. Please sign in again.', 'error')
        cfg = campaign_for_vanity_host()
        if cfg:
            return redirect(hub_login_url(vanity_absolute_url(cfg, next_path)))
        return redirect(login_url(next_path))
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('Account not found.', 'error')
        return redirect(login_url(next_path))
    session['user'] = user.username
    return redirect(next_path)


@bp.route('/api/auth/campaign-handoff', methods=['POST'])
def campaign_handoff_init():
    """Return a one-time vanity-host URL to copy the hub session after Web3Auth."""
    from services.campaign_auth import build_campaign_handoff_redirect, safe_campaign_return_url
    from services.identity import get_current_user

    current = get_current_user()
    if not current:
        return jsonify({'error': 'Not authenticated'}), 401
    data = request.get_json(silent=True) or {}
    next_url = safe_campaign_return_url(data.get('next'))
    if not next_url:
        return jsonify({'error': 'Invalid return URL'}), 400
    try:
        url = build_campaign_handoff_redirect(next_url, current['username'])
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return jsonify({'url': url})


@bp.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """API logout endpoint"""
    session.pop('user', None)
    return jsonify({'success': True})
