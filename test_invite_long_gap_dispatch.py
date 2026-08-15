"""Long-gap dispatch classify/draft pipeline helpers."""
import json
from pathlib import Path
from uuid import uuid4

import pytest

from services.dp_admin_invite_store import set_selected_invite_emails
from services.invite_long_gap_dispatch import (
    _CLASSIFICATION_ERROR_MESSAGE,
    _CLASSIFICATION_UNAVAILABLE,
    _FALLBACK_DP_CATALOG,
    _HEURISTIC_CLASSIFY_MARKER,
    _classification_error_result,
    _collect_draft_targets,
    _first_name_for_row,
    _heuristic_classify_contact,
    _parse_classify_response,
    _workgroup_dp_draft_guidance,
    build_long_gap_contact_list,
    get_long_gap_dispatch_cutoff,
    intern_alum_heuristic,
    is_long_gap_last_contact,
    long_gap_dispatch_use_llm,
    merge_classify_result_into_row,
    parse_classify_result_item,
    render_long_gap_template_email,
)
from services.zoho_mail import admin_snapshot_key


def _unique(prefix: str) -> str:
    return f'{prefix}-{uuid4().hex[:8]}'


def test_is_long_gap_last_contact():
    cutoff = get_long_gap_dispatch_cutoff()
    assert cutoff.isoformat() == '2025-01-01'
    assert is_long_gap_last_contact('2024-12-31') is True
    assert is_long_gap_last_contact('2025-01-01') is False
    assert is_long_gap_last_contact('') is True


def test_intern_alum_heuristic():
    assert intern_alum_heuristic(
        snippets=['Thanks for the Bridgit intern program'],
        subjects=['Presence intern wrap-up'],
    ) == (True, 'intern keyword with Bridgit/Presence context')
    assert intern_alum_heuristic(subjects=['weekly newsletter']) == (False, '')
    hit, note = intern_alum_heuristic(matched_terms=['presence', 'ved'])
    assert hit is True
    assert 'presence' in note


def test_parse_classify_result_item():
    catalog = list(_FALLBACK_DP_CATALOG)
    parsed = parse_classify_result_item(
        {
            'email': 'Kevin@Example.com',
            'dp_slug': 'dp15',
            'confidence': 'high',
            'skip': False,
            'intern_alum': False,
            'why': 'Security thread history',
        },
        catalog,
    )
    assert parsed['email'] == 'kevin@example.com'
    assert parsed['dp_suggestion'] == 'dp15-security-provenance'
    assert parsed['confidence'] == 'high'
    assert parsed['why'] == 'Security thread history'


def test_merge_classify_result_preserves_intern_override():
    row = {
        'email': 'user@example.com',
        'intern_alum': False,
        'intern_alum_overridden': True,
        'intern_notes': '',
        'matched_terms': ['presence', 'ved'],
    }
    result = {
        'intern_alum': True,
        'intern_notes': 'LLM says intern',
        'classification_status': 'done',
    }
    contact = {
        'snippets': ['Bridgit intern program'],
        'sample_subjects': ['Presence intern wrap-up'],
    }
    merge_classify_result_into_row(row, result, contact)
    assert row['intern_alum'] is False
    assert row['intern_notes'] == ''
    assert row['classification_status'] == 'done'


def test_merge_classify_result_preserves_dp_skip_and_approved():
    row = {
        'email': 'user@example.com',
        'approved': True,
        'dp_suggestion': None,
        'dp_label': '',
        'confidence': 'high',
        'dp_overridden': True,
        'skip': True,
        'skip_reason': 'vendor',
        'skip_overridden': True,
        'intern_alum_overridden': False,
        'matched_terms': [],
    }
    result = {
        'approved': False,
        'dp_suggestion': 'dp15-security-provenance',
        'dp_label': 'Security',
        'confidence': 'low',
        'skip': False,
        'skip_reason': '',
        'classification_status': 'done',
        'why': 'heuristic',
    }
    contact = {'sample_subjects': ['hello']}
    merge_classify_result_into_row(row, result, contact)
    assert row['approved'] is True
    assert row['dp_suggestion'] is None
    assert row['dp_label'] == ''
    assert row['confidence'] == 'high'
    assert row['skip'] is True
    assert row['skip_reason'] == 'vendor'
    assert row['classification_status'] == 'done'


def test_merge_classify_result_applies_heuristic_without_override():
    row = {
        'email': 'user@example.com',
        'intern_alum': False,
        'intern_alum_overridden': False,
        'intern_notes': '',
        'matched_terms': [],
    }
    result = {
        'intern_alum': False,
        'intern_notes': '',
        'classification_status': 'done',
    }
    contact = {
        'snippets': ['Thanks for the Bridgit intern program'],
        'sample_subjects': ['Presence intern wrap-up'],
    }
    merge_classify_result_into_row(row, result, contact)
    assert row['intern_alum'] is True
    assert 'Bridgit' in row['intern_notes'] or 'intern' in row['intern_notes'].lower()


def test_parse_classify_response_valid_json():
    catalog = list(_FALLBACK_DP_CATALOG)
    by_id = {entry['id']: entry for entry in catalog}
    by_slug = {(entry.get('slug') or '').lower(): entry for entry in catalog if entry.get('slug')}
    raw = json.dumps({
        'results': [{
            'email': 'user@example.com',
            'dp_slug': 'dp15',
            'confidence': 'high',
            'skip': False,
            'why': 'Security background',
        }],
    })
    parsed = _parse_classify_response(raw, by_id, by_slug)
    assert 'user@example.com' in parsed
    assert parsed['user@example.com']['dp_suggestion'] == 'dp15-security-provenance'
    assert parsed['user@example.com']['classification_status'] == 'done'


def test_parse_classify_response_rejects_empty():
    catalog = list(_FALLBACK_DP_CATALOG)
    by_id = {entry['id']: entry for entry in catalog}
    by_slug = {}
    with pytest.raises(ValueError, match='empty'):
        _parse_classify_response('', by_id, by_slug)


def test_classification_error_result_defaults():
    result = _classification_error_result()
    assert result['skip'] is False
    assert result['dp_suggestion'] is None
    assert result['why'] == _CLASSIFICATION_UNAVAILABLE
    assert result['classification_status'] == 'error'
    assert result['classification_error'] == _CLASSIFICATION_ERROR_MESSAGE


def test_merge_classify_error_result_applies_heuristic():
    row = {
        'email': 'user@example.com',
        'intern_alum': False,
        'intern_alum_overridden': False,
        'intern_notes': '',
        'matched_terms': [],
    }
    contact = {
        'snippets': ['Thanks for the Bridgit intern program'],
        'sample_subjects': ['Presence intern wrap-up'],
    }
    merge_classify_result_into_row(row, _classification_error_result(), contact)
    assert row['classification_status'] == 'error'
    assert row['why'] == _CLASSIFICATION_UNAVAILABLE
    assert row['intern_alum'] is True


def test_heuristic_classify_contact_without_llm():
    catalog = list(_FALLBACK_DP_CATALOG)
    by_id = {entry['id']: entry for entry in catalog}
    by_slug = {(entry.get('slug') or '').lower(): entry for entry in catalog if entry.get('slug')}
    contact = {
        'email': 'user@example.com',
        'sample_subjects': ['Meta-Layer workshop follow-up'],
        'snippets': ['Thanks for the Bridgit intern program'],
        'matched_terms': ['meta-layer'],
    }
    result = _heuristic_classify_contact(contact, by_id, by_slug)
    assert result['classification_status'] == 'done'
    assert result['classification_error'] == ''
    assert result['classification_source'] == _HEURISTIC_CLASSIFY_MARKER
    assert result['intern_alum'] is True
    assert 'Meta-Layer' in result['why'] or 'meta-layer' in result['why'].lower()


def test_merge_classify_resets_stale_draft_error():
    row = {
        'email': 'user@example.com',
        'draft_status': 'error',
        'draft_error': 'dp_suggestion required',
        'draft_body': '',
        'intern_alum_overridden': False,
        'matched_terms': [],
    }
    result = {
        'classification_status': 'done',
        'classification_error': '',
        'why': 'test',
    }
    contact = {'sample_subjects': ['hello']}
    merge_classify_result_into_row(row, result, contact)
    assert row['draft_status'] == 'pending'
    assert row['draft_error'] == ''


def test_build_long_gap_contact_list_intersects_selection(tmp_path, monkeypatch):
    admin_email = f'daveed-{_unique("lg")}@example.com'
    admin_key = admin_snapshot_key(admin_email)
    snapshots_dir = tmp_path / 'invite_zoho_snapshots'
    snapshots_dir.mkdir()
    selected_dir = tmp_path / 'invite_zoho_selected'
    selected_dir.mkdir()

    contacts = [
        {
            'email': 'old@example.com',
            'name': 'Old Contact',
            'last_contact': '2023-01-01',
            'message_count': 2,
            'subjects': ['meta-layer workshop'],
        },
        {
            'email': 'recent@example.com',
            'name': 'Recent Contact',
            'last_contact': '2025-01-01',
            'message_count': 1,
            'subjects': ['follow up'],
        },
        {
            'email': 'unselected@example.com',
            'name': 'Unselected',
            'last_contact': '2020-01-01',
            'message_count': 1,
        },
    ]
    (snapshots_dir / f'{admin_key}.json').write_text(
        json.dumps({'owner_email': admin_email, 'contacts': contacts}),
        encoding='utf-8',
    )
    (selected_dir / f'{admin_key}.json').write_text(
        json.dumps({'selected_emails': ['old@example.com', 'recent@example.com']}),
        encoding='utf-8',
    )

    monkeypatch.setattr('services.dp_admin_invite_store.INSTANCE_DIR', str(tmp_path))
    monkeypatch.setattr('services.zoho_mail.INSTANCE_DIR', str(tmp_path))

    admin = {'id': 'admin-1', 'email': admin_email}
    set_selected_invite_emails(admin, ['old@example.com', 'recent@example.com'])
    rows = build_long_gap_contact_list(admin)
    emails = sorted(row['email'] for row in rows)
    assert emails == ['old@example.com']
    assert get_long_gap_dispatch_cutoff().isoformat() == '2025-01-01'


def test_collect_draft_targets_skips_done_and_non_approved():
    rows = {
        'done@example.com': {
            'email': 'done@example.com',
            'approved': True,
            'skip': False,
            'draft_status': 'done',
            'draft_body': 'hello',
        },
        'pending@example.com': {
            'email': 'pending@example.com',
            'approved': True,
            'skip': False,
            'draft_status': 'pending',
        },
        'notapproved@example.com': {
            'email': 'notapproved@example.com',
            'approved': False,
            'draft_status': 'pending',
        },
        'skipped@example.com': {
            'email': 'skipped@example.com',
            'approved': True,
            'skip': True,
            'draft_status': 'pending',
        },
    }
    targets, skip_patches = _collect_draft_targets(rows)
    assert len(targets) == 1
    assert targets[0]['email'] == 'pending@example.com'
    assert len(skip_patches) == 1
    assert skip_patches[0][0] == 'skipped@example.com'


def test_collect_draft_targets_force_regenerates_done():
    rows = {
        'done@example.com': {
            'email': 'done@example.com',
            'approved': True,
            'skip': False,
            'draft_status': 'done',
            'draft_body': 'stale generic draft',
        },
    }
    targets, skip_patches = _collect_draft_targets(
        rows,
        emails=['done@example.com'],
        force=True,
    )
    assert len(targets) == 1
    assert targets[0]['draft_body'] == ''
    assert targets[0]['draft_status'] == 'pending'
    assert skip_patches == []


def test_workgroup_dp_draft_guidance_names_workgroup():
    row = {
        'dp_label': 'DP6 - Commerce',
        'sample_subjects': ['Re: Bridgit advisor call'],
        'snippets': ['Hey brotha, traveling tomorrow'],
    }
    contact = {'sample_subjects': ['Re: Catching up']}
    catalog_entry = {
        'id': 'wg-commerce',
        'name': 'DP6 - Commerce',
        'description': 'Commerce patterns on the layered web.',
    }
    guidance = _workgroup_dp_draft_guidance(row, catalog_entry, contact)
    assert 'DP6' in guidance
    assert 'Commerce' in guidance
    assert 'Bridgit advisor call' in guidance
    assert 'MUST explicitly invite' in guidance


def test_long_gap_dispatch_use_llm_defaults_false(monkeypatch):
    monkeypatch.delenv('LONG_GAP_DISPATCH_USE_LLM', raising=False)
    assert long_gap_dispatch_use_llm() is False
    monkeypatch.setenv('LONG_GAP_DISPATCH_USE_LLM', 'true')
    assert long_gap_dispatch_use_llm() is True


def test_first_name_from_contact_name():
    row = {'email': 'kevin@example.com', 'name': 'Kevin Example'}
    contact = {'email': 'kevin@example.com', 'name': 'Kevin Example'}
    assert _first_name_for_row(row, contact) == 'Kevin'


def test_first_name_from_email_local_part():
    row = {'email': 'jane.doe@example.com', 'name': 'jane.doe@example.com'}
    contact = {'email': 'jane.doe@example.com'}
    assert _first_name_for_row(row, contact) == 'jane'


def test_first_name_strips_wrapping_quotes():
    row = {'email': 'agustinborra@gmail.com', 'name': '"Agustín Borrazás"'}
    contact = {'email': 'agustinborra@gmail.com', 'name': '"Agustín Borrazás"'}
    assert _first_name_for_row(row, contact) == 'Agustín'


def test_render_long_gap_template_sanitizes_quoted_name():
    row = {
        'email': 'agustinborra@gmail.com',
        'name': '"Agustín Borrazás"',
        'dp_suggestion': None,
        'dp_label': '',
    }
    contact = {'email': 'agustinborra@gmail.com', 'name': '"Agustín Borrazás"'}
    body = render_long_gap_template_email(row, contact)
    assert body.startswith('Hi Agustín,')
    assert 'Hi "Agustín' not in body


def test_render_long_gap_template_without_dp():
    row = {
        'email': 'user@example.com',
        'name': 'Alex Smith',
        'dp_suggestion': None,
        'dp_label': '',
    }
    contact = {'email': 'user@example.com', 'name': 'Alex Smith'}
    body = render_long_gap_template_email(row, contact)
    assert body.startswith('Hi Alex,')
    assert "It's been a long time" in body
    assert 'Metaweb book was published in late 2023' in body
    assert 'solid version' in body
    assert '0.77' not in body
    assert 'community AI assistant' in body
    assert (
        'As someone with an early view into the meta-layer conversation, we would love your input.'
        in body
    )
    assert 'who was early in the meta-layer conversation' not in body
    assert 'we would need your input' not in body
    assert 'contribute as an individual' in body
    assert 'https://desirableproperties.org to participate' in body
    assert 'Looking forward to hearing from you' not in body
    assert 'few months since we last connected' not in body
    assert 'Warmly,\nDaveed Benjamin' in body
    assert 'Hermes' not in body
    assert 'would love to invite you to join' not in body
    assert '\u2014' not in body


def test_render_long_gap_template_with_dp():
    catalog_entry = {
        'id': 'dp15-security-provenance',
        'slug': 'dp15',
        'name': 'DP15 - Security and Provenance',
        'description': 'Security, provenance, trust, and verification on the layered web.',
    }
    row = {
        'email': 'user@example.com',
        'name': 'Alex Smith',
        'dp_suggestion': 'dp15-security-provenance',
        'dp_label': 'DP15 - Security and Provenance',
    }
    contact = {'email': 'user@example.com', 'name': 'Alex Smith'}
    body = render_long_gap_template_email(row, contact, catalog_entry=catalog_entry)
    assert 'DP15 - Security and Provenance' in body
    assert 'would love your input on DP15 - Security and Provenance' in body
    assert 'workgroup focused on Security, provenance, trust, and verification on the layered web.' in body
    assert 'Take a look here:' in body
    assert '/workgroups/dp15' in body
    assert 'Your perspective would be a genuine asset to this group.' not in body
    assert 'Looking forward to hearing from you' not in body
    assert "It's been a long time" in body
    assert '\u2014' not in body


def test_draft_one_row_template_skips_llm(monkeypatch):
    from services.invite_long_gap_dispatch import _draft_one_row

    monkeypatch.delenv('LONG_GAP_DISPATCH_USE_LLM', raising=False)

    def fail_llm(*_args, **_kwargs):
        raise AssertionError('call_llm should not run in template mode')

    monkeypatch.setattr('services.invite_long_gap_dispatch.call_llm', fail_llm)
    monkeypatch.setattr(
        'services.invite_long_gap_dispatch.draft_admin_invitation_email',
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('draft_admin_invitation_email')),
    )
    monkeypatch.setattr(
        'services.invite_long_gap_dispatch._dispatch_catalog',
        lambda: list(_FALLBACK_DP_CATALOG),
    )

    admin = {'id': 'admin-1', 'email': 'admin@example.com'}
    row = {
        'email': 'user@example.com',
        'name': 'Alex Smith',
        'dp_suggestion': None,
        'dp_label': '',
    }
    contact = {'email': 'user@example.com', 'name': 'Alex Smith'}
    email, body, err = _draft_one_row(admin, row, contact)
    assert email == 'user@example.com'
    assert err is None
    assert body and body.startswith('Hi Alex,')


def test_send_long_gap_dispatch_email_test_mode_skips_invite_flow(monkeypatch):
    """Test sends must not run membership checks or create platform invitations."""
    from fixtures.isolated_app import isolated_app, make_user
    from extensions import db
    from services.invite_long_gap_dispatch import send_long_gap_dispatch_email

    source_email = 'agustinborra@gmail.com'
    draft_body = 'Hi Agustin,\n\nDraft preview body for DP22.'

    def fake_build_contacts(_admin):
        return [{'email': source_email, 'name': 'Agustin Borrazas'}]

    def fake_get_rows(owner):
        return {
            'rows': {
                source_email: {
                    'email': source_email,
                    'name': 'Agustin Borrazas',
                    'approved': True,
                    'skip': False,
                    'draft_body': draft_body,
                    'dp_suggestion': '615ec91b-62e1-4bf6-90a5-e8f5082e4d7e',
                    'dp_label': 'DP22 - Civic Memory & Epistemic Continuity',
                },
            },
        }

    invite_called = False

    def fail_invite(**_kwargs):
        nonlocal invite_called
        invite_called = True
        return {'blocked': True, 'error': 'should not run'}, 400

    plain_args = {}

    def fake_plain(inviter, to_email, to_name, body, **kwargs):
        plain_args['inviter'] = inviter
        plain_args['to_email'] = to_email
        plain_args['to_name'] = to_name
        plain_args['body'] = body
        plain_args['dp_card_image_url'] = kwargs.get('dp_card_image_url')
        return True

    record_args = {}

    def fake_record(**kwargs):
        record_args.update(kwargs)
        return type('Row', (), {'id': 'send-1'})()

    with isolated_app() as ctx:
        with ctx.app.app_context():
            inviter = make_user(
                username='daveed-test',
                email='daveed@bridgit.io',
                role='admin',
                display_name='Daveed Benjamin',
            )
            db.session.commit()
            admin = {'id': inviter.id, 'email': 'daveed@bridgit.io', 'role': 'admin'}

            monkeypatch.setattr(
                'services.invite_long_gap_dispatch.is_dp_site_admin',
                lambda _admin: True,
            )
            monkeypatch.setattr(
                'services.invite_long_gap_dispatch.build_long_gap_contact_list',
                fake_build_contacts,
            )
            monkeypatch.setattr(
                'services.invite_long_gap_dispatch.get_long_gap_dispatch_rows',
                fake_get_rows,
            )
            monkeypatch.setattr(
                'services.workgroup_invite_ai.send_admin_invitation_email',
                fail_invite,
            )
            monkeypatch.setattr(
                'services.invite_long_gap_dispatch._send_long_gap_plain_email',
                fake_plain,
            )
            monkeypatch.setattr(
                'services.dp_admin_invite_store.record_admin_invite_send',
                fake_record,
            )

            payload, status = send_long_gap_dispatch_email(
                admin,
                email=source_email,
                test_mode=True,
                test_recipient_email='daveed@bridgit.io',
            )

    assert status == 200
    assert payload['success'] is True
    assert payload['test_mode'] is True
    assert payload['test_for_email'] == source_email
    assert payload['delivered_to'] == 'daveed@bridgit.io'
    assert invite_called is False
    assert plain_args['to_email'] == 'daveed@bridgit.io'
    assert plain_args['to_name'] == 'Agustin Borrazas'
    assert plain_args['body'] == draft_body
    assert record_args['recipient_name'] == 'Agustin Borrazas'
    assert record_args['source'] == 'long_gap_dispatch|test'
    assert record_args['workgroup_ids'] == []
