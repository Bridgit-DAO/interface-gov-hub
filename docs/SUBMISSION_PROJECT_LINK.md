# Submission → Project Direct Link

## Summary

Fixed the issue where ML-DRAFT-001 wasn't appearing in the Create Vote dropdown for the Metaweb layer.

## The Problem

**Original Design (IETF-style):**
- Submissions had NO direct link to Projects/Layers
- Indirect link: `Submission.group` → `Workgroup.acronym` → `Workgroup.project_id` → `Project`
- This worked for IETF where every draft belongs to a Working Group
- **Didn't work for Metaweb**: Layer-level drafts (ML-DRAFT-001) have empty `group` field

**Why ML-DRAFT-001 was missing:**
- ML-DRAFT-001 had `group = ''` (empty) - it's a layer-level draft
- The API filtered by `Submission.group.in_(workgroup_acronyms)`
- Empty group didn't match any workgroup acronym → excluded from results

## The Solution

### 1. Added `project_id` to Submission Model

```python
class Submission(db.Model):
    # ... existing fields ...
    project_id = db.Column(db.String(50), db.ForeignKey('project.id'), nullable=True, index=True)
```

**Database Migration:**
- Column already existed in both dev and prod databases
- Set ML-DRAFT-001's `project_id` to Metaweb: `proj_dfupe6bwkkul`

### 2. Simplified API Logic

**Before (complex workgroup-based filtering):**
```python
# Get workgroups, filter by group.in_(acronyms), special case for Metaweb...
```

**After (simple, correct logic):**
```python
@app.route('/api/projects/<project_id>/submissions/', methods=['GET'])
def api_list_project_submissions(project_id):
    """List approved drafts (not RFCs) for a project - eligible for voting"""
    submissions = Submission.query.filter(
        Submission.project_id == project_id,
        Submission.status == 'approved',
        Submission.doc_type == 'draft'
    ).order_by(Submission.submitted_at.desc()).all()
```

**Criteria for voting eligibility:**
- ✅ Belongs to the project (`project_id` matches)
- ✅ Is approved (`status = 'approved'`)
- ✅ Is a draft, not an RFC (`doc_type = 'draft'`)
- ❌ Workgroups are irrelevant to voting

### 3. Updated Submission Creation

**New submissions** (`/submit/`):
- Use `project_id` from form (`request.form.get('project_id')`) when provided
- Otherwise use `g.layer.id` when submitting from a layer subdomain
- Layer selector: when on main dev site (no subdomain), show dropdown of approved layers; when on layer subdomain, show layer name + hidden input

**Revisions** (`/submit/revision/<draft_name>/`):
- Inherit `project_id` from parent submission (revisions belong to same layer)

## Result

✅ **ML-DRAFT-001 now appears in the Create Vote dropdown for Metaweb**
✅ **Submissions are properly linked to their layer/project**
✅ **Vote eligibility is simple and correct: approved drafts for that project**
✅ **Future submissions automatically get the correct `project_id`**

## Testing

```bash
# Verify API returns ML-DRAFT-001 for Metaweb
curl "http://127.0.0.1:8001/api/projects/proj_dfupe6bwkkul/submissions/"

# Expected: 1 submission (ML-Draft-001)
```

## Database State

**Dev DB (`instance_dev/datatracker_dev.db`):**
- Submission `rlgl62rk` (ML-Draft-001) → `project_id = proj_dfupe6bwkkul`

**Prod DB (`instance/datatracker.db`):**
- Submission `cnqi3t48` (ML-Draft-001) → `project_id = proj_dfupe6bwkkul`

## Migration Notes

If deploying to a fresh database or environment without `project_id` column:

```sql
-- Add column
ALTER TABLE submission ADD COLUMN project_id VARCHAR(50);

-- Create index
CREATE INDEX IF NOT EXISTS idx_submission_project ON submission(project_id);

-- Set project_id for existing submissions (example for Metaweb)
UPDATE submission 
SET project_id = 'proj_dfupe6bwkkul' 
WHERE ml_number LIKE 'ML-%';
```
