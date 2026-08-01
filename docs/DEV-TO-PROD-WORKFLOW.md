# Gov Hub: development → production

## Branches

| Branch | Role | Server checkout | URL | systemd unit |
|--------|------|-----------------|-----|--------------|
| `development` | Integration & testing | `/home/ubuntu/gov-hub-dev` | dev.hub.themetalayer.org (8001) | `datatracker-dev.service` |
| `production` | Live release | `/home/ubuntu/gov-hub-prod` | hub.themetalayer.org (8000) | `datatracker.service` |

Remote: `https://github.com/Bridgit-DAO/interface-gov-hub.git`

`legacy-main` on the remote preserves the old dev `main` history before `development` was aligned to `production` (2026-07). Do not merge the old 90-commit backlog into `development`.

## Process rules (required)

1. **All feature work lands on `development`.** Do not commit features directly to `production`.
2. **Test on dev before every promote.** Use port 8001 / `dev.hub.themetalayer.org` and the pre-promote checklist below.
3. **Promote to production** only by merging `development` into `production` (locally on `gov-hub-prod` or via GitHub PR).
4. **Hotfixes on production** are allowed when prod is broken and dev cannot wait—but **backport to `development` the same day** (cherry-pick or merge `production` → `development`).
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

Complete on `gov-hub-dev` **before** merging to `production`:

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

## Ship to production

```bash
cd ~/gov-hub-prod
git fetch origin
git checkout production
git pull origin production
git merge origin/development -m "ship: merge development to production"
git push origin production
systemctl --user restart datatracker.service
```

After promote, confirm prod health and keep branches aligned:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://govhub.live/
cd ~/gov-hub-dev && git pull origin development   # if hotfix was prod-only, merge prod→dev instead
```

## Hotfix workflow (production emergency)

```bash
# 1. Fix on production (minimal diff)
cd ~/gov-hub-prod
git checkout production
# ... fix, commit ...
git push origin production
systemctl --user restart datatracker.service

# 2. Backport to development same day
cd ~/gov-hub-dev
git checkout development
git pull origin development
git cherry-pick <hotfix-commit>   # or: git merge origin/production
git push origin development
systemctl --user restart datatracker-dev.service
```

## Branch out of sync?

If `development` and `production` have diverged (parallel commits on both sides), **do not** merge blindly. Follow the inventory and ordered plan in [SYNC.md](./SYNC.md):

1. Merge **production → development** first (integrate live-only work).
2. Resolve conflicts on an integration branch; test on dev.
3. Merge **development → production** to promote.

## systemd paths (confirmed)

- **Dev:** `WorkingDirectory=/home/ubuntu/gov-hub-dev`, `FLASK_PORT=8001`, `datatracker-dev.service`
- **Prod:** `WorkingDirectory=/home/ubuntu/gov-hub-prod`, `FLASK_PORT=8000`, `datatracker.service`

## Git worktrees note

This server uses one repo with two worktrees (`gov-hub-dev` on `development`, `gov-hub-prod` on `production`). Only one worktree can check out a given branch at a time.
