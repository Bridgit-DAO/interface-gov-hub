"""Tests for DP Proposal scaffolding (API + permissions)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _auth_client(app, username):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user'] = username
    return client


def _enable_dp_proposals(app):
    from extensions import db
    from models import SiteConfig
    from services.product_rollout import PRODUCT_ROLLOUT_SITE_CONFIG_KEY

    with app.app_context():
        row = SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).first()
        cfg = {}
        if row and row.value:
            cfg = json.loads(row.value)
        cfg['patches'] = True
        payload = json.dumps(cfg, sort_keys=True)
        if row:
            row.value = payload
        else:
            db.session.add(SiteConfig(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY, value=payload))
        db.session.commit()


def _find_approved_non_dp_submission():
    from models import Submission
    from services.dp_proposals import is_dp_submission

    for sub in Submission.query.filter_by(status='approved', doc_type='draft').all():
        if not is_dp_submission(sub):
            return sub
    return None


def _find_approved_dp_submission():
    from models import Submission
    from services.dp_proposals import is_dp_submission

    for sub in Submission.query.filter_by(status='approved', doc_type='draft').all():
        if is_dp_submission(sub):
            return sub
    return None


def _sample_passage_from_submission(sub):
    from services.dp_proposals import load_submission_plain_document_text
    import re

    body = load_submission_plain_document_text(sub)
    if not body:
        return None
    for sentence in re.split(r'(?<=[.!?])\s+', body):
        sentence = sentence.strip()
        if len(sentence.split()) >= 6:
            return sentence
    return body[:120].strip() if body else None


def test_classify_bogus_proposal_not_in_document():
    from app import app
    from models import DpProposal
    from services.dp_proposals import classify_proposal_location

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        proposal = DpProposal(
            submission_id=sub.id,
            scope='dp',
            status='pending',
            anchor_hash='deadbeef',
            original_text='The quick brown fox jumps over the lazy dog.',
            proposed_text='The quick brown fox jumps over the lazy dog. Revised.',
            content_hash_at_create=sub.content_hash,
        )
        assert classify_proposal_location(proposal, sub) == 'bogus'


def test_reconcile_dp_proposal_locations_deletes_bogus():
    from app import app
    from extensions import db
    from models import DpProposal, User
    from services.dp_proposals import classify_proposal_location, reconcile_dp_proposal_locations

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        user = User.query.first()
        if not user:
            return
        bogus = DpProposal(
            submission_id=sub.id,
            scope='dp',
            status='pending',
            anchor_hash='bogus-anchor-hash',
            original_text='Alpha sentence one.',
            proposed_text='Alpha sentence one. Revised.',
            content_hash_at_create=sub.content_hash,
            author_user_id=user.id,
        )
        db.session.add(bogus)
        db.session.commit()
        bogus_id = bogus.id
        assert classify_proposal_location(bogus, sub) == 'bogus'
        stats = reconcile_dp_proposal_locations()
        assert bogus_id in stats['deleted_ids']
        assert DpProposal.query.get(bogus_id) is None


def test_compute_anchor_hash_stable():
    from services.dp_proposals import compute_anchor_hash

    h1 = compute_anchor_hash('sub-1', 'abc', 'Hello world.')
    h2 = compute_anchor_hash('sub-1', 'abc', 'Hello world.')
    h3 = compute_anchor_hash('sub-1', 'abc', 'Different.')
    assert h1 == h2
    assert h1 != h3


def test_focused_passage_core_trims_unchanged_sentences():
    from services.dp_proposals import focused_passage_core

    original = (
        'This draft articulates DP11. '
        'The central claim is ethical AI at the interface. '
        'In such conditions, trust collapses.'
    )
    proposed = (
        'This draft articulates DP11. '
        'The central claim is ethical AI at the interface. '
        'In such conditions, trust collapses and semantic chaos ensues.'
    )
    o, p = focused_passage_core(original, proposed)
    assert o == 'In such conditions, trust collapses.'
    assert p == 'In such conditions, trust collapses and semantic chaos ensues.'


def test_retrim_stored_proposal_backfill():
    from app import app
    from extensions import db
    from models import DpProposal, Submission, User
    from services.dp_proposals import (
        compute_anchor_hash,
        retrim_all_dp_proposals,
        retrim_stored_proposal,
        serialize_context_anchor,
    )

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        user = User.query.first()
        if not user:
            return

        original = 'Lead sentence. Changed sentence here.'
        proposed = 'Lead sentence. Changed sentence there.'
        row = DpProposal(
            submission_id=sub.id,
            scope='dp',
            status='pending',
            anchor_hash=compute_anchor_hash(sub.id, sub.content_hash, original),
            context_anchor=serialize_context_anchor({
                'textQuote': {'type': 'TextQuoteSelector', 'exact': original},
            }),
            original_text=original,
            proposed_text=proposed,
            content_hash_at_create=sub.content_hash,
            author_user_id=user.id,
        )
        db.session.add(row)
        db.session.commit()
        pid = row.id

        changed, err = retrim_stored_proposal(row)
        assert err is None
        assert changed is True
        assert row.original_text == 'Changed sentence here.'
        assert row.proposed_text == 'Changed sentence there.'
        db.session.commit()

        row2 = DpProposal.query.get(pid)
        assert row2.original_text == 'Changed sentence here.'
        db.session.delete(row2)
        db.session.commit()


def test_validate_create_payload_trims_and_aligns_anchor():
    from services.dp_proposals import validate_create_payload

    payload, err = validate_create_payload({
        'original_text': 'Alpha one. Beta two. Gamma three.',
        'proposed_text': 'Alpha one. Beta two. Gamma changed.',
        'context_anchor': {
            'textQuote': {
                'type': 'TextQuoteSelector',
                'exact': 'Alpha one. Beta two. Gamma three.',
                'prefix': '…',
                'suffix': '…',
            },
        },
    })
    assert err is None
    assert payload['original_text'] == 'Gamma three.'
    assert payload['proposed_text'] == 'Gamma changed.'
    assert payload['context_anchor']['textQuote']['exact'] == 'Gamma three.'


def test_list_proposals_requires_feature():
    from app import app

    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        ref = sub.id

    with app.test_client() as client:
        r = client.get(f'/api/doc/draft/{ref}/proposals/')
        if r.status_code == 403:
            return
        assert r.status_code in (200, 403)


def test_create_and_list_proposal():
    from app import app
    from extensions import db
    from models import User

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        user = User.query.first()
        if not user:
            return
        ref = sub.id
        username = user.username
        passage = _sample_passage_from_submission(sub)
        if not passage:
            return

    client = _auth_client(app, username)
    r = client.post(
        f'/api/doc/draft/{ref}/proposals/',
        json={
            'original_text': passage,
            'proposed_text': passage + ' Revised.',
            'context_anchor': {'textQuote': {'exact': passage}},
        },
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    data = r.get_json()
    assert data['proposal']['status'] == 'pending'
    assert data['status_label'] == 'Patch'

    r2 = client.get(f'/api/doc/draft/{ref}/proposals/')
    assert r2.status_code == 200
    listed = r2.get_json()
    assert listed['count'] >= 1
    assert listed['counts_by_status'].get('pending', 0) >= 1


def test_create_proposal_with_rationale_and_reference():
    from app import app
    from models import User

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        user = User.query.first()
        if not user:
            return
        ref = sub.id
        username = user.username
        passage = _sample_passage_from_submission(sub)
        if not passage:
            return

    client = _auth_client(app, username)
    r = client.post(
        f'/api/doc/draft/{ref}/proposals/',
        json={
            'original_text': passage,
            'proposed_text': passage + ' Revised.',
            'context_anchor': {'textQuote': {'exact': passage}},
            'rationale': 'Clearer wording for readers.',
            'reference_url': 'https://example.com/rfc',
        },
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    prop = r.get_json()['proposal']
    assert prop['rationale'] == 'Clearer wording for readers.'
    assert prop['reference_url'] == 'https://example.com/rfc'




def test_assist_context_lists_comment_and_patch_actions():
    from services.assist import get_available_actions

    comment_actions = [a['id'] for a in get_available_actions('comment')]
    patch_actions = [a['id'] for a in get_available_actions('patch')]

    assert 'draft_comment' in comment_actions
    assert 'improve_patch' not in comment_actions
    assert 'improve_patch' in patch_actions
    assert 'draft_comment' not in patch_actions


def test_assist_context_endpoint_for_patch():
    from app import app
    from models import User

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        user = User.query.first()
        if not user:
            return
        ref = sub.id
        username = user.username
        passage = _sample_passage_from_submission(sub)
        if not passage:
            return

    client = _auth_client(app, username)
    r = client.post(
        f'/api/doc/draft/{ref}/assist/context/',
        json={
            'mode': 'patch',
            'selected_passage': passage,
            'proposed_text': passage + ' Revised.',
            'rationale': 'Clearer wording.',
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data['context']['mode'] == 'patch'
    assert data['context']['selected_passage']
    assert any(a['id'] == 'improve_patch' for a in data['actions'])


def test_assist_generate_uses_monkeypatched_llm(monkeypatch):
    from services import assist

    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')
    monkeypatch.setattr(assist, 'call_llm', lambda messages, cfg: 'Improved draft.')

    result = assist.generate_draft(
        'improve_comment',
        {
            'mode': 'comment',
            'submission': {'title': 'Draft title', 'draft_ref': 'draft-1'},
            'document': {'body': 'Document text.'},
            'user_draft': 'rough draft',
            'sources': {},
        },
        user_prompt=None,
        user_id='u1',
    )

    assert result['draft'] == 'Improved draft.'
    assert result['ai_assisted'] is True
    assert result['provider'] == 'openai'


def test_reference_url_rejects_non_http():
    from services.dp_proposals import validate_reference_url

    url, err = validate_reference_url('javascript:alert(1)')
    assert url is None
    assert err


def test_accept_proposal_requires_site_admin():
    from app import app
    from models import User

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        outsider = User.query.filter(User.role == 'user').first()
        if not outsider:
            return
        ref = sub.id
        outsider_name = outsider.username
        passage = _sample_passage_from_submission(sub)
        if not passage:
            return

    client = _auth_client(app, outsider_name)
    create = client.post(
        f'/api/doc/draft/{ref}/proposals/',
        json={
            'original_text': passage,
            'proposed_text': passage + ' Revised.',
        },
    )
    if create.status_code != 201:
        return
    pid = create.get_json()['proposal']['id']

    deny = client.post(f'/api/doc/draft/{ref}/proposals/{pid}/accept/')
    assert deny.status_code == 403


def test_read_meta_for_dp():
    from app import app

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        ref = sub.id

    with app.test_client() as client:
        r = client.get(f'/api/doc/draft/{ref}/read-meta/')
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert data['is_dp'] is True
        assert data['proposals_enabled'] is True


def test_dp_challenge_page_loads():
    from app import app

    _enable_dp_proposals(app)
    with app.test_client() as client:
        r = client.get('/dp-challenge/')
        assert r.status_code == 200, r.get_data(as_text=True)
        assert b'DP Challenge' in r.data
        assert b'Your line can become the standard' in r.data
        assert b'Contributors' in r.data


def test_dp_challenge_recent_api():
    from app import app
    from extensions import db
    from models import DpProposal, Submission, User

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        user = User.query.first()
        if not user:
            return
        from services.dp_proposals import compute_anchor_hash

        original = 'One.'
        row = DpProposal(
            submission_id=sub.id,
            scope='dp',
            status='pending',
            anchor_hash=compute_anchor_hash(sub.id, sub.content_hash, original),
            original_text=original,
            proposed_text='Two.',
            author_user_id=user.id,
        )
        db.session.add(row)
        db.session.commit()

    with app.test_client() as client:
        r = client.get('/api/dp-challenge/recent')
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('enabled') is True
        assert isinstance(data.get('events'), list)


def test_admin_dashboard_loads():
    from app import app
    from models import User

    _enable_dp_proposals(app)
    with app.app_context():
        admin = User.query.filter(User.role.in_(['admin', 'editor'])).first()
        if not admin:
            return
        username = admin.username

    client = _auth_client(app, username)
    r = client.get('/admin/dp-proposals/')
    assert r.status_code == 200
    assert b'Patches' in r.data


def test_patches_page_loads():
    from app import app

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        ref = sub.id

    with app.test_client() as client:
        r = client.get(f'/doc/draft/{ref}/patches/')
        assert r.status_code == 200, r.get_data(as_text=True)
        assert b'Patches' in r.data
        assert b'passage-level only' in r.data
        assert b'document-wide patches' in r.data


def test_suggest_edit_page_loads():
    from app import app

    _enable_dp_proposals(app)
    with app.test_client() as client:
        r = client.get('/suggest-edit/')
        assert r.status_code == 200, r.get_data(as_text=True)
        assert b'Propose a Patch' in r.data
        assert b'Help refine living documents' in r.data


def test_patch_diff_endpoint():
    from app import app
    from extensions import db
    from models import DpProposal, User

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_dp_submission()
        if not sub:
            return
        user = User.query.first()
        if not user:
            return

        original = 'the quick fox'
        proposed = 'the slow fox'
        row = DpProposal(
            submission_id=sub.id,
            scope='dp',
            status='pending',
            anchor_hash='test-diff-anchor-hash',
            original_text=original,
            proposed_text=proposed,
            content_hash_at_create=sub.content_hash,
            author_user_id=user.id,
        )
        db.session.add(row)
        db.session.commit()
        patch_id = row.id

    with app.test_client() as client:
        r = client.get(f'/api/doc/patch/{patch_id}/diff/')
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert '<del class="dp-diff-del">quick</del>' in data['html']
        assert '<mark class="dp-diff-ins">slow</mark>' in data['html']
        assert data['added'] == 4
        assert data['removed'] == 5

    with app.app_context():
        db.session.delete(DpProposal.query.get(patch_id))
        db.session.commit()


def test_patch_diff_endpoint_missing_patch():
    from app import app

    with app.test_client() as client:
        r = client.get('/api/doc/patch/does-not-exist/diff/')
        assert r.status_code == 404


def test_read_meta_for_non_dp():
    from app import app

    _enable_dp_proposals(app)
    with app.app_context():
        sub = _find_approved_non_dp_submission()
        if not sub:
            return
        ref = sub.id

    with app.test_client() as client:
        r = client.get(f'/api/doc/draft/{ref}/read-meta/')
        assert r.status_code == 200, r.get_data(as_text=True)
        data = r.get_json()
        assert data['is_dp'] is False
        assert data['mode'] == 'document'
        assert data['proposals_enabled'] is True
        assert data['labels']['pending_status'] == 'Patch'

