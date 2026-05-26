"""Authorization tests for admin-only coordinator management."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _participant_user():
    from app import app
    from models import User

    with app.app_context():
        user = User.query.filter_by(role='user').first()
        if not user:
            user = User.query.filter(User.role.notin_(['admin', 'editor'])).first()
    return user


def _admin_user():
    from app import app
    from models import User

    with app.app_context():
        return User.query.filter(User.role.in_(['admin', 'editor'])).first()


def test_admin_chairs_requires_admin_role():
    from app import app

    participant = _participant_user()
    if not participant:
        pytest.skip('No participant user in DB')

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = participant.username

    response = client.get('/admin/chairs/')
    assert response.status_code == 403


def test_participant_cannot_approve_chair():
    from app import app
    from models import WorkingGroupChair

    with app.app_context():
        participant = _participant_user()
        chair = WorkingGroupChair.query.first()
    if not participant or not chair:
        pytest.skip('Need participant user and at least one chair row')

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = participant.username
        sess['_csrf_token'] = 'test-csrf-token'

    response = client.post(
        f'/admin/chairs/{chair.id}/approve',
        data={'csrf_token': 'test-csrf-token'},
    )
    assert response.status_code == 403


def test_deploy_status_hidden_outside_dev(monkeypatch):
    from app import app

    monkeypatch.setenv('DEPLOY_STATUS_SECRET', '')
    with app.app_context():
        app.config['IS_DEVELOPMENT'] = False
        app.config['ENV'] = 'production'

    client = app.test_client()
    response = client.get('/_deploy/status')
    assert response.status_code == 404


def test_deploy_health_still_public(monkeypatch):
    from app import app

    monkeypatch.setenv('DEPLOY_STATUS_SECRET', '')
    with app.app_context():
        app.config['IS_DEVELOPMENT'] = False

    client = app.test_client()
    response = client.get('/_deploy/health')
    assert response.status_code in (200, 503)
