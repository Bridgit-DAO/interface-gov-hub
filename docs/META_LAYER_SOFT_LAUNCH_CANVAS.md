# Meta-Layer Soft Launch Canvas (amended)

**Canonical for implementation.** This document merges the original soft-launch narrative with **Directive §15** (status, artifact vs bridge wording, API rules). Where earlier copy differed, **this file wins.**

**Stack note (gov-hub-dev):** Flask + SQLAlchemy + Vue 3 + Vite – not React/Next; same “components first, fixtures first” build order applies.

**Scaffold (implemented):**

| URL | Purpose |
|-----|---------|
| `/soft-launch/` | Homepage + activity + roles (fixture copy) |
| `/soft-launch/onboarding/` | Five-step onboarding (client-side steps) |
| `/soft-launch/artifact/?scenario=…` | Demo contribution (`under_review`, `under_review_ready`, `vote_scheduled`, `vote_open`, `approved`, `implemented`) |
| `GET /api/soft-launch/fixtures/` | Full JSON fixture payload (`participation_cards`, `activity_cards`, …) |
| `GET /api/soft-launch/lifecycle/` | Ordered stages for steppers |

Code: `fixtures/soft_launch.py`, `services/soft_launch_lifecycle.py`, `routes/soft_launch.py`, `routes/soft_launch_pages.py`, **`static/css/soft-launch.css`** (homepage layer; no Tailwind). Vue slice list: `client/soft-launch/README.md`.

**Wire demo actions:** set environment variable `SOFT_LAUNCH_WIRED_ARTIFACT_ID` to a real `Artifact.id` (UUID). While logged in, **Support** / **Oppose** on `/soft-launch/artifact/` POST to `/api/artifacts/<id>/support/` and `/opposition/`. Other buttons stay preview-only until those flows exist.

---

## 1. Homepage (above the fold)

- **Headline:** Build decisions, not just discussions  
- **Subtext:** A coordination layer where ideas become proposals, and proposals become reality.  
- **Primary CTA:** Get Started  
- **Microcopy under CTA:** Start with one idea. It takes less than 60 seconds.  
- **Secondary CTA:** Explore Activity  

---

## 2. How it works

1. **Contribute** – Share an idea or insight  
2. **Review** – Others **support**, **oppose**, or expand it *(artifact actions use **Oppose**; API relation type remains `opposes`)*  
3. **Decide** – Contributions move toward decision and implementation  

---

## 3. Live activity (example cards)

Use types/statuses consistent with the **six-stage model** (§7). Example:

- **Consent-based agent boundaries** – Type: Insight · Status: **In Review** · Space: AI Governance · Activity: 5 comments  
- **Carbon credit verification model** – Type: Proposal · Status: **Draft** · Space: Climate · Activity: 2 supports  

---

## 4. Choose your role

- **Share ideas** – Start a contribution or proposal  
- **Review contributions** – Comment, **support**, **oppose**, add evidence  
- **Build & implement** – Turn **approved** ideas into action  

---

## 5. Onboarding flow

Unchanged flow (intent → context / space → create → confirmation → next steps). **Language:** Contribution / Space or Project on entry; after publish, introduce **Layer** and **Artifact** (see §9).

---

## 6. Artifact (contribution) page

### Header

Title · **Status** (UI label from §7) · Type · Space  

### Primary actions (artifact)

**Support** · **Oppose** · **Comment** · **Add Evidence**  
*(Maps to relation types `supports` / `opposes` where applicable. Do **not** add a `contradicts` relation type on artifacts.)*

### Relationships section (structural, artifact ↔ artifact)

- **Supports:** …  
- **Opposition:** … *(or “Opposes” – list uses `opposes` edges)*  
- **Builds on:** …  

### Activity, next-step prompts, review → voting

As in the original canvas (readiness panel, transition callouts, modal, voting panel). **Voting actions:** Support · **Oppose** · Abstain.

---

## 7. Status model (visible lifecycle)

### Display (UI)

**Draft → In Review → Vote Scheduled → Voting → Approved → Implemented**

### Stored values (`Artifact.status`) – fixed set for this surface

| UI label          | Stored value      |
|-------------------|-------------------|
| Draft             | `draft`           |
| In Review         | `under_review`    |
| Vote Scheduled    | `vote_scheduled`  |
| Voting            | `vote_open`       |
| Approved          | `approved`        |
| Implemented       | `implemented`     |

**Rules:** Do **not** introduce new status strings for this UX. Do **not** use **`adopted`** for new work. Normalize or hide legacy values (`submitted`, `open_for_comment`, `adopted`, etc.) in the soft-launch UI.

---

## 8. Add insight / contribution copy

Same fields and success tone as the original canvas; success line can stay “part of the system” then **Layer** naming on transition (§9).

---

## 9. Language strategy

### Onboarding (entry)

Contribution · Space/Project · simple verbs · **Decision** as a concept.

### System (core)

**Layer** · **Artifact** · **Bridge** – use consistently after the first meaningful action.

### Artifact vs bridge (do not mix)

| | **Artifact relations** | **Bridges** |
|--|------------------------|------------|
| Role | Structural links between artifacts | Claim-centric / evidentiary links to content |
| Examples | `supports`, `opposes`, `builds_on`, … | `cites`, `contradicted_by`, `supported_by`, `related_to` |

### Hard rules

- Never **“Refute”**  
- **Artifact** primary buttons: **Oppose** (not a separate `contradicts` type)  
- **Bridges** use passive, claim-centric strings (`contradicted_by`, `supported_by`, …)  
- Do not flatten or rename **Bridge** as a concept  
- Do not expose full protocol language before the first action  

---

## 10. Core UX rules

Always show **next action**, **status**, and **activity**; keep first contribution lightweight; preserve system integrity under the hood.

---

## 11. Build sequence

1. Wire **fixtures / fake data** (Python dicts + Flask-shaped JSON)  
2. Manual flow test  
3. Connect backend  

---

## 12. Review → voting (summary)

Unchanged intent from the original canvas: readiness checklist visible; transition callouts; modal with decision question and minimal voting settings; voting state with timing and tallies; **“What informed this vote”** panel; post-vote outcome with clear next step.

**Post-vote labels:** **Approved** / not approved / needs more review (not “Adopted” as a stored canonical for this path).

---

## 13. Priority

**P0:** Homepage, onboarding, contribution create, artifact page, activity feed, status, readiness, voting transition modal, voting UI.  
**P1:** Relationships depth, role filters, empty states, post-vote polish.

---

## 14. Core principle

Do not change the **underlying** governance model; change **how people enter it** and make **review → decision** visible and actionable.

---

## 15. API / data constraints (reminder)

- **Artifact `artifact_relation` types (unchanged):**  
  `builds_on`, `references`, `supports`, `opposes`, `amends`, `implements`, `awarded_for`  
- **Bridge `relationship` (canonical only, strict API):**  
  `cites`, `contradicted_by`, `supported_by`, `related_to`  
- One-off DB cleanup: `python migrate_bridge_relationship_labels.py` on databases that predate the rename.

---

*Amended for alignment with Directive §15 and gov-hub-dev implementation (March 2026).*
