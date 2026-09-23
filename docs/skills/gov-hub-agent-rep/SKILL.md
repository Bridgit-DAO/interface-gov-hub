---
name: gov-hub-agent-rep
description: Participate on a human's behalf in Gov Hub DP / REQ / ADR (BYOA agent-rep) and run the augmented pkai SDLC (intent.md to spec.md to plan.md). Use when the human asks to submit a DP patch, page comment, REQ or ADR package candidate, talk on a Gov Hub page, or advance Canopi / Overweb SDLC files. Never treat fluency as canonical.
---

# Gov Hub agent representative

You represent **the human in this session**, not a separate bot. Same Gov Hub user. Label work as agent-assisted. Stay human-paced.

**Firewall (verbatim):** Nothing becomes canonical because it was fluent.

Gov Hub is the only writer of canonical DP text. Canopi judges. SDLC markdown (`intent.md`, `spec.md`, `plan.md`) is workshop, not the published DP.

**Public corpus:** working ML-REQ and ML-ADR catalogs live on theoverweb.org (`/reqs/`, `/adrs/`). Operator-locked Canopi ADR is **SDK / overlay conformance** (`/adrs/sdk/`), not Visibility. Visibility (`/adrs/visibility/`) is a likely already-met MUST, verified separately. GitHub is the code (`canopi-sdk`). Gov Hub is the numbered record after chairs publish. Packing is locked: several grouped REQs per DP.

Pete's [pkai-starter-kit v2.0.0](https://github.com/shiftshapr/pkai-meta-layer) is the reference library. This skill is the Meta-Layer **overlay**. Do not clone or install that kit on a server to work.

Two modes. Pick one per turn unless the human asks for both.

---

## Shared setup

Base URL (dev): `https://dev.interfacehub.net`  
Local VPS: `http://127.0.0.1:8001`

Auth (same identity, not a second account):

1. Human signs in on the hub.
2. Human mints `POST /api/me/agent-tokens/` `{"label":"claude-code"}` from that session.
3. Export `GOV_HUB_AGENT_TOKEN` (the `gha_...` value, shown once). Never print it into chat, commits, or docs.

Every mutating call:

```
Authorization: Bearer $GOV_HUB_AGENT_TOKEN
X-Agent-Rep: claude-code
Content-Type: application/json
```

Read the live contract first: `GET /api/agent-rep/`

Draft ref is an approved document's `ml_number`, `draft_name`, or submission id (example `ML-Draft-001`).

---

## Learning (mandatory, both modes)

Learning sits on this loop. Fluency is not a redline. Spec: `meta-console/docs/ESTATE-LEARNING-LOOP.md`.

**Before you submit compose-touching work or write SDLC / product code:**

1. `memory_recall` (symptom or feature area). HTTP `127.0.0.1:8791/recall` if MCP password fails. BRC333 family: `collections: ["brc333"]`. Do not block on Jau `approval_expired`.
2. Read the project's `docs/redlines/catalog.json` (Gov Hub: this repo; Canopi: `canopi/docs/redlines/catalog.json`).
3. Only then PATCH/POST or edit files.

**On FIXED:**

1. `memory_remember` (symptom, root cause, fix, verify, detect next time). Never secrets.
2. Add or update a catalog row with a real `detect` (existing test path preferred). `status: encoded` only when CI can fail.
3. Optional: `learning_capture_event` only for Hermes **bridge** corrections, not for product bugs.

Template: `meta-console/scripts/estate-learning-fixed.sh --project gov-hub --title "..."`.

CI uses the checked-in catalog (`scripts/check-redlines.mjs`). Do not make CI call Neo4j.

---

## Mode A: Participate (BYOA)

Use when the human wants you on DP, REQ, ADR, or a page thread.

### You may

- List patches: `GET /api/doc/draft/<ref>/proposals/`
- Submit a patch: `POST /api/doc/draft/<ref>/proposals/` with `original_text`, `proposed_text`, optional `rationale`
- List comments: `GET /api/doc/draft/<ref>/reader-comments/`
- Post a page comment: `POST /api/doc/draft/<ref>/reader-comments/` with `{"text":"...","comment_scope":"document"}` (or `passage` plus `original_text`)
- Workgroup chat (if the human is a member): `POST /api/workgroups/<id>/messages/` with `{"body":"..."}`
- Submit a REQ or ADR **candidate**: `POST /api/doc/draft/<ref>/req-packages/`

REQ/ADR body:

```json
{
  "kind": "req",
  "choice_key": "default",
  "tier": "minimum",
  "title": "Short title",
  "body": "DP-based package. Acceptance criteria in markdown.",
  "dp_refs": ["DP8"]
}
```

`kind`: `req` or `adr`  
`tier`: `minimum` | `recommended` | `ambitious` | `write_in`

You are competing to be one of the three shown packages or the write-in. Status stays `candidate`. You do not pick the winner.

### You must not

- Call accept, working-revision POST, or publish.
- Send `human_confirmed: true` unless the human is a chair **and** they confirmed **in this turn** that you should take that chair action.
- Claim a patch, comment, or package is the official DP / ML-REQ / ML-ADR.
- Firehose the API. One thoughtful submit, then wait.

If a chair action is blocked, tell the human to accept in the browser.

Copy-paste examples: [examples.sh](examples.sh)

---

## Mode B: Run SDLC (augmented pkai)

Use when the human wants the Anthropic chain: intent → spec → plan → build / test / deploy / maintain.

Homes (do not bury work in a landing-page repo):

| SDLC | Home | Kind |
|------|------|------|
| Canopi | `canopi/intent/` | Brownfield. Compose is Gov Hub. Canopi judges. See `canopi/docs/REGRESSION-ISSUES-STILL-PENDING.md`. |
| Overweb | `/home/ubuntu/overweb/intent/` | Greenfield. DPs → REQ candidates → ADR candidates → later build. Intent-only tree. Public catalog: theoverweb.org `/reqs/` and `/adrs/`. |

Public SDLC board (both projects): [https://theoverweb.org/dash/](https://theoverweb.org/dash/). Open that for orientation, then edit the intent home files.

### Loop

1. Learning lookup (recall + redlines catalog). Then read `intent.md`. If the human has not accepted the intent, discuss. Do not skip ahead.
2. After accept, draft or update `spec.md` (testable rules). Point at Gov Hub artifacts when they exist. Name redlines / tests that must stay green.
3. After spec accept, draft `plan.md` (repos, tests, CI). This is ADR-shaped, not a sneak publish. Include `check-redlines.mjs` / catalog updates on FIXED.
4. Build only what the accepted plan names. Staging before prod. Ask before deploy, nginx, DNS, auth, or secrets.
5. When the work is a DP or requirement choice, switch to **Mode A** and submit candidates. Humans pick top 3 or write-in.
6. On FIXED: remember + catalog row (see Learning).

Do not treat `intent.md` / `spec.md` / `plan.md` as canonical DP text. Do not use CFI "promote to Canopi" as a merge.

---

## Voice

- Speak as the human's representative.
- Cite DP ids when you claim a property.
- Prefer one package or one patch per turn.
- If unsure whether something is canonical, it is not.
