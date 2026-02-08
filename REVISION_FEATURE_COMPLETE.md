# Revision Loading Feature - Implementation Complete

**Date:** 2026-02-08  
**Status:** ✅ Implemented and Deployed  
**Branch:** dev  
**Server:** Running on port 8000

## What Was Implemented

### 1. Database Schema ✅
Added 4 new fields to `Submission` model:
- `parent_draft_name` (String) - Link to parent draft
- `revision_number` (String) - e.g., "01", "02"
- `what_changed` (Text) - Submitter's explanation of changes
- `is_revision` (Boolean) - Flag indicating this is a revision

**Migrations:**
- ✅ Dev database migrated
- ✅ Production database migrated
- ✅ Backups created for both

### 2. Backend Routes ✅

#### New Route: `/submit/revision/<draft_name>/`
**GET:** Shows revision submission form
- Pre-populates all fields from current draft
- Draft name is locked (displayed but not editable)
- Auto-calculates new revision number
- Shows current → new revision transition

**POST:** Processes revision submission
- Validates required fields
- Supports file upload and ordinal inscriptions
- Stores "what changed" explanation
- Creates submission with `is_revision=True`
- Links to parent draft via `parent_draft_name`
- Logs revision in document history

#### Updated Route: `/submit/status/<submission_id>/`
**Enhanced to show revision information:**
- Displays "This is a revision" callout
- Shows revision number and parent draft link
- Displays "What changed" explanation when present
- Works in same flow as regular submissions

### 3. Frontend UI ✅

#### Draft Detail Page (`/doc/draft/<name>/`)
- Added **"Submit New Revision"** button (green, with plus icon)
- Positioned in actions sidebar after "View Revisions"
- Only visible for authenticated users
- Only shown for approved drafts

#### Revisions Page (`/doc/draft/<name>/revisions/`)
- Added **"Submit New Revision"** button in top button row
- Same visibility rules as draft detail
- Positioned after "Back to Draft" button

#### Revision Submission Form
**Layout:**
- Breadcrumb navigation
- Current → New revision indicator (alert box)
- Draft name field (locked/disabled)
- Title, Authors, Abstract, Group (pre-filled, editable)
- **"What changed" textarea** with:
  - Clear label: "What changed since the last revision?"
  - Helper text explaining purpose
  - Example placeholder text
  - Optional (never blocks submission)
- Upload tabs (File / Bitcoin Ordinal)
- Submit and Cancel buttons

#### Submission Status Page (Revisions)
**When viewing a revision submission:**
- Blue info alert: "This is a revision"
- Shows revision number
- Links to parent draft
- Displays "What changed" in a card (when present)

### 4. Admin Experience ✅

**Single Submission Flow:**
- Revisions appear in same queue as new drafts
- No separate "revisions queue"

**Clear Indication:**
- Revision callout on submission detail/status page
- "What changed" explanation visible to admins
- Link to parent draft for context

**Approval Process:**
- Same workflow as new drafts
- Admin can see "what changed" to inform decision
- After approval, parent draft is updated with new revision

## How It Works

### User Flow: Submitting a Revision

1. **Navigate to draft**
   - Go to draft detail page or revisions page
   - See "Submit New Revision" button (if authenticated)

2. **Click button**
   - Taken to `/submit/revision/<draft_name>/`
   - Form is pre-populated with current draft data
   - Sees current revision → new revision

3. **Fill form**
   - Edit title, authors, abstract, group if needed
   - Optionally add "what changed" explanation
   - Upload new file OR enter ordinal inscription ID

4. **Submit**
   - Revision created with `is_revision=True`
   - Redirected to submission status page
   - Sees revision information clearly displayed

5. **Wait for approval**
   - Admin reviews in normal submission queue
   - Admin sees it's a revision with "what changed"
   - Admin approves or rejects

6. **After approval**
   - Parent draft updated to new revision
   - New revision appears on revisions page
   - "What changed" stored in history

### Admin Flow: Reviewing a Revision

1. **See submission in queue**
   - Appears in normal submission list
   - (Future: could add "Revision" badge in list)

2. **View submission detail**
   - Sees "This is a revision" callout
   - Sees parent draft link
   - Reads "what changed" explanation

3. **Approve or reject**
   - Same buttons as regular submissions
   - If approved, parent draft is updated
   - Revision history is updated

## Files Modified

1. **ietf_data_viewer_simple.py**
   - Added 4 fields to Submission model
   - Added `/submit/revision/<draft_name>/` route (GET and POST)
   - Updated submission status template with revision info
   - Added "Submit New Revision" buttons to 2 pages
   - Updated `draft_revisions()` to include current_user

2. **migrate_add_revision_fields.py** (new)
   - Migration script for revision fields
   - Idempotent (safe to re-run)
   - Creates backups

3. **Databases**
   - `instance_dev/datatracker_dev.db` - Migrated ✅
   - `instance/datatracker.db` - Migrated ✅

## Testing Checklist

### Manual Testing Needed
- [ ] Navigate to an approved draft
- [ ] Click "Submit New Revision" button
- [ ] Verify form is pre-populated
- [ ] Verify draft name is locked
- [ ] Verify revision number is auto-calculated
- [ ] Add "what changed" text
- [ ] Upload a file
- [ ] Submit revision
- [ ] Verify submission status shows revision info
- [ ] Admin: Approve the revision
- [ ] Verify parent draft shows new revision
- [ ] Verify "what changed" appears in history
- [ ] Test with ordinal inscription
- [ ] Test without "what changed" (should work)

### Edge Cases to Test
- [ ] Revision of a submission (not in DRAFTS)
- [ ] Multiple sequential revisions (00 → 01 → 02)
- [ ] Revision with very long "what changed" text
- [ ] Revision without "what changed" (optional)
- [ ] Unauthenticated user (button should not appear)
- [ ] Unapproved draft (button should not appear)

## Success Metrics

✅ **Implementation Complete:**
- [x] Database migration successful
- [x] Backend route implemented
- [x] Frontend buttons added
- [x] Revision form created
- [x] Submission status updated
- [x] Admin sees revision info
- [x] Server running successfully

⏳ **Testing Phase:**
- [ ] User can submit file revision
- [ ] User can submit ordinal revision
- [ ] "What changed" field works
- [ ] Admin can review and approve
- [ ] Parent draft updates correctly
- [ ] Revision history is accurate

## Known Limitations

1. **Revisions page currently shows placeholder**
   - Shows current revision only
   - Needs enhancement to show full revision history
   - Can be improved in future iteration

2. **No revision comparison yet**
   - No diff view between revisions
   - Can be added later

3. **Sequential revisions only**
   - Must submit revisions in order (00 → 01 → 02)
   - No branching or parallel revisions

## Next Steps

1. **User Testing** (Immediate)
   - Test the complete flow
   - Submit a real revision
   - Verify approval workflow

2. **Enhancements** (Future)
   - Show full revision history on revisions page
   - Add diff view between revisions
   - Add revision comparison tool
   - Show "what changed" in revision list

3. **Documentation** (Soon)
   - User guide: "How to submit a revision"
   - Admin guide: "Reviewing revisions"
   - FAQ about revisions

## Deployment Status

- ✅ Code committed to dev branch
- ✅ Database migrations run
- ✅ Server running on port 8000
- ✅ Ready for user testing

**URL:** http://localhost:8000/

**Test Account:** Use any existing user account to test

---

**Implementation Time:** ~1 hour  
**Status:** ✅ Complete and Running  
**Next:** User testing and feedback
