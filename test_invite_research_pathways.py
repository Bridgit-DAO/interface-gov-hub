"""Invite research pathway helpers."""
from services.invite_research_pathways import build_pathway_context_bundle, pathway_name_search


def test_build_pathway_context_bundle_merges_search_and_url():
    bundle = build_pathway_context_bundle(
        search_results=[
            {
                'url': 'https://example.com/post',
                'title': 'Meta-layer essay',
                'rationale': 'Discusses layered web governance.',
            },
        ],
        url_author={
            'name': 'Jane Doe',
            'role': 'Researcher',
            'context': 'Writes about civic infrastructure.',
            'source_url': 'https://example.com/post',
            'suggested_email': 'jane@example.com',
        },
        page_summary='A long essay on governance.',
    )
    assert bundle['name'] == 'Jane Doe'
    assert bundle['email'] == 'jane@example.com'
    assert 'Meta-layer essay' in bundle['previous_interaction']
    assert 'https://example.com/post' in bundle['extra_links']


def test_build_pathway_context_bundle_extracts_linkedin_url():
    bundle = build_pathway_context_bundle(
        search_results=[
            {
                'url': 'https://www.linkedin.com/in/kpbarry/',
                'title': 'Kevin Barry',
                'snippet': 'Engineer',
            },
        ],
    )
    assert bundle['linkedin_url'] == 'https://www.linkedin.com/in/kpbarry/'


def test_pathway_name_search_requires_name():
    payload, status = pathway_name_search(name='')
    assert status == 400
    assert payload.get('error')
