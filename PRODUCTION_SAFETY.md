# 🚨 PRODUCTION SAFETY MEASURES

**Last Updated:** 2026-01-18
**Status:** ACTIVE - Post-Incident Safeguards Implemented

## Incident Summary

On 2026-01-18, a database migration script accidentally ran on production, wiping all data. This was caused by insufficient environment checks and safeguards.

## Implemented Safeguards

### 1. **Production Lock System**
- **File:** `.production_lock`
- **Effect:** Flask app shows warning on startup in production
- **Purpose:** Visual reminder that destructive operations are blocked

### 2. **Migration Script Safeguards**
- **Environment Detection:** Shows which environment will be affected
- **Production Confirmation:** Requires typing "YES" to confirm production operations
- **Automatic Backups:** Creates timestamped backup before any changes
- **Backup Verification:** Ensures backup is created successfully before proceeding
- **Production Restrictions:** Refuses destructive operations on production

### 3. **Deployment Safeguards**
- **Production Confirmation:** Requires typing "DEPLOY_PRODUCTION" for prod deployments
- **Backup Verification:** Checks for recent production backup (< 1 hour old)
- **Clear Warnings:** Shows affected URL and service name

### 4. **Git Safeguards**
- **Pre-commit Hook:** Prevents committing database files
- **Gitignore:** Excludes all database files and safety files
- **Production Lock:** Included in gitignore to prevent accidental commits

### 5. **Environment Verification**
- **FLASK_ENV Checks:** All scripts verify environment before operations
- **Path Verification:** Shows full database paths before operations
- **Size Verification:** Confirms database exists and has content

## Usage Instructions

### For Development Work
```bash
# Safe - automatically detects dev environment
FLASK_ENV=development python3 migrate_db_schema.py
```

### For Production Maintenance (Admin Only)
```bash
# Remove lock temporarily (with extreme caution)
rm .production_lock

# Run with explicit confirmation required
python3 migrate_db_schema.py

# Restore lock immediately
touch .production_lock
```

### For Deployments
```bash
# Dev deployment - no confirmation needed
python3 deploy.py dev

# Prod deployment - requires "DEPLOY_PRODUCTION" confirmation
python3 deploy.py prod
```

## Verification Commands

```bash
# Check production lock status
ls -la .production_lock

# Verify gitignore excludes databases
grep "\.db" .gitignore

# Test migration safeguards
python3 migrate_db_schema.py

# Check recent backups
ls -la backups/ | grep prod-working
```

## Emergency Procedures

If production data loss occurs:

1. **Stop all services immediately**
   ```bash
   systemctl --user stop datatracker.service
   ```

2. **Restore from backup**
   ```bash
   cp backups/prod-working-YYYYMMDD_HHMMSS.db instance/datatracker.db
   ```

3. **Verify data integrity**
   ```bash
   sqlite3 instance/datatracker.db "SELECT COUNT(*) FROM submission;"
   ```

4. **Restart services**
   ```bash
   systemctl --user restart datatracker.service
   ```

## Lessons Learned

1. **Never run destructive scripts on production**
2. **Always verify environment before operations**
3. **Require explicit confirmation for production changes**
4. **Create backups before ANY database operations**
5. **Use proper migration tools (Alembic) for schema changes**
6. **Implement multiple layers of safety checks**

## Contact

For production maintenance, contact the system administrator. These safeguards are designed to prevent accidental data loss while still allowing necessary maintenance operations.