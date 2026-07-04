# Signal Artifact — Architecture (consolidated)

**Status:** Design / pre-implementation  
**Related:** `signal_artifact_cursor_briefing.md`, `artifact_specification.md`  
**Last updated:** 2026-05-26  
**Context:** Architecture discussion for Gov Hub homepage Signal under Quick stats; implementation deferred.

---

## Purpose

Signal is a **Metaweb primitive**: a living, versioned stream of short civic reflections — not a quote widget or social feed. The homepage card under Quick stats is a **view** into one configured stream instance, not a special-case feature.

Design goals: calm, dignified, traceable, stewarded civic memory.

---

## Core architectural move

Treat **Signal as a first-class artifact type** aligned with the existing Gov Hub artifact spine.

| Layer | Entity | Role |
|-------|--------|------|
| **Signal stream** | `Artifact` with `artifact_type='signal'` | Container: voice, cadence, generation mode, reliability config, steward settings |
| **Signal item** | Child entity (table or sub-model) | One reflection: text, sequence, versions, engagement, slot metadata |

**Homepage placement:** glass card in the Quick stats column (`col-lg-4`), beside Documents / Workgroups. Resolved via site config pointer (e.g. `site_config.signals_primary_stream_id` → primary stream artifact).

**Rollout:** gate behind `product_rollout.signals` (same pattern as nav pills, page heroes).

---

## Artifact spec additions

Extend `artifact_specification.md` with:

### Signal stream (`artifact_type='signal'`)

- **Purpose:** curated civic reflection stream; institutional memory
- **`artifact_subtype`:** e.g. `primary`, `layer`, `workgroup` (future per-layer streams)
- **`layer_id`:** nullable for site-wide Meta-Layer stream
- **`knowledge_scaffold`:** `contentPattern`, `frequency`, `generationMode`, `slug`, optional `cognitiveEnvironment`, **reliability config** (see below)
- **Relationships:** other artifacts cite signal items via `ArtifactRelation`

### Signal item (not a full governance artifact)

- Lightweight, high-churn content
- Mandatory version history — never silent overwrite
- Editorial status: `draft → scheduled → published → archived`
- Slot metadata: `expected_publish_date`, `actual_publish_at`, `slot_status`

**Recommendation:** one stream artifact + many signal items in dedicated tables (`signal_item`, `signal_version`). Seed from JSON; normalize early. Spec JSON schema now (see briefing); avoid long-term engagement in JSON blobs.

**Linking:** other artifacts reference signal items; items are not promoted to full artifact types (avoids directory pollution with thousands of one-liners).

---

## Data model (briefing + architecture extensions)

See `signal_artifact_cursor_briefing.md` for full TypeScript-style schema (`SignalArtifact`, `SignalItem`, `SignalContentPattern`, `SignalFrequency`, `SignalVersion`, etc.).

### Reliability config (new — on stream scaffold)

```yaml
reliability:
  minScheduledAhead: 7          # minimum approved+scheduled items in queue
  graceMinutes: 30              # on-time if live within this window after publishTime
  missDeadlineHours: 4          # after this, slot is declared missed
  liveTtlHours: 24              # homepage "today's signal" window (daily cadence)
  shortieAfterDays: 7           # archive compact presentation after this
  fallbackPoolEnabled: true     # emergency reserve of steward-approved signals
```

### Stream reliability states

- `active` — normal operation
- `degraded` — miss or failed publish; recovery in progress or fallback used
- `paused` — intentional halt (blocked if queue below minimum depth)

### Slot status (per item / slot)

- `on_time` — published within grace window
- `late` — published after grace, before miss deadline
- `missed` — no live signal by miss deadline
- `recovered` — published after miss via fallback ladder

---

## Publishing as infrastructure (critical)

**A missed signal is a problem. A failed scheduled publish is a big deal.**

Signal is a **daily civic clock**, not optional content. Publishing must be a first-class service.

### Two failure modes

| Failure | Meaning |
|---------|---------|
| **Missed slot** | No signal live for the expected calendar window |
| **Failed publish** | Scheduled/ready item did not publish at `publishTime` |

Record which case occurred in EventLog and slot metadata.

### Publish contract (daily example)

- Cadence: daily @ 08:00 `America/Los_Angeles`
- Grace: 30 minutes (on-time if live by 08:30)
- Miss deadline: 4 hours after publishTime
- Minimum queue: 7 items approved+scheduled ahead

### Publish worker (required)

- Dedicated job (systemd timer or equivalent), every 1–5 minutes
- Idempotent `publish_due_signals()` — never rely on homepage load
- Separate health check: "Is today's slot satisfied?"

### Fallback ladder (on publish failure)

1. Retry intended scheduled item
2. Promote next approved item from queue
3. Pull from **fallback pool** (`fallback_eligible` items, steward-curated, not yesterday's repeat)
4. Escalate: steward + site-admin alert; stream → `degraded`
5. Last resort: honest **degraded UI** ("Signal paused — steward notified") — **not** silence, **not** yesterday's text posing as today

### Proactive alerts

- Queue depth &lt; 3 days → warning
- Queue depth &lt; 1 day → urgent
- Scheduled item past `publish_at` still `scheduled` → critical
- Miss declared → in-app + email to stewards; admin banner

Event types: `signal_publish_attempted`, `signal_publish_failed`, `signal_publish_recovered`, `signal_slot_missed`.

---

## Display lifecycle: live → dead → archive shortie

Editorial status and display lifecycle are **separate dimensions**.

| Phase | Window (daily example) | Homepage | Archive |
|-------|------------------------|----------|---------|
| **Live** | Current slot / until next publish | "Today's Signal" | Visible |
| **Recent** | 24h–7d | Hidden | Full row |
| **Dead (shortie)** | After `shortieAfterDays` | Never current | Compact one-line entry |

**Dead** = no longer eligible as current signal; still linkable, commentable, bookmarkable.

Homepage resolver:

```
current_live_signal(stream_id)
  WHERE status = published
    AND published_at satisfies current slot window
```

If none → miss/degraded UI, not "most recent published ever."

**Shortie** = archive presentation mode (computed from dates or set by nightly job):

```
#1842 · 2026-03-12 · "Every protocol shapes behavior."
```

---

## Engagement

Attach to **signal item**, not only stream.

| Capability | Approach |
|------------|----------|
| Comments / replies | Extend `Comment` with `signal_item_id`; reuse threading patterns from artifact comments |
| Follow stream | `UserEventSubscription`: `subject_type='signal_stream'`, `event_type='signal_published'` |
| Like / bookmark | New `signal_engagement(user_id, signal_item_id, kind)` — counts derived from rows, not JSON |
| Share | Link to item page + optional Open Graph |
| References | `ArtifactRelation` or draft metadata → `signal_item_id` |

**Product guardrail:** no dopamine loops, no like-spam notifications. Follow notifications only on new publish, opt-in.

---

## LLM + steward operations

Three operator surfaces:

### 1. Configuration (slow-changing)

Stream scaffold: `contentPattern`, `frequency`, `generationMode`, `cognitiveEnvironment`. Steward UI: Admin → Signals → Stream settings. Version stream-level config changes in audit log.

### 2. Content operations (day-to-day)

- **Queue** — drafts, scheduled, LLM proposals awaiting approval
- **Published** — archive with edit / retire
- **Import** — JSON batch (seed file)
- **Generate** — "Request N drafts" with optional context override

**Rule:** LLM output always `draft`. Human steward approves → schedule → publish. Never auto-publish.

**Queue discipline:** "Approve week" batch workflow; auto-assign `publish_at` to next open slot on approve; weekly LLM buffer generation.

### 3. LLM service

`services/signal_generation.py`:

- Input: ordered published texts + `contentPattern` + optional context + count
- Output: strict JSON (`text`, `tags`, `rationale`)
- Dedup: similarity check against existing signals before steward review
- Prompt: see `signal_artifact_cursor_briefing.md`

---

## Human interface map

| Surface | Audience | Purpose |
|---------|----------|---------|
| Homepage card | Public | Today's live signal under Quick stats |
| Logged-in greeting | Authenticated | Optional warm "Welcome back / Today's Signal" |
| `/signals/` archive | Public | Chronological feed, tags, search, sort by engagement |
| Item page | Public | Canonical text, versions, references, discuss |
| Steward admin | Stewards | Config, queue, LLM generate, approve, import |

Homepage card (calm, not social bait):

```txt
Signals
Signal #1842

Every protocol shapes behavior.

♡ 241   Bookmark   Share   Discuss
```

---

## Phasing

### Phase 1 — Primitive + homepage (MVP)

1. Spec `signal` in artifact docs
2. Stream artifact + item + version tables
3. JSON seed import
4. Homepage card + publish worker + reliability config
5. Manual steward create/edit with version history
6. Archive page

### Phase 2 — Engagement

7. Like, bookmark, share
8. Comments on item
9. Follow stream

### Phase 3 — LLM

10. Generate drafts + steward approval UI
11. Scheduling automation + proactive queue alerts

### Defer

- Version-level reaction splits
- Reputation graph
- Auto context ingestion
- Recommendation algorithms
- Cross-artifact citation graph viz

---

## Design principles (non-negotiable)

- Restraint, dignity, clarity, traceability, continuity, human stewardship
- Not a quote wall, social feed, or motivational wallpaper
- A quiet observatory — living civic intelligence
- Misses are visible to stewards, not hidden from the public via stale content

---

## Open decisions (when returning to implementation)

- Exact grace window and shortie TTL values
- Fallback pool size and eligibility rules
- Whether weekly/layer streams share same reliability model
- Slack/external escalation webhook (post-MVP)
- `product_rollout.signals` default for dev vs prod

---

## References

- `signal_artifact_cursor_briefing.md` — schema, UI mockups, LLM prompt, MVP acceptance criteria
- `artifact_specification.md` — base artifact model
- `routes/pages.py` — Quick stats column placement
- `models/artifact.py` — `Artifact`, `Comment`, `knowledge_scaffold`
- `models/notifications.py` — `UserEventSubscription` for follow
