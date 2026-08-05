"""Paragraph-level diff between two revisions, and the compare UI on /revisions/.

Runs entirely on a disposable database (``fixtures.isolated_app``) so the
deployed data is never touched.
"""
import os
import sys
from datetime import datetime, timedelta
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fixtures.isolated_app import isolated_app  # noqa: E402

ML_NUMBER = 'ML-Draft-902'

REV_00_BODY = """# Isolated Diff Draft

Opening paragraph that survives every revision untouched.

A middle paragraph that revision one rewrites in place.

A paragraph that revision one deletes outright.

Closing paragraph that survives every revision untouched.
"""

REV_01_BODY = """# Isolated Diff Draft

Opening paragraph that survives every revision untouched.

A middle paragraph that revision one rewrites completely in place.

---

A brand new paragraph introduced by revision one.

Closing paragraph that survives every revision untouched.
"""


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
        title='Isolated Diff Test Draft',
        authors=['Test Author'],
        abstract='Disposable draft used by revision diff tests.',
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
    from extensions import db

    base = datetime(2026, 2, 1, 12, 0, 0)
    parent = _make_submission(
        ctx.tmpdir,
        draft_name='iso-diff-parent',
        body=REV_00_BODY,
        submitted_at=base,
        approved_at=base,
        is_revision=False,
    )
    revision = _make_submission(
        ctx.tmpdir,
        draft_name='iso-diff-01',
        body=REV_01_BODY,
        submitted_at=base + timedelta(days=10),
        approved_at=base + timedelta(days=10),
        is_revision=True,
        revision_number='01',
        parent_draft_name=parent.id,
        what_changed='Rewrote the middle paragraph, dropped one, added one.',
    )
    db.session.commit()
    return parent, revision


def test_split_blocks_drops_blank_runs_and_markdown_rules():
    from services.revision_diff import split_blocks

    blocks = split_blocks('First paragraph.\n\n---\n\n\nSecond paragraph.\n\n***\n')

    assert blocks == ['First paragraph.', 'Second paragraph.']


def test_diff_reports_added_removed_and_rewritten_paragraphs():
    from services.revision_diff import diff_revisions

    result = diff_revisions(REV_00_BODY, REV_01_BODY)
    kinds = [row['kind'] for row in result['rows']]

    assert result['available'] is True
    assert result['stats']['added'] == 1
    assert result['stats']['removed'] == 1
    assert result['stats']['rewritten'] == 1
    # A rewrite is only word-diffed when the two paragraphs still resemble
    # each other; an unrelated pair reads better as a removal plus an addition.
    assert 'rewritten' in kinds and 'added' in kinds and 'removed' in kinds


def test_identical_revisions_report_no_changes():
    from services.revision_diff import diff_revisions

    result = diff_revisions(REV_00_BODY, REV_00_BODY)

    assert result['rows'] == []
    assert 'identical' in result['reason']


def test_rewritten_paragraph_is_diffed_word_by_word():
    from services.revision_diff import render_diff_stats, diff_revisions

    result = diff_revisions(
        'Shared paragraph.\n\nThe old wording of a sentence.',
        'Shared paragraph.\n\nThe new wording of a sentence.',
    )
    rewritten = [r for r in result['rows'] if r['kind'] == 'rewritten']

    assert len(rewritten) == 1
    assert rewritten[0]['old'] == 'The old wording of a sentence.'
    assert rewritten[0]['new'] == 'The new wording of a sentence.'
    assert '1 paragraph rewritten' in render_diff_stats(result['stats'])


def test_oversized_bodies_are_reported_instead_of_diffed():
    from services.revision_diff import MAX_BLOCKS, diff_revisions

    huge = '\n\n'.join(f'Paragraph {i}.' for i in range(MAX_BLOCKS + 2))
    result = diff_revisions(huge, huge + '\n\nOne more.')

    assert result['available'] is False
    assert 'too long to diff' in result['reason']


def test_revision_body_text_reads_the_stored_upload():
    from services.revision_diff import revision_body_text

    with isolated_app() as ctx:
        with ctx.app.app_context():
            _parent, revision = _seed_family(ctx)

            text = revision_body_text(revision)

        assert 'A brand new paragraph introduced by revision one.' in text
        # Paragraph breaks survive, which is what the block diff aligns on.
        assert '\n\n' in text


def test_revisions_page_renders_a_diff_by_default():
    with isolated_app() as ctx:
        with ctx.app.app_context():
            parent, _revision = _seed_family(ctx)
            parent_draft = parent.draft_name

        html = ctx.client().get(f'/doc/draft/{parent_draft}/revisions/').get_data(as_text=True)

        assert 'What changed between revisions' in html
        assert '<div class="collapse" id="revision-diff-panel">' in html
        assert 'Compare Revision 00 (original) → Revision 01' in html
        assert 'Hide comparison' in html
        assert 'Comparing <strong>Revision 00 (original)</strong>' in html
        assert 'A brand new paragraph introduced by revision one.' in html
        assert 'A paragraph that revision one deletes outright.' in html
        assert '1 paragraph added' in html
        assert 'Compare with Revision 00 (original)' in html


def test_revisions_page_honours_explicit_from_and_to():
    with isolated_app() as ctx:
        with ctx.app.app_context():
            parent, revision = _seed_family(ctx)
            parent_draft, parent_id, revision_id = parent.draft_name, parent.id, revision.id

        client = ctx.client()
        same = client.get(
            f'/doc/draft/{parent_draft}/revisions/?from={revision_id}&to={revision_id}'
        ).get_data(as_text=True)
        reversed_pair = client.get(
            f'/doc/draft/{parent_draft}/revisions/?from={revision_id}&to={parent_id}'
        ).get_data(as_text=True)

        # from == to falls back to the revision before it rather than an empty diff.
        assert '<div class="collapse show" id="revision-diff-panel">' in same
        assert 'Comparing <strong>Revision 00 (original)</strong> with <strong>Revision 01</strong>' in same
        # Comparing newest against oldest inverts which side is added.
        assert '<div class="collapse show" id="revision-diff-panel">' in reversed_pair
        assert 'Comparing <strong>Revision 01</strong> with <strong>Revision 00 (original)</strong>' in reversed_pair
        assert '1 paragraph removed' in reversed_pair


def test_revisions_page_without_revisions_has_no_compare_panel():
    with isolated_app() as ctx:
        with ctx.app.app_context():
            from extensions import db

            base = datetime(2026, 2, 1, 12, 0, 0)
            lone = _make_submission(
                ctx.tmpdir,
                draft_name='iso-diff-lone',
                body=REV_00_BODY,
                submitted_at=base,
                approved_at=base,
                is_revision=False,
            )
            db.session.commit()
            lone_draft = lone.draft_name

        html = ctx.client().get(f'/doc/draft/{lone_draft}/revisions/').get_data(as_text=True)

        assert 'What changed between revisions' not in html
        assert 'No revisions yet.' in html
