# Production Migration Plan - BUILD 64

**Date:** 2026-02-09  
**Target Build:** 64  
**Estimated Duration:** 5-10 minutes  
**Risk Level:** Low (tested on dev, includes rollback plan)

## Summary of Changes

This migration includes three major improvements:

### 1. PublishedDraft Table Removal (BUILD 61)
- Removes unused `published_draft` table (0 records)
- Adds `rfc_number` column to `submission` table
- Unifies data model to use single `submission` table

### 2. Ordinal Markdown Rendering Fix (BUILD 60)
- Fixes regex to handle nested HTML in `<figcaption>` tags
- Enables proper image display in ordinal previews

### 3. Duplicate Revision Number Prevention (BUILD 62-64)
- Auto-assigns next available revision number on duplicate
- Prevents approval of revisions with conflicting numbers
- Seamless user experience without errors

## Pre-Migration Checklist

- [x] All changes tested on dev
- [x] Migration script created and tested
- [x] Backup strategy confirmed
- [x] Rollback plan documented
- [x] Current production state verified (2 submissions)

## Migration Steps

### Step 1: Backup Production Database

```bash
cd /home/ubuntu/datatracker/instance
cp datatracker.db datatracker.db.backup.pre_build64_$(date +%Y%m%d_%H%M%S)
ls -lh datatracker.db*
```

**Verify:** Backup file created with current timestamp

### Step 2: Merge Dev to Main

```bash
cd /home/ubuntu/datatracker
git checkout main
git merge dev -m "Merge dev: BUILD 64 - PublishedDraft removal, ordinal fixes, duplicate revision prevention"
```

**Verify:** Merge completes without conflicts

### Step 3: Run Database Migration

```bash
cd /home/ubuntu/datatracker
python3 migrate_remove_published_draft.py /home/ubuntu/datatracker/instance/datatracker.db
```

**Expected Output:**
```
============================================================
PublishedDraft Table Removal Migration
============================================================

Target database: /home/ubuntu/datatracker/instance/datatracker.db

📦 Creating backup: /home/ubuntu/datatracker/instance/datatracker.db.backup.remove_published_draft_YYYYMMDD_HHMMSS
✅ Backup created successfully
➕ Adding rfc_number column to submission table...
✅ rfc_number column added
🗑️  Dropping published_draft table...
✅ published_draft table dropped

✅ Migration completed successfully!
```

**Verify:** 
- No errors in output
- Backup created
- Migration completed successfully

### Step 4: Restart Production Server

```bash
cd /home/ubuntu/datatracker
systemctl --user stop datatracker.service
sleep 2
pkill -9 -f "python.*ietf_data.*8000" 2>/dev/null
sleep 1
systemctl --user start datatracker.service
sleep 3
systemctl --user status datatracker.service
```

**Verify:**
- Service shows "active (running)"
- No errors in status output

### Step 5: Post-Migration Verification

#### 5.1 Check Build Number
```bash
curl -s https://rfc.themetalayer.org/ | grep -o "Build [0-9]*"
```
**Expected:** `Build 64`

#### 5.2 Verify Database Schema
```bash
sqlite3 /home/ubuntu/datatracker/instance/datatracker.db << 'EOF'
PRAGMA table_info(submission);
SELECT name FROM sqlite_master WHERE type='table' AND name='published_draft';
EOF
```
**Expected:**
- `rfc_number` column exists in submission table
- No output for published_draft query (table removed)

#### 5.3 Check Data Integrity
```bash
sqlite3 /home/ubuntu/datatracker/instance/datatracker.db << 'EOF'
SELECT COUNT(*) as total_submissions FROM submission;
SELECT COUNT(*) as approved_submissions FROM submission WHERE status='approved';
SELECT id, ml_number, revision_number, status FROM submission;
EOF
```
**Expected:**
- 2 total submissions
- 2 approved submissions
- Both submissions intact with ML-Draft-001

#### 5.4 Test Website Functionality
- [ ] Homepage loads: https://rfc.themetalayer.org/
- [ ] Documents page loads: https://rfc.themetalayer.org/doc/all/
- [ ] Document detail page loads: https://rfc.themetalayer.org/doc/draft/9sbj6o76/
- [ ] Revisions page loads: https://rfc.themetalayer.org/doc/draft/9sbj6o76/revisions/
- [ ] Admin dashboard loads (if logged in)
- [ ] Ordinal preview works on revision submission page

#### 5.5 Test Ordinal Image Display
Visit: https://rfc.themetalayer.org/doc/draft/9sbj6o76/
**Verify:** Image displays correctly in the document

## Rollback Plan

If any issues occur:

### Option 1: Quick Rollback (Restore Database Only)
```bash
cd /home/ubuntu/datatracker/instance
cp datatracker.db datatracker.db.broken_$(date +%Y%m%d_%H%M%S)
cp datatracker.db.backup.pre_build64_* datatracker.db
systemctl --user restart datatracker.service
```

### Option 2: Full Rollback (Code + Database)
```bash
cd /home/ubuntu/datatracker
# Save broken state
cp instance/datatracker.db instance/datatracker.db.broken_$(date +%Y%m%d_%H%M%S)

# Restore database
cp instance/datatracker.db.backup.pre_build64_* instance/datatracker.db

# Rollback code
git checkout main
git reset --hard <previous-commit-hash>

# Restart
systemctl --user restart datatracker.service
```

**Previous commit hash:** Check with `git log --oneline -5` before migration

## Known Issues & Notes

### Non-Breaking Issues
1. **Dev has 3 test submissions** - Production only has 2 (the real ones)
2. **No comments on production** - Expected, comment system is new
3. **Database file size may change** - Normal after dropping table

### Expected Behavior Changes
1. **Admin dashboard counts** - Will now show correct approved draft counts
2. **Duplicate revision prevention** - Auto-assigns next available number
3. **Ordinal images** - Will display correctly in previews and document pages

## Post-Migration Tasks

After successful migration:

1. **Switch back to dev branch**
   ```bash
   git checkout dev
   ```

2. **Monitor for 24 hours**
   - Check server logs: `journalctl --user -u datatracker.service -f`
   - Watch for any errors or unusual behavior

3. **Test revision submission**
   - Submit a new revision to verify duplicate prevention works
   - Verify ordinal preview displays images correctly

## Emergency Contacts

If issues arise:
- Database backups: `/home/ubuntu/datatracker/instance/datatracker.db.backup.*`
- Migration logs: Check terminal output
- Server logs: `journalctl --user -u datatracker.service -n 100`

## Success Criteria

Migration is successful when:
- ✅ BUILD 64 is live on production
- ✅ All 2 submissions are intact
- ✅ Website pages load without errors
- ✅ Ordinal images display correctly
- ✅ Admin dashboard shows correct counts
- ✅ No errors in server logs

---

**Ready to proceed?** Follow steps 1-5 in order, verifying each step before continuing.
