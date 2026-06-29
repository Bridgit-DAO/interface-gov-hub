"""Request/response middleware: script name, deployment safety, security headers, layer resolution."""
import re
import secrets

from flask import request, g, jsonify, session, current_app, redirect, flash

from models import Layer
from services.utils import _is_uuid_like


# CSP for embed widget: Web3Auth modal, Font Awesome (cdnjs), CDNs
EMBED_CSP = (
    "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: https: http: blob:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' 'unsafe-hashes' https: http: blob:; "
    "style-src 'self' 'unsafe-inline' https: http: blob:; "
    "frame-src 'self' https: http: blob: https://*.web3auth.io https://*.walletconnect.org https://*.walletconnect.com; "
    "connect-src 'self' https: http: wss: blob:; "
    "img-src 'self' data: https: http: blob:; "
    "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com;"
)

DEFAULT_CSP = (
    "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: https: http:; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' 'unsafe-hashes' https: http: blob: https://unpkg.com https://cdn.jsdelivr.net https://*.web3auth.io https://*.walletconnect.org https://*.walletconnect.com; "
    "style-src 'self' 'unsafe-inline' https: http:; "
    "frame-src 'self' https: http: blob: https://*.web3auth.io https://*.walletconnect.org https://*.walletconnect.com; "
    "connect-src 'self' https: http: wss:; "
    "img-src 'self' data: https: http: blob:; "
    "font-src 'self' data: https://cdnjs.cloudflare.com https://fonts.gstatic.com https:;"
)

UNSAFE_METHODS = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})
CSRF_EXEMPT_PREFIXES = ('/_deploy/', '/auth/', '/static/')
# Exact paths and suffixes exempt from CSRF (webhooks, public sign-in, embed waitlist join).
CSRF_EXEMPT_EXACT = frozenset({
    '/api/auth/web3auth',
    '/api/inscribe/stripe-webhook',
})
CSRF_EXEMPT_SUFFIXES = ('/join-email', '/join-email/')
CSRF_FIELD_RE = re.compile(
    r'(<form\b(?=[^>]*\bmethod=["\']?post["\']?)[^>]*>)',
    flags=re.IGNORECASE,
)


def _csrf_token():
    from services.csrf import get_or_create_csrf_token
    return get_or_create_csrf_token()


def _csrf_exempt_path(path):
    p = path or ''
    if any(p.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES):
        return True
    normalized = p.rstrip('/') or '/'
    if normalized in CSRF_EXEMPT_EXACT:
        return True
    for suffix in CSRF_EXEMPT_SUFFIXES:
        if normalized.endswith(suffix.rstrip('/')) or p.endswith(suffix):
            return True
    return False


def _request_looks_like_browser_form():
    ctype = (request.content_type or '').split(';', 1)[0].strip().lower()
    return ctype in ('application/x-www-form-urlencoded', 'multipart/form-data')


def _inject_csrf_inputs(response):
    if response.direct_passthrough:
        return response
    ctype = (response.content_type or '').lower()
    if 'text/html' not in ctype:
        return response
    body = response.get_data(as_text=True)
    if '<form' not in body.lower():
        return response
    token_input = (
        f'<input type="hidden" name="csrf_token" value="{_csrf_token()}">'
    )
    body = CSRF_FIELD_RE.sub(lambda m: m.group(1) + token_input, body)
    response.set_data(body)
    return response


def register_request_handlers(app, deployment_mode=False, base_domain='themetalayer.org', reserved_subdomains=None, base_domains=None):
    """Register before_request and after_request handlers with the Flask app."""
    if reserved_subdomains is None:
        reserved_subdomains = {"www", "dev", "api", "docs", "rfc", "app", "admin", "status", "static", "assets", "staging", "beta"}

    @app.before_request
    def _resolve_site_locale():
        from services.locale import resolve_request_locale
        resolve_request_locale()

    @app.before_request
    def set_script_name_from_proxy():
        """When served under /dev/ (layer subdomain path), set SCRIPT_NAME so url_for generates correct links."""
        prefix = request.headers.get('X-Forwarded-Prefix', '').rstrip('/')
        if prefix:
            request.environ['SCRIPT_NAME'] = prefix

    @app.before_request
    def deployment_safety_check():
        """Block data modifications during deployment"""
        if deployment_mode and request.method in ['POST', 'PUT', 'DELETE', 'PATCH']:
            if (request.path.startswith('/_deploy/') or
                request.path.startswith('/static/') or
                request.path in ['/login/', '/logout/']):
                return
            print(f"🚨 BLOCKED {request.method} {request.path} - Deployment mode active")
            return jsonify({'error': 'Data modifications disabled during deployment'}), 403

    @app.before_request
    def csrf_check():
        """Protect form POSTs and session-authenticated JSON API calls."""
        import sys

        from services.csrf import csrf_token_valid, get_or_create_csrf_token

        if current_app.config.get('TESTING') or 'pytest' in sys.modules:
            return None
        if request.method not in UNSAFE_METHODS:
            return None
        if _csrf_exempt_path(request.path):
            return None

        expected = session.get('_csrf_token') or get_or_create_csrf_token()

        if _request_looks_like_browser_form():
            supplied = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
            if not csrf_token_valid(supplied, expected):
                accept = (request.headers.get('Accept') or '').lower()
                if 'text/html' in accept and request.referrer:
                    flash(
                        'Your session security token expired. Please refresh the page and try again.',
                        'error',
                    )
                    return redirect(request.referrer)
                return jsonify({'error': 'Invalid CSRF token'}), 400
            return None

        # Cookie-session JSON APIs: require X-CSRFToken (see BASE_TEMPLATE fetch wrapper).
        if 'user' not in session:
            return None

        ctype = (request.content_type or '').split(';', 1)[0].strip().lower()
        if ctype not in ('application/json', 'application/vnd.api+json'):
            return None

        supplied = request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token')
        if not csrf_token_valid(supplied, expected):
            return jsonify({'error': 'Invalid CSRF token'}), 403
        return None

    @app.after_request
    def add_security_headers(response):
        """Add security headers including CSP for inline scripts"""
        if request.path.startswith('/embed/'):
            response.headers['Content-Security-Policy'] = EMBED_CSP
        else:
            response.headers['Content-Security-Policy'] = DEFAULT_CSP
        if request.is_secure:
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=63072000; includeSubDomains; preload',
            )
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'camera=(), microphone=(), geolocation=()',
        )
        if request.path.startswith('/embed/'):
            response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        else:
            response.headers.setdefault('X-Frame-Options', 'DENY')
        return _inject_csrf_inputs(response)

    @app.before_request
    def _resolve_campaign_host():
        from services.campaign_pages import campaign_for_host

        host = (request.headers.get('X-Forwarded-Host') or request.host).split(',')[0].strip().split(':')[0].lower()
        cfg = campaign_for_host(host)
        if not cfg:
            return
        g.campaign_slug = cfg.slug
        g.campaign_config = cfg
        path = request.path or '/'
        if path.startswith(('/static/', '/api/', '/auth/', '/login/', '/_deploy/')):
            return

    @app.before_request
    def _resolve_layer():
        if getattr(g, 'campaign_slug', None):
            return
        _do_resolve_layer_from_host(base_domain, reserved_subdomains, base_domains)

    @app.before_request
    def _product_rollout():
        from services.product_rollout import apply_product_rollout_before_request
        return apply_product_rollout_before_request()


def _do_resolve_layer_from_host(base_domain='themetalayer.org', reserved_subdomains=None, base_domains=None):
    """Resolve layer context from subdomain or path (GOV-HUB-3). Standalone for tests."""
    from flask import request, g

    if reserved_subdomains is None:
        reserved_subdomains = {"www", "dev", "api", "docs", "rfc", "app", "admin", "status", "static", "assets", "staging", "beta"}
    if base_domains is None:
        base_domains = [base_domain]

    g.layer = None
    g.layer_slug = None

    # Prefer X-Forwarded-Host when behind proxy (ProxyFix x_host=1 handles this for request.host)
    host = (request.headers.get('X-Forwarded-Host') or request.host).split(',')[0].strip().split(':')[0].lower()

    # Try each base domain (longer first so canopi.rfc.themetalayer.org matches rfc.themetalayer.org)
    for bd in sorted(base_domains, key=len, reverse=True):
        if host == bd or host.endswith('.' + bd):
            subdomain = host[: -(len(bd) + 1)] if host != bd else ''
            if subdomain and '.' not in subdomain and subdomain not in reserved_subdomains:
                project = Layer.query.filter_by(slug=subdomain).first()
                if project:
                    g.layer = project
                    g.layer_slug = subdomain
                    return
            break  # Matched a base domain, don't try others

    path = (request.path or '').rstrip('/')
    if path.startswith('/'):
        path = path[1:]
    parts = path.split('/') if path else []

    # /layers/<slug>/ = directory view (global nav: Layers, Roles, etc.). Do NOT set g.layer_slug.
    if len(parts) >= 1 and parts[0] == 'layers' and len(parts) >= 2:
        slug = parts[1]
        if slug and slug not in ('create',):
            project = Layer.query.filter_by(slug=slug).first()
            if project:
                g.layer = project
                # g.layer_slug left None so governance nav shows Layers (global), not About (layer-centric)
                return

    if len(parts) >= 2 and parts[0] == 'layer':
        segment = parts[1]
        if segment:
            if _is_uuid_like(segment):
                project = Layer.query.filter_by(public_id=segment).first()
            else:
                project = Layer.query.filter_by(slug=segment).first()
            if project:
                g.layer = project
                g.layer_slug = project.slug
                return


def resolve_layer_from_host():
    """Resolve layer from subdomain/path. For tests: use with app.test_request_context()."""
    from config import BASE_DOMAIN, RESERVED_SUBDOMAINS, BASE_DOMAINS
    _do_resolve_layer_from_host(BASE_DOMAIN, RESERVED_SUBDOMAINS, BASE_DOMAINS)
