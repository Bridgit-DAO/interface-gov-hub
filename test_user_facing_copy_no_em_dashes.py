"""Guard user-facing invite/workgroup copy against em dashes (U+2014)."""
from pathlib import Path

_EM = '\u2014'

# Paths relative to gov-hub-dev root; only strings users/support agents see in invite flows.
_USER_FACING_FILES = (
    'static/js/gh-invite.js',
    'services/dp_welcome.py',
    'data/support-runbooks.json',
    'services/workgroup_invite_ai.py',
)


def test_user_facing_copy_has_no_em_dashes():
    root = Path(__file__).resolve().parent
    offenders = []
    for rel in _USER_FACING_FILES:
        text = (root / rel).read_text(encoding='utf-8')
        if _EM in text:
            offenders.append(rel)
    assert not offenders, f'Em dash found in user-facing copy: {", ".join(offenders)}'
