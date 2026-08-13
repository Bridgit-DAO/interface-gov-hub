"""Web research helpers for invite contact discovery."""
from services.web_research import (
    build_person_search_queries,
    build_research_warnings,
    extract_linkedin_vanity,
    research_person_corpus,
)


def test_extract_linkedin_vanity_from_profile_url():
    assert extract_linkedin_vanity('https://www.linkedin.com/in/kpbarry/') == 'kpbarry'


def test_build_person_search_queries_targets_linkedin_slug():
    queries = build_person_search_queries(
        'Kevin Barry',
        'https://www.linkedin.com/in/kpbarry/',
    )
    assert any('site:linkedin.com/in/kpbarry' in q for q in queries)
    assert any('Kevin Barry' in q for q in queries)


def test_build_research_warnings_when_search_unconfigured(monkeypatch):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    monkeypatch.delenv('TAVILY_API_KEY', raising=False)
    warnings = build_research_warnings(
        linkedin_url='https://www.linkedin.com/in/kpbarry/',
        linkedin_fetch_ok=False,
        search_results=[],
        search_available=False,
        combined_text='',
    )
    assert any('BRAVE_SEARCH_API_KEY' in item for item in warnings)
    assert any('LinkedIn blocked' in item for item in warnings)


def test_research_person_corpus_includes_linkedin_anchor_when_fetch_blocked(monkeypatch):
    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    monkeypatch.delenv('TAVILY_API_KEY', raising=False)
    monkeypatch.setattr(
        'services.web_research.fetch_url_text',
        lambda url: {'url': url, 'ok': False, 'error': 'HTTP 999', 'text': ''},
    )
    monkeypatch.setattr('services.web_research.web_search', lambda *args, **kwargs: [])

    corpus = research_person_corpus(
        name='Kevin Barry',
        linkedin_url='https://www.linkedin.com/in/kpbarry/',
    )
    assert corpus['linkedin_vanity'] == 'kpbarry'
    assert corpus['linkedin_fetch_ok'] is False
    assert 'kpbarry' in corpus['combined_text']
    assert corpus['research_warnings']
