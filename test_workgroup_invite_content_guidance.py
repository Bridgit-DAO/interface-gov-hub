"""Unit tests for invite content guidance in AI draft emails."""
from services.workgroup_invite_ai import _DP_ENGAGEMENT_PARAGRAPH, _invite_content_guidance


def test_invite_content_guidance_empty():
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
