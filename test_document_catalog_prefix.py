"""Tests for /doc/all/ catalog prefix badge resolution and backfill migration."""
import sqlite3
from uuid import uuid4

from fixtures.isolated_app import isolated_app
from services.layer_prefixes import (
    catalog_prefix_badge_value,
    effective_prefix_for_document,
    parse_prefix_from_ml_number,
    resolve_prefix_code_for_backfill,
)


def test_catalog_prefix_badge_shows_even_when_ml_number_matches_prefix():
    assert catalog_prefix_badge_value('ML', 'ML-Draft-001') == 'ML'
    assert catalog_prefix_badge_value('ML', 'ml-draft-030') == 'ML'
    assert catalog_prefix_badge_value('CL', 'CL-Draft-007') == 'CL'


def test_catalog_prefix_badge_shows_when_not_redundant():
    assert catalog_prefix_badge_value('CL', 'ML-Draft-001') == 'CL'
    assert catalog_prefix_badge_value('ML', 'Draft-001') == 'ML'
    assert catalog_prefix_badge_value('ML', None) == 'ML'
    assert catalog_prefix_badge_value('ML', '') == 'ML'


def test_effective_prefix_for_document_honours_override():
    assert effective_prefix_for_document(prefix_code='CL', layer_id='any') == 'CL'


def test_effective_prefix_for_document_falls_back_to_ml_without_layer():
    assert effective_prefix_for_document(prefix_code=None, layer_id=None) == 'ML'


def test_parse_prefix_from_ml_number():
    assert parse_prefix_from_ml_number('ML-Draft-001') == 'ML'
    assert parse_prefix_from_ml_number('cl-draft-030') == 'CL'
    assert parse_prefix_from_ml_number('Draft-001') is None
    assert parse_prefix_from_ml_number(None) is None


def test_resolve_prefix_code_for_backfill_prefers_layer_default():
    assert resolve_prefix_code_for_backfill(layer_default_prefix='CL', ml_number='ML-Draft-001') == 'CL'


def test_resolve_prefix_code_for_backfill_parses_ml_number():
    assert resolve_prefix_code_for_backfill(layer_default_prefix=None, ml_number='ML-Draft-030') == 'ML'


def test_resolve_prefix_code_for_backfill_falls_back_to_ml():
    assert resolve_prefix_code_for_backfill(layer_default_prefix=None, ml_number=None) == 'ML'


def test_migrate_submission_prefix_code_backfill_idempotent():
    from extensions import db
    from migrations import (
        migrate_layer_prefix_v1,
        migrate_submission_prefix_code_v1,
        migrate_submission_prefix_code_backfill_v1,
    )
    from models import Layer, LayerPrefix, Submission, User

    with isolated_app() as ctx:
        with ctx.app.app_context():
            migrate_layer_prefix_v1(ctx.app)
            migrate_submission_prefix_code_v1(ctx.app)

            owner = User(
                id=str(uuid4()),
                username='prefix-backfill-owner',
                email='prefix-backfill-owner@example.com',
                role='user',
                displayName='Prefix Backfill Owner',
                password_hash='!test',
            )
            layer = Layer(
                id=str(uuid4()),
                name='Prefix Backfill Layer',
                slug='prefix-backfill-layer',
                initiator_id=owner.id,
                approval_status='approved',
                display_status='active',
            )
            db.session.add_all([owner, layer])
            db.session.flush()

            db.session.add(LayerPrefix(
                id=str(uuid4()),
                layer_id=layer.id,
                prefix='CL',
                is_default=True,
                created_by=owner.id,
            ))

            sub_from_layer = Submission(
                id=str(uuid4()),
                public_id=str(uuid4()),
                title='Layer default prefix',
                layer_id=layer.id,
                ml_number='CL-Draft-001',
                status='approved',
            )
            sub_from_ml = Submission(
                id=str(uuid4()),
                public_id=str(uuid4()),
                title='Parsed from ml_number',
                ml_number='ML-Draft-030',
                status='approved',
            )
            sub_fallback = Submission(
                id=str(uuid4()),
                public_id=str(uuid4()),
                title='Fallback ML',
                status='approved',
            )
            db.session.add_all([sub_from_layer, sub_from_ml, sub_fallback])
            db.session.commit()

            migrate_submission_prefix_code_backfill_v1(ctx.app)
            migrate_submission_prefix_code_backfill_v1(ctx.app)

            conn = sqlite3.connect(ctx.db_path)
            rows = conn.execute(
                "SELECT id, prefix_code FROM submission ORDER BY title"
            ).fetchall()
            conn.close()

            prefix_by_id = {row[0]: row[1] for row in rows}
            assert prefix_by_id[sub_from_layer.id] == 'CL'
            assert prefix_by_id[sub_from_ml.id] == 'ML'
            assert prefix_by_id[sub_fallback.id] == 'ML'

            null_count = sum(1 for _, code in rows if not code)
            assert null_count == 0


def test_catalog_includes_layer_link_for_prefix_badge():
    from extensions import db
    from migrations import migrate_submission_prefix_code_v1
    from models import Layer, Submission, User
    from routes.documents import _build_all_documents_catalog

    with isolated_app() as ctx:
        with ctx.app.app_context():
            migrate_submission_prefix_code_v1(ctx.app)

            owner = User(
                id=str(uuid4()),
                username='catalog-prefix-owner',
                email='catalog-prefix-owner@example.com',
                role='user',
                displayName='Catalog Prefix Owner',
                password_hash='!test',
            )
            layer = Layer(
                id=str(uuid4()),
                name='Catalog Prefix Layer',
                slug='catalog-prefix-layer',
                initiator_id=owner.id,
                approval_status='approved',
                display_status='active',
            )
            db.session.add_all([owner, layer])
            db.session.flush()
            submission = Submission(
                id=str(uuid4()),
                public_id=str(uuid4()),
                title='Catalog prefix draft',
                layer_id=layer.id,
                ml_number='ML-Draft-001',
                prefix_code='ML',
                status='approved',
            )
            db.session.add(submission)
            db.session.commit()

            catalog = _build_all_documents_catalog()
            row = next(item for item in catalog if item['name'] == submission.id)
            assert row['prefix'] == 'ML'
            assert row['layer_slug'] == 'catalog-prefix-layer'
            assert row['layer_name'] == 'Catalog Prefix Layer'

            client = ctx.client()
            response = client.get('/doc/all/')
            html = response.get_data(as_text=True)
            assert 'catalog-prefix-layer' in html
            assert 'function renderPrefixBadge(d)' in html
            assert 'encodeURIComponent(d.layer_slug)' in html
            assert "('View ' + d.layer_name)" in html
