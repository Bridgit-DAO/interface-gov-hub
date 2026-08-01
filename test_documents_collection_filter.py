"""Tests for the /doc/all/?collection= query-string filter (external deep-link support)."""
import pytest

from app import app
from services.documents import (
    DESIRABLE_PROPERTIES_META_LAYER_TITLE,
    DOC_COLLECTION_DESIRABLE_PROPERTIES,
    filter_documents_by_collection,
    is_desirable_properties_collection_document,
)


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_is_desirable_properties_collection_document_matches_dp_titles():
    assert is_desirable_properties_collection_document('DP1 - Federated Auth & Accountability')
    assert is_desirable_properties_collection_document('DP22 – Civic Memory & Sensemaking Continuity')
    assert is_desirable_properties_collection_document(DESIRABLE_PROPERTIES_META_LAYER_TITLE)
    assert is_desirable_properties_collection_document('The Desirable Properties of a Meta-Layer')


def test_is_desirable_properties_collection_document_excludes_other_docs():
    assert not is_desirable_properties_collection_document('Foundational Governance Practices')
    assert not is_desirable_properties_collection_document('The Metaweb Charter')
    assert not is_desirable_properties_collection_document('')
    assert not is_desirable_properties_collection_document(None)


def test_filter_documents_by_collection_desirable_properties():
    docs = [
        {'title': 'DP1 - Federated Auth & Accountability'},
        {'title': 'DP10 - Education'},
        {'title': DESIRABLE_PROPERTIES_META_LAYER_TITLE},
        {'title': 'The Metaweb Charter'},
        {'title': 'Foundational Governance Practices'},
    ]
    filtered = filter_documents_by_collection(docs, DOC_COLLECTION_DESIRABLE_PROPERTIES)
    titles = {d['title'] for d in filtered}
    assert titles == {
        'DP1 - Federated Auth & Accountability',
        'DP10 - Education',
        DESIRABLE_PROPERTIES_META_LAYER_TITLE,
    }


def test_filter_documents_by_collection_unknown_value_returns_all():
    docs = [{'title': 'DP1 - Federated Auth & Accountability'}, {'title': 'The Metaweb Charter'}]
    assert filter_documents_by_collection(docs, 'not-a-real-collection') == docs
    assert filter_documents_by_collection(docs, '') == docs
    assert filter_documents_by_collection(docs, None) == docs


def test_doc_all_route_unfiltered_still_200(client):
    r = client.get('/doc/all/')
    assert r.status_code == 200
    assert 'Documents' in r.get_data(as_text=True)


def test_doc_all_route_desirable_properties_filter(client):
    r = client.get('/doc/all/?collection=desirable-properties')
    assert r.status_code == 200
    text = r.get_data(as_text=True)
    assert 'Clear filter' in text
    assert DESIRABLE_PROPERTIES_META_LAYER_TITLE in text

    with app.app_context():
        from routes.documents import _build_all_documents_catalog

        full_catalog = _build_all_documents_catalog()
        expected = filter_documents_by_collection(full_catalog, DOC_COLLECTION_DESIRABLE_PROPERTIES)

    assert len(expected) >= 20  # ~23 DP drafts + meta-layer draft, per current dev DB
    for doc in expected:
        # Titles are embedded in a JSON blob (may be unicode-escaped), so match on the
        # stable document id/name instead of the raw (possibly non-ASCII) title text.
        assert doc['name'] in text
    # Sanity: something outside the collection must NOT be present.
    non_dp_names = [
        d['name'] for d in full_catalog
        if not is_desirable_properties_collection_document(d['title'])
    ]
    if non_dp_names:
        assert non_dp_names[0] not in text


def test_doc_all_route_garbage_collection_value_degrades_gracefully(client):
    r = client.get('/doc/all/?collection=totally-bogus-value')
    assert r.status_code == 200
    assert 'Clear filter' not in r.get_data(as_text=True)
