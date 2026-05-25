# Gov Hub — Feature Map

This document clusters all contemplated features for the Governance Hub, identifies which kinds of projects would use them, and organizes them as a potential website menu structure.

---

# 1) Layers (Top-Level Governance Domains)

**What it is**
The primary governance container (currently implemented as Project in code; conceptually: Layer). A Layer holds members, roles, drafts, votes, milestones, and recognition.

**Contemplated features**

- Layer creation and profile (mission, description, branding)
- Subdomain and path routing:
  - `layername.themetalayer.org`
  - `themetalayer.org/layer/layername`
- Layer membership management
- Configurable governance parameters (quorum defaults, thresholds)
- Reserved slug protection (dev/rfc/www/etc.)
- Public Layer landing page

**Who uses it**

- Protocol communities (Web3/blockchain)
- Open-source ecosystems
- Civic tech initiatives
- Local/regional chapters
- Research collectives
- Cultural stewardship groups

---

# 2) People & Identity Anchors (IA)

**What it is**
Persistent, pseudonymous identity that carries contribution and governance lineage across Layers.

**Contemplated features**

- Session-based auth (current)
- Web3Auth wallet generation (ETH/BTC custodial - we'd want to auto generate both an  ETC address for voting and BTC address for badges)
- Multiple wallets per IA
- Wallet rotation events (future)
- Cross-layer identity continuity
- Anonymous-but-verified voting (future)
- Social recovery concepts (future)

**Who uses it**

- Privacy-conscious communities
- Web3-native ecosystems
- Youth participation programs
- Global distributed contributors

---

# 3) Roles & Triads

**What it is**
Roles define stewardship responsibilities; triads (rule-of-three) are role-anchored accountability units that prevent bottlenecks and concentration of power.

Triads are not free-floating groups. A triad exists specifically in service of a Role.

**Design Model (Hybrid Implementation)**
Triads reuse the same underlying group infrastructure as Guilds (shared membership, messaging, artifact support), but with strict constraints:
- `type = triad`
- `max_members = 3`
- `role_id` is required (must be anchored to a Role)
- Layer-scoped

This allows code reuse without sacrificing governance clarity.

**Contemplated features**

- Role creation per Layer
- Role claims (time-bound stewardship terms)
- “Create Triad” available only from Role page
- Triad formation (max 3 members)
- Observer mode (time-bound; triad-approved; no voting)
- Weekly triad reports (artifact or structured update)
- Public triad intention statement (focus, duration, differentiation from other triads)
- Visibility into multiple triads per role (competition on proposals, not duplication of artifacts)

**Cultural Guardrail**
New triads must articulate how their focus differs from existing triads for the same Role. Competition happens through proposals and artifacts—not redundant structures.

**Who uses it**

- Volunteer-driven organizations
- DAO-like governance groups
- Working groups within protocols
- Research collectives

---

# 4) Workgroups & Guilds

**What it is**
Workgroups are scoped execution units within a Layer. Guilds are contributor collectives that can author drafts, coordinate activity, and persist beyond a single Role.

Guilds are broader than triads and are not required to be role-anchored.

**Design Relationship to Triads**
- Guilds: flexible size, independent identity, may author drafts
- Triads: max 3, role-anchored, stewardship/accountability focused
- Both can share the same underlying group infrastructure in code

**Contemplated features**

- Workgroup creation and membership
- Guild formation (flexible size)
- Guild-as-author for drafts
- Workgroup-specific documents and roles
- Workgroup branding assets

**Who uses it**

- Multi-team Layers (Overweb, Canopi, chapters)
- Protocol communities with multiple initiatives
- Topic-specific civic teams

---

# 5) Drafts, Documents & Evolution (IETF-Inspired)


**What it is**
Structured draft → RFC-style document evolution with transparent commentary and voting.

**Contemplated features**

- Draft (Submission) creation
- Inline and whole-document commenting
- Version tracking (as needed)
- Draft → Vote → Adopted pipeline
- Document categories/tags:
  - document / template / tool / guide / glossary / policy
- Cross-referencing between drafts
- Multi-Layer adoption

**Who uses it**

- Standards bodies
- Protocol governance communities
- Research networks
- Charter and constitutional drafting groups

---

# 6) Voting (v1 and Beyond)

**What it is**
Configurable, membership-based voting tied to a Layer.

**Contemplated features**

- Admin-started vote (start, duration, quorum, threshold)
- Eligibility snapshot at activation
- Default choices: Yes / No / Abstain (but vote creator can specify the choice set)
- Deterministic outcome summary
- CLI/systemd vote lifecycle
- Future: chain anchoring (e.g., Base)
- Future: alternative voting mechanisms

**Who uses it**

- Protocol upgrade processes
- Draft ratification bodies
- Civic governance initiatives

---

# 6A) Role Elections (Voted Roles)

**What it is**
A voting mechanism specifically for selecting who holds a Role (or multiple seats for a Role) within a Layer.

**Election modes (contested vs confirmatory)**
- **Confirm/Reject**: one candidate → Yes/No (simple legitimacy check)
- **Single-winner**: multiple candidates → one winner
- **Multi-seat**: multiple candidates → N seats (e.g., 3 coordinators)
- **Multi-position**: one election fills several distinct roles (later)

**Ballot order randomization**
To reduce position bias, candidate order should be **shuffled per voter view** (or at least randomized per page load) while preserving auditability.

**Contemplated features**
- Candidate nomination/registration (self-nominate or nominated)
- Candidate statements + optional artifact submissions
- Eligibility rules (v1: active members; later: badge/quest-based)
- Configurable seats (N), quorum, threshold, and term length
- Tie-handling policy (runoff / extended voting / coin-flip not recommended)
- Public results summary + rationale

**Who uses it**
- Stewardship councils
- Coordinator selection
- Role triads and rotating stewards
- Chapters and working groups

---

# 7) Recognition & Badges

**What it is**
Durable recognition for structural contribution and stewardship.

**Contemplated features**

- Badge issuance and detail pages
- Earner vs holder distinction
- Year overlay (issued year)
- Founding wave markers
- PEARL reflection overlay
- Append-only artifact trail
- Optional inscription support (future)

## Badge Privileges / Entitlements / Access Rights

Badges may optionally confer structured benefits, including:

- Access to private groups or steward circles
- Eligibility to vote in specific decision classes
- Eligibility to claim certain roles
- Admission to events or workshops
- Early participation rights in new initiatives

Privileges can be configured as:

- Non-transferable (identity-bound)
- Transferable to holder
- Earner-only even if transferred
- Time-limited or one-time
- Layer-scoped or cross-layer

**Who uses it**

- Stewardship-driven ecosystems
- Civic participation programs
- Open-source contributor communities

---

# 7A) Quests & Bounties

**What it is**
A structured way to turn “we need help” into clear, time-bounded missions that produce real artifacts — with rewards.

- **Quest** = a defined contribution path with acceptance criteria (can award a badge).
- **Bounty** = a quest with an explicit reward (can be non-monetary, monetary, or both).

Quests are designed to be approachable for newcomers while still producing governance-relevant work.

**Contemplated features**

- Quest templates (review, research, outreach, build, design, governance)
- Micro-quests (20–60 minutes) vs deep quests (multi-day)
- Artifact requirement (link/upload/inscription) + optional PEARL reflection
- Review workflow (triad or role-based reviewers)
- Layer-scoped or cross-layer quests
- Quest feed + filtering (difficulty, time, skills, urgency)
- Bounty types:
  - Badge-only
  - Badge + privilege (access/eligibility)
  - Badge + recognition spotlight
  - Optional monetary reward (later; pluggable)
- Anti-spam safeguards (rate limits, reviewer gates, minimum quality bar)

**Who uses it**

- Early-stage Layers that need rapid contribution
- Youth and newcomer onboarding funnels
- Hackathon-style cohorts
- Communities needing structured outreach/research/design
- Governance bodies that want artifact-based legitimacy

---

# 8) Civic Mason Monument

**What it is**
A symbolic, public memory structure where contributors place bricks representing real stewardship.

**Contemplated features**

- Drag-and-drop brick placement
- 5-second confirmation countdown
- Masonry grid rules (half-offset rows)
- Annual color palette
- Hover reveals identity + 200-char message
- Append-only message history
- Governance lineage indicator (not prestige)
- Infinite growth through the year

**Who uses it**

- Youth engagement initiatives
- Long-horizon governance communities
- Civic experiment ecosystems

---

# 8A) Digital Monuments Registry

**What it is**
A way to register and steward durable public-facing “monuments” — digital places, artifacts, collections, or reference points that a Layer considers culturally or civically important.

A monument can be:
- An Ordinal inscription (or set/collection)
- A document or corpus (with archived mirror links)
- A dataset, glossary, or canonical reference
- A page, hub, or endpoint used as source-of-truth

**Contemplated features**
- Monument registration (title, description, steward(s), Layer association)
- Monument types and metadata (inscribed vs offchain; canonical links)
- Provenance fields (who registered, when, what authority)
- Stewardship expectations (maintenance cadence, review checkpoints)
- Monument visibility controls (public by default; optional restricted)
- Linkouts to permanent archives (e.g., archived copy/Wayback-style) where appropriate
- Cross-references: monuments linked to drafts, votes, roles, and badges

**Who uses it**
- Cultural preservation collectives
- Standards bodies (canonical references)
- Protocol communities (sources of truth)
- Chapters and civic initiatives

---

# 9) Milestones & Capability Unlock

**What it is**
A maturity ladder that unlocks governance capabilities as participation grows.

**Contemplated features**

- Join thresholds
- Role/workgroup unlock rules
- Vote unlock thresholds
- Distribution-based anti-capture thresholds
- Layer-configurable milestone stacks (within invariants)

**Who uses it**

- Early-stage governance projects
- Communities scaling from small to large
- Experimental civic systems

---

# 10) Integrity, Anti-Capture & Dispute Resolution

**What it is**
Structural safeguards that keep governance legible and resistant to concentration.

**Contemplated features**

- Rule-of-three triads
- Eligibility snapshots
- Quorum + threshold enforcement
- Reserved slug protections
- Append-only governance mindset
- Dispute and appeal workflows (lightweight v1; expand later)

**Who uses it**

- Communities concerned about capture
- Multi-stakeholder governance systems

---

# 11) Onboarding & Activation Funnel

**What it is**
A “Find Your Role in 5 Minutes” experience converting curiosity into contribution.

**Contemplated features**

- Interest prompts (no jargon)
- Instant role matches
- Active triads seeking members
- Micro-tasks (20 min)
- Activation challenges that generate artifacts
- Meetings as optional deepening

**Who uses it**

- Youth communities
- Hackathon cohorts
- Growing ecosystems needing contributor inflow

---

# 12) Governance Lineage Graph

**What it is**
A traceable map of how ideas evolve, influence decisions, and propagate across Layers.

**Contemplated features**

- Reference tracking (cites, amends, forks, implements)
- Brick-to-proposal linkage
- Cross-Layer adoption mapping
- Discoverable depth without gamification

**Who uses it**

- Governance researchers
- Protocol designers
- Transparency advocates
- Long-term ecosystem stewards

---

# Suggested Website Menu IA (Initial System / Phase 1 Rollout)

The first release should prioritize clarity and contribution. Navigation should help people quickly understand where they belong and how they can participate.

Top-level navigation should therefore be simple and action-oriented.

## Global Navigation (Phase 1)

**Home**

Front door for the Governance Hub and each Layer.

Typical content:
- Layer overview
- "What draws you here?" onboarding prompt
- Active opportunities
- Featured drafts or votes
- Monument callout
- Join / waitlist call-to-action

---

**Contribute**

Primary participation funnel.

Subsections:
- Find Your Role
- Quests / Challenges
- Join a Triad
- Submit Idea / Draft
- Waitlists

Purpose:
Make it extremely easy for new participants to take a meaningful first step.

---

**Governance**

Where decision-making processes live.

Subsections:
- Drafts
- Votes
- Roles
- Workgroups
- Roadmap / Goals
- Milestones

Purpose:
Allow participants to track how ideas evolve and how decisions are made.

---

**Community**

People and collaboration structures.

Subsections:
- People
- Guilds
- Triads
- Workgroups
- Layers

Purpose:
Enable discovery of collaborators and governance participants.

---

**Recognition**

Acknowledgement of stewardship and contributions.

Subsections:
- Badges
- Civic Mason
- PEARL
- Monument Registry
- Digital Monuments

Purpose:
Celebrate contribution and maintain visible civic memory.

---

**Learn**

Educational and orientation resources.

Subsections:
- How the System Works
- Stewardship Guide
- Draft → RFC Process
- Glossary
- Learning Modules

Purpose:
Lower the barrier to participation and help new contributors understand governance mechanics.

---

## Layer-Level Navigation

Each Layer should also have a local navigation surface focused on governance activity within that layer.

Recommended Layer navigation:

- Overview
- Roles
- Drafts
- Votes
- Workgroups
- People
- Monument

This keeps the global system simple while allowing each Layer to function as its own governance workspace.

---

---

# Implementation Strategy — Full System, Phased Exposure

The Governance Hub should be **implemented with the full feature set in the architecture**, but **exposed to users in phases through the navigation system**. This ensures the system can grow without repeated refactoring while keeping the user experience simple during early adoption.

Key principle:

**Build the full capability surface, but reveal functionality gradually through navigation and permissions.**

This means:

- Database models can include monuments, quests, bridges, elections, badges, etc.
- APIs and internal logic can support these systems.
- But the UI should only expose the features relevant to the current phase.

---

# Phase 1 — Initial Public Navigation

Navigation exposed to users:

**Home | Contribute | Governance | Community | Recognition | Learn**

Primary features exposed in Phase 1:

- Layers
- Membership & Identity Anchors
- Roles
- Triads
- Drafts
- Voting (basic draft voting)
- Waitlists
- Monument registration
- Civic Mason monument
- Badges
- Basic onboarding

Features implemented but not yet prominently exposed:

- Quests / Bounties
- Role elections
- Artifact Bridges / Digital Monument Bridges
- Learning modules
- Roadmaps & goals
- Governance lineage graph
- Advanced dispute resolution
- Artifacts as first-class objects

These may exist in the system but are not primary navigation items yet.

---

# Phase 2 — Contribution Expansion

Navigation additions likely appear under **Contribute** and **Governance**.

Features surfaced:

- Quests & Bounties
- Artifacts as first-class objects
- Artifact-based contributions
- Artifact Bridges / Digital Monument Bridges
- Role elections
- Expanded governance proposals

Purpose:

Encourage structured participation, make contributions legible as durable artifacts, and enable bridges between monuments, artifacts, and external web content.

---

# Phase 3 — Knowledge & Governance Depth

Navigation additions likely appear under **Learn** and **Governance**.

Features surfaced:

- Learning modules
- Governance lineage graph
- Expanded dispute resolution
- Advanced governance analytics

Purpose:

Deepen institutional memory and governance literacy.

---

# Phase 4 — Overweb / Canopi Integration

Advanced functionality tied to the broader meta-layer ecosystem.

Features surfaced:

- Bridge system connecting monuments to Web2 content
- Migration of bridges into Canopi / Overweb protocol
- Cross-layer governance interoperability

Purpose:

Transition the Governance Hub into a fully meta-layer compliant coordination system.

---

This phased exposure approach ensures:

- Simpler onboarding for early users
- Architectural stability for future features
- Reduced UI complexity
- Faster iteration during early adoption

---

---

# Core Architectural Rule for Cursor

To prevent the Governance Hub from becoming rigid as new governance models emerge, the system must follow a **composable governance architecture**.

**Rule:**

All governance entities must be implemented as **composable primitives connected through extensible typed relationships**, not rigid hierarchies.

This means objects such as:

- Layers
- Roles
- Triads
- Guilds
- Documents / Drafts
- Votes
- Quests
- Badges
- Monuments
- Artifacts

must not assume fixed parent-child structures. Instead, any object should be able to relate to any other object through a flexible relationship model.

Example relationships the system must support:

- A quest may produce a badge
- A role may require a vote
- A monument may reference a document
- A document may belong to multiple layers
- A badge may grant privileges
- A bridge may link any artifact or monument to external web content

Implementation guidance:

Cursor should implement an **extensible relationship graph (typed relations table or similar pattern)** so that new connections between objects can be added without schema redesign.

The goal is to allow the governance ecosystem to evolve without database restructuring or hard-coded assumptions.

---

# Artifact Graph Governance

Artifacts should be treated as **first-class governance objects**, not as attachments or incidental uploads.

This means the system should support:

- Artifact identity (`public_id`)
- Artifact pages
- Artifact provenance (creator, layer, time, source)
- Artifact status / review states
- Artifact linkage to roles, quests, votes, badges, monuments, and bridges
- Artifact-centered workflows (triad reports, challenge submissions, reflections, proposals, monument registrations)

Artifacts become the center of governance memory:

people → roles / triads → artifacts → drafts / proposals → votes / decisions → lineage

This makes governance evidence-based, traceable, and durable.

---

# Event Stream Rule for Cursor

Important governance actions must append immutable events to a shared event log. Current-state tables may exist for convenience, but the system must preserve an append-only event history for artifacts, votes, roles, monuments, bridges, badges, and governance changes.

Minimum event coverage should include:

- role claimed
- triad formed
- triad report filed
- artifact created
- artifact reviewed
- draft created
- draft amended
- vote started
- ballot cast
- vote closed
- badge issued
- monument registered
- bridge created or updated
- roadmap / goal changes

This preserves lineage, enables auditability, and keeps the governance system from becoming ahistorical.

---

End of Feature Map.

