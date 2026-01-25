# BLINDSPOT ANALYSIS: Hidden Risks & Edge Cases

**Date:** 2026-01-25  
**Agent:** BLINDSPOT (Blind-Spot Identifier)  
**Scope:** Identify overlooked edge cases, race conditions, and hidden assumptions

## 1. Race Conditions

### 1.1 Concurrent Submissions
**Scenario:** Two users submit documents simultaneously

**Analysis:**
- ✓ Submission IDs are random 8-character strings (collision unlikely)
- ✓ File names include submission ID (no overwrite risk)
- ✓ Database uses transactions (ACID properties)
- ⚠️ **BLINDSPOT:** SQLite write lock could cause one submission to fail

**Mitigation:**
- SQLite handles this with automatic retry
- Error message shown to user
- **Risk Level:** LOW

### 1.2 Migration During Active Use
**Scenario:** User submits document while migration is running

**Analysis:**
- ⚠️ **BLINDSPOT:** Migration locks database during ALTER TABLE
- User submission would fail or timeout
- No data corruption risk (transactions)

**Mitigation:**
- Run migration during maintenance window
- Put application in read-only mode
- **Risk Level:** MEDIUM (dev), LOW (with proper scheduling)

### 1.3 File Processing Race
**Scenario:** File deleted while being processed

**Analysis:**
- ⚠️ **BLINDSPOT:** File could be deleted between upload and calculation
- Exception handling catches this
- Defaults applied (1, 0)

**Mitigation:**
- Already handled by exception handling
- **Risk Level:** LOW

## 2. Edge Cases Not Covered

### 2.1 Unicode and Special Characters
**Scenario:** File contains emoji, special Unicode, or non-Latin scripts

**Test Cases:**
- ✓ UTF-8 encoding with `errors='replace'` handles this
- ✓ Word splitting works for most languages
- ⚠️ **BLINDSPOT:** CJK languages (Chinese/Japanese/Korean) don't use spaces

**Impact:**
- Word count may be inaccurate for CJK documents
- Page count derived from word count also affected

**Mitigation:**
- Document limitation in user guide
- Consider language-aware word counting in future
- **Risk Level:** LOW (acceptable for MVP)

### 2.2 Binary Files Disguised as Text
**Scenario:** User renames .exe to .txt and uploads

**Analysis:**
- ⚠️ **BLINDSPOT:** File would be read as text with `errors='replace'`
- Garbage characters would be counted as "words"
- No security risk (not executed)

**Mitigation:**
- Add MIME type validation (recommended by RED)
- **Risk Level:** LOW (cosmetic issue)

### 2.3 Extremely Long Lines
**Scenario:** File has single line with millions of characters

**Analysis:**
- ⚠️ **BLINDSPOT:** `f.read()` loads entire file into memory
- Could cause memory exhaustion
- File size limit (50MB) provides some protection

**Mitigation:**
- Existing file size limit (50MB)
- Consider streaming for large files
- **Risk Level:** LOW (mitigated by size limit)

### 2.4 Symbolic Links
**Scenario:** Uploaded file is actually a symlink

**Analysis:**
- ⚠️ **BLINDSPOT:** `os.path.exists()` follows symlinks
- Could read files outside upload directory
- `secure_filename()` doesn't prevent this

**Mitigation:**
- Check if file is symlink: `os.path.islink()`
- Reject symlinks
- **Risk Level:** MEDIUM (security concern)

**Recommendation:** Add symlink check:
```python
if os.path.islink(file_path):
    print(f"[WARNING] Symlink detected: {file_path}")
    return (1, 0)
```

### 2.5 Zero-Byte Files
**Scenario:** User uploads empty file

**Analysis:**
- ✓ Handled correctly (0 words, 1 page)
- No errors

**Status:** ✅ COVERED

### 2.6 Files with Only Whitespace
**Scenario:** File contains only spaces, tabs, newlines

**Analysis:**
- `content.split()` returns empty list
- `len([])` = 0 words
- ✓ Handled correctly (0 words, 1 page)

**Status:** ✅ COVERED

## 3. Assumption Failures

### 3.1 Assumption: Files Never Change
**Reality:** File could be modified after upload

**Analysis:**
- ⚠️ **BLINDSPOT:** Stored pages/words become stale if file modified
- No mechanism to detect or recalculate

**Impact:**
- Displayed values don't match actual file
- Rare scenario (files shouldn't be modified after upload)

**Mitigation:**
- Document that files are immutable after upload
- Add file hash to detect modifications (future)
- **Risk Level:** LOW

### 3.2 Assumption: Calculation Always Succeeds
**Reality:** Calculation can fail (handled with defaults)

**Analysis:**
- ✓ Exception handling provides defaults
- ⚠️ **BLINDSPOT:** No indication to user that calculation failed
- User sees "1 page, 0 words" for both missing files and failed calculations

**Impact:**
- User confusion
- No way to distinguish between missing file and failed calculation

**Mitigation:**
- Add status field: "calculated", "default", "failed"
- Show warning icon for failed calculations
- **Risk Level:** LOW (cosmetic)

### 3.3 Assumption: 500 Words Per Page
**Reality:** Varies by formatting, font size, margins

**Analysis:**
- ⚠️ **BLINDSPOT:** Estimation may be inaccurate
- RFC documents typically use fixed formatting
- Acceptable approximation

**Impact:**
- Page count is estimate, not exact
- Users may expect exact count

**Mitigation:**
- Document that page count is estimated
- Label as "~5 pages" instead of "5 pages"
- **Risk Level:** LOW (acceptable)

### 3.4 Assumption: Signal.SIGALRM Available
**Reality:** Not available on Windows

**Analysis:**
- ⚠️ **BLINDSPOT:** Timeout doesn't work on Windows
- Code checks `hasattr(signal, 'SIGALRM')` but continues anyway
- Windows users have no timeout protection

**Impact:**
- Malicious file could hang processing on Windows
- Dev environment is Linux (not affected)

**Mitigation:**
- Use threading.Timer for cross-platform timeout
- **Risk Level:** MEDIUM (Windows only)

**Recommendation:** Cross-platform timeout:
```python
import threading

def timeout_wrapper(func, args, timeout):
    result = [None]
    exception = [None]
    
    def target():
        try:
            result[0] = func(*args)
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        # Timeout occurred
        return None
    if exception[0]:
        raise exception[0]
    return result[0]
```

## 4. Hidden Dependencies

### 4.1 PyPDF2 and python-docx
**Analysis:**
- ⚠️ **BLINDSPOT:** Optional dependencies
- If not installed, PDF/DOCX files get defaults (1, 0)
- No error shown to user

**Impact:**
- Silent failure for PDF/DOCX files
- User doesn't know calculation failed

**Mitigation:**
- Check dependencies on startup
- Log warning if missing
- **Risk Level:** LOW (dev environment has them)

### 4.2 File System Permissions
**Analysis:**
- ⚠️ **BLINDSPOT:** Upload directory must be writable
- If permissions wrong, submissions fail
- Error handling shows generic message

**Impact:**
- All submissions fail
- Difficult to diagnose

**Mitigation:**
- Check upload directory on startup
- Create if doesn't exist
- **Risk Level:** LOW (handled by Flask)

## 5. Scalability Blind Spots

### 5.1 Growing Database
**Scenario:** 10,000+ submissions

**Analysis:**
- ⚠️ **BLINDSPOT:** `all_documents()` loads all submissions into memory
- No pagination
- Could be slow with many submissions

**Impact:**
- Slow page load
- High memory usage

**Mitigation:**
- Add pagination (future)
- Add indexes on status column
- **Risk Level:** LOW (current scale), MEDIUM (future)

### 5.2 Disk Space
**Scenario:** Many large files uploaded

**Analysis:**
- ⚠️ **BLINDSPOT:** No disk space monitoring
- No cleanup of old files
- Could fill disk

**Impact:**
- Submissions fail when disk full
- Application crashes

**Mitigation:**
- Monitor disk usage
- Implement file retention policy
- Add disk space check before upload
- **Risk Level:** MEDIUM (long-term)

## 6. User Experience Blind Spots

### 6.1 Progress Indication
**Scenario:** User uploads large file

**Analysis:**
- ⚠️ **BLINDSPOT:** No progress bar or indication
- User doesn't know if upload/processing is working
- May click submit multiple times

**Impact:**
- Poor UX
- Duplicate submissions possible

**Mitigation:**
- Add progress bar (future)
- Disable submit button after click
- **Risk Level:** LOW (UX issue)

### 6.2 Error Messages
**Scenario:** Calculation fails

**Analysis:**
- ⚠️ **BLINDSPOT:** Generic "1 page, 0 words" shown
- No indication of error
- User doesn't know to retry or report issue

**Impact:**
- Confusion
- Unreported bugs

**Mitigation:**
- Add calculation status indicator
- Show warning for failed calculations
- **Risk Level:** LOW (cosmetic)

## 7. Recurring Pattern Detection

### Pattern 1: Silent Failures
**Occurrences:**
- Missing dependencies
- Failed calculations
- Timeout on Windows

**Root Cause:** Exception handling with defaults masks errors

**Prevention:**
- Add logging for all failures
- Add status field to track calculation state
- Alert admins on repeated failures

### Pattern 2: Platform-Specific Issues
**Occurrences:**
- Signal.SIGALRM on Windows
- File path separators
- Line endings

**Root Cause:** Unix-centric development

**Prevention:**
- Test on multiple platforms
- Use cross-platform libraries
- Add platform checks

### Pattern 3: Scale-Related Issues
**Occurrences:**
- Loading all submissions
- No pagination
- No disk space monitoring

**Root Cause:** MVP mindset, not production-ready

**Prevention:**
- Design for scale from start
- Add monitoring early
- Implement limits

## 8. Summary of Blind Spots

### Critical: 0
### High: 0
### Medium: 3
1. Symlink security risk
2. Windows timeout not working
3. Disk space monitoring

### Low: 8
1. CJK language word counting
2. Binary files as text
3. Stale pages/words after file modification
4. No calculation status indicator
5. Missing dependencies silent failure
6. Scalability (pagination)
7. Progress indication
8. Error messages

## 9. Recommendations

### Immediate:
1. Add symlink check in calculate_pages_and_words()
2. Implement cross-platform timeout using threading
3. Add dependency check on startup

### Short-term:
4. Add calculation status field
5. Improve error messages
6. Add disk space monitoring

### Long-term:
7. Implement pagination for documents page
8. Add progress indication for uploads
9. Language-aware word counting

## 10. Conclusion

**Status:** ✅ **ACCEPTABLE RISK**

Most blind spots are low-risk and acceptable for development/testing. The medium-risk items (symlink, Windows timeout, disk space) should be addressed before production deployment.

**Blind-Spot Triggers Documented:**
- Silent failures with defaults
- Platform-specific behavior
- Scale-related limitations

**Approved for:** Development, Testing  
**Requires fixes for:** Production (address medium-risk items)

---

**BLINDSPOT Agent:** a1c30f27-767f-4566-8324-454313a9cea8  
**Signature:** Blind-spot analysis complete - 2026-01-25
