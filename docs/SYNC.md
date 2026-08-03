# Branch sync plan (development ↔ main)

**As of:** 2026-08-01 (historical inventory below)  
**Updated:** 2026-08-03 — live release branch is **`main`** (retargeted to the former `production` tip; `production` kept temporarily as an alias). Promote with `development` → `main`. See [DEV-TO-PROD-WORKFLOW.md](./DEV-TO-PROD-WORKFLOW.md).  
**Merge-base:** `dfc42dbd2`  
**Worktrees:** `gov-hub-dev` → `development` (8001), `gov-hub-prod` → `main` (8000)

> Historical note: tables and commands below that say `production` refer to the gated live branch as of the 2026-08-01 sync. That tip is now `main` (same SHA as `origin/production` until the alias is deleted).

## Current state

| Branch | HEAD | Commits ahead of merge-base |
|--------|------|----------------------------|
| `development` | `b5b65f1ec` | 14 |
| `production` | `121df5041` | 22 |

Both branches contain **parallel copies** of the same fixes (different SHAs, same subjects). That duplication is the main source of merge pain—not unrelated features.

### Parallel commits (already on both sides; resolve by keeping one side or merging hunks)

| development | production | Subject |
|-------------|------------|---------|
| `b5b65f1ec` | `121df5041` | fix: waitlist deep link ReferenceError on enabledWaitlists |
| `6828f6968` | `bf1ccad78` | feat: Metaweb catalog API and multi-workgroup action checks |
| `def06f3c1` | `8a5d77540` | fix: badges page load, role-images rollout, and Canopi profile avatars |
| `8889f28f6` | `a3ec9e9a6` | fix(ui): workgroups directory active-only, remove status filter |
| `f352ce7fa` | `a1aa39e7d` | fix: correct workgroup self-nomination misclassification |
| `bb2acadaa` | `f1139a00d` | fix: use hub.themetalayer.org for outbound email links |
| `8c4ac337b` | `e1a351e08` | feat: show Join/Nominate buttons for signed-out users on workgroup detail |
| `e8e52cc66` | `bba1c4ce7` | fix: nomination respond buttons broken by invalid GhDialog JS |
| `d7bc98260` | `42719df9d` | feat: email layer admins when nominee accepts nomination |
| `faa9b337f` | `1b9b19980` | fix: update nomination acceptance page disclaimer text |

### development-only (not on production)

| Commit | Theme |
|--------|-------|
| `8a041160e` | DP proposals: refresh auth state + patch count without full reload |
| `4921ff52f` | Documents: `collection=` query filter on `/doc/all/` |
| `bab347f1c` | Refactor: shared email/public URL helpers, people directory, workgroup APIs |
| `a21b3cacc` | People: workgroup rosters, patch diffs, fewer dead-end prompts |
| `d0eb06632` | Config: reserve hub subdomain + layer host tests |

### production-only (not on development)

| Commit | Theme |
|--------|-------|
| `b78814c93` | DP APIs: Bearer Web3Auth, considered status, badge hooks |
| `39512e559` | Docs: hub.themetalayer.org nginx alias |
| `a5422a9b6` | Support: tickets, admin UI, Hermes triage API |
| `9a0a72f47` | DP: workgroup welcome delivery + membership on admin approve |
| `a114fe15c` | Nominations: bind responses to nominee, harden approval |
| `85e74d6bd` | Scope: remove unused `/api/me/layer-admin/<slug>/` |
| `da97be39d` | Canopi: resolve layer by slug or name, not acronym |
| `9cd822f4b` | Governance Phase 0: contribution registry, scout queue, patch accept permissions |
| `7805d3136` | Governance: harden contribution pipeline after Phase 0 review |
| `ec58d99cd` | Governance Phase 1: Canopi contribution intake webhook |
| `d4fd70aeb` | Governance: harden contribution intake and queue processing |
| `db3f69b9b` | Tests: hub.themetalayer.org hosts + nomination self-detection |

---

## Merge conflict preview (dry-run)

`git merge-tree $(git merge-base development production) development production` reports **18 files changed in both** with textual conflicts:

```
app.py
cli/notification_digest.py
database/__init__.py
migrations/__init__.py
models/coordination.py
routes/directory.py
routes/dp_proposals.py
routes/layer_detail_render.py
routes/nominations_pages.py
routes/workgroups.py
routes/workgroups_api.py
routes/workgroups_pages.py
services/document_patches_page.py
services/layer_invitation_mail.py
services/product_rollout.py
services/workgroup_membership.py
services/workgroup_nomination_mail.py
services/workgroup_positions.py
```

**High-risk overlap areas** (both branches edited the same modules for different features):

- **Workgroups / nominations:** prod added nomination binding + DP welcome; dev added rosters, people directory, public URL refactor.
- **DP proposals:** prod added Web3Auth bearer, governance pipeline, contribution intake; dev added reader auth refresh and collection filter.
- **Migrations / database:** prod Phase 0 schema changes vs dev people-directory tables—must merge migration chains carefully.
- **layer_invitation_mail:** dev refactored to shared `public_urls` helpers; prod kept inline URLs—keep dev refactor + prod behavior.

**Do not** force-merge either direction without a conflict-resolution session and dev testing.

---

## Recommended sync order

Goal: **`development` becomes the single integration branch** containing everything, tested on 8001, then promoted to `main`.

### Phase 1 — Merge live (`main` / then-`production`) → development (integration)

```bash
cd ~/gov-hub-dev
git fetch origin
git checkout development
git pull origin development

# Optional: integration branch so development stays deployable during resolution
git checkout -b sync/prod-into-dev-20260801
git merge origin/main -m "sync: merge main into development"
# (During the 2026-08-01 sync this was origin/production — same tip as main after 2026-08-03.)
# Resolve 18 conflicts (see resolution guide below)
git push origin sync/prod-into-dev-20260801
```

**Why prod → dev first:** Production has live-only features (governance pipeline, support tickets, DP welcome, Web3Auth) that must land on dev before any dev→prod promote. Merging dev→prod first would ship dev-only work but **drop** prod-only commits.

### Phase 2 — Test on dev (mandatory gate)

See checklist in [DEV-TO-PROD-WORKFLOW.md](./DEV-TO-PROD-WORKFLOW.md#pre-promote-checklist-on-development).

```bash
cd ~/gov-hub-dev
git checkout development   # after merge PR approved
git merge sync/prod-into-dev-20260801
systemctl --user restart datatracker-dev.service
python3 test_core_features.py
python3 -m pytest test_layer_features.py test_layer_resolution.py test_workgroup_nomination_mail.py \
  test_metaweb_action_status.py test_dp_proposals.py test_documents_collection_filter.py \
  test_workgroup_membership.py test_text_diff.py 2>/dev/null || true
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://dev.govhub.live/api/metaweb/action-status \
  -H 'Content-Type: application/json' -d '{"checks":[]}'
```

Fix failures on `development` only. Do not patch `main` directly except documented hotfixes.

### Phase 3 — Promote development → main

After dev tests pass and the integration merge is on `origin/development`:

```bash
cd ~/gov-hub-prod
git fetch origin
git checkout main
git pull origin main
git merge origin/development -m "ship: merge development to main (post-sync)"
git push origin main
systemctl --user restart datatracker.service
```

This merge should be **clean or low-conflict** because `main` is an ancestor of the integrated development tip.

### Phase 4 — Verify prod + align worktrees

```bash
# Prod health
curl -s -o /dev/null -w "%{http_code}\n" https://govhub.live/

# Both worktrees on expected branches
git -C ~/gov-hub-dev rev-parse development
git -C ~/gov-hub-prod rev-parse main
git merge-base development main  # should equal main HEAD after sync
```

---

## Conflict resolution guide (prod → dev)

When resolving the 18 files, prefer **combining both behaviors**:

| File / area | Keep from production | Keep from development |
|-------------|---------------------|----------------------|
| `migrations/__init__.py`, `database/__init__.py` | Phase 0/1 migration steps | Any dev-only schema for people/rosters |
| `routes/dp_proposals.py`, `services/*dp*` | Web3Auth, contribution pipeline, badge hooks | Collection filter, reader auth refresh |
| `routes/workgroups*.py`, `services/workgroup_*` | DP welcome, nomination binding | Rosters, people directory links, public URL refactor |
| `routes/directory.py` | — | People directory + roster UI |
| `services/layer_invitation_mail.py` | Correct hub URLs | `public_urls` / `email_layout` refactor |
| `routes/nominations_pages.py` | Nominee binding hardening | GhDialog fixes (likely identical) |
| Parallel-fix files | Either side if identical | Prefer dev if dev has extra tests (`d0eb06632`) |

For **parallel duplicate commits**, diff the two sides; if hunks match, take either. If dev has strictly more (e.g. `config.py` hub subdomain fix + tests), keep dev.

---

## After sync: prevent re-divergence

1. **All feature work on `development`** — no direct commits to `main`.
2. **Test on dev** (8001 / dev.govhub.live) before every promote.
3. **Promote only via** `git merge origin/development` on `gov-hub-prod` (or PR on GitHub) into `main`.
4. **Hotfixes on `main`** — cherry-pick or merge back to `development` the same day.
5. **Never** cherry-pick the same fix to both branches independently (causes duplicate SHAs and merge conflicts).

See [DEV-TO-PROD-WORKFLOW.md](./DEV-TO-PROD-WORKFLOW.md) for daily commands and the pre-promote checklist.

---

## Approval required before executing

The first git operation with risk is **Phase 1 merge** (18 conflicts). Document updates are safe; **do not run the merge** until a human approves the plan and allocates time for conflict resolution (~1–2 hours).
