# ML-REQ and ML-ADR Specification

**Status:** Draft (dev implementation started Aug 2026)  
**Branch:** `development` on `gov-hub-dev`  
**Vision:** [`meta-console/docs/OVERWEB-ESTATE-VISION.md`](../../meta-console/docs/OVERWEB-ESTATE-VISION.md)  
**Artifact base:** [`artifact_specification.md`](../artifact_specification.md)

---

## 1. Purpose

**ML-REQ** (Meta-Layer Requirement) and **ML-ADR** (Meta-Layer Architecture Decision Record) connect governance to code. Desirable Properties and Hermes-guided Minimum Permissible Affordances become testable requirements; engineering records how each requirement is enforced.

**Where this applies:** ML-REQ/ML-ADR gates are enforced on the **Overweb substrate** via **Overweb Studio** (layer/app builder, sandbox, progressive deploy). **BRC333 Studio** (`app.brc333.xyz`) immortalizes forever artifacts on Bitcoin; it does not replace substrate enforcement. A promoted substrate app may later inscribe an attestation through BRC333 Studio.

```
Desirable Properties → Hermes (MPA) → ML-REQ → ML-ADR → substrate code + CI
                                                              ↓
                                    optional immortalization → BRC333 Studio
```

---

## 2. Identifiers

| Type | `Submission.doc_type` | Public number | Example |
|------|----------------------|---------------|---------|
| ML-Draft | `draft` | `ML-Draft-NNN` | ML-Draft-042 |
| ML-RFC | `rfc` | `ML-RFC-NNN` | ML-RFC-003 |
| ML-REQ | `req` | `ML-REQ-NNN` | ML-REQ-001 |
| ML-ADR | `adr` | `ML-ADR-NNN` | ML-ADR-001 |

Numbering uses `get_next_ml_number()` in `services/submissions.py`. Layer-specific prefixes apply (e.g. `CL-REQ-001`).

**Artifact types** (GOV-HUB-3): `requirement` and `adr` mirror submission semantics for relations, votes, and lifecycle UI.

Constants: `services/ml_document_types.py`.

---

## 3. ML-REQ fields

Extend submission body (Markdown frontmatter or structured JSON in `Artifact` metadata when migrated):

| Field | Required | Description |
|-------|----------|-------------|
| `scope` | yes | `overweb-app` \| `estate-service` \| `protocol` \| `layer` |
| `priority` | yes | `must` \| `should` \| `may` (RFC 2119) |
| `acceptance_criteria` | yes | List of machine-checkable conditions |
| `verification_method` | yes | `test` \| `lint` \| `audit` \| `manual` |
| `implements_dp` | no | e.g. `DP8` (Vicariance) |
| `mpa_ref` | no | Minimum Permissible Affordance label |
| `status` | yes | `draft` → `under_review` → `approved` → `implemented` → `deprecated` |

### Relations

- `implements` → ML-ADR
- `derived_from` → ML-Draft, Desirable Property
- `verified_by` → Evidence artifact
- `supersedes` / `amends` → other ML-REQ

### Seed requirements (Overweb)

| ID | Title | DP |
|----|-------|-----|
| ML-REQ-001 | Sandbox isolation before production deploy | DP8 |
| ML-REQ-002 | AI disclosure and consent in layer UI | TBD |
| ML-REQ-003 | Anonymized tag stream consent | TBD |

---

## 4. ML-ADR fields

| Field | Required | Description |
|-------|----------|-------------|
| `context` | yes | Problem and constraints |
| `decision` | yes | What was chosen |
| `consequences` | yes | Tradeoffs |
| `enforcement` | yes | Repo paths, CI jobs, CLI commands (`meta-layer req verify`) |
| `status` | yes | `proposed` → `accepted` → `deprecated` → `superseded` |

### Relations

- `decides_for` → ML-REQ
- `builds_on` → other ML-ADR
- `implemented_by` → Implementation artifact

### Seed ADRs

| ID | Title |
|----|-------|
| ML-ADR-001 | `deployment_stage` enum and sandbox routing |
| ML-ADR-002 | GhDialog-only confirmations (workspace rule) |

---

## 5. Implementation phases (gov-hub-dev)

### Phase A (this sprint)

- [x] `services/ml_document_types.py` constants
- [x] `doc_type` accepts `req`, `adr` on submission create
- [x] `requirement` / `adr` in knowledge-layer artifact schema
- [x] Artifact picker includes `requirement`, `adr`
- [ ] Submit form UI: doc_type selector includes ML-REQ / ML-ADR
- [ ] Layer docs tab lists req/adr submissions
- [ ] Template markdown for new ML-REQ / ML-ADR

### Phase B

- Structured metadata column or JSON on `Artifact` for acceptance_criteria, enforcement
- API: filter artifacts by `artifact_type=requirement`
- Vote references ML-REQ artifacts
- Hermes export: MPA session → draft ML-REQ on dev hub
- **Overweb Studio** reads approved ML-REQs before production promote (substrate gate; not BRC333 Studio)

### Phase C

- GitHub sync paths `ml-req/**`, `ml-adr/**`
- `meta-layer req verify` reads ML-ADR enforcement from API or synced files
- OpenAPI documentation

---

## 6. Hermes integration

Hermes (`neo4j-knowledge-graph`, port 8790) drafts contributions today. Phase B adds:

1. User explores DPs on theoverweb.org or desirableproperties.org/agent
2. Hermes proposes MPA set + ML-REQ outline
3. `POST` to Gov Hub dev with `doc_type=req` (when `HERMES_GOVHUB_ENABLED=1`)

See [`neo4j-knowledge-graph/docs/HERMES-ESTATE-SCOPE.md`](../../neo4j-knowledge-graph/docs/HERMES-ESTATE-SCOPE.md).

---

## 7. Testing

```bash
cd /home/ubuntu/gov-hub-dev
python3 -m pytest test_ml_document_types.py test_knowledge_layer_integration.py -q
```

Manual: create submission with `doc_type=req` on dev; approve; confirm `ML-REQ-001` numbering.

---

*Evolve, don't replace. Submissions remain the transport until full artifact migration completes.*
