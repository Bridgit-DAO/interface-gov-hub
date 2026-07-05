#!/usr/bin/env python3
"""Smoke tests for knowledge layer + collections scaffolding."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_knowledge_schema_endpoint():
    from app import app

    with app.test_client() as c:
        r = c.get('/api/knowledge-layer/schema/')
        assert r.status_code == 200, r.data
        d = r.get_json()
        assert 'feature_flags' in d
        assert 'artifact_types' in d
        assert 'proposal' in d['artifact_types']
        assert d['artifact_types']['proposal']['default'] == 'decision'
        assert 'pattern' in d['knowledge_forms']
        assert 'opus' in d['knowledge_forms']
        assert d['knowledge_form_core_questions'].get('pattern')
        assert 'research' in d['scaffold_status_enums']


def test_validate_knowledge_for_create():
    from app import app
    from services.knowledge_layer import validate_knowledge_for_create

    cfg = app.config
    form, sc, err = validate_knowledge_for_create(
        'proposal', 'decision', None, cfg
    )
    assert not err and form == 'decision' and sc is None

    form_r, _, err = validate_knowledge_for_create(
        'proposal', 'research', None, cfg
    )
    assert not err and form_r == 'research'

    _, _, err = validate_knowledge_for_create(
        'proposal', 'not_a_real_form', None, cfg
    )
    assert err, 'invalid knowledge_form must be rejected'

    scfg = {
        'KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED': True,
        'KNOWLEDGE_SCAFFOLD_ENABLED': True,
    }
    form, sc, err = validate_knowledge_for_create(
        'document', 'pattern', {'recurring_tension': 'x'}, scfg
    )
    assert not err and form == 'pattern' and sc == {'recurring_tension': 'x'}

    _, _, err = validate_knowledge_for_create(
        'document', 'research', {'status': 'not_a_status'}, scfg
    )
    assert err, 'invalid research.status must be rejected'


def test_apply_knowledge_patch_clears_scaffold_when_form_cleared():
    from app import app
    from extensions import db
    from models import Artifact, Layer

    with app.app_context():
        layer = Layer.query.first()
        if not layer:
            print('⚠️  No layer – skip patch test')
            return
        art = Artifact(
            layer_id=layer.id,
            artifact_type='proposal',
            title='KL test',
            status='draft',
            knowledge_form='decision',
            knowledge_scaffold={'what_resolves': 'x'},
        )
        db.session.add(art)
        db.session.commit()
        aid = art.id

    with app.test_client() as c:
        # Login may be required – skip if 401
        r = c.patch(
            f'/api/artifacts/{aid}/',
            json={'knowledge_form': None},
            headers={'Content-Type': 'application/json'},
        )
        if r.status_code in (401, 302):
            print('⚠️  PATCH requires auth – skip')
            with app.app_context():
                db.session.delete(Artifact.query.get(aid))
                db.session.commit()
            return
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body['artifact'].get('knowledge_form') is None
        assert body['artifact'].get('knowledge_scaffold') is None

    with app.app_context():
        db.session.delete(Artifact.query.get(aid))
        db.session.commit()


def test_contribution_type_filter_analytics():
    from app import app
    from models import Layer

    with app.app_context():
        layer = Layer.query.first()
        if not layer:
            print('⚠️  No layer – skip filter analytics test')
            return

    with app.test_client() as c:
        r = c.post(
            f'/api/layers/{layer.id}/contribution-type-filter/',
            json={'knowledge_form': 'model'},
        )
        assert r.status_code == 200, r.get_data(as_text=True)
        bad = c.post(
            f'/api/layers/{layer.id}/contribution-type-filter/',
            json={'knowledge_form': 'not_a_form'},
        )
        assert bad.status_code == 400

    with app.test_client() as c:
        r = c.get(f'/api/layers/{layer.id}/activity/?limit=50')
        assert r.status_code == 200
        evs = r.get_json()['events']
        assert not any(e['event_type'] == 'contribution_type_filter_applied' for e in evs)

        r2 = c.get(
            f'/api/layers/{layer.id}/activity/?event_type=contribution_type_filter_applied&limit=5'
        )
        assert r2.status_code == 200
        evs2 = r2.get_json()['events']
        assert any(e['event_type'] == 'contribution_type_filter_applied' for e in evs2)


if __name__ == '__main__':
    test_knowledge_schema_endpoint()
    print('✅ test_knowledge_schema_endpoint')
    test_validate_knowledge_for_create()
    print('✅ test_validate_knowledge_for_create')
    test_apply_knowledge_patch_clears_scaffold_when_form_cleared()
    print('✅ test_apply_knowledge_patch_clears_scaffold_when_form_cleared')
    test_contribution_type_filter_analytics()
    print('✅ test_contribution_type_filter_analytics')
