"""Invite research disambiguation fallbacks."""
from services.workgroup_invite_ai import _finalize_research_analysis


def test_ambiguous_without_candidates_uses_linkedin_anchor():
    ambiguous, candidates, resolved = _finalize_research_analysis(
        {'ambiguous': True, 'candidates': [], 'resolved_person': None},
        name='Jane Doe',
        linkedin_url='linkedin.com/in/janedoe',
    )
    assert ambiguous is False
    assert candidates == []
    assert resolved['name'] == 'Jane Doe'
    assert 'linkedin.com/in/janedoe' in resolved['source_urls'][0]


def test_ambiguous_with_single_resolved_person_is_cleared():
    ambiguous, candidates, resolved = _finalize_research_analysis(
        {
            'ambiguous': True,
            'candidates': [],
            'resolved_person': {
                'name': 'Jane Doe',
                'headline': 'Engineer',
                'summary': 'Built things.',
                'expertise_tags': ['engineering'],
            },
        },
        name='Jane Doe',
        linkedin_url='https://linkedin.com/in/janedoe',
    )
    assert ambiguous is False
    assert resolved['headline'] == 'Engineer'


def test_true_disambiguation_keeps_candidates():
    ambiguous, candidates, _resolved = _finalize_research_analysis(
        {
            'ambiguous': True,
            'candidates': [
                {'name': 'Jane Doe', 'headline': 'A', 'source_urls': []},
                {'name': 'Jane Doe', 'headline': 'B', 'source_urls': []},
            ],
            'resolved_person': None,
        },
        name='Jane Doe',
    )
    assert ambiguous is True
    assert len(candidates) == 2
