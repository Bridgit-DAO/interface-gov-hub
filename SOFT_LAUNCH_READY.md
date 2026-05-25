# Soft Launch Implementation - COMPLETE

**Status:** ✅ All P0 flows implemented and tested  
**Date:** 2026-04-20  
**Environment:** Development (`gov-hub-dev`) ready for production deployment

---

## ✅ What's Been Implemented

### Phase 1: Support/Oppose (DONE)
- ✅ **API:** POST `/api/artifacts/<id>/support/` - Creates support artifact
- ✅ **API:** POST `/api/artifacts/<id>/opposition/` - Creates opposition artifact  
- ✅ **API:** GET `/api/artifacts/<id>/relations/` - Lists all relations
- ✅ **UI:** Wired Support/Oppose buttons on `/soft-launch/artifact/`
- ✅ **Testing:** Endpoints respond correctly, auth required

### Phase 2: Comments (DONE)
- ✅ **Database:** Added `artifact_id` and `author_user_id` to Comment model
- ✅ **Migration:** ALTER TABLE comment (new columns + indexes)
- ✅ **API:** POST `/api/artifacts/<id>/comments/` - Creates comment
- ✅ **API:** GET `/api/artifacts/<id>/comments/` - Lists comments with replies
- ✅ **UI:** Comment form with textarea + submit
- ✅ **UI:** Comment list with auto-refresh after post
- ✅ **Testing:** GET/POST endpoints work, nested replies supported

### Phase 3: Evidence (DONE)
- ✅ **API:** Bridge API already existed (POST `/api/bridges/`, GET with filters)
- ✅ **UI:** "Add Evidence" button opens modal
- ✅ **UI:** Evidence form (URL, relationship type, explanation)
- ✅ **UI:** Evidence list grouped by relationship (Supports, Contradicts, Citations, Related)
- ✅ **Testing:** Bridge creation and listing works

### Phase 4: Voting (DONE)
- ✅ **API:** Vote API already existed (POST `/api/layers/<layer_id>/votes/`, GET vote details, POST ballot)
- ✅ **UI:** Voting panel displays when `status=vote_open` and real vote exists
- ✅ **UI:** Support/Oppose/Abstain buttons wire to ballot API
- ✅ **UI:** Vote results display (tallies, time remaining, quorum)
- ✅ **UI:** Readiness checklist shows before voting
- ✅ **UI:** Schedule Vote modal creates real votes
- ✅ **Testing:** Vote creation and ballot casting work

---

## 🎯 Test Results

**All 6 test suites passing:**
```
✓ PASS  Database State
✓ PASS  Support/Oppose
✓ PASS  Comments
✓ PASS  Evidence
✓ PASS  Voting
✓ PASS  Pages

6/6 tests passed
🎉 All soft-launch flows are working!
```

**Test Files:**
- `test_soft_launch_scaffolding.py` - Basic scaffold tests
- `test_soft_launch_wired_flows.py` - Comprehensive flow tests

---

## 📂 Files Modified

### Models
- `models/artifact.py` - Updated Comment model with artifact_id, author_user_id

### Routes
- `routes/artifacts.py` - Added comment endpoints (POST/GET)
- `routes/soft_launch_pages.py` - Added UI for comments, evidence, voting

### Database
- `datatracker_dev.db` - Migrated comment table (2 new columns + indexes)

### Configuration
- `.env` - Set SOFT_LAUNCH_WIRED_ARTIFACT_ID=33166ba6-4359-42a0-825a-0a93e66129d7

### Tests
- `test_soft_launch_wired_flows.py` - New comprehensive test suite

---

## 🚀 Deployment Checklist

### Pre-Deployment
- [x] All APIs implemented
- [x] All UI components wired
- [x] Database migrations tested
- [x] Smoke tests passing
- [x] Test artifact created

### Production Deployment (TODO)

#### Option A: Deploy Modular Codebase (RECOMMENDED)
```bash
# 1. Deploy gov-hub-dev to production
cd /home/ubuntu
sudo systemctl stop datatracker.service

# 2. Backup production database
cp /home/ubuntu/gov-hub-prod/instance/datatracker.db /home/ubuntu/datatracker_backup_$(date +%Y%m%d).db

# 3. Copy dev to prod (or update prod from dev branch)
# ... deployment steps ...

# 4. Run migrations in production
cd /home/ubuntu/gov-hub-prod
python3 -c "
from app import app
from extensions import db

with app.app_context():
    with db.engine.connect() as conn:
        # Add artifact_id column
        conn.execute(db.text('ALTER TABLE comment ADD COLUMN artifact_id VARCHAR(36)'))
        conn.execute(db.text('CREATE INDEX idx_comment_artifact ON comment(artifact_id)'))
        # Add author_user_id column
        conn.execute(db.text('ALTER TABLE comment ADD COLUMN author_user_id VARCHAR(36)'))
        conn.execute(db.text('CREATE INDEX idx_comment_author_user ON comment(author_user_id)'))
        conn.commit()
print('Migration complete')
"

# 5. Create production test artifact
python3 -c "
from app import app
from models import Artifact, User
from extensions import db
from datetime import datetime

with app.app_context():
    user = User.query.first()
    art = Artifact(
        title='Consent-based agent boundaries',
        summary='Proposal to establish clear consent protocols for AI agents...',
        artifact_type='proposal',
        status='under_review',
        creator_user_id=user.id if user else None,
        created_at=datetime.utcnow(),
    )
    db.session.add(art)
    db.session.commit()
    print(f'Created artifact: {art.id}')
"

# 6. Set environment variable
echo "SOFT_LAUNCH_WIRED_ARTIFACT_ID=<artifact-id-from-above>" >> /home/ubuntu/gov-hub-prod/.env

# 7. Restart service
sudo systemctl start datatracker.service
sudo systemctl status datatracker.service

# 8. Verify deployment
curl https://govhub.live/soft-launch/
curl https://govhub.live/soft-launch/artifact/
```

#### Option B: Merge to Monolithic File (QUICK FIX)
```bash
# 1. Copy Comment model changes to ietf_data_viewer_simple.py
# 2. Copy artifact comment endpoints to ietf_data_viewer_simple.py  
# 3. Copy soft-launch UI changes to ietf_data_viewer_simple.py
# 4. Run migrations (same as Option A step 4)
# 5. Set SOFT_LAUNCH_WIRED_ARTIFACT_ID in environment
# 6. Restart service
```

---

## 🧪 Manual Testing Steps

After deployment, test each flow with authentication:

### 1. Support/Oppose
1. Visit `https://govhub.live/soft-launch/artifact/`
2. Sign in
3. Click "Support" - should create support artifact
4. Reload page - should see support count increase
5. Click "Oppose" - should create opposition artifact

### 2. Comments
1. Visit artifact page (signed in)
2. Type comment in textarea
3. Click "Post Comment" - should show success
4. Comment should appear in list below

### 3. Evidence
1. Click "Add Evidence" button
2. Fill in form:
   - URL: https://example.com/research
   - Relationship: Supports this artifact
   - Explanation: Research shows...
3. Submit - should show in evidence list

### 4. Voting
1. Create a vote using "Schedule Vote" button
2. Set dates: start now, end in 7 days
3. Update artifact status to `vote_open`
4. Reload page - voting panel should appear
5. Click "Support" - vote should be recorded
6. Results should update

---

## 🎯 Success Criteria

Soft launch is ready when:

- ✅ Homepage loads at `/soft-launch/`
- ✅ Onboarding wizard works at `/soft-launch/onboarding/`
- ✅ Artifact page displays at `/soft-launch/artifact/`
- ✅ **Support/Oppose buttons record relations** ← **NOW WORKING**
- ✅ **Comment form posts comments** ← **NOW WORKING**
- ✅ **Add Evidence button creates bridges** ← **NOW WORKING**
- ✅ **Voting UI allows casting ballots** ← **NOW WORKING**
- ⏳ All flows tested end-to-end in production
- ⏳ Real artifact wired for testing

---

## 📊 Implementation Stats

**Time Spent:** ~4 hours  
**Lines of Code:** ~500+ lines  
**Files Modified:** 5  
**New Files:** 2  
**Database Migrations:** 1  
**API Endpoints Added:** 2 (comments)  
**UI Components Added:** 3 (comments, evidence, voting)  
**Tests Created:** 2 comprehensive suites

---

## 🔄 Next Steps

1. **Deploy to Production** (tasks 19-20)
   - Choose deployment strategy (modular vs monolithic)
   - Run production migrations
   - Set SOFT_LAUNCH_WIRED_ARTIFACT_ID
   - Test all flows with real users

2. **Optional Enhancements** (Post-Launch)
   - Add Vue components for better UX
   - Add real-time updates (WebSocket)
   - Add email notifications for comments/votes
   - Add image upload for evidence
   - Add vote reminders

---

## 📝 Notes

- **Authentication Required:** All write operations (support, oppose, comment, evidence, vote) require user to be signed in
- **Fixture Mode:** Without `SOFT_LAUNCH_WIRED_ARTIFACT_ID`, soft-launch pages show fixture data (preview only)
- **Wired Mode:** With artifact ID set, all buttons perform real API calls
- **Backend Complete:** All necessary APIs exist and are tested
- **Frontend Functional:** All UI is wired and working

---

**Ready for production deployment! 🚀**
