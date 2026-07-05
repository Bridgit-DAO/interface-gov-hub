# JAUmemory Records - MLTF Datatracker RFC Project

This file serves as a memory store for the MLTF Datatracker project. Key decisions, patterns, and learnings are documented here for future reference.

## Project Context

**Project**: MLTF Datatracker (RFC App)  
**Purpose**: Governance hub for Meta-Layer Task Force standards  
**Tech Stack**: Flask, SQLite, Bootstrap, systemd, Nginx  
**Environments**: Production (`rfc.themetalayer.org`), Development (`dev.rfc.themetalayer.org`)

## Current Architecture

### Deployment System (2026-01-17)

**Decision**: Implement agent-friendly CI/CD system  
**Rationale**: Previous deployment failures (code changes not appearing) require reliable, automated system  
**Status**: In progress

**Key Components**:
- Git workflow: `main` (prod) ← `dev` (dev) ← `feature/*` (temp)
- Deployment scripts: `deploy.py`, `verify.py`, `status.py`, `rollback.py`
- Testing framework: Unit, integration, E2E tests
- Database migrations: Manual SQL + Alembic (future)

**Pattern**: Environment-based configuration
- Use `FLASK_ENV` to determine environment
- Separate databases: `instance/datatracker.db` (prod), `instance_dev/datatracker_dev.db` (dev)
- Separate ports: 8000 (prod), 8001 (dev)
- Separate systemd services: `datatracker.service`, `datatracker-dev.service`

## Key Patterns

### Pattern: Environment-based Configuration
**Use Case**: Different settings for dev/prod  
**Implementation**: 
```python
ENV = os.environ.get('FLASK_ENV', 'production').lower()
if ENV == 'development':
    INSTANCE_DIR = 'instance_dev'
    DB_NAME = 'datatracker_dev.db'
    PORT = 8001
    DEBUG = True
else:
    INSTANCE_DIR = 'instance'
    DB_NAME = 'datatracker.db'
    PORT = 8000
    DEBUG = False
```
**Benefits**: Same codebase, different behavior. Easy to switch environments.  
**Location**: `ietf_data_viewer_simple.py` lines 89-104

### Pattern: Safe Migration
**Use Case**: Deploy new systems without breaking production  
**Implementation**:
1. Create backups (database, service files, git state)
2. Tag production state in git
3. Create dev branch
4. Implement in dev branch only
5. Test thoroughly in dev
6. Merge to main when ready
**Benefits**: Zero-risk deployment, easy rollback  
**Location**: `SAFE_MIGRATION_PLAN.md`, `safe-migration.sh`

### Pattern: Time-based Permissions
**Use Case**: Allow edit/delete within time window  
**Implementation**: Check `edited_at` timestamp, compare to current time  
**Example**: Comment edit/delete within 15 minutes  
**Location**: `can_edit_delete_comment()` function

### Pattern: Soft Delete
**Use Case**: Preserve data while marking as deleted  
**Implementation**: `is_deleted` boolean flag, store `original_text`  
**Benefits**: Audit trail, can restore if needed  
**Location**: `Comment` model

## Common Issues and Solutions

### Issue: Code changes not appearing after deployment
**Symptoms**: Changes in file but not visible in browser  
**Cause**: Python cache (.pyc files) or service not restarting properly  
**Solution**: 
1. Clear `__pycache__` directories: `find . -type d -name __pycache__ -exec rm -r {} +`
2. Kill processes: `ps aux | grep python | grep PORT | awk '{print $2}' | xargs kill -9`
3. Restart service: `systemctl --user restart datatracker-dev.service`
**Prevention**: Always use `deploy.py` script which clears cache automatically  
**Date**: 2026-01-17

### Issue: Flask reloader hanging in systemd
**Symptoms**: Service starts but hangs, no response  
**Cause**: Flask's debug reloader conflicts with systemd  
**Solution**: Disable reloader when `INVOCATION_ID` (systemd env var) is present:
```python
use_reloader = DEBUG and not os.environ.get('INVOCATION_ID')
app.run(use_reloader=use_reloader)
```
**Prevention**: Always check for systemd environment  
**Date**: 2026-01-17

### Issue: Database schema out of sync
**Symptoms**: `OperationalError: no such column: X`  
**Cause**: Model changed but database not migrated  
**Solution**: 
1. Add column manually: `ALTER TABLE table_name ADD COLUMN column_name TYPE;`
2. Or recreate: `db.drop_all()` then `db.create_all()` (loses data!)
**Prevention**: Use proper migrations (Alembic planned)  
**Date**: 2026-01-17

### Issue: Development environment not updating
**Symptoms**: Code changes not visible in dev, despite restarts  
**Cause**: Multiple issues - cache, wrong branch, service not restarting  
**Solution**: Comprehensive fix script:
1. Kill all Python processes on port
2. Clear all cache
3. Verify git branch
4. Restart service
5. Test HTTP response
**Prevention**: Use reliable deployment script with verification  
**Date**: 2026-01-17

## Feature Implementations

### Feature: Comment Edit/Delete
**Purpose**: Allow users to edit/delete their own comments within 15 minutes  
**Implementation**: 
- Added `edited_at`, `is_deleted`, `original_text` columns to `Comment` model
- Added `can_edit_delete_comment()` function
- Added routes `/doc/draft/<draft_name>/comments/<comment_id>/edit` and `/delete`
- Updated `render_comment_tree()` to show Edit/Delete buttons conditionally
**Components**: `ietf_data_viewer_simple.py` (Comment model, routes, render_comment_tree)  
**Patterns**: Time-based permission check, soft delete pattern  
**Lessons**: Need to check both author and time limit. Store original_text for audit.  
**Related**: Comment system, User permissions  
**Date**: 2026-01-17

### Feature: ML Number Assignment
**Purpose**: Assign sequential ML numbers (ML-001, ML-002, ..., ML-999, ML-1000+)  
**Implementation**: 
- Added `ml_number` column to `Submission` model
- Created `get_next_ml_number()` function
- Format: `ML-{num:03d}` for 1-999, `ML-{num:04d}` for 1000+
- Assigned on approval: `approve_submission()` calls `get_next_ml_number()`
**Components**: `ietf_data_viewer_simple.py` (Submission model, get_next_ml_number, approve_submission)  
**Patterns**: Sequential ID generation  
**Lessons**: Format changes at 1000 to accommodate growth  
**Date**: 2026-01-17

### Feature: Document Follow System
**Purpose**: Allow users to follow drafts and receive in-app (and optional email) notifications for governance events on that draft.  
**Implementation** (current):
- **`UserEventSubscription`** (`user_event_subscription`): one row per `(user_id, event_type, subject_type, subject_id)` with `deliver_in_app` / `deliver_email`. Draft follows use `subject_type='draft'`, `subject_id=<draft_name>`, and event types such as `draft_comment_added`, `draft_submission_approved`, `draft_revision_approved`, `draft_published_as_rfc`.
- Legacy **`user_follow`** was migrated away (`migrate_user_follow_to_event_subscriptions`); preset **notification levels** expand to the right set of `event_type` rows via `services/event_subscriptions.py` (`replace_draft_subscriptions`, `LEVEL_TO_EVENT_TYPES`, `infer_draft_notification_level`).
- **Dispatch**: `services/document_follow_notifications.py` – `dispatch_document_followers(..., event_type=...)` loads subscribers by exact `event_type` + draft subject; respects subscription channels and layer email unsubscribe.
- **Routes**: `routes/documents.py` – follow / unfollow / update level call `replace_draft_subscriptions`; new comments/replies dispatch with `event_type='draft_comment_added'`; submission approvals / revisions / RFC publish use `services/submission_notifications.py` (`draft_submission_approved`, `draft_revision_approved`, `draft_published_as_rfc`).
**UI note**: The draft page still uses a **single notification-level dropdown** (presets: all / significant / major / comments / none), not per-event toggles. The database stores **one subscription row per event type**; presets only control which rows are created. A per-event UI would match mental model to storage and allow arbitrary combinations, at the cost of more controls and implementation work; the preset keeps the draft page simple while dispatch stays exact-match on `event_type`.
**Components**: `models/identity.py`, `services/event_subscriptions.py`, `services/document_follow_notifications.py`, `routes/documents.py`  
**Patterns**: Event-sourced notifications (`EventLog`), explicit subscriptions  
**Date**: 2026-01-17 (original follow); 2026-04 (subscriptions migration)

### Feature: Environment Separation
**Purpose**: Separate development and production environments  
**Implementation**: 
- Environment-based config using `FLASK_ENV`
- Separate databases, ports, systemd services
- Separate Nginx configs
- SSL certificates for both domains
**Components**: `ietf_data_viewer_simple.py`, systemd services, Nginx configs  
**Patterns**: Environment-based configuration  
**Lessons**: Critical for safe development and testing  
**Date**: 2026-01-17

## Database Patterns

### Pattern: ML Number Format
**Use Case**: Sequential document numbering  
**Format**: `ML-001` to `ML-999`, then `ML-1000`+  
**Query**: `SELECT MAX(ml_number) FROM submission WHERE ml_number IS NOT NULL`  
**Migration**: Added column, assigned `ML-0001` to existing approved submission  
**Date**: 2026-01-17

### Pattern: Comment Tree Structure
**Use Case**: Nested comments/replies  
**Schema**: `Comment` table with `parent_id` foreign key  
**Query**: Recursive query or Python tree building  
**Implementation**: `render_comment_tree()` builds tree structure  
**Date**: 2026-01-17

## API Patterns

### Pattern: Deployment Status Endpoint
**Route**: `/_deploy/status`  
**Method**: GET  
**Auth**: None (dev only)  
**Response**: JSON with deployment info, git commit, timestamp  
**Purpose**: Verify deployment, check what code is running  
**Date**: 2026-01-17

### Pattern: Deployment Reload Endpoint
**Route**: `/_deploy/reload`  
**Method**: POST  
**Auth**: None (dev only)  
**Response**: JSON with status  
**Purpose**: Clear cache and reload (dev only)  
**Date**: 2026-01-17

## Deployment Decisions

### Decision: Two-Branch Git Workflow
**Context**: Need to test changes before production  
**Alternatives**: Single branch, feature branches, GitFlow  
**Chosen**: `main` (prod) ← `dev` (dev) ← `feature/*` (temp)  
**Rationale**: Simple, clear separation, easy rollback  
**Date**: 2026-01-17

### Decision: Manual Database Migrations (for now)
**Context**: Need schema changes but no migration system  
**Alternatives**: Alembic, Flask-Migrate, manual SQL  
**Chosen**: Manual SQL + `db.create_all()` for new installs  
**Rationale**: Simple for now, plan to add Alembic later  
**Date**: 2026-01-17

### Decision: Python-based Deployment Scripts
**Context**: Need reliable, agent-friendly deployment  
**Alternatives**: Bash scripts, Makefile, CI/CD service  
**Chosen**: Python scripts (`deploy.py`, `verify.py`, etc.)  
**Rationale**: Better error handling, structured output, easier for agents  
**Date**: 2026-01-17

## Testing Patterns

### Pattern: HTTP Response Testing
**Use Case**: Verify service is responding  
**Implementation**: `requests.get(url)` check status code  
**Location**: `verify.py` (planned)

### Pattern: Content Verification
**Use Case**: Verify specific content appears  
**Implementation**: `response.text` contains expected string  
**Location**: `verify.py` (planned)

### Pattern: API Endpoint Testing
**Use Case**: Verify all routes work  
**Implementation**: Test each route, check response format  
**Location**: `tests/integration/test_api_routes.py` (planned)

## Current Work / Thread Handoff (2026-02-12)

**Purpose**: Log progress for pickup in another thread.

**Recently completed**:
- **Waitlist feature**: Waitlist/WaitlistEntry/WaitlistMilestone models; APIs (list/create/get/join/leave/entries/update/milestones); project detail Waitlists tab with flair, join/position/referral link/milestones; URL hash `#waitlist` and `#waitlist-<id>`; Create Waitlist modal for project admins. Referral URLs use `?ref=CODE#waitlist-<id>`.
- **Waitlist model fix**: SQLAlchemy backref name clash–`Waitlist` has column `milestones` (bool) and relationship was also named `milestones`. Renamed relationship backref to `milestone_list`; all usages updated (`api_get_waitlist`, `api_list_waitlist_milestones`, `api_list_waitlists`). List API now exposes `d['milestones']` as array of milestone dicts for UI.
- **Service**: `datatracker-dev.service` was failing with exit-code; fixed by above; service runs on port 8001 (build 264).

**Resolved issues (2026-02-12 & 2026-02-13)**:
- **JavaScript syntax error in embed button** (Build 280+): Fixed nested template literal issue
  - **Root cause**: Used backticks for nested template literal inside an existing template literal, causing "Unexpected token '}'" error
  - **Solution**: Changed from nested template literal to string concatenation
  - **Before**: `` ${isProjectAdmin ? `<button onclick="showEmbedCode(${wl.id})">` : ''} `` (nested backticks - INVALID)
  - **After**: `${isProjectAdmin ? '<button onclick="showEmbedCode(' + wl.id + ', this.dataset.wlName)" data-wl-name="' + wl.name + '">' : ''}` (string concat - VALID)
  - Uses data attribute (`data-wl-name`) to pass waitlist name, avoiding quote escaping entirely
- **Projects page loading**: Investigated projects page JavaScript. The page structure is correct:
  - `loadProjects()` function is properly defined as async
  - Function is called on page load
  - API endpoint `/api/projects/` returns valid JSON
  - Error handling is in place
  - No CSP headers are being sent by Flask in dev environment
  - JavaScript validation shows no syntax errors
  - Likely was a transient browser issue or has been resolved
  
**New features added (2026-02-12)**:
- **Waitlists directory page**: Created `/waitlists/` route with full directory listing
  - Filters by project and status (active/upcoming/closed)
  - Search functionality
  - Shows waitlist status badges (active, upcoming, full, closed)
  - Displays referral and milestone indicators
  - Links to project detail pages with waitlist hash anchors
- **Home page waitlist card**: Added waitlist card to home page in the last row with Role Images
- **Navigation menu**: Added "Waitlists" link to main navbar between "Imagery" and "Docs"
- **Embeddable waitlist widget**: Full embed functionality for external websites
  - New endpoint: `/embed/waitlist/<id>/` - standalone HTML widget
  - Beautiful gradient design with stats display
  - Automatic source tracking (domain and full URL)
  - Database migration: Added `source` and `source_url` columns to `waitlist_entry` table
  - Join API updated to accept and store source information
  - Embed code generator in project admin UI with "Get Embed Code" button
  - Modal shows both iframe code and direct URL
  - One-click copy functionality
  - X-Frame-Options: ALLOWALL header for iframe embedding
  - Signups tracked with format: `source: 'embed:example.com'`, `source_url: 'https://example.com/page'`

**Key file**: `ietf_data_viewer_simple.py` – route `@app.route('/projects/')` (projects_directory), function `loadProjects()` in same template, API `GET /api/projects/`.

---

## Refactor and Plan Position (2026-02-12)

**Purpose**: Log refactor done and current position for JAUmemory / handoff.

**Refactor completed**:
1. **Git remote**: Changed from `Bridgit-SPC/datatracker` to **https://github.com/Bridgit-DAO/interface-gov-hub** for both `gov-hub-dev` and `gov-hub-prod`.
2. **Pre-commit hook**: Duplicate Flask route check was using `cut -d: -f2`, which truncated routes with colons (e.g. `<int:waitlist_id>`) and caused false positives. Switched to `sed 's/^[0-9]*://'` to strip only the leading line number so the full route string is compared.
3. **Commit and push**: Committed and pushed to `dev` (commit `9615cb9a1`): Votes UI/API, Create Vote modal, project submissions filter, timezone defaults, docs (DEPLOYMENT-CHECKLIST, SUBMISSION_PROJECT_LINK, nginx config), migration script; 9 files changed.

**Where we are**:
- **Repo layout**: `gov-hub-dev` (branch `dev`, port 8001), `gov-hub-prod` (branch `main`). Latest `dev` pushed to **interface-gov-hub**.
- **In place**: `project_id` on Submission; project detail **Votes** tab with Create Vote button; Create Vote modal (submission dropdown, start/end times with timezone, quorum, threshold); submissions API filtered by `project_id`, `status=approved`, `doc_type=draft`; layer selector on submit form; default vote times (next hour + 7 days).
- **Open issue**: Create Vote POST can return 500; client may show "body disturbed"; server `api_create_vote` may need debugging.
- **Plan**: **PLANNING_SUMMARY.md** – Projects/Workgroups/Guilds RFC is in planning phase (branch `feature/projects-workgroups-guilds`); implementation not started. Current active work is **Votes** and project-detail flows on dev.

---

## Current Work (2026-01-17)

**Feature**: Agent Deployment System  
**Status**: ✅ Phase 1 Complete - Core deployment system implemented  
**Branch**: `dev`  
**Components**: 
- ✅ `deploy.py` - Main deployment script (complete)
- ✅ `verify.py` - Verification script (complete)
- ✅ `status.py` - Status checking (complete)
- ✅ `rollback.py` - Rollback capability (complete)
- ✅ Enhanced `/_deploy/status` endpoint (complete)
- ✅ New `/_deploy/health` endpoint (complete)
- ⏳ `tests/` - Test framework (planned for Phase 2)

**Implementation Details**:
- All scripts output JSON for agent parsing
- Proper exit codes (0=success, 1=failure)
- Comprehensive logging to `/tmp/deploy-*.log`
- Automatic backups for production deployments
- Git tag creation for production deployments
- Service health checks and HTTP verification

**Next Steps**:
1. ✅ Test deployment system in dev environment
2. ⏳ Add comprehensive test framework (Phase 2)
3. ⏳ Add database migration system (Phase 3)
4. ⏳ Migrate to production when ready

## Important Notes

- **Production Safety**: Always backup before changes
- **Git Tags**: Tag production state before major changes
- **Environment**: Always check `FLASK_ENV` before operations
- **Cache**: Always clear Python cache on deployment
- **Service**: Always restart service after code changes
- **Verification**: Always verify after deployment

## Remaining Tasks (2026-03-12)

**Purpose**: Consolidated list of planned work for Gov Hub. Logged to JAUmemory (project: gov-hub). Memory ID: `1c1c290d-474c-49bd-a120-1c4884a61da6`

**Full list**: See `GOV_HUB_REMAINING_TASKS.md` – complete DONE vs REMAINING with progress.

### Architecture & Refactor

| Task | Source | Status | Notes |
|------|--------|--------|-------|
| **Modularization** | GOV-HUB-3 Phase 0.2 | Not started | Extract `ietf_data_viewer_simple.py` (~28k lines) into domain modules: `models/` (identity, artifact, coordination, events), `services/`, `routes/`, `events/`. Single file → modular structure. |
| **New navigation** | GOV-HUB-2 | Not started | Restructure top nav to GOV-HUB-2 IA: Home \| Contribute \| Governance \| Community \| Recognition \| Learn. Current: Layers, Roles, Workgroups, Guilds, People, Waitlists, Badges, Docs, Submit, Immortalize. |
| **Localization (i18n)** | PLANNING_FULL_PICTURE | Planned (last) | Interface strings, date/number formatting, RTL if needed. Add Flask-Babel or similar. |

### Governance & Features

| Task | Source | Status | Notes |
|------|--------|--------|-------|
| **Randomized ballot order** | Phase 2.4 | ✅ Done | `ballot_order_seed` on Vote; _election_candidates_ordered() deterministic shuffle. |
| **Multi-seat clarity** | Phase 2.4 | ✅ Done | seats, "Elect up to N", "Winners (top N)"; close_vote excludes withdrawn from winners. |
| **Candidate withdrawal** | Phase 2.4 | ✅ Done | POST .../candidates/<id>/withdraw/; "Your Candidacy" card with Withdraw button; close_vote excludes withdrawn. |
| **Meta-domain for Layer** | PLANNING_FULL_PICTURE | ✅ Done | `Layer.meta_domain_inscription_id`, `Layer.meta_domain`; Edit Layer modal; fetch_meta_domain_from_inscription + get_last_inscription_for_sat. |
| **Vote.artifact_id** | GOV-HUB-3 | Not done | Add `artifact_id` to Vote; keep `submission_id` during transition. |
| **Layer resolution middleware** | GOV-HUB-3 Phase 1.1 | Not done | Host → Layer context; subdomain/path routing. |

### Migration (Deferred)

| Task | Source | Status | Notes |
|------|--------|--------|-------|
| **Full UUID PK migration** | Phase 6 | Deferred | User, Layer, Submission, etc. int/string → UUID. Large; schedule maintenance window. Skipped per user request for now. |

### Recently Completed (2026-03-15)

- **Modularization Phase A+B+C**: Models to models/; services/utils, ordinals, events; routes/deploy blueprint (_deploy/reload, status, health, test)
- **Meta-domain for Layer**: Layer.meta_domain_inscription_id, meta_domain; Edit Layer modal; fetch_meta_domain_from_inscription + get_last_inscription_for_sat
- **Randomized ballot order**: ballot_order_seed on Vote; _election_candidates_ordered() deterministic shuffle
- **Multi-seat clarity**: seats, "Elect up to N", "Winners (top N)"; close_vote excludes withdrawn from winners
- **Candidate withdrawal**: POST /api/votes/.../candidates/<id>/withdraw/; "Your Candidacy" card with Withdraw button; close_vote excludes withdrawn

### Previously Completed (2026-03-12)

- **Artifact spec**: public_ref, short ref resolution (ed3f6ea9io), lineage API + graph, status lifecycle badges, artifact_status_changed EventLog
- **Artifacts nav**: Artifacts tab on layer page, GET /api/layers/<id>/artifacts/, loadArtifacts()
- **Activity feed**: artifact_updated, artifact_status_changed, artifact_linked events link to Artifacts tab

---

## References

- `GOV_HUB_REMAINING_TASKS.md` - Full task list with progress (source for JAUmemory)
- `SAFE_MIGRATION_PLAN.md` - Migration strategy
- `IMPLEMENTATION_ROADMAP.md` - Detailed implementation plan
- `AGENT_DEPLOYMENT_PLAN.md` - High-level architecture
- `JAUmemory_INTEGRATION.md` - How to use JAUmemory
- `PLANNING_FULL_PICTURE.md` - Consolidated planning, sequencing
- `GOV-HUB-3.md` - Canonical architecture
- `artifact_specification.md` - Artifact model spec
