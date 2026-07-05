# UUID Migration Complete

**Date:** 2026-03-12  
**Phase:** 2 & 3 of UUID + Layer Migration Plan (GOV-HUB-3)

## Summary

Added `public_id` (UUID) to all major entities. Canonical UUID-based URLs now work.

## What Was Done

### 1. Migration Script (`migrate_uuid.py`)

- Adds `public_id` column to: claim, role, working_group, role_image, cluster, badge_cycle, one_time_badge, guild, ballot
- Backfills existing rows with UUIDs
- Creates unique indexes
- Backs up DB before running

**Run:** `python migrate_uuid.py [--dry-run] [--db path]`

### 2. Model Updates

- **Cluster, Role, Claim, Workgroup, RoleImage**: Added `public_id` column (nullable, unique, default=uuid4)
- **to_dict()**: Included `public_id` in serialization for Role, Claim, Cluster, Workgroup

### 3. Canonical UUID Routes

| Route | Resolves | Redirects to |
|-------|----------|--------------|
| `/p/<public_id>` | User | User profile |
| `/layer/<public_id>` | Layer | Layer detail |
| `/draft/<public_id>` | Submission | Draft detail |
| `/vote/<public_id>` | Vote | Vote detail |
| `/role/<public_id>` | Role | Role detail |
| `/claim/<public_id>` | Claim | Role detail |
| `/badge/<public_id>` | Badge | Role detail |

### 4. API Support for UUID Lookup

- `GET /api/claims/<id>/` – accepts claim id or public_id UUID
- `GET /api/roles/<id>/` – accepts role id or public_id UUID
- `GET /api/badges/<id>/` – accepts badge id or public_id UUID

### 5. Startup Migration

- Extended `public_id` migration (in `ietf_data_viewer_simple.py` ~line 370) to include: vote, claim, role, working_group, role_image, cluster, badge_cycle, one_time_badge, guild

## Tables with public_id

- user, layer, submission, badge, vote (already had)
- claim, role, working_group, role_image, cluster, badge_cycle, one_time_badge, guild, ballot (added)

## Next Steps (Optional)

Full UUID primary key migration (int/string → UUID) per GOV-HUB-3 Phase 2 would require:

1. Recreate tables with UUID PKs
2. Migrate all data
3. Update all FK references

Deferred to a later phase. Current `public_id` approach provides UUID-based URLs and API compatibility without breaking existing PKs.
