"""Tests for Canopi synthesis export helpers."""
from services.canopi_synthesis import (
    anchor_identity_hash_from_context,
    book_page_id_for_dp_number,
    compute_anchor_union_hash,
)


def test_book_page_id_for_dp_number():
    assert book_page_id_for_dp_number(9) == 'book_desirableproperties_org_viewer_dp09'


def test_anchor_identity_hash_from_context_json():
    raw = '{"anchorIdentityHash":"abc123def","textQuote":{"exact":"hello"}}'
    assert anchor_identity_hash_from_context(raw) == 'abc123def'


def test_compute_anchor_union_hash_sorted_unique():
    a = compute_anchor_union_hash(['b', 'a', 'b'])
    b = compute_anchor_union_hash(['a', 'b'])
    assert a == b
    assert len(a) == 64
