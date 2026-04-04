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


def load_build_number():
    """Load and increment build number for cache busting. Returns int."""
    path = os.path.join(PROJECT_ROOT, 'instance_dev', 'build_number.txt')
    try:
        with open(path, 'r') as f:
            n = int(f.read().strip())
    except (FileNotFoundError, ValueError):
        n = 74
    try:
        with open(path, 'w') as f:
            f.write(str(n + 1))
    except Exception:
        pass
    return n


BUILD_NUMBER = load_build_number()
