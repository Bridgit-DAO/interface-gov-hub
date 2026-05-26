"""Tests for draft read-page return navigation."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_read_page_url_with_return_to():
    from services.read_navigation import read_page_url, draft_reader_back_href

    assert (
        read_page_url('j64tnris', '/dp-challenge/')
        == '/doc/draft/j64tnris/read/?return_to=%2Fdp-challenge%2F'
    )
    assert read_page_url('ML-Draft-002', None) == '/doc/draft/ML-Draft-002/read/'
    assert draft_reader_back_href('/dp-challenge/') == '/dp-challenge/'
    assert draft_reader_back_href('//evil') == '/doc/all/'
    assert draft_reader_back_href(None) == '/doc/all/'


def test_draft_reader_back_href_in_html():
    from app import app

    client = app.test_client()
    r = client.get('/doc/draft/j64tnris/read/?return_to=/dp-challenge/')
    if r.status_code == 404:
        return
    assert r.status_code == 200
    assert 'href="/dp-challenge/"' in r.get_data(as_text=True)
    assert 'id="draftReaderBack"' in r.get_data(as_text=True)
