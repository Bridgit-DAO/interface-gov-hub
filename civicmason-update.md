# Gov Hub – Protocol Canvas Updates

This document captures the **additional protocol-level clarifications** that should be incorporated so the system does not drift as design and implementation continue.

These updates elevate several ideas from UI behavior or conversation into explicit protocol / architecture rules.

---

# 1. Civic Mason Placement Protocol

The brick system is not just UI. It is part of the protocol.

## Core placement rules

- Bricks grow **bottom-up only**
- A new brick must overlap at least **50% of a supporting brick below**
- Base row bricks sit directly on the bottom edge of the canvas
- Sparse early emergence is expected and is **not** a failure state
- Placement is permanent after confirmation, except for the 5-second cancel window

These are protocol rules, not optional front-end affordances.

---

# 2. Brick Placement Eligibility Protocol

Brick placement must be explicitly governed by eligibility rules.

## Eligibility requirements

- User must hold the relevant **Civic Mason badge**
- User may place **only one brick per IdentityAnchor per year per layer**
- Placement rights are consumed upon confirmation

This prevents duplicate placements and preserves the meaning of brick placement as a civic ritual.

---

# 3. Contribution → Artifact → Badge → Placement Chain

This chain should be explicit in the protocol.

## Canonical sequence

1. User takes action / contributes
2. Action produces an **artifact**
3. Artifact is reviewed / validated
4. Badge is awarded
5. Badge unlocks brick placement

This ties contribution, governance, and visible recognition into a single protocol flow.

---

# 4. Artifact Graph Clarification

Artifacts are first-class protocol objects.

The artifact graph must support typed relationships between:

- artifact → artifact
- artifact → role
- artifact → vote
- artifact → quest
- artifact → monument
- artifact → layer

These relationships are part of the protocol itself, not just UI navigation.

---

# 5. Bridges as First-Class Relationships

Bridges are not merely interface links.
They are protocol-level typed relationships.

## Bridge categories

- **Internal bridges** = artifact graph relationships inside Gov Hub
- **External bridges** = links from artifacts/monuments to web resources

Examples:

- artifact → artifact
- artifact → web page
- artifact → image
- artifact → text fragment
- artifact → video timestamp
- artifact → monument

Bridges must be modeled as first-class relationships.

---

# 6. Bridge Phasing Clarification

Bridge capability should be phased clearly.

## Phase I

- internal artifact graph relationships
- basic typed relationships between governance objects

## Phase II

- external bridge system
- web linking
- alpha bridge behavior inside Gov Hub
- eventual migration path to Canopi / Overweb applications

This should be reflected explicitly in phasing documents.

---

# 7. UUID + `io` Reference Convention

Protocol documentation should clearly distinguish between internal and public identifiers.

## Rule

- UUID = canonical internal identifier
- public_id = human-readable short identifier
- `io` suffix = artifact reference marker in public contexts

Example:

- artifact UUID = canonical identity
- artifact public_id = `A47`
- artifact public_ref = `A47io`

The `io` suffix is not part of the UUID itself.
It is a public-facing signal that the object is an information object / artifact.

---

# 8. Event System Completeness

The event stream must explicitly include the full governance lifecycle.

Minimum protocol-level event coverage should include:

- layer_created
- member_joined_layer
- member_left_layer
- member_removed
- role_claimed
- role_term_ended
- triad_formed
- triad_report_filed
- artifact_created
- artifact_linked
- artifact_reviewed
- artifact_adopted
- vote_started
- ballot_cast
- vote_closed
- election_opened
- election_closed
- quest_completed
- quest_reviewed
- badge_awarded
- monument_registered
- bridge_created
- bridge_updated
- layer_config_changed
- milestone_reached
- goal_created
- goal_updated
- roadmap_item_changed
- brick_placed
- brick_message_updated

This keeps lineage, activity feeds, and notifications complete.

---

# 9. Bootstrap Governance Model

The bootstrap governance pattern must be explicit in the protocol.

## Rule

- Initiator becomes initial bootstrap admin
- Initiator may appoint additional admins
- Bootstrap admins may form an initial governance triad
- Bootstrap admin powers are temporary and must sunset

## Transition rule

When governance thresholds are met (or governance is activated by vote), admin override powers sunset and governance transitions to role/triad/vote-based stewardship.

All bootstrap actions must emit events.

---

# 10. Documents Are Artifacts

Documents should not be treated as a separate conceptual category outside the artifact model.

## Rule

Documents are a type of artifact.

They may be:

- governance instruments
- policies
- templates
- tools
- guides
- adopted documents across layers

This should be explicit so the artifact-first architecture remains coherent.

---

# 11. Structural Integrity Rule

This should be added as a protocol / architecture guardrail.

## Rule

The system must prioritize **structural integrity and rule visibility over UI convenience**.

No interface should allow actions that violate underlying governance, artifact, or placement constraints.

This protects the protocol from future “helpful” UX changes that would erode the actual system logic.

---

# Summary

These updates ensure that:

- the brick system is treated as protocol, not decoration
- bridges are treated as first-class relationships
- artifacts remain central
- event history is complete
- bootstrap governance is explicit
- documents stay inside the artifact model
- future UI changes cannot violate structural rules

---

# Mural Background Plan

Use `civicmason-mural.png` as the full-page background for the Civic Mason page.

## Mural Composition (from civicmason-mural.png)

The mural has three horizontal bands:

1. **Bottom** – Silhouetted workers/masons (hard hats, bricks, trowels); sepia-toned, faded fresco style; represents human effort and foundation.
2. **Middle** – Solid brick wall; earthy reds, oranges, browns; mortar lines; bridge between workers and vision.
3. **Top** – City skyline in golden glow; hemispherical network/grid above; digital connectivity / civic infrastructure.

**Style:** Vertical (portrait), warm earthy palette, weathered texture, central light source drawing eye upward.

## Implementation Plan

### 1. Asset Placement

- Copy `civicmason-mural.png` to `static/images/civicmason-mural.png` (or `static/images/civic-mason/`).
- Serve via `/static/images/civicmason-mural.png`.

### 2. Page Layout

- **Full-page background:** Apply mural as `background-image` on the Civic Mason page container (or a dedicated wrapper).
- **Cover behavior:** `background-size: cover` so mural fills viewport; `background-position: center` to keep composition balanced.
- **Repeat:** `background-repeat: no-repeat`.

### 3. Layering (Z-Order)

Per spec: mural must NOT constrain placement. Z-order:

1. Mural (bottom, low opacity if needed for contrast)
2. Optional overlay (e.g. `rgba(0,0,0,0.1)`) to reduce contrast under bricks
3. Brick grid + drop zones
4. Header / breadcrumb / Place Brick controls
5. Modals (confirmation, etc.)

### 4. Contrast & Readability

- **Header / breadcrumb:** Use semi-transparent background or text shadow so they remain readable over the mural.
- **Brick grid:** Placed bricks sit over the middle band; ensure sufficient contrast (mural may need `filter: brightness()` or overlay).
- **Bright top band:** The golden glow at top may wash out content; consider:
  - Darkening overlay over the mural
  - Or positioning primary UI (grid, header) over the middle/bottom bands where contrast is better

### 5. Responsive Behavior

- **Desktop:** Full mural visible; grid centered or aligned over middle band.
- **Mobile:** Mural scales; consider `background-position: center bottom` so workers + brick wall remain visible when viewport is short.
- **Aspect ratio:** Mural is portrait; on wide screens, sides may crop. Center keeps the narrative (workers → wall → city) intact.

### 6. Protocol Alignment

- Mural is **symbolic only** – does not define grid, slots, or placement rules.
- Grid rules (bottom-up, 50% overlap, base row) remain protocol-defined.
- Mural reinforces meaning; bricks are placed by users and grow over the mural.

### 7. Implementation Steps

| Step | Action |
|------|--------|
| 1 | Add mural to `static/images/` |
| 2 | Create full-page wrapper for Civic Mason route with mural background |
| 3 | Add overlay (optional) for contrast; tune opacity |
| 4 | Ensure header, breadcrumb, and controls have readable contrast |
| 5 | Test on mobile; adjust `background-position` if needed |
| 6 | Verify brick grid remains clearly visible over middle band |
