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

    from services.campaign_auth import campaign_login_url, gov_hub_public_url
    from services.campaign_pages import get_campaign

    app = Flask(__name__)
    cfg = get_campaign('teilhard')
    assert cfg is not None
    hub = gov_hub_public_url()
    with app.test_request_context('/', base_url='https://teilhardtest.com/'):
        href = campaign_login_url(cfg, '/docs/statement/')
        assert href.startswith(hub + '/login/?next=')
        assert 'teilhardtest.com' in href
        assert 'docs%2Fstatement' in href or 'docs/statement' in href


def test_campaign_login_url_on_hub_stays_relative():
    from flask import Flask

    from services.campaign_auth import campaign_login_url, gov_hub_public_url
    from services.campaign_pages import get_campaign

    app = Flask(__name__)
    cfg = get_campaign('teilhard')
    assert cfg is not None
    hub = gov_hub_public_url()
    with app.test_request_context('/', base_url=hub + '/'):
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
    from services.campaign_auth import gov_hub_public_url
    assert gov_hub_public_url().split('://', 1)[1] + '/login/' in loc
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


def test_campaign_shell_shows_user_when_session_on_vanity():
    """Vanity campaign header should reflect an established session after handoff."""
    from app import app
    from services.campaign_auth import make_campaign_handoff_token

    app.config['TESTING'] = True
    with app.test_client() as client:
        token = make_campaign_handoff_token('admin')
        client.get(
            f'/auth/campaign-handoff/?token={token}&next=/docs/statement/',
            base_url='https://teilhardtest.com',
            follow_redirects=True,
        )
        r = client.get('/docs/statement/', base_url='https://teilhardtest.com')
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert 'gh-campaign-user-menu' in body
        assert 'Sign out' in body
        assert 'dropdown-menu' in body
        assert 'gh-campaign-user-name' not in body
        assert 'data-gh-authed="1"' in body
        assert 'gh-campaign-dev-banner' in body
        assert 'gh-endorse-form' in body


def test_campaign_shell_sign_in_when_anonymous_on_vanity():
    from app import app

    app.config['TESTING'] = True
    with app.test_client() as client:
        r = client.get(
            '/docs/statement/',
            base_url='https://teilhardtest.com',
        )
        body = r.get_data(as_text=True)
        assert 'btn-outline-light' in body
        assert 'Sign in</a>' in body
        assert 'data-gh-authed="0"' in body
        assert 'ghCampaignHubHandoff' in body
