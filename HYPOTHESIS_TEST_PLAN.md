# Hypothesis Integration - Test Plan

## Test Environment Setup

### Prerequisites
- Datatracker running locally or in staging
- Multiple browsers available (Chrome, Firefox, Safari)
- Mobile device or browser emulator
- Hypothesis account (for authenticated tests)

## Test Cases

### 1. Configuration Tests

#### TC-001: Settings Configuration
**Objective:** Verify Hypothesis settings are properly configured

**Steps:**
1. Check `ietf/settings.py` for `HYPOTHESIS_ENABLED = True`
2. Verify `HYPOTHESIS_CONFIG` dictionary exists
3. Confirm all required keys are present

**Expected Result:**
- Settings are present and valid
- No syntax errors

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-002: CSP Configuration
**Objective:** Verify Content Security Policy allows Hypothesis

**Steps:**
1. Check `k8s/nginx-datatracker.conf`
2. Check `k8s/nginx-auth.conf`
3. Verify `https://hypothes.is` is in allowed sources
4. Verify `script-src` and `connect-src` include Hypothesis

**Expected Result:**
- CSP includes Hypothesis domains
- No CSP violations in browser console

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

### 2. Frontend Integration Tests

#### TC-003: Template Integration
**Objective:** Verify Hypothesis client loads on document pages

**Steps:**
1. Navigate to `/doc/html/rfc8989`
2. Open browser DevTools → Network tab
3. Enable annotations via preferences
4. Reload page
5. Check for `embed.js` request

**Expected Result:**
- `embed.js` loads successfully (200 status)
- No JavaScript errors in console
- Hypothesis sidebar appears

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-004: User Preferences - Enable
**Objective:** Verify users can enable annotations

**Steps:**
1. Navigate to any document HTML view
2. Click sidebar toggle
3. Go to "Prefs" tab
4. Select "Show annotations"
5. Verify page reloads
6. Check for Hypothesis sidebar

**Expected Result:**
- Preference saves (check cookie: `annotations=on`)
- Page reloads automatically
- Hypothesis sidebar is visible

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-005: User Preferences - Disable
**Objective:** Verify users can disable annotations

**Steps:**
1. With annotations enabled, go to "Prefs" tab
2. Select "Hide annotations"
3. Verify page reloads
4. Check Hypothesis sidebar is gone

**Expected Result:**
- Preference saves (check cookie: `annotations=off`)
- Page reloads automatically
- Hypothesis sidebar is not visible
- No `embed.js` loaded

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-006: Preference Persistence
**Objective:** Verify annotation preference persists across sessions

**Steps:**
1. Enable annotations
2. Close browser
3. Reopen browser
4. Navigate to any document
5. Check if annotations are still enabled

**Expected Result:**
- Cookie persists
- Annotations remain enabled

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

### 3. Annotation Functionality Tests

#### TC-007: Anonymous Annotation Creation
**Objective:** Verify anonymous users can create annotations

**Steps:**
1. Enable annotations (not logged into Hypothesis)
2. Select text in document
3. Click "Annotate" button
4. Type annotation text
5. Click "Post to Public"

**Expected Result:**
- Annotation is created
- Annotation appears in sidebar
- Annotation is attributed to "Anonymous"

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-008: Authenticated Annotation Creation
**Objective:** Verify authenticated users can create annotations

**Steps:**
1. Enable annotations
2. Log into Hypothesis account
3. Select text in document
4. Create annotation
5. Post as public or private

**Expected Result:**
- Annotation is created
- Annotation shows user's name
- Private annotations only visible to user

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-009: Highlight Creation
**Objective:** Verify users can create highlights without comments

**Steps:**
1. Enable annotations
2. Select text
3. Click highlighter icon
4. Verify highlight appears

**Expected Result:**
- Highlight is created (no comment)
- Highlight visible in document
- Highlight listed in sidebar

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-010: Page Notes
**Objective:** Verify users can create page-level notes

**Steps:**
1. Enable annotations
2. Click "Page Note" button in sidebar
3. Type note
4. Post note

**Expected Result:**
- Page note is created
- Note appears in sidebar
- Note not anchored to specific text

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-011: Reply to Annotation
**Objective:** Verify users can reply to existing annotations

**Steps:**
1. Find existing annotation
2. Click "Reply" button
3. Type reply
4. Post reply

**Expected Result:**
- Reply is created
- Reply appears under original annotation
- Thread is maintained

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

### 4. Document Type Tests

#### TC-012: RFC Annotations
**Objective:** Verify annotations work on RFCs

**Steps:**
1. Navigate to `/doc/html/rfc8989`
2. Enable annotations
3. Create annotation
4. Check browser console for tag: `rfc:8989`

**Expected Result:**
- Annotations work on RFC
- Correct tags applied (`rfc:8989`, `ietf:rfc`)
- No errors

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-013: Internet-Draft Annotations
**Objective:** Verify annotations work on Internet-Drafts

**Steps:**
1. Navigate to `/doc/html/draft-ietf-example-00`
2. Enable annotations
3. Create annotation
4. Check for tag: `draft:draft-ietf-example-00`

**Expected Result:**
- Annotations work on draft
- Correct tags applied (includes revision)
- No errors

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-014: Draft Revision Isolation
**Objective:** Verify annotations are revision-specific for drafts

**Steps:**
1. Navigate to `draft-ietf-example-00`
2. Enable annotations and create annotation
3. Navigate to `draft-ietf-example-01`
4. Check if annotation from -00 appears

**Expected Result:**
- Annotation from -00 does NOT appear on -01
- Each revision has separate annotation space
- Tags include revision number

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

### 5. Browser Compatibility Tests

#### TC-015: Chrome/Edge Compatibility
**Objective:** Verify functionality in Chrome/Edge

**Steps:**
1. Open document in Chrome/Edge
2. Enable annotations
3. Create annotation
4. Verify all features work

**Expected Result:**
- All features functional
- No console errors
- UI renders correctly

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-016: Firefox Compatibility
**Objective:** Verify functionality in Firefox

**Steps:**
1. Open document in Firefox
2. Enable annotations
3. Create annotation
4. Verify all features work

**Expected Result:**
- All features functional
- No console errors
- UI renders correctly

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-017: Safari Compatibility
**Objective:** Verify functionality in Safari

**Steps:**
1. Open document in Safari
2. Enable annotations
3. Create annotation
4. Verify all features work

**Expected Result:**
- All features functional
- No console errors
- UI renders correctly

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

### 6. Mobile Responsiveness Tests

#### TC-018: Mobile View - Enable Annotations
**Objective:** Verify annotations work on mobile devices

**Steps:**
1. Open document on mobile device or emulator
2. Access preferences
3. Enable annotations
4. Verify sidebar appears

**Expected Result:**
- Preferences accessible on mobile
- Annotations can be enabled
- Sidebar adapts to mobile screen

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-019: Mobile View - Create Annotation
**Objective:** Verify annotation creation on mobile

**Steps:**
1. On mobile, enable annotations
2. Select text (long press)
3. Create annotation
4. Verify annotation appears

**Expected Result:**
- Text selection works on mobile
- Annotation creation works
- UI is usable on small screens

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

### 7. Performance Tests

#### TC-020: Page Load Performance
**Objective:** Measure impact on page load time

**Steps:**
1. Measure page load time WITHOUT annotations
2. Enable annotations
3. Measure page load time WITH annotations
4. Compare results

**Expected Result:**
- Minimal impact on load time (<500ms difference)
- Hypothesis client loads asynchronously
- No blocking of page render

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

**Results:**
- Without annotations: _____ ms
- With annotations: _____ ms
- Difference: _____ ms

---

#### TC-021: Memory Usage
**Objective:** Verify reasonable memory usage

**Steps:**
1. Open DevTools → Performance/Memory
2. Load document with annotations
3. Monitor memory usage
4. Create several annotations
5. Check for memory leaks

**Expected Result:**
- Memory usage remains reasonable
- No memory leaks detected
- Browser remains responsive

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

### 8. Security Tests

#### TC-022: CSP Compliance
**Objective:** Verify no CSP violations

**Steps:**
1. Open browser console
2. Navigate to document with annotations
3. Check for CSP violation warnings
4. Verify all Hypothesis resources load

**Expected Result:**
- No CSP violations in console
- All resources load successfully
- No blocked requests

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-023: XSS Protection
**Objective:** Verify annotation content is sanitized

**Steps:**
1. Create annotation with HTML/script tags
2. Verify content is sanitized
3. Check for XSS vulnerabilities

**Expected Result:**
- HTML/script tags are escaped or removed
- No script execution from annotation content
- Hypothesis handles sanitization

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

### 9. Integration Tests

#### TC-024: Theme Compatibility
**Objective:** Verify annotations work with light/dark themes

**Steps:**
1. Enable annotations
2. Switch to light theme
3. Verify Hypothesis sidebar adapts
4. Switch to dark theme
5. Verify sidebar adapts

**Expected Result:**
- Sidebar adapts to theme
- Annotations remain readable
- No visual glitches

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-025: Sidebar Interaction
**Objective:** Verify Hypothesis sidebar doesn't conflict with document sidebar

**Steps:**
1. Enable annotations
2. Toggle document sidebar
3. Open Hypothesis sidebar
4. Verify both work independently

**Expected Result:**
- Both sidebars function correctly
- No layout conflicts
- No JavaScript errors

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

### 10. Edge Cases

#### TC-026: Disabled Globally
**Objective:** Verify behavior when disabled globally

**Steps:**
1. Set `HYPOTHESIS_ENABLED = False`
2. Restart server
3. Navigate to document
4. Check preferences

**Expected Result:**
- No annotation preferences shown
- No Hypothesis client loaded
- No errors

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-027: Network Offline
**Objective:** Verify graceful handling of offline state

**Steps:**
1. Enable annotations
2. Disconnect network
3. Navigate to document
4. Check for errors

**Expected Result:**
- Page loads (cached)
- Hypothesis client fails gracefully
- No blocking errors
- User can still read document

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

#### TC-028: Very Long Documents
**Objective:** Verify performance with large documents

**Steps:**
1. Open very long RFC (e.g., RFC 9110)
2. Enable annotations
3. Create annotations at different positions
4. Check performance

**Expected Result:**
- Annotations work throughout document
- No performance degradation
- Scrolling remains smooth

**Status:** ⬜ Not Started | ⬜ In Progress | ⬜ Passed | ⬜ Failed

---

## Test Summary

### Statistics
- **Total Test Cases:** 28
- **Passed:** ___
- **Failed:** ___
- **Not Started:** ___
- **In Progress:** ___

### Critical Issues Found
1. 
2. 
3. 

### Non-Critical Issues Found
1. 
2. 
3. 

### Recommendations
1. 
2. 
3. 

---

## Sign-off

**Tested By:** _______________  
**Date:** _______________  
**Environment:** _______________  
**Status:** ⬜ Ready for Production | ⬜ Needs Work | ⬜ Blocked

---

**Next Steps:**
- [ ] Address critical issues
- [ ] Retest failed cases
- [ ] Deploy to staging
- [ ] User acceptance testing
- [ ] Production deployment
