"""DP server proxy auth for Gov Hub admin invite routes."""
from unittest.mock import patch

import pytest

from app import app
from extensions import db
from models import User


@pytest.fixture
def client():
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_dp_proxy_admin_auth_allows_zoho_pathway(client, monkeypatch):
    secret = 'test-dp-proxy-secret'
    admin_email = 'daveed@example.com'
    monkeypatch.setenv('METAWEB_GOVHUB_INTERNAL_SECRET', secret)
    monkeypatch.setattr('config.DP_ADMIN_EMAILS', (admin_email,))
    monkeypatch.setattr('services.workgroup_authority.DP_ADMIN_EMAILS', (admin_email,))

    with patch('routes.dp_admin_invite.pathway_zoho_mail_contacts') as mock_pathway:
        mock_pathway.return_value = (
            {
                'success': True,
                'configured': True,
                'source': 'snapshot',
                'contacts': [{'id': 'a@example.com', 'email': 'a@example.com', 'name': 'A'}],
            },
            200,
        )
        response = client.post(
            '/api/admin/dp-invite/pathways/zoho/',
            json={'show_hidden': False},
            headers={
                'Authorization': f'Bearer {secret}',
                'X-DP-Admin-Email': admin_email,
            },
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['configured'] is True
    assert payload['contacts'][0]['email'] == 'a@example.com'
    mock_pathway.assert_called_once()


def test_dp_proxy_admin_auth_rejects_missing_header(client, monkeypatch):
    secret = 'test-dp-proxy-secret'
    monkeypatch.setenv('METAWEB_GOVHUB_INTERNAL_SECRET', secret)
    monkeypatch.setattr('config.DP_ADMIN_EMAILS', ('daveed@example.com',))

    response = client.post(
        '/api/admin/dp-invite/pathways/zoho/',
        json={},
        headers={'Authorization': f'Bearer {secret}'},
    )

    assert response.status_code == 401
    assert response.get_json()['error'] == 'Authentication required'


def test_dp_proxy_admin_auth_rejects_non_admin_email(client, monkeypatch):
    secret = 'test-dp-proxy-secret'
    monkeypatch.setenv('METAWEB_GOVHUB_INTERNAL_SECRET', secret)
    monkeypatch.setattr('config.DP_ADMIN_EMAILS', ('daveed@example.com',))

    response = client.post(
        '/api/admin/dp-invite/pathways/zoho/',
        json={},
        headers={
            'Authorization': f'Bearer {secret}',
            'X-DP-Admin-Email': 'stranger@example.com',
        },
    )

    assert response.status_code == 401


def test_dp_proxy_selection_get_set_and_patch(client, monkeypatch, tmp_path):
    secret = 'test-dp-proxy-secret'
    admin_email = 'daveed@example.com'
    monkeypatch.setenv('METAWEB_GOVHUB_INTERNAL_SECRET', secret)
    monkeypatch.setattr('config.DP_ADMIN_EMAILS', (admin_email,))
    monkeypatch.setattr('services.workgroup_authority.DP_ADMIN_EMAILS', (admin_email,))
    monkeypatch.setattr('services.dp_admin_invite_store.INSTANCE_DIR', str(tmp_path))

    headers = {
        'Authorization': f'Bearer {secret}',
        'X-DP-Admin-Email': admin_email,
    }

    empty = client.get('/api/admin/dp-invite/contacts/selection/', headers=headers)
    assert empty.status_code == 200
    assert empty.get_json()['emails'] == []

    saved = client.post(
        '/api/admin/dp-invite/contacts/selection/',
        json={'emails': ['Kevin@Example.com', 'nathan@example.com']},
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.get_json()['emails'] == ['kevin@example.com', 'nathan@example.com']

    patched = client.patch(
        '/api/admin/dp-invite/contacts/selection/',
        json={'remove': ['nathan@example.com'], 'add': ['noise@example.com']},
        headers=headers,
    )
    assert patched.status_code == 200
    assert patched.get_json()['emails'] == ['kevin@example.com', 'noise@example.com']
