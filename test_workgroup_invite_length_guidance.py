"""Unit tests for invite email length and tone guidance."""
from services.workgroup_invite_ai import (
    _DP_ENGAGEMENT_PARAGRAPH,
    _LENGTH_GUIDANCE,
    _LENGTH_LONG_EXPAND_THRESHOLD,
    _LENGTH_MIN_WORDS,
    _TONE_GUIDANCE,
    _dp_engagement_instruction,
    _invite_content_guidance,
)


def test_length_guidance_structural_rules():
    assert '120–180' in _LENGTH_GUIDANCE['short']
    assert '3 short paragraphs' in _LENGTH_GUIDANCE['short']
    assert 'single-sentence summary' in _LENGTH_GUIDANCE['short']

    assert '220–320' in _LENGTH_GUIDANCE['medium']
    assert 'baseline length' in _LENGTH_GUIDANCE['medium']

    assert '380–520' in _LENGTH_GUIDANCE['long']
    assert '100 words longer' in _LENGTH_GUIDANCE['long']
    assert 'why this specific person' in _LENGTH_GUIDANCE['long']
    assert 'what participation looks like' in _LENGTH_GUIDANCE['long']


def test_length_min_words_long_threshold():
    assert _LENGTH_MIN_WORDS['long'] == _LENGTH_LONG_EXPAND_THRESHOLD == 350


def test_tone_guidance_differentiation():
    warm = _TONE_GUIDANCE['warm']
    professional = _TONE_GUIDANCE['professional']
    direct = _TONE_GUIDANCE['direct']
    assert 'conversational' in warm
    assert 'formality' in professional
    assert 'minimal preamble' in direct
    assert warm != professional != direct


def test_dp_engagement_instruction_short_vs_medium():
    short = _dp_engagement_instruction(length_key='short')
    medium = _dp_engagement_instruction(length_key='medium')
    assert 'one sentence only' in short.lower()
    assert _DP_ENGAGEMENT_PARAGRAPH not in short
    assert _DP_ENGAGEMENT_PARAGRAPH in medium


def test_invite_content_guidance_short_abbreviates_dp_engagement():
    guidance = _invite_content_guidance({
        'lead': 'events',
        'events': [{
            'title': 'Fork in the Web workshops',
            'url': 'https://desirableproperties.org/series/fork-in-the-web',
        }],
        'perspectives': [],
    }, length_key='short')
    assert 'one-sentence' in guidance.lower()
    assert _DP_ENGAGEMENT_PARAGRAPH not in guidance

    medium_guidance = _invite_content_guidance({
        'lead': 'events',
        'events': [{
            'title': 'Fork in the Web workshops',
            'url': 'https://desirableproperties.org/series/fork-in-the-web',
        }],
        'perspectives': [],
    }, length_key='medium')
    assert _DP_ENGAGEMENT_PARAGRAPH in medium_guidance
