"""Canopi intake must keep patch_mode: an insert filed as replace would delete its anchor on promote."""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _run_intake(monkeypatch, patch_mode):
    from fixtures.isolated_app import isolated_app

    import services.canopi_contributions as cc
    import services.product_rollout as pr

    captured = {}
    sub = SimpleNamespace(id='sub-1', status='approved', layer_id=None, group='', title='DP15 - Security & Provenance')
    row = SimpleNamespace(id='prop-1', contribution_registry_id=None,
                          to_dict=lambda: {'id': 'prop-1'}, status_label=lambda: 'Open')

    def fake_create(submission, **kwargs):
        captured.update(kwargs)
        return row

    monkeypatch.setattr(cc, '_find_existing_canopi_patch', lambda ext: None)
    monkeypatch.setattr(cc, 'resolve_submission_for_proposals', lambda ref: (sub, None))
    monkeypatch.setattr(cc, 'resolve_canonical_submission', lambda s: s)
    monkeypatch.setattr(pr, 'is_feature_enabled', lambda name: True)
    monkeypatch.setattr(cc, '_resolve_author_user_id', lambda **kw: ('user-1', None))
    monkeypatch.setattr(cc, 'passage_exists_in_current_document', lambda s, text: True)
    monkeypatch.setattr(cc, 'validate_proposal_scope_for_submission', lambda s, scope: None)
    monkeypatch.setattr(cc, 'create_dp_proposal', fake_create)
    monkeypatch.setattr(cc, '_enqueue_patch_pipeline', lambda *a, **k: None)
    monkeypatch.setattr('services.events.emit_event', lambda *a, **k: None)
    monkeypatch.setattr(cc.db.session, 'flush', lambda: None)
    monkeypatch.setattr(cc.db.session, 'commit', lambda: None)

    with isolated_app() as ctx, ctx.app.app_context():
        payload = {'original_text': 'Anchor sentence.', 'proposed_text': 'New sentence.', 'scope': 'dp'}
        if patch_mode:
            payload['patch_mode'] = patch_mode
        resp, status = cc.intake_canopi_patch(
            draft_ref='ML-Draft-019', external_id='canopi-msg-1',
            author_user_id='user-1', author_email='a@example.org', payload=payload,
        )
    return resp, status, captured


def test_intake_passes_insert_patch_mode(monkeypatch):
    _, status, captured = _run_intake(monkeypatch, 'insert')
    assert status == 201
    assert captured['patch_mode'] == 'insert'
    assert captured['source_channel'] == 'canopi'


def test_intake_defaults_to_replace(monkeypatch):
    _, status, captured = _run_intake(monkeypatch, None)
    assert status == 201
    assert captured['patch_mode'] == 'replace'
