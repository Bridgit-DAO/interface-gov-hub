# EventLog event_type audit

Single source of truth: `services/event_registry.py` (`REGISTERED_EVENT_TYPES`).

All `emit_event(...)` call sites should use a key defined there. If you add a new event:

1. Add a row to `REGISTERED_EVENT_TYPES` with `show_in_layer_feed` and optional `document_follow_category` (legacy grouping label only).
2. Emit via `services.events.emit_event`.
3. If users should be able to **follow** this event on a draft, ensure dispatch uses that exact `event_type` and that `services/event_subscriptions.py` includes it in `DRAFT_EVENT_TYPES` / `LEVEL_TO_EVENT_TYPES` so presets stay consistent.

## emit_event call sites (codebase audit)

| event_type | Module / location |
|------------|-------------------|
| `layer_config_changed` | `routes/layers.py` (patch layer) |
| `contribution_type_filter_applied` | `routes/layers.py` |
| `guild_layer_linked` | `routes/layers.py`, `routes/guilds.py` |
| `guild_layer_unlinked` | `routes/layers.py`, `routes/guilds.py` |
| `member_joined` / `member_removed` | `routes/layers.py` |
| `workgroup_member_joined` / `workgroup_member_left` | `services/workgroup_membership.py` |
| `artifact_collection_created` / `artifact_collection_item_added` | `routes/collections.py` |
| `brick_placed` | `routes/civic_mason.py` |
| `draft_comment_added` | `routes/documents.py` |
| `draft_submission_approved` / `draft_revision_approved` / `draft_published_as_rfc` | `routes/submissions.py` |
| `artifact_created` / `artifact_updated` / `artifact_status_changed` / `artifact_linked` / `contribution_type_set` / `contribution_type_cleared` / `quest_created` / `monument_created` | `routes/artifacts.py` |
| `artifact_created` | `services/artifact.py` |
| `vote_started` / `vote_closed` / `role_claimed` (system) | `services/coordination.py` |
| `ballot_cast` / `vote_candidate_added` / `vote_candidate_withdrawn` | `routes/votes.py` |
| `role_claimed` | `routes/roles.py`, `services/coordination.py` (election) |
| `waitlist_joined` / `waitlist_left` | `routes/waitlists.py` |
| `guild_artifact_linked` / `guild_artifact_unlinked` | `routes/guilds.py` |
| `badge_nominated` / `badge_approved` / `badge_rejected` | `routes/roles.py` |

Layer activity feed excludes types where `show_in_layer_feed` is false (see `EXCLUDED_FROM_ACTIVITY_FEED`).
