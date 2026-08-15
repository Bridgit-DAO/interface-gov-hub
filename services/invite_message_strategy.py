"""Per-contact message strategy for DP admin Zoho batch invites."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

META_LAYER_CUTOFF = date(2024, 9, 16)

MessageStrategy = Literal['long_gap_reconnect', 'recent_follow_up', 'custom']
VALID_STRATEGIES = frozenset({'long_gap_reconnect', 'recent_follow_up', 'custom'})


def _parse_last_contact_date(last_contact: str) -> Optional[date]:
    cleaned = (last_contact or '').strip()
    if not cleaned:
        return None
    date_part = cleaned[:10]
    try:
        return datetime.strptime(date_part, '%Y-%m-%d').date()
    except ValueError:
        return None


def suggest_message_strategy(last_contact: str) -> MessageStrategy:
    """Suggest outreach tone from last meta-layer contact date."""
    contact_date = _parse_last_contact_date(last_contact)
    if contact_date is None:
        return 'long_gap_reconnect'
    if contact_date < META_LAYER_CUTOFF:
        return 'long_gap_reconnect'
    return 'recent_follow_up'


def normalize_message_strategy(value: str) -> Optional[MessageStrategy]:
    raw = (value or '').strip().lower()
    if raw in VALID_STRATEGIES:
        return raw  # type: ignore[return-value]
    return None


def strategy_label(strategy: str) -> str:
    labels = {
        'long_gap_reconnect': 'Long-gap reconnection',
        'recent_follow_up': 'Recent follow-up',
        'custom': 'Custom',
    }
    return labels.get((strategy or '').strip().lower(), strategy)


def strategy_prompt_block(strategy: str, *, confirmed: bool) -> str:
    """LLM guidance block for confirmed admin message strategy."""
    if not confirmed:
        return ''

    key = (strategy or '').strip().lower()
    if key == 'long_gap_reconnect':
        return (
            'MESSAGE STRATEGY (long-gap reconnection – admin confirmed):\n'
            'Open with a warm reconnection tone. Include something like: '
            '"It\'s been a long time. I hope you are well. Since we\'ve been in touch, I\'ve been cooking."\n'
            'Then briefly catch them up on the Meta-Layer arc:\n'
            '- After the Metaweb book (late 2023), the Meta-Layer Initiative kicked off.\n'
            '- Vint Cerf challenged us on Desirable Properties of a layered web.\n'
            '- Two calls for input produced a solid 0.77 version; we are launching digital 1.0 on '
            'September 16, 2026 (the two-year kickoff anniversary).\n'
            'Invite them to use the community AI assistant; offer an individual conversation '
            '(5–10 minutes to a couple of hours); and invite them to join or lead a workgroup.\n'
            'Weave in Zoho email history naturally – do not sound like a form letter.'
        )
    if key == 'recent_follow_up':
        return (
            'MESSAGE STRATEGY (recent follow-up – admin confirmed):\n'
            'Assume more shared context from contact within the past ~2 years (since September 16, 2024). '
            'Use a shorter, warmer follow-up tone – reference recent threads or subjects when available. '
            'Skip the long Meta-Layer history recap unless a single tight line adds value. '
            'Lead quickly into the workgroup invitation and current Desirable Properties momentum.'
        )
    if key == 'custom':
        return (
            'MESSAGE STRATEGY (custom – admin confirmed):\n'
            'Follow extra_guidance and Zoho context; no default long-gap or recent-follow-up template.'
        )
    return ''
