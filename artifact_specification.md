# Gov Hub – Artifact System Specification

**Part of:** GOV-HUB-3 artifact work (Task 7 – Artifact Base Model, Task 8 – ArtifactRelation, Phase 3.4 – Lineage). Referenced from `GOV-HUB-3.md` and `PLANNING_FULL_PICTURE.md`.

This document defines the **artifact model** for the Governance Hub. Artifacts are the core knowledge objects of the system and form the basis of governance, collaboration, and institutional memory.

The Governance Hub is designed as an **artifact-driven governance system**. Decisions, evidence, learning, and relationships are captured as artifacts connected through typed relationships (bridges).

---

# Core Principle

Artifacts represent **durable knowledge objects**.

Artifacts must be:

- addressable
- linkable
- attributable
- versionable
- translatable
- referenceable in governance processes

Artifacts exist independently of any specific workflow (voting, quests, badges, etc.).

Workflows operate **on top of artifacts**, not inside them.

---

# Artifact Identity

Each artifact must have:

UUID (internal primary key)

public_id (human readable short identifier)

public_ref (public artifact reference using `io` suffix)

Example:

artifact.id = UUID

artifact.public_id = "A47"

artifact.public_ref = "A47io"

The `io` suffix signals that the object is an **information artifact**.

The suffix is presentation-level only and **not part of the UUID**.

---

# Artifact Base Fields

All artifacts share a base structure.

Fields:

id (UUID)

public_id

layer_id

creator_identity_anchor_id

artifact_type

artifact_subtype

title

summary

body

uri (optional external reference)

source_language

current_language

status

created_at

updated_at

---

# Core Artifact Types

These represent the fundamental knowledge roles in governance.

## Proposal Artifact

Purpose:

Propose a change, idea, policy, or action.

Examples:

- governance proposal
- RFC draft
- policy change
- architecture proposal

Typical relationships:

builds_on

references

amends

supersedes

---

## Evidence Artifact

Purpose:

Provide supporting or opposing evidence.

Evidence artifacts must include **either a link or uploaded material**.

Examples:

- research paper
- data analysis
- benchmark
- experiment
- external source summary

Evidence relationships (supporting):

supports

corroborates

cites

Evidence relationships (opposing):

contradicts

refutes

---

## Insight Artifact

Purpose:

Capture observations, critiques, or improvement suggestions.

Examples:

- design insight
- architectural critique
- improvement proposal

Relationships:

references

improves

challenges

builds_on

---

## Reflection Artifact (PEARL)

Purpose:

Capture learning and reflection from experience.

Examples:

- PEARL reflection
- governance retrospective
- contributor reflection

Relationships:

reflects_on

derived_from

responds_to

---

## Translation Artifact

Purpose:

Represent translated content.

Translations are separate artifacts and must never overwrite originals.

Fields:

translated_from_artifact_id

translation_type

translator_identity_anchor_id

translation_status

Relationships:

translation_of

machine_translation_of

human_translation_of

reviewed_translation_of

---

## Implementation Artifact

Purpose:

Represent real-world execution of proposals.

Examples:

- code implementation
- governance rule adoption
- infrastructure deployment

Relationships:

implements

validates

derived_from

---

## Decision Artifact

Purpose:

Record governance outcomes.

Examples:

- adopted proposal
- governance resolution

Often generated automatically when votes conclude.

Relationships:

adopts

rejects

supersedes

---

## Monument Artifact

Purpose:

Register culturally important digital monuments.

Examples:

- digital monument
- canonical knowledge object

Relationships:

documents

commemorates

anchors

---

## Bridge Artifact

Purpose:

Represent links between artifacts and external web resources.

Bridge artifacts enable Web2-compatible linking until full Overweb/Canopi bridging is available.

Possible bridge targets:

webpage

image

text fragment

video segment

dataset

social post

Bridge relationships:

links_to

anchors_to

references_external

---

# Supplementary Artifact Types

These expand governance capabilities but derive from core artifact types.

Timeline Artifact

Tracks project timelines or historical records.

Roadmap Artifact

Defines milestones and planned development phases.

Specification Artifact

Formal technical or governance specification.

Guide / Template Artifact

Reusable governance tools.

Survey Artifact

Community input collection.

---

# Artifact Relationships (Bridges)

Artifacts form a **knowledge graph** through typed relationships.

Examples:

builds_on

references

supports

corroborates

cites

contradicts

refutes

amends

supersedes

implements

translation_of

reflects_on

derived_from

responds_to

---

# Artifact Graph Principle

Artifacts should form a **governance lineage graph**.

Example chain:

Proposal → Evidence → Vote → Decision → Implementation → Reflection

This allows governance communities to trace:

- how ideas emerged
- what evidence supported them
- how decisions were made
- what was implemented
- what was learned afterward

---

# Relationship Storage

Relationships should be stored in a separate table.

ArtifactRelation

Fields:

id

from_object_type

from_object_id

to_object_type

to_object_id

relation_type

created_by_identity_anchor_id

created_at

This system allows relationships between:

artifact → artifact

artifact → monument

artifact → vote

artifact → external content

---

# Vote Objects

Votes are **governance workflow objects**, not primary artifacts.

However:

Votes may reference artifacts.

Example:

vote.artifact_id → proposal artifact

Vote results may generate **Decision Artifacts** automatically.

---

# Artifact Status Model

Artifacts move through governance and knowledge workflows using a **status lifecycle**. Status represents the maturity and governance state of the artifact.

Common statuses:

- draft
- submitted
- under_review
- reviewed
- open_for_comment (RFC stage)
- vote_scheduled
- vote_open
- adopted
- rejected
- implemented
- superseded
- archived

Purpose of statuses:

- allow artifacts to move through governance stages
- make artifact maturity visible
- support governance automation (votes, milestones, quests)

Example lifecycle:

Draft → Submitted → Under Review → Open for Comment → Vote → Adopted → Implemented → Reflection

Not every artifact type uses the full lifecycle. For example:

Evidence artifacts may remain simply `submitted` or `reviewed`.

Reflection artifacts may move directly from `submitted` → `reviewed`.

Translation artifacts may move through:

- machine_generated
- human_review
- reviewed

Status transitions should emit **EventLog events** so governance lineage can be reconstructed.

---

# Governance Knowledge System

The artifact system allows governance to become:

- evidence-driven

- traceable

- explainable

- historically navigable

Artifacts and their relationships become the long-term **institutional memory of the layer ecosystem**.

