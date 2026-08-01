# Gov Hub – Canonical Architecture & Build Plan

**Version:** 3.0
**Date:** March 10, 2026
**Status:** Authoritative – supersedes GOV-HUB-2.md for implementation purposes.

GOV-HUB-2.md is retained as the original feature vocabulary reference.

**See also:**
- `artifact_specification.md` – full artifact model spec: types (Proposal, Evidence, Insight, Reflection, Translation, Implementation, Decision, Monument, Bridge), relationships, status lifecycle, ArtifactRelation schema.
- `PLANNING_FULL_PICTURE.md` – consolidated view of Phase 2.4 (Role elections), Phase 3.4 (Artifact lineage), UUID migration, meta-domain, and localization with implementation detail and sequencing.

---

# Building Context – This Is an Evolution, Not a Greenfield Build

**This document describes an architectural evolution of an existing, running system.**

Do not treat this as a fresh start. The Gov Hub is already in production.

## Existing System

| Item | Detail |
|---|---|
| **Dev environment** | `/home/ubuntu/gov-hub-dev` |
| **Dev URL** | `https://dev.hub.themetalayer.org` |
| **Production URL** | `https://rfc.themetalayer.org` |
| **Backend** | Flask + SQLAlchemy (`ietf_data_viewer_simple.py` – MLGH/Meta-Layer app) |
| **Frontend** | Vue 3 + Vite + Bootstrap 5 (`client/`) |
| **Database** | SQLite (dev: `instance_dev/datatracker_dev.db`, prod: `instance/datatracker.db`) |
| **Auth** | Session-based + Web3Auth (already deployed) |
| **Build system** | Vite + Yarn |

## What Already Exists

The following features are already implemented in some form and must not be broken:

- **Projects** (= Layers in GOV-HUB-3 terminology) – model exists, routes exist
- **Roles & Role Claims** – implemented (`RFC_ROLES_CLAIMS_BADGES.md`)
- **Workgroups & Guilds** – implemented (`PROJECTS_WORKGROUPS_GUILDS_STATUS.md`)
- **Drafts / Submissions** – IETF-inspired draft workflow exists
- **Badges** – feature planned and partially implemented (`BADGES_FEATURE_PLAN.md`)
- **Ordinals** – Bitcoin Ordinals integration implemented (`ORDINALS_FINAL_SUMMARY.md`)
- **Web3Auth** – wallet auth deployed (`WEB3AUTH_DEPLOYMENT.md`)

## Approach

**Evolve, don't replace.**

All work in GOV-HUB-3 follows the "minimize blast radius" principle:

- Preserve all working production features during migration
- Refactor toward the new architecture incrementally
- Use the dev environment (`gov-hub-dev`) to build and verify before promoting to prod
- Database migrations must have backups and rollback paths

**Planned migrations (approved):**

- **Project → Layer in code**: Full rename. Model `Project` → `Layer`, table `project` → `layer`, all `project_id` → `layer_id`. Routes `/api/projects/` → `/api/layers/`. No backward compatibility layer – clean break.
- **UUID for existing entities**: Migrate all primary keys to UUID. User (int→UUID), Project/Layer (string→UUID), Submission (string→UUID), Vote, Ballot, Claim, Role, Workgroup, Guild, Badge, etc. SQLite: use `CHAR(36)` or `TEXT`. Clean break – no legacy ID support.

## Migration Safety Rules

1. Never run destructive migrations on production without a verified backup
2. Always test in `gov-hub-dev` (dev.hub.themetalayer.org) before deploying to prod (rfc.themetalayer.org)
3. New modules and models are additive – existing routes and models stay functional during transition
4. Any schema change that touches existing tables requires a migration script and a rollback path
5. The EventLog is new infrastructure – it does not replace any existing table; it runs alongside

---

# Gap Analysis – What Exists vs What GOV-HUB-3 Requires

This section maps the current codebase to the GOV-HUB-3 architecture. All models live in `ietf_data_viewer_simple.py` (Flask + SQLAlchemy).

## ✅ Already Implemented (Evolve, Don't Replace)

| GOV-HUB-3 Concept | Current Implementation | Notes |
|---|---|---|
| **Layer** | `Project` → `Layer` | Migration planned: full code rename. id will become UUID; table `layer`; `layer_id` FKs. |
| **Layer membership** | `ProjectMember` | user_id, project_id, status. Active members = voting eligibility. |
| **Layer admin** | `ProjectAdmin` | Admin table exists. Map to Admin Role semantics. |
| **Workgroup** | `Workgroup` | project_id, coordinator, status. Layer-scoped. |
| **Guild** | `Guild` | Cross-project. GuildMembership, GuildInvitation. |
| **Role** | `Role` | project_id, cluster, titleGuild, titleOperational, claimRequiresApproval, badgeEnabled. |
| **Role claim** | `Claim` | role_id, user_id, status (pending_approval, active, etc.), intent, evidence. |
| **Draft/Submission** | `Submission` | project_id, status, ordinal integration, revision fields. Has public_id. |
| **Vote** | `Vote` | project_id, submission_id, start_at, end_at, quorum_count, win_threshold, status. |
| **Vote eligibility** | `VoteEligibilitySnapshot` | vote_id, person_id, is_eligible. Snapshot at activation. |
| **Ballot** | `Ballot` | vote_id, person_id, choice. |
| **Badge** | `Badge` (from Role) | role_badge, founding_wave_badge, term_renewal_marker. BadgeSkin, BadgeCycle, OneTimeBadge. |
| **User/Identity** | `User` | public_id, displayName, Web3Auth, evmAddress, solanaAddress. Not yet IdentityAnchor abstraction. |
| **Status audit** | `StatusChange` | Polymorphic entity_type, entity_id. Append-only audit. |
| **Ordinals** | Submission fields | sourceType, ordinalId, inscriptionNumber, etc. InscriptionOrder for wizard. |

## ⚠️ Partially Implemented (Extend or Refactor)

| GOV-HUB-3 Concept | Current State | Gap |
|---|---|---|
| **Vote → Artifact** | Vote references `submission_id` | GOV-HUB-3: Vote references `artifact_id`. Submission should become Artifact subtype. Migration: add artifact_id or map submission as artifact. |
| **UUID primary keys** | Project uses string id (proj_...). Submission uses string id. User uses integer id. | **Migration planned**: All existing entities transition to UUID PKs. See "UUID + Layer Migration Plan" below. |
| **Badge approval** | Badge has approval workflow | No Badge Keeper Role. No revolving triad. No PEARL path. |
| **Modular structure** | Single file `ietf_data_viewer_simple.py` (~26k lines) | Phase 0: Extract models into domain modules. Extract routes. Extract services. |
| **Host → Layer** | No subdomain routing | Need middleware: dev.hub.themetalayer.org vs layer.themetalayer.org. Nginx already has dev subdomain. |

## ❌ Not Yet Implemented (Build New)

| GOV-HUB-3 Concept | Required | Priority |
|---|---|---|
| **EventLog** | Append-only governance event table | Phase 0 – blocks everything |
| **Artifact** base model | Central knowledge object; Submission as subtype | Phase 1 |
| **ArtifactRelation** | Typed relationships (builds_on, references, opposes, etc.) | Phase 0/1 |
| **Bridge** | Artifact ↔ external URL / monument | Phase 2+ |
| **IdentityAnchor** | Abstraction over User for cross-layer identity | Phase 1 – or defer; User can serve initially |
| **WalletBinding** | On-demand EVM/BTC Taproot; chain_type | Phase 1+ |
| **Triad** | Role-anchored, max 3. Distinct from Guild. | Phase 1 – may map to Workgroup with type=triad |
| **Badge Keeper Role** | Predefined Role; configures review system | Phase 2 |
| **PEARL** | Reflection artifact, 5 fields, badge overlay | Phase 3 |
| **Quest** | Quest model, QuestSubmission artifact | Phase 2 |
| **Monument** | Digital monuments registry | Phase 2/3 |
| **Waitlist** | Layer/role/triad waitlists | Phase 1 |
| **Activity feed** | Reads from EventLog | Phase 1 |
| **Layer resolution middleware** | Host → layer context; reserved subdomains | Phase 1 |

## Summary: Immediate Priorities

Given what exists, the **revised build order** is:

1. **EventLog** – Add new table. Emit events from existing Vote, Claim, Badge, ProjectMember flows. No schema change to existing tables.
2. **Modular extraction** – Split `ietf_data_viewer_simple.py` into domain modules (models/, services/, routes/). Preserve all behavior.
3. **Artifact + ArtifactRelation** – Add Artifact model. Link Submission to Artifact (subtype or relation). Add ArtifactRelation for draft→draft links.
4. **Vote.artifact_id** – Add artifact_id to Vote; keep submission_id for backward compat during transition; migrate votes to reference artifact.
5. **Layer resolution** – Middleware: parse Host header, resolve layer from subdomain or path. Set request context.
6. **UUID on new entities** – All new tables use UUID. Existing tables: add uuid column where needed, migrate incrementally.
7. **Waitlists** – New model. Basic join/role/triad interest.
8. **Activity feed** – New route + service. Query EventLog, return recent events for layer.

Defer to later phases: IdentityAnchor (User suffices for now), Triad as distinct model (Claim + Role may suffice initially), Badge Keeper, PEARL, Quests, Monuments, Bridges.

---

# UUID + Layer Migration Plan – Overview

This section describes the approved migration: (1) transition all existing entities to UUID primary keys, and (2) rename Project to Layer throughout the codebase. Clean break – no backward compatibility.

## Scope

| Migration | What changes |
|---|---|
| **UUID** | All primary keys become UUID. Tables: User, Project→Layer, Submission, Vote, Ballot, VoteEligibilitySnapshot, Claim, Role, Workgroup, Guild, GuildMembership, GuildInvitation, Badge, RoleImage, RoleImageVote, BadgeSkin, BadgeCycle, OneTimeBadge, Comment, StatusChange, InscriptionOrder, UserNotification, etc. |
| **Project → Layer** | Model `Project` → `Layer`. Table `project` → `layer`. All `project_id` columns → `layer_id`. All Python/JS/SQL references. Routes `/api/projects/` → `/api/layers/`. Frontend: project → layer. |

## Execution Order

**Recommended sequence:** Project→Layer first (fewer FK cascades), then UUID.

### Phase 1 – Project → Layer Rename

1. Create migration script: add `layer` table (copy of `project` schema), migrate data, update all FKs in child tables to point to `layer`, drop `project`.
2. Rename model in code: `Project` → `Layer`, `ProjectMember` → `LayerMember`, `ProjectAdmin` → `LayerAdmin`.
3. Rename all `project_id` → `layer_id` in models, routes, services, frontend.
4. Update API routes: `/api/projects/` → `/api/layers/`.
5. Update frontend: all project references → layer.
6. Verify dev, then prod.

### Phase 2 – UUID Migration (by dependency order)

Tables must be migrated in topological order (parents before children):

1. **User** – int → UUID. All tables with `user_id` FK must be updated.
2. **Layer** (formerly Project) – string → UUID. All `layer_id` FKs.
3. **Submission** – string → UUID. Vote, Comment, etc. reference it.
4. **Role, Workgroup, Guild** – migrate PKs.
5. **Vote, Claim, Badge, Ballot, VoteEligibilitySnapshot** – migrate PKs.
6. **Remaining tables** – RoleImage, BadgeSkin, BadgeCycle, OneTimeBadge, Comment, StatusChange, etc.

Per-table steps:
- Add new column `id_new` (UUID, nullable).
- Backfill: generate UUID for each row.
- Add unique constraint.
- Update all FK columns in child tables to use new UUIDs.
- Drop old PK, rename `id_new` → `id`.
- Drop old FK columns, add new FKs.

### Phase 3 – Cleanup

- Remove any legacy columns.
- Update `public_id` usage where it overlapped with old ids.
- Update URL patterns (e.g. `/layer/<uuid>` instead of `/project/<slug>`).
- Full regression test.

## Risk Mitigation

- Backup database before each phase.
- Run full migration on dev first; verify all features.
- Keep migration scripts; document rollback steps.
- Consider feature flag to disable prod during migration window if needed.

---

---

# Part I – Architectural Domains

The system is organized into three non-overlapping domains. All models, services, and events belong to exactly one domain.

---

## Domain 1 – Identity (Who)

Models representing persistent participants and their governance eligibility.

Entities:

- IdentityAnchor (IA)
- WalletBinding
- LayerMembership
- RoleClaim
- BadgeAward
- Ballot

Purpose:

- Preserve authorship and participation continuity
- Determine governance eligibility
- Anchor contributions to persistent pseudonymous identities

Identity objects persist across Layers and Artifacts. A participant's governance lineage travels with them.

---

## Domain 2 – Artifact (What)

**Full specification:** `artifact_specification.md`

Artifacts are first-class governance objects. They are the center of the system.

An Artifact represents any durable contribution or knowledge object.

Examples:

- Drafts and proposals
- Documents, guides, glossaries
- Quest outputs
- Triad reports
- PEARL reflections
- Monument registrations
- Bridge records

Entities:

- Artifact
- Submission (Artifact subtype – drafts, proposals)
- Reflection (Artifact subtype – `reflection_type = pearl`; linked to a specific BadgeAward; has 5 structured fields; `pearl_complete` drives badge overlay)
- TriadReport (Artifact subtype)
- QuestSubmission (Artifact subtype)
- MonumentRecord (Artifact subtype)
- Bridge
- ArtifactRelation

Artifacts form a **knowledge graph**. They may reference other artifacts through typed relationships:

```
artifact → builds_on → artifact
artifact → opposes    → artifact
artifact → references → artifact
artifact → implements → artifact
artifact → amends     → artifact
```

Artifacts may also reference external objects through Bridges.

Artifacts are not attachments. They are the evidence layer of governance.

---

## Domain 3 – Coordination (How)

The coordination domain governs how people organize and make decisions.

Entities:

- Layer
- Role (including predefined: Admin, Badge Keeper)
- Triad (Layer-scoped, role-anchored, max 3)
- Guild (cross-layer, persistent, participates in Workgroups)
- Workgroup (Layer-scoped, may serve as judging/decision body)
- Vote
- Election
- Quest
- Milestone
- Goal
- RoadmapItem
- Monument
- LayerConfig
- Dispute
- BadgeDefinition (owned by Badge Keeper Role; includes `pearl_eligible`, `review_system`)

Coordination structures organize governance but do not hold knowledge themselves. Knowledge resides in Artifacts.

---

# Part II – Architectural Rules

## Rule 1 – Artifact-First Architecture

Artifacts must exist independently of coordination structures.

A draft Artifact must exist independently of a vote, a role, or a workgroup.

Governance actions reference Artifacts – they do not embed them.

---

## Rule 2 – Typed Relationship Graph

All core objects must support typed relationships via the ArtifactRelation model.

Examples:

```
artifact  → artifact
artifact  → monument
artifact  → layer
artifact  → external URL
artifact  → bridge
```

These relationships form the governance knowledge network.

Later phases will migrate bridge construction to Canopi and other Overweb-compatible applications. Gov Hub bridges are initially an **alpha demonstration layer**.

---

## Rule 3 – Event-Driven Governance History

All governance actions must emit events to an append-only EventLog.

Minimum event coverage:

```
member_joined
member_removed
role_claimed
role_term_ended
triad_formed
triad_report_filed
artifact_created
artifact_linked
artifact_adopted
draft_created
draft_amended
vote_started
ballot_cast
vote_closed
election_opened
election_closed
quest_completed
quest_reviewed
badge_nominated
badge_approved
badge_rejected
pearl_submitted
pearl_approved
pearl_rejected
review_triad_formed
review_triad_term_ended
monument_registered
bridge_created
bridge_updated
milestone_reached
layer_config_changed
```

The EventLog powers:

- Activity feeds
- Notifications
- Governance lineage
- Analytics
- Audit trails

The system behaves like an append-only governance log.

---

## Rule 4 – UUID Internal IDs + Short Public IDs

All core entities must use UUID primary keys internally.

Each entity should also have a short human-readable `public_id` for URLs and governance references.

Example:

```
artifact.id        = "550e8400-e29b-41d4-a716-446655440000"  (UUID, internal)
artifact.public_id = "A47"                                   (short, URL-safe)
```

The `io` notation (e.g., "A47io") may be used as a **presentation-layer** convention to visually distinguish artifact references in interfaces, logs, and lineage displays. It is not part of the UUID or the database primary key.

Entities requiring UUID + public_id:

- Layer
- IdentityAnchor
- Artifact (all subtypes)
- Role
- Triad
- Vote
- Ballot
- Quest
- Monument
- Badge
- Bridge

---

## Rule 5 – Composable Feature Exposure

The Gov Hub implements the full architecture but exposes capabilities in phases.

The full system spine is built early. User-facing surfaces are revealed gradually.

---

## Rule 6 – Bridges Are Universal Relationships

Bridges connect Artifacts and Monuments to:

- Web pages
- Images
- Text fragments
- Video timestamps
- External documents

Gov Hub bridges are temporary alpha infrastructure. Future bridge infrastructure migrates to Canopi and Overweb-compatible layers.

---

## Rule 7 – Governance Is Artifact-Driven

Decisions must be based on Artifacts.

- Votes reference Artifacts
- Quests produce Artifacts
- Badges reference Artifacts
- Monuments represent Artifacts

Artifacts are the evidence layer of governance.

---

# Part III – Feature Map

---

## 1) Layers

**What it is**

The primary governance container. Conceptually: Layer. Implementation: Project model (Layer semantics only – there will never be both Projects and Layers as distinct entities).

**Features**

- Layer creation and profile (mission, description, branding)
- Subdomain and path routing:
  - `layername.themetalayer.org`
  - `themetalayer.org/layer/layername`
- Reserved slug protection: `www`, `dev`, `api`, `docs`, `rfc`, `app`, `admin`, `status`, `hub`. We also need to protect `dev.hub`.
- Layer membership management
- Configurable governance parameters (quorum defaults, thresholds)
- Public Layer landing page

**Who uses it**

Protocol communities, open-source ecosystems, civic tech initiatives, local and regional chapters, research collectives, cultural stewardship groups.

---

## 1A) Layer Administration

**What it is**

A predefined Admin Role that allows a small number of participants to manage Layer configuration before full governance structures are in place.

**Design**

- Admin is a predefined Role – not a special flag or superuser account
- Minimum: 1 person may hold the Admin Role
- Maximum: 3 people (a natural triad)
- Admin authority is scoped to: Layer config, membership management, governance parameter changes
- Admin authority does not override votes or triad reports

**Bootstrap to stewardship transition**

The Admin Role transitions to standard role-based stewardship via:

- A configurable milestone (e.g., reaching a member threshold), or
- A Layer vote

All configuration changes made by admins emit `layer_config_changed` events to the EventLog.

---

## 2) People & Identity Anchors (IA)

**What it is**

Persistent, pseudonymous identity that carries contribution and governance lineage across Layers.

**Features**

- Session-based auth (current)
- Web3Auth wallet generation – **on demand only**:
  - EVM address: activated by the participant when they first choose to vote or opt in from their identity profile
  - Bitcoin Taproot address: generated when the participant claims or is issued their first Ordinal-based badge
  - Both live on `WalletBinding` with `chain_type = evm` or `chain_type = btc_taproot`
  - Keys are generated at the moment of opt-in – not pre-generated with an activation flag
- Multiple wallets per IA
- Wallet rotation events (future)
- Cross-layer identity continuity
- Anonymous-but-verified voting (future)
- Social recovery concepts (future)

**Who uses it**

Privacy-conscious communities, Web3-native ecosystems, youth participation programs, global distributed contributors.

---

## 3) Roles & Triads

**What it is**

Roles define stewardship responsibilities. Triads (rule-of-three) are role-anchored accountability units that prevent bottlenecks and concentration of power.

Triads are not free-floating groups. A Triad exists specifically in service of a Role.

**Design Model**

Triads reuse the same underlying Group infrastructure as Guilds (shared membership, messaging, artifact support), but with strict constraints:

- `type = triad`
- `max_members = 3`
- `role_id` is required (must be anchored to a Role)
- Layer-scoped

**Features**

- Role creation per Layer
- Role claims (time-bound stewardship terms)
- "Create Triad" available only from Role page
- Triad formation (max 3 members)
- Observer mode (time-bound; triad-approved; no voting)
- Weekly triad reports (Artifact subtype: TriadReport)
- Public triad intention statement (focus, duration, differentiation from other triads)
- Visibility into multiple triads per Role
- Triads displayable on the Guilds page (Community section), with search and filters

**Triad creation in the role process**

Triad creation must be accessible from the role claim flow. Most roles require a triad; role claimants can attach their role to a triad.

- **During claim**: A claimant can create a triad by adding two more people in the role claim process.
- **After claim**: Triad formation can also happen later – a claimant may form their triad after claiming.
- **Provisional status**: When one person has claimed a role that requires a triad, they are **provisional** until the triad is in place. The triad does not officially exist until all three members have confirmed their participation.

**Cultural Guardrail**

New triads must articulate how their focus differs from existing triads for the same Role. Competition happens through proposals and artifacts – not redundant structures.

**Who uses it**

Volunteer-driven organizations, DAO-like governance groups, working groups within protocols, research collectives.

---

## 4) Workgroups & Guilds

**What it is**

Two distinct coordination structures sharing common Group infrastructure but with different scopes, authorities, and relationship rules.

**Distinction**

| | Workgroup | Guild |
|---|---|---|
| **Scope** | Layer-scoped | Cross-layer |
| **Decision authority** | May serve as judging or decision body for certain governance decisions within its Layer | Advisory and contributory – no Layer-level authority |
| **Membership** | Layer members + invited Guild participants | Cross-layer contributors |
| **Participation rule** | Guilds may participate in Workgroups | Workgroups may NOT participate in Guilds |
| **Lifespan** | Project-tied, may be time-bounded | Persistent, not time-bounded by default |

**Relationship model**

The participation relationship is one-directional:

```
Guild → participates in → Workgroup
Workgroup ✗ participates in ✗ Guild
```

This preserves the Workgroup's Layer authority. A Guild contributes expertise and capacity to a Workgroup, but the Workgroup's governance decisions remain scoped to its Layer.

**Example use**

A "Protocol Researchers Guild" (cross-layer) may participate in a "Standards Workgroup" (Layer-scoped) as contributors and reviewers. The Standards Workgroup may render a judgment on a draft proposal. The Guild has no authority over that judgment – it contributed to the process.

**Features**

- Workgroup creation and membership (Layer-scoped)
- Workgroup as judging/decision body for designated governance decisions
- Guild formation (flexible size, cross-layer)
- Guild-as-author for drafts
- Guild participation in Workgroups (member-level join)
- Workgroup-specific documents and roles
- Workgroup branding assets

**Who uses it**

Multi-team Layers, protocol communities with multiple initiatives, topic-specific civic teams, cross-Layer researcher and contributor networks.

---

## 5) Drafts, Documents & Evolution (IETF-Inspired)

**What it is**

Structured draft → RFC-style document evolution with transparent commentary and voting.

RFC (Request for Comment) – a draft that has been opened for community review and comment before a formal vote.

**Features**

- Draft (Submission as Artifact) creation
- Inline and whole-document commenting
- Version tracking
- Draft → Vote → Adopted pipeline
- Document categories: document / template / tool / guide / glossary / policy
- Cross-referencing between drafts (ArtifactRelation)
- Multi-Layer adoption

**Who uses it**

Standards bodies, protocol governance communities, research networks, charter and constitutional drafting groups.

---

## 5A) Structured Opposition

**What it is**

A formal mechanism for documenting disagreement, alternatives, and forks – preventing governance by silence and giving minority views a legitimate path.

**Features**

- Any Artifact (proposal, draft) can receive a Support Artifact or Opposition Artifact
- Alternative proposals may be forked from an existing draft
- Support and opposition artifacts are first-class – they appear in the governance lineage
- Opposition is not blocking – it is informational and participatory
- Voting results displayed alongside the opposition artifact count for context

**Why it matters**

Without structured opposition, governance defaults to whoever shows up. This feature ensures that absence of objection cannot be mistaken for consensus.

**Who uses it**

Draft authors, governance participants, minority stakeholders, protocol researchers.

---

## 6) Voting (v1 and Beyond)

**What it is**

Configurable, membership-based voting tied to a Layer, referencing an Artifact.

**Features**

- Admin-started vote (start, duration, quorum, threshold)
- Eligibility snapshot at activation (VoteEligibility table)
- Eligible voters: Layer members with `status = active`
- Default choices: Yes / No / Abstain (creator may specify choice set)
- Deterministic outcome summary
- Vote → Artifact linkage: `Vote.artifact_id`
- Future: chain anchoring (e.g., Base)
- Future: alternative voting mechanisms

**Who uses it**

Protocol upgrade processes, draft ratification bodies, civic governance initiatives.

---

## 7) Role Elections (Voted Roles)

**What it is**

A voting mechanism specifically for selecting who holds a Role (or multiple seats) within a Layer.

**Election modes**

- **Confirm/Reject**: one candidate → Yes/No
- **Single-winner**: multiple candidates → one winner
- **Multi-seat**: multiple candidates → N seats
- **Multi-position**: one election fills several distinct roles (later)

**Ballot order randomization**

Candidate order is shuffled per voter view (or per page load) to reduce position bias while preserving auditability.

**Features**

- Candidate nomination / registration (self-nominate or nominated)
- Candidate statements and optional Artifact submissions
- Eligibility rules (v1: active members; later: badge/quest-based)
- Configurable seats (N), quorum, threshold, and term length
- Tie-handling policy (runoff / extended voting preferred)
- Public results summary and rationale

**Who uses it**

Stewardship councils, coordinator selection, role triads and rotating stewards, chapters and working groups.

---

## 8) Recognition & Badges

**What it is**

Durable recognition for structural contribution and stewardship.

**Features**

- Badge definitions and detail pages
- Badge issuance (references an Artifact as justification)
- Badge approval pathway (see below – not automatic)
- Earner vs. holder distinction
- Year overlay (issued year)
- Founding wave markers
- PEARL upgrade path: badges marked `pearl_eligible` support an optional PEARL reflection journey; on completion, the badge receives the PEARL overlay (see Section 9)
- Append-only artifact trail
- Ordinal badge anchoring: Bitcoin Taproot wallet generated on demand at first badge issuance; badge inscription optional

**Badge Approval Pathway**

Badge issuance is not automatic. Every badge award passes through an approval workflow before it is issued.

Flow:

```
Contribution made → Badge nomination / self-nomination
      ↓
Review body evaluates (Badge Keeper or delegated triads)
      ↓
Approved → badge_award created, event emitted, privileges activated
Rejected → feedback provided, resubmission allowed
```

The review body is configured by the Badge Keeper Role (see Section 8A). Approval and rejection are both recorded as EventLog entries.

**Badge Privileges / Entitlements**

Badges may optionally confer structured benefits:

- Access to private groups or steward circles
- Eligibility to vote in specific decision classes
- Eligibility to claim certain roles
- Admission to events or workshops
- Early participation rights in new initiatives

Privileges can be configured as: non-transferable, transferable to holder, earner-only even if transferred, time-limited or one-time, Layer-scoped or cross-layer.

**Who uses it**

Stewardship-driven ecosystems, civic participation programs, open-source contributor communities.

---

## 8A) Badge Keeper Role (Lineage Keeper)

**What it is**

The Badge Keeper is a named Layer Role responsible for the integrity and lineage of all badges issued within that Layer. The Badge Keeper does not necessarily review every badge personally – their primary function is to establish and maintain the review system.

**Responsibilities**

- Define which badges are available in the Layer
- Set `pearl_eligible` on badge definitions
- Configure the review system for badge approvals and PEARL approvals:
  - **Direct review**: Badge Keeper reviews nominations personally
  - **Delegated review**: Badge Keeper establishes a triad or workgroup as the review body
  - **Revolving triads**: Badge Keeper sets up time-bound review triads that rotate on a defined cycle (e.g., monthly), distributing the review burden and preventing bottleneck or capture
- Maintain badge definition history (append-only)
- Handle escalations and edge cases

**Revolving Triad Review System**

The revolving triad model is the recommended pattern for active Layers with high badge volume:

1. Badge Keeper establishes a review triad for a defined term (e.g., 4–8 weeks)
2. The triad reviews incoming badge nominations and PEARL submissions during their term
3. At term end, a new triad is formed – members may not serve consecutive terms (anti-capture)
4. Transition events are logged: `review_triad_formed`, `review_triad_term_ended`

This distributes authority, prevents single-reviewer bottlenecks, and builds reviewer experience across the community.

**Data model additions**

Badge definition:
- `keeper_role_id` – the Badge Keeper Role that owns this badge definition
- `review_system` (`direct` | `triad` | `workgroup`)
- `review_triad_id` (nullable – current active review triad if `review_system = triad`)

Badge award:
- `status` (`nominated` | `under_review` | `approved` | `rejected`)
- `reviewed_by_type` (`role` | `triad` | `workgroup`)
- `reviewed_by_id`
- `review_notes`
- `reviewed_at`

**Who uses it**

Every Layer that issues badges needs a Badge Keeper Role. In early-stage Layers, this may be held by an admin. Over time it transitions to a dedicated steward or rotating triad structure.

---

## 9) PEARL Framework

**What it is**

PEARL is an optional upgrade layer that can be applied to certain badges. A standard badge recognizes what you did. A PEARL badge recognizes how you did it – with documented intention, engagement, impact, reflection, and forward leverage.

PEARL stands for:

- **P**repare – What was your intention or goal going into this contribution?
- **E**ngage – What did you do? How did you participate?
- **A**dd Value – What was the impact or outcome of your contribution?
- **R**eflect – What did you learn? What would you do differently?
- **L**everage – How will you apply or share this experience going forward?

The framework is adapted from the PEARL Project Framework for constructivist, experiential learning (University at Buffalo CATT). In governance, the same structure applies: participants don't passively observe – they prepare, act, contribute, and reflect.

**How it works**

1. A badge definition is marked `pearl_eligible = true`
2. The participant earns the base badge through normal contribution
3. Optionally, the participant initiates the PEARL path for that badge
4. They complete all 5 stages – each stage is a prompted text field (and optionally linked to supporting artifacts)
5. When all 5 stages are submitted, the badge receives the **PEARL overlay** – a visual designation indicating the full reflective path was completed
6. The PEARL record is public and linkable as part of the participant's governance lineage

A participant may hold the base badge without completing PEARL. PEARL is always optional. It is not required for badge issuance.

**PEARL Approval Pathway**

Submitting all 5 stages does not automatically grant the PEARL overlay. The completed PEARL journey is submitted for review, following the same review system the Badge Keeper has configured for that badge.

Flow:

```
Participant completes all 5 stages → PEARL submitted for review
      ↓
Review body evaluates (same body as badge approval – Badge Keeper, triad, or workgroup)
      ↓
Approved → pearl_complete = true, PEARL overlay applied to badge
Rejected → feedback provided, participant may revise and resubmit
```

This ensures PEARL maintains lineage integrity. The Badge Keeper's system handles both badge awards and PEARL completions. A participant who earns a PEARL overlay has cleared two review gates: the badge itself and the reflective journey.

**Data model**

PEARL is a structured Artifact subtype (`Reflection`, `reflection_type = pearl`), linked to a specific badge award.

Fields:

- `id` (UUID)
- `public_id`
- `artifact_type = reflection`
- `reflection_type = pearl`
- `badge_award_id` (the specific badge award this PEARL is for)
- `identity_anchor_id`
- `layer_id`
- `prepare_text`
- `engage_text`
- `add_value_text`
- `reflect_text`
- `leverage_text`
- `status` (`draft` | `submitted` | `under_review` | `approved` | `rejected`)
- `review_notes`
- `reviewed_by_type` (`role` | `triad` | `workgroup`)
- `reviewed_by_id`
- `reviewed_at`
- `pearl_complete` (boolean – true only after approval)
- `created_at`
- `completed_at`

Badge definition model adds:

- `pearl_eligible` (boolean – whether this badge type supports the PEARL path)

Badge award model adds:

- `pearl_artifact_id` (nullable – linked PEARL reflection once approved)
- `pearl_complete` (boolean – drives the visual overlay)

**Where it appears in the UI**

- Badge detail page: PEARL overlay badge visual when `pearl_complete = true`
- Participant identity profile: PEARL badges displayed distinctly in contribution history
- Recognition nav section: `Recognition > PEARL` – a public feed of completed PEARL journeys
- Badge issuance flow: optional "Begin your PEARL path" prompt if badge is PEARL-eligible

**What it is not**

PEARL is not a scoring or ranking system. It does not gate badge issuance. It does not evaluate the quality of a contribution. It exists to transform governance experience into durable, searchable institutional knowledge – so that the how of governance is as visible as the what.

**Who uses it**

Badge earners who want to document and share their governance journey. Layers that want to cultivate reflective governance culture. Future participants learning from documented experience.

---

## 10) Quests & Bounties

**What it is**

A structured way to turn "we need help" into clear, time-bounded missions that produce real Artifacts – with rewards.

- **Quest** = a defined contribution path with acceptance criteria (can award a badge)
- **Bounty** = a quest with an explicit reward (non-monetary, monetary, or both)

**Features**

- Quest templates (review, research, outreach, build, design, governance)
- Micro-quests (20–60 minutes) vs. deep quests (multi-day)
- Artifact requirement (link / upload / inscription) + optional PEARL reflection
- Review workflow (triad or role-based reviewers)
- Layer-scoped or cross-layer quests
- Quest feed + filtering (difficulty, time, skills, urgency)
- Bounty types: Badge-only / Badge + privilege / Badge + recognition spotlight / Optional monetary (later)
- Anti-spam safeguards (rate limits, reviewer gates, minimum quality bar)

**Dependency:** Quests depend on stable triad/role review flows from Phase 1. Quests are a Phase 2 feature.

**Who uses it**

Early-stage Layers, youth and newcomer onboarding funnels, hackathon-style cohorts, governance bodies needing artifact-based legitimacy.

---

## 11) Civic Mason Monument

**What it is**

A symbolic, public memory structure where contributors place bricks representing real stewardship.

**Features**

- Drag-and-drop brick placement
- 5-second confirmation countdown
- Masonry grid rules (half-offset rows, only 50% on a row, can go outside field)
- Annual color palette
- Hover reveals identity + 200-char message
- Append-only message history
- Governance lineage indicator (not prestige)
- Brick linkable to Artifacts (Phase 2+)
- Infinite growth through the year

**Who uses it**

Youth engagement initiatives, long-horizon governance communities, civic experiment ecosystems.

---

## 12) Digital Monuments Registry

**What it is**

A way to register and steward durable public-facing "monuments" – digital places, artifacts, collections, or reference points that a Layer considers culturally or civically important.

A monument can be: an Ordinal inscription (or set/collection), a document or corpus, a dataset, glossary, or canonical reference, a page, hub, or endpoint used as source-of-truth.

**Features**

- Monument registration (title, description, steward(s), Layer association)
- Monument types and metadata (inscribed vs. offchain; canonical links)
- Provenance fields (who registered, when, what authority)
- Stewardship expectations (maintenance cadence, review checkpoints)
- Monument visibility controls (public by default)
- Linkouts to permanent archives where appropriate
- Cross-references: monuments linked to drafts, votes, roles, and badges via ArtifactRelation

**Who uses it**

Cultural preservation collectives, standards bodies, protocol communities, chapters and civic initiatives.

---

## 13) Milestones & Capability Unlock

**What it is**

A maturity ladder that unlocks governance capabilities as participation grows.

**Features**

- Join thresholds
- Role/workgroup unlock rules
- Vote unlock thresholds
- Distribution-based anti-capture thresholds
- Layer-configurable milestone stacks (within invariants)
- Milestone completion emits `milestone_reached` event

**Who uses it**

Early-stage governance projects, communities scaling from small to large, experimental civic systems.

---

## 14) Integrity, Anti-Capture & Dispute Resolution

**What it is**

Structural safeguards that keep governance legible and resistant to concentration.

**Features**

- Rule-of-three triads
- Eligibility snapshots
- Quorum + threshold enforcement
- Reserved slug protections
- Append-only governance mindset (EventLog)
- Structured Opposition artifacts (see 5A)
- Dispute and appeal workflows (lightweight v1 – dispute filed as Artifact; outcomes recorded as events)

**Who uses it**

Communities concerned about capture, multi-stakeholder governance systems.

---

## 15) Onboarding & Activation Funnel

**What it is**

A "Find Your Role in 5 Minutes" experience converting curiosity into contribution.

**Features**

- Interest prompts (no jargon)
- Instant role matches
- Active triads seeking members
- Micro-tasks (20 min)
- Activation challenges that generate Artifacts
- Meetings as optional deepening

**Who uses it**

Youth communities, hackathon cohorts, growing ecosystems needing contributor inflow.

---

## 15A) Opportunity Surfaces

**What it is**

A system-wide display of open needs – turning latent capacity into visible, actionable opportunities. Prevents governance from stalling due to lack of visible entry points.

**Features**

- Open quests (filterable by time, skill, urgency)
- Proposals missing support or opposition artifacts
- Triads seeking members
- Roles awaiting claims
- Review requests awaiting reviewers
- Shown on Layer home, Contribute section, and onboarding flow

**Why it matters**

Without visible opportunity surfaces, new contributors have no clear path in. This feature is the connective tissue between onboarding (finding a role) and actual governance participation (acting on a need).

**Who uses it**

New contributors, Layers with active governance needs, quest and review participants.

---

## 16) Governance Lineage Graph

**What it is**

A traceable map of how ideas evolve, influence decisions, and propagate across Layers.

**Features**

- Reference tracking (cites, amends, forks, implements) via ArtifactRelation
- Brick-to-Artifact linkage (Phase 2+)
- Cross-Layer adoption mapping
- Faint toggleable lineage lines in the UI
- Artifact ancestry and descendants view
- Discoverable depth without gamification

**Who uses it**

Governance researchers, protocol designers, transparency advocates, long-term ecosystem stewards.

---

## 17) Notifications & Activity Feed

**What it is**

An event-driven system keeping participants aware of governance activity.

**Two-tier implementation:**

**Tier 1 – Basic Activity Feed (Phase 1)**
- Layer-scoped feed
- Reads directly from EventLog
- No user preferences required
- Examples: artifact submitted, role claimed, vote started, triad formed

**Tier 2 – Full Notifications (Phase 4)**
- User-configurable notification preferences per event type
- Digest options (immediate / daily / weekly)
- Cross-layer notification routing

**Who uses it**

All participants; Layer administrators monitoring governance health.

---

# Part IV – Website Navigation IA

## Global Navigation (Phase 1)

**Home**
Layer overview, onboarding prompt, active opportunities, featured drafts or votes, monument callout, join/waitlist CTA.

**Contribute**
Find Your Role / Quests & Challenges / Join a Triad / Submit Draft / Waitlists / Open Opportunities

**Governance**
Drafts / Votes / Roles / Roadmap & Goals / Milestones

**Community**
People / Triads / Guilds / Workgroups / Layers – Guilds page displays both Guilds and Triads with search and filters

**Recognition**
Badges / Civic Mason / PEARL / Monument Registry

**Learn**
How the System Works / Stewardship Guide / Draft → RFC Process (RFC = Request for Comment) / Glossary / Learning Modules

---

## Layer-Level Navigation

Each Layer has a local navigation surface:

Overview / Roles / Drafts / Votes / Workgroups / People / Monument

---

# Part V – Implementation Strategy

## Principle

Build the full system spine early. Expose the right surfaces at the right time.

Build order: Data primitives → Relationship model → Event model → Governance workflows → Recognition and memory → Advanced visualization

---

## Phase 0 – Foundations

Establish stable infrastructure before any governance workflows.

### 0.1 UUID + public_id strategy
- UUID primary keys on all major entities
- Short `public_id` for human-readable references and URLs
- `io` presentation suffix optional at display layer only

### 0.2 Domain separation – Modular Architecture

The system uses a **modular architecture** organized by domain and concern. No monolithic files. Each domain and layer of the stack has its own module.

Recommended folder structure:

```
src/
  models/
    identity/        ← IdentityAnchor, WalletBinding, LayerMembership, RoleClaim, BadgeAward, Ballot
    artifact/        ← Artifact, Submission, Reflection, TriadReport, QuestSubmission, MonumentRecord, Bridge, ArtifactRelation
    coordination/    ← Layer, Role, Triad, Guild, Workgroup, Vote, Election, Quest, Milestone, Monument, BadgeDefinition, LayerConfig, Dispute
    events/          ← EventLog

  services/
    identity/
    artifact/
    coordination/
    events/

  middleware/
    layer-resolution.ts    ← host → layer context
    auth.ts
    permissions.ts

  routes/
    layers/
    roles/
    triads/
    artifacts/
    votes/
    badges/
    quests/
    monuments/

  events/
    emitters/        ← per-domain event emitters
    handlers/        ← listeners and side-effect handlers (notifications, feed updates)
```

No governance logic lives in route handlers. Routes call services. Services own logic and emit events. Models define shape only.

### 0.3 Event log
Implement append-only EventLog before any governance actions are built. All later actions emit events.

### 0.4 Typed relationship / bridge infrastructure
Implement ArtifactRelation and Bridge base models before monuments, quests, or lineage features.

**Deliverables:** UUID adoption, EventLog, ArtifactRelation/Bridge base model, domain-oriented module structure.

---

## Phase 1 – Core Governance Spine

Minimum usable governance system.

### 1.1 Layer resolution
Host → Layer middleware, reserved subdomain protection, path fallback routing.

### 1.2 Identity and membership
Identity anchors, Layer membership, role claims, active membership status, on-demand EVM wallet binding.

### 1.3 Roles and triads
Role creation, role claims, triad creation (role-anchored, max 3), weekly triad reports as Artifacts.

### 1.4 Artifact model
Artifact base model, Submission as Artifact subtype, artifact pages, artifact provenance fields.

### 1.5 Draft voting v1
Vote model, ballots, VoteEligibility snapshot, start/close lifecycle, vote references artifact_id.

### 1.6 Waitlists
Layer or role waitlists, basic request/join pathways, waitlist triggers notifications (Tier 1 feed).

### 1.7 Basic Activity Feed
Layer-scoped feed reading from EventLog. No preferences. Tier 1 only.

**Deliverables:** Working Layer pages, roles + triads, drafts/submissions as artifacts, voting on drafts, waitlists, basic activity feed.

---

## Phase 2 – Contribution Engine

Makes the system meaningfully participatory.

### 2.1 Quests and bounties
Quest creation, quest submission as Artifacts, review flow, badge/bounty linkage.

### 2.2 Opportunity surfaces
Open quests, missing support/opposition artifacts, triads seeking members, review requests.

### 2.3 Structured opposition
Proposal → support artifact, proposal → opposition artifact, alternative proposal forks.

### 2.4 Role elections
Candidate registration, approval/multi-candidate/multi-seat models, randomized ballot order.

### 2.5 Digital Monuments Registry
Monument registration, stewardship fields, monument/artifact linkage.

**Deliverables:** Clear contributor pathways, structured deliberation, election-capable governance, monument registry.

---

## Phase 3 – Recognition & Civic Memory

Turns contributions into visible historical memory.

### 3.1 Badge system
Badge definitions, badge awards (referencing Artifacts), privileges/entitlements, PEARL integration (pending PEARL definition).

### 3.2 Civic Mason
Badge-linked brick placement, brick messages, hover state, brick/artifact linkage.

### 3.3 Bitcoin Taproot wallet
On-demand generation at first badge issuance, Ordinal inscription support, WalletBinding with `chain_type = btc_taproot`.

### 3.4 Artifact lineage visualization
Faint toggleable lines, artifact ancestry/descendants, governance impact display.

**Deliverables:** Recognition flows, civic memory layer, Ordinal badge anchoring.

---

## Phase 4 – Knowledge & Governance Depth

Deepens institutional intelligence.

### 4.1 Governance lineage graph
Influence chains, artifact hubs, cross-layer references.

### 4.2 Full notifications
User notification preferences, cross-layer routing, digest options.

### 4.3 Roadmaps, milestones, and goals
Goal creation, roadmap items, progress updates, milestone completion events, optional goal voting.

### 4.4 Learning modules
Governance literacy, Layer-specific onboarding, role-specific learning.

### 4.5 Dispute resolution
Dispute filed as Artifact, mediation workflow, outcomes recorded as events.

**Deliverables:** Rich activity awareness, Layer planning tools, learning and dispute handling.

---

## Phase 5 – Overweb / Canopi Transition Layer

Moves alpha bridge concepts into their long-term home.

### 5.1 Alpha bridge support in Gov Hub
Artifact/web bridges, monument/web bridges, selectors for text, image, video, etc.

### 5.2 Migration path to Canopi
Bridge ownership transfer model, Overweb-compliant bridge records, external application integration.

### 5.3 Cross-layer interoperability
Cross-layer monument linkage, cross-layer artifact references, cross-layer governance adoption.

**Deliverables:** Working alpha bridges, clear migration path to Canopi, meta-layer interoperability foundation.

---

# Part VI – Build Checklist (Immediate Next Tasks)

**Note:** The generic checklist below assumes a greenfield build. Given the existing codebase, follow the **Revised Priorities** in the Gap Analysis section above. The first concrete steps are: EventLog → modular extraction → Artifact + ArtifactRelation → Vote.artifact_id → Layer resolution.

Execution order reflects actual dependency chain.

---

## Task 1 – UUID Infrastructure

Add UUID primary keys to all major entities. Add short `public_id` fields. Standardize route resolution to use `public_id` in URLs. `io` suffix is presentation-layer only.

Entities: Layer, IdentityAnchor, Artifact, Role, Triad, Vote, Ballot, Quest, Monument, Badge, Bridge.

---

## Task 2 – EventLog System

Implement append-only governance event log before any governance workflows are built.

Fields: `id`, `event_type`, `actor_type`, `actor_id`, `subject_type`, `subject_id`, `payload_json`, `created_at`.

This must exist before votes, roles, and artifacts are built. All later actions emit events here.

---

## Task 3 – Identity Anchor Model

Create IdentityAnchor (IA).

Fields: `id` (UUID), `public_id`, `display_name`, `profile_fields`.

WalletBinding (separate table): `identity_anchor_id`, `chain_type` (`evm` | `btc_taproot`), `address`, `created_at`.

Wallets are generated on demand – not pre-generated. EVM at first vote opt-in. BTC Taproot at first badge issuance.

---

## Task 4 – Membership System

Create LayerMembership model.

Fields: `id`, `identity_anchor_id`, `layer_id`, `status`, `joined_at`.

Membership with `status = active` determines voting eligibility.

---

## Task 5 – Layer + Host Middleware

Implement host → Layer resolution middleware.

Support: `layer.themetalayer.org` and `themetalayer.org/layer/layername`.

Reserved subdomains: `www`, `dev`, `api`, `docs`, `rfc`, `app`, `admin`, `status`.

Middleware sets Layer context for all requests.

---

## Task 6 – Roles & Triads

Role model: `id`, `layer_id`, `name`, `cluster`, `guild_name`, `requires_triad` (bool).

Triad model: `id`, `role_id`, `max_members = 3`, `status` (pending | active). Triad is not official until all three members have confirmed.

Claim model: when `role.requires_triad` and claimant is sole holder, claim status is `provisional` until triad is formed and all three have confirmed.

Triad creation is accessible from the role claim process: claimants can add two more people during claim or later. See "Triad creation in the role process" in Section 3.

Admin Role is a predefined Role at Layer creation. Min 1 holder, max 3 (triad). Transitions to standard stewardship via milestone or vote.

---

## Task 7 – Artifact Base Model

**See `artifact_specification.md` for full field definitions, artifact types, and status lifecycle.**

Create the central Artifact model.

Fields: `id` (UUID), `public_id`, `layer_id`, `creator_identity_anchor_id`, `artifact_type`, `artifact_subtype`, `title`, `summary`, `body`, `uri`, `source_language`, `current_language`, `status`, `created_at`, `updated_at`.

Core artifact types (from spec): Proposal, Evidence, Insight, Reflection (PEARL), Translation, Implementation, Decision, Monument, Bridge.

Map existing Submission model as an Artifact subtype or linked model.

Artifacts must exist independently of governance workflows.

---

## Task 8 – ArtifactRelation Model

**See `artifact_specification.md` for full relationship taxonomy.**

Implement typed relationships between objects.

Fields: `id`, `from_object_type`, `from_object_id`, `to_object_type`, `to_object_id`, `relation_type`, `created_by_identity_anchor_id`, `created_at`.

Relation types (from spec): `builds_on`, `references`, `supports`, `corroborates`, `cites`, `contradicts`, `refutes`, `amends`, `supersedes`, `implements`, `translation_of`, `reflects_on`, `derived_from`, `responds_to`, `links_to`, `anchors_to`, `references_external`.

This is the backbone of the artifact graph.

---

## Task 9 – Bridge Model

Implement web-compatible linking.

Fields: `id`, `artifact_id`, `monument_id` (nullable), `target_type`, `target_uri`, `selector_data`, `created_at`.

Target types: `webpage`, `image`, `text_fragment`, `video_segment`.

Alpha demonstration layer – will migrate to Canopi in Phase 5.

---

## Task 10 – Voting System (v1)

Vote model: `id`, `layer_id`, `artifact_id`, `start_at`, `end_at`, `quorum`, `threshold`, `status`.

Ballot model: `id`, `vote_id`, `identity_anchor_id`, `choice`, `cast_at`.

VoteEligibility snapshot table: snapshot of eligible members at vote start.

---

## Task 11 – Waitlists

Allow participants to register interest in: joining a layer, claiming a role, joining a triad.

Waitlist entries emit events. EventLog feeds the basic activity feed when opportunities open.

---

## Task 12 – Basic Activity Feed (Tier 1)

Layer-scoped event feed reading from EventLog.

Example items: artifact submitted, role claimed, vote started, triad formed.

No user preferences at this stage. Full notification preferences are Phase 4.

---

## Task 13 – Initial UI Navigation

Expose only the minimal Phase 1 navigation surface:

`Home | Contribute | Governance | Community | Recognition | Learn`

Each connects to Phase 1 features only.

---

# Part VII – Success Criteria (Phase 0 + Phase 1)

The system has its **governance spine** when it supports:

- Creating a Layer
- Joining a Layer
- Creating Roles
- Forming Triads
- Submitting Artifacts
- Voting on drafts
- Recording all governance actions as events

Once these capabilities exist, all higher-order features (quests, elections, monuments, badges, bridges) layer on top without architectural refactoring.

---

# Open Items

All architectural open items resolved. Document is complete for Phase 0 + Phase 1 build initiation.

| # | Item | Status |
|---|------|--------|
| 1 | PEARL definition | **Resolved** – See Section 9. Artifact subtype with 5 structured fields. |
| 2 | Workgroup vs. Guild | **Resolved** – See Section 4. Distinct entities: Workgroup is Layer-scoped with decision authority; Guild is cross-layer and participates in Workgroups (not vice versa). |

---

*End of GOV-HUB-3.md*
