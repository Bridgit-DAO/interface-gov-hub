"""Application configuration: env, paths, deployment, build number."""
import os

from dotenv import load_dotenv

load_dotenv('/home/ubuntu/xowlz/burned/.env')

# Project root (parent of config.py)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

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

# Host → Layer middleware (GOV-HUB-3)
RESERVED_SUBDOMAINS = {
    "www", "dev", "api", "docs", "rfc", "app", "admin", "status",
    "static", "assets", "staging", "beta"
}
BASE_DOMAIN = "themetalayer.org"
# Multiple base domains for layer subdomain resolution
# (canopi.themetalayer.org, canopi.rfc.themetalayer.org - prod only; dev uses paths)
BASE_DOMAINS = ["rfc.themetalayer.org", "themetalayer.org"]

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
