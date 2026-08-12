"""Unit tests for assist draft cleaning (em-dash stripping)."""
from services.assist import clean_draft, strip_em_dashes

_EM = '\u2014'
_EN = '\u2013'


def test_strip_em_dashes_replaces_em_with_en():
    assert strip_em_dashes(f'the layered web {_EM} governance') == f'the layered web {_EN} governance'


def test_strip_em_dashes_preserves_en_dash():
    assert strip_em_dashes(f'About 120{_EN}180 words.') == f'About 120{_EN}180 words.'


def test_strip_em_dashes_empty_and_none():
    assert strip_em_dashes('') == ''
    assert strip_em_dashes(None) == ''


def test_clean_draft_strips_em_dashes():
    raw = f'Hi Pat,\n\nWe discussed the layered web {_EM} governance patterns.'
    cleaned = clean_draft(raw)
    assert _EM not in cleaned
    assert f'layered web {_EN} governance' in cleaned


def test_clean_draft_removes_reasoning_tags_and_em_dashes():
    raw = (
        f'<reasoning>thinking</reasoning>\n\n'
        f'Hi Pat,\n\nYou may have missed {_EM} triaging submissions.'
    )
    cleaned = clean_draft(raw)
    assert 'thinking' not in cleaned
    assert _EM not in cleaned
    assert f'missed {_EN} triaging' in cleaned
