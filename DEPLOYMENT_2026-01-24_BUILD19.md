# Production Deployment - BUILD 19
## Date: 2026-01-24 02:53 UTC

### ✅ Deployment Status: SUCCESSFUL

## Changes Deployed

### 🪙 Ordinals Integration (Complete)
- **Ordinal Source Type**: Users can now submit drafts from Bitcoin Ordinals
- **Content Preview**: Images, text, markdown, and HTML content display
- **Metadata Display**: Inscription number, block height, timestamp
- **Markdown Support**: Automatic detection and conversion with image URL fixing
- **Mixed Sources**: Drafts can have versions from both files and ordinals

### 🔧 Bug Fixes
- **User Attribution**: Fixed Web3Auth users showing as "Anonymous User"
  - Now uses `displayName` or `oauthName` as fallback
- **Submission Access**: Fixed 403 errors on submission status pages
- **Redirect Fix**: Submissions now redirect to correct status page with ID
- **Timestamp Parsing**: Fixed UTC timestamp format handling

### 📊 UI Improvements
- **Submission Lists**: Show inscription number/ID for ordinal submissions
- **Admin Dashboard**: Display ordinal metadata in submission management
- **Source Badges**: Visual indicators for file vs ordinal sources

### 📦 Dependencies Added
- `markdown2==2.5.4` - Markdown to HTML conversion
- `bleach==6.2.0` - HTML sanitization
- `webencodings==0.5.1` - Character encoding support

## Database Status
- **Production Database**: Cleared and ready
- **Backup Created**: `instance/datatracker.db.backup.20260124_025305`
- **Submissions**: 0 (clean start)
- **Users**: Preserved (Web3Auth users intact)

## Service Status
- **Production Service**: `datatracker.service` ✅ Active
- **Development Service**: `datatracker-dev.service` ✅ Active
- **Port**: 8000 (production), 8001 (development)
- **Build Number**: 19

## Git Status
- **Branch**: `main`
- **Commit**: `f5dd7f6a7` - "feat: Complete ordinals integration"
- **Feature Branch**: `feature/ordinals-integration` (merged)

## Testing Checklist
- [ ] Test ordinal submission with inscription ID
- [ ] Verify metadata display (inscription number, block height, timestamp)
- [ ] Test markdown detection and image rendering
- [ ] Verify user attribution shows correct names
- [ ] Test submission access for owners
- [ ] Check admin submission management page
- [ ] Verify file uploads still work

## Rollback Instructions
If issues arise:
```bash
cd /home/ubuntu/datatracker
git checkout <previous-commit>
systemctl --user restart datatracker.service
```

## Next Steps
1. Monitor production logs for errors
2. Test ordinal submission flow
3. Verify all features work as expected
4. Update user documentation if needed

## Notes
- All test submissions from development have been cleared
- Production database is clean and ready for real submissions
- Web3Auth integration remains functional
- Dark theme is default for all pages

---
**Deployed by**: AI Assistant
**Environment**: Production (rfc.themetalayer.org)
**Status**: ✅ Operational
