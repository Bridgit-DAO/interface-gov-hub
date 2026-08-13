"""Zoho Mail snapshot ingest helpers."""
import json
import os
from pathlib import Path

from services.zoho_mail import (
    aggregate_external_contacts,
    contacts_snapshot_path,
    message_matches_meta_layer,
    search_meta_layer_contacts,
    zoho_snapshot_configured,
)


def test_message_matches_meta_layer_term():
    assert message_matches_meta_layer('Meta-layer workshop', 'Thanks for joining')
    assert not message_matches_meta_layer('Lunch tomorrow', 'See you at noon')


def test_aggregate_external_contacts_excludes_owner():
    messages = [
        {
            'subject': 'Gov Hub invite',
            'summary': 'Join our workgroup',
            'received': '2026-01-02',
            'participants': ['Kevin Barry <kevin@example.com>', 'You <owner@example.com>'],
        },
    ]
    contacts = aggregate_external_contacts(messages, owner_email='owner@example.com')
    assert len(contacts) == 1
    assert contacts[0]['email'] == 'kevin@example.com'
    assert contacts[0]['message_count'] == 1


def test_search_meta_layer_contacts_prefers_snapshot(tmp_path, monkeypatch):
    snapshot = tmp_path / 'invite_zoho_contacts_snapshot.json'
    snapshot.write_text(
        json.dumps(
            {
                'exported_at': '2026-01-01T00:00:00+00:00',
                'message_count': 2,
                'contacts': [
                    {
                        'email': 'kevin@example.com',
                        'name': 'Kevin Barry',
                        'message_count': 2,
                        'subjects': ['Meta-layer cert'],
                        'snippets': ['Congrats on Level I'],
                        'last_contact': '2026-01-01',
                    },
                ],
            },
        ),
        encoding='utf-8',
    )
    monkeypatch.setenv('ZOHO_MAIL_CONTACTS_SNAPSHOT', str(snapshot))
    monkeypatch.delenv('ZOHO_MAIL_REFRESH_TOKEN', raising=False)

    payload = search_meta_layer_contacts()
    assert payload['configured'] is True
    assert payload['source'] == 'snapshot'
    assert payload['contacts'][0]['email'] == 'kevin@example.com'
    assert zoho_snapshot_configured() is True
    assert contacts_snapshot_path() == str(snapshot)
