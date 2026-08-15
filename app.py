"""
GovHub Application factory.
Creates and configures the Flask app for the Interface Governance Hub.

Use: app = create_app() or from app import app
"""
import os
import sys

from flask import Flask

from config import (
    BUILD_NUMBER,
    PROJECT_ROOT,
    INSTANCE_DIR,
    DB_PATH,
    DEBUG,
    IS_DEVELOPMENT,
    ENV,
    PORT,
    RESERVED_SUBDOMAINS,
    BASE_DOMAIN,
    BASE_DOMAINS,
    DEPLOYMENT_MODE,
    KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED,
    KNOWLEDGE_SCAFFOLD_ENABLED,
    KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED,
    LAYER_TAGS_ENABLED,
    LAYER_TAG_FILTERS_ENABLED,
    DOCUMENT_TAGS_ENABLED,
    ARTIFACT_TAGS_ENABLED,
    ARTIFACT_TAG_FILTERS_ENABLED,
    PUBLIC_BASE_URL,
    CANOPI_PUBLIC_URL,
    CANOPI_INTERNAL_API_URL,
)

# Ensure instance directory exists
os.makedirs(INSTANCE_DIR, exist_ok=True)


def create_app(database_uri=None, *, testing=False):
    """Create and configure the Flask application.

    ``database_uri`` overrides the configured SQLite database. Tests use it
    (with ``testing=True``) to run against a disposable database instead of
    the deployed one; production always leaves both arguments unset.
    """
    app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=True)
    secret_key = (os.environ.get('SECRET_KEY') or '').strip()
    if not secret_key:
        is_dev_checkout = os.path.basename(PROJECT_ROOT).endswith('-dev')
        if not IS_DEVELOPMENT and not is_dev_checkout and 'pytest' not in sys.modules:
            raise RuntimeError('SECRET_KEY must be set in production.')
        print('⚠️  SECRET_KEY is not set; using an insecure development-only fallback.')
        secret_key = 'dev-only-insecure-secret-key'
    app.secret_key = secret_key

    # Trust X-Forwarded-* when behind nginx (proto + host for layer subdomain resolution)
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    except ImportError:
        pass

    # Database
    app.config['SQLALCHEMY_DATABASE_URI'] = database_uri or f'sqlite:///{DB_PATH}'
    app.config['TESTING'] = bool(testing)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'connect_args': {'timeout': 30},
    }
    app.config['DEBUG'] = DEBUG

    # App config for blueprints
    app.config['IS_DEVELOPMENT'] = IS_DEVELOPMENT
    app.config['ENV'] = ENV
    app.config['PORT'] = PORT
    app.config['DB_PATH'] = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    app.config['RESERVED_SUBDOMAINS'] = RESERVED_SUBDOMAINS
    app.config['KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED'] = KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED
    app.config['KNOWLEDGE_SCAFFOLD_ENABLED'] = KNOWLEDGE_SCAFFOLD_ENABLED
    app.config['KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED'] = KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED
    app.config['LAYER_TAGS_ENABLED'] = LAYER_TAGS_ENABLED
    app.config['LAYER_TAG_FILTERS_ENABLED'] = LAYER_TAG_FILTERS_ENABLED
    app.config['DOCUMENT_TAGS_ENABLED'] = DOCUMENT_TAGS_ENABLED
    app.config['ARTIFACT_TAGS_ENABLED'] = ARTIFACT_TAGS_ENABLED
    app.config['ARTIFACT_TAG_FILTERS_ENABLED'] = ARTIFACT_TAG_FILTERS_ENABLED
    app.config['PUBLIC_BASE_URL'] = PUBLIC_BASE_URL
    app.config['CANOPI_PUBLIC_URL'] = CANOPI_PUBLIC_URL
    app.config['CANOPI_INTERNAL_API_URL'] = CANOPI_INTERNAL_API_URL

    # Session security
    app.config['SESSION_COOKIE_SECURE'] = not (IS_DEVELOPMENT or testing)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Extensions
    from extensions import db
    db.init_app(app)

    if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:///'):
        from sqlalchemy import event

        with app.app_context():
            sqlite_engine = db.engine

        @event.listens_for(sqlite_engine, 'connect')
        def _set_sqlite_pragmas(dbapi_connection, connection_record):
            del connection_record
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL')
            # Auto-checkpoint when WAL reaches ~200 pages (~800 KB) instead of
            # the default 1000 pages (~4 MB). Prevents WAL from growing large
            # enough to cause 'disk I/O error' on read paths on a long-running
            # dev/prod server that has minimal write traffic.
            cursor.execute('PRAGMA wal_autocheckpoint=200')
            cursor.execute('PRAGMA busy_timeout=30000')
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()

        # Periodic best-effort WAL checkpoint so the file stays small even when
        # nothing is writing (default autocheckpoint only fires on writes).
        # Without this the WAL can grow to MB on dev where the long-running
        # Flask process only does a handful of writes. Disposable test apps
        # are short-lived, so they skip the background thread.
        import threading
        import time as _time

        def _sqlite_wal_periodic_checkpoint():
            interval = int(os.environ.get('SQLITE_WAL_CHECKPOINT_SECS', '60'))
            while True:
                _time.sleep(interval)
                try:
                    with app.app_context():
                        with db.engine.connect() as _conn:
                            _conn.exec_driver_sql('PRAGMA wal_checkpoint(PASSIVE)')
                            _conn.commit()
                except Exception as _err:  # noqa: BLE001
                    try:
                        app.logger.warning('WAL checkpoint failed: %s', _err)
                    except Exception:
                        pass

        if not testing:
            threading.Thread(
                target=_sqlite_wal_periodic_checkpoint,
                name='sqlite-wal-checkpoint',
                daemon=True,
            ).start()

    # Models (must be after db.init_app)
    from models import (
        User,
        UserEventSubscription, UserNotification,
        EventLog, StatusChange,
        Layer, LayerMember, LayerAdmin,
        Waitlist, WaitlistEntry, WaitlistMilestone, EmailUnsubscribe, WaitlistEmailSignup,
        Workgroup, WorkingGroupMember, WorkingGroupChair, CoordinatorRequest, WorkgroupMemberRequest,
        Guild, GuildMembership, GuildInvitation, LayerInvitation,
        Cluster, Role, RoleImage, RoleImageVote,
        Claim, Badge, BadgeSkin, BadgeCycle, OneTimeBadge,
        Vote, VoteEligibilitySnapshot, VoteCandidate, Ballot,
        Quest, QuestSubmission, Monument, Brick,
        Submission, SiteConfig, InscriptionOrder,
        Comment, DocumentHistory,
        Artifact, ArtifactRelation,
        ArtifactCollection, ArtifactCollectionItem,
        Bridge, BridgeSession,
        LayerPrefix,
    )

    # Blueprints
    from routes.deploy import bp as deploy_bp
    from routes.auth import bp as auth_bp
    from routes.layers import bp as layers_bp
    from routes.layers_pages import bp as layers_pages_bp
    from routes.workgroups import bp as workgroups_bp
    from routes.dp_admin_invite import bp as dp_admin_invite_bp
    from routes.workgroups_api import bp as workgroups_api_bp
    from routes.workgroups_pages import bp as workgroups_pages_bp
    from routes.nominations_pages import bp as nominations_pages_bp
    from routes.guilds import bp as guilds_bp
    from routes.guilds_pages import bp as guilds_pages_bp
    from routes.waitlists import bp as waitlists_bp
    from routes.votes import bp as votes_bp, bp_pages as votes_pages_bp
    from routes.artifacts import bp as artifacts_bp
    from routes.collections import bp as collections_bp
    from routes.roles import bp as roles_bp, bp_uploads as roles_uploads_bp
    from routes.roles_pages import bp as roles_pages_bp
    from routes.submissions import bp as submissions_bp
    from routes.ordinals import bp as ordinals_bp, bp_pages as ordinals_pages_bp
    from routes.documents import bp as documents_bp
    from routes.notifications import bp as notifications_bp
    from routes.admin import bp as admin_bp
    from routes.product_rollout_admin import bp as product_rollout_admin_bp
    from routes.pages import bp as pages_bp
    from routes.users import bp as users_bp
    from routes.profile_pages import bp as profile_pages_bp
    from routes.security_pages import bp as security_pages_bp
    from routes.mfa import bp as mfa_bp
    from routes.group import bp as group_bp
    from routes.directory import bp as directory_bp
    from routes.bridges import bp as bridges_bp
    from routes.bridges_pages import bp as bridges_pages_bp
    from routes.civic_mason import bp as civic_mason_bp
    from routes.civic_mason_pages import bp as civic_mason_pages_bp
    from routes.soft_launch import bp as soft_launch_bp
    from routes.soft_launch_pages import bp as soft_launch_pages_bp
    from routes.layer_invitations import bp as layer_invitations_bp, bp_pages as layer_invite_pages_bp
    from routes.dp_proposals import bp as dp_proposals_bp, admin_bp as dp_proposals_admin_bp
    from routes.dp_challenge_pages import bp as dp_challenge_bp
    from routes.patches_pages import bp as patches_pages_bp
    from routes.platform_invitations import bp as platform_invitations_bp
    from routes.brc333_badges_admin import bp as brc333_badges_admin_bp
    from routes.metaweb import bp as metaweb_bp
    from routes.canopi_internal import bp as canopi_internal_bp
    from routes.dp_internal import bp as dp_internal_bp
    from routes.scope_email import bp as scope_email_bp
    from routes.layer_connections import bp as layer_connections_bp
    from routes.layer_connections_pages import bp as layer_connections_pages_bp
    from routes.support_api import bp as support_api_bp
    from routes.support_pages import bp as support_pages_bp
    from routes.referral_links import bp as referral_links_bp
    from routes.layer_programs import bp as layer_programs_bp
    try:
        from routes.social_connect import bp as social_connect_bp, google_bp, github_bp, discord_bp, twitter_bp
        # Register each OAuth blueprint independently so one failure doesn't break others
        for name, oauth_bp, prefix in [
            ('google', google_bp, '/auth/google'),
            ('github', github_bp, '/auth/github'),
            ('discord', discord_bp, '/auth/discord'),
            ('twitter', twitter_bp, '/auth/twitter'),
        ]:
            if oauth_bp is None:
                continue
            try:
                app.register_blueprint(oauth_bp, url_prefix=prefix)
            except Exception as e:
                print(f"⚠️  OAuth {name} disabled: {e}")
        app.register_blueprint(social_connect_bp)
    except ImportError as e:
        if 'flask_dance' in str(e).lower():
            print("⚠️  flask-dance not installed; social account linking disabled. pip install flask-dance[sqla]")
        else:
            raise
    app.register_blueprint(deploy_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(layers_bp)
    app.register_blueprint(layers_pages_bp)
    app.register_blueprint(workgroups_bp)
    app.register_blueprint(dp_admin_invite_bp)
    app.register_blueprint(workgroups_api_bp)
    app.register_blueprint(workgroups_pages_bp)
    app.register_blueprint(nominations_pages_bp)
    app.register_blueprint(guilds_bp)
    app.register_blueprint(guilds_pages_bp)
    app.register_blueprint(waitlists_bp)
    app.register_blueprint(referral_links_bp)
    app.register_blueprint(layer_programs_bp)
    app.register_blueprint(votes_bp)
    app.register_blueprint(votes_pages_bp)
    app.register_blueprint(artifacts_bp)
    app.register_blueprint(collections_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(roles_uploads_bp)
    app.register_blueprint(roles_pages_bp)
    app.register_blueprint(submissions_bp)
    app.register_blueprint(ordinals_bp)
    app.register_blueprint(ordinals_pages_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(product_rollout_admin_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(profile_pages_bp)
    app.register_blueprint(security_pages_bp)
    app.register_blueprint(mfa_bp)
    app.register_blueprint(group_bp)
    app.register_blueprint(directory_bp)
    app.register_blueprint(bridges_bp)
    app.register_blueprint(bridges_pages_bp)
    app.register_blueprint(civic_mason_bp)
    app.register_blueprint(civic_mason_pages_bp)
    app.register_blueprint(soft_launch_bp)
    app.register_blueprint(soft_launch_pages_bp)
    app.register_blueprint(layer_invitations_bp)
    app.register_blueprint(layer_invite_pages_bp)
    app.register_blueprint(dp_proposals_bp)
    app.register_blueprint(dp_proposals_admin_bp)
    app.register_blueprint(dp_challenge_bp)
    app.register_blueprint(patches_pages_bp)
    app.register_blueprint(platform_invitations_bp)
    app.register_blueprint(metaweb_bp)
    app.register_blueprint(brc333_badges_admin_bp)
    app.register_blueprint(canopi_internal_bp)
    app.register_blueprint(dp_internal_bp)
    app.register_blueprint(scope_email_bp)
    app.register_blueprint(layer_connections_bp)
    app.register_blueprint(layer_connections_pages_bp)
    app.register_blueprint(support_api_bp)
    app.register_blueprint(support_pages_bp)

    # CLI
    from cli import register_cli
    register_cli(app)

    # Middleware
    from middleware import register_request_handlers
    register_request_handlers(app, deployment_mode=DEPLOYMENT_MODE, base_domain=BASE_DOMAIN, reserved_subdomains=RESERVED_SUBDOMAINS, base_domains=BASE_DOMAINS)

    # Upload config
    UPLOAD_FOLDER = '/home/ubuntu/data-tracker/uploads'
    ROLE_IMAGE_UPLOAD_FOLDER = '/home/ubuntu/data-tracker/uploads/role_images'
    ENTITY_IMAGE_UPLOAD_FOLDER = '/home/ubuntu/data-tracker/uploads/entity_images'
    PROFILE_IMAGE_UPLOAD_FOLDER = '/home/ubuntu/data-tracker/uploads/profile_images'

    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
    app.config['ROLE_IMAGE_UPLOAD_FOLDER'] = ROLE_IMAGE_UPLOAD_FOLDER
    app.config['ENTITY_IMAGE_UPLOAD_FOLDER'] = ENTITY_IMAGE_UPLOAD_FOLDER
    app.config['PROFILE_IMAGE_UPLOAD_FOLDER'] = PROFILE_IMAGE_UPLOAD_FOLDER

    for folder in [UPLOAD_FOLDER, ROLE_IMAGE_UPLOAD_FOLDER, ENTITY_IMAGE_UPLOAD_FOLDER, PROFILE_IMAGE_UPLOAD_FOLDER]:
        os.makedirs(folder, exist_ok=True)

    # Rendering
    from templates.html_templates import BASE_TEMPLATE
    from services.rendering import configure_rendering
    FONT_AWESOME_LINK = '<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">'
    configure_rendering(BASE_TEMPLATE, FONT_AWESOME_LINK, BUILD_NUMBER)

    @app.route('/static/images/reader-guide/<path:filename>')
    def reader_guide_gif(filename):
        """Serve reader-guide media with Content-Type matching file bytes (not extension only)."""
        from flask import abort, send_file
        if '..' in filename or filename.startswith('/'):
            abort(404)
        base = filename.split('?', 1)[0]
        directory = os.path.join(app.root_path, 'static', 'images', 'reader-guide')
        path = os.path.join(directory, base)
        if not os.path.isfile(path):
            abort(404)
        with open(path, 'rb') as handle:
            magic = handle.read(6)
        if magic[:3] == b'GIF':
            mime = 'image/gif'
        elif magic[:2] == b'\xff\xd8':
            mime = 'image/jpeg'
        elif magic[:8] == b'\x89PNG\r\n\x1a\n':
            mime = 'image/png'
        else:
            mime = 'application/octet-stream'
        return send_file(path, mimetype=mime, conditional=True)

    # Log OAuth errors (token exchange failures, etc.) for debugging
    import logging
    import traceback
    from flask import jsonify, request
    from werkzeug.exceptions import HTTPException

    _oauth_log = logging.getLogger('oauth_debug')
    _oauth_log.setLevel(logging.DEBUG)
    if not testing:
        _oauth_fh = logging.FileHandler(os.path.join(INSTANCE_DIR, 'oauth_debug.log'), encoding='utf-8')
        _oauth_fh.setLevel(logging.DEBUG)
        _oauth_fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        _oauth_log.addHandler(_oauth_fh)

    @app.errorhandler(Exception)
    def _log_oauth_exceptions(exc):
        if isinstance(exc, HTTPException):
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'error': exc.description or exc.name,
                    'code': f'http_{exc.code}',
                }), exc.code
            return exc
        if request.path.startswith('/api/'):
            _oauth_log.error(
                "API error on %s: %s\n%s",
                request.path,
                exc,
                traceback.format_exc(),
            )
            return jsonify({
                'success': False,
                'error': 'Internal server error',
                'code': 'internal_server_error',
            }), 500
        if request.path and '/auth/' in request.path and '/authorized' in request.path:
            _oauth_log.error(
                "OAuth callback error on %s: %s\nrequest.args=%s\ntraceback:\n%s",
                request.path,
                exc,
                dict(request.args),
                traceback.format_exc(),
            )
        raise exc

    return app


# Module-level app for direct import (e.g. from app import app)
app = create_app()
