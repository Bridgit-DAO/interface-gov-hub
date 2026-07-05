# Gov Hub – Full Picture Planning

**Version:** 1.0  
**Date:** March 12, 2026  
**Purpose:** Consolidated view of all planned work, dependencies, and sequencing.

---

## Overview

This document integrates all active and planned tasks into a single view. It expands GOV-HUB-3 phase items with implementation detail and adds cross-cutting work (meta-domain, localization).

---

## Current State (As of March 2026)

| Area | Status |
|------|--------|
| **Election flow** | ✅ Done – self-registration, multi-candidate ballots, claim creation for winners |
| **Reinscription resolution** | ✅ Done – `get_last_inscription_for_sat()` in gov-hub |
| **Project → Layer** | ✅ Done |
| **public_id (UUID-style URLs)** | ✅ Done – entities expose public_id; routes accept UUID |
| **Full UUID PK migration** | ⏳ Planned – see Phase 6 below |

---

## Phase 2.4 – Role Elections (Expanded)

**Location in GOV-HUB-3:** Phase 2 – Contribution Engine  
**Dependencies:** Election flow (done), Vote/VoteCandidate/Ballot models (exist)

### Scope

| Item | Detail |
|------|--------|
| **Candidate registration** | ✅ Self-register + admin-add via `POST /api/votes/<id>/candidates/` |
| **Multi-candidate ballots** | ✅ `castBallotCandidate()`, choice = candidate_id |
| **Randomized ballot order** | ❌ Not yet – ballot UI shows candidates in fixed `display_order` |
| **Multi-seat elections** | ⚠️ Partial – `close_vote` supports `seats`; UI may need seat-count display |

### Remaining Work

1. **Randomized ballot order**
   - Add `ballot_order_seed` (or similar) to Vote when activated
   - Shuffle candidate list per voter using deterministic seed + user_id (so same user sees same order, different users see different orders)
   - Or: shuffle once at activation, store order in Vote; all voters see same randomized order

2. **Multi-seat clarity**
   - Ensure Vote model supports `seats` (e.g. 3 seats → top 3 candidates win)
   - UI: show "Elect up to N" and display seat count in results

3. **Withdrawal**
   - VoteCandidate has `status` (approved, withdrawn) – ensure UI supports candidate withdrawal before vote closes

### Deliverables

- Randomized candidate order on ballot (configurable per vote)
- Clear multi-seat handling in close_vote and results UI
- Candidate withdrawal flow (if not already complete)

---

## Artifact System – Specification Reference

**Source of truth:** `artifact_specification.md`

The artifact model defines:

- **Core types:** Proposal, Evidence, Insight, Reflection (PEARL), Translation, Implementation, Decision, Monument, Bridge
- **Base fields:** id (UUID), public_id, layer_id, creator_identity_anchor_id, artifact_type, artifact_subtype, title, summary, body, uri, status, etc.
- **Relationships:** builds_on, references, supports, contradicts, implements, translation_of, reflects_on, etc.
- **ArtifactRelation schema:** from_object_type, from_object_id, to_object_type, to_object_id, relation_type
- **Status lifecycle:** draft → submitted → under_review → adopted → implemented → archived (and variants)
- **Governance lineage:** Proposal → Evidence → Vote → Decision → Implementation → Reflection

---

## Phase 3.4 – Artifact Lineage Visualization (Expanded)

**Location in GOV-HUB-3:** Phase 3 – Recognition & Civic Memory  
**Dependencies:** Artifact model, ArtifactRelation (see `artifact_specification.md` for full relation types)

### Scope

| Item | Detail |
|------|--------|
| **Visual graph** | Interactive graph of artifact relations |
| **Ancestry** | Parents / builds_on / references – "where did this come from?" |
| **Descendants** | Children – "what was built from this?" |
| **Governance impact** | Votes, claims, badges linked to artifacts |

### Implementation Approach

1. **Data model**
   - ArtifactRelation: `source_artifact_id`, `target_artifact_id`, `relation_type` (builds_on, references, opposes, etc.)
   - Query: ancestors = transitive closure of incoming relations; descendants = transitive closure of outgoing relations

2. **API**
   - `GET /api/artifacts/<id>/lineage` → `{ ancestors: [...], descendants: [...] }`
   - Optional: `depth` param to limit graph depth

3. **Frontend**
   - Toggleable overlay or sidebar on artifact detail page
   - Faint lines connecting nodes (D3.js, Cytoscape.js, or similar)
   - Click node → navigate to artifact
   - Optional: highlight governance impact (votes, badges) on nodes

### Deliverables

- Lineage API endpoint
- Artifact detail page: "Lineage" toggle → graph view
- Support for relation types from `artifact_specification.md` (builds_on, references, supports, contradicts, implements, etc.)

---

## Phase 6 – UUID Migration (Full PK Migration)

**Location in GOV-HUB-3:** UUID + Layer Migration Plan (Phase 2)  
**Current state:** `public_id` added to entities; URLs use public_id. **PKs remain int/string.**

### Scope

| Migration | What changes |
|-----------|--------------|
| **User** | `id` int → UUID. All `user_id` FKs updated. |
| **Layer** | `id` string → UUID. All `layer_id` FKs. |
| **Submission** | `id` string → UUID. Vote, Comment, etc. |
| **Role, Workgroup, Guild** | PK → UUID |
| **Vote, Claim, Badge, Ballot, VoteEligibilitySnapshot** | PK → UUID |
| **Remaining** | RoleImage, BadgeSkin, BadgeCycle, OneTimeBadge, Comment, StatusChange, InscriptionOrder, UserNotification, etc. |

### Execution Order (Topological)

1. **User** – int → UUID
2. **Layer** – string → UUID
3. **Submission** – string → UUID
4. **Role, Workgroup, Guild**
5. **Vote, Claim, Badge, Ballot, VoteEligibilitySnapshot**
6. **Remaining tables**

### Per-Table Steps

1. Add `id_new` (UUID, nullable)
2. Backfill UUID for each row
3. Add unique constraint
4. Update child FKs to new UUIDs
5. Drop old PK, rename `id_new` → `id`
6. Update SQLAlchemy models

### Risk Mitigation

- Full backup before migration
- Run on dev first; full regression
- Migration scripts with rollback path
- Consider maintenance window for prod

### Deliverables

- Migration scripts (per table or batched)
- Rollback documentation
- All entities use UUID primary keys

---

## Cross-Cutting Work

### Meta-Domain for Layer

**Status:** Planned  
**Dependencies:** `get_last_inscription_for_sat` (done)

| Item | Detail |
|------|--------|
| **Format** | `example.com.meta` or `x.example.com.meta` (x = n, nw, s, sw, w, e, se, ne) |
| **Source** | Ordinal inscription content (domain string) |
| **Reinscription** | Use `/r/sat/{sat}/at/-1` → `get_last_inscription_for_sat(sat)` |
| **Storage** | `Layer.meta_domain_inscription_id`, `Layer.meta_domain` (cached string) |
| **Usage** | Display, identity, monument association |
| **Cardinality** | One meta-domain per layer |

### Localization (i18n)

**Status:** Planned (last)  
**Scope:** Interface strings, date/number formatting, RTL if needed

### Artifact / Inscription ↔ Meta-Domain Association

**Status:** Deferred  
**Scope:** Link artifacts and inscriptions to meta-domains for discovery/identity

---

## Suggested Sequencing

| Order | Task | Phase | Status |
|-------|------|-------|--------|
| 1 | Meta-domain for Layer | – | ✅ Done – Layer.meta_domain_inscription_id, meta_domain; Edit modal; fetch_meta_domain_from_inscription |
| 2 | Phase 2.4 – Randomized ballot order | 2.4 | ✅ Done – ballot_order_seed on Vote; _election_candidates_ordered() |
| 3 | Phase 2.4 – Multi-seat polish | 2.4 | ✅ Done – seats, "Elect up to N", "Winners (top N)"; close_vote excludes withdrawn |
| 4 | Phase 3.4 – Artifact lineage | 3.4 | ✅ Done – GET /api/artifacts/<id>/lineage/; D3 lineage graph modal |
| 5 | UUID migration | 6 | ✅ Done – All PKs migrated to UUID |
| 6 | Phase 3.2 – Civic Mason | 3.2 | Pending – Brick model, placement UI, hover state |
| 7 | Phase 2.5 – Digital Monuments Registry UI | 2.5 | Pending – Monument model exists; needs registry UI |
| 8 | Phase 3.3 – Bitcoin Taproot wallet | 3.3 | Pending |
| 9 | Localization | – | Last |

---

## References

- **GOV-HUB-3.md** – Canonical architecture, Phase 0–5
- **UUID_MIGRATION_COMPLETE.md** – Current public_id state; full PK migration deferred
- **RFC_ROLES_CLAIMS_BADGES.md** – Role/claim/badge implementation
