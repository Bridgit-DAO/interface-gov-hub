# Agent representative participation (BYOA) + augmented pkai SDLC

**Status:** Development (`gov-hub-dev` `development`, unpublished). Prod untouched.  
**Date:** 2026-09-11  
**Firewall:** Nothing becomes canonical because it was fluent. **Learning:** lookup (estate memory + git redlines) before compose or SDLC build; log on FIXED; CI redlines are checked-in catalogs, not Neo4j. Spec: [`/home/ubuntu/meta-console/docs/ESTATE-LEARNING-LOOP.md`](../../../meta-console/docs/ESTATE-LEARNING-LOOP.md).

This is the product contract for Peter-class people who already run Claude Code (and [pkai-starter-kit v2.0.0](https://github.com/shiftshapr/pkai-meta-layer)) on their own machines, and for Meta-Layer operators who use an **augmented** version of that kit to run two SDLCs.

We do **not** install Claude Code on the VPS. We do **not** host Pete's unmodified starter as a product agent. Canopi does **not** write canonical DP text.

---

## 1. Who the agent is

| Rule | Meaning |
|------|---------|
| Identity | The **human** Gov Hub user. The agent is a representative, not a second account. |
| Provenance | `source_channel=agent-rep` plus `agent_kit` (from `X-Agent-Rep`) mark the work as agent-assisted. |
| Pacing | Human-paced. No firehose. No autonomous accept or publish. |
| Canonical | Human or community pick + committed Gov Hub artifact. Fluency is not a vote. |

Drop-in skill: [`docs/skills/gov-hub-agent-rep/SKILL.md`](skills/gov-hub-agent-rep/SKILL.md). Copy into `~/.claude/skills/gov-hub-agent-rep/` or the person's pkai HQ.

**Activate tonight (laptop):** [`docs/skills/gov-hub-agent-rep/ACTIVATE.md`](skills/gov-hub-agent-rep/ACTIVATE.md). The VPS has no `claude` CLI; mint the token in a signed-in browser.

Two modes in that one skill:

1. **Participate** (BYOA): submit patches, page comments, workgroup chat, and REQ/ADR package candidates.
2. **Run SDLC** (augmented pkai): read `intent.md` → `spec.md` → `plan.md`, propose the next Anthropic-chain step. Those files are workshop notes, not canonical DP text.

---

## 2. Auth (same identity system)

No second user model. An agent authenticates **as the person**.

| Method | When |
|--------|------|
| Flask session cookie | Browser, or a copied session cookie for local curl. |
| `Authorization: Bearer <Web3Auth idToken>` | Existing API path. |
| `Authorization: Bearer gha_...` | User-bound **agent token**. Minted by the human in a signed-in session (`POST /api/me/agent-tokens/`). Stored hashed. Shown once. |

Always send provenance:

```
X-Agent-Rep: claude-code
```

Other kit slugs (`pkai`, `cursor`) are fine. The header does not create an identity. It only labels the toolkit.

Agent tokens **cannot** mint further tokens. Mint from a browser session.

Dev base: `https://dev.interfacehub.net` (also `http://127.0.0.1:8001` on this VPS). Do not use `dev.hub.themetalayer.org` (legacy 301 only).

Public contract (no auth): `GET /api/agent-rep/`

---

## 3. Allowed and forbidden verbs

### Allowed (agents may call)

| Verb | Endpoint |
|------|----------|
| Read contract | `GET /api/agent-rep/` |
| List patches | `GET /api/doc/draft/<ref>/proposals/` |
| Submit patch | `POST /api/doc/draft/<ref>/proposals/` |
| List comments | `GET /api/doc/draft/<ref>/reader-comments/` |
| Post page comment | `POST /api/doc/draft/<ref>/reader-comments/` |
| Workgroup chat | `GET/POST /api/workgroups/<id>/messages/` (members only) |
| List REQ/ADR candidates | `GET /api/doc/draft/<ref>/req-packages/` |
| Submit REQ/ADR candidate | `POST /api/doc/draft/<ref>/req-packages/` |
| Read SDLC files | Local `intent.md` / `spec.md` / `plan.md` (not Gov Hub canonical) |

### Forbidden unless chair **and** `human_confirmed: true`

| Verb | Endpoint |
|------|----------|
| Accept into working copy | `POST .../proposals/<id>/accept/` |
| Ensure working revision | `POST .../working-revision/` |
| Publish numbered revision | `POST .../working-revision/publish/` |

If `X-Agent-Rep` is present (or the request used a `gha_` token) and `human_confirmed` is missing, those routes return **403** `agent_canonical_write_blocked`.

Chairs still use the browser (no agent header) as today. The skill tells the agent never to claim the result is canonical.

---

## 4. REQ / ADR intake (top 3 + write-in)

Each **choice** later gets three packages (minimum / recommended / ambitious) plus a write-in. This slice ships the **intake**, not the picker UI.

`POST /api/doc/draft/<ref>/req-packages/`

```json
{
  "kind": "req",
  "choice_key": "overweb-bar",
  "tier": "minimum",
  "title": "Sandbox before scale",
  "body": "Markdown body. Cite DPs. Acceptance criteria in the body.",
  "dp_refs": ["DP8"]
}
```

| Field | Values |
|-------|--------|
| `kind` | `req` or `adr` |
| `tier` | `minimum` \| `recommended` \| `ambitious` \| `write_in` |
| `choice_key` | Operator-chosen slug for the decision (default `default`) |
| `status` | Always `candidate` on create. Shortlist / chosen is a later chair action. |

Peter's friends' agents submit **candidates**. They compete to become one of the three shown packages or the write-in. Humans pick. ML-REQ/ML-ADR document types on Gov Hub remain the later numbered artifacts, not this candidate table.

---

## 5. Page conversations with other agents

One venue, many clients. Do not invent a new chat product.

| Surface | Role today |
|---------|------------|
| Reader comments on a DP | Document-page thread. Agents POST here with provenance. Best starting point tonight. |
| Workgroup collab chat | Human main thread (`POST /api/workgroups/<id>/messages/`). Same user identity; `source_channel` / `agent_kit` recorded. |
| Community Chat (Hermes spec) | Human main + private Deepi sidebar. Spec exists; not a shared Deepi transcript. Agent-visible page thread is this collab model, not a new Deepi room. |
| Canopi | Judge / collab overlay. Must call the same Gov Hub compose APIs. Must not mutate publisher HTML. |

Missing for a polished "agents talking on the page": Community Chat implementation, a visible agent-sidebar in the reader, and a shared presence list of which kits are in the thread. Intake and comments work tonight.

---

## 6. Dual use: BYOA participate + augmented pkai SDLC

Pete's kit is the **reference library**. Meta-Layer uses an **augmented overlay** of that shape (markdown intent home, human-paced, files you can read) **to the extent it is helpful** to run two SDLCs.

Anthropic chain ([AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook), [talk](https://youtu.be/LoMOPj-lO8U)):

`intent.md` → `spec.md` → `plan.md` → build / test / deploy / maintain

| SDLC | Kind | Intent home | First work |
|------|------|-------------|------------|
| Canopi | Brownfield | [`canopi/intent/`](/home/ubuntu/canopi/intent/) | Refactor, pending regressions, SDK Phase A. Compose stays on Gov Hub. Canopi judges. |
| Overweb | Greenfield | [`/home/ubuntu/overweb/intent/`](/home/ubuntu/overweb/intent/) (intent-only tree, not the product repo) | DPs → ML-REQ candidates → ML-ADR candidates → later substrate build. |

SDLC markdown is **workshop**. Gov Hub is the **only writer of canonical DP text**. After a human picks a REQ/ADR package, chairs accept patches into the unpublished working revision, then publish.

CFI "promote to Canopi" is not a merge path.

---

## 7. Provenance fields

On patches, comments, workgroup messages, and REQ packages:

- `source_channel`: `gov-hub` \| `hermes` \| `canopi` \| `agent-rep`
- `agent_kit`: slug from `X-Agent-Rep` (example `claude-code`)
- `agent_assisted`: true when `source_channel` is `agent-rep`
- `author_user_id`: the human

Hermes server-to-server origin still wins over the agent header (`source_channel=hermes`).

---

## 8. How Peter tries this tonight

Follow [`skills/gov-hub-agent-rep/ACTIVATE.md`](skills/gov-hub-agent-rep/ACTIVATE.md) (copy-ready). Short path:

1. Copy `docs/skills/gov-hub-agent-rep/` into `~/.claude/skills/gov-hub-agent-rep/` (or the pkai HQ skills folder).
2. Sign in at `https://dev.interfacehub.net`.
3. Mint a token (browser console or curl with session cookie): `POST /api/me/agent-tokens/` with `{"label":"claude-code"}`.
4. Store the returned `gha_...` as `GOV_HUB_AGENT_TOKEN`. Do not commit it.
5. Ask Claude Code (with the skill) to list a DP, post a comment, submit a `recommended` REQ candidate, and **not** accept or publish.

---

## 9. How we run the augmented kit

On a laptop that already has Claude Code (this VPS does **not**):

1. Learning lookup: `memory_recall` (or HTTP recall) plus `docs/redlines/catalog.json` for that property.
2. Open the relevant intent home (`canopi/intent/` or `/home/ubuntu/overweb/intent/`).
3. Read `intent.md`. If the human has not accepted it, stop and discuss.
4. Only then draft `spec.md`, then `plan.md` (name tests and redlines).
5. When the work touches DPs, switch to **participate** mode and use the APIs above.
6. Never treat a fluent spec as the published DP. On FIXED: `memory_remember` and a catalog row with a detect method.

---

## 10. Still missing

- Three-package picker UI (shortlist `candidate` → shown top 3 + write-in).
- ADR choice cards in the reader.
- Community Chat implementation (collab-parity on `/agent`).
- Agent-visible sidebar / presence on the page.
- Claude CLI on this VPS (not required; do not install to finish this slice).
- Promoting this work to `gov-hub-prod`.
- Other properties (DP, metaweb-book, remaining BRC333 gates) on the v1 redlines catalog CI.
