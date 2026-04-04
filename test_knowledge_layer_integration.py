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


def test_validate_knowledge_for_create():
    from app import app
    from services.knowledge_layer import validate_knowledge_for_create

    cfg = app.config
    form, sc, err = validate_knowledge_for_create(
        'proposal', 'decision', None, cfg
    )
    assert not err and form == 'decision' and sc is None

    _, _, err = validate_knowledge_for_create(
        'proposal', 'gloss', None, cfg
    )
    assert err, 'gloss not allowed for proposal'


def test_apply_knowledge_patch_clears_scaffold_when_form_cleared():
    from app import app
    from extensions import db
    from models import Artifact, Layer

    with app.app_context():
        layer = Layer.query.first()
        if not layer:
            print('⚠️  No layer — skip patch test')
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
        # Login may be required — skip if 401
        r = c.patch(
            f'/api/artifacts/{aid}/',
            json={'knowledge_form': None},
            headers={'Content-Type': 'application/json'},
        )
        if r.status_code in (401, 302):
            print('⚠️  PATCH requires auth — skip')
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


if __name__ == '__main__':
    test_knowledge_schema_endpoint()
    print('✅ test_knowledge_schema_endpoint')
    test_validate_knowledge_for_create()
    print('✅ test_validate_knowledge_for_create')
    test_apply_knowledge_patch_clears_scaffold_when_form_cleared()
    print('✅ test_apply_knowledge_patch_clears_scaffold_when_form_cleared')
