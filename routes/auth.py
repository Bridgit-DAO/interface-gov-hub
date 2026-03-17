"""Auth routes: login, logout, register, Web3Auth, api/user/me, api/user/display-name."""
import re
from datetime import datetime

from flask import Blueprint, jsonify, request, session, flash, redirect, url_for, render_template_string
from werkzeug.security import generate_password_hash

from extensions import db
from models import User
from services.utils import check_rate_limit

bp = Blueprint('auth', __name__, url_prefix='')

LOGIN_TEMPLATE = """
<div class="container mt-4">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h3 class="mb-0">Sign In</h3>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>

                    <!-- Single Web3Auth Sign In Button - uses loginWithWeb3Auth from BASE_TEMPLATE -->
                    <div class="mb-4 text-center">
                        <p class="text-muted mb-3">Connect your account to continue</p>
                        <button type="button" class="btn btn-primary btn-lg" id="web3auth-signin-btn" onclick="loginWithWeb3Auth()">
                            <svg width="20" height="20" class="me-2" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle;">
                                <path d="M12 2L2 7v10c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-10-5zm0 18c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6z"/>
                            </svg>
                            Sign In with Web3Auth
                        </button>
                        <p class="text-muted mt-3 small">Sign in with Google, Twitter, Email, or connect your wallet</p>
                    </div>

                </div>
            </div>
        </div>
    </div>
</div>
"""

REGISTER_TEMPLATE = """
<div class="container mt-4">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h3 class="mb-0">Create Account</h3>
                </div>
                <div class="card-body">
                    <div id="flash-messages"></div>
                    
                    <form method="POST">
                        <div class="mb-3">
                            <label for="username" class="form-label">Username</label>
                            <input type="text" class="form-control" id="username" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label for="name" class="form-label">Full Name</label>
                            <input type="text" class="form-control" id="name" name="name" required>
                        </div>
                        <div class="mb-3">
                            <label for="email" class="form-label">Email</label>
                            <input type="email" class="form-control" id="email" name="email" required>
                        </div>
                        <div class="mb-3">
                            <label for="password" class="form-label">Password</label>
                            <input type="password" class="form-control" id="password" name="password" required minlength="6">
                        </div>
                        <div class="d-grid">
                            <button type="submit" class="btn btn-primary">Create Account</button>
                        </div>
                    </form>
                    
                    <hr>
                    <div class="text-center">
                        <p class="mb-0">Already have an account? <a href="/login/">Sign in</a></p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
"""


@bp.route('/login/', methods=['GET'])
def login():
    """Show dedicated login page with Web3Auth sign-in. Use ?redirect=URL to return after login."""
    from services.rendering import _format_base_template, generate_user_menu
    from services.identity import get_current_user
    from config import BUILD_NUMBER
    user_menu = generate_user_menu()
    current_theme = session.get('theme', get_current_user().get('theme', 'dark') if get_current_user() else 'dark')
    return _format_base_template(
        title="Sign In - MLGH",
        theme=current_theme,
        user_menu=user_menu,
        content=LOGIN_TEMPLATE,
        build_number=BUILD_NUMBER,
        hypothesis_config=""
    )


@bp.route('/logout/')
def logout():
    """User logout"""
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('pages.home'))


@bp.route('/register/', methods=['GET', 'POST'])
def register():
    """User registration"""
    from services.rendering import _format_base_template
    from config import BUILD_NUMBER
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()

        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            if existing_user.username == username:
                flash('Username already exists.', 'error')
            else:
                flash('Email already registered.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        else:
            new_user = User(
                username=username,
                password_hash=generate_password_hash(password),
                name=name,
                email=email,
                role='user',
                theme='dark'
            )
            db.session.add(new_user)
            db.session.commit()

            session['user'] = username
            flash(f'Account created successfully! Welcome, {name}!', 'success')
            return redirect(url_for('pages.home'))

    user_menu = """
    <div class="nav-item">
        <a class="nav-link" href="/login/">Sign In</a>
    </div>
    """
    return render_template_string(_format_base_template(title="Register - MLGH", theme="light", user_menu=user_menu, content=REGISTER_TEMPLATE, build_number=BUILD_NUMBER, hypothesis_config=""))


@bp.route('/api/auth/web3auth', methods=['POST'])
def web3auth_login():
    """Web3Auth login endpoint"""
    client_ip = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', 'unknown')
    if not check_rate_limit(f"web3auth_{client_ip}", max_requests=50, window_seconds=600):
        return jsonify({'error': 'Too many sign-in attempts. Please wait a few minutes and try again.'}), 429

    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        verifierId = data.get('verifierId')
        typeOfLogin = data.get('typeOfLogin')
        email = data.get('email')
        name = data.get('name')
        profileImage = data.get('profileImage')
        evmAddress = data.get('evmAddress')
        solanaAddress = data.get('solanaAddress')

        if not verifierId:
            return jsonify({'error': 'verifierId required'}), 400

        user = User.query.filter_by(web3authVerifierId=verifierId).first()
        if not user and email:
            user = User.query.filter_by(email=email).first()

        if user:
            user.web3authVerifierId = verifierId
            user.typeOfLogin = typeOfLogin
            user.last_login = datetime.utcnow()
            if name:
                user.displayName = name
                user.displayNameSetAt = datetime.utcnow()
                user.oauthName = name
            if profileImage:
                user.profileImage = profileImage
            if evmAddress:
                user.evmAddress = evmAddress
            if solanaAddress:
                user.solanaAddress = solanaAddress
            db.session.commit()
        else:
            existing_handles = db.session.query(User.username).all()
            existing_handles = [h[0] for h in existing_handles]
            if typeOfLogin == 'wallet' and evmAddress:
                short_address = f"{evmAddress[:6]}...{evmAddress[-4:]}"
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
                web3authVerifierId=verifierId,
                typeOfLogin=typeOfLogin,
                displayName=name if name else None,
                displayNameSetAt=datetime.utcnow() if name else None,
                oauthName=name,
                email=email,
                profileImage=profileImage,
                evmAddress=evmAddress,
                solanaAddress=solanaAddress,
                username=handle,
                handle=handle,
                role='user',
                theme='dark',
                last_login=datetime.utcnow()
            )
            db.session.add(user)
            db.session.commit()

        session['user'] = user.username
        session['theme'] = user.theme

        safe_user_data = {
            'id': user.id,
            'username': user.username,
            'displayName': user.displayName,
            'oauthName': user.oauthName,
            'email': user.email,
            'profileImage': user.profileImage,
            'evmAddress': user.evmAddress,
            'solanaAddress': user.solanaAddress,
            'typeOfLogin': user.typeOfLogin,
            'theme': user.theme
        }
        return jsonify({'success': True, 'user': safe_user_data})

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        from flask import current_app
        current_app.logger.error(f"Web3Auth login error: {e}\n{error_details}")
        db.session.rollback()
        return jsonify({'error': f'Authentication failed: {str(e)}'}), 500


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


@bp.route('/api/auth/logout', methods=['POST'])
def api_logout():
    """API logout endpoint"""
    session.pop('user', None)
    return jsonify({'success': True})
