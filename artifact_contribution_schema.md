# Artifact Contribution Type Schema + UI Logic (Cursor Ready)

**Canonical product spec:** `gov_hub_knowledge_layer_garden_phased_briefing.md` (§4, §4a, locked decisions).  
This file is the **implementation-facing** summary for Cursor.

---

## 1. Core Fields

### Artifact type (required)

What the object *is*.

`artifact_type` (enum, exact strings TBD vs production):

- `proposal`
- `document`
- `evidence`
- `meeting_summary`
- `decision`
- `bridge`
- `translation`
- `monument_context`
- `comment`
- `poll`
- `announcement`
- `event`

---

### Contribution type (optional, single value)

What kind of thinking the artifact embodies — **IFP-aligned knowledge form**.

- **UI label:** Contribution type  
- **Storage / API:** `knowledge_form` (nullable enum; same seven values, stable casing per API convention e.g. snake_case)

`knowledge_form` (when set, exactly one of):

- `inquiry`
- `principle`
- `model`
- `conviction`
- `decision`
- `gloss`
- `scenario`

**Rules (Unified Phase I):**

- Optional — **`NULL` / omitted = unset** (no default backfill on create).
- **At most one** value per artifact (not a list). **Multi-tag contribution typing is explicitly not supported.**
- Picker offers **default + up to three alternates** (four choices total) per `artifact_type`; user may **clear** selection to leave unset.
- **Authors and editors** may set or change while they can edit the artifact; **moderators / administrators** may override with audit + policy (see briefing locked decisions).

---

## 2. Default when user opens the picker

If the user opens the contribution-type control, pre-highlight the **default** for that `artifact_type` (they can confirm, pick another allowed value, or dismiss / clear).

| `artifact_type`   | Default `knowledge_form` |
|-------------------|---------------------------|
| `proposal`        | `decision`                |
| `document`        | `model`                   |
| `evidence`        | `model`                   |
| `meeting_summary` | `model`                   |
| `decision`        | `decision`                |
| `bridge`          | `gloss`                   |
| `translation`     | `gloss`                   |
| `monument_context`| `scenario`                |
| `comment`         | `conviction`              |
| `poll`            | `decision`                |
| `announcement`    | `decision`                |
| `event`           | `scenario`                |

---

## 3. Allowed picker set (default + ≤3 alternates)

Values below are the **only** options shown for that type (plus clear/unset). No full seven-option list per type.

| `artifact_type`   | Allowed `knowledge_form` values (order: default first) |
|-------------------|--------------------------------------------------------|
| `proposal`        | decision, principle, model, inquiry                    |
| `document`        | model, principle, scenario, decision                   |
| `evidence`        | model, scenario, principle, gloss                      |
| `meeting_summary` | model, scenario, inquiry, decision                     |
| `decision`        | decision, principle, model, scenario                   |
| `bridge`          | gloss, model, principle, inquiry                       |
| `translation`     | gloss, principle, model                                |
| `monument_context`| scenario, principle, gloss, model                      |
| `comment`         | conviction, inquiry, principle, model                |
| `poll`            | decision, inquiry, principle                           |
| `announcement`    | decision, principle, model                             |
| `event`           | scenario, inquiry, model                               |

---

## 4. UI logic (create / edit)

1. User selects or has `artifact_type` (required).
2. Optional block: **“What kind of contribution is this?”** with helper: *Helps others understand how to engage with this contribution.*
3. If the user expands the control: show **only** the allowed set for that artifact type (§3); **no** value pre-persisted until they confirm (or persist default only if product chooses “default on save” — briefing assumes nullable unless set).
4. User may select **one** value or **clear** to unset (clears `knowledge_scaffold` on save).
5. If **`knowledge_scaffold_enabled`** and `knowledge_form` is set: show **optional** prompts per **§6** (collapsible section is fine).
6. **Badges (display):** always **artifact type**; **second chip only if `knowledge_form` is non-null** — `[Artifact type] · [Contribution type]` (see briefing §4a). Scaffold does not add a third badge in v1.

---

## 5. Validation

- `knowledge_form` optional; if present must be **one** allowed enum value **and** must be in the **allowed set for that `artifact_type`** (server-side enforce).
- `knowledge_scaffold` must be **null** when `knowledge_form` is null; when non-null, keys must match **§6** for that form only; enforce string max lengths.
- Do not block publish if unset or if scaffold fields are empty.

---

## 6. Optional scaffolding (`knowledge_scaffold`)

When `knowledge_form` is non-null, the artifact may include **optional** structured prompts. **All** scaffold fields are optional; empty scaffold is valid.

| `knowledge_form` | JSON keys (optional) | Typical UI label |
|------------------|----------------------|------------------|
| `inquiry` | `what_is_unclear` (string), `status`: `open` \| `closed` | What is unclear? / Status |
| `principle` | `why_matters` (string) | Why does this matter? |
| `model` | `key_assumptions` (string) | Key assumptions |
| `conviction` | `why_believe` (string) | Why do you believe this? |
| `decision` | `what_resolves` (string), `status`: `draft` \| `final` | What does this resolve? / Status |
| `gloss` | `definition` (string) | Definition |
| `scenario` | `actors_context` (string) | Actors / context |

**Rules:**

- Store as nullable **JSON** on the artifact, e.g. `knowledge_scaffold`.
- If `knowledge_form` is **null**, persist `knowledge_scaffold` as **null** (server clears on save).
- Reject JSON keys that do not belong to the active `knowledge_form`.
- Recommend **max length** per string field (e.g. 2000 codepoints); trim whitespace.
- On `knowledge_form` change, **drop** incompatible scaffold keys (v1 default: wipe non-matching keys).
- Feature flag: **`knowledge_scaffold_enabled`** (separate from contribution-type flag if you want staged rollout).

Full spec: briefing **§5**.

---

## 7. Guardrails

- Do **not** merge `artifact_type` and `knowledge_form` into one field.
- Do **not** require `knowledge_form` or any scaffold field.
- Do **not** allow **multiple** contribution types per artifact.
- Keep scaffold **lightweight** — no required sub-schema in v1.
- **No** relationship / graph UI in Unified Phase I (briefing).
- **Guild ↔ artifact** links remain separate from future **artifact ↔ artifact** edges.

---

## 8. Unified Phase I — also in scope (see briefing §4a)

- **Filtering** by contribution type (facets on feeds / search; feature-flagged rollout).
- **Feature flags:** e.g. `knowledge_contribution_type_enabled`, optional `knowledge_contribution_type_filters_enabled`.
- **Analytics:** e.g. `contribution_type_set`, `contribution_type_cleared`, `contribution_type_filter_applied`.
- **Indexes:** `knowledge_form` (+ scoped composite if queries are always by layer/tenant).

**Localization:** after Unified Phase I is stable, localize Contribution type labels, help copy, and **scaffold** prompts.

---

## 9. Deferred (Unified II+)

- Relationship UI, graph, bundles (briefing §12).
- **Rich** structured fields beyond §6 minimal scaffold (lineage, linked artifacts, etc.).

---

## Summary

| Field                 | Role                                      |
|-----------------------|-------------------------------------------|
| `artifact_type`       | What it is (required)                     |
| `knowledge_form`      | How it thinks (optional, **single**, nullable) |
| `knowledge_scaffold`  | Optional prompts when form is set (JSON)|

Keep them separate. **One** contribution type max. Scaffold never blocks publish.

---

## Code integration (`gov-hub-dev`)

| Area | Location |
|------|-----------|
| Validation + matrix | `services/knowledge_layer.py` |
| `Artifact` columns | `models/artifact.py` (`knowledge_form`, `knowledge_scaffold`) |
| Collections | `models/collection.py`, `routes/collections.py` |
| API | `GET /api/knowledge-layer/schema/`, `PATCH/POST` artifacts in `routes/artifacts.py`, `?knowledge_form=` on layer artifact list |
| Migration | `migrations.migrate_knowledge_layer_integration`, wired in `database/init_db` |
| Feature flags | `config.py` → `app.config` (`KNOWLEDGE_CONTRIBUTION_*`) |
| Events | `contribution_type_set`, `contribution_type_cleared`, `artifact_collection_*` via `emit_event` |
| Smoke tests | `test_knowledge_layer_integration.py` |

Env: `GOVHUB_KNOWLEDGE_CONTRIBUTION_TYPE_ENABLED`, `GOVHUB_KNOWLEDGE_SCAFFOLD_ENABLED`, `GOVHUB_KNOWLEDGE_CONTRIBUTION_FILTERS_ENABLED`.
