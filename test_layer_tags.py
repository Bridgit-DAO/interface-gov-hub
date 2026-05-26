#!/usr/bin/env python3
"""Tests for unified layer_tag (artifacts + submissions)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_normalize_slug():
    from services.layer_tags import normalize_slug, parse_tag_slugs

    assert normalize_slug('Climate Policy') == 'climate-policy'
    assert normalize_slug('  foo_bar  ') == 'foo-bar'
    assert normalize_slug('x') is None
    assert parse_tag_slugs('aa, bb, climate-policy') == ['aa', 'bb', 'climate-policy']


def test_document_category():
    from services.document_categories import normalize_document_category, DOCUMENT_CATEGORIES

    assert normalize_document_category('policy') == 'policy'
    assert normalize_document_category('invalid') == 'document'
    assert 'glossary' in DOCUMENT_CATEGORIES


def test_artifact_and_submission_tags():
    from app import app
    from extensions import db
    from models import Artifact, Layer, Submission
    from models.layer_tag import SUBJECT_ARTIFACT, SUBJECT_SUBMISSION
    from services.layer_tags import (
        set_artifact_tags,
        set_submission_tags,
        tags_for_subject,
        sync_submission_tags_to_artifact,
    )

    with app.app_context():
        layer = Layer.query.first()
        if not layer:
            print('⚠️  No layer — skip tag test')
            return
        art = Artifact(
            layer_id=layer.id,
            artifact_type='proposal',
            title='Layer tag test artifact',
            status='draft',
        )
        db.session.add(art)
        db.session.flush()
        set_artifact_tags(art, ['governance'], user_id=None)
        sub = Submission(
            draft_name='tag-test-sub',
            title='Tag test submission',
            layer_id=layer.id,
            status='submitted',
            authors=['Test'],
            artifact_id=art.id,
        )
        db.session.add(sub)
        db.session.flush()
        set_submission_tags(sub, ['climate-policy'], user_id=None)
        db.session.commit()

        assert tags_for_subject(SUBJECT_ARTIFACT, art.id)[0]['slug'] == 'governance'
        assert tags_for_subject(SUBJECT_SUBMISSION, sub.id)[0]['slug'] == 'climate-policy'

        sub.artifact_id = art.id
        sync_submission_tags_to_artifact(sub)
        db.session.commit()
        art_tags = {t['slug'] for t in tags_for_subject(SUBJECT_ARTIFACT, art.id)}
        assert 'climate-policy' in art_tags


def test_layer_tags_api():
    from app import app

    with app.app_context():
        from models import Layer

        layer = Layer.query.first()
        if not layer:
            print('⚠️  No layer — skip API test')
            return
        client = app.test_client()
        r = client.get(f'/api/layers/{layer.id}/layer-tags/')
        if r.status_code == 403:
            print('⚠️  Artifacts rollout disabled in test env — skip API test')
            return
        assert r.status_code == 200
        data = r.get_json()
        assert data.get('enabled') is True
        assert 'tags' in data


if __name__ == '__main__':
    test_normalize_slug()
    test_document_category()
    test_artifact_and_submission_tags()
    test_layer_tags_api()
    print('✅ layer tag tests passed')
