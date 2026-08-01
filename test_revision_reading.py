"""ML-number reads serve the latest approved revision, and patch applicability.

Runs entirely on a disposable database (``fixtures.isolated_app``) so the
deployed data is never touched.
"""
import os
import sys
from datetime import datetime, timedelta
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixtures.isolated_app import isolated_app  # noqa: E402

ML_NUMBER = 'ML-Draft-901'

REV_00_BODY = (
    'The Meta-Layer keeps trust visible. '
    'This sentence only exists in the original draft. '
    'Shared vocabulary is the foundation of interoperability.'
)
REV_01_BODY = (
    'The Meta-Layer keeps trust visible. '
    'Shared vocabulary is the foundation of interoperability. '
    'Revision one adds a paragraph about governance.'
)


def _write_body(tmpdir, name, text):
    path = os.path.join(tmpdir, name)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(text)
    return path


def _make_submission(tmpdir, *, draft_name, body, **kwargs):
    from extensions import db
    from models import Submission
    from services.submission_dedup import compute_content_hash_for_file

    path = _write_body(tmpdir, f'{draft_name}.txt', body)
    submission = Submission(
        id=str(uuid4()),
        public_id=str(uuid4()),
        title='Isolated Revision Test Draft',
        authors=['Test Author'],
        abstract='Disposable draft used by revision reading tests.',
        group='test',
        filename=f'{draft_name}.txt',
        file_path=path,
        draft_name=draft_name,
        status='approved',
        ml_number=ML_NUMBER,
        doc_type='draft',
        **kwargs,
    )
    submission.content_hash = compute_content_hash_for_file(path, submission.filename)
    db.session.add(submission)
    db.session.flush()
    return submission


def _seed_family(ctx):
    """Rev 00 parent plus one approved revision, both under the same ML number."""
    from extensions import db

    base = datetime(2026, 1, 1, 12, 0, 0)
    parent = _make_submission(
        ctx.tmpdir,
        draft_name='iso-rev-parent',
        body=REV_00_BODY,
        submitted_at=base,
        approved_at=base,
        is_revision=False,
    )
    revision = _make_submission(
        ctx.tmpdir,
        draft_name='iso-rev-01',
        body=REV_01_BODY,
        submitted_at=base + timedelta(days=30),
        approved_at=base + timedelta(days=30),
        is_revision=True,
        revision_number='01',
        parent_draft_name=parent.id,
        what_changed='Dropped the original-only sentence; added governance text.',
    )
    db.session.commit()
    return parent, revision


def _enable_patches():
    import json

    from extensions import db
    from models import SiteConfig
    from services.product_rollout import PRODUCT_ROLLOUT_SITE_CONFIG_KEY

    row = SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).first()
    cfg = json.loads(row.value) if row and row.value else {}
    cfg['patches'] = True
    payload = json.dumps(cfg, sort_keys=True)
    if row:
        row.value = payload
    else:
        db.session.add(SiteConfig(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY, value=payload))
    db.session.commit()


def _make_patch(submission, *, original_text, created_at, content_hash_at_create):
    from extensions import db
    from models import DpProposal
    from services.dp_proposals import compute_anchor_hash

    proposal = DpProposal(
        id=str(uuid4()),
        submission_id=submission.id,
        scope='document',
        status='pending',
        anchor_hash=compute_anchor_hash(
            submission.id, content_hash_at_create, original_text
        ),
        original_text=original_text,
        proposed_text=original_text + ' And a suggested addition.',
        content_hash_at_create=content_hash_at_create,
        created_at=created_at,
    )
    db.session.add(proposal)
    db.session.flush()
    return proposal


def test_ml_number_resolves_to_latest_approved_revision():
    from services.submissions import (
        get_readable_submission_by_ref,
        get_submission_by_ref,
        latest_approved_revision,
    )

    with isolated_app() as ctx:
        with ctx.app.app_context():
            parent, revision = _seed_family(ctx)

            assert latest_approved_revision(parent).id == revision.id
            assert get_readable_submission_by_ref(ML_NUMBER).id == revision.id
            # Row-level refs still address exactly one row.
            assert get_readable_submission_by_ref(parent.draft_name).id == parent.id
            assert get_readable_submission_by_ref(revision.draft_name).id == revision.id
            assert get_submission_by_ref(ML_NUMBER).id == parent.id


def test_read_route_by_ml_number_serves_latest_revision_body():
    with isolated_app() as ctx:
        with ctx.app.app_context():
            parent, revision = _seed_family(ctx)
            parent_draft = parent.draft_name
            revision_draft = revision.draft_name

        client = ctx.client()
        by_ml = client.get(f'/doc/draft/{ML_NUMBER}/read/').get_data(as_text=True)
        by_revision = client.get(f'/doc/draft/{revision_draft}/read/').get_data(as_text=True)
        by_parent = client.get(f'/doc/draft/{parent_draft}/read/').get_data(as_text=True)

        assert 'Revision one adds a paragraph about governance.' in by_ml
        assert 'This sentence only exists in the original draft.' not in by_ml
        assert 'Revision one adds a paragraph about governance.' in by_revision
        # Addressing the parent row directly still serves Rev 00.
        assert 'This sentence only exists in the original draft.' in by_parent


def test_read_route_shows_which_revision_is_served():
    with isolated_app() as ctx:
        with ctx.app.app_context():
            parent, _revision = _seed_family(ctx)
            parent_draft = parent.draft_name

        client = ctx.client()
        assert 'Revision 01' in client.get(f'/doc/draft/{ML_NUMBER}/read/').get_data(as_text=True)
        assert 'Revision 00 (original)' in client.get(
            f'/doc/draft/{parent_draft}/read/'
        ).get_data(as_text=True)


def test_patch_applicability_reflects_served_revision():
    from services.dp_proposals import list_proposals_for_submission

    with isolated_app() as ctx:
        with ctx.app.app_context():
            from extensions import db

            _enable_patches()
            parent, _revision = _seed_family(ctx)
            still_there = _make_patch(
                parent,
                original_text='Shared vocabulary is the foundation of interoperability.',
                created_at=datetime(2026, 1, 5),
                content_hash_at_create=parent.content_hash,
            )
            dropped = _make_patch(
                parent,
                original_text='This sentence only exists in the original draft.',
                created_at=datetime(2026, 1, 6),
                content_hash_at_create=parent.content_hash,
            )
            nowhere = _make_patch(
                parent,
                original_text='The quick brown fox jumps over the lazy dog.',
                created_at=datetime(2026, 1, 7),
                content_hash_at_create=parent.content_hash,
            )
            db.session.commit()
            still_there_id, dropped_id, nowhere_id = (
                still_there.id, dropped.id, nowhere.id
            )

            rows = {row.id: row.applicability for row in list_proposals_for_submission(parent.id)}

        assert rows[still_there_id] == 'applies'
        assert rows[dropped_id] == 'needs-review'
        # Text that exists in no revision is dropped from the list entirely.
        assert nowhere_id not in rows


def test_proposals_api_reports_applicability():
    with isolated_app() as ctx:
        with ctx.app.app_context():
            from extensions import db

            _enable_patches()
            parent, _revision = _seed_family(ctx)
            _make_patch(
                parent,
                original_text='This sentence only exists in the original draft.',
                created_at=datetime(2026, 1, 6),
                content_hash_at_create=parent.content_hash,
            )
            db.session.commit()

        payload = ctx.client().get(f'/api/doc/draft/{ML_NUMBER}/proposals/').get_json()

        assert payload['counts_by_applicability'] == {
            'applies': 0, 'needs-review': 1, 'orphaned': 0,
        }
        assert payload['proposals'][0]['applicability'] == 'needs-review'
        assert payload['proposals'][0]['applicability_label'] == 'Needs re-anchoring'


def test_family_patch_summary_attributes_patches_to_a_revision():
    from services.dp_proposals import family_patch_summary

    with isolated_app() as ctx:
        with ctx.app.app_context():
            from extensions import db

            _enable_patches()
            parent, revision = _seed_family(ctx)
            _make_patch(
                parent,
                original_text='This sentence only exists in the original draft.',
                created_at=datetime(2026, 1, 6),
                content_hash_at_create=parent.content_hash,
            )
            _make_patch(
                parent,
                original_text='Revision one adds a paragraph about governance.',
                created_at=datetime(2026, 3, 1),
                content_hash_at_create=revision.content_hash,
            )
            db.session.commit()

            summary = family_patch_summary(parent)

            assert summary['total'] == 2
            assert summary['counts']['applies'] == 1
            assert summary['counts']['needs-review'] == 1
            assert summary['per_revision'][parent.id]['needs-review'] == 1
            assert summary['per_revision'][revision.id]['applies'] == 1
            assert summary['unattributed'] == 0


def test_revisions_page_lists_revision_and_patch_context():
    with isolated_app() as ctx:
        with ctx.app.app_context():
            from extensions import db

            _enable_patches()
            parent, _revision = _seed_family(ctx)
            _make_patch(
                parent,
                original_text='This sentence only exists in the original draft.',
                created_at=datetime(2026, 1, 6),
                content_hash_at_create=parent.content_hash,
            )
            db.session.commit()
            parent_draft = parent.draft_name

        html = ctx.client().get(f'/doc/draft/{parent_draft}/revisions/').get_data(as_text=True)

        assert 'Revision 01' in html
        assert 'Dropped the original-only sentence' in html
        assert 'Read this revision' in html
        assert 'scoped to the whole document family' in html
        assert 'need re-anchoring' in html
