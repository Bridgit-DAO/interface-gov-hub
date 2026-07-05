New Issues in This Document
1. The io Suffix – Technically Ambiguous
Task 1 introduces the io suffix for artifact identifiers:

artifact.id = UUID (format [random part]io) artifact.public_id = "A47io"

Two problems:

First: The phrase "UUID (format [random part]io)" is ambiguous. If the UUID itself ends in "io", it violates standard UUID format (hex-only, 8-4-4-4-12). If "io" is only appended to the public_id, that's a presentation-layer choice and should be stated clearly as such.

Second: "io" is an overloaded term – it means I/O operations in computing, it's a top-level domain (.io), and it could confuse developers who encounter it in logs without context. The intent (making artifact IDs visually distinct) is good, but "io" is a weak sigil for this purpose. Consider alternatives: a hash prefix (#A47), a typed prefix (art:A47), or a different suffix (A47-d for document, A47-r for reflection).

Revision required: Clarify that io is a public_id presentation convention only – UUID is standard UUID. Also assess whether "io" is the right distinguishing mark or whether a typed prefix would be clearer.

2. Three Overlapping Implementation Sequences
This document now creates three competing implementation orderings:

Original GOV-HUB-2.md: Phases 1–4
This document, Implementation Order: Phases 0–5
This document, Build Checklist: Tasks 1–13
These are not aligned. For example:

Notifications and Activity Feed appears in Phase 4 of the Implementation Order but as Task 12 (immediate work) in the Build Checklist.
Phase 0 in the Implementation Order is labeled "Foundations" and covers UUID, EventLog, and domain separation – but Tasks 1–5 in the Checklist cover these same items without the Phase 0 label.
The original GOV-HUB-2.md Phase 1 includes Badges and Civic Mason; the new Phase 3 pushes both to later.
Revision required: Designate one sequence as canonical. Recommendation: the Phase 0–5 Implementation Order in this document is canonical. The Build Checklist maps to Phase 0 + Phase 1 tasks only. The original GOV-HUB-2.md phasing is superseded. A one-line note at the top of each should say so.

3. Activity Feed Contradiction
As noted above: the Implementation Order places "Notifications and Activity Feed" in Phase 4. The Build Checklist has it as Task 12 (immediate). These are the same feature.

This contradiction matters because Task 12 says "Basic Activity Feed reads from EventLog" – and the EventLog (Task 5) is correctly placed in the immediate build. So a basic feed is a Phase 0/1 output. But full notification preferences are Phase 4.

Revision required: Split the concept:

Basic Activity Feed (reads EventLog, layer-scoped, no preferences) → Phase 1, Task 12
Notification Preferences + Digest → Phase 4
4. Task Execution Order Has a Dependency Problem
The Build Checklist is numbered 1–13, but the execution order implied by dependencies is different. Specifically:

Task 7 (Identity Anchor) and Task 8 (Membership) must exist before Task 9 (Roles/Triads) and Task 10 (Voting). But they appear after Tasks 1–6.
Task 4 (Bridge Model) has artifact_id as a field, so it depends on Task 2 (Artifact). This dependency is fine in the current order.
Task 6 (Host → Layer Middleware) has no dependency on Tasks 2–5 and could run in parallel.
Revision required: Add a dependency note or reorder the checklist to reflect actual execution sequence:

1. UUID + Domain Structure
2. EventLog
3. Identity Anchor + Wallet Bindings
4. Membership System
5. Layer + Host Middleware
6. Roles + Triads
7. Artifact Base Model
8. ArtifactRelation Model
9. Bridge Model
10. Voting System (v1)
11. Waitlists
12. Basic Activity Feed
13. Initial UI Navigation
5. Bootstrap Governance Is Underspecified
The Bootstrap Governance section reads:

Layer initiators may create initial admins. Admins may form an early governance triad. Over time governance transitions to role-based stewardship.

For a system explicitly designed to resist power concentration, the bootstrapping moment is the most vulnerable point. Three questions are unanswered:

What is an "admin" in this context? Is it a Role? A permission flag? A system-level override?
What prevents a single Layer initiator from retaining admin rights indefinitely? The document doesn't define when or how the transition to role-based stewardship happens. Is it triggered by a milestone? A vote?
What's the minimum governance state at Layer creation? One person? One triad? What's the floor?
Revision required: Add a # Bootstrap Governance Model section with:

Definition of initial admin (scope: Layer config access only; not equivalent to a governance role)
Required early action: nominate at least one Role and initiate Triad formation within N days
Sunset trigger: once a Layer reaches Milestone 1 (configurable member threshold), admin override powers expire
All bootstrap actions emit events to EventLog
6. rfc Missing from Reserved Subdomain List
Task 6 (Host Middleware) lists reserved subdomains as: www, dev, api, docs. The original GOV-HUB-2.md included rfc in the reserved slug list. The RFC-style draft process is central to the system. If rfc.themetalayer.org is not reserved, a Layer named "RFC" could capture it.

Revision required: Add rfc (and consider app, admin, status) to the reserved subdomain list.

7. "Structured Opposition" and "Opportunity Surfaces" Are Unnamed Features
Phase 2 introduces two meaningful concepts:

Structured Opposition: Proposal → support artifact / opposition artifact / fork
Opportunity Surfaces: System-wide display of open needs (missing artifacts, open quests, triad vacancies)
Neither appears in the Feature Map sections. They're buried in the Implementation Order as sub-bullets.

Revision required: Promote both to named Feature Map sections – or at minimum, add them to Section 5 (Drafts & Documents) and Section 11 (Onboarding & Activation) respectively. "Structured Opposition" is particularly important: it's the mechanism that prevents governance by silence and gives minority voices a legitimate path.

8. BTC Address – Rationale Still Unclear
Task 7 still mentions "BTC badge anchoring" as a wallet binding use case. The previous review flagged this. The entity model now has chain_type on WalletBinding, which is the correct technical approach. But there's still no explanation of why a BTC address is generated automatically vs. EVM only.

If BTC is for Ordinal inscriptions (Bitcoin-native badge anchoring), that's a meaningful Phase 3+ feature. But auto-generating a custodial BTC wallet at identity creation for a feature that won't be exposed until Phase 3 carries risk: key management, security surface, user confusion.

Revision required: Either (a) defer BTC wallet generation to Phase 3 when Ordinals/badge anchoring is actually built, and use EVM only in Phase 0–2; or (b) add a one-sentence rationale for why BTC is generated at identity creation time.

