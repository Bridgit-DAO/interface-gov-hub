"""Canonical artifact lifecycle for Meta-Layer soft launch (UI + API alignment).

See docs/META_LAYER_SOFT_LAUNCH_CANVAS.md §7.
"""

# Ordered pipeline (stored Artifact.status values)
ORDERED_STATUSES = (
    'draft',
    'under_review',
    'vote_scheduled',
    'vote_open',
    'approved',
    'implemented',
)

STATUS_UI_LABEL = {
    'draft': 'Draft',
    'under_review': 'In Review',
    'vote_scheduled': 'Vote Scheduled',
    'vote_open': 'Voting',
    'approved': 'Approved',
    'implemented': 'Implemented',
}

# One-line explainers for demo / artifact header (extend per product copy)
STAGE_EXPLAINER = {
    'draft': 'This contribution is not yet visible for review.',
    'under_review': (
        'This contribution is being discussed, challenged, and strengthened before a decision.'
    ),
    'vote_scheduled': 'Voting is scheduled; participants can prepare before ballots open.',
    'vote_open': 'This contribution is now open for decision.',
    'approved': 'The community approved this contribution.',
    'implemented': 'This contribution is reflected in implementation or follow-up work.',
}


def ui_label_for_status(stored: str) -> str:
    return STATUS_UI_LABEL.get((stored or '').strip().lower(), stored or 'Unknown')


def index_of_status(stored: str) -> int:
    key = (stored or '').strip().lower()
    try:
        return ORDERED_STATUSES.index(key)
    except ValueError:
        return -1


def allowed_artifact_actions(stored: str) -> dict:
    """
    Stub for primary artifact controls (wire to auth + is_layer_admin later).

    Returns flags used by demo templates / future Vue props.
    """
    s = (stored or '').strip().lower()
    in_review = s == 'under_review'
    voting = s == 'vote_open'
    return {
        'show_support': in_review or voting,
        'show_oppose': in_review or voting,
        'show_comment': in_review or s == 'vote_scheduled',
        'show_add_evidence': in_review or s == 'vote_scheduled',
        'show_abstain': voting,
        'show_move_to_voting': in_review,
        'show_review_readiness_modal': in_review or s == 'vote_scheduled',
        'show_readiness_panel': in_review,
        'show_voting_context_panel': voting or s == 'approved',
        'show_transition_callout': in_review,
    }


def can_open_voting_demo(user_is_layer_admin: bool) -> bool:
    """Placeholder until wired to coordination.is_layer_admin."""
    return bool(user_is_layer_admin)
