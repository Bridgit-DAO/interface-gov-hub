# Production Migration Plan - Build 51
**Date:** 2026-02-08  

> **Historical:** Pre-dates the 2026-08-03 policy that **`main` is production**.
> The git branch `production` is retired. See [docs/DEV-TO-MAIN-WORKFLOW.md](docs/DEV-TO-MAIN-WORKFLOW.md).

**Target:** Production (rfc.themetalayer.org)  
**Current Build:** 33 → **New Build:** 51

## Overview
This migration includes critical fixes for markdown rendering, ordinal document display, and UI improvements. **IMPORTANT:** Database migration required but NO data transfer from dev.

---

## Pre-Migration Checklist

### 1. Backup Current Production
```bash
# Backup production database
cd /home/ubuntu/datatracker
cp instance/datatracker.db instance/datatracker.db.backup.pre_build51_$(date +%Y%m%d_%H%M%S)

# Backup production code (if needed)
git stash save "Production state before build 51 migration"
```

### 2. Verify Current State
```bash
# Check production service status
systemctl --user status datatracker.service

# Check current build number
curl -s https://rfc.themetalayer.org/ | grep -o "Build [0-9]*"

# Check database schema
sqlite3 instance/datatracker.db ".schema submission" | grep -E "(is_revision|revision_number|parent_draft_name|what_changed)"
```

---

## Database Migration Steps

### Required Schema Changes
The production database needs these columns (if not already present):

```sql
-- Check if columns exist
SELECT sql FROM sqlite_master WHERE type='table' AND name='submission';

-- Add columns if missing (script will check first)
ALTER TABLE submission ADD COLUMN is_revision BOOLEAN DEFAULT 0;
ALTER TABLE submission ADD COLUMN revision_number TEXT DEFAULT '00';
ALTER TABLE submission ADD COLUMN parent_draft_name TEXT;
ALTER TABLE submission ADD COLUMN what_changed TEXT;
```

### Migration Script
The application automatically adds these columns on startup. Verify with:

```bash
# Start production temporarily to run migration
cd /home/ubuntu/datatracker
python3 -c "
from ietf_data_viewer_simple import db, app
with app.app_context():
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns('submission')]
    required = ['is_revision', 'revision_number', 'parent_draft_name', 'what_changed']
    for col in required:
        if col in columns:
            print(f'✓ {col} exists')
        else:
            print(f'✗ {col} MISSING')
"
```

### CRITICAL: Do NOT Copy Dev Database
```bash
# ❌ DO NOT DO THIS:
# cp instance_dev/datatracker_dev.db instance/datatracker.db

# ✅ CORRECT: Keep production database, only update schema
# The application will automatically add missing columns on startup
```

---

## Code Deployment Steps

### 1. Switch to Production Branch
```bash
cd /home/ubuntu/datatracker

# Ensure dev changes are committed
git status

# Merge dev into main (production release branch)
git checkout main
git pull origin main
git merge dev --no-ff -m "Merge build 51: Markdown rendering and UI improvements"

# Or cherry-pick specific commit
# git cherry-pick 3eb0d97b2
```

### 2. Update Production Code
```bash
# If using direct deployment
git checkout main
git pull

# Verify build number changed
grep "BUILD_NUMBER = " ietf_data_viewer_simple.py
# Should show: BUILD_NUMBER = 51
```

### 3. Clear Python Cache
```bash
cd /home/ubuntu/datatracker
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
```

---

## Service Restart

### Option A: Using Restart Script
```bash
cd /home/ubuntu/datatracker
bash force-restart-production.sh  # If exists
# OR
systemctl --user restart datatracker.service
```

### Option B: Manual Restart
```bash
# Stop service
systemctl --user stop datatracker.service

# Kill any lingering processes
pkill -9 -f "python.*ietf_data.*8000" 2>/dev/null || true
sleep 2

# Start service
systemctl --user start datatracker.service
sleep 5

# Verify
systemctl --user status datatracker.service
```

---

## Post-Migration Verification

### 1. Service Health Check
```bash
# Check service is running
systemctl --user is-active datatracker.service

# Check logs for errors
journalctl --user -u datatracker.service -n 50 --no-pager

# Verify build number
curl -s https://rfc.themetalayer.org/ | grep -o "Build [0-9]*"
# Should show: Build 51
```

### 2. Database Verification
```bash
# Check columns were added
sqlite3 instance/datatracker.db "PRAGMA table_info(submission);" | grep -E "(is_revision|revision_number|parent_draft_name|what_changed)"

# Check existing data is intact
sqlite3 instance/datatracker.db "SELECT COUNT(*) FROM submission;"
sqlite3 instance/datatracker.db "SELECT COUNT(*) FROM user;"
```

### 3. Functional Testing

#### Test 1: Homepage
- Visit https://rfc.themetalayer.org/
- Verify "Build 51" appears in footer
- Check no console errors

#### Test 2: Document Display
- Navigate to any approved ML-Draft
- Verify proper display ID (ML-Draft-XXX, not internal ID)
- Check markdown rendering (if ordinal document)
- Verify images display correctly

#### Test 3: Ordinal Preview
- Go to Submit Draft page
- Switch to Ordinal tab
- Enter inscription ID: `a455e1c4ca82bc15c2b0bde0eb647f09d5117e8203054bbb729f48f0d9e9aa72i0`
- Click "Preview Ordinal"
- Verify:
  - No CORS errors
  - Markdown renders correctly
  - Images display with proper sizing
  - No excessive line breaks

#### Test 4: Revisions & History Pages
- Navigate to any document's revisions page
- Verify breadcrumb shows: Home > Documents > **ML-Draft-XXX** > Revisions
- Verify title shows: "Revisions for **ML-Draft-XXX**" (not internal ID)
- Check history page similarly

#### Test 5: Revision Submission
- If logged in, try submitting a revision
- Verify ordinal preview works
- Verify "what changed" field appears

---

## Rollback Plan

### If Issues Occur:

#### 1. Quick Rollback (Code Only)
```bash
cd /home/ubuntu/datatracker

# Revert to previous commit
git log --oneline -5  # Find previous commit
git checkout <previous-commit-hash>

# Restart service
systemctl --user restart datatracker.service
```

#### 2. Full Rollback (Code + Database)
```bash
cd /home/ubuntu/datatracker

# Stop service
systemctl --user stop datatracker.service

# Restore database backup
cp instance/datatracker.db.backup.pre_build51_* instance/datatracker.db

# Revert code
git checkout <previous-commit-hash>

# Clear cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Restart
systemctl --user start datatracker.service
```

---

## Key Changes in Build 51

### 1. Markdown Rendering Improvements
- Removed `break-on-newline` to fix excessive line breaks
- Added figure tag preprocessing for images
- Enhanced image URL handling (bare inscription IDs, /content/ paths)
- Updated bleach sanitization for figure/figcaption tags

### 2. Ordinal Preview Fix
- Replaced CORS-breaking direct fetch with API endpoints
- Uses `/api/ordinal/preview` for metadata
- Uses `/api/ordinal/convert-markdown` for rendering
- Proper error handling and loading states

### 3. UI Improvements
- Fixed History page to show ML-Draft numbers
- Fixed Revisions page to show ML-Draft numbers
- Added build number footer for version tracking
- Improved document content styling for ordinals

### 4. Database Schema
- Added `is_revision` column (BOOLEAN)
- Added `revision_number` column (TEXT)
- Added `parent_draft_name` column (TEXT)
- Added `what_changed` column (TEXT)

---

## Important Notes

1. **NO DATA TRANSFER**: Production database stays as-is, only schema updated
2. **Automatic Migration**: Application adds missing columns on startup
3. **Zero Downtime**: Can be done with quick service restart
4. **Backward Compatible**: New columns have defaults, existing data unaffected
5. **Build Number**: Footer now shows build for cache busting

---

## Estimated Timeline

- **Backup:** 2 minutes
- **Code Deployment:** 3 minutes
- **Service Restart:** 1 minute
- **Verification:** 5 minutes
- **Total:** ~15 minutes

---

## Success Criteria

- ✅ Service running with Build 51
- ✅ Database has all required columns
- ✅ Existing documents display correctly
- ✅ Ordinal preview works without errors
- ✅ History/Revisions pages show ML-Draft numbers
- ✅ No console errors or 500 errors
- ✅ Images display in ordinal documents

---

## Support Contacts

- **Developer:** Available during migration
- **Logs Location:** `/var/log/datatracker/` or `journalctl --user -u datatracker.service`
- **Database:** `/home/ubuntu/datatracker/instance/datatracker.db`

---

## Post-Migration Tasks

1. Monitor logs for 24 hours
2. Check for any user-reported issues
3. Verify all ordinal documents render correctly
4. Test revision submission workflow
5. Update documentation if needed

---

**Ready to proceed?** Review this plan and execute step-by-step.
