# Production Migration: Remaining Dev Changes

## Overview

**Purpose:** Deploy the latest dev changes to production.  
**Scope:** Code only; no database schema changes.  
**Target commit:** `259a9c6a8` (and any later dev commits before you run this).

## What’s in This Migration

- **People table**
  - Search (live filter by name/username).
  - Workgroup dropdown filter.
  - Role column visible only to editor/admin.
  - “Add as coordinator” (Actions) only for admin.
  - Comments column (site document comments count).
  - Member column; “Coordinator for” renamed to “Coordinator”.
- **UI / fixes**
  - Navbar and dropdown z-index adjusted so the user dropdown stays usable (collapse on production, dropdown on dev).
  - Consistent page wrapping via `render_page()` where applicable (People, Add as coordinator, Meetings).
- **Script**
  - `simple-restart-production.sh` for restarting the production service.

## Pre-Migration Checklist

- [ ] Dev is tested and acceptable (People search/filter, Role/Actions visibility).
- [ ] Production is currently stable on the previous deploy.
- [ ] You have access to the production host and can run `git` and `systemctl --user` (or your production restart method).

## Migration Steps

### 1. On production host: fetch and merge dev

```bash
cd /home/ubuntu/datatracker
git fetch origin
git checkout main
git merge dev --no-edit
```

Resolve any merge conflicts if they appear; then ensure the app still runs (e.g. run tests or a quick smoke check).

### 2. Restart production (use the new script)

```bash
cd /home/ubuntu/datatracker
./simple-restart-production.sh
```

This restarts `datatracker.service` (port 8000). If your production restart is different (e.g. system `systemctl`, Docker, or k8s), use that instead; the important step is that production runs the new code.

### 3. Push main (optional)

If you use `main` as the record of what’s in production:

```bash
git push origin main
```

### 4. Verify

- [ ] Open production site (e.g. https://rfc.themetalayer.org).
- [ ] Confirm build/version if shown (e.g. Build 74 or higher).
- [ ] **People:** Open People, use search and workgroup filter; confirm Role only for editor/admin and “Add as coordinator” only for admin; check Comments column.

## Rollback

If something is wrong:

```bash
cd /home/ubuntu/datatracker
git checkout main
git reset --hard origin/main   # or the commit hash that was live before this migration
./simple-restart-production.sh
```

Then fix issues on dev and re-run this migration when ready.

## Database

No DB migrations are required for this batch. All changes are in application code and static assets. Existing tables (including `user`, `comment`, `working_group_member`, `working_group_chair`, etc.) are already used as-is.

## Summary

| Step | Action |
|------|--------|
| 1 | On production: `git fetch origin && git checkout main && git merge dev` |
| 2 | Restart production: `./simple-restart-production.sh` (or your normal restart) |
| 3 | Optionally push `main`: `git push origin main` |
| 4 | Verify People page and build |

Estimated time: about 5 minutes.
