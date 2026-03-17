"""
MLGH Data Viewer - Application factory.
Creates and configures the Flask app for Meta-Layer Task Force governance.

Use: app = create_app() or from app import app
"""
import os

from flask import Flask

from config import (
    BUILD_NUMBER,
    INSTANCE_DIR,
    DB_PATH,
    DEBUG,
    IS_DEVELOPMENT,
    ENV,
    PORT,
    RESERVED_SUBDOMAINS,
    BASE_DOMAINS,
    DEPLOYMENT_MODE,
)

# Ensure instance directory exists
os.makedirs(INSTANCE_DIR, exist_ok=True)


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_path=INSTANCE_DIR, instance_relative_config=True)
    app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')

    # Trust X-Forwarded-* when behind nginx (proto + host for layer subdomain resolution)
    try:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    except ImportError:
        pass

    # Database
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DEBUG'] = DEBUG

    # App config for blueprints
    app.config['IS_DEVELOPMENT'] = IS_DEVELOPMENT
    app.config['ENV'] = ENV
    app.config['PORT'] = PORT
    app.config['DB_PATH'] = DB_PATH
    app.config['RESERVED_SUBDOMAINS'] = RESERVED_SUBDOMAINS

    # Session security
    app.config['SESSION_COOKIE_SECURE'] = not IS_DEVELOPMENT
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Extensions
    from extensions import db
    db.init_app(app)

    # Models (must be after db.init_app)
    from models import (
        User, UserFollow, HypothesisAccount,
        EventLog, StatusChange,
        Layer, LayerMember, LayerAdmin,
        Waitlist, WaitlistEntry, WaitlistMilestone, EmailUnsubscribe, WaitlistEmailSignup,
        Workgroup, WorkingGroupMember, WorkingGroupChair, CoordinatorRequest, WorkgroupMemberRequest,
        Guild, GuildMembership, GuildInvitation,
        Cluster, Role, RoleImage, RoleImageVote,
        Claim, Badge, BadgeSkin, BadgeCycle, OneTimeBadge,
        Vote, VoteEligibilitySnapshot, VoteCandidate, Ballot,
        Quest, QuestSubmission, Monument, Brick,
        Submission, SiteConfig, InscriptionOrder,
        Comment, DocumentHistory,
        Artifact, ArtifactRelation,
        Bridge, BridgeSession,
    )

    # Blueprints
    from routes.deploy import bp as deploy_bp
    from routes.auth import bp as auth_bp
    from routes.layers import bp as layers_bp
    from routes.layers_pages import bp as layers_pages_bp
    from routes.workgroups import bp as workgroups_bp
    from routes.workgroups_pages import bp as workgroups_pages_bp
    from routes.guilds import bp as guilds_bp
    from routes.guilds_pages import bp as guilds_pages_bp
    from routes.waitlists import bp as waitlists_bp
    from routes.votes import bp as votes_bp, bp_pages as votes_pages_bp
    from routes.artifacts import bp as artifacts_bp
    from routes.roles import bp as roles_bp, bp_uploads as roles_uploads_bp
    from routes.roles_pages import bp as roles_pages_bp
    from routes.submissions import bp as submissions_bp
    from routes.ordinals import bp as ordinals_bp, bp_pages as ordinals_pages_bp
    from routes.documents import bp as documents_bp
    from routes.admin import bp as admin_bp
    from routes.pages import bp as pages_bp
    from routes.users import bp as users_bp
    from routes.profile_pages import bp as profile_pages_bp
    from routes.group import bp as group_bp
    from routes.directory import bp as directory_bp
    from routes.bridges import bp as bridges_bp
    from routes.bridges_pages import bp as bridges_pages_bp
    from routes.civic_mason import bp as civic_mason_bp
    from routes.civic_mason_pages import bp as civic_mason_pages_bp

    app.register_blueprint(deploy_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(layers_bp)
    app.register_blueprint(layers_pages_bp)
    app.register_blueprint(workgroups_bp)
    app.register_blueprint(workgroups_pages_bp)
    app.register_blueprint(guilds_bp)
    app.register_blueprint(guilds_pages_bp)
    app.register_blueprint(waitlists_bp)
    app.register_blueprint(votes_bp)
    app.register_blueprint(votes_pages_bp)
    app.register_blueprint(artifacts_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(roles_uploads_bp)
    app.register_blueprint(roles_pages_bp)
    app.register_blueprint(submissions_bp)
    app.register_blueprint(ordinals_bp)
    app.register_blueprint(ordinals_pages_bp)
    app.register_blueprint(documents_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(profile_pages_bp)
    app.register_blueprint(group_bp)
    app.register_blueprint(directory_bp)
    app.register_blueprint(bridges_bp)
    app.register_blueprint(bridges_pages_bp)
    app.register_blueprint(civic_mason_bp)
    app.register_blueprint(civic_mason_pages_bp)

    # CLI
    from cli import register_cli
    register_cli(app)

    # Middleware
    from middleware import register_request_handlers
    register_request_handlers(app, deployment_mode=DEPLOYMENT_MODE, base_domain='themetalayer.org', reserved_subdomains=RESERVED_SUBDOMAINS, base_domains=BASE_DOMAINS)

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

    return app


# Module-level app for direct import (e.g. from app import app)
app = create_app()
