#!/usr/bin/env python3
"""Tests for layer-scoped artifact tags."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_normalize_slug():
    from services.artifact_tags import normalize_slug, parse_tag_slugs

    assert normalize_slug('Climate Policy') == 'climate-policy'
    assert normalize_slug('  foo_bar  ') == 'foo-bar'
    assert normalize_slug('x') is None
    assert parse_tag_slugs('aa, bb, climate-policy') == ['aa', 'bb', 'climate-policy']


def test_set_and_filter_tags():
    from app import app
    from extensions import db
    from models import Artifact, Layer
    from services.artifact_tags import set_artifact_tags, apply_tag_filter, tags_for_artifact

    with app.app_context():
        layer = Layer.query.first()
        if not layer:
            print('⚠️  No layer – skip tag test')
            return
        art = Artifact(
            layer_id=layer.id,
            artifact_type='proposal',
            title='Tag test artifact',
            status='draft',
        )
        db.session.add(art)
        db.session.flush()
        added, removed = set_artifact_tags(art, ['governance', 'climate-policy'], user_id=None)
        db.session.commit()
        assert 'governance' in added
        tags = tags_for_artifact(art.id)
        slugs = {t['slug'] for t in tags}
        assert slugs == {'governance', 'climate-policy'}

        q = apply_tag_filter(
            Artifact.query.filter_by(layer_id=layer.id),
            ['governance', 'climate-policy'],
            match_any=False,
        )
        assert art.id in [a.id for a in q.all()]

        q_or = apply_tag_filter(
            Artifact.query.filter_by(layer_id=layer.id),
            ['missing-tag', 'governance'],
            match_any=True,
        )
        assert art.id in [a.id for a in q_or.all()]

        set_artifact_tags(art, ['governance'], user_id=None)
        db.session.commit()
        tags2 = tags_for_artifact(art.id)
        assert len(tags2) == 1
        db.session.delete(art)
        db.session.commit()


def test_artifact_tags_api():
    from app import app
    from extensions import db
    from models import Artifact, Layer, User

    with app.test_client() as c:
        with app.app_context():
            layer = Layer.query.first()
            user = User.query.first()
            if not layer or not user:
                print('⚠️  No layer/user – skip API test')
                return
            username = user.username
            art = Artifact(
                layer_id=layer.id,
                artifact_type='proposal',
                title='API tag test',
                status='draft',
            )
            db.session.add(art)
            db.session.commit()
            aid = art.id
            lid = layer.id

        with c.session_transaction() as sess:
            sess['user'] = username

        r = c.patch(
            f'/api/artifacts/{aid}/',
            json={'tag_slugs': ['api-tag', 'second-tag']},
        )
        assert r.status_code == 200, r.data
        body = r.get_json()
        slugs = {t['slug'] for t in body['artifact']['tags']}
        assert slugs == {'api-tag', 'second-tag'}

        r2 = c.get(f'/api/layers/{lid}/artifact-tags/')
        assert r2.status_code == 200
        tag_slugs = {t['slug'] for t in r2.get_json()['tags']}
        assert 'api-tag' in tag_slugs

        r3 = c.get(f'/api/layers/{lid}/artifacts/?tags=api-tag,second-tag')
        assert r3.status_code == 200
        ids = {a['id'] for a in r3.get_json()['artifacts']}
        assert aid in ids

        with app.app_context():
            art = Artifact.query.get(aid)
            db.session.delete(art)
            db.session.commit()


if __name__ == '__main__':
    test_normalize_slug()
    test_set_and_filter_tags()
    test_artifact_tags_api()
    print('✅ artifact tag tests passed')
