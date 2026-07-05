# Gov Hub Knowledge Layer + Garden

## Phased Implementation Briefing

This briefing defines the structured knowledge layer for Gov Hub and its evolution into a knowledge garden / topic map system compatible with the IFP Garden.

This knowledge layer is **additive**. It does not replace:

- artifact types
- guild functionality
- layer constitutions
- guild constitutions
- governance systems
- civic participation systems

It adds a second semantic layer across the existing architecture.

---

## Locked decisions (product, comms, environment)

- **Outward roadmap:** The **customer-facing** phased story is **§12 Unified Phasing (Phase I–IV)** – civic, constitutions, graph, and interoperability in one arc. **§3** remains the **knowledge-layer** implementation breakdown (forms → relationships → topic map → bundles/interop) for engineering; release notes should **crosswalk** deploy slices to Phase I–IV so expectations stay aligned.
- **Unified Phase I vs II boundary:** **Unified Phase I** includes the **current extent of Civic Mason** (already implemented) and **does not** wait on relationship UI, **advanced** constitution grouping UI, topic **graph**, or **bundles** – those belong to **Unified Phase II** onward. **Unified Phase I** *does* include **collections** as the grouping primitive for constitution sets (and similar), implemented as attach/list semantics; richer constitution **views** and **grouping UX** mature in **Unified Phase II**.
- **Guild (Unified Phase I):** **Guild identity**, **membership** (including richer states as spec’d), **guild ↔ layer link**, and **guild ↔ artifact authorship** (sponsor/co-author/review links as applicable). **Guild internal operating roles** do **not** grant layer governance authority by default.
- **Environments:** Build and experiment on **dev.govhub.live** first. When the stack behaves acceptably, **soft launch** on **govhub.live** (production). Treat dev as disposable for graph experiments unless a migration path is explicitly defined.
- **Contribution type (UX):** User-facing label for `knowledge_form` is **Contribution type** (internal/API may remain `knowledge_form` / stable enum values).
- **`knowledge_form` data rule:** Field is **always optional** and **nullable** when unset – no auto-backfill requirement. **Multi-tag** contribution typing is **not** supported (at most one `knowledge_form` per artifact).
- **Scaffolding:** Optional **per–contribution-type** prompts may ship once `knowledge_form` exists (see **§5** and `artifact_contribution_schema.md`). Every scaffold field stays **optional**; nothing in the scaffold blocks publish. Prefer a **feature flag** for scaffold UI until stable. **Localization** should include scaffold labels and placeholders when scaffold is exposed to users.
- **Who may set contribution type:** **Authors and editors** may set or change `knowledge_form` on artifacts they can edit. **Moderators and administrators** may still override after publish. Operational expectations for overrides: **audit trail** (from → to, actor, timestamp; optional reason), **notification** to authors where practical, and a **written policy** for when reclassification is appropriate (quality and taxonomy vs viewpoint).
- **Localization:** After the rest of **Unified Phase I** is stable, run a **localization pass** (Contribution type labels, help copy, and **scaffold** strings when scaffold is enabled).
- **Graph separation:** **Guild ↔ artifact** (and quest) links stay a **separate** relation family from **artifact ↔ artifact** bridges (Unified Phase II). No merging into one undifferentiated edge model.

---

## Agreed design direction (tacit acceptance)

The following match prior PM recommendations and are **baseline product/engineering expectations** unless superseded.

- **Content bridges vs artifact bridges:** Treat **two predicate namespaces**. **Content bridges** express how *ideas or claims* relate (e.g. `supported_by`, `contradicted_by`, and extensions in that family). **Artifact bridges** express how *governance objects* relate (e.g. workflow, derivation, `informed_by`, `derived_from`, duplicate/same-thread patterns as adopted). Document, API, and UI should not imply one mechanism covers both; labels may use “content link” vs “artifact link” (or qualified “bridge”) for clarity.
- **Permissions:** Content assertions (especially contradicts/supports on others’ work) may warrant **stricter** rules than structural artifact links; define per-predicate or per-family policy.
- **Topic map (Phase 3):** Prefer **layers, filters, or toggles** for content-heavy vs artifact-heavy edges, or a **merged view with a clear legend** – avoid a single undifferentiated edge soup early.
- **Analytics:** Track **content-bridge** adoption separately from **artifact-link** adoption.
- **Bundles (Phase 4):** When a machine bundle format is defined, exports should **name predicate families** (or equivalent grouping) so consumers do not flatten two semantics into one undifferentiated edge list. Until a frozen interchange schema exists, treat published IFP gardens as **human exemplars**, not a byte contract; plan explicit **bundle versioning** when formal exchange lands. **Risk to track:** upstream gardens may define **additional form types** beyond these seven; maintain a **mapping / versioning** story so imports do not silently drop or mislabel nodes.
- **Unified Phase I scope:** **All** artifact types participate: finalize **§4** matrix after review; acceptance includes **at least one create path per artifact type** with optional contribution type, badges, and filters where applicable.
- **Civic Mason:** Baseline is **Unified Phase I** (current product). **Form-aware** or relationship-dependent brick↔artifact enhancements ship with **Unified Phase II** APIs, not as a blocker for contribution typing in Phase I.
- **Environments:** Use **feature flags** (or equivalent) per environment so dev experiments do not dictate production behavior by accident.

---

# 1. Core Concept

We are introducing a second semantic layer to Gov Hub.

- **Artifact Type** = what the artifact does (Proposal, Comment, Resource, Meeting Summary, etc.)
- **Knowledge Form** (storage/API) = what kind of thinking the contribution represents (Inquiry, Principle, Model, etc.). In the **UI**, call this **Contribution type**.

We are NOT replacing artifact types.
We are layering optional structured cognition on top of them (`knowledge_form` nullable).

---

# 2. Knowledge Forms (Aligned with IFP)

These forms must remain stable:

- Inquiry
- Principle
- Model
- Conviction
- Decision
- Gloss
- Scenario

These map directly to IFP Garden forms and should not be renamed or fragmented.

---

# 3. Phased Implementation

**Crosswalk:** This section is the **knowledge-layer-only** slice. The **outward** unified narrative (with civic, graph timing, and meta-layer) is **§12**; map each release to both.

## Phase 1: Structured Knowledge Layer

Goal: Introduce optional **Contribution type** (`knowledge_form`) without disrupting existing workflows.

Key features:

- Keep artifact types unchanged
- Add **optional**, **nullable** contribution type selector (create + edit for **authors and editors**)
- When the user opens the selector, show **smart default** per artifact type and only **3–4** allowed types (not the full seven) per **§4** matrix
- **Optional scaffolding** (§5): lightweight prompts keyed off `knowledge_form`; all optional; flag-gated rollout recommended
- **Badge rules:** see **§4a** (artifact type always; contribution type only when set)
- **Filtering:** see **§4a** (placement options)
- **Collections:** artifacts can be grouped into **collections** (e.g. constitution sets); minimal list/attach semantics in Unified Phase I

Defer to **Unified Phase II** (knowledge-layer crosswalk): relationship editing UI, advanced constitution grouping **UI**, graph view, bundles, **rich** structured fields beyond §5 minimal scaffold (see §6).

Outcome:

- Typed artifacts
- Early structured reasoning

---

## Phase 2: Relationship Layer

Goal: Make reasoning explicit.

Key features:

- Introduce relationships between artifacts (see **Agreed design direction** for **content** vs **artifact** predicate families). Illustrative artifact-side predicates:
  - supports
  - resolves
  - conflicts_with
  - informed_by
  - derived_from
- Lightweight UI to create/view relationships
- Show related items on artifacts

Outcome:

- Connected reasoning graph (implicit)

---

## Phase 3: Knowledge Garden / Topic Map

Goal: Make reasoning visible and navigable.

Key features:

- Graph / topic map view
- Node = typed artifact
- Edge = relationship
- Multiple views:
  - Topic Map (default)
  - Open Inquiries
  - Principles
  - Decision Lineage
- Filtering and clustering
- Bundle / patch creation (group nodes into reusable sets)
- Graph UX: differentiate **content** vs **artifact** edges (layers, filters, or legend) per **Agreed design direction**

Important:

Topic maps are introduced only after sufficient structured data exists.

---

## Phase 4: Interoperability (Meta-layer)

Goal: Enable portability and cross-system knowledge sharing.

Key features:

- Export Gov Hub knowledge as graph bundles (tag **predicate families** in the interchange model when specified)
- Import IFP garden patches
- Mixed local + imported graphs
- Agent-readable governance memory

Outcome:

- Gov Hub becomes garden-compatible and meta-layer ready

---

# 4. Preliminary matrix: Artifact type → Contribution type (`knowledge_form`)

**Implementation mirror:** `artifact_contribution_schema.md` (defaults, allowed sets, validation, UI steps).  
**Status:** Reconcile **slug** names with the live codebase and product labels before implementation.

**Rules:** `knowledge_form` is **nullable**. Picker shows **default + up to three alternates** (four total). User may leave unset. Moderators/admins may override per **Locked decisions**.

| Artifact slug (preliminary) | Typical product label | Default | Picker also (choose ≤3) | Notes |
|----------------------------|------------------------|---------|---------------------------|--------|
| `proposal` | Proposal | Decision | Principle, Model, Inquiry | |
| `document` | Document / working doc | Model | Principle, Scenario, Decision | Merge “working doc” vs `document` in code review |
| `evidence` | Evidence / resource | Model | Scenario, Principle, Gloss | Merge with “Resource” if one type |
| `meeting_summary` | Meeting summary | Model | Scenario, Inquiry | Add Decision if summaries often record decisions |
| `decision` | Decision record | Decision | Principle, Model, Scenario | Disambiguate in UI: artifact type vs contribution type “Decision” |
| `bridge` | Bridge | Gloss | Model, Principle, Inquiry | |
| `translation` | Translation | Gloss | Principle, Model | |
| `monument_context` | Monument context | Scenario | Principle, Gloss, Model | Align with `artifact_contribution_schema.md` |
| `comment` | Comment / reply | Conviction | Inquiry, Principle, Model | |
| `poll` | Poll / vote | Decision | Inquiry, Principle | |
| `announcement` | Announcement | Decision | Principle, Model | |
| `event` | Event | Scenario | Inquiry, Model | |

**Review questions for you:** (1) Confirm one row per **canonical** `artifact_type` in production. (2) `decision` artifact vs **Decision** contribution type – OK with copy (“Decision record” vs “Decision (contribution)”) or rename label. (3) Whether `event` warrants **Decision** in the alternate set for scheduled governance milestones. (4) Schema doc uses **`monument_context`** as canonical slug.

---

# 4a. Badges, filters, feature flags, analytics, indexes (Unified Phase I)

## Badge rules

- **Always show** artifact type (existing behavior).
- **Contribution type:** show a **second badge** only when `knowledge_form` is **non-null** – avoids noisy “empty” chips and keeps lists scannable.
- **Order:** `[Artifact type] · [Contribution type]` (contribution type secondary).
- **Truncation:** on narrow layouts, truncate **artifact type** first if needed; keep contribution type readable when present (or collapse to icon + tooltip – product choice).
- **Consistency:** same component on list rows, detail header, and (if applicable) thread previews; omit second badge in compact contexts only if explicitly designed (e.g. mobile one-line).

## Filter placement (options)

- **Primary artifact feeds / search:** add **Contribution type** as a **facet** (multi-select) next to existing filters – highest value.
- **Guild / layer artifact tabs:** same facet when those views are artifact-centric.
- **Collections / constitution sets:** optional facet inside collection scope.
- **Defer:** graph-specific filters to Unified Phase II (graph itself is Phase II+ per §12).

## Feature flags (pattern)

- **`knowledge_contribution_type_enabled`** (global or per-tenant): master switch to show selector, badges, and filters; allows instant rollback on **govhub.live**.
- **`knowledge_contribution_type_filters_enabled`:** optional sub-flag if you want to stage filters after create/edit ships.
- **Environment defaults:** **on** on **dev.govhub.live** for dogfooding; **off** or **pilot tenants only** on production until soft launch criteria met.

## Events / analytics (minimum)

- `contribution_type_set` (artifact_id, type, source: create|edit|moderation)
- `contribution_type_cleared`
- `contribution_type_filter_applied` (facet values, surface: feed|search|guild|…)
- Keep names stable so Unified Phase II can add `artifact_link_created` / `content_link_created` without renaming Phase I events.

## Indexes

- Index **`knowledge_form`** for filtered lists (and composite `(layer_id, knowledge_form)` or equivalent if queries are always scoped).
- If filtering “unset only,” use **`WHERE knowledge_form IS NULL`** – ensure planner-friendly partial index if that query is hot.

---

# 5. Optional scaffolding (minimal v1)

**Purpose:** When `knowledge_form` is set, offer **optional** prompts so authors can add a little structure without required schemas.

**Storage (recommended):** `knowledge_scaffold` – nullable JSON object on the artifact (or equivalent). Shape **depends on** `knowledge_form`. If `knowledge_form` is **null**, `knowledge_scaffold` must be **null** on write (server clears orphaned scaffold).

**Rules:**

- **No required** scaffold fields – ever, in this v1.
- **String fields:** trim whitespace; enforce a **max length** (e.g. 2000 UTF-8 codepoints per field; tune per product).
- **Enums** below are optional; allow `null` = “not specified.”
- Ship behind **`knowledge_scaffold_enabled`** (or combine with contribution-type master flag) until validated.

**Per-form shapes (v1):**

| `knowledge_form` | JSON keys (all optional) | UI prompt (English; localize) |
|------------------|---------------------------|-------------------------------|
| `inquiry` | `what_is_unclear` (string), `status` (`open` \| `closed`) | What is unclear? / Status |
| `principle` | `why_matters` (string) | Why does this matter? |
| `model` | `key_assumptions` (string) | Key assumptions |
| `claim` | `why_believe` (string) | Why do you believe this? |
| `decision` | `what_resolves` (string), `status` (`draft` \| `final`) | What does this resolve? / Status |
| `gloss` | `definition` (string) | Definition |
| `scenario` | `actors_context` (string) | Actors / context |

**Validation:** Reject unknown keys for the active `knowledge_form`. Changing `knowledge_form` may **drop** scaffold keys that do not apply (product choice: wipe vs migrate – default **wipe** for v1 simplicity).

**Readiness to implement:** `knowledge_form` enum + API stable; contribution-type picker live or in same release; migration adds nullable JSON column; copy deck + i18n keys for prompts.

---

# 6. Future (Rich Forms)

Beyond §5 minimal scaffold, each form may gain **richer** structure (lifecycle, lineage UI, linked artifacts, etc.) – typically **Unified Phase II+**:

- Inquiry → related models, candidate resolutions, full status lifecycle
- Principle → scope, explicit conflict links
- Model → mechanisms, tradeoffs
- Conviction → confidence, evidence, evolution
- Decision → lineage, supporting inputs (ties to relationship layer)
- Gloss → aliases, examples, cross-links
- Scenario → steps, outcomes, failure modes

§5 must not block these extensions (keep `knowledge_scaffold` evolvable or add parallel columns later).

---

# 7. Knowledge Garden Concept

A knowledge garden is:

> a graph of typed reasoning across artifacts

- Nodes = knowledge-form-typed artifacts
- Edges = relationships
- Bundles = reusable topic groupings

This mirrors the IFP Garden model.

---

# 8. Topic Map Timing

Topic maps should be introduced in Phase 3, not earlier.

Requirements before launch:

- sufficient typed artifacts
- meaningful distribution across forms
- early relationships present

Otherwise the graph will be empty or misleading.

---

# 9. IFP Compatibility

We are explicitly designing for compatibility with the IFP Garden.

Requirements:

- keep the 7 knowledge forms unchanged
- treat typed artifacts as graph nodes
- support relationships as edges
- support export/import of node-edge bundles

Implication:

- Gov Hub can import IFP gardens
- Gov Hub can export its own gardens
- IFP Garden can act as a reference implementation

---

# 10. Import / Export Model (High-Level)

Use a portable graph format:

- Bundle
- Nodes (knowledge-form typed)
- Edges (relationships)

Gov Hub mappings:

- Artifact → Node
- Relationship → Edge
- Topic / bundle → Garden bundle

This enables interoperability without changing internal architecture.

---

# 11. Knowledge Layer Integration (Critical)

The Knowledge Layer is an **orthogonal semantic layer applied to all artifacts**.

It augments rather than replaces existing system components.

## Core Rule

Every artifact has BOTH:

- artifact_type (what it does)
- knowledge_form (what kind of thinking it represents)

---

## Integration with Artifact System

All artifact types support knowledge forms, including:

- proposal
- document
- evidence
- meeting_summary
- decision
- bridge
- translation
- monument_context

Examples:

- proposal + Decision
- document + Principle
- meeting_summary + Model or Scenario
- glossary entry + Gloss

---

## Integration with Guilds

Guilds are knowledge-producing entities.

They:

- produce artifacts across knowledge forms
- may specialize in forms (e.g., Principle-heavy guilds)
- may develop constitutions composed of structured reasoning

---

## Integration with Layers

Layers are also governance-producing entities and may have their own constitutions.

Layer constitutions are composed of artifacts WITH knowledge forms.

Examples:

- Layer purpose statement → Principle
- Layer governance process → Model
- Layer decision rule → Decision
- Layer glossary / shared terms → Gloss

This means layers, like guilds, can use the draft / review / adoption system to develop constitutional structures through artifacts.

---

## Integration with Constitutions

Both **guild constitutions** and **layer constitutions** are composed of artifacts WITH knowledge forms.

Examples:

- Purpose → Principle
- Governance model → Model
- Rule / adopted policy → Decision
- Definitions / terms → Gloss
- Future planning clause → Scenario

This transforms constitutions into:

> structured reasoning systems, not static documents

---

## Integration with Meeting Summaries

meeting_summary artifacts:

- are typically Model or Scenario
- may also be Inquiry in lightweight capture mode
- can generate downstream artifacts:
  - Inquiry
  - Decision
  - Proposal
  - Principle

They act as:

> entry points into the knowledge graph

---

## Integration with Civic Mason

- **Unified Phase I:** Civic Mason baseline (already in product) may link bricks to artifacts; those artifacts may carry optional **Contribution type** when set.
- **Unified Phase II+:** Deeper **form-aware** or relationship-driven civic↔knowledge behavior (anything that depends on **artifact ↔ artifact** APIs) ships with the relationship layer.

Result over time:

> civic structure can reflect patterns of thinking as contribution typing and graphs mature

---

## Relationship Alignment

Use **one** relationship system in the product, with **two explicit families** of predicates (see **Agreed design direction**):

- **Content bridges** – how propositions or narrative content relate (e.g. `supported_by`, `contradicted_by`; align naming with governance copy and moderation policy).
- **Artifact bridges** – how artifacts link as objects in workflow and lineage (e.g. `informed_by`, `derived_from`, `resolves`, `conflicts_with` where used as **object** links rather than textual support).

Illustrative artifact-side predicates (exact names are implementation details):

- supports / resolves / conflicts_with / informed_by / derived_from

No duplicate relationship **store** or parallel graph should be created; **do** keep predicate families distinct in UX, permissions, analytics, and export.

---

# 12. Unified Phasing (Aligned)

**Primary outward story:** Use **Phase I–IV** below for public roadmap, partner briefings, and sequencing expectations. Detailed knowledge milestones without civic/graph packaging live in **§3**.

## Phase I – Core System + Knowledge Layer + Civic (baseline)

- layers
- artifact system
- draft / vote / adoption
- identity anchors
- meeting_summary
- **Civic Mason** at **current** implemented extent (bricks / participation baseline – not deferred)
- optional **Contribution type** (`knowledge_form`, nullable) per **§3–§4**
- **Collections** as grouping primitive (e.g. attach artifacts to a constitution set); minimal UX
- **Guilds (extensions in this phase):** identity surface, membership, **guild ↔ layer** link, **guild ↔ artifact** authorship/sponsorship/review links per guild extensions briefing
- support for layer and guild constitutions **as adopted artifacts** grouped via **collections**

Defer to **Phase II** (do not block Phase I on):

- relationship editing UI (artifact ↔ artifact, content bridges)
- **advanced** constitution grouping / visualization UI (beyond collections list/attach)
- topic **graph** view
- **bundles** import/export
- **required** heavy schemas; **rich** form structures beyond **§5** optional scaffold (optional scaffold stays Unified Phase I–appropriate)

Goal:

> low-friction governance + structured cognition + civic baseline

---

## Phase II – Relationships + Constitutions (depth)

- artifact relationships
- knowledge relationships (same system)
- richer **constitution** grouping and **views** (building on collections)
- bundle-oriented workflows as applicable
- guild governance activation (Tier 2+)

Goal:

> connected reasoning + composable governance

---

## Phase III – Civic Layer (expansion)

Builds on **Civic Mason baseline from Phase I**.

- badge system (deeper integration)
- brick system **expansion** and visible participation **at scale**
- optional synergy with knowledge layer (e.g. contribution-type-aware surfacing) as specs mature

Goal:

> governance becomes more visible and embodied

---

## Phase IV – Graph + Interoperability

- topic maps
- knowledge garden
- bundle import/export (IFP compatibility)
- Overweb / Canopi integration

Goal:

> meta-layer knowledge system

---

# 13. Strategic Framing

This is not just a UX feature.

It is the introduction of:

> a cognitive substrate for governance

Progression:

- Phase 1 → classify thinking
- Phase 2 → connect thinking
- Phase 3 → visualize thinking
- Phase 4 → share thinking across systems

---

# 14. Key Design Constraints

Do NOT:

- replace artifact types
- show a giant flat list of options
- enforce heavy schemas early
- launch empty graph views
- create a second, duplicate relationship system
- treat guild constitutions or layer constitutions as special objects outside the artifact model

Do:

- use layered selection
- use smart defaults
- keep forms lightweight initially
- preserve extensibility
- maintain IFP compatibility
- keep both layer and guild constitutions inside the artifact-first model
- keep **content-bridge** and **artifact-bridge** semantics distinguishable in UX, permissions, analytics, and future export (see **Agreed design direction**)

---

# 15. Outcome

If implemented correctly:

- Gov Hub remains easy to use
- Governance becomes structured and legible
- Threads become reusable knowledge
- Guild constitutions become structured reasoning systems
- Layer constitutions become structured reasoning systems
- Topic maps emerge naturally
- System becomes compatible with IFP Garden

---

# End of Briefing

