"""Admin invite workgroup match normalization."""
from services.workgroup_invite_ai import _normalize_workgroup_matches


def test_normalize_workgroup_matches_sorts_by_score():
    catalog = {
        'wg-a': {'id': 'wg-a', 'name': 'DP Discovery', 'slug': 'dp-discovery'},
        'wg-b': {'id': 'wg-b', 'name': 'DP22 Civic Memory', 'slug': 'dp22-civic-memory'},
    }
    matches = _normalize_workgroup_matches(
        {
            'workgroup_matches': [
                {
                    'workgroup_id': 'wg-b',
                    'confidence': 'medium',
                    'score': 62,
                    'rationale': 'Strong civic memory fit.',
                },
                {
                    'workgroup_id': 'wg-a',
                    'confidence': 'high',
                    'score': 91,
                    'rationale': 'Best overall fit.',
                },
            ],
        },
        catalog,
    )
    assert [row['workgroup_id'] for row in matches] == ['wg-a', 'wg-b']
    assert matches[0]['confidence'] == 'high'
    assert matches[0]['score'] == 91


def test_normalize_workgroup_matches_ignores_unknown_ids():
    catalog = {
        'wg-a': {'id': 'wg-a', 'name': 'DP Discovery', 'slug': 'dp-discovery'},
    }
    matches = _normalize_workgroup_matches(
        {
            'workgroup_matches': [
                {'workgroup_id': 'missing', 'confidence': 'high', 'score': 99, 'rationale': ''},
                {'workgroup_id': 'wg-a', 'confidence': 'low', 'score': 30, 'rationale': 'ok'},
            ],
        },
        catalog,
    )
    assert len(matches) == 1
    assert matches[0]['workgroup_id'] == 'wg-a'
