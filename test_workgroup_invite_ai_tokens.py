"""Token budgets and draft completeness for AI invite emails."""
from services.workgroup_invite_ai import (
    _INVITE_DRAFT_MAX_TOKENS,
    _INVITE_RESEARCH_MAX_TOKENS,
    invite_draft_looks_complete,
    invite_draft_max_tokens,
)


def test_invite_draft_max_tokens_by_length():
    assert invite_draft_max_tokens('short') == _INVITE_DRAFT_MAX_TOKENS['short']
    assert invite_draft_max_tokens('medium') == _INVITE_DRAFT_MAX_TOKENS['medium']
    assert invite_draft_max_tokens('long') == _INVITE_DRAFT_MAX_TOKENS['long']
    assert invite_draft_max_tokens('unknown') == _INVITE_DRAFT_MAX_TOKENS['medium']


def test_invite_draft_max_tokens_long_with_content_bonus():
    base = invite_draft_max_tokens('long')
    with_content = invite_draft_max_tokens('long', has_invite_content=True)
    assert with_content > base
    assert with_content >= 4000


def test_invite_research_max_tokens_exceeds_generic_assist_default():
    from services.assist import MAX_OUTPUT_TOKENS

    assert _INVITE_RESEARCH_MAX_TOKENS > MAX_OUTPUT_TOKENS


def test_invite_draft_looks_complete_with_join_primary():
    draft = (
        'Hi Alex,\n\n'
        'We would love your perspective on governance patterns.\n\n'
        'Join us here:\n[JOIN_PRIMARY]'
    )
    assert invite_draft_looks_complete(draft) is True


def test_invite_draft_looks_complete_rejects_mid_sentence_truncation():
    assert invite_draft_looks_complete('Hi Pat,\n\nand capturing signals from practice') is False


def test_invite_draft_looks_complete_accepts_sentence_endings():
    assert invite_draft_looks_complete('Hi Pat,\n\nHope to see you soon.') is True
    assert invite_draft_looks_complete('Thanks for considering this!') is True
