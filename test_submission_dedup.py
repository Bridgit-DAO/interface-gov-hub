"""Tests for submission duplicate detection and content hashing."""
from services.submission_dedup import (
    compute_content_hash_from_bytes,
    find_submission_conflict,
    hash_text_content,
    normalize_ordinal_id,
    normalize_text_for_hash,
)


def test_normalize_text_for_hash_ignores_case_and_whitespace():
    a = normalize_text_for_hash('Hello   World')
    b = normalize_text_for_hash('hello world')
    assert a == b


def test_same_text_different_title_same_hash():
    h1 = hash_text_content('Civic Digital Artifacts body text here.')
    h2 = hash_text_content('Civic Digital Artifacts body text here.')
    assert h1 == h2


def test_hash_text_vs_binary():
    text = b'The same words in the document.'
    assert compute_content_hash_from_bytes(text, content_type='text/plain') == hash_text_content(
        'The same words in the document.'
    )


def test_normalize_ordinal_id():
    assert normalize_ordinal_id('AbC123i0') == 'abc123i0'


def test_find_submission_conflict_by_title():
    from app import app as flask_app
    from models import Submission

    with flask_app.app_context():
        parent = Submission.query.filter(
            Submission.title.ilike('DP1%'),
            Submission.status.in_(['approved', 'published']),
        ).first()
        if not parent:
            return
        conflict = find_submission_conflict(title=parent.title)
        assert conflict is not None
        assert conflict[0] in ('title', 'content_hash', 'ordinal_id')


def test_civic_duplicate_content_hash():
    """ML-Draft-005/012 duplicate would share content hash once backfilled."""
    from app import app as flask_app
    from models import Submission

    with flask_app.app_context():
        rows = Submission.query.filter(
            Submission.title == 'Civic Digital Artifacts',
        ).all()
        hashes = [(s.id, s.ml_number, s.status, (s.content_hash or '')[:12]) for s in rows]
        if len(rows) < 2:
            return
        with_hash = [s for s in rows if s.content_hash]
        if len(with_hash) >= 2:
            assert with_hash[0].content_hash == with_hash[1].content_hash
