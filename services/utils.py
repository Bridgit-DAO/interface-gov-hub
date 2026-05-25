"""Pure utility functions (no db, no Flask app)."""
import re
import random
import string
import secrets
import time
from collections import defaultdict

# In-memory rate limit store (per-process)
_rate_limit_store = defaultdict(list)


def coerce_storage_bool(value, default=False):
    """SQLite often stores booleans as TEXT '0'/'1'; bool('0') is True in Python."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) != 0
    s = str(value).strip().lower()
    if s in ('0', 'false', 'no', 'off', '', 'none', 'null'):
        return False
    if s in ('1', 'true', 'yes', 'on'):
        return True
    return default


def check_rate_limit(identifier, max_requests=5, window_seconds=300):
    """Simple in-memory rate limiting. Returns True if under limit, False if exceeded."""
    now = time.time()
    key = str(identifier)
    _rate_limit_store[key] = [t for t in _rate_limit_store[key] if now - t < window_seconds]
    if len(_rate_limit_store[key]) >= max_requests:
        return False
    _rate_limit_store[key].append(now)
    return True


def _is_uuid_like(s):
    """True if s looks like a UUID (36 chars, hex + hyphens)."""
    if not s or not isinstance(s, str):
        return False
    return len(s) == 36 and s.count('-') == 4 and all(c in '0123456789abcdefABCDEF-' for c in s)


def create_slug(text):
    """Create URL-safe slug from text."""
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    return slug[:100]


def _generate_id(prefix):
    """Generate unique ID with given prefix."""
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"{prefix}_{suffix}"


def generate_layer_id():
    return _generate_id("layer")


def generate_workgroup_id():
    return _generate_id("wg")


def generate_guild_id():
    return _generate_id("guild")


def generate_cluster_id():
    return _generate_id("clu")


def generate_role_id():
    return _generate_id("rol")


def generate_claim_id():
    return _generate_id("clm")


def generate_badge_id():
    return _generate_id("bdg")


def generate_invitation_token():
    """Generate secure token for guild invitations."""
    return secrets.token_urlsafe(32)


def generate_role_image_id():
    """Generate unique role image ID with rimg_ prefix."""
    return _generate_id("rimg")


def allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed. Default: txt, pdf, xml, doc, docx."""
    if allowed_extensions is None:
        allowed_extensions = {'txt', 'pdf', 'xml', 'doc', 'docx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def allowed_image_file(filename, allowed_extensions=None):
    """Check if image file extension is allowed. Default: png, jpg, jpeg, gif, webp, svg."""
    if allowed_extensions is None:
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
