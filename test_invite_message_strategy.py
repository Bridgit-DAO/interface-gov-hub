"""Per-contact invite message strategy helpers."""
from datetime import date

from services.invite_message_strategy import (
    META_LAYER_CUTOFF,
    strategy_prompt_block,
    suggest_message_strategy,
)


def test_meta_layer_cutoff_date():
    assert META_LAYER_CUTOFF == date(2024, 9, 16)


def test_suggest_long_gap_before_cutoff():
    assert suggest_message_strategy('2024-09-15') == 'long_gap_reconnect'
    assert suggest_message_strategy('2023-01-01T12:00:00+00:00') == 'long_gap_reconnect'


def test_suggest_recent_follow_up_on_or_after_cutoff():
    assert suggest_message_strategy('2024-09-16') == 'recent_follow_up'
    assert suggest_message_strategy('2026-06-15') == 'recent_follow_up'


def test_suggest_long_gap_when_last_contact_missing():
    assert suggest_message_strategy('') == 'long_gap_reconnect'


def test_strategy_prompt_block_requires_confirmation():
    assert strategy_prompt_block('long_gap_reconnect', confirmed=False) == ''
    assert strategy_prompt_block('recent_follow_up', confirmed=False) == ''


def test_strategy_prompt_block_long_gap_content():
    block = strategy_prompt_block('long_gap_reconnect', confirmed=True)
    assert 'long-gap reconnection' in block.lower()
    assert "it's been a long time" in block.lower()
    assert 'meta-layer initiative' in block.lower()
    assert 'vint cerf' in block.lower()
    assert 'september 16, 2026' in block.lower()


def test_strategy_prompt_block_recent_follow_up_content():
    block = strategy_prompt_block('recent_follow_up', confirmed=True)
    assert 'recent follow-up' in block.lower()
    assert 'september 16, 2024' in block.lower()
