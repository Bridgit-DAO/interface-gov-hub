# Gov Hub — All Remaining Tasks & Progress

**Project:** gov-hub  
**Date:** 2026-03-12  
**Purpose:** Complete list for JAUmemory and handoff. Source: PLANNING_FULL_PICTURE.md, GOV-HUB-3.md, GOV-HUB-2.md, artifact_specification.md.

---

## DONE (Completed)

| Item | Notes |
|------|-------|
| Project → Layer rename | Model, table, routes, frontend |
| public_id (UUID-style URLs) | Entities expose public_id; routes accept UUID |
| Election flow | Self-registration, multi-candidate ballots, claim creation |
| Reinscription resolution | get_last_inscription_for_sat() |
| EventLog | Append-only table; emit from Vote, Claim, Badge, etc. |
| Artifact + ArtifactRelation | Base model, Submission linked via artifact_id |
| Activity feed | Layer-scoped, reads EventLog |
| Waitlists | Models, APIs, layer tab, embed widget |
| **Artifact public_ref** | First 8 chars of public_id + "io" |
| **Artifact short ref resolution** | URLs like /layers/x/artifacts/ed3f6ea9io/ |
| **Lineage API** | GET /api/artifacts/<id>/lineage/ |
| **Lineage graph** | D3 force-directed on artifact detail modal |
| **Status lifecycle badges** | draft, submitted, under_review, adopted, etc. |
| **artifact_status_changed EventLog** | Emitted on status transitions |
| **Artifacts tab** | Layer page tab, GET /api/layers/<id>/artifacts/ |
| **Activity feed artifact events** | artifact_created, artifact_updated, artifact_status_changed, artifact_linked → Artifacts tab |
| **Meta-domain for Layer** | Layer.meta_domain_inscription_id, meta_domain; Edit Layer modal; fetch_meta_domain_from_inscription + get_last_inscription_for_sat |
| **Randomized ballot order** | ballot_order_seed on Vote; _election_candidates_ordered() deterministic shuffle; used in ballot APIs |
| **Multi-seat clarity** | seats, "Elect up to N", "Winners (top N)"; close_vote excludes withdrawn from winners |
| **Candidate withdrawal** | POST .../candidates/<id>/withdraw/; "Your Candidacy" card with Withdraw button; close_vote excludes withdrawn |
| **Modularization** | Phase A–E: models/, services/, routes/, app.py, run.py, wsgi.py; ietf_data_viewer_simple.py removed |
| **New navigation** | Home \| Contribute \| Governance \| Community \| Recognition \| Learn (dropdowns, mobile toggler) |
| **Vote.artifact_id** | artifact_id, layer_id, vote_type, role_id, seats; migration backfills from project_id |
| **Layer resolution** | resolve_layer_from_host in middleware; subdomain/path routing |

---

## NOT DONE (Remaining)

### Architecture & Refactor

| Task | Source | Notes |
|------|--------|-------|
| **Localization (i18n)** | PLANNING_FULL_PICTURE | Interface strings, date/number formatting, RTL. Planned last. |

### Phase 3+ — Artifact & Governance

| Task | Status | Notes |
|------|--------|-------|
| Vote.artifact_id | Done | artifact_id, layer_id, vote_type, role_id, seats added; migration backfills layer_id from project_id |
| Layer resolution middleware | Done | resolve_layer_from_host in middleware; subdomain/path routing |
| Artifact / Inscription ↔ Meta-domain | Deferred | Link for discovery/identity |
| Bridge | Not done | Artifact ↔ external URL / monument |
| IdentityAnchor | Deferred | User suffices for now |
| Badge Keeper Role | Not done | Phase 2 |
| PEARL | Not done | Phase 3 — reflection artifact, 5 fields |
| Triad (distinct) | Deferred | May map to Workgroup with type=triad |

### Migration (Deferred)

| Task | Status | Notes |
|------|--------|-------|
| Full UUID PK migration | Deferred | User, Layer, Submission, etc. int/string → UUID. Large; maintenance window. |

---

## Suggested Order

1. ~~Modularization~~ ✓
2. ~~New navigation~~ ✓
3. ~~Vote.artifact_id~~ ✓
4. ~~Layer resolution~~ ✓
5. UUID migration (when ready)
6. Localization (last)

---

## References

- **MODULARIZATION_SPEC.md** — File-by-file extraction plan (models, routes, services, phased execution)
- PLANNING_FULL_PICTURE.md
- GOV-HUB-3.md
- GOV-HUB-2.md
- artifact_specification.md
- JAUmemory_RECORDS.md
