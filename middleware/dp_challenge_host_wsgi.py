"""Rewrite DP Challenge custom domains to the existing hub."""
from __future__ import annotations

from typing import Callable, Iterable


class DpChallengeHostRewriteMiddleware:
    """Map desirableproperties.org/ to /dp-challenge/ without new routes."""

    _SKIP_PREFIXES = ('/static/', '/api/', '/auth/', '/login/', '/_deploy/')

    def __init__(self, wsgi_app: Callable, hosts: Iterable[str] = ()):
        self.wsgi_app = wsgi_app
        self.hosts = {h.lower().strip() for h in hosts if h}

    def __call__(self, environ, start_response):
        host = (
            environ.get('HTTP_X_FORWARDED_HOST')
            or environ.get('HTTP_HOST')
            or ''
        ).split(',')[0].strip().split(':')[0].lower()
        if host in self.hosts:
            path = environ.get('PATH_INFO') or '/'
            if not path.startswith(self._SKIP_PREFIXES) and not path.startswith('/dp-challenge/'):
                if path == '/':
                    environ['PATH_INFO'] = '/dp-challenge/'
                else:
                    new_path = '/dp-challenge' + path
                    if not new_path.endswith('/'):
                        new_path += '/'
                    environ['PATH_INFO'] = new_path
        return self.wsgi_app(environ, start_response)


def wrap_dp_challenge_host_rewrite(wsgi_app):
    return DpChallengeHostRewriteMiddleware(
        wsgi_app,
        hosts=('desirableproperties.org', 'www.desirableproperties.org'),
    )
