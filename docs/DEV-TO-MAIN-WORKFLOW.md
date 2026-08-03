# Gov Hub: development → main

## Branches

| Branch | Role | Server checkout | URL | systemd unit |
|--------|------|-----------------|-----|--------------|
| `development` | Integration & testing | `/home/ubuntu/gov-hub-dev` | dev.hub.themetalayer.org (8001) | `datatracker-dev.service` |
| `main` | **Live production** | `/home/ubuntu/gov-hub-prod` | hub.themetalayer.org / govhub.live (8000) | `datatracker.service` |

**Policy:** `main` **is** production. There is no separate `production` git branch.

**Retired (do not use):** git branch `production` — superseded by `main` on 2026-08-03. Delete remote when ready:

```bash
git push origin --delete production   # after confirming origin/main is canonical
git branch -d production                # local, if present
```

Remote: `https://github.com/Bridgit-DAO/interface-gov-hub.git`

**2026-08-03:** `main` was retargeted to the former `production` tip (pointer move, not a content merge). Old `main` tip is preserved at `archive/main-20260803`. All promotes and hotfixes use **`main`**. Deploy/rollback: `python3 deploy.py main`, `python3 rollback.py main` (CLI alias `prod` is deprecated).

`legacy-main` on the remote preserves older pre-`development` history. Do not merge that backlog into `development`.

## Process rules (required)

1. **All feature work lands on `development`.** Do not commit features directly to `main`.
2. **Test on dev before every promote.** Use port 8001 / `dev.hub.themetalayer.org` and the pre-promote checklist below.
3. **Promote to live** only by merging `development` into `main` (locally on `gov-hub-prod` worktree or via GitHub PR).
4. **Hotfixes on `main`** are allowed when live is broken and dev cannot wait—but **backport to `development` the same day** (cherry-pick or merge `main` → `development`).
5. **Never duplicate fixes** on both branches (same change, two commits). That causes painful merges; see [SYNC.md](./SYNC.md) for the 2026-08 divergence post-mortem.
6. **CI / tests before promote.** Run local tests on dev; GitHub Actions runs on PRs to `main`/`feat/rfc` (datatracker upstream paths)—Gov Hub–specific tests are run manually on the server.

## Daily work (development)

```bash
cd ~/gov-hub-dev
git checkout development
git pull origin development
# ... edit, commit ...
git push origin development
systemctl --user restart datatracker-dev.service
```

Verify on **dev only**:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://dev.govhub.live/api/metaweb/action-status \
  -H 'Content-Type: application/json' -d '{"checks":[]}'
# 401 without auth is OK; 404 means wrong deploy
```

## Pre-promote checklist (on development)

Complete on `gov-hub-dev` **before** merging to `main`:

- [ ] `git status` clean; branch pushed to `origin/development`
- [ ] `systemctl --user restart datatracker-dev.service` — dev app starts without traceback
- [ ] `python3 test_core_features.py` passes
- [ ] Gov Hub tests relevant to the change (examples):
  ```bash
  python3 -m pytest test_layer_features.py test_layer_resolution.py \
    test_workgroup_nomination_mail.py test_metaweb_action_status.py \
    test_dp_proposals.py test_documents_collection_filter.py \
    test_workgroup_membership.py test_text_diff.py -q
  ```
- [ ] Smoke-test changed flows on https://dev.govhub.live (login, workgroups, nominations, DP reader if touched)
- [ ] Migrations: if `migrations/__init__.py` changed, confirm dev DB migrates cleanly on restart
- [ ] No secrets or `.env` changes committed

## Ship to main (live)

```bash
cd ~/gov-hub-prod
git fetch origin
git checkout main
git pull origin main
git merge origin/development -m "ship: merge development to main"
git push origin main
systemctl --user restart datatracker.service
```

After promote, confirm live health and keep branches aligned:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://govhub.live/
cd ~/gov-hub-dev && git pull origin development   # if hotfix was main-only, merge main→dev instead
```

Optional deploy helper (from live worktree):

```bash
cd ~/gov-hub-prod && python3 deploy.py main
```

## Hotfix workflow (live emergency)

```bash
# 1. Fix on main (minimal diff)
cd ~/gov-hub-prod
git checkout main
# ... fix, commit ...
git push origin main
systemctl --user restart datatracker.service

# 2. Backport to development same day
cd ~/gov-hub-dev
git checkout development
git pull origin development
git cherry-pick <hotfix-commit>   # or: git merge origin/main
git push origin development
systemctl --user restart datatracker-dev.service
```

## Branch out of sync?

If `development` and `main` have diverged (parallel commits on both sides), **do not** merge blindly. Follow the inventory and ordered plan in [SYNC.md](./SYNC.md):

1. Merge **main → development** first (integrate live-only work).
2. Resolve conflicts on an integration branch; test on dev.
3. Merge **development → main** to promote.

## systemd paths (confirmed)

- **Dev:** `WorkingDirectory=/home/ubuntu/gov-hub-dev`, `FLASK_PORT=8001`, `datatracker-dev.service`
- **Live (main):** `WorkingDirectory=/home/ubuntu/gov-hub-prod`, `FLASK_PORT=8000`, `datatracker.service`

> **Directory name:** `~/gov-hub-prod` is the live worktree path (historical name). It tracks git branch **`main`**, not a `production` branch.

## Git worktrees note

This server uses one repo with two worktrees (`gov-hub-dev` on `development`, `gov-hub-prod` on `main`). Only one worktree can check out a given branch at a time.
