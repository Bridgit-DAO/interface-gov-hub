"""Application configuration: env, paths, deployment, build number."""
import os

from dotenv import load_dotenv

# Project root (parent of config.py)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# Load .env from project root (gov-hub-dev/.env)
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Environment
ENV = os.environ.get('FLASK_ENV', 'production').lower()
IS_PRODUCTION = ENV == 'production'
IS_DEVELOPMENT = ENV == 'development'

# Paths and DB
if IS_DEVELOPMENT:
    INSTANCE_DIR = os.path.join(PROJECT_ROOT, 'instance_dev')
    DB_NAME = 'datatracker_dev.db'
    PORT = int(os.environ.get('FLASK_PORT', 8001))
    DEBUG = True
else:
    INSTANCE_DIR = os.path.join(PROJECT_ROOT, 'instance')
    DB_NAME = 'datatracker.db'
    PORT = int(os.environ.get('FLASK_PORT', 8000))
    DEBUG = False

DB_PATH = os.path.join(INSTANCE_DIR, DB_NAME)

# Soft-launch artifact demo: UUID of a real Artifact. When set, Support/Oppose on
# /soft-launch/artifact/ POST to /api/artifacts/<id>/support|opposition/ (session auth).
SOFT_LAUNCH_WIRED_ARTIFACT_ID = os.environ.get('SOFT_LAUNCH_WIRED_ARTIFACT_ID', '').strip()

# Knowledge layer (contribution type + scaffold) — see services/knowledge_layer.py, artifact_contribution_schema.md
def _env_bool(key: str, default: str) -> bool:
    return os.environ.get(key, default).strip().lower() in ('1', 'true', 'yes', 'on')


KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED = _env_bool('GOVHUB_KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED', 'true')
KNOWLEDGE_SCAFFOLD_ENABLED = _env_bool('GOVHUB_KNOWLEDGE_SCAFFOLD_ENABLED', 'false')
KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED = _env_bool('GOVHUB_KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED', 'true')

ARTIFACT_TAGS_ENABLED = _env_bool('GOVHUB_ARTIFACT_TAGS_ENABLED', 'true')
ARTIFACT_TAG_FILTERS_ENABLED = _env_bool('GOVHUB_ARTIFACT_TAG_FILTERS_ENABLED', 'true')

# Host → Layer middleware (GOV-HUB-3)
RESERVED_SUBDOMAINS = {
    "www", "dev", "api", "docs", "rfc", "app", "admin", "status",
    "static", "assets", "staging", "beta"
}
BASE_DOMAIN = "themetalayer.org"
# Multiple base domains for layer subdomain resolution (longest suffix wins in middleware).
# - rfc.* / themetalayer.org: production RFC / Meta-Layer hosts
# - dev.rfc.*: [layer].dev.rfc.themetalayer.org → same layer as /layer/[layer]/ on dev
# - govhub.live / dev.govhub.live: production Gov Hub + dev + layer vanity hosts
BASE_DOMAINS = [
    "dev.rfc.themetalayer.org",
    "rfc.themetalayer.org",
    "dev.govhub.live",
    "govhub.live",
    "themetalayer.org",
]

# Deployment safety
deployment_flag_file = os.path.join(PROJECT_ROOT, f".deployment_{'dev' if IS_DEVELOPMENT else 'prod'}")
DEPLOYMENT_MODE = os.path.exists(deployment_flag_file)

# Absolute site URL for email links (notifications, unsubscribe). No trailing slash.
PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'https://rfc.themetalayer.org').rstrip('/')

# Optional: shown in document-follow notification emails (on-page discussion via Canopi).
CANOPI_PUBLIC_URL = os.environ.get('CANOPI_PUBLIC_URL', 'https://app.canopi.live').rstrip('/')


def _git_rev_list_count():
    """Total commits on HEAD when .git exists (optional fallback for dev checkouts)."""
    try:
        import subprocess

        r = subprocess.run(
            ['git', '-C', PROJECT_ROOT, 'rev-list', '--count', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
        if r.returncode != 0:
            return None
        s = (r.stdout or '').strip()
        return int(s) if s.isdigit() else None
    except (OSError, ValueError):
        return None


def load_build_number():
    """
    Footer build number (cache busting / deploy verification).

    Priority:
    1. GOV_HUB_BUILD_NUMBER — CI or emergency override in .env only.
    2. INSTANCE_DIR/build_number.txt — maintained by scripts/update_build_number.sh on each deploy.
    3. Git commit depth — only if GOV_HUB_BUILD_FROM_GIT=1 (large on forked repos; opt-in).
    4. Default 74.
    """
    env_raw = os.environ.get('GOV_HUB_BUILD_NUMBER', '').strip()
    if env_raw:
        try:
            return int(env_raw)
        except ValueError:
            pass

    path = os.path.join(INSTANCE_DIR, 'build_number.txt')
    try:
        with open(path, 'r') as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        pass

    if os.environ.get('GOV_HUB_BUILD_FROM_GIT', '').strip().lower() in ('1', 'true', 'yes'):
        n = _git_rev_list_count()
        if n is not None:
            return n

    return 74


BUILD_NUMBER = load_build_number()
