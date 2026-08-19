"""Rewrite PATH_INFO for custom campaign domains before Flask builds the Request."""
from __future__ import annotations

from typing import Callable, Dict, Mapping


class CampaignHostRewriteMiddleware:
    """Map teilhardtest.com/ → /campaign/teilhard/ at the WSGI layer."""

    _SKIP_PREFIXES = (
        '/static/',
        '/uploads/',
        '/api/',
        '/auth/',
        '/login/',
        '/logout/',
        '/_deploy/',
        '/embed/',
        '/doc/',
        '/view/',
        '/download/',
    )

    def __init__(self, wsgi_app: Callable, host_to_slug: Mapping[str, str]):
        self.wsgi_app = wsgi_app
        self.host_to_slug = dict(host_to_slug)

    def __call__(self, environ, start_response):
        host = (
            environ.get('HTTP_X_FORWARDED_HOST')
            or environ.get('HTTP_HOST')
            or ''
        ).split(',')[0].strip().split(':')[0].lower()
        slug = self.host_to_slug.get(host)
        if slug:
            path = environ.get('PATH_INFO') or '/'
            if not path.startswith(self._SKIP_PREFIXES):
                prefix = f'/campaign/{slug}'
                if not path.startswith(prefix):
                    if path == '/':
                        environ['PATH_INFO'] = f'{prefix}/'
                    else:
                        new_path = prefix + path
                        if not new_path.endswith('/'):
                            new_path += '/'
                        environ['PATH_INFO'] = new_path
        return self.wsgi_app(environ, start_response)


def build_campaign_host_map(app) -> Dict[str, str]:
    with app.app_context():
        from services.campaign_pages import _load_all_campaigns

        host_map: Dict[str, str] = {}
        for slug, cfg in _load_all_campaigns().items():
            for host in cfg.hosts():
                host_map[host] = slug
        return host_map


def wrap_campaign_host_rewrite(wsgi_app, app):
    return CampaignHostRewriteMiddleware(wsgi_app, build_campaign_host_map(app))
