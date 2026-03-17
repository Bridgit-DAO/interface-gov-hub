# Gov Hub — Modularization Spec

**Purpose:** File-by-file extraction plan for splitting `ietf_data_viewer_simple.py` (~29k lines) into domain modules.  
**Source:** GOV-HUB-3 Phase 0.2, GOV_HUB_REMAINING_TASKS.md  
**Principle:** Routes call services. Services own logic and emit events. Models define shape only.

---

## Target Structure (Python/Flask)

```
gov-hub-dev/
  app.py                    # Entry point: create_app(), register blueprints, init db
  config.py                 # Config, env vars
  extensions.py             # db, migrate, etc.

  models/
    __init__.py             # Import all, expose for db.create_all()
    identity.py             # User, UserFollow, HypothesisAccount
    artifact.py             # Submission, Artifact, ArtifactRelation, Comment, DocumentHistory
    coordination.py        # Layer, LayerMember, LayerAdmin, Workgroup, Guild, Cluster, Role, Claim, Badge, Vote, Ballot, etc.
    events.py              # EventLog, StatusChange

  services/
    __init__.py
    identity.py             # get_current_user, auth helpers, referral codes
    artifact.py             # get_artifact_by_ref, _ensure_artifact_for_submission, ordinal helpers
    coordination.py        # is_layer_admin, activate_vote, close_vote, _election_candidates_ordered
    events.py              # emit_event
    ordinals.py             # get_last_inscription_for_sat, fetch_meta_domain_from_inscription, _ordinals_fetch_json
    utils.py                # create_slug, generate_*_id, allowed_file, etc.

  routes/
    __init__.py
    auth.py                 # login, logout, register, web3auth, api/user/me
    layers.py               # /api/layers/, /layers/, layer detail
    workgroups.py           # /api/workgroups/, /api/layers/<id>/workgroups/
    guilds.py               # /api/guilds/
    roles.py                # /api/roles/, /api/clusters/, claims, badges
    votes.py                # /api/votes/, /vote/<id>/
    artifacts.py            # /api/artifacts/, lineage, support/opposition
    waitlists.py            # /api/waitlists/, /embed/waitlist/
    submissions.py          # /submit/, /api/submissions/, /admin/submissions/
    documents.py            # /doc/draft/, /doc/active/, comments, follow
    ordinals.py             # /api/ordinal/, /api/inscribe/, /api/inscription/
    admin.py                # /admin/*, chair nominations, coordinator requests
    pages.py                # /, /profile/, /my-layers/, directory pages
    deploy.py               # /_deploy/status, /_deploy/reload
```

---

## Model → File Mapping

| Model | Target File | Notes |
|-------|-------------|-------|
| User | models/identity.py | |
| UserFollow | models/identity.py | |
| HypothesisAccount | models/identity.py | |
| Submission | models/artifact.py | |
| SiteConfig | models/artifact.py | Or config.py |
| InscriptionOrder | models/artifact.py | Ordinal wizard |
| Comment | models/artifact.py | |
| DocumentHistory | models/artifact.py | |
| Artifact | models/artifact.py | |
| ArtifactRelation | models/artifact.py | |
| Layer | models/coordination.py | |
| LayerMember | models/coordination.py | |
| LayerAdmin | models/coordination.py | |
| Waitlist | models/coordination.py | |
| WaitlistEntry | models/coordination.py | |
| WaitlistMilestone | models/coordination.py | |
| EmailUnsubscribe | models/coordination.py | |
| WaitlistEmailSignup | models/coordination.py | |
| Workgroup | models/coordination.py | |
| WorkingGroupMember | models/coordination.py | |
| WorkingGroupChair | models/coordination.py | |
| CoordinatorRequest | models/coordination.py | |
| WorkgroupMemberRequest | models/coordination.py | |
| Guild | models/coordination.py | |
| GuildMembership | models/coordination.py | |
| GuildInvitation | models/coordination.py | |
| Cluster | models/coordination.py | |
| Role | models/coordination.py | |
| RoleImage | models/coordination.py | |
| RoleImageVote | models/coordination.py | |
| Claim | models/coordination.py | |
| Badge | models/coordination.py | |
| BadgeSkin | models/coordination.py | |
| BadgeCycle | models/coordination.py | |
| OneTimeBadge | models/coordination.py | |
| Vote | models/coordination.py | |
| VoteEligibilitySnapshot | models/coordination.py | |
| VoteCandidate | models/coordination.py | |
| Ballot | models/coordination.py | |
| Quest | models/coordination.py | |
| QuestSubmission | models/coordination.py | |
| Monument | models/coordination.py | |
| StatusChange | models/events.py | |
| EventLog | models/events.py | |

---

## Route → Blueprint Mapping

| Route Prefix / Pattern | Blueprint | Notes |
|------------------------|-----------|-------|
| /login, /logout, /register | auth | |
| /api/auth/*, /api/user/me, /api/user/display-name | auth | |
| /api/ordinal/*, /api/inscribe/*, /api/inscription/*, /immortalize/, /inscribe/ | ordinals | ✓ extracted |
| /api/layers/* | layers | Main layer CRUD, activity, members |
| /layers/, /layer/<ref> | layers | Page routes |
| /api/layers/<id>/workgroups/, /api/workgroups/* | workgroups | |
| /api/guilds/* | guilds | |
| /api/layers/<id>/clusters/, /api/clusters/* | roles | |
| /api/layers/<id>/roles/, /api/roles/* | roles | |
| /api/claims/*, /api/badges/* | roles | |
| /api/role-images/*, /api/roles/<slug>/images/ | roles | |
| /api/one-time-badges/* | roles | |
| /api/layers/<id>/votes/, /api/votes/*, /votes/<id>/ | votes | ✓ extracted |
| /api/artifacts/*, /api/layers/<id>/artifacts/ | artifacts | |
| /api/layers/<id>/artifact-relations/ | artifacts | |
| /api/layers/<id>/opportunities/, quests, monuments | artifacts | |
| /api/layers/<id>/waitlists/, /api/waitlists/* | waitlists | |
| /embed/waitlist/* | waitlists | |
| /submit/*, /api/submissions/* | submissions | ✓ extracted |
| /admin/submissions/* | submissions | |
| /doc/draft/*, /doc/active/, /doc/all/ | documents | ✓ extracted |
| /admin/* | admin | ✓ extracted (submissions in submissions blueprint) |
| /, /profile/, /my-layers/, /p/<id>, /layer/<ref>, /draft/<id>, /vote/<id>, /role/<id>, /claim/<id>, /badge/<id> | pages | ✓ extracted |
| /roles/, /badges/, /workgroups/, /waitlists/, /guilds/ | pages | Directory pages (remaining) |
| /_deploy/* | deploy | |

---

## Service/Helper → File Mapping

| Function | Target | Notes |
|----------|--------|-------|
| get_current_user | services/identity.py | |
| require_auth, require_role | services/identity.py | Or middleware |
| generate_referral_code, get_or_create_referral_code | services/identity.py | |
| emit_event | services/events.py | |
| is_layer_admin | services/coordination.py | |
| activate_vote, close_vote | services/coordination.py | |
| _election_candidates_ordered | services/coordination.py | |
| get_artifact_by_ref | services/artifact.py | |
| _ensure_artifact_for_submission | services/artifact.py | |
| get_last_inscription_for_sat | services/ordinals.py | |
| fetch_meta_domain_from_inscription | services/ordinals.py | |
| _ordinals_fetch_json | services/ordinals.py | |
| create_slug | services/utils.py | |
| generate_*_id (layer, workgroup, guild, etc.) | services/utils.py | |
| allowed_file, allowed_image_file | services/utils.py | |
| get_submission_by_ref | services/artifact.py | |
| add_to_document_history | services/artifact.py | |
| build_comment_tree, render_comment_tree | services/artifact.py | |
| resolve_layer_from_host | middleware or services | |
| _format_base_template, render_page, generate_user_menu | templates/ or services | Shared rendering |

---

## Phased Execution (Minimize Blast Radius)

### Phase A: Extract models only (no route changes)
1. Create `models/` package with identity, artifact, coordination, events.
2. Move model classes from `ietf_data_viewer_simple.py` to respective files.
3. In main file, `from models import *` or `from models.identity import User, ...`.
4. Verify: app starts, all routes work, no import errors.

### Phase B: Extract services
1. Create `services/` package.
2. Move pure functions (no route decorators) to services. Handle circular imports via lazy import or dependency injection.
3. Update main file to import from services.
4. Verify: app starts, all routes work.

### Phase C: Extract routes into blueprints
1. Create `routes/` package, one blueprint per domain.
2. Move `@app.route` handlers to blueprint `@bp.route`.
3. In `app.py`, `app.register_blueprint(layers_bp, url_prefix='')` etc.
4. Verify: all URLs resolve, no 404s.

### Phase D: Create app.py entry point
1. Create `app.py` with `create_app()` factory.
2. Move Flask app creation, config, extensions init from main file.
3. Keep `ietf_data_viewer_simple.py` as thin wrapper that imports and runs, or switch entry to `app:app`.
4. Update `run.py`, `wsgi.py`, or systemd to use new entry.

### Phase E: Cleanup ✓
1. Remove dead code from original file. ✓
2. Delete `ietf_data_viewer_simple.py` — migrated to app.py, run.py. ✓
3. Scripts updated to import from app, extensions, models, database. ✓

---

## Dependency Order (Avoid Circular Imports)

```
models/events.py       (no model deps)
models/identity.py    (User, etc. — no coordination deps)
models/artifact.py   (may reference User, Layer)
models/coordination.py (references User, Layer, Artifact, EventLog)

services/events.py    (uses EventLog)
services/utils.py     (no db)
services/ordinals.py  (no db)
services/identity.py  (uses User)
services/artifact.py  (uses Artifact, Submission, User)
services/coordination.py (uses Vote, Layer, etc.)
```

Use `db` from `extensions.py` to avoid circular imports. Models import `db` from extensions; services receive `db` or import from app context.

---

## Verification Checklist

- [x] **Phase A (2026-03-15):** Models extracted to models/ package; extensions.py; app starts, migrations run
- [x] **Phase B (2026-03-15):** services/utils.py, services/ordinals.py, services/events.py; emit_event, create_slug, generate_*_id, ordinals helpers extracted
- [x] **Phase C (2026-03-15):** routes/deploy.py blueprint; /_deploy/reload, /_deploy/status, /_deploy/health, /_deploy/test
- [x] `python -c "from app import create_app; app = create_app(); print('OK')"` (Phase D complete)
- [x] All existing routes return expected status codes (curl / returns 200)
- [ ] No duplicate route definitions (pre-commit hook)
- [x] Database migrations still run (init_db, migrate_*)
- [x] Dev server starts: `FLASK_ENV=development python ietf_data_viewer_simple.py`
- [ ] Production deploy succeeds

---

## References

- GOV-HUB-3.md § 0.2
- GOV_HUB_REMAINING_TASKS.md
- JAUmemory_RECORDS.md
