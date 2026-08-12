"""Unit tests for workgroup invite join placeholder substitution."""
from services.platform_invitation_mail import (
    build_multi_workgroup_invite_plain_body,
    invite_body_uses_join_placeholders,
    substitute_workgroup_join_placeholders,
)

LINKS = [
    {'workgroup_name': 'Primary WG', 'landing_url': 'https://gov.example/invite/primary'},
    {'workgroup_name': 'Extra WG', 'landing_url': 'https://gov.example/invite/extra1'},
]


def test_invite_body_uses_join_placeholders_detects_primary():
    assert invite_body_uses_join_placeholders('Join here: [JOIN_PRIMARY]') is True


def test_invite_body_uses_join_placeholders_detects_extra():
    assert invite_body_uses_join_placeholders('Also: [JOIN_EXTRA_1]') is True


def test_invite_body_uses_join_placeholders_false_for_plain_text():
    assert invite_body_uses_join_placeholders('Join our workgroup when you can.') is False


def test_substitute_join_primary():
    body = 'Please join here: [JOIN_PRIMARY] — thanks!'
    out = substitute_workgroup_join_placeholders(body, LINKS)
    assert out == 'Please join here: https://gov.example/invite/primary — thanks!'


def test_substitute_join_extra_numbered():
    body = 'Primary: [JOIN_PRIMARY]\nExtra: [JOIN_EXTRA_1]'
    out = substitute_workgroup_join_placeholders(body, LINKS)
    assert 'https://gov.example/invite/primary' in out
    assert 'https://gov.example/invite/extra1' in out
    assert '[JOIN_' not in out


def test_substitute_join_case_insensitive():
    body = 'Link: [join_primary]'
    out = substitute_workgroup_join_placeholders(body, LINKS)
    assert out == 'Link: https://gov.example/invite/primary'


def test_substitute_strips_unmatched_extra_placeholder():
    body = 'Only primary [JOIN_PRIMARY] and missing [JOIN_EXTRA_9]'
    out = substitute_workgroup_join_placeholders(body, LINKS)
    assert out == 'Only primary https://gov.example/invite/primary and missing '


def test_plain_body_omits_appended_links_when_inline():
    plain = build_multi_workgroup_invite_plain_body(
        invitee_name='Alex',
        body_text='Join: https://gov.example/invite/primary',
        links=LINKS,
        inline_join_links=True,
    )
    assert 'Join link(s):' not in plain
    assert 'https://gov.example/invite/primary' in plain


def test_plain_body_appends_links_when_not_inline():
    plain = build_multi_workgroup_invite_plain_body(
        invitee_name='Alex',
        body_text='Would love your perspective.',
        links=LINKS,
        inline_join_links=False,
    )
    assert 'Join link(s):' in plain
    assert '- Primary WG: https://gov.example/invite/primary' in plain


def test_plain_body_skips_greeting_when_body_already_has_one():
    plain = build_multi_workgroup_invite_plain_body(
        invitee_name='Daveed Benjamin',
        body_text='Hi Daveed,\n\nOur many conversations...',
        links=LINKS,
        inline_join_links=True,
    )
    assert plain.count('Hi ') == 1
    assert plain.startswith('Hi Daveed,')
    assert 'Hi Daveed Benjamin' not in plain


def test_plain_body_adds_greeting_when_body_missing_one():
    plain = build_multi_workgroup_invite_plain_body(
        invitee_name='Daveed Benjamin',
        body_text='Our many conversations...',
        links=LINKS,
        inline_join_links=True,
    )
    assert plain.startswith('Hi Daveed Benjamin,')


def test_plain_body_omits_sign_in_email_note():
    plain = build_multi_workgroup_invite_plain_body(
        invitee_name='Alex',
        body_text='Would love your perspective.',
        links=LINKS,
        inline_join_links=False,
    )
    assert 'same email' not in plain.lower()
    assert 'signing in' not in plain.lower()
