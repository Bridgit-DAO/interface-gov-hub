"""Tests for /doc/all/ catalog prefix badge resolution."""
from services.layer_prefixes import catalog_prefix_badge_value, effective_prefix_for_document


def test_catalog_prefix_badge_omits_when_ml_number_starts_with_prefix():
    assert catalog_prefix_badge_value('ML', 'ML-Draft-001') is None
    assert catalog_prefix_badge_value('ML', 'ml-draft-030') is None
    assert catalog_prefix_badge_value('CL', 'CL-Draft-007') is None


def test_catalog_prefix_badge_shows_when_not_redundant():
    assert catalog_prefix_badge_value('CL', 'ML-Draft-001') == 'CL'
    assert catalog_prefix_badge_value('ML', 'Draft-001') == 'ML'
    assert catalog_prefix_badge_value('ML', None) == 'ML'
    assert catalog_prefix_badge_value('ML', '') == 'ML'


def test_effective_prefix_for_document_honours_override():
    assert effective_prefix_for_document(prefix_code='CL', layer_id='any') == 'CL'


def test_effective_prefix_for_document_falls_back_to_ml_without_layer():
    assert effective_prefix_for_document(prefix_code=None, layer_id=None) == 'ML'
