# PublishedDraft Table Removal - BUILD 61

**Date:** 2026-02-09  
**Status:** ✅ Completed on dev, ready for production  
**Build:** 61

## Summary

Successfully removed the unused `PublishedDraft` table and unified the data model to use only the `Submission` table for tracking the full document lifecycle.

## Problem

The system had **two parallel data stores** for documents:
1. **`submission` table**: Where approved drafts actually lived (status='approved')
2. **`published_draft` table**: Intended for RFC-numbered documents but **unused (0 records)**

This caused:
- Confusion about the "source of truth"
- Duplicate code paths
- Admin dashboard showing incorrect counts (0 published drafts)
- Unnecessary complexity

## Solution

**Unified data model**: All documents now live in the `submission` table with their lifecycle tracked by the `status` field:
- `status='submitted'` - Initial submission
- `status='approved'` - Approved as ML-Draft
- `status='published'` - Becomes an ML-RFC (with `rfc_number`)
- `status='rejected'` - Rejected

## Changes Made

### 1. Database Schema
- ✅ Added `rfc_number INTEGER` column to `submission` table
- ✅ Removed `published_draft` table entirely

### 2. Code Changes
- ✅ Removed `PublishedDraft` model class (line 305-320)
- ✅ Removed startup code that loaded `PublishedDraft` into `DRAFTS` list (lines 83-101)
- ✅ Updated admin dashboard to count from `submission` table (line 4625)
- ✅ Updated `update_submission_status()` to store RFC data in `submission` table (lines 5428-5443)
  - Stores `rfc_number` directly in submission
  - Converts ML-Draft-XXX to ML-RFC-XXX format
  - Sets `doc_type='rfc'`

### 3. Migration Script
Created `migrate_remove_published_draft.py` which:
- Creates timestamped backup
- Adds `rfc_number` column to submission table
- Drops `published_draft` table
- Verifies changes

## Testing on Dev

✅ **Database migration successful**
- Backup created: `datatracker_dev.db.backup.remove_published_draft_20260209_011630`
- rfc_number column added
- published_draft table removed
- All existing data intact (4 submissions preserved)

✅ **Application working**
- Dev server restarted with BUILD 61
- Documents page loads correctly
- Admin dashboard accessible
- No errors in logs

## Production Migration Plan

### Prerequisites
1. ✅ Code changes committed to dev branch
2. ✅ Migration script tested on dev
3. ✅ Backup strategy confirmed

### Steps

1. **Backup production database**
   ```bash
   cd /home/ubuntu/datatracker/instance
   cp datatracker.db datatracker.db.backup.pre_build61_$(date +%Y%m%d_%H%M%S)
   ```

2. **Merge dev to main**
   ```bash
   git checkout main
   git merge dev
   ```

3. **Run migration script**
   ```bash
   python3 migrate_remove_published_draft.py /home/ubuntu/datatracker/instance/datatracker.db
   ```

4. **Restart production server**
   ```bash
   systemctl --user restart datatracker.service
   ```

5. **Verify**
   - Check BUILD 61 is live
   - Verify documents page loads
   - Check admin dashboard shows correct counts
   - Test document detail pages

### Rollback Plan

If issues arise:
```bash
cd /home/ubuntu/datatracker
git checkout main
git reset --hard <previous-commit>
cp instance/datatracker.db.backup.pre_build61_* instance/datatracker.db
systemctl --user restart datatracker.service
```

## Benefits

1. **Simplified data model** - Single source of truth for all documents
2. **Accurate counts** - Admin dashboard now shows correct published document counts
3. **Cleaner code** - Removed duplicate model and loading logic
4. **Better maintainability** - Fewer tables to manage and sync
5. **Clear lifecycle** - Document status tracked in one place

## Files Modified

- `ietf_data_viewer_simple.py` - Model and logic changes
- `migrate_remove_published_draft.py` - New migration script

## Database Impact

- **Dev**: ✅ Migrated successfully, 4 submissions preserved
- **Production**: Pending migration (2 submissions will be preserved)

## Notes

- The `published_draft` table was completely unused (0 records in both dev and production)
- All existing approved drafts remain in the `submission` table
- No data loss occurred during migration
- The migration is reversible via database backup

---

**Next Step:** Merge to main and deploy to production when ready.
