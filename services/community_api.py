"""Delegated API access; no global secrets or proxy administrator impersonation."""
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import abort, current_app, g, request
from extensions import db
from models import User
from models.community_intelligence import CIAccessToken
from services import community_intelligence as ci

# Explicit allowlist: new endpoints do not become agent-accessible by accident.
ENDPOINT_SCOPES = {
    **dict.fromkeys(['overview', 'detail', 'original', 'answer', 'rooms_list',
                    'rooms_get', 'rooms_draft', 'tracked_opportunities', 'openapi'], 'read'),
    **dict.fromkeys(['submit', 'retry'], 'contribute'),
    **dict.fromkeys(['rooms_create', 'rooms_message', 'rooms_facilitate', 'rooms_action',
                    'save_opportunity', 'update_opportunity'], 'coordinate'),
}
SCOPES = {'read', 'contribute', 'coordinate'}


def digest(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


def token_valid(token):
    return token is not None and token.revoked_at is None and token.expires_at > datetime.utcnow()


def authenticate(layer_id):
    if not request.is_secure and not current_app.config.get('IS_DEVELOPMENT') and not current_app.testing:
        abort(403, description='Bearer credentials require HTTPS.')
    auth = request.headers.get('Authorization', '')
    scheme, _, secret = auth.partition(' ')
    if scheme.lower() != 'bearer' or not secret.startswith('ci_') or len(secret) > 200:
        abort(401, description='A valid Community Intelligence bearer token is required.')
    token = CIAccessToken.query.filter_by(digest=digest(secret), layer_id=layer_id).first()
    if not token_valid(token):
        abort(401, description='Token invalid, expired or revoked.')
    needed = ENDPOINT_SCOPES.get(request.endpoint.rsplit('.', 1)[-1])
    if needed is None or needed not in token.scopes:
        abort(403, description='This token does not permit this operation. Human review and administration require a session.')
    user = db.session.get(User, token.user_id)
    if not user:
        abort(401)
    # Revalidate credential after response construction, alongside memberships.
    g.ci_token_id = token.id
    g.ci_token_scopes = tuple(token.scopes)
    from services.utils import check_rate_limit
    if not check_rate_limit('ci-api:' + token.id, max_requests=120, window_seconds=60):
        abort(429, description='API request limit exceeded. Retry in 60 seconds.')
    return {'id': user.id, 'username': user.username, 'role': user.role}


def issue(layer_id, user_id, data):
    scopes = data.get('scopes', ['read'])
    days = data.get('expires_in_days', 7)
    if not isinstance(scopes, list) or not scopes or not all(isinstance(s, str) and s in SCOPES for s in scopes):
        abort(400, description='Scopes must be read, contribute or coordinate.')
    if type(days) is not int or not 1 <= days <= 90:
        abort(400, description='Expiry must be between 1 and 90 days.')
    count = CIAccessToken.query.filter_by(layer_id=layer_id, user_id=user_id, revoked_at=None).filter(
        CIAccessToken.expires_at > datetime.utcnow()).count()
    if count >= 20:
        abort(409, description='Revoke an existing token before issuing another (limit 20).')
    secret = 'ci_' + secrets.token_urlsafe(32)
    token = CIAccessToken(layer_id=layer_id, user_id=user_id, name=ci.text_field(data, 'name', 100),
                          digest=digest(secret), scopes=sorted(set(scopes)),
                          expires_at=datetime.utcnow() + timedelta(days=days))
    db.session.add(token)
    db.session.flush()
    return token, secret


def describe(token):
    return dict(id=token.id, name=token.name, scopes=token.scopes,
                expires_at=token.expires_at.isoformat()+'Z',
                revoked=token.revoked_at is not None, created_at=token.created_at.isoformat()+'Z')


def allowed_origin():
    origin = request.headers.get('Origin')
    allowed = current_app.config.get('COMMUNITY_API_ORIGINS', ())
    return origin if origin and origin != 'null' and origin in allowed and '*' not in origin else None


def preflight():
    if not allowed_origin():
        abort(403, description='Origin is not allowed for this API.')
    if request.headers.get('Access-Control-Request-Method') not in {'GET', 'POST', 'PATCH', 'DELETE'}:
        abort(403)
    headers = {h.strip().lower() for h in request.headers.get('Access-Control-Request-Headers', '').split(',') if h.strip()}
    if not headers <= {'authorization', 'content-type'}:
        abort(403)
    return '', 204


def cors(response):
    response.vary.add('Origin')
    if allowed_origin() and (request.method == 'OPTIONS' or request.headers.get('Authorization')):
        response.headers['Access-Control-Allow-Origin'] = allowed_origin()
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
        response.headers['Access-Control-Expose-Headers'] = 'Retry-After, X-Community-API-Version'
        response.headers['Access-Control-Max-Age'] = '600'
    response.headers['X-Community-API-Version'] = '1'
    if response.status_code == 401:
        response.headers['WWW-Authenticate'] = 'Bearer realm="community-intelligence"'
    if response.status_code == 429:
        response.headers['Retry-After'] = '60'
    return response
