# Gov Hub: development → production

## Branches

| Branch | Role | Server checkout | URL | systemd unit |
|--------|------|-----------------|-----|--------------|
| `development` | Day-to-day work | `/home/ubuntu/gov-hub-dev` | dev.govhub.live (8001) | `datatracker-dev.service` |
| `production` | Live release | `/home/ubuntu/gov-hub-prod` | govhub.live (8000) | `datatracker.service` |

Remote: `https://github.com/Bridgit-DAO/interface-gov-hub.git`

`legacy-main` on the remote preserves the old dev `main` history before `development` was aligned to `production` (2026-07). Do not merge the old 90-commit backlog into `development`.

## Daily work (dev)

```bash
cd ~/gov-hub-dev
git checkout development
git pull origin development
# ... edit, commit ...
git push origin development
systemctl --user restart datatracker-dev.service
```

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

After merging on `gov-hub-prod`, `gov-hub-dev` should `git pull origin development` if you also committed on prod only (normally you merge on prod and push `production`; keep `development` as the integration branch and merge **into** `production`).

## systemd paths (confirmed)

- **Dev:** `WorkingDirectory=/home/ubuntu/gov-hub-dev`, `FLASK_PORT=8001`, `datatracker-dev.service`
- **Prod:** `WorkingDirectory=/home/ubuntu/gov-hub-prod`, `FLASK_PORT=8000`, `datatracker.service`

## Quick health check

```bash
# Dev API should exist (401 without auth is OK; 404 means wrong code/deploy)
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://dev.govhub.live/api/metaweb/action-status -H 'Content-Type: application/json' -d '{"checks":[]}'
```

## Git worktrees note

This server uses one repo with two worktrees (`gov-hub-dev` on `development`, `gov-hub-prod` on `production`). Only one worktree can check out a given branch at a time.
