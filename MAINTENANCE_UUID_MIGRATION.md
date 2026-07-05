# UUID Primary Key Migration – Maintenance Window

**Phase:** 6 + 7 (PLANNING_FULL_PICTURE.md)  
**Scope:** Full PK migration from int/string to UUID for all major entities. Phase 7 migrates remaining string(50) PK tables.

## Pre-Migration Checklist

- [ ] **Full backup** – Script creates timestamped backup automatically; also take external backup
- [ ] **Maintenance window** – Schedule downtime; migration can take several minutes
- [ ] **Stop application** – No writes during migration
- [ ] **Test on dev first** – Run full migration on dev DB, verify app works

## Running the Migration

```bash
# Dry run (no changes)
python migrate_uuid_pk.py --dry-run

# Full migration (creates backup first)
python migrate_uuid_pk.py

# Custom DB path
python migrate_uuid_pk.py --db /path/to/datatracker.db

# Run specific phase only (for debugging)
python migrate_uuid_pk.py --phase 1   # User only
python migrate_uuid_pk.py --phase 2   # Layer only
python migrate_uuid_pk.py --phase 3   # Submission only
python migrate_uuid_pk.py --phase 7   # BadgeSkin, BadgeCycle, OneTimeBadge, GuildInvitation, StatusChange (if 1–6 already run)
```

## Phases

| Phase | Tables | Notes |
|-------|--------|-------|
| 1 | User | int → UUID; updates all user_id FKs |
| 2 | Layer | string → UUID; updates all layer_id FKs |
| 3 | Submission | string(8) → UUID; updates submission_id FKs |
| 4 | Cluster, Role, Claim, Badge, Guild | string → UUID |
| 5 | Vote, Ballot, VoteEligibilitySnapshot, VoteCandidate | int → UUID |
| 6 | Remaining | Waitlist, Comment, VoteEligibilitySnapshot, VoteCandidate, RoleImage, Quest, LayerMember, LayerAdmin, WorkingGroup, GuildMembership, CoordinatorRequest, WorkgroupMemberRequest, UserEventSubscription, DocumentHistory, RoleImageVote, EventLog, QuestSubmission, Monument, WorkingGroupMember, WorkingGroupChair, ArtifactRelation, UserNotification |
| 7 | String(50) PKs | BadgeSkin, BadgeCycle, OneTimeBadge, GuildInvitation, StatusChange; RoleImage.layer_id, RoleImage.cycle_id → String(36) |

## Rollback

If migration fails or issues are discovered:

1. **Stop the application**
2. **Restore from backup:**
   ```bash
   cp /path/to/datatable_dev.db.backup_pre_uuid_pk_YYYYMMDD_HHMMSS /path/to/datatable_dev.db
   ```
3. **Restart application**
4. **Report** – Migration script does not support partial rollback; restore full backup

## Post-Migration

1. **Update SQLAlchemy models** – ✅ Done. `id` column types updated for User, Layer, Submission, Role, Claim, Badge, Cluster, Guild, Vote, Ballot. All `user_id`, `layer_id`, `role_id`, etc. FKs updated to `String(36)`.
   - `User.id`: `db.Integer` → `db.String(36)` or `db.Uuid`
   - `Layer.id`: `db.String(50)` → `db.String(36)`
   - `Submission.id`: `db.String(8)` → `db.String(36)`
   - All FK columns referencing these tables
2. **Update routes** – Any routes using integer/string IDs must accept UUID
3. **Update API** – Ensure API accepts UUID in paths
4. **Recreate indexes** – Migration drops tables; run `db.create_all()` or add index migration if needed
5. **Smoke test** – Login, view layers (workgroups count), submissions, votes, roles, claims, badges, waitlists (Members, Milestones), embed widget

6. **Submission/Layer creation** – Code that creates `Submission(id=submission_id, ...)` or `Layer(id=project_id, ...)` with short human-readable IDs must be updated: either omit `id` (let default UUID generate) or pass `id=str(uuid4())`. Use `draft_name`/`ml_number` for human-readable identifiers.

## Testing

```bash
# Use development DB (instance_dev/datatracker_dev.db) for testing
export FLASK_ENV=development

# 1. Start the app
python ietf_data_viewer_simple.py
# or: FLASK_APP=ietf_data_viewer_simple flask run

# 2. Smoke test (manual)
# - Login
# - View / (home)
# - View /layers/ (or /layers/<slug>/)
# - View /doc/draft/<id-or-draft_name>/ (use a submission UUID or draft_name)
# - View /submit/status/ (my submissions)
# - Create a new layer (API or UI)
# - Submit a draft

# 3. Quick DB check (UUID format)
python -c "
import sqlite3
conn = sqlite3.connect('instance_dev/datatracker_dev.db')
c = conn.cursor()
for t in ['user', 'layer', 'submission']:
    c.execute(f'SELECT id FROM {t} LIMIT 1')
    r = c.fetchone()
    print(f'{t}: {r[0][:36] if r else None} (len={len(r[0]) if r else 0})')
conn.close()
"

# 4. Test get_submission_by_ref (if app loads)
python -c "
from ietf_data_viewer_simple import app, get_submission_by_ref
with app.app_context():
    s = get_submission_by_ref('any-existing-uuid-or-draft_name')
    print('Found:', s.id if s else None)
"
```

## Requirements

- **SQLite 3.35+** – For `ALTER TABLE RENAME COLUMN` (used in some migrations)
- **Python 3.7+**

## References

- `PLANNING_FULL_PICTURE.md` – Phase 6 scope
- `GOV-HUB-3.md` – UUID + Layer Migration Plan
- `UUID_MIGRATION_COMPLETE.md` – Current public_id state (additive migration already done)
