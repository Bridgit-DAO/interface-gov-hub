# Civic Mason – Brick Placement Interface Specification

This document defines the intended user experience and rules for the Civic Mason brick placement interface.

It is meant to guide design and implementation in Cursor.

---

# Implementation Status (Updated)

## Implemented

| Feature | Status | Notes |
|---------|--------|-------|
| Badge-gated eligibility | Done | User must have issued badge from role with `civic_mason_eligible=True` |
| Global wall | Done | Single wall at `/civic-mason/`; not layer-scoped |
| Half-offset grid | Done | Row 0: x=0,1,2,…; Row 1: x=0.5,1.5,…; colors by year |
| Placement scaffold / drop zones | Done | Dashed outlines on empty valid slots |
| Drag-and-drop | Done | Draggable brick source; drop on valid slots |
| 5-second confirmation | Done | Modal with countdown; Cancel aborts |
| Message (max 200 chars) | Done | Optional message in confirmation modal; append-only history via `BrickMessage` |
| Support rule | Done | Row > 0 requires at least one brick below |
| 50% row limit | Done | At most half of slots per row filled |
| Hover tooltip | Done | Display name + message on hover |
| Non-Mason state | Done | No drag source or Place Brick for ineligible users |
| Mason state | Done | Place Brick + draggable brick when eligible |
| Nav link | Done | Recognition → Civic Mason |

## Deviations from Spec

| Spec | Implementation |
|------|----------------|
| One brick per person per year per layer | **Not enforced.** No per-year limit. Users can place multiple bricks. |
| Layer-scoped | **Global first.** Layer scope is allowed; starting with `layer_id = NULL`. |
| Message after confirmation | Message is in the confirmation modal (before API call), not a separate step after. |
| Testing mode (`earned = true` bypass) | Not implemented. |

## Civic Mason Next Steps (Integrated Roadmap)

The following phases integrate the interface spec, Task 14 (Brick System + UI), and Task 15 (Localization) into a single implementation sequence.

### Phase A – Data & Eligibility (Foundation)

| Step | Description | Spec |
|------|-------------|------|
| A1 | Add optional `layer_id` to Brick; support layer-scoped walls (start with NULL = global) | Design Decision |
| A2 | Enforce one brick per user per year (per layer) | Core Rule, Eligibility Logic |
| A3 | Add `color_variant` to Brick; year-based palettes (5–7 variants) | Task 14 Color System |
| A4 | Testing bypass: `earned = true` for dev | Testing Mode |

### Phase B – Eligibility UX & States

| Step | Description | Spec |
|------|-------------|------|
| B1 | "Already placed" state: show "You've already placed your brick for this year" when ineligible | Already Placed State |
| B2 | Message update flow: view brick, update message, view history | Already Placed State, Message System |
| B3 | Aspirational CTAs for non-Masons: "Earn your Civic Mason badge"; Start Steward Challenge, View Open Quests, Learn how to earn | Non-Mason State |

### Phase C – Visual & Interaction Polish

| Step | Description | Spec |
|------|-------------|------|
| C1 | Color variant selection before placement (from current year palette) | Task 14 Interaction Flow |
| C2 | Hover slot: highlighted outline + snap preview during drag | Task 14 Visual States |
| C3 | Richer hover panel: avatar, badge, year, layer, message, "view history", artifact links | Hover Behavior, Task 14 Hover / Detail Panel |
| C4 | Brick rendering: soft bevel, micro-noise texture, subtle variation | Task 14 Brick Rendering |
| C5 | Aging system: darkening/desaturation, edge wear over time (client-side from timestamp) | Task 14 Aging System |

### Phase D – Mural & Full-Page Experience

| Step | Description | Spec |
|------|-------------|------|
| D1 | Full-page mural background (symbolic, non-constraining) | Mural Concept |
| D2 | Three-band mural composition: builders (bottom), brick field (middle), network/future (top) | Task 14 Mural |
| D3 | Full-page civic surface; mural fades under bricks | Full-Page Visual Concept |
| D4 | Grid helper toggle (show/hide scaffold outlines) | Task 14 Rendering Layers |

### Phase E – Performance & Scale

| Step | Description | Spec |
|------|-------------|------|
| E1 | Tiling/virtualization for large walls | Task 14 Performance |
| E2 | Lazy-load bricks outside viewport | Task 14 Performance |

### Phase F – Localization (Task 15)

| Step | Description | Spec |
|------|-------------|------|
| F1 | Interface i18n: externalize UI strings, key-based lookup, user language preference | Task 15 Interface Localization |
| F2 | ArtifactTranslation model + workflow (draft → review → accepted) | Task 15 Artifact Translation |
| F3 | Language toggle on artifact view; fallback to original | Task 15 UI Behavior |

### Architectural Constraint (All Phases)

**"Never Let Presentation Shape the System"** – Mural must NOT define grid or placement. All relationships via Artifact, ArtifactRelation, EventLog.

## Code Locations

- `models/coordination.py` – Brick, BrickMessage, Role.civic_mason_eligible
- `services/civic_mason.py` – Eligibility, placement validation
- `routes/civic_mason.py` – API: `/api/civic-mason/bricks/`, `/eligible/`
- `routes/civic_mason_pages.py` – Page at `/civic-mason/`, drag-drop UI

## Design Decision: Layer Scope

**Allow layer scope**, but start with `layer_id = NULL` (global wall).

- The model and API should support an optional `layer_id` on Brick.
- When `layer_id` is NULL, the brick belongs to the global wall.
- Layer-scoped walls can be added later; the initial deployment is global only.

---

# Core Rule

Only people who have earned a **Civic Mason badge** may place a brick.

Constraint:

- **One brick per person per year per layer**

This is not just a permission rule. It is part of the meaning of the system.

Placing a brick is a **status-gated civic ritual**, not a generic UI action.

---

# Eligibility Logic

A person may place a brick only if:

- `has_civic_mason_badge == true`
- `brick_placed_this_year == false`

If both are true:
- user is eligible to place a brick

If not:
- user is not eligible

---

# Testing Mode

For testing, the system should allow:

- `earned = true`

This bypasses the badge check so the placement interface can be exercised in development.

---

# Two Main Interface States

## 1. Non-Mason State

This is the default state for most users.

The user sees:

- full-page mural / brick canvas
- existing bricks
- faint placement scaffold / outlines

The user does **not** see:

- an available brick
- drag interaction
- placement trigger

Instead, the interface should clearly communicate:

> Earn your Civic Mason badge to place your brick.

Possible calls to action:

- Start a Steward Challenge
- View Open Quests
- Learn how to earn Civic Mason

Important tone rule:

This should not feel like rejection or a locked paywall.
It should feel aspirational and invitational.

---

## 2. Mason State

This state appears only if the person has earned Civic Mason and has not yet placed a brick for the current year / layer.

The user sees:

- the same mural / brick canvas
- existing bricks
- faint placement scaffold
- a **triggered placement affordance**

The brick placement trigger should appear **only** if the person is eligible.

Recommended affordance:

- a clear **“Place Your Brick”** call to action
- or a subtle highlighted prompt indicating that the user has a brick available

The placement UI should not appear at all for ineligible users.

---

# Full-Page Visual Concept

The interface should be a **full-page civic surface**, not a form.

The page should show:

- a mural or symbolic background
- staggered brick placement outlines
- existing placed bricks
- a growing collective structure

This should feel like:

- a living civic monument
- a shared construction surface
- a symbolic record of contribution

It should not feel like:

- a checkout form
- a submission wizard
- a configuration panel

---

# Mural Concept

A mural should sit underneath the brick surface.

Purpose of the mural:

- reinforce meaning and identity
- create visual richness at the beginning when few bricks exist
- become increasingly covered as more people place bricks

The mural is not decorative only.
It represents the latent civic / civilizational meaning that the community gradually builds over.

The mural may be:

- symbolic
- narrative
- geometric

But it should support the feeling of **building something larger than oneself**.

---

# Placement Scaffold

The canvas should show the **outline of where bricks can be placed**.

Requirements:

- full-page view
- staggered brick pattern
- subtle visible outlines
- sufficient clarity so placement logic is understandable

Rules:

- rows are half-offset like real bricks
- scaffold should support emergent structure
- not a predefined sculpture

The scaffold may be faint at rest and more visible during interaction.

---

# Placement Trigger

The brick should not always be visible.

The interaction is **triggered**.

Rule:

- the trigger appears only if the user has earned Civic Mason and has not already placed a brick for the current year/layer

When triggered:

- user clicks **Place Your Brick**
- their brick becomes available for drag-and-drop placement

---

# Brick Placement Interaction

## Flow

1. User clicks **Place Your Brick**
2. A draggable brick appears
3. Valid slots illuminate
4. User drags brick over the scaffold
5. Valid positions show snap preview
6. User drops the brick into a valid position

Invalid placements should not be accepted.

---

# Placement Confirmation Ritual

After drop:

A lightweight overlay or modal appears.

Message example:

> Are you sure this is where you want to place your brick?

A countdown appears:

- 5
- 4
- 3
- 2
- 1

Options:

- Cancel
- Confirm now

If canceled:
- the brick returns to the user

If confirmed or countdown completes:
- the brick is placed permanently

This creates intentionality and a sense of civic weight.

---

# Message / Inscription Step

After confirmation, the user may add a message.

Rules:

- max 200 characters
- message is associated with the brick
- message can be updated later
- message history is preserved

This should feel like an inscription, not a form submission.

---

# Hover Behavior (For Everyone)

When **anyone** hovers over a placed brick, they should see the same information.

Hover details should include:

- display name
- profile image or avatar
- latest message / inscription
- year
- layer
- linked artifact or contribution (if available)
- optional governance / lineage indicator

This applies to:

- Mason users
- non-Mason users
- general visitors

Hovering should create:

- social proof
- aspiration
- visibility into contribution
- a sense of shared civic history

---

# Already Placed State

If a person has already placed a brick for the current year/layer:

The interface should communicate clearly:

> You’ve already placed your brick for this year.

Optional actions:

- view your brick
- update your message
- review message history

They should not be able to place a second brick.

---

# Visual Design Requirements

The interface should prioritize:

- full-page immersion
- civic / symbolic tone
- subtle interaction cues
- calm visual hierarchy

Avoid:

- form-heavy layouts
- overly gamified UI
- dashboard aesthetic
- noisy controls

This should feel like:

- entering a civic construction space
- becoming part of a living structure

---

# Key Cursor Guidance

Cursor should implement the brick placement interface as a **wall-first spatial interaction**, not a form-first workflow.

Meaning:

- the mural and brick canvas are primary
- drag-and-drop placement is primary
- message input is secondary
- permissioning is explicit and meaningful
- hover info is available to everyone

This interface is both:

- a contribution ritual
- a public memory surface

It should communicate that clearly.



---

# Task 14 – Civic Mason Wall (Brick System + UI Spec)

This defines the full rendering, interaction, and data model for the Civic Mason brick interface.

## Core Principles

- Structure is defined ONLY by grid rules (not mural)
- Mural is symbolic, non-constraining, and fades over time
- One brick per IdentityAnchor per year (enforced)
- Placement is permanent (no deletion; updates only affect message history)

## Grid & Placement Rules

- Staggered brick grid (half-offset per row)
- A brick must overlap at least 50% of a brick below (except base row)
- Base row: can be placed anywhere but only 50% of slots can be filled
- Valid slots are precomputed and rendered as faint outlines
- User can only place in valid slots

## Visual States

- Empty slot: faint dashed outline (toggleable helper layer)
- Hover slot: highlighted outline + snap preview
- Active placement: glowing slot + draggable brick preview
- Placed brick: solid with subtle texture

## Color System (Year-Based Palettes)

- Each year defines a color family (5–7 variants)
- Example:
  - 2026: warm browns (founding)
  - 2027: stone greys
  - 2028: deep blues
- User selects a color variant before placement
- Color is immutable after placement

## Brick Rendering

- Slight variation in tone and texture (no identical bricks)
- Soft bevel + micro-noise texture
- Subtle imperfections at creation (non-uniform edges)

## Aging System

- Bricks age over time (time-since-placement)
- Effects:
  - slight darkening/desaturation
  - edge wear
  - micro-cracks (very subtle)
- Optional: interaction-aware preservation
  - frequently referenced bricks retain brightness or gain a faint glow

## Interaction Flow

1. User has Civic Mason badge (eligibility = true)
2. Click “Place Your Brick”
3. Choose color variant (from current year palette)
4. Drag brick across grid
5. Valid slots highlight
6. Drop into slot
7. Confirmation modal (5-second countdown to cancel)
8. On confirm:
   - brick is placed
   - message (≤200 chars) is saved
   - initial history entry created

## Hover / Detail Panel

On hover of a placed brick:

- display name
- profile image
- badge (Civic Mason + year)
- message (current)
- “view history” (message edits)
- links to related artifacts (if any)

## Message System

- Initial message required at placement (≤200 chars)
- Users can update message over time
- Full history retained and viewable

## Eligibility Rules

- Only users with Civic Mason badge can place
- One brick per IdentityAnchor per year
- If not eligible:
  - placement UI disabled
  - clear message explaining requirement

## Mural (Background Layer)

- Three-band conceptual composition:
  1. Human builders / civic action (bottom)
  2. Brick field (middle – user contributions)
  3. Network / meta-layer / future city (top)

- Mural must:
  - NOT constrain placement
  - be partially obscured by bricks over time
  - reduce contrast under brick layer

### Representation Guidelines

- Figures, if discernible, MUST be diverse:
  - age, gender, ethnicity
  - global representation
- Avoid dominance of any single group
- Keep semi-abstract to avoid narrative rigidity

## Rendering Layers (Z-Order)

1. Mural (background, low contrast)
2. Grid helper (toggleable outlines)
3. Placed bricks
4. Hover/interaction highlights
5. UI overlays (modals, panels)

## Performance Notes

- Use tiling/virtualization for large walls
- Lazy-load bricks outside viewport
- Aging can be computed client-side from timestamp

## Data Model Additions

Brick (can be Artifact subtype or dedicated model):

- id (UUID)
- identity_anchor_id
- layer_id
- year
- color_variant
- grid_position (row, col)
- message_current
- created_at

BrickMessageHistory:

- id
- brick_id
- message
- created_at

## EventLog Additions

- brick_placed
- brick_message_updated

---

# Task 15 – Localization (i18n + Artifact Translation)

Implement two layers of localization: interface language and artifact translation.

## Interface Localization (i18n)

- All UI strings externalized to translation files (e.g., JSON per locale)
- Key-based lookup (no inline strings)
- User language preference stored on IdentityAnchor
- Fallback to default (en-US)
- Runtime language switch (no reload if possible)

Example:

- "place_brick_button": {
  "en": "Place Your Brick",
  "es": "Coloca tu ladrillo"
}

## Artifact Translation System

Artifacts support multiple language versions.

Model: ArtifactTranslation

- id (UUID)
- artifact_id
- language_code
- translated_title
- translated_body / summary
- translator_identity_anchor_id
- status (draft, review, accepted)
- created_at

## Workflow

1. User initiates translation for an artifact
2. Draft translation created
3. Optional review (triad or open)
4. Accepted translation becomes selectable view

## UI Behavior

- Language toggle on artifact view
- Default to user’s preferred language if available
- Fallback to original language

## EventLog Additions

- translation_created
- translation_accepted

## Future Extension

- Cross-layer translation reuse
- Machine-assisted suggestions (clearly labeled)

---

# Architectural Rule (Critical)

## Rule: "Never Let Presentation Shape the System"

- Mural MUST NOT define grid or placement
- UI labels MUST NOT define data model
- Navigation MUST NOT constrain relationships

All relationships must be expressed through:

- Artifact
- ArtifactRelation
- EventLog

This preserves long-term flexibility and prevents rigid system design.