"""Shared config for DP Challenge and Suggest an Edit (same hub + read UI, different labels/filters)."""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

ProposalMode = Literal['dp', 'document']

PROPOSAL_MODES: Dict[ProposalMode, Dict[str, Any]] = {
    'dp': {
        'scope': 'dp',
        'feature_flag': 'dp_proposals',
        'hub_path': '/dp-challenge/',
        'recent_api_path': '/api/dp-challenge/recent',
        'page_title': 'DP Challenge',
        'page_tagline': 'Your line can become the standard — propose edits on DP drafts.',
        'breadcrumb': 'DP Challenge',
        'icon': 'fa-highlighter',
        'picker_empty': 'No approved DP drafts yet',
        'picker_placeholder': 'Choose a DP draft…',
        'cta_button': 'Start a DP Proposal',
        'read_button': 'Read & propose',
        'hero_aria': 'How to submit a DP proposal: read the draft, select a sentence, and propose a clearer replacement.',
        'hero_image': '/static/images/dp-challenge-hero.png',
        'stat_docs_label': 'DPs with activity',
        'contributor_docs_col': 'DPs touched',
        'show_dp_column': True,
        'show_hero': True,
        'empty_docs': (
            'No proposals yet. Open a DP draft, select a sentence, and be the first to suggest a change.'
        ),
        'empty_contributors': 'No contributors yet. Be the first to propose an edit on a DP draft.',
        'labels': {
            'pending_status': 'DP Proposal',
            'pending_plural': 'DP Proposals',
            'accepted_status': 'Amendment',
            'accepted_plural': 'Amendments',
            'compose_title': 'Suggest a DP Proposal',
            'list_title': 'Proposals on this passage',
            'list_add': 'Suggest a DP Proposal',
            'post_button': 'Post proposal',
            'create_hover': 'Suggest a DP Proposal',
            'link_prefix': 'DP Proposal',
            'toast_new': 'New proposal',
            'toast_accepted': 'Amendment accepted',
            'toolbar_label': 'DP Props',
            'toolbar_visibility_title': 'DP Props visibility',
            'toolbar_select_aria': 'DP Props display',
            'display_near': 'Near proposal',
            'count_word': 'proposal',
            'location_not_found': 'location not found in document',
        },
    },
    'document': {
        'scope': 'document',
        'feature_flag': 'document_edits',
        'hub_path': '/suggest-edit/',
        'recent_api_path': '/api/suggest-edit/recent',
        'page_title': 'Suggest an Edit',
        'page_tagline': 'Help refine living documents — select a sentence and propose clearer wording.',
        'breadcrumb': 'Suggest an Edit',
        'icon': 'fa-pen-fancy',
        'picker_empty': 'No approved documents yet',
        'picker_placeholder': 'Choose a document…',
        'cta_button': 'Start a suggested edit',
        'read_button': 'Read & suggest',
        'hero_aria': 'How to suggest an edit: read the document, select a sentence, and propose clearer wording.',
        'hero_image': '/static/images/suggest-edit-hero.png',
        'stat_docs_label': 'Documents with activity',
        'contributor_docs_col': 'Docs touched',
        'show_dp_column': False,
        'show_hero': True,
        'empty_docs': (
            'No suggested edits yet. Open a document, select a sentence, and be the first to suggest a change.'
        ),
        'empty_contributors': 'No contributors yet. Be the first to suggest an edit on a document.',
        'labels': {
            'pending_status': 'Suggested edit',
            'pending_plural': 'Suggested edits',
            'accepted_status': 'Amendment',
            'accepted_plural': 'Amendments',
            'compose_title': 'Suggest an edit',
            'list_title': 'Edits on this passage',
            'list_add': 'Suggest an edit',
            'post_button': 'Post suggestion',
            'create_hover': 'Suggest an edit',
            'link_prefix': 'Suggested edit',
            'toast_new': 'New suggested edit',
            'toast_accepted': 'Amendment accepted',
            'toolbar_label': 'Edits',
            'toolbar_visibility_title': 'Suggested edits visibility',
            'toolbar_select_aria': 'Suggested edits display',
            'display_near': 'Near edit',
            'count_word': 'edit',
            'location_not_found': 'location not found in document',
        },
    },
}


def get_proposal_mode(mode: str) -> Dict[str, Any]:
    key = mode if mode in PROPOSAL_MODES else 'dp'
    return PROPOSAL_MODES[key]  # type: ignore[index]


def proposal_mode_for_submission(submission) -> ProposalMode:
    from services.dp_proposals import is_dp_submission

    return 'dp' if is_dp_submission(submission) else 'document'


def mode_labels(mode: ProposalMode) -> Dict[str, str]:
    return dict(get_proposal_mode(mode)['labels'])


def is_mode_enabled(mode: ProposalMode) -> bool:
    from services.product_rollout import is_feature_enabled

    return is_feature_enabled(get_proposal_mode(mode)['feature_flag'])
