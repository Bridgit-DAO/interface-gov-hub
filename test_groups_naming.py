"""Tests for DP workgroup display naming."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from services.groups import (
    DP_DESCRIPTIONS,
    extract_dp_number,
    format_dp_display_name,
    strip_workgroup_suffix,
)


def test_extract_dp_number():
    assert extract_dp_number('dp1-federated-auth') == 1
    assert extract_dp_number('dp21-multi-modal') == 21
    assert extract_dp_number('ml-governance') is None
    assert extract_dp_number('governance') is None


def test_strip_workgroup_suffix():
    assert strip_workgroup_suffix('Commerce Working Group') == 'Commerce'
    assert strip_workgroup_suffix('Interface Governance Workgroup') == 'Interface Governance'
    assert strip_workgroup_suffix('DP1 - Federated Authentication') == 'DP1 - Federated Authentication'


def test_format_dp_display_name():
    assert format_dp_display_name(
        'dp1-federated-auth',
        'Federated Authentication & Accountability',
    ) == 'DP1 - Federated Authentication & Accountability'
    assert format_dp_display_name(
        'dp6-commerce',
        'Commerce Working Group',
    ) == 'DP6 - Commerce'
    assert format_dp_display_name('ml-governance', 'Interface Governance Workgroup') == 'Interface Governance'
    assert format_dp_display_name('governance', 'Governance') == 'Governance'


def test_load_group_data_names():
    import services.groups as groups_mod
    importlib.reload(groups_mod)
    by_acronym = {g['acronym']: g['name'] for g in groups_mod.load_group_data()}
    assert by_acronym['dp1-federated-auth'] == 'DP1 - Federated Authentication & Accountability'
    assert by_acronym['dp21-multi-modal'] == 'DP21 - Multi-modal'
    assert by_acronym['ml-governance'] == 'Interface Governance'
    assert ' Working Group' not in ' '.join(by_acronym.values())
    assert ' Workgroup' not in ' '.join(by_acronym.values())


def test_all_dp_descriptions_have_titles():
    for acronym, info in DP_DESCRIPTIONS.items():
        assert extract_dp_number(acronym) is not None
        assert info['title']
