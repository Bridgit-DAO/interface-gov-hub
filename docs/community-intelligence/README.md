# Community Intelligence: foundation increment

Reviewed and implemented on 2026-09-25 against `Bridgit-DAO/interface-gov-hub`, branch `development`, commit `c3c408b34ec6f7b445406243789f5daae9c61dc7`. Local work branch: `codex/community-intelligence`.

This is a working local foundation, **not the completed Community Intelligence pilot**. It implements source submission, queued extraction, steward review/correction, access-controlled cited retrieval, lifecycle controls, removal, and simple need/offer suggestions. Group AI conversations, human-confirmed action/proposal handoff, live Hermes, OCR and continuous connectors remain unfinished.

## Briefing review

The briefing correctly treats ownership, permissions, source provenance, and durable retirement as foundational. Its major unresolved assumptions were the organization identity model, equivalence of existing claims/programs, installed Hermes interfaces, and deployment infrastructure. Inspection resolved the application structure but did not establish production runtime state or credentials.

The key implementation decisions are:

- Reuse existing users, sessions, active layer memberships, Flask routes, SQLAlchemy, the page shell and CSRF helpers.
- Keep organizational knowledge separate from existing role/badge claims and participation-cohort programs. Reusing those tables would assign the wrong ownership and lifecycle semantics.
- Add organization membership with administrator, steward and contributor roles. Creating a workspace is self-registration, not a verified real-world organization identity. Names do not auto-merge. Cross-layer organizational publication is through independently scoped source records; private source titles/counts do not appear to other organizations.
- Keep evidence and lifecycle records together in the transactional store in this increment. No graph/search dual writes, stale embeddings or public original-file URLs. Small originals are stored as database blobs with a 5 MB cap; object-storage projection is later work.
- Expose deterministic passage retrieval and need/offer topic matching honestly. They are useful workflow plumbing, not evaluated semantic AI.
- Explicitly reject URL ingestion until a restricted fetcher can be provided. Image-only extraction fails visibly rather than pretending to read it.

## Verified architecture and reuse map

| Area | Verified code | Result |
|---|---|---|
| App | `app.py`, `config.py`, `extensions.py` | Flask application factory; Flask-SQLAlchemy; configured SQLite with WAL and foreign keys. A vendored Django IETF tree also exists, but is not this app's route runtime. |
| Identity | `models/identity.py`, `services/identity.py` | Existing User model and session username lookup reused. |
| Layers | `models/coordination.py`, `services/access_policy.py` | Layer, LayerMember, LayerAdmin exist. Feature requires an active LayerMember; global/layer admin is not a private-data override. |
| Organizations | `models/coordination.py` | Guild is a cross-project collaboration group, not an authoritative organizational identity. No equivalent organization membership model found in inspected models. New CIOrganization/CIMembership introduced. |
| Programs | `models/layer_program.py` | LayerProgram controls cohort/waitlist/launch participation. New CIProgram owns organization-specific lifecycle in a layer. |
| Knowledge | `services/knowledge_layer.py`, `models/artifact.py` | Contribution vocabulary/scaffolds exist; role `Claim` is not an evidence claim. CIClaim is separate, source-attributed evidence. |
| UI | `services/rendering.py`, `routes/layer_detail_render.py`, `services/csrf.py` | Existing page shell and layer navigation reused; new template and opt-in link. |
| Chat | `models/coordination.py:WorkgroupMessage`, `routes/workgroups_api.py` | Workgroup chat exists. It has no source-lineage/audience-intersection model suitable for silently injecting private knowledge. Reuse is deferred until those policies exist. |
| Governance | `models/dp_proposal.py`, `routes/dp_proposals.py`, `models/artifact.py` | Proposal and artifact flows exist; new code does not create parallel decisions or bind organizations. Handoff is tracked below. |
| Hermes | `routes/support_api.py`, `services/support_auth.py`, `routes/dp_internal.py` | Existing inbound operational APIs use Hermes/ops credentials. They are not an installed-version-verified, permission-scoped community agent gateway. No terminal agent is exposed. |
| Deepi | `shiftshapr/desirable-properties/challenge-site/src/app/agent/page.tsx`, `src/app/api/agent/chat/route.ts` | Inspected via GitHub. Next.js UI uses HermesChat; server reads a session and proxies to configured Hermes `/api/dp/chat` with identity, message/history and document context. It is a separate service. No upstream version or restricted tool schema was verified. |
| Jobs | `cli/`, support services; vendored Celery requirements | Existing CLI convention reused. No verified Gov Hub production extraction queue was established. New source rows are a durable polling queue, drained by an explicit command. |
| Storage/operations | `config.py`, `migrations/__init__.py`, `fixtures/isolated_app.py` | Disposable DB test fixture reused. No Neo4j connection, production object storage, or live search projection was verified. No deployment performed. |
| Instructions | `.cursorrules`, `DEVELOPMENT_SAFETY.md`, `DEVELOPMENT_WORKFLOW.md` | Development-only work; no production DB changes. No AGENTS.md found in the repository tree. JAUmemory is mentioned in repository workflow but unavailable in this session. |

Deepi source reference: https://github.com/shiftshapr/desirable-properties/blob/main/challenge-site/src/app/api/agent/chat/route.ts

## Files and data ownership

- `models/community_intelligence.py`: six additive tables: organization, membership, program, immutable contribution/version, attributed claim, private content-free audit event.
- `services/community_intelligence.py`: policy filters, revision checks, extraction jobs, review, removal, citations and matching.
- `services/community_extraction.py`: local TXT/MD, PDF and DOCX extraction. Exact extraction locators are text lines/spans, PDF page/line/span, or DOCX paragraph/line/span. PDF line numbers refer to extractor output, not universal printed line numbers. Original downloads allow checking layout.
- `routes/community_intelligence.py`: session-authenticated API and page; delivery-time access/revision checks; no-store responses.
- `templates/community_intelligence.html`: overview, our knowledge, cited search, suggestions and detailed review.
- `migrations/community_intelligence.py`, `cli/community_intelligence.py`: explicit migration and worker commands.
- `fixtures/community_intelligence.py`, `scripts/community_demo.py`: synthetic scenario in an empty temporary database, with a loopback-only demo login and local worker.
- `test_community_intelligence.py`: security and lifecycle integration tests against the real Flask app.

A CISource is one immutable uploaded version, not a mutable document. New content becomes a separate contribution. Claims are independently attributed per source; semantic merging and cross-source canonical claims are deferred. Withdrawing one source removes only its claims, leaving other independently reviewed contributions intact. Dates unknown in the source remain null.

Source states: queued → processing → needs_review → ready, or failed; withdrawn is terminal. Claim standing: proposed, confirmed, rejected, disputed. Program lifecycle: unknown, planned, active, paused, completed, discontinued. Extraction never changes program lifecycle. Only active programs contribute to current answers and matching; historical retrieval is explicit.

## Run the synthetic demo

Use Python 3.11+ in an isolated virtual environment. Tested here with Python 3.14 and the package versions installed on 2026-09-25.

```sh
python3 -m venv .venv-community
.venv-community/bin/pip install -r requirements-community-dev.txt
.venv-community/bin/python scripts/community_demo.py
```

Open the `LOCAL_DEMO_URL` printed by the command. The server binds only to `127.0.0.1:5000`. Its random local login token and three synthetic accounts are **demo-only**, never an authentication integration. Closing the script removes its temporary database. No outbound messages, live model calls, remote migrations, or production data are used.

Walkthrough:

1. Open the private autumn newsletter, inspect the exact passage, and confirm/correct/reject it. Its tentative wording is preserved.
2. Ask “Who offers training?” and expand the source citations. Only reviewed accessible evidence appears.
3. Open Opportunities. Learning Neighbors' need matches Curriculum Commons' offer and Open Door Venue's offer through the reviewed topic `community training`.
4. Switch to `open-door-venue`, open Our knowledge, change Learning room to discontinued, and save. Its suggestion disappears and current answers exclude it.
5. Check “Include planned, paused and historical programs” to retrieve the dated lifecycle history.
6. Upload the same note again: it is deduplicated and does not reactivate the program. The automated test also verifies this replay.
7. Inspect the real PNG fixture's failed state. It explicitly reports unavailable OCR.

The demo's local worker drains queued uploads every two seconds. The normal app requires `community-work` to be run by an operator or existing scheduler.

## Integrate into development

1. Apply this patch to the recorded base (or review any conflicts on a newer branch).
2. Use `FLASK_ENV=development`. Verify the actual DB path, make a timestamped backup of an existing development database, and verify the backup before migrating. The migration creates only the six new tables; it does not seed users or change existing tables.
3. Run `.venv-community/bin/flask --app app community-migrate`.
4. Set `GOVHUB_COMMUNITY_INTELLIGENCE_LAYERS` to comma-separated **internal Layer.id values**, not slugs or public IDs. Empty means disabled everywhere. Add pilot accounts through existing layer membership mechanisms.
5. Run `.venv-community/bin/flask --app app community-work --limit 10` as needed. Jobs remain durable and visible between runs. A failed/interrupted job can be explicitly retried by a steward, up to three attempts.
6. Visit `/layers/<internal-layer-id>/community/` or the enabled layer's new navigation entry.

Local portability change: development/test upload folders default alongside the configured database rather than trying to create `/home/ubuntu` on macOS. Production retains its existing default. Existing development installations that use the legacy upload directory should set `GOVHUB_UPLOAD_ROOT=/home/ubuntu/data-tracker/uploads` before using this branch. This feature itself stores originals in its scoped database blobs.

## API and permission contract

Base: `/api/layers/<layer_id>/community`. All endpoints require an active layer membership and the layer allowlist flag. Mutations and answers require a valid session CSRF header `X-CSRFToken`, including in tests. No client-supplied role, org ID or layer ID grants access.

| Operation | Method / suffix | Authority |
|---|---|---|
| Workspace | GET `/` | Active layer member; private filters precede counts/metadata |
| Register organization | POST `/organizations/` | Active layer member, becomes its administrator |
| Add/remove member | POST `/organizations/<id>/members/`; DELETE `/organizations/<id>/members/<user_id>/` | Organization administrator; new member must belong to current layer. Administrator removal is deferred. |
| Create program | POST `/programs/` | Organization steward/administrator |
| Lifecycle | PATCH `/programs/<id>/` | Steward/administrator, exact revision required |
| Upload | POST `/sources/` (multipart) | Organization member, always private initially |
| Evidence/original | GET `/sources/<id>/`; GET `/sources/<id>/original/` | Owning organization member or layer audience after explicit publication |
| Review | POST `/sources/<id>/review/` | Steward/administrator; base source revision + selected claim decisions |
| Sharing | PATCH `/sources/<id>/` | Steward/administrator; revision + `visibility: private|layer` |
| Retry | POST `/sources/<id>/retry/` | Steward/administrator; failed/processing only, revision required |
| Removal | DELETE `/sources/<id>/` | Organization administrator; revision required |
| Evidence answer | POST `/answer/` | Current user permissions; question ≤500 characters, optional boolean `historical` |

Publishing shares the **whole source**, original and extracted passages, with current layer members; the UI previews this consequence. Unconfirmed/disputed passages remain labeled and excluded from answers/matching. There is no public or selected-user publication in this increment. Global/layer admins receive no private organization bypass. Cited sources/programs are rechecked immediately before preparing delivery; a changed policy, membership, or evidence revision replaces the prepared response with 409 and no citations.

Matching uses only layer-shared knowledge, never the asker's private evidence. Suggestions are recomputed, bounded to 200 candidate passages and 20 matches, and do not establish partnerships or assign people. Source listings show at most the latest 100 accessible sources; pagination is deferred.

## Operations, recovery and retention

- No model provider is configured and no uploaded data is sent to a model. External model quality/cost/retention evaluation has **not** been performed. Optional social OAuth dependencies missing in the local runtime log a warning; CI uses the existing authenticated session mechanism.
- Limits: 5 MB per upload, 50 PDF pages, 20 MB expanded DOCX, 100,000 extracted characters, 200 passages, 2,000 characters per passage, three extraction attempts. Review warnings identify truncation and unreadable PDF pages. Native parsing still requires OS-level resource/network isolation before accepting untrusted public uploads at scale.
- Each extraction claim is unconfirmed. Steward edits do not rewrite the original evidence. Extraction warnings are visible. No automatic semantic negation/conflict detection, freshness inference, or entity resolution is claimed.
- Worker acquisition/completion uses conditional state+revision writes. Repeated work is idempotent. A removal or intervening retry makes the old worker's completion a no-op, preventing resurrection. Processing jobs interrupted by a crash need explicit retry; automatic leases, backoff and dead-letter handling are later work.
- CIAudit stores actor/target IDs, action and revision without source text or filenames; it is not in the public activity feed. No audit viewer/export is exposed yet.
- Removal atomically clears original bytes, title/warnings/errors and all source claims. The minimal organization-scoped content hash tombstone blocks replay, including into another program/layer. There are no embeddings, caches, persisted answers, rooms, or graph copies in this increment.
- Logical removal is not secure physical erasure from SQLite pages/WAL, operator backups, or prior downloads. Operators must define backup expiry, secure-storage handling and replay of withdrawal tombstones after restoration before offering a deletion SLA. No such SLA is claimed here.
- Rollback: clear the layer allowlist and stop the worker, then revert code. Retain the additive tables for recovery rather than dropping user evidence. A destructive schema downgrade is intentionally not automatic. No production rollout, paid activation, remote branch push or PR creation was performed.

## Remaining staged implementation

| Stage | Next concrete work | Gate |
|---|---|---|
| Foundation completion | Restricted public-URL fetch worker; OCR adapter; semantic extractor with evaluated schema; job leases/backoff; source-version grouping; selected audiences; storage/quotas; profile and membership-management UI; freshness/effective dates | Live extraction evaluation, URL rebinding/redirect tests, quotas and resource isolation |
| Coordination | Persisted opportunities with dependency revisions and dismissal feedback; reuse WorkgroupMessage through explicit immutable audience policy; narrow scoped Hermes tool gateway; owner-accepted actions and existing proposal handoff | Room audience expansion/revocation tests and end-to-end discussion → confirmed next step |
| Updates | Dedicated signed inbound-mail/RSS adapters, source identity verification, cursors, deduplication and change-review digests | Duplicate webhook, stale-source and failed-cursor tests; authorized provider configuration |
| Federation | Organization export + evidence manifest, stable namespaces/versioned policies; independently operated peer adapters later | Export scope tests before federation claims |

The first pilot is not complete until group conversations and confirmed governance handoff work. The briefing's requested scanned-document success and configured-model evaluation are also outstanding; current fixtures explicitly demonstrate unavailable OCR and deterministic workflow behavior instead.
