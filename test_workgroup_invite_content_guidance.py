"""Unit tests for invite content guidance in AI draft emails."""
from services.workgroup_invite_ai import (
    _DP_ENGAGEMENT_PARAGRAPH,
    _format_invite_date,
    _invite_content_guidance,
    _normalize_invite_content_for_llm,
)


def test_format_invite_date():
    assert _format_invite_date('2026-08-10') == 'August 10, 2026'
    assert _format_invite_date('2026-08-10T00:00:00.000Z') == 'August 10, 2026'


def test_normalize_invite_content_for_llm_dates():
    normalized = _normalize_invite_content_for_llm({
        'lead': 'events',
        'events': [{
            'title': 'Series',
            'kind': 'series',
            'next_session_date': '2026-08-17',
            'series_started': '2026-08-10',
        }],
        'perspectives': [],
    })
    assert normalized['events'][0]['next_session_date'] == 'August 17, 2026'
    assert normalized['events'][0]['series_started'] == 'August 10, 2026'


def test_invite_content_guidance_empty():
    assert _DP_ENGAGEMENT_PARAGRAPH
    assert '\u2014' not in _DP_ENGAGEMENT_PARAGRAPH
    assert _invite_content_guidance(None) == ''
    assert _invite_content_guidance({}) == ''
    assert _invite_content_guidance({'events': [], 'perspectives': []}) == ''


def test_invite_content_guidance_events_lead():
    guidance = _invite_content_guidance({
        'lead': 'events',
        'events': [{
            'title': 'Fork in the Web workshops',
            'url': 'https://desirableproperties.org/series/fork-in-the-web',
            'description': 'Event series',
            'event_date': '2026-09-01T00:00:00.000Z',
        }],
        'perspectives': [{
            'title': 'A Fork in the Web',
            'url': 'https://desirableproperties.org/perspectives/a-fork-in-the-web',
            'slug': 'a-fork-in-the-web',
        }],
    })
    assert 'EVENTS TO MENTION' in guidance
    assert 'Fork in the Web workshops' in guidance
    assert 'PERSPECTIVES TO MENTION' in guidance
    assert 'a-fork-in-the-web' in guidance
    assert _DP_ENGAGEMENT_PARAGRAPH in guidance
    assert guidance.index('EVENTS TO MENTION') < guidance.index('PERSPECTIVES TO MENTION')


def test_invite_content_guidance_perspectives_lead():
    guidance = _invite_content_guidance({
        'lead': 'perspectives',
        'events': [{
            'title': 'Fork in the Web workshops',
            'url': 'https://desirableproperties.org/series/fork-in-the-web',
        }],
        'perspectives': [{
            'title': 'A Fork in the Web',
            'url': 'https://desirableproperties.org/perspectives/a-fork-in-the-web',
            'slug': 'a-fork-in-the-web',
        }],
    })
    assert guidance.index('PERSPECTIVES TO MENTION') < guidance.index('EVENTS TO MENTION')


def test_invite_content_guidance_engagement_lead():
    guidance = _invite_content_guidance({
        'lead': 'engagement',
        'events': [{
            'title': 'Fork in the Web workshops',
            'url': 'https://desirableproperties.org/series/fork-in-the-web',
        }],
        'perspectives': [{
            'title': 'A Fork in the Web',
            'url': 'https://desirableproperties.org/perspectives/a-fork-in-the-web',
            'slug': 'a-fork-in-the-web',
        }],
    })
    assert 'DESIRABLE PROPERTIES ENGAGEMENT' in guidance
    assert guidance.index('DESIRABLE PROPERTIES ENGAGEMENT') < guidance.index('EVENTS TO MENTION')
    assert guidance.index('EVENTS TO MENTION') < guidance.index('PERSPECTIVES TO MENTION')
    assert 'Include this Desirable Properties engagement paragraph verbatim' not in guidance


def test_invite_content_guidance_series_kind_date_wording():
    guidance = _invite_content_guidance({
        'lead': 'events',
        'events': [{
            'title': 'Fork in the Web workshops',
            'url': 'https://desirableproperties.org/series/fork-in-the-web',
            'kind': 'series',
            'event_date': '2026-08-17',
            'next_session_date': '2026-08-17',
            'series_started': '2026-06-01',
        }],
        'perspectives': [],
    })
    assert 'kind=series' in guidance
    assert 'next session is on August 17, 2026' in guidance
    assert 'ongoing (started June 1, 2026)' in guidance
    assert '2026-08-17' not in guidance
    assert 'FULL absolute URLs' in guidance
