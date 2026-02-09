# Hypothesis Integration - Production Migration Plan

## Overview

**Migration Date:** TBD  
**Current Status:** Completed in dev (commit c09f6523b)  
**Target:** Production deployment of Hypothesis annotation integration  
**Downtime Required:** ~5 minutes (for nginx config reload)

## Pre-Migration Checklist

### 1. Environment Verification
- [ ] Verify `.env` file contains `HYPOTHESIS_API_TOKEN` in production
- [ ] Confirm production database has `HypothesisAccount` table
- [ ] Test Hypothesis API connectivity from production server
- [ ] Verify SSL/TLS certificates are valid for hypothes.is domains

### 2. Configuration Review
- [ ] Review `HYPOTHESIS_CONFIG` settings for production
- [ ] Confirm `HYPOTHESIS_ENABLED = True` in production settings
- [ ] Validate Content Security Policy changes in nginx configs
- [ ] Test annotation count API endpoint: `/api/annotations/<doc>/count`

### 3. Testing Requirements
- [ ] Dev environment fully tested with real Hypothesis accounts
- [ ] Cross-browser testing completed (Chrome, Firefox, Safari, Edge)
- [ ] Mobile responsiveness verified
- [ ] Performance impact assessed (annotation loading time)

## Migration Steps

### Step 1: Database Migration (if needed)
```bash
# Check if HypothesisAccount table exists
python3 -c "
from ietf_data_viewer_simple import db, HypothesisAccount
try:
    count = HypothesisAccount.query.count()
    print(f'✅ HypothesisAccount table exists with {count} records')
except:
    print('🔄 Creating HypothesisAccount table...')
    db.create_all()
    print('✅ HypothesisAccount table created')
"
```

### Step 2: Environment Configuration
```bash
# Ensure production .env has Hypothesis API token
grep -q "HYPOTHESIS_API_TOKEN" /home/ubuntu/xowlz/burned/.env || echo "❌ Missing HYPOTHESIS_API_TOKEN"

# Verify token works
curl -H "Authorization: Bearer $(grep HYPOTHESIS_API_TOKEN /home/ubuntu/xowlz/burned/.env | cut -d= -f2)" \
     "https://hypothes.is/api/profile" | jq .
```

### Step 3: Nginx Configuration Update
```bash
# Backup current nginx configs
cp /path/to/nginx/conf.d/datatracker.conf /path/to/nginx/conf.d/datatracker.conf.backup
cp /path/to/nginx/conf.d/auth.conf /path/to/nginx/conf.d/auth.conf.backup

# Deploy new configs with Hypothesis CSP
# (Copy from k8s/nginx-datatracker.conf and k8s/nginx-auth.conf)

# Test nginx config
nginx -t

# Reload nginx (no downtime)
nginx -s reload
```

### Step 4: Application Deployment
```bash
# Deploy updated application code
git checkout main
git merge dev  # After testing
systemctl restart datatracker  # Or your deployment method

# Verify deployment
curl "https://rfc.themetalayer.org/api/annotations/test/count"
```

### Step 5: Verification Tests

#### Functional Tests
1. **Annotation Toggle**
   - Visit any document page
   - Click "Enable Annotations" → should reload with Hypothesis sidebar
   - Click "Disable Annotations" → should reload without sidebar

2. **Hypothesis Client Loading**
   - Enable annotations
   - Check browser dev tools for successful load of `embed.js`
   - Verify no CSP violations in console

3. **User Account Flow**
   - Enable annotations (not logged in) → should show signup prompt
   - Create Hypothesis account → should allow annotation creation
   - Verify annotations are attributed to correct user

4. **API Integration**
   - Test annotation count endpoint: `/api/annotations/<document>/count`
   - Verify counts update when annotations are added
   - Check server logs for API errors

#### Performance Tests
- [ ] Page load time impact < 200ms additional
- [ ] Annotation sidebar loads within 2 seconds
- [ ] No memory leaks in long sessions

## Rollback Plan

### If Issues Detected
1. **Disable annotations globally:**
   ```python
   # In production settings
   HYPOTHESIS_ENABLED = False
   ```

2. **Revert nginx configs:**
   ```bash
   cp /path/to/nginx/conf.d/datatracker.conf.backup /path/to/nginx/conf.d/datatracker.conf
   cp /path/to/nginx/conf.d/auth.conf.backup /path/to/nginx/conf.d/auth.conf
   nginx -s reload
   ```

3. **Revert application code:**
   ```bash
   git revert c09f6523b
   systemctl restart datatracker
   ```

## Post-Migration Monitoring

### Week 1: Intensive Monitoring
- [ ] Monitor annotation usage metrics
- [ ] Check for CSP violations in browser logs
- [ ] Verify API rate limits not exceeded
- [ ] Monitor server performance impact

### Metrics to Track
- Annotation creation rate
- User adoption (% enabling annotations)
- API response times for `/api/annotations/*/count`
- Browser console errors related to Hypothesis
- Server memory/CPU impact

## Known Limitations & Future Work

### Current Limitations
- Users must create their own Hypothesis accounts (no auto-creation)
- No integration with Meta-Layer user accounts
- Public annotations only (no private workgroup annotations)

### Phase 2 Planning
- [ ] Investigate Hypothesis partnership for auto-account creation
- [ ] Implement grant token system for seamless user experience  
- [ ] Add moderation tools for inappropriate annotations
- [ ] Consider private annotation spaces for working groups

## Security Considerations

### Content Security Policy
- Added `https://hypothes.is` to script-src and connect-src
- Hypothesis handles content sanitization
- No user-generated content stored on our servers

### API Token Security
- Token stored in `.env` file (not in code)
- Used only server-side for reading operations
- Never sent to client browsers
- Rotate token if compromised

### User Privacy
- Annotations stored on Hypothesis servers
- Subject to Hypothesis privacy policy
- Users control their own annotation visibility
- No Meta-Layer user data shared with Hypothesis

## Contact Information

**Technical Lead:** [Your name]  
**Hypothesis Support:** support@hypothes.is  
**Emergency Contact:** [Emergency contact]

## Success Criteria

### Minimum Viable Migration
- [ ] No errors in production logs
- [ ] Annotation toggle works correctly
- [ ] Users can create and view annotations
- [ ] No performance degradation

### Full Success
- [ ] >10% user adoption within first month
- [ ] <0.1% error rate on annotation API calls
- [ ] Positive user feedback on annotation experience
- [ ] No security incidents related to Hypothesis integration

---

**Migration Approval Required From:**
- [ ] Technical Lead
- [ ] Security Review
- [ ] Product Owner
- [ ] Operations Team

**Estimated Migration Time:** 30 minutes  
**Rollback Time:** 10 minutes  
**Risk Level:** Low-Medium (new feature, well-tested)