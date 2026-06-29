# Civic Mason — Brick Placement Interface Specification

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

## Not Yet Implemented (Next)

| Feature | Spec Reference |
|--------|----------------|
| Layer scope support | Design decision above; add optional `layer_id` to Brick |
| One brick per year limit | Core Rule, Eligibility Logic |
| Testing bypass | Testing Mode |
| Full-page mural background | Mural Concept |
| Richer hover (avatar, layer, artifact, lineage) | Hover Behavior |
| “Already placed” state + message update flow | Already Placed State |
| Aspirational CTAs for non-Masons (Start Steward Challenge, etc.) | Non-Mason State |

## Code Locations

- `models/coordination.py` — Brick, BrickMessage, Role.civic_mason_eligible
- `services/civic_mason.py` — Eligibility, placement validation
- `routes/civic_mason.py` — API: `/api/civic-mason/bricks/`, `/eligible/`
- `routes/civic_mason_pages.py` — Page at `/civic-mason/`, drag-drop UI

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