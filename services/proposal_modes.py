"""Shared config for DP Challenge and Suggest an Edit (same hub + read UI, different labels/filters)."""
from __future__ import annotations

from typing import Any, Dict, Literal, Optional

ProposalMode = Literal['dp', 'document']

# User-facing vocabulary for sentence-level text changes (both DP and non-DP).
PATCH_LABELS: Dict[str, str] = {
    'pending_status': 'Patch',
    'pending_plural': 'Patches',
    'accepted_status': 'Merged',
    'accepted_plural': 'Merged',
    'compose_title': 'Propose a patch',
    'compose_tab': 'Patch',
    'guide_tab': 'Patch',
    'list_title': 'Patches on this passage',
    'list_add': 'Propose a patch',
    'post_button': 'Submit patch',
    'create_hover': 'Propose a patch',
    'link_prefix': 'Patch',
    'toast_new': 'New patch',
    'toast_accepted': 'Patch merged',
    'accept_button': 'Merge patch',
    'toolbar_label': 'Patches',
    'toolbar_visibility_title': 'Patches visibility',
    'toolbar_select_aria': 'Patches display',
    'display_near': 'Near patch',
    'count_word': 'patch',
    'hover_section': 'Patches',
    'proposed_label': 'Patched text',
    'location_not_found': 'location not found in document',
}

PROPOSAL_MODES: Dict[ProposalMode, Dict[str, Any]] = {
    'dp': {
        'scope': 'dp',
        'feature_flag': 'patches',
        'hub_path': '/dp-challenge/',
        'recent_api_path': '/api/dp-challenge/recent',
        'page_title': 'DP Challenge',
        'page_tagline': 'Your line can become the standard – propose patches on DP drafts.',
        'breadcrumb': 'DP Challenge',
        'icon': 'fa-highlighter',
        'picker_empty': 'No approved DP drafts yet',
        'picker_placeholder': 'Pick a DP draft to patch…',
        'cta_button': 'Propose a patch',
        'read_button': 'Read & patch',
        'hero_aria': 'How to propose a patch: read the draft, select a sentence, and submit clearer wording.',
        'hero_image_light': '/static/images/dp/dp-patch-light.png',
        'hero_image_dark': '/static/images/dp/dp-patch-dark.png',
        'stat_docs_label': 'DPs with activity',
        'contributor_docs_col': 'DPs touched',
        'show_dp_column': True,
        'show_hero': True,
        'empty_docs': (
            'No patches yet. Open a DP draft, select a sentence, and be the first to propose a patch.'
        ),
        'empty_contributors': 'No contributors yet. Be the first to propose a patch on a DP draft.',
        'labels': dict(PATCH_LABELS),
    },
    'document': {
        'scope': 'document',
        'feature_flag': 'patches',
        'hub_path': '/suggest-edit/',
        'recent_api_path': '/api/suggest-edit/recent',
        'page_title': 'Propose a Patch',
        'page_tagline': 'Help refine living documents – select a sentence and propose a patch.',
        'breadcrumb': 'Propose a Patch',
        'icon': 'fa-pen-fancy',
        'picker_empty': 'No approved documents yet',
        'picker_placeholder': 'Pick a document to patch…',
        'cta_button': 'Propose a patch',
        'read_button': 'Read & patch',
        'hero_aria': 'How to propose a patch: read the document, select a sentence, and submit clearer wording.',
        'hero_image_light': '/static/images/doc-patch-light.png',
        'hero_image_dark': '/static/images/doc-patch-dark.png',
        'stat_docs_label': 'Documents with activity',
        'contributor_docs_col': 'Docs touched',
        'show_dp_column': False,
        'show_hero': True,
        'empty_docs': (
            'No patches yet. Open a document, select a sentence, and be the first to propose a patch.'
        ),
        'empty_contributors': 'No contributors yet. Be the first to propose a patch on a document.',
        'labels': dict(PATCH_LABELS),
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
