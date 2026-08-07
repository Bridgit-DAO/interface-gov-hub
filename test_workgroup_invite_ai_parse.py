"""Unit tests for AI invite LLM JSON extraction."""
import json

import pytest

from services.workgroup_invite_ai import _parse_json_object


SAMPLE = {
    'ambiguous': False,
    'candidates': [],
    'resolved_person': {
        'name': 'Mike Witmore',
        'headline': 'Director',
        'summary': 'Scholar of Shakespeare.',
        'expertise_tags': ['literature'],
    },
    'suggested_workgroups': [],
}


def test_parse_plain_json():
    assert _parse_json_object(json.dumps(SAMPLE))['resolved_person']['name'] == 'Mike Witmore'


def test_parse_markdown_fenced_json():
    raw = f"```json\n{json.dumps(SAMPLE, indent=2)}\n```"
    assert _parse_json_object(raw)['ambiguous'] is False


def test_parse_trailing_commentary_extra_data():
    # Reproduces: json.JSONDecodeError Extra data: line N column 1
    raw = json.dumps(SAMPLE, indent=2) + "\n\nHere is a brief note about confidence."
    parsed = _parse_json_object(raw)
    assert parsed['resolved_person']['name'] == 'Mike Witmore'


def test_parse_leading_prose_then_object():
    raw = "Sure, here is the analysis:\n" + json.dumps(SAMPLE)
    assert _parse_json_object(raw)['candidates'] == []


def test_parse_fenced_with_trailing_text():
    raw = f"```json\n{json.dumps(SAMPLE)}\n```\nHope this helps!"
    assert _parse_json_object(raw)['suggested_workgroups'] == []


def test_parse_nested_braces_in_strings():
    payload = {
        **SAMPLE,
        'resolved_person': {
            **SAMPLE['resolved_person'],
            'summary': 'Wrote about {meta} and "quotes".',
        },
    }
    raw = "Result:\n" + json.dumps(payload) + "\nDone."
    assert '{meta}' in _parse_json_object(raw)['resolved_person']['summary']


def test_parse_rejects_non_object():
    with pytest.raises(json.JSONDecodeError):
        _parse_json_object('[1, 2, 3]')


def test_parse_rejects_empty():
    with pytest.raises(json.JSONDecodeError):
        _parse_json_object('   ')
