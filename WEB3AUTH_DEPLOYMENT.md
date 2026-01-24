# Web3Auth Production Deployment Guide

## Overview
This guide covers deploying the Web3Auth integration to production with minimal downtime.

## Pre-Deployment Checklist

### ✅ Verified on Dev (port 8001)
- [x] Google login works
- [x] Twitter login works  
- [x] Email passwordless login works
- [x] Dark theme modal displays correctly
- [x] User profile displays name correctly after login
- [x] Logout and re-login works with account selection

### Production URLs
- **Production**: https://rfc.themetalayer.org (port 8000)
- **Dev**: https://dev.rfc.themetalayer.org (port 8001)

## Deployment Steps

### Step 1: Deploy to Production

Run the deployment script:

```bash
cd /home/ubuntu/datatracker
./deploy-web3auth.sh
```

The script will:
1. ✅ Backup production database
2. ✅ Verify dev service is working
3. ✅ Ask for confirmation
4. ✅ Reload systemd daemon
5. ✅ Restart production service (minimal downtime: ~3-5 seconds)
6. ✅ Verify service is running and responding
7. ✅ Display service status

**Expected downtime**: 3-5 seconds

### Step 2: Post-Deployment Testing

After deployment completes, immediately test:

1. **Homepage loads**
   ```bash
   curl -I https://rfc.themetalayer.org
   ```

2. **Sign In button present**
   - Visit https://rfc.themetalayer.org
   - Click "Sign In" in the navbar
   - Verify Web3Auth modal appears with dark theme

3. **Google Login**
   - Click "Continue with Google"
   - Select your Google account
   - Verify successful login
   - Check profile dropdown shows your name

4. **Twitter Login**
   - Log out
   - Click "Sign In"
   - Click "Continue with X (Twitter)"
   - Complete Twitter auth
   - Verify successful login

5. **Email Login**
   - Log out
   - Click "Sign In"
   - Click "Continue with Email"
   - Enter email and complete passwordless flow
   - Verify successful login

6. **Logout and Re-login**
   - Log out
   - Click "Sign In" → Google
   - Verify Google account selection appears (not auto-login)

### Step 3: Monitor Logs

Monitor production logs for any errors:

```bash
journalctl --user -u datatracker.service -f
```

Look for:
- ❌ Any Python exceptions
- ❌ 500 errors on /api/auth/web3auth
- ❌ Database errors
- ✅ Successful logins

## Rollback Procedure

If something goes wrong:

```bash
cd /home/ubuntu/datatracker
./rollback-web3auth.sh
```

This will:
1. Stop production service
2. Restore database from backup
3. Restart production service

## Configuration Details

### Web3Auth Settings
- **Network**: `sapphire_devnet`
- **Client ID**: `BKvRj4akAwrNHHk4UyYCC4zt9KWigdiuosCX5-idVNclsk9hPPQ4_b8grcl0JF4NhT26oLWb3O5K949SVv6lTGk`
- **Theme**: Dark mode
- **Login Methods**: Google, Twitter (X), Email Passwordless, Wallet Connect

### Domain Whitelist
Ensure the following domains are whitelisted in Web3Auth Dashboard:
- https://rfc.themetalayer.org
- https://dev.rfc.themetalayer.org

## Changes Deployed

### Frontend Changes
1. ✅ Removed separate login page - Sign In now triggers modal on any page
2. ✅ Removed Register button from navbar
3. ✅ Web3Auth modal with Google, Twitter, Email, Wallet options
4. ✅ Dark theme by default
5. ✅ Dark theme Web3Auth modal
6. ✅ Forced Google account selection on re-login

### Backend Changes
1. ✅ `/login/` route redirects to home with modal trigger
2. ✅ `/api/auth/web3auth` endpoint handles all Web3Auth logins
3. ✅ User creation/update logic for Web3Auth users
4. ✅ Display name from OAuth stored and shown in profile dropdown
5. ✅ Support for Google, Twitter, Email passwordless logins

### Database Changes
- No schema changes required
- Existing users are updated with Web3Auth credentials on first login
- New users are created with Web3Auth profile data

## Troubleshooting

### Issue: Modal shows white background
**Solution**: Clear browser cache and hard refresh (Ctrl+Shift+R)

### Issue: "verifierId required" error
**Solution**: Check browser console logs, ensure Web3Auth is initialized correctly

### Issue: UNIQUE constraint failed: user.email
**Solution**: User already exists, backend should update existing user (this is handled in latest version)

### Issue: Service won't start
**Check logs**:
```bash
journalctl --user -u datatracker.service -n 100 --no-pager
```

### Issue: 500 error on login
**Check backend logs**:
```bash
journalctl --user -u datatracker.service -f
```

Look for Python traceback showing the exact error.

## Manual Deployment (Alternative)

If you prefer manual deployment:

```bash
# 1. Backup database
cp /home/ubuntu/datatracker/instance/datatracker.db \
   /home/ubuntu/datatracker/backups/datatracker_prod_backup_$(date +%Y%m%d_%H%M%S).db

# 2. Reload systemd
systemctl --user daemon-reload

# 3. Restart production service
systemctl --user restart datatracker.service

# 4. Check status
systemctl --user status datatracker.service

# 5. Test endpoint
curl http://localhost:8000/
```

## Support Commands

### Check service status
```bash
systemctl --user status datatracker.service
```

### Restart production
```bash
systemctl --user restart datatracker.service
```

### View logs (last 50 lines)
```bash
journalctl --user -u datatracker.service -n 50
```

### Follow logs live
```bash
journalctl --user -u datatracker.service -f
```

### Check which file is running
```bash
systemctl --user cat datatracker.service | grep ExecStart
```

## Success Criteria

Deployment is successful when:
- ✅ Production service is running
- ✅ Homepage loads without errors
- ✅ Sign In button triggers Web3Auth modal
- ✅ Modal has dark theme
- ✅ Google login works
- ✅ Twitter login works
- ✅ Email login works
- ✅ User name displays in profile dropdown
- ✅ Logout and re-login shows account selection
- ✅ No errors in production logs

## Timeline

- **Preparation**: 2 minutes (read this guide)
- **Execution**: 1 minute (run script)
- **Downtime**: 3-5 seconds (service restart)
- **Verification**: 5 minutes (test all login methods)
- **Total**: ~8 minutes

## Notes

- Both dev and production run the same `ietf_data_viewer_simple.py` file
- Dev uses port 8001, Production uses port 8000
- Database files are separate (instance_dev/datatracker_dev.db vs instance/datatracker.db)
- No code changes needed between dev and production
- Environment variables (FLASK_ENV, FLASK_PORT) control behavior

## Contact

If you encounter issues:
1. Check logs first
2. Try rollback if critical
3. Dev environment remains available for testing
