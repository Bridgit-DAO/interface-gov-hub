"""
Canonical registry for EventLog event_type values.

Unknown types still append to EventLog (forward-compatible); emit_event logs a debug warning.
See docs/EVENT_TYPES.md for the audit table synced from this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional


@dataclass(frozen=True)
class EventTypeDef:
    """Metadata for governance events."""

    label: str
    show_in_layer_feed: bool
    # Legacy grouping label; document-follow delivery uses exact event_type + UserEventSubscription rows.
    document_follow_category: Optional[str] = None


# document_follow_category is historical grouping; subscriptions match REGISTERED_EVENT_TYPES keys per draft.

REGISTERED_EVENT_TYPES: Dict[str, EventTypeDef] = {
    # —— Document / draft (Meta-Layer submissions) ——
    'draft_comment_added': EventTypeDef('Comment on draft', True, 'comment'),
    'draft_submission_approved': EventTypeDef('Draft approved (initial)', True, 'state_change'),
    'draft_revision_approved': EventTypeDef('Draft revision approved', True, 'revision'),
    'draft_published_as_rfc': EventTypeDef('Draft published as RFC', True, 'major_change'),
    # —— Layer / membership ——
    'layer_config_changed': EventTypeDef('Layer configuration changed', True, None),
    'member_joined': EventTypeDef('Member joined layer', True, None),
    'member_removed': EventTypeDef('Member left layer', True, None),
    'contribution_type_filter_applied': EventTypeDef('Contribution filter used', False, None),
    # —— Guilds ——
    'guild_layer_linked': EventTypeDef('Guild linked to layer', True, None),
    'guild_layer_unlinked': EventTypeDef('Guild unlinked from layer', True, None),
    'guild_artifact_linked': EventTypeDef('Guild linked to artifact', True, None),
    'guild_artifact_unlinked': EventTypeDef('Guild unlinked from artifact', True, None),
    # —— Artifacts ——
    'artifact_created': EventTypeDef('Artifact created', True, None),
    'artifact_updated': EventTypeDef('Artifact updated', True, None),
    'artifact_status_changed': EventTypeDef('Artifact status changed', True, None),
    'artifact_linked': EventTypeDef('Artifact linked', True, None),
    'contribution_type_set': EventTypeDef('Contribution type set', True, None),
    'contribution_type_cleared': EventTypeDef('Contribution type cleared', True, None),
    'quest_created': EventTypeDef('Quest created', True, None),
    'monument_created': EventTypeDef('Monument created', True, None),
    # —— Collections ——
    'artifact_collection_created': EventTypeDef('Collection created', True, None),
    'artifact_collection_item_added': EventTypeDef('Item added to collection', True, None),
    # —— Votes / roles / coordination ——
    'vote_started': EventTypeDef('Vote started', True, None),
    'vote_closed': EventTypeDef('Vote closed', True, None),
    'ballot_cast': EventTypeDef('Ballot cast', True, None),
    'vote_candidate_added': EventTypeDef('Vote candidate added', True, None),
    'vote_candidate_withdrawn': EventTypeDef('Vote candidate withdrawn', True, None),
    'role_claimed': EventTypeDef('Role claimed', True, None),
    # —— Waitlists ——
    'waitlist_joined': EventTypeDef('Waitlist joined', True, None),
    'waitlist_left': EventTypeDef('Waitlist left', True, None),
    # —— Civic Mason ——
    'brick_placed': EventTypeDef('Brick placed', True, None),
    # —— Badges ——
    'badge_nominated': EventTypeDef('Badge nominated', True, None),
    'badge_approved': EventTypeDef('Badge approved', True, None),
    'badge_rejected': EventTypeDef('Badge rejected', True, None),
}


def is_registered_event_type(event_type: str) -> bool:
    return event_type in REGISTERED_EVENT_TYPES


def get_event_def(event_type: str) -> Optional[EventTypeDef]:
    return REGISTERED_EVENT_TYPES.get(event_type)


EXCLUDED_FROM_ACTIVITY_FEED: FrozenSet[str] = frozenset(
    name for name, defn in REGISTERED_EVENT_TYPES.items() if not defn.show_in_layer_feed
)
