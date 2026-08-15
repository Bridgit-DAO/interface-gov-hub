"""Invite research pathway helpers."""
from services.invite_research_pathways import (
    build_pathway_context_bundle,
    build_zoho_contact_context,
    format_contact_recency,
    infer_communication_style,
    pathway_name_search,
)


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


def test_infer_communication_style_detects_casual_warm():
    style = infer_communication_style(
        snippets=['Hey! Thanks so much – looking forward to the workshop.'],
        subjects=['Gov Hub follow-up'],
    )
    assert 'casual' in style['labels'] or 'warm' in style['labels']
    assert style['formality'] in {'casual', 'neutral'}


def test_infer_communication_style_detects_formal_technical():
    style = infer_communication_style(
        snippets=[
            'Dear Daveed, Please find attached the RFC schema draft for the interoperability protocol.',
        ],
        subjects=['Re: API implementation'],
    )
    assert 'formal' in style['labels']
    assert 'technical' in style['labels']


def test_build_zoho_contact_context_includes_history_fields():
    ctx = build_zoho_contact_context({
        'email': 'kevin@example.com',
        'name': 'Kevin',
        'message_count': 4,
        'last_contact': '2026-06-15T10:00:00+00:00',
        'sample_subjects': ['Meta-layer workshop', 'Gov Hub sync'],
        'snippets': ['Thanks for the governance conversation.'],
        'summary': 'Discussed layered web governance.',
    })
    assert ctx['message_count'] == 4
    assert ctx['last_contact'].startswith('2026-06-15')
    assert ctx['subjects'] == ['Meta-layer workshop', 'Gov Hub sync']
    assert ctx['communication_style']['labels']


def test_build_pathway_context_bundle_includes_zoho_contact_context():
    bundle = build_pathway_context_bundle(
        zoho_contact={
            'email': 'kevin@example.com',
            'name': 'Kevin',
            'message_count': 3,
            'last_contact': '2026-07-01',
            'sample_subjects': ['Workgroup invite'],
            'snippets': ['Great chat about interoperability.'],
            'summary': 'Meta-layer collaborator.',
        },
    )
    assert bundle['email'] == 'kevin@example.com'
    assert bundle['zoho_contact_context']
    assert bundle['zoho_contact_context']['message_count'] == 3
    assert 'Email history' in bundle['previous_interaction']
    assert 'communication style' in bundle['previous_interaction'].lower()


def test_build_zoho_contact_context_includes_strategy():
    ctx = build_zoho_contact_context({
        'email': 'kevin@example.com',
        'name': 'Kevin',
        'last_contact': '2023-05-01',
    })
    assert ctx['suggested_strategy'] == 'long_gap_reconnect'
    assert ctx['message_strategy'] == 'long_gap_reconnect'

    recent = build_zoho_contact_context({
        'email': 'kevin@example.com',
        'name': 'Kevin',
        'last_contact': '2025-01-01',
    })
    assert recent['suggested_strategy'] == 'recent_follow_up'


def test_format_contact_recency_phrases():
    assert 'week' in format_contact_recency('2026-08-10')
    assert 'while' in format_contact_recency('2024-01-01')
