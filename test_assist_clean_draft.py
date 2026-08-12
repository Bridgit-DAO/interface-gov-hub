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


def test_clean_draft_unwraps_think_block_with_draft_inside():
    think_open = '<' + 'think' + '>'
    think_close = '</' + 'think' + '>'
    raw = (
        'Hi Daveed,\n'
        'Our many conversations about the layered web.\n\n'
        'https://desirableproperties.org/perspectives/a-fork-in-the-web\n\n'
        'There is also\n'
        f'{think_open}\n'
        'more about the Desirable Properties Challenge and why this workgroup matters. '
        'Your perspective would strengthen our work.\n\n'
        '[JOIN_PRIMARY]\n'
        f'{think_close}'
    )
    cleaned = clean_draft(raw)
    assert 'There is also' in cleaned
    assert 'Desirable Properties Challenge' in cleaned
    assert '[JOIN_PRIMARY]' in cleaned
    assert think_open not in cleaned
    assert think_close not in cleaned


def test_clean_draft_keeps_answer_after_think_block():
    think_open = '<' + 'think' + '>'
    think_close = '</' + 'think' + '>'
    raw = (
        f'{think_open}planning the email{think_close}\n\n'
        'Hi Pat,\n\nThanks for your work on governance patterns.\n\n'
        '[JOIN_PRIMARY]'
    )
    cleaned = clean_draft(raw)
    assert 'planning the email' not in cleaned
    assert 'Hi Pat,' in cleaned
    assert '[JOIN_PRIMARY]' in cleaned


def test_clean_draft_truncates_after_first_join_primary():
    raw = (
        'Hi Daveed,\n\n'
        'First complete draft with enough words to pass validation checks.\n\n'
        'Best regards,\nDaveed\n\n'
        '[JOIN_PRIMARY]\n\n'
        '---\n\n'
        'Let me count words approximately:\n'
        '- Hi Daveed, (2)\n'
        'Total: ~352 words. Slightly under target.\n\n'
        'Let me expand a bit.\n\n'
        '---\n\n'
        'Hi Daveed,\n\n'
        'Second revised draft body.\n\n'
        '[JOIN_PRIMARY]\n\n'
        'Hmm let me recount:\n'
        'Total: ~367 words.\n'
    )
    cleaned = clean_draft(raw)
    assert cleaned.endswith('[JOIN_PRIMARY]')
    assert cleaned.count('[JOIN_PRIMARY]') == 1
    assert 'Let me count' not in cleaned
    assert 'Second revised draft' not in cleaned
    assert 'Hmm let me recount' not in cleaned


def test_clean_draft_strips_meta_divider_without_join_primary():
    raw = (
        'Hi Pat,\n\n'
        'Thanks for your thoughtful contributions to the workgroup.\n\n'
        'Best regards,\nPat\n\n'
        '---\n\n'
        'Let me reconsider the tone and expand this to about 200 words.\n'
    )
    cleaned = clean_draft(raw)
    assert 'Let me reconsider' not in cleaned
    assert cleaned.endswith('Pat')
    assert '---' not in cleaned
