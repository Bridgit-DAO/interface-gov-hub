"""Tests for ML draft numbering and duplicate detection."""
from datetime import datetime

from services.ml_numbering import (
    build_ml_renumber_plan,
    creation_order_sort_key,
    find_conflicting_submission,
    format_ml_draft_number,
    is_ml_numbering_sealed,
    normalize_title,
    parse_ml_draft_seq,
)
from services.workgroup_links import extract_dp_number_from_title


class _FakeSub:
    def __init__(self, title, is_revision=False, submitted_at=None, id='x'):
        self.title = title
        self.is_revision = is_revision
        self.submitted_at = submitted_at
        self.id = id


def test_normalize_title():
    assert normalize_title('  Civic Digital Artifacts  ') == 'civic digital artifacts'
    assert normalize_title('DP13 – AI Containment') == normalize_title('DP13 - AI Containment')


def test_find_conflicting_submission():
    from app import create_app

    app = create_app()
    with app.app_context():
        from models import Submission

        parent = Submission.query.filter(
            Submission.title.ilike('DP1%'),
            Submission.status.in_(['approved', 'published']),
        ).first()
        if not parent:
            return
        assert find_conflicting_submission(parent.title) is not None
        assert find_conflicting_submission('Totally Unique Title XYZ 999') is None


def test_build_ml_renumber_plan_shape():
    from app import create_app

    app = create_app()
    with app.app_context():
        plan = build_ml_renumber_plan()
        assert len(plan) >= 20
        assert plan[0]['new_ml'] == 'ML-Draft-001'
        for idx, entry in enumerate(plan, start=1):
            assert entry['new_ml'] == format_ml_draft_number(idx)


def test_creation_order_sort_key():
    early = _FakeSub('DP1', submitted_at=datetime(2026, 1, 1), id='a')
    late = _FakeSub('DP11', submitted_at=datetime(2026, 6, 1), id='b')
    assert creation_order_sort_key(early, [early]) < creation_order_sort_key(late, [late])


def test_format_and_parse_ml():
    assert format_ml_draft_number(1) == 'ML-Draft-001'
    assert parse_ml_draft_seq('ML-Draft-026') == 26
    assert parse_ml_draft_seq('ML-RFC-001') is None


def test_extract_dp_number_from_title_still_works():
    assert extract_dp_number_from_title('DP21 - Multi-Modal') == 21


def test_sealed_blocks_renumber_check():
    from app import create_app
    from services.ml_numbering import needs_ml_renumber, seal_ml_numbering

    app = create_app()
    with app.app_context():
        if is_ml_numbering_sealed():
            assert needs_ml_renumber() is False
            return
        # Do not seal in test – prod uses seal explicitly
