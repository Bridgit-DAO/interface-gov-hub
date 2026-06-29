"""Email helpers: unsubscribe token creation/verification."""
import base64
import hmac
import hashlib

from flask import current_app


def make_unsubscribe_token(scope_id, user_id_or_email, scope_type='layer'):
    """Create signed token for unsubscribe link."""
    secret = (current_app.secret_key or 'secret').encode('utf-8')
    payload = f"{scope_type}:{scope_id}:{user_id_or_email}"
    sig = hmac.new(secret, payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode().rstrip('=')


def verify_unsubscribe_token(token):
    """Verify and decode token. Returns (scope_type, scope_id, user_id_or_email) or None."""
    try:
        padded = token + '=' * (4 - len(token) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
        payload, sig = raw.rsplit(':', 1)
        secret = (current_app.secret_key or 'secret').encode('utf-8')
        expected = hmac.new(secret, payload.encode('utf-8'), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return None
        parts = payload.split(':', 2)
        if len(parts) == 3:
            return (parts[0], parts[1], parts[2])
        if len(parts) == 2:
            return ('layer', parts[0], parts[1])
    except Exception:
        pass
    return None
