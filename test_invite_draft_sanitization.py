"""Unit tests for invite draft body sanitization."""
from services.platform_invitation_mail import sanitize_invite_email_body


def test_sanitize_removes_join_primary_marker():
    body = (
        'Hi Shambhavi,\n\n'
        'I would love for you to join our Security and Provenance workgroup.\n\n'
        'Best,\nDaveed\n\n'
        '[JOIN_PRIMARY]'
    )
    cleaned = sanitize_invite_email_body(body)
    assert '[JOIN_PRIMARY]' not in cleaned
    assert 'Security and Provenance' in cleaned
    assert cleaned.endswith('Daveed')


def test_sanitize_removes_join_extra_markers():
    body = 'Primary invite.\n\nExtra: [JOIN_EXTRA_1]\n[JOIN_PRIMARY]'
    cleaned = sanitize_invite_email_body(body)
    assert '[JOIN_' not in cleaned.upper()


def test_sanitize_removes_bracket_stage_direction_lines():
    body = (
        'Email is off.\n\n'
        'Hi Shambhavi,\n\n'
        'Our work on provenance continues to deepen.\n\n'
        '[Then workgroup invitation - lead with primary]\n'
        'Join the DP15 Security and Provenance workgroup.\n\n'
        '[Close warmly, reference shared interests]\n'
        'Hope to see you there.\n\n'
        'Best,\nDaveed'
    )
    cleaned = sanitize_invite_email_body(body)
    assert 'Email is off' not in cleaned
    assert '[Then workgroup' not in cleaned
    assert '[Close warmly' not in cleaned
    assert 'Hi Shambhavi,' in cleaned
    assert 'provenance continues' in cleaned


def test_sanitize_removes_inline_stage_direction_brackets():
    body = (
        'Hi Pat,\n\n'
        'Great catching up [Close warmly, reference shared interests] about governance.\n\n'
        'Best,\nPat'
    )
    cleaned = sanitize_invite_email_body(body)
    assert '[Close warmly' not in cleaned
    assert 'Great catching up' in cleaned
    assert 'about governance' in cleaned


def test_sanitize_removes_prompt_label_leaks():
    body = (
        'MESSAGE STRATEGY (long-gap reconnection – admin confirmed):\n'
        'Open with a warm reconnection tone.\n\n'
        'Hi Alex,\n\n'
        'It has been a while since we connected.\n\n'
        'Best,\nAlex'
    )
    cleaned = sanitize_invite_email_body(body)
    assert 'MESSAGE STRATEGY' not in cleaned
    assert 'Hi Alex,' in cleaned


def test_sanitize_strips_llm_reasoning_after_sign_off():
    """Abeed sample: planning checklist leaked after Daveed sign-off."""
    body = (
        'Hi Abeed,\n\n'
        'It has been a long time. I hope you are well.\n\n'
        'Hope to hear from you soon.\n\n'
        'Daveed\n\n'
        'Let me check requirements:\n'
        '- "Hi Abeed," - ✓\n'
        '- Natural calendar dates - ✓\n'
        'Let me finalize:'
    )
    cleaned = sanitize_invite_email_body(body)
    assert cleaned.endswith('Daveed')
    assert 'Let me check' not in cleaned
    assert 'Let me finalize' not in cleaned
    assert '✓' not in cleaned


def test_sanitize_strips_inline_planning_mid_draft():
    body = (
        'Hi Pat,\n\n'
        'Warm opening about the Meta-Layer arc.\n\n'
        'Let me reconsider the tone and expand this.\n\n'
        'More draft text that should be removed.'
    )
    cleaned = sanitize_invite_email_body(body)
    assert 'Let me reconsider' not in cleaned
    assert cleaned.endswith('Warm opening about the Meta-Layer arc.')


def test_sanitize_preserves_event_urls_in_brackets():
    body = (
        'Hi Pat,\n\n'
        'See our event at https://desirableproperties.org/events/fork.\n\n'
        'Best,\nPat'
    )
    cleaned = sanitize_invite_email_body(body)
    assert 'https://desirableproperties.org/events/fork' in cleaned
