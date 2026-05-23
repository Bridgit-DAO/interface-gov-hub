#!/usr/bin/env python3
"""Unit checks for bridge relationship types (strict, pre-launch API)."""
import sys

sys.path.insert(0, '.')

from routes.bridges import (
    DEFAULT_RELATIONSHIP,
    RELATIONSHIP_TYPES,
    parse_bridge_relationship,
)


def test_relationship_types_frozen_set():
    assert RELATIONSHIP_TYPES == frozenset({
        'cites', 'contradicted_by', 'supported_by', 'related_to',
    })


def test_parse_canonical():
    for v in RELATIONSHIP_TYPES:
        out, err = parse_bridge_relationship(v, default_if_missing=False)
        assert err is None and out == v


def test_parse_default_when_missing():
    out, err = parse_bridge_relationship(None, default_if_missing=True)
    assert err is None and out == DEFAULT_RELATIONSHIP
    out, err = parse_bridge_relationship('', default_if_missing=True)
    assert err is None and out == DEFAULT_RELATIONSHIP


def test_parse_rejects_unknown():
    out, err = parse_bridge_relationship('contradicts', default_if_missing=False)
    assert out is None and err is not None
    out, err = parse_bridge_relationship('supports', default_if_missing=True)
    assert out is None and err is not None


def test_parse_requires_value_when_no_default():
    out, err = parse_bridge_relationship(None, default_if_missing=False)
    assert out is None and err is not None


if __name__ == '__main__':
    test_relationship_types_frozen_set()
    test_parse_canonical()
    test_parse_default_when_missing()
    test_parse_rejects_unknown()
    test_parse_requires_value_when_no_default()
    print('test_bridge_relationships: ok')
