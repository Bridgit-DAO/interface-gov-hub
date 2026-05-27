"""Tests for post-login return URL helpers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_safe_return_path():
    from services.auth_redirect import safe_return_path

    assert safe_return_path('/doc/draft/foo/read/') == '/doc/draft/foo/read/'
    assert safe_return_path('/doc/draft/foo/read/?x=1') == '/doc/draft/foo/read/?x=1'
    assert safe_return_path('https://evil.com/phish') is None
    assert safe_return_path('//evil.com/phish') is None
    assert safe_return_path(None) is None


def test_login_url_includes_next():
    from services.auth_redirect import login_url

    assert login_url('/doc/draft/j64tnris/read/') == '/login/?next=%2Fdoc%2Fdraft%2Fj64tnris%2Fread%2F'
    assert login_url() == '/login/'


def test_register_route_redirects_to_login():
    from app import app

    client = app.test_client()
    r = client.get('/register/', follow_redirects=False)
    assert r.status_code == 302
    assert '/login/' in r.headers.get('Location', '')


def test_login_admin_shortcut_redirects():
    from app import app

    client = app.test_client()
    r = client.get('/login/product-rollout', follow_redirects=False)
    assert r.status_code == 302
    assert r.headers.get('Location') == '/login/?next=%2Fadmin%2Fproduct-rollout%2F'

    r = client.get('/login/nav-pills', follow_redirects=False)
    assert r.status_code == 302
    assert r.headers.get('Location') == '/login/?next=%2Fadmin%2Fnav-pills%2F'


def test_login_route_redirects_when_already_authed():
    from app import app
    from models import User

    with app.app_context():
        user = User.query.first()
        if not user:
            return
        username = user.username

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = username
    r = client.get('/login/?next=/doc/draft/j64tnris/read/')
    assert r.status_code == 302
    assert '/doc/draft/j64tnris/read/' in r.headers.get('Location', '')
