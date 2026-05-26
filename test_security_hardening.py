"""Tests for URL safety and upload validation."""
import os
import sys
from io import BytesIO

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_validate_ordinals_fetch_url_accepts_content_url():
    from services.url_safety import validate_ordinals_fetch_url

    url = 'https://ordinals.com/content/8e24de5198a4634a1eea89b0984119aea18123e48e132i0'
    assert validate_ordinals_fetch_url(url) == url


def test_validate_ordinals_fetch_url_rejects_internal():
    from services.url_safety import validate_ordinals_fetch_url

    with pytest.raises(ValueError):
        validate_ordinals_fetch_url('http://127.0.0.1/content/foo')


def test_validate_ordinals_fetch_url_rejects_non_ordinals_host():
    from services.url_safety import validate_ordinals_fetch_url

    with pytest.raises(ValueError):
        validate_ordinals_fetch_url('https://evil.com/content/abc')


def test_submission_upload_rejects_bad_extension():
    from app import app

    with app.app_context():
        from services.submission_uploads import validate_submission_upload

        storage = type('FS', (), {})()
        storage.filename = 'malware.exe'
        storage.seek = lambda *a, **k: None
        storage.tell = lambda: 100

        _, err = validate_submission_upload(storage)
        assert err is not None
        assert 'Invalid file type' in err


def test_user_search_requires_auth():
    from app import app

    client = app.test_client()
    response = client.get('/api/users/search/?q=ad')
    assert response.status_code in (302, 401, 403)


def test_session_json_csrf_required_without_pytest_bypass():
    from app import app
    from models import User

    with app.app_context():
        user = User.query.first()
        if not user:
            pytest.skip('Need a user in DB')
        username = user.username

    saved_pytest = sys.modules.pop('pytest', None)
    try:
        with app.test_client() as client:
            with client.session_transaction() as sess:
                sess['user'] = username
                sess['_csrf_token'] = 'expected-token'

            bad = client.patch(
                '/api/submissions/fake-id/metadata/',
                json={'title': 'nope'},
            )
            ok = client.patch(
                '/api/submissions/fake-id/metadata/',
                json={'title': 'nope'},
                headers={'X-CSRFToken': 'expected-token'},
            )
    finally:
        if saved_pytest is not None:
            sys.modules['pytest'] = saved_pytest

    assert bad.status_code == 403
    assert ok.status_code != 403
