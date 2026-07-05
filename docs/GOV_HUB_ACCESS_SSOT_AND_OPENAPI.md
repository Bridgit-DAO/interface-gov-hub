# Gov-Hub-Dev: access model, schema SSOT, notifications, OpenAPI

This document is the **product + engineering contract** for visibility/join rules, how database changes are owned, shipping the **notification subscription stack (choice A)**, and maintaining **OpenAPI** alongside Flask.

---

## 1. Target access model (layers, guilds, quests)

Use **two independent axes** everywhere. Mixing them into one enum causes impossible states and leaky APIs.

### 1.1 `listing_visibility` – *who can see that the entity exists*

| Value       | Meaning (recommended semantics) |
|------------|----------------------------------|
| `public`   | Anonymous and logged-in users may see **listing metadata** (name, slug, teaser) subject to route policy. |
| `private` | Only eligible members / invite holders / staff see the entity in lists and detail. Others get 404 or empty list (pick one policy per resource and document it in OpenAPI). |

### 1.2 `join_policy` – *how someone becomes a participant*

**Layers and guilds** (same enum set):

| Value            | Meaning |
|------------------|---------|
| `open`           | Eligible users can join without an invite (subject to auth; e.g. must be logged in). |
| `by_invitation`  | Membership requires a valid invite (or admin add), not self-serve join. |

**Quests** (superset):

| Value              | Meaning |
|--------------------|---------|
| `open`             | Any eligible user (e.g. logged in) may participate if they satisfy listing visibility. |
| `open_to_layer`    | Only users who are **active members** of the quest’s `layer_id` may participate. |
| `open_to_guild`    | Only users who are **active members** of at least one guild **linked** to the quest (via `GuildQuestLink` or a dedicated quest–guild scope you define) may participate. |
| `by_invitation`    | Participation requires invite or explicit grant. |

### 1.3 Composition rules (examples)

- **Public layer + open join**: directory shows the layer; “Join” works for any logged-in user (or stricter if you require email verification).
- **Private layer + open join**: contradictory unless “open” only applies **after** visibility is satisfied (e.g. link-only discovery). Prefer: private layers are always `by_invitation` or use a separate **“unlisted”** flag later.
- **Quest `open_to_guild`**: enforce at **quest submission / assignment** time, not only in the UI. Server must check guild membership + link rows.

### 1.4 Implementation status (v1)

**Shipped in code:** `listing_visibility` and `join_policy` columns on `layer`, `guild`, and `quest` (defaults: `public` / `open`), idempotent SQLite migration `migrate_access_control_v1`, helpers in `services/access_policy.py`, and route enforcement for:

- Layer and guild **list + detail + carousel** (private → 404 for non-members except layer admins / site admin for layers; guild members for guilds).
- Quest **listings** and **submit** (`open_to_layer`, `open_to_guild`, `by_invitation` interim: creator or layer admin only).

**Still to do:** Quest invitation objects, guild/layer **join_policy** enforcement on join endpoints, full UI for toggles, and expanding OpenAPI/CI lint.

---

## 2. Notifications (choice **A** – ship the full stack)

**Goal:** No orphaned modules: everything that imports `UserEventSubscription` / `UserNotification` (or successors) lives in git with models, migrations, and routes.

### 2.1 Recommended shape

1. **Models** in `models/` (or split module), exported from `models/__init__.py`.
2. **Migration** in `migrations/__init__.py` inside a named `migrate_*` function (consistent with current `init_db`), **or** introduce Alembic (see §3) – do not add tables only in `create_all()` without a migration path for production SQLite/Postgres.
3. **Services** (`document_follow_notifications`, `event_subscriptions`, etc.) committed together.
4. **Routes** re-wired in one change set so `from app import app` and pytest never see a half-imported graph.
5. **Backfill** optional: migrate `UserFollow` rows into `UserEventSubscription` if you replace the follow table, or keep `UserFollow` read-only until cutover.

### 2.2 Deprecation

Once subscriptions are authoritative, **remove** duplicate paths: legacy `UserFollow`-only notification logic, Hypothesis-specific delivery if product is retired, and comments in `event_registry` that reference models that do not exist.

---

## 3. Single source of truth (SSOT) for schema changes

You effectively have **three** patterns in the wild. Here is when to use each and when to switch.

### 3.1 Pattern A – `migrate_*` functions + `database/init_db.py` (current default)

**What it is:** Idempotent Python checks (`sqlite_master`, `PRAGMA`, etc.) that add columns/tables, invoked from `init_db()` and pytest `conftest`.

**Pros:** Simple for SQLite dev; no extra tooling; matches existing `gov-hub-dev` history.

**Cons:** Harder to review diffs for large teams; ordering of calls matters; Postgres parity is manual; no automatic “down” migrations.

**Stay here if:** You remain SQLite-first, small team, and migrations stay small and idempotent.

### 3.2 Pattern B – Alembic (SQLAlchemy migrations)

**What it is:** Versioned revision files; `upgrade` / `downgrade`; can target Postgres and SQLite.

**Pros:** Industry standard; reviewable; reproducible prod deploys; easier multi-developer branching.

**Cons:** Upfront setup; you must align `env.py` with Flask app context; still need discipline to run migrations in CI/CD.

**Switch when:** You add Postgres (or another server DB), hire more contributors, or `migrate_*` becomes unmaintainable.

### 3.3 Pattern C – External SQL + ops-run scripts

**Pros:** DBA-friendly for large installations.

**Cons:** Drifts from ORM unless strictly paired with models; easy to forget in dev.

**Use for:** One-off data fixes, not routine schema.

### 3.4 Practical recommendation for Gov-Hub-Dev

- **Short term:** Keep **Pattern A** for new columns (`listing_visibility`, `join_policy`, notification tables). Add one `migrate_access_control_v1` and one `migrate_event_subscriptions_v1` (names illustrative) that are idempotent and listed in `database/__init__.py` in dependency order.
- **Trigger to adopt Alembic:** First production Postgres deployment or when migration ordering bugs cost more than one day.

---

## 4. OpenAPI

### 4.1 Location

- **`openapi/openapi.yaml`** – OpenAPI 3.x document, versioned with the API.

### 4.2 SSOT tension

- **Code is the behavior**; **OpenAPI is the promise** to integrators.
- **Rule:** Any **public** JSON API change merges **OpenAPI in the same PR** (or CI fails).

### 4.3 Auth

Document session cookie auth (e.g. `session` cookie) as `securitySchemes.cookieAuth` with `type: apiKey`, `in: cookie`, `name: session` (adjust to your real cookie name from Flask config).

### 4.4 CI (recommended next step)

Add a job that runs `npx @redocly/cli lint openapi/openapi.yaml` or `swagger-cli validate` so the file cannot rot.

### 4.5 Optional later: generated clients

If you publish SDKs, consider generating from OpenAPI; keep the YAML authoritative.

---

## 5. Legacy removal (explicit targets)

| Area              | Action |
|-------------------|--------|
| Hypothesis        | Remove models, routes, and templates if product direction is Canopi-only; grep `hypothesis`, `HypothesisAccount`. |
| `UserFollow`      | After subscription migration, redirect UI/API to `UserEventSubscription` or drop table behind migration. |
| Duplicate follow notification code | One delivery pipeline only. |
| Untracked `services/*` | Nothing under `services/` that is imported should stay untracked – commit or delete. |

---

## 6. Suggested implementation order

1. **OpenAPI baseline** – merge `openapi/openapi.yaml` + lint in CI; cover guild/layer link endpoints first, expand weekly.
2. **Access columns + migration** – layer, guild, quest; defaults preserve today’s behavior.
3. **Central policy module** – all list/detail/join checks call shared functions; add pytest matrix.
4. **Notifications stack (A)** – models, migration, wire routes/services, remove legacy duplicate.
5. **Quest rules** – enforce `open_to_layer` / `open_to_guild` on submission endpoints.
6. **UI** – forms for officers/admins; consistent error messages matching OpenAPI error schema.

---

## 7. Related files

- `database/__init__.py` – migration runner order.
- `migrations/__init__.py` – idempotent DDL.
- `openapi/openapi.yaml` – public HTTP contract.
- `models/coordination.py` – `Layer`, `Guild`, `Quest` (columns to extend).
- `services/guild_phase1.py` – guild–layer–artifact–quest **link** permissions (orthogonal to listing/join visibility).
