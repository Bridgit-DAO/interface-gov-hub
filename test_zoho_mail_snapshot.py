"""Zoho Mail snapshot ingest helpers."""
import json
import os
from pathlib import Path

from services.zoho_mail import (
    aggregate_external_contacts,
    contact_has_meta_layer_signal,
    contact_matches_meta_layer_topics,
    contacts_snapshot_path,
    filter_outreach_contacts,
    message_matches_meta_layer,
    meta_layer_terms,
    outreach_selection_reasons,
    owner_exclude_emails,
    search_meta_layer_contacts,
    zoho_snapshot_configured,
)


def test_message_matches_meta_layer_term():
    assert message_matches_meta_layer('Meta-layer workshop', 'Thanks for joining')
    assert message_matches_meta_layer('Trust and identity panel', 'Discussing verification')
    assert message_matches_meta_layer('Intellectual sovereignty notes', 'Civic governance draft')
    assert not message_matches_meta_layer('Lunch tomorrow', 'See you at noon')


def test_meta_layer_terms_include_expanded_topics():
    terms = meta_layer_terms()
    for expected in (
        'presence',
        'overweb',
        'pci community',
        'trust',
        'identity',
        'misinformation',
        'credential',
        'verification',
        'reputation',
        'intellectual sovereignty',
        'certification',
        'governance',
        'fixing the internet',
        'open web',
        'civic tech',
        'digital public infrastructure',
    ):
        assert expected in terms


def test_contact_matches_meta_layer_topics_from_subjects_and_snippets():
    row = {
        'meta_layer_message_count': 0,
        'subjects': ['Overweb planning call'],
        'snippets': ['Follow up on presence community'],
    }
    assert contact_matches_meta_layer_topics(row)
    assert contact_has_meta_layer_signal(row)


def test_outreach_selection_reasons_message_count_and_topic_hits():
    row = {
        'email': 'partner@example.com',
        'message_count': 4,
        'meta_layer_message_count': 2,
        'keyword_score': 5,
        'subjects': ['Overweb planning call', 'Lunch tomorrow'],
        'snippets': ['Follow up on presence community'],
    }
    reasons = outreach_selection_reasons(row, min_meta_layer_messages=1)
    assert reasons['meta_layer_message_count'] == 2
    assert reasons['matched_via_message_count'] is True
    assert reasons['matched_via_topics'] is True
    assert reasons['message_count'] == 4
    assert reasons['keyword_score'] == 5
    assert 'overweb' in reasons['matched_terms']
    assert 'presence' in reasons['matched_terms']
    assert reasons['sample_subject_hits'] == ['Overweb planning call']


def test_outreach_selection_reasons_topic_only_without_message_count():
    row = {
        'email': 'partner@example.com',
        'message_count': 1,
        'meta_layer_message_count': 0,
        'keyword_score': 0,
        'subjects': ['Identity verification for civic trust'],
        'snippets': ['Misinformation working group notes'],
    }
    reasons = outreach_selection_reasons(row, min_meta_layer_messages=1)
    assert reasons['matched_via_message_count'] is False
    assert reasons['matched_via_topics'] is True
    assert 'identity' in reasons['matched_terms']
    assert 'verification' in reasons['matched_terms']
    assert 'misinformation' in reasons['matched_terms']
    assert reasons['sample_subject_hits'] == ['Identity verification for civic trust']


def test_filter_outreach_contacts_keeps_topic_match_without_message_count():
    contacts = [
        {
            'email': 'partner@example.com',
            'name': 'Partner',
            'message_count': 1,
            'meta_layer_message_count': 0,
            'subjects': ['Identity verification for civic trust'],
            'snippets': ['Misinformation working group notes'],
            'last_contact': '2026-01-01',
        },
        {
            'email': 'noreply@example.com',
            'name': 'No Reply',
            'message_count': 1,
            'meta_layer_message_count': 0,
            'subjects': ['Identity verification update'],
            'snippets': ['Automated notice'],
            'last_contact': '2026-01-01',
        },
        {
            'email': 'random@example.com',
            'name': 'Random',
            'message_count': 1,
            'meta_layer_message_count': 0,
            'subjects': ['Coffee next week'],
            'snippets': ['See you soon'],
            'last_contact': '2026-01-01',
        },
    ]
    filtered = filter_outreach_contacts(contacts)
    assert [row['email'] for row in filtered] == ['partner@example.com']


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


def test_owner_exclude_emails_includes_aliases():
    excluded = owner_exclude_emails('daveed@bridgit.io')
    assert 'daveed@bridgit.io' in excluded
    assert 'dave@bridgit.io' in excluded
    assert 'daveroom@gmail.com' in excluded


def test_aggregate_external_contacts_unlimited_by_default():
    messages = [
        {
            'subject': f'Meta-layer thread {index}',
            'summary': 'desirable properties',
            'received': f'2026-01-{index + 1:02d}',
            'keyword_hits': 2,
            'participants': [f'Person {index} <person{index}@example.com>'],
        }
        for index in range(50)
    ]
    contacts = aggregate_external_contacts(messages, owner_email='owner@example.com')
    assert len(contacts) == 50


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
