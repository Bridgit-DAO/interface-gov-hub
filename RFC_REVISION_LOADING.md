# RFC: Revision Loading Feature

**Status:** Planning  
**Priority:** High (needed immediately)  
**Branch:** dev  
**Date:** 2026-02-08

## Problem Statement

Currently, there is no easy way to submit a new revision of an existing draft. Users need to:
1. Navigate to a draft's detail page or revisions page
2. Have a clear action to "Submit New Revision"
3. Be taken to a submission form that is **locked to that specific draft**
4. Submit the revision
5. See the newest version displayed immediately

## Requirements

### 1. Entry Points for Revision Submission

Users should be able to initiate a revision from:

#### A. Draft Detail Page
- Add "Submit New Revision" button in the actions section
- Button should be prominent and clearly labeled
- Only visible to authenticated users

#### B. Revisions Page
- Add "Submit New Revision" button at the top
- Button should indicate it's for the current draft
- Only visible to authenticated users

### 2. Revision Submission Flow

#### Step 1: Navigate to Revision Form
- URL: `/submit/revision/<draft_name>/`
- Form is pre-populated with draft information
- Draft name is locked (cannot be changed)
- Clear indication this is a revision, not a new draft

#### Step 2: Pre-populated Fields
- **Draft Name:** Locked, displayed prominently
- **Title:** Pre-filled from current version (editable)
- **Authors:** Pre-filled from current version (editable)
- **Abstract:** Pre-filled from current version (editable)
- **Group:** Pre-filled from current version (editable)
- **Current Revision:** Displayed (e.g., "Current: 00")
- **New Revision:** Auto-calculated (e.g., "New: 01")

#### Step 3: New Fields for Revisions
- **What Changed:** Text area (optional but recommended)
  - Helper text: "Briefly describe substantive changes so reviewers can understand what evolved and why"
  - Placeholder: "Example: Clarified workgroup role; added glossary; no change to core principles"
  - Never blocks submission
  - Stored in revision history

#### Step 4: File/Ordinal Upload
- Same upload mechanism as new drafts
- Support both file upload and ordinal inscription
- Calculate pages and words from new version

#### Step 5: Validation
- Ensure new revision number is sequential
- Validate file format
- Check required fields

#### Step 6: Submission
- Create new submission record with:
  - Link to parent draft
  - Revision number
  - "What changed" text
  - All other metadata
- Status: "submitted" (requires approval)

### 3. Display Updates

#### After Submission
- Redirect to submission status page
- Show revision number prominently
- Indicate it's a revision of existing draft
- Link back to parent draft

#### After Approval
- Update draft detail page to show latest revision
- Add revision to revisions page
- Display "what changed" in revision history
- Update all metadata (pages, words, etc.)

### 4. Admin Pages: Revisions in the Same Submission Flow

**Principle:** Admin pages use the **same submission flow** for both new drafts and revisions. No separate admin flow for revisions. Revisions are just submissions with `is_revision=True`.

**Requirements for admin pages:**

1. **Single flow** – List/queue/approve submissions the same way whether they are new drafts or revisions. No separate "revisions queue."

2. **Clear indication when it’s a revision** – On every admin view that shows a submission, visibly indicate when it is a revision:
   - **Submission list/queue:** e.g. badge or label: "Revision" or "Rev 01 of &lt;draft-name&gt;"
   - **Submission detail/status:** Prominent callout, e.g. "This is revision 01 of draft-xyz"
   - **Approval page:** Same callout so the approver knows they are approving a revision, not a new draft

3. **Display the explanation when present** – If the submitter filled in "What changed since the last revision?", show it on admin pages:
   - **Submission detail page:** Dedicated section, e.g. "What changed (revision)" with the full text
   - **Submission list/queue:** Optional short preview (e.g. first 80 chars) or tooltip if space is limited
   - **Approval page:** Show the full "what changed" text so the approver can use it when reviewing

4. **Link to parent draft** – On admin views for a revision, always provide a link to the parent draft (e.g. `/doc/draft/{parent_draft_name}/`) so admins can compare or check context.

**Summary:** Revisions are handled in the same submission flow as new drafts; admin UIs must clearly mark them as revisions and surface the "what changed" explanation wherever it helps (detail, queue, approval).

**Example – Admin submission detail / approval view for a revision:**

```html
<!-- When submission.is_revision is True -->
<div class="alert alert-info mb-3">
    <strong><i class="fas fa-code-branch me-2"></i>This is a revision</strong><br>
    Revision <strong>{{ submission.revision_number }}</strong> of
    <a href="/doc/draft/{{ submission.parent_draft_name }}/">{{ submission.parent_draft_name }}</a>
</div>

{% if submission.what_changed %}
<div class="card mb-3">
    <div class="card-header">
        <strong>What changed (submitter’s explanation)</strong>
    </div>
    <div class="card-body">
        <p class="mb-0">{{ submission.what_changed }}</p>
    </div>
</div>
{% endif %}
```

## Database Schema Changes

### Submission Model Updates

```python
class Submission(db.Model):
    # ... existing fields ...
    
    # NEW FIELDS for revisions
    parent_draft_name = db.Column(db.String(255), nullable=True)  # Link to parent draft
    revision_number = db.Column(db.String(10), nullable=True)  # e.g., "01", "02"
    what_changed = db.Column(db.Text, nullable=True)  # Description of changes
    is_revision = db.Column(db.Boolean, default=False)  # Flag to indicate revision
```

### Draft/Document Updates

When a revision is approved:
1. Update the draft's current revision number
2. Store the "what changed" text in history
3. Update pages, words, and other metadata
4. Keep previous versions accessible

## UI Implementation

### 1. Draft Detail Page Updates

Add button in actions section:

```html
<div class="mb-4">
    <a href="/doc/draft/{draft_name}/" class="btn btn-primary me-2">
        <i class="fas fa-file-alt me-1"></i>View Draft
    </a>
    {% if current_user %}
    <a href="/submit/revision/{draft_name}/" class="btn btn-success me-2">
        <i class="fas fa-plus me-1"></i>Submit New Revision
    </a>
    {% endif %}
    <a href="/doc/draft/{draft_name}/comments/" class="btn btn-outline-secondary me-2">Comments</a>
    <a href="/doc/draft/{draft_name}/revisions/" class="btn btn-outline-secondary me-2">Revisions</a>
    <a href="/doc/draft/{draft_name}/history/" class="btn btn-outline-secondary">History</a>
</div>
```

### 2. Revisions Page Updates

Add button at the top:

```html
<div class="mb-4">
    <a href="/doc/draft/{draft_name}/" class="btn btn-secondary me-2">
        <i class="fas fa-arrow-left me-1"></i>Back to Draft
    </a>
    {% if current_user %}
    <a href="/submit/revision/{draft_name}/" class="btn btn-success me-2">
        <i class="fas fa-plus me-1"></i>Submit New Revision
    </a>
    {% endif %}
    <a href="/doc/draft/{draft_name}/comments/" class="btn btn-outline-secondary me-2">Comments</a>
    <a href="/doc/draft/{draft_name}/history/" class="btn btn-outline-secondary">History</a>
</div>
```

### 3. Revision Submission Form

New route: `/submit/revision/<draft_name>/`

```html
<div class="container mt-4">
    <nav aria-label="breadcrumb">
        <ol class="breadcrumb">
            <li class="breadcrumb-item"><a href="/">Home</a></li>
            <li class="breadcrumb-item"><a href="/doc/draft/{draft_name}/">{draft_name}</a></li>
            <li class="breadcrumb-item active">Submit Revision</li>
        </ol>
    </nav>
    
    <h1>Submit New Revision</h1>
    <p class="lead">Submit a new revision of {draft_name}</p>
    
    <div class="alert alert-info">
        <i class="fas fa-info-circle me-2"></i>
        <strong>Current Revision:</strong> {current_rev} → <strong>New Revision:</strong> {new_rev}
    </div>
    
    <form method="POST" enctype="multipart/form-data">
        <!-- Draft Name (locked) -->
        <div class="mb-3">
            <label class="form-label">Draft Name</label>
            <input type="text" class="form-control" value="{draft_name}" disabled>
            <input type="hidden" name="draft_name" value="{draft_name}">
        </div>
        
        <!-- Title (pre-filled, editable) -->
        <div class="mb-3">
            <label class="form-label">Title *</label>
            <input type="text" class="form-control" name="title" value="{current_title}" required>
        </div>
        
        <!-- Authors (pre-filled, editable) -->
        <div class="mb-3">
            <label class="form-label">Authors *</label>
            <input type="text" class="form-control" name="authors" value="{current_authors}" required>
            <small class="form-text text-muted">Comma-separated list</small>
        </div>
        
        <!-- Abstract (pre-filled, editable) -->
        <div class="mb-3">
            <label class="form-label">Abstract</label>
            <textarea class="form-control" name="abstract" rows="4">{current_abstract}</textarea>
        </div>
        
        <!-- Group (pre-filled, editable) -->
        <div class="mb-3">
            <label class="form-label">Working Group</label>
            <select class="form-control" name="group">
                <option value="">Select a Working Group</option>
                <!-- Group options with current group pre-selected -->
            </select>
        </div>
        
        <!-- What Changed (NEW) -->
        <div class="mb-3">
            <label class="form-label">What changed since the last revision?</label>
            <textarea class="form-control" name="what_changed" rows="3" 
                      placeholder="Example: Clarified workgroup role in determining rough consensus; added glossary; no change to core governance principles."></textarea>
            <small class="form-text text-muted">
                Optional but recommended. Briefly describe substantive changes so reviewers and future readers 
                can understand what evolved and why. Not required for minor or editorial edits.
            </small>
        </div>
        
        <!-- File Upload Tabs (same as new submission) -->
        <ul class="nav nav-tabs" role="tablist">
            <li class="nav-item">
                <a class="nav-link active" data-bs-toggle="tab" href="#upload">Upload File</a>
            </li>
            <li class="nav-item">
                <a class="nav-link" data-bs-toggle="tab" href="#ordinal">Bitcoin Ordinal</a>
            </li>
        </ul>
        
        <div class="tab-content mt-3">
            <!-- Upload tab -->
            <div id="upload" class="tab-pane active">
                <div class="mb-3">
                    <label class="form-label">Upload Document *</label>
                    <input type="file" class="form-control" name="file" accept=".txt,.pdf,.xml,.docx">
                    <small class="form-text text-muted">Supported formats: TXT, PDF, XML, DOCX</small>
                </div>
            </div>
            
            <!-- Ordinal tab -->
            <div id="ordinal" class="tab-pane">
                <!-- Same ordinal fields as new submission -->
            </div>
        </div>
        
        <input type="hidden" name="sourceType" value="file" id="sourceType">
        
        <div class="mt-4">
            <button type="submit" class="btn btn-success btn-lg">
                <i class="fas fa-upload me-2"></i>Submit Revision
            </button>
            <a href="/doc/draft/{draft_name}/" class="btn btn-secondary btn-lg ms-2">Cancel</a>
        </div>
    </form>
</div>
```

## Backend Implementation

### 1. New Route

```python
@app.route('/submit/revision/<draft_name>/', methods=['GET', 'POST'])
@require_auth
def submit_revision(draft_name):
    # Find the current draft
    draft = next((d for d in DRAFTS if d['name'] == draft_name), None)
    
    if not draft:
        # Try to find as submission
        submission = Submission.query.filter_by(id=draft_name).first()
        if submission:
            # Convert submission to draft format
            draft = {
                'name': submission.id,
                'title': submission.title,
                'authors': ', '.join(submission.authors) if isinstance(submission.authors, list) else submission.authors,
                'abstract': submission.abstract or '',
                'group': submission.group or '',
                'rev': '00',
            }
        else:
            flash('Draft not found', 'error')
            return redirect('/doc/all/')
    
    if request.method == 'GET':
        # Show form with pre-populated data
        return render_revision_form(draft)
    
    # POST: Process revision submission
    # Calculate new revision number
    current_rev = int(draft.get('rev', '00'))
    new_rev = f"{current_rev + 1:02d}"
    
    # Get form data
    title = request.form.get('title', '').strip()
    authors = request.form.get('authors', '').strip()
    abstract = request.form.get('abstract', '').strip()
    group = request.form.get('group', '').strip()
    what_changed = request.form.get('what_changed', '').strip()
    source_type = request.form.get('sourceType', 'file').strip()
    
    # Process authors
    authors_list = [a.strip() for a in authors.split(',') if a.strip()]
    
    # Generate submission ID
    submission_id = generate_submission_id()
    
    # Handle file upload or ordinal (same as new submission)
    if source_type == 'ordinal':
        # Process ordinal submission
        # ... (same as submit_draft)
        pass
    else:
        # Process file upload
        file = request.files.get('file')
        if not file:
            flash('File is required', 'error')
            return render_revision_form(draft)
        
        # Save file and calculate pages/words
        filename = f"{submission_id}-{file.filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        pages, words = calculate_pages_and_words(file_path, filename)
    
    # Create submission record
    submission = Submission(
        id=submission_id,
        title=title,
        authors=authors_list,
        abstract=abstract,
        group=group,
        filename=filename if source_type == 'file' else None,
        file_path=file_path if source_type == 'file' else None,
        submitted_by=get_current_user()['name'],
        sourceType=source_type,
        pages=pages,
        words=words,
        # NEW FIELDS
        parent_draft_name=draft_name,
        revision_number=new_rev,
        what_changed=what_changed,
        is_revision=True
    )
    
    db.session.add(submission)
    db.session.commit()
    
    # Log the action
    add_to_document_history(
        draft_name, 
        "revision_submitted", 
        get_current_user()['name'], 
        f"Revision {new_rev} submitted. Changes: {what_changed[:100] if what_changed else 'No description provided'}"
    )
    
    flash(f'Revision {new_rev} submitted successfully!', 'success')
    return redirect(f'/submit/status/{submission_id}/')
```

### 2. Update Submission Status Page

Show revision information:

```python
if submission.is_revision:
    revision_info = f"""
    <div class="alert alert-info">
        <i class="fas fa-code-branch me-2"></i>
        <strong>This is revision {submission.revision_number} of 
        <a href="/doc/draft/{submission.parent_draft_name}/">{submission.parent_draft_name}</a></strong>
    </div>
    """
    
    if submission.what_changed:
        revision_info += f"""
        <div class="card mb-3">
            <div class="card-header">
                <h6>What Changed</h6>
            </div>
            <div class="card-body">
                <p>{submission.what_changed}</p>
            </div>
        </div>
        """
```

### 3. Update Approval Process

When approving a revision:

```python
@app.route('/submit/approve/<submission_id>', methods=['POST'])
@require_admin
def approve_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    
    if submission.is_revision:
        # Update the parent draft
        parent_draft = find_draft(submission.parent_draft_name)
        if parent_draft:
            # Update revision number
            parent_draft['rev'] = submission.revision_number
            # Update metadata
            parent_draft['pages'] = submission.pages
            parent_draft['words'] = submission.words
            parent_draft['title'] = submission.title
            parent_draft['authors'] = submission.authors
            parent_draft['abstract'] = submission.abstract
            # Store "what changed" in history
            add_to_document_history(
                submission.parent_draft_name,
                "revision_approved",
                get_current_user()['name'],
                f"Revision {submission.revision_number} approved. Changes: {submission.what_changed}"
            )
    
    # ... rest of approval logic
```

### 4. Update Revisions Page

Show all revisions with "what changed":

```python
def draft_revisions(draft_name):
    # Get all submissions for this draft
    revisions = Submission.query.filter_by(
        parent_draft_name=draft_name,
        is_revision=True
    ).order_by(Submission.revision_number.desc()).all()
    
    # Build revisions HTML
    revisions_html = ""
    for rev in revisions:
        status_badge = get_status_badge(rev.status)
        revisions_html += f"""
        <div class="card mb-3">
            <div class="card-header">
                <h5>Revision {rev.revision_number} {status_badge}</h5>
                <small>Submitted by {rev.submitted_by} on {rev.submitted_at.strftime('%Y-%m-%d')}</small>
            </div>
            <div class="card-body">
                <p><strong>Pages:</strong> {rev.pages} | <strong>Words:</strong> {rev.words}</p>
                {f'<div class="alert alert-light"><strong>What Changed:</strong><br>{rev.what_changed}</div>' if rev.what_changed else ''}
                <a href="/submit/status/{rev.id}/" class="btn btn-sm btn-primary">View Details</a>
            </div>
        </div>
        """
    
    # ... rest of revisions page
```

## Implementation Checklist

### Phase 1: Database (Immediate)
- [ ] Add migration for new fields (parent_draft_name, revision_number, what_changed, is_revision)
- [ ] Update Submission model
- [ ] Test migration on dev database

### Phase 2: Backend (Immediate)
- [ ] Create `/submit/revision/<draft_name>/` route
- [ ] Implement GET handler (show form with pre-populated data)
- [ ] Implement POST handler (process revision submission)
- [ ] Update approval process to handle revisions
- [ ] Update submission status page to show revision info
- [ ] Update revisions page to show all revisions with "what changed"

### Phase 3: Frontend (Immediate)
- [ ] Add "Submit New Revision" button to draft detail page
- [ ] Add "Submit New Revision" button to revisions page
- [ ] Create revision submission form template
- [ ] Update submission status template for revisions
- [ ] Update revisions page template

### Phase 4: Admin Pages (Immediate)
- [ ] Submission list/queue: show "Revision" badge and parent draft name for revisions
- [ ] Submission detail/status: show "This is revision N of &lt;draft&gt;" callout
- [ ] Submission detail/status: show "What changed" section when present
- [ ] Approval page: show revision callout and full "what changed" text
- [ ] All admin views: include link to parent draft for revisions

### Phase 5: Testing (Immediate)
- [ ] Test revision submission flow (file upload)
- [ ] Test revision submission flow (ordinal)
- [ ] Test pre-population of fields
- [ ] Test "what changed" field (optional)
- [ ] Test approval of revisions
- [ ] Test admin list/detail/approval show revision + "what changed"
- [ ] Test display of revisions on revisions page
- [ ] Test revision history

## Success Criteria

- ✅ Users can click "Submit New Revision" from draft detail page
- ✅ Users can click "Submit New Revision" from revisions page
- ✅ Revision form is pre-populated with current draft data
- ✅ Draft name is locked (cannot be changed)
- ✅ Revision number is auto-calculated
- ✅ "What changed" field is available (optional)
- ✅ File upload and ordinal submission both work
- ✅ Revision submissions require approval
- ✅ After approval, newest version displays on draft page
- ✅ Revisions page shows all revisions with "what changed"
- ✅ Revision history is complete and accurate
- ✅ **Admin:** Same submission flow for new drafts and revisions (no separate queue)
- ✅ **Admin:** Revisions are clearly indicated (badge/label/callout) on list, detail, and approval
- ✅ **Admin:** "What changed" is displayed wherever the submission is shown when present
- ✅ **Admin:** Link to parent draft is available on revision views

## Timeline

**Target: Immediate (before big refactor)**

- **Day 1:** Database migration and model updates
- **Day 1:** Backend implementation (routes and logic)
- **Day 1:** Frontend updates (buttons and form)
- **Day 1:** Testing and deployment to dev
- **Day 2:** User testing and fixes
- **Day 2:** Deploy to production

## Notes

- This is a **high priority** feature needed immediately
- Must be completed **before** the big Projects/Workgroups/Guilds refactor
- Keep it simple and focused on the immediate need
- Can be enhanced later with more sophisticated revision tracking
