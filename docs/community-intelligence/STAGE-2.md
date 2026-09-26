# Coordination increment

Builds on foundation commit `37e7058`. This increment adds working, evidence-scoped discussions and owner-confirmed next actions. It does not claim that the complete pilot or live AI integration is finished.

## Implemented

- Start a persisted discussion directly from a reviewed, layer-shared need/offer suggestion. The server validates both claims, organizations, matching topic, source policies, current programs and revisions.
- Choose up to 20 other participants by exact username. They must already be active layer members. The creator is included. Audience membership is immutable; no expansion route exists. No invitation messages or notifications are sent.
- Post attributed contributions. Only fixed participants who remain active layer members can list/read/write the room. Private organization evidence is excluded even when the asker has personal access to it.
- Request a deterministic, source-backed facilitation guide. It cites the room's reviewed passages and prompts participants to resolve capacity, timing, disagreement and next steps. It is clearly labeled rule-based, does not claim consensus, and does not call a live model.
- Propose an action for a room participant. The action stays tentative until that exact user accepts it. A creator, steward or global administrator cannot accept for somebody else. Acceptance records time and revision and conveys personal acceptance only, not organizational authority or partnership consent.
- Download a private, attributed Markdown proposal draft and open the existing `/submit/?layer_id=...` workflow. Draft review and upload remain explicit human steps; nothing is auto-published and no parallel proposal-decision system was introduced.
- Changes to source/claim/program revisions, retirement, or access make the dependent room stale. Its title, participants, messages, actions and citations are withheld, and new writes/export are blocked. Republishing a source does not reopen old history. Start a new room with current evidence.
- Source removal deletes dependent stored messages/actions and clears the room title, in the same transaction as original/claim removal. Minimal dependency IDs remain. This conservatively removes the whole affected conversation's content, including human messages, since they can quote removed evidence.
- Idempotency keys deduplicate room/message/action creation. Conditional source/program/membership writes serialize discussion writes with withdrawal and retirement. Final response checks discard prepared responses if evidence is revoked mid-request.

## Why not use WorkgroupMessage directly?

`routes/workgroups.py` and `services/workgroup_chat.py` expose a member chat with non-member teasers. They have no evidence dependency policy. Putting source-derived content there would make it readable through unrelated routes. The new room tables reuse existing User and LayerMember identity, but keep evidence-dependent history behind one policy boundary. An audited future workgroup adapter can link rooms without copying protected text into teaser-enabled chat.

## New data and migration

`CIRoom`: layer, creator, immutable member IDs, title, dependency snapshots and request key.
`CIRoomMessage`: room, attributed requester/author, human or facilitator kind, text, request key and time.
`CIAction`: room, proposer, proposed owner, proposed/accepted/declined status, acceptance time and revision.

The existing additive `community-migrate` command now also creates these three tables. Re-run it against the backed-up development database before enabling the new code. It creates missing tables without altering existing columns. No deployed database was migrated during this task.

## API additions

All suffixes are under `/api/layers/<layer_id>/community`; existing session, layer, CSRF and no-store checks apply.

| Method | Suffix | Result |
|---|---|---|
| GET / POST | `/rooms/` | Authorized room list / create from two claim IDs and member usernames |
| GET | `/rooms/<id>/` | Full authorized discussion or content-free stale notice |
| POST | `/rooms/<id>/messages/` | Attributed contribution |
| POST | `/rooms/<id>/facilitate/` | Deterministic sourced guide |
| POST | `/rooms/<id>/actions/` | Tentative owner-specific action |
| PATCH | `/rooms/<id>/actions/<action_id>/` | Proposed owner accepts/declines against the current revision |
| GET | `/rooms/<id>/proposal-draft/` | Private review draft attachment, revalidated before delivery |

Room lists are limited to the latest 100 authorized rooms; each room has a 200-message and 100-action cap. JSON membership filtering uses the existing SQLite runtime's `json_each`. General database portability and pagination are later work.

## Validation

- **21 feature/coordination tests passed**, including all 15 foundation tests and six coordination scenarios.
- **13 existing regression checks passed** against an isolated synthetic database.
- Browser verification: opened a reviewed suggestion, created a fixed three-participant room, and posted an attributed contribution while preserving unresolved capacity and timing.
- No live Hermes/model calls, external messages, remote data migrations or deployments.

Run:

```sh
FLASK_ENV=development GOVHUB_SKIP_SHARED_DB_MIGRATIONS=1 \
  .venv-community/bin/python -m pytest test_community_intelligence.py test_community_rooms.py -q --disable-warnings
.venv-community/bin/python scripts/community_regression.py
COMMUNITY_DEMO_PORT=5001 .venv-community/bin/python scripts/community_demo.py
```

## Remaining work

Live Hermes orchestration with narrow authenticated tools and configured-model evaluation; successful OCR and safe public URL ingestion; persistent opportunity status/dismissal workflows; organization-authorized decisions beyond personal action acceptance; direct governed proposal handoff after private-draft permissions are audited; newsletter/RSS adapters, digests, and federation. Current room creation persists the exploration context, but suggestions themselves remain computed rule-based matches rather than a full opportunity lifecycle.
