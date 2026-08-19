"""Tests for campaign vanity-domain auth helpers."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('SECRET_KEY', 'isolated-test-secret-key')


def test_safe_campaign_return_url_allows_registered_vanity():
    from services.campaign_auth import safe_campaign_return_url

    url = safe_campaign_return_url('https://teilhardtest.com/docs/statement/')
    assert url == 'https://teilhardtest.com/docs/statement/'


def test_safe_campaign_return_url_rejects_unknown_host():
    from services.campaign_auth import safe_campaign_return_url

    assert safe_campaign_return_url('https://evil.example/phish') is None


def test_campaign_login_url_on_vanity_uses_hub():
    from flask import Flask

    from services.campaign_auth import campaign_login_url
    from services.campaign_pages import get_campaign

    app = Flask(__name__)
    cfg = get_campaign('teilhard')
    assert cfg is not None
    with app.test_request_context('/', base_url='https://teilhardtest.com/'):
        href = campaign_login_url(cfg, '/docs/statement/')
        assert href.startswith('https://dev.hub.themetalayer.org/login/?next=')
        assert 'teilhardtest.com' in href
        assert 'docs%2Fstatement' in href or 'docs/statement' in href


def test_campaign_login_url_on_hub_stays_relative():
    from flask import Flask

    from services.campaign_auth import campaign_login_url
    from services.campaign_pages import get_campaign

    app = Flask(__name__)
    cfg = get_campaign('teilhard')
    assert cfg is not None
    with app.test_request_context('/', base_url='https://dev.hub.themetalayer.org/'):
        href = campaign_login_url(cfg, '/docs/statement/')
        assert href.startswith('/login/?next=')
        assert 'teilhard' in href
        assert 'statement' in href


def test_vanity_login_redirects_to_hub():
    from app import app

    client = app.test_client()
    r = client.get(
        '/login/?next=/campaign/teilhard/docs/statement/',
        base_url='https://teilhardtest.com/',
        follow_redirects=False,
    )
    assert r.status_code == 302
    loc = r.headers.get('Location', '')
    assert 'dev.hub.themetalayer.org/login/' in loc
    assert 'teilhardtest.com' in loc


def test_handoff_token_round_trip():
    from services.campaign_auth import make_campaign_handoff_token, verify_campaign_handoff_token

    token = make_campaign_handoff_token('test-user')
    assert verify_campaign_handoff_token(token) == 'test-user'


def test_build_campaign_handoff_redirect():
    from services.campaign_auth import build_campaign_handoff_redirect

    url = build_campaign_handoff_redirect(
        'https://teilhardtest.com/docs/statement/',
        'test-user',
    )
    assert url.startswith('https://teilhardtest.com/auth/campaign-handoff/?token=')
    assert 'next=' in url


def test_hub_login_sso_redirects_when_already_authenticated():
    """Hub /login/ with hub session + campaign next= should hand off without Web3Auth."""
    from app import app

    app.config['TESTING'] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user'] = 'admin'
        r = client.get(
            '/login/?next=https://teilhardtest.com/docs/statement/',
            follow_redirects=False,
        )
        assert r.status_code == 302
        loc = r.headers.get('Location', '')
        assert loc.startswith('https://teilhardtest.com/auth/campaign-handoff/?token=')
