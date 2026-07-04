"""OAuth social account linking: connect Google, GitHub, Twitter/X, Discord."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, redirect, url_for, flash, session, request

_log = logging.getLogger(__name__)
if not _log.handlers:
    _sh = logging.StreamHandler()
    _sh.setLevel(logging.DEBUG)
    _log.addHandler(_sh)
    _log.setLevel(logging.DEBUG)

# Ensure .env is loaded before reading OAuth vars (deployment may have different cwd)
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / '.env')
from flask_dance.consumer import oauth_authorized, oauth_error
from flask_dance.consumer.oauth2 import OAuth2ConsumerBlueprint
from flask_dance.contrib.google import make_google_blueprint
from flask_dance.contrib.github import make_github_blueprint
from flask_dance.contrib.discord import make_discord_blueprint

from extensions import db
from models import User, UserLinkedAccount
from services.identity import get_current_user, require_auth

bp = Blueprint('social_connect', __name__, url_prefix='')


def _current_user_id():
    """Get current user id from session."""
    cu = get_current_user()
    return cu['id'] if cu else None


def _provider_user_info(blueprint, token):
    """Fetch user info from provider. Returns (provider_user_id, profile_url, avatar_url, display_name)."""
    name = blueprint.name
    if not token:
        return None

    if name == 'google':
        resp = blueprint.session.get('https://www.googleapis.com/oauth2/v2/userinfo')
        if not resp.ok:
            return None
        data = resp.json()
        # Google+ shut down in 2019 — don't fabricate a plus.google.com URL; store empty string when no link is returned.
        return (
            str(data.get('id', '')),
            data.get('link') or '',
            data.get('picture', ''),
            data.get('name', ''),
        )
    if name == 'github':
        resp = blueprint.session.get('/user')
        if not resp.ok:
            return None
        data = resp.json()
        return (
            str(data.get('id', '')),
            data.get('html_url', f"https://github.com/{data.get('login', '')}"),
            data.get('avatar_url', ''),
            data.get('name') or data.get('login', ''),
        )
    if name == 'discord':
        resp = blueprint.session.get('/api/users/@me')
        if not resp.ok:
            return None
        data = resp.json()
        avatar = data.get('avatar')
        uid = data.get('id', '')
        avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png" if avatar else ''
        return (
            str(uid),
            f"https://discord.com/users/{uid}",
            avatar_url,
            data.get('username', '') or data.get('global_name', ''),
        )
    if name == 'twitter':
        import hashlib as _hashlib
        import requests as _requests

        access_token = token.get('access_token', '') if isinstance(token, dict) else ''

        # Try API call first
        if access_token:
            resp = _requests.get(
                'https://api.twitter.com/2/users/me',
                headers={'Authorization': f'Bearer {access_token}'},
                params={'user.fields': 'profile_image_url,name,username'},
                timeout=10,
            )
            _log.info("[oauth] twitter /2/users/me status=%s body=%s",
                      resp.status_code, resp.text[:400] if resp.text else '')
            if resp.ok:
                data = resp.json()
                user_data = data.get('data', {})
                uid = user_data.get('id', '')
                username = user_data.get('username', '')
                profile_url = f"https://x.com/{username}" if username else ''
                avatar_url = user_data.get('profile_image_url', '').replace('_normal', '_400x400') or ''
                display_name = user_data.get('name', '') or username or uid
                return (str(uid), profile_url, avatar_url, display_name)

            # API blocked by tier (403) — store account using token fingerprint as uid
            if resp.status_code == 403:
                _log.info("[oauth] twitter API tier limitation, storing account with token fingerprint")
                uid = 'tw_' + _hashlib.sha256(access_token.encode()).hexdigest()[:16]
                return (uid, 'https://x.com', '', 'X (Twitter) User')

        return None
    return None


def _create_linked_account(provider, provider_user_id, profile_url, avatar_url, display_name, access_token, user_id):
    """Create or update UserLinkedAccount."""
    existing = UserLinkedAccount.query.filter_by(
        provider=provider,
        provider_user_id=provider_user_id
    ).first()
    if existing and str(existing.user_id) != str(user_id):
        return False, "This account is already linked to another user."
    acc = UserLinkedAccount.query.filter_by(user_id=user_id, provider=provider).first()
    if acc:
        acc.provider_user_id = provider_user_id
        acc.profile_url = profile_url
        acc.avatar_url = avatar_url
        acc.display_name = display_name
        acc.access_token = access_token
    else:
        acc = UserLinkedAccount(
            user_id=user_id,
            provider=provider,
            provider_user_id=provider_user_id,
            profile_url=profile_url,
            avatar_url=avatar_url,
            display_name=display_name,
            access_token=access_token,
        )
        db.session.add(acc)
    db.session.commit()
    return True, None


# OAuth URLs: login_url='/' and authorized_url='/authorized' give clean paths:
# /auth/<provider>/ and /auth/<provider>/authorized (no double /google/google/)
_oauth_urls = {'login_url': '/', 'authorized_url': '/authorized'}

# Google
google_bp = make_google_blueprint(
    client_id=os.environ.get('GOOGLE_OAUTH_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET'),
    redirect_to='profile_pages.profile_edit',
    scope=['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile'],
    **_oauth_urls,
)

# GitHub
github_bp = make_github_blueprint(
    client_id=os.environ.get('GITHUB_OAUTH_CLIENT_ID'),
    client_secret=os.environ.get('GITHUB_OAUTH_CLIENT_SECRET'),
    redirect_to='profile_pages.profile_edit',
    **_oauth_urls,
)

# Discord (fallback: DISCORD_OAUTH_APPLICATION_ID = client_id)
discord_bp = make_discord_blueprint(
    client_id=os.environ.get('DISCORD_OAUTH_CLIENT_ID') or os.environ.get('DISCORD_OAUTH_APPLICATION_ID'),
    client_secret=os.environ.get('DISCORD_OAUTH_CLIENT_SECRET'),
    redirect_to='profile_pages.profile_edit',
    scope=['identify'],
    **_oauth_urls,
)

# X (Twitter) OAuth 2.0 - custom blueprint (Flask-Dance has no built-in X provider)
# Only create when credentials exist; otherwise client_id=None gets sent literally to Twitter
_twitter_client_id = (os.environ.get('TWITTER_OAUTH_CLIENT_ID') or '').strip()
_twitter_client_secret = (os.environ.get('TWITTER_OAUTH_CLIENT_SECRET') or '').strip()
if _twitter_client_id and _twitter_client_secret:
    twitter_bp = OAuth2ConsumerBlueprint(
        name='twitter',
        import_name=__name__,
        client_id=_twitter_client_id,
        client_secret=_twitter_client_secret,
        base_url='https://api.twitter.com/2/',
        authorization_url='https://twitter.com/i/oauth2/authorize',
        token_url='https://api.twitter.com/2/oauth2/token',
        redirect_to='profile_pages.profile_edit',
        scope=['tweet.read', 'users.read'],
        use_pkce=True,
        code_challenge_method='S256',
        login_url='/',
        authorized_url='/authorized',
    )
    @twitter_bp.after_app_request
    def _log_twitter_redirect(response):
        if response.status_code in (301, 302, 303, 307, 308):
            loc = response.headers.get('Location', '')
            if 'oauth2/authorize' in loc or 'twitter.com' in loc or 'x.com' in loc:
                _log.info("[oauth] twitter authorization redirect → %s", loc)
        return response
else:
    twitter_bp = None


def _oauth_authorized_handler(blueprint, token):
    _log.info("[oauth] authorized handler called for %s | token_keys=%s", blueprint.name,
              list(token.keys()) if isinstance(token, dict) else type(token).__name__)
    user_id = _current_user_id()
    _log.info("[oauth] user_id from session: %s", user_id)
    if not user_id:
        flash('Please log in first to connect your account.', 'warning')
        return redirect(url_for('auth.login'))
    info = _provider_user_info(blueprint, token)
    _log.info("[oauth] provider_user_info result for %s: %s", blueprint.name, info)
    if not info:
        flash(f'Failed to fetch your {blueprint.name} profile.', 'error')
        return redirect(url_for('profile_pages.profile_edit'))
    provider_user_id, profile_url, avatar_url, display_name = info
    access_token = token.get('access_token', '') if isinstance(token, dict) else str(token) if token else ''
    try:
        ok, err = _create_linked_account(
            blueprint.name, provider_user_id, profile_url, avatar_url, display_name,
            access_token, user_id
        )
    except Exception as exc:
        _log.exception("[oauth] DB error saving %s linked account: %s", blueprint.name, exc)
        flash('A database error occurred while connecting your account.', 'error')
        return redirect(url_for('profile_pages.profile_edit'))
    _log.info("[oauth] _create_linked_account result: ok=%s err=%s", ok, err)
    if not ok:
        flash(err or 'Failed to connect account.', 'error')
    else:
        flash(f'Successfully connected your {blueprint.name} account!', 'success')
    return redirect(url_for('profile_pages.profile_edit'))


@oauth_authorized.connect_via(google_bp)
def google_connected(blueprint, token):
    return _oauth_authorized_handler(blueprint, token)


@oauth_authorized.connect_via(github_bp)
def github_connected(blueprint, token):
    return _oauth_authorized_handler(blueprint, token)


@oauth_authorized.connect_via(discord_bp)
def discord_connected(blueprint, token):
    return _oauth_authorized_handler(blueprint, token)


if twitter_bp:
    @oauth_authorized.connect_via(twitter_bp)
    def twitter_connected(blueprint, token):
        return _oauth_authorized_handler(blueprint, token)


def _log_oauth_error(blueprint, **kwargs):
    """Log OAuth errors for debugging. OAuth2: error, error_description, error_uri. OAuth1: message, response."""
    msg = kwargs.get('error') or kwargs.get('message') or 'unknown'
    _log.warning(
        "OAuth error [%s]: %s | request.args=%s | kwargs=%s",
        blueprint.name,
        msg,
        dict(request.args) if request else {},
        kwargs,
    )


@oauth_error.connect_via(google_bp)
@oauth_error.connect_via(github_bp)
@oauth_error.connect_via(discord_bp)
def oauth_error_handler(blueprint, **kwargs):
    _log_oauth_error(blueprint, **kwargs)
    msg = kwargs.get('error') or kwargs.get('error_description') or kwargs.get('message') or 'OAuth failed'
    flash(f'OAuth error with {blueprint.name}: {msg}', 'error')
    return redirect(url_for('profile_pages.profile_edit'))


if twitter_bp:
    @oauth_error.connect_via(twitter_bp)
    def twitter_oauth_error_handler(blueprint, **kwargs):
        _log_oauth_error(blueprint, **kwargs)
        msg = kwargs.get('error') or kwargs.get('error_description') or kwargs.get('message') or 'OAuth failed'
        flash(f'OAuth error with {blueprint.name}: {msg}', 'error')
        return redirect(url_for('profile_pages.profile_edit'))


# Connect routes - require auth, then redirect to provider's OAuth flow
@bp.route('/profile/connect/google/')
@require_auth
def connect_google():
    return redirect(url_for('google.login'))


@bp.route('/profile/connect/github/')
@require_auth
def connect_github():
    return redirect(url_for('github.login'))


@bp.route('/profile/connect/discord/')
@require_auth
def connect_discord():
    return redirect(url_for('discord.login'))


@bp.route('/profile/connect/twitter/')
@require_auth
def connect_twitter():
    if twitter_bp is None:
        flash('Twitter connect is not configured. Check TWITTER_OAUTH_CLIENT_ID in .env.', 'warning')
        return redirect(url_for('profile_pages.profile_edit'))
    _log.info("[oauth] twitter_bp.client_id loaded as: [%s]", twitter_bp.client_id)
    login_url = url_for('twitter.login')
    _log.info("[oauth] redirecting to twitter login url: %s", login_url)
    return redirect(login_url)


# Disconnect
@bp.route('/profile/connect/<provider>/disconnect/', methods=['POST'])
@require_auth
def disconnect(provider):
    if provider not in ('google', 'github', 'discord', 'twitter'):
        flash('Invalid provider.', 'error')
        return redirect(url_for('profile_pages.profile_edit'))
    user_id = _current_user_id()
    if not user_id:
        return redirect(url_for('auth.login'))
    acc = UserLinkedAccount.query.filter_by(user_id=user_id, provider=provider).first()
    if acc:
        db.session.delete(acc)
        db.session.commit()
        flash(f'Disconnected your {provider} account.', 'info')
    return redirect(url_for('profile_pages.profile_edit'))
