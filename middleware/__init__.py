"""Request/response middleware: script name, deployment safety, security headers, layer resolution."""
from flask import request, g, jsonify

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


def register_request_handlers(app, deployment_mode=False, base_domain='themetalayer.org', reserved_subdomains=None, base_domains=None):
    """Register before_request and after_request handlers with the Flask app."""
    if reserved_subdomains is None:
        reserved_subdomains = {"www", "dev", "api", "docs", "rfc", "app", "admin", "status", "static", "assets", "staging", "beta"}

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

    @app.after_request
    def add_security_headers(response):
        """Add security headers including CSP for inline scripts"""
        if request.path.startswith('/embed/'):
            response.headers['Content-Security-Policy'] = EMBED_CSP
        else:
            response.headers['Content-Security-Policy'] = DEFAULT_CSP
        return response

    @app.before_request
    def _resolve_layer():
        _do_resolve_layer_from_host(base_domain, reserved_subdomains, base_domains)


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
