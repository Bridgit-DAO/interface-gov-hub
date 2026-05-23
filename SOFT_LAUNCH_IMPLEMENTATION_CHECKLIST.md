# Soft Launch Implementation Checklist

**Goal:** Wire the 4 core artifact actions (Support/Oppose, Comment, Add Evidence, Vote) to make the soft-launch demo fully functional.

**Current Status:** Scaffold complete, all backend models exist, most APIs exist. Need to create artifact action APIs and wire frontend.

---

## Phase 1: Support/Oppose (Artifact Relations) - 2 hours

### Backend API (routes/artifacts.py)

#### ☐ 1.1 Create support endpoint
```python
@bp.route('/artifacts/<artifact_id>/support/', methods=['POST'])
@require_auth
def support_artifact(artifact_id):
    """Create a 'supports' artifact relation."""
    # Validate artifact exists
    # Get current user
    # Check if relation already exists
    # Create ArtifactRelation(
    #     from_object_type='artifact',
    #     from_object_id=artifact.id,
    #     to_object_id=artifact.id,
    #     relation_type='supports',
    #     created_by_user_id=user.id
    # )
    # Return 201 with relation_id
```

**File:** `/home/ubuntu/gov-hub-dev/routes/artifacts.py` (create if doesn't exist)

#### ☐ 1.2 Create oppose endpoint
```python
@bp.route('/artifacts/<artifact_id>/oppose/', methods=['POST'])
@require_auth
def oppose_artifact(artifact_id):
    """Create an 'opposes' artifact relation."""
    # Same pattern as support, but relation_type='opposes'
```

#### ☐ 1.3 Create relations list endpoint
```python
@bp.route('/artifacts/<artifact_id>/relations/', methods=['GET'])
def get_artifact_relations(artifact_id):
    """List all relations for an artifact (supports, opposes, etc)."""
    # Query ArtifactRelation where from_object_id=artifact_id
    # Group by relation_type
    # Return {
    #   'supports': [user_ids],
    #   'opposes': [user_ids],
    #   'builds_on': [artifact_ids],
    # }
```

#### ☐ 1.4 Wire routes to app.py
```python
from routes.artifacts import bp as artifacts_bp
app.register_blueprint(artifacts_bp)
```

---

### Frontend Wiring (routes/soft_launch_pages.py)

#### ☐ 1.5 Update artifact page JavaScript
Add AJAX handlers for Support/Oppose buttons:

```javascript
// When SOFT_LAUNCH_WIRED_ARTIFACT_ID is set, wire real actions
const artifactId = "{{ wired_artifact_id }}";

document.querySelector('.btn-support').addEventListener('click', async () => {
    const resp = await fetch(`/api/artifacts/${artifactId}/support/`, {
        method: 'POST',
        credentials: 'include'
    });
    if (resp.ok) {
        alert('Support recorded!');
        location.reload();
    }
});

document.querySelector('.btn-oppose').addEventListener('click', async () => {
    const resp = await fetch(`/api/artifacts/${artifactId}/oppose/`, {
        method: 'POST',
        credentials: 'include'
    });
    if (resp.ok) {
        alert('Opposition recorded!');
        location.reload();
    }
});
```

#### ☐ 1.6 Display relation counts
Update artifact page template to show:
- "12 people support this"
- "3 people oppose this"

---

## Phase 2: Comments - 2 hours

### Backend API (routes/artifacts.py)

#### ☐ 2.1 Update Comment model
**File:** `/home/ubuntu/gov-hub-dev/models/artifact.py`

```python
class Comment(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid4()))
    draft_name = db.Column(db.String(255), index=True)  # Legacy, keep for backcompat
    artifact_id = db.Column(db.String(36), db.ForeignKey('artifact.id'), nullable=True, index=True)  # NEW
    text = db.Column(db.Text)
    author = db.Column(db.String(100))  # Legacy
    author_user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=True)  # NEW
    # ... rest of fields
```

Run migration to add `artifact_id` and `author_user_id` columns.

#### ☐ 2.2 Create comment endpoint
```python
@bp.route('/artifacts/<artifact_id>/comments/', methods=['POST'])
@require_auth
def create_comment(artifact_id):
    """Create a comment on an artifact."""
    # Validate artifact exists
    # Get current user
    # Get request JSON: { "text": "...", "parent_id": "..." }
    # Create Comment(
    #     artifact_id=artifact_id,
    #     text=text,
    #     author_user_id=user.id,
    #     author=user.display_name,
    #     parent_id=parent_id
    # )
    # Return 201 with comment JSON
```

#### ☐ 2.3 List comments endpoint
```python
@bp.route('/artifacts/<artifact_id>/comments/', methods=['GET'])
def list_comments(artifact_id):
    """List all comments for an artifact (with replies nested)."""
    # Query Comment where artifact_id=artifact_id and parent_id is None
    # For each, fetch replies recursively
    # Return comments tree
```

---

### Frontend UI (routes/soft_launch_pages.py)

#### ☐ 2.4 Add comment form to artifact page
Add below artifact description:

```html
<div class="card mt-4">
  <div class="card-header">Comments</div>
  <div class="card-body">
    <form id="comment-form">
      <textarea class="form-control mb-2" name="text" rows="3" 
                placeholder="Share your thoughts..." required></textarea>
      <button type="submit" class="btn btn-primary">Post Comment</button>
    </form>
  </div>
</div>

<script>
document.getElementById('comment-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const resp = await fetch(`/api/artifacts/${artifactId}/comments/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: formData.get('text') }),
        credentials: 'include'
    });
    if (resp.ok) {
        location.reload();
    }
});
</script>
```

#### ☐ 2.5 Display comment list
Fetch and render comments below form:

```html
<div id="comments-list" class="mt-3">
  <!-- Populated via JS fetch to /api/artifacts/<id>/comments/ -->
</div>

<script>
async function loadComments() {
    const resp = await fetch(`/api/artifacts/${artifactId}/comments/`);
    const comments = await resp.json();
    // Render comments with reply threads
}
loadComments();
</script>
```

---

## Phase 3: Add Evidence (Bridges) - 3 hours

### Backend API
✅ **Already exists:** `/api/bridges/` routes in `routes/bridges.py`

- `POST /api/bridges/` - Create bridge
- `GET /api/bridges/?artifact_id=<id>` - List bridges (need to add filter)

#### ☐ 3.1 Add artifact_id filter to bridges list
**File:** `/home/ubuntu/gov-hub-dev/routes/bridges.py`

Update `GET /api/bridges/` to accept `?source_url=<artifact_url>` or `?artifact_id=<id>`.

---

### Frontend UI (routes/soft_launch_pages.py)

#### ☐ 3.2 Add "Add Evidence" button
Add to artifact page primary actions:

```html
<button class="btn btn-secondary" data-bs-toggle="modal" data-bs-target="#evidenceModal">
  Add Evidence
</button>
```

#### ☐ 3.3 Create evidence modal form
```html
<div class="modal fade" id="evidenceModal">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Add Evidence</h5>
      </div>
      <div class="modal-body">
        <form id="evidence-form">
          <input type="hidden" name="source_url" value="https://govhub.live/artifacts/{{ artifact.id }}">
          
          <label>Evidence URL</label>
          <input type="url" class="form-control mb-2" name="target_url" required>
          
          <label>Relationship</label>
          <select class="form-select mb-2" name="relationship">
            <option value="supported_by">Supports this artifact</option>
            <option value="contradicted_by">Contradicts this artifact</option>
            <option value="cites">Cites/References</option>
            <option value="related_to">Related</option>
          </select>
          
          <label>Explanation (optional)</label>
          <textarea class="form-control mb-2" name="explanation" rows="2"></textarea>
          
          <button type="submit" class="btn btn-primary">Add Evidence</button>
        </form>
      </div>
    </div>
  </div>
</div>

<script>
document.getElementById('evidence-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const resp = await fetch('/api/bridges/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            name: 'Evidence for artifact',
            source: {
                url: formData.get('source_url'),
                content_type: 'text'
            },
            target: {
                url: formData.get('target_url'),
                content_type: 'text'
            },
            relationship: formData.get('relationship'),
            explanation: formData.get('explanation')
        }),
        credentials: 'include'
    });
    if (resp.ok) {
        location.reload();
    }
});
</script>
```

#### ☐ 3.4 Display evidence list
Add "Evidence" section to artifact page:

```html
<div class="card mt-4">
  <div class="card-header">Evidence</div>
  <div class="card-body" id="evidence-list">
    <!-- Populated via JS -->
  </div>
</div>

<script>
async function loadEvidence() {
    const artifactUrl = `https://govhub.live/artifacts/${artifactId}`;
    const resp = await fetch(`/api/bridges/?source_url=${encodeURIComponent(artifactUrl)}`);
    const data = await resp.json();
    // Render bridges grouped by relationship type
}
loadEvidence();
</script>
```

---

## Phase 4: Voting - 4 hours

### Backend API
✅ **Already exists:** `/api/votes/` routes in `routes/votes.py`

- `POST /api/layers/<layer_id>/votes/` - Create vote
- `POST /api/votes/<vote_id>/ballot/` - Cast ballot
- `GET /api/votes/<vote_id>/` - Get vote details

#### ☐ 4.1 Link artifact to vote
Ensure `Vote.artifact_id` is populated when creating votes for artifacts.

---

### Frontend UI (routes/soft_launch_pages.py)

#### ☐ 4.2 Add voting panel (when status=vote_open)
Update artifact page template to conditionally show voting UI:

```python
# In soft_launch_pages.py, when rendering artifact with scenario='vote_open'
if scenario == 'vote_open':
    # Check if real vote exists for this artifact
    vote = Vote.query.filter_by(artifact_id=artifact_id, status='active').first()
    if vote:
        voting_html = f'''
        <div class="card border-primary mt-4">
          <div class="card-header bg-primary text-white">
            <h5>Cast Your Vote</h5>
            <p class="mb-0">Voting closes: {vote.end_at.strftime('%B %d, %Y at %I:%M %p UTC')}</p>
          </div>
          <div class="card-body">
            <form id="ballot-form">
              <div class="btn-group w-100" role="group">
                <input type="radio" class="btn-check" name="position" id="support" value="support" required>
                <label class="btn btn-outline-success" for="support">Support</label>
                
                <input type="radio" class="btn-check" name="position" id="oppose" value="oppose">
                <label class="btn btn-outline-danger" for="oppose">Oppose</label>
                
                <input type="radio" class="btn-check" name="position" id="abstain" value="abstain">
                <label class="btn btn-outline-secondary" for="abstain">Abstain</label>
              </div>
              <button type="submit" class="btn btn-primary w-100 mt-3">Submit Vote</button>
            </form>
          </div>
        </div>
        
        <script>
        document.getElementById('ballot-form').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const position = document.querySelector('input[name="position"]:checked').value;
            const resp = await fetch('/api/votes/{vote.id}/ballot/', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ position }}),
                credentials: 'include'
            }});
            if (resp.ok) {{
                alert('Vote recorded!');
                location.reload();
            }}
        }});
        </script>
        '''
```

#### ☐ 4.3 Display vote results
When vote is closed or user has voted:

```html
<div class="card mt-4">
  <div class="card-header">Vote Results</div>
  <div class="card-body">
    <div class="row text-center">
      <div class="col-4">
        <h3 class="text-success">{{ support_count }}</h3>
        <p>Support</p>
      </div>
      <div class="col-4">
        <h3 class="text-danger">{{ oppose_count }}</h3>
        <p>Oppose</p>
      </div>
      <div class="col-4">
        <h3 class="text-muted">{{ abstain_count }}</h3>
        <p>Abstain</p>
      </div>
    </div>
    <div class="progress mt-3">
      <div class="progress-bar bg-success" style="width: {{ support_pct }}%">{{ support_pct }}%</div>
      <div class="progress-bar bg-danger" style="width: {{ oppose_pct }}%">{{ oppose_pct }}%</div>
    </div>
  </div>
</div>
```

#### ☐ 4.4 Add readiness checklist (when status=under_review_ready)
Add "Ready for Vote" panel to artifact page:

```html
<div class="card border-warning mt-4">
  <div class="card-header bg-warning">
    <h5>Review Complete - Ready for Vote</h5>
  </div>
  <div class="card-body">
    <h6>Readiness Checklist</h6>
    <ul class="list-unstyled">
      <li>✓ Minimum review period met (7 days)</li>
      <li>✓ At least 3 comments received</li>
      <li>✓ Author has addressed feedback</li>
    </ul>
    <button class="btn btn-warning" data-bs-toggle="modal" data-bs-target="#scheduleVoteModal">
      Schedule Vote
    </button>
  </div>
</div>
```

#### ☐ 4.5 Create vote scheduling modal
```html
<div class="modal fade" id="scheduleVoteModal">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Schedule Vote</h5>
      </div>
      <div class="modal-body">
        <form id="schedule-vote-form">
          <label>Start Date</label>
          <input type="datetime-local" class="form-control mb-2" name="start_at" required>
          
          <label>End Date</label>
          <input type="datetime-local" class="form-control mb-2" name="end_at" required>
          
          <label>Decision Question</label>
          <textarea class="form-control mb-2" name="title" required>Should we approve this artifact?</textarea>
          
          <button type="submit" class="btn btn-primary">Schedule Vote</button>
        </form>
      </div>
    </div>
  </div>
</div>

<script>
document.getElementById('schedule-vote-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    // POST to /api/layers/<layer_id>/votes/
    // with artifact_id, title, start_at, end_at
});
</script>
```

---

## Phase 5: Testing & Deployment - 2 hours

#### ☐ 5.1 Create test artifact in dev database
```sql
INSERT INTO artifact (id, public_id, title, description, status, layer_id, created_by_user_id)
VALUES (
    'test-artifact-001',
    'test-artifact-001',
    'Consent-based agent boundaries',
    'Proposal to establish clear consent protocols for AI agents...',
    'under_review',
    NULL,
    'admin-user-id'
);
```

#### ☐ 5.2 Set environment variable
```bash
export SOFT_LAUNCH_WIRED_ARTIFACT_ID="test-artifact-001"
```

#### ☐ 5.3 Manual testing checklist
- [ ] Visit `/soft-launch/artifact/` - verify artifact displays
- [ ] Click "Support" - verify relation created
- [ ] Click "Oppose" - verify relation created
- [ ] Post comment - verify comment appears
- [ ] Add evidence - verify bridge created
- [ ] Change status to `vote_open` - verify voting panel appears
- [ ] Cast vote - verify ballot recorded
- [ ] Check vote results - verify tallies display

#### ☐ 5.4 Automated smoke test
Update `test_soft_launch_scaffolding.py`:

```python
def test_wired_artifact_flows():
    """Test all flows when SOFT_LAUNCH_WIRED_ARTIFACT_ID is set."""
    with app.app_context():
        c = app.test_client()
        
        # Create test artifact
        artifact = Artifact(id='test-001', title='Test', status='under_review')
        db.session.add(artifact)
        db.session.commit()
        
        # Test support endpoint
        r = c.post(f'/api/artifacts/{artifact.id}/support/', json={})
        assert r.status_code == 201
        
        # Test comment endpoint
        r = c.post(f'/api/artifacts/{artifact.id}/comments/', 
                   json={'text': 'Great idea!'})
        assert r.status_code == 201
        
        # Test bridge endpoint
        r = c.post('/api/bridges/', json={
            'source': {'url': f'https://govhub.live/artifacts/{artifact.id}'},
            'target': {'url': 'https://example.com/evidence'},
            'relationship': 'supported_by'
        })
        assert r.status_code == 201
```

#### ☐ 5.5 Deploy to production
Choose deployment strategy:

**Option A: Merge to monolithic prod file**
- Copy artifact API routes to `gov-hub-prod/ietf_data_viewer_simple.py`
- Copy soft-launch routes to prod
- Restart service

**Option B: Switch production to modular dev**
- Deploy `gov-hub-dev` directory as new production
- Update nginx/systemd config
- Migrate database if needed

#### ☐ 5.6 Production environment setup
```bash
# In production environment
export SOFT_LAUNCH_WIRED_ARTIFACT_ID="<real-artifact-uuid>"
export GOV_HUB_BUILD_NUMBER=$(cat instance/build_number.txt)
```

---

## Success Criteria

Soft launch is ready when:

- [x] Homepage loads at `/soft-launch/`
- [x] Onboarding wizard works at `/soft-launch/onboarding/`
- [x] Artifact page displays at `/soft-launch/artifact/`
- [ ] **Support/Oppose buttons record relations**
- [ ] **Comment form posts comments**
- [ ] **Add Evidence button creates bridges**
- [ ] **Voting UI allows casting ballots**
- [ ] All flows tested end-to-end
- [ ] Deployed to production
- [ ] Real artifact wired for testing

---

## Files to Create/Modify

### New Files
- `/home/ubuntu/gov-hub-dev/routes/artifacts.py` - Artifact action APIs

### Modified Files
- `/home/ubuntu/gov-hub-dev/routes/soft_launch_pages.py` - Add UI for comments, evidence, voting
- `/home/ubuntu/gov-hub-dev/models/artifact.py` - Update Comment model with artifact_id
- `/home/ubuntu/gov-hub-dev/app.py` - Register artifacts blueprint
- `/home/ubuntu/gov-hub-dev/test_soft_launch_scaffolding.py` - Add wired flow tests
- `/home/ubuntu/gov-hub-dev/static/css/soft-launch.css` - Style new UI elements

### Migrations Needed
```sql
-- Add artifact_id to comments table
ALTER TABLE comment ADD COLUMN artifact_id VARCHAR(36);
ALTER TABLE comment ADD COLUMN author_user_id VARCHAR(36);
CREATE INDEX idx_comment_artifact ON comment(artifact_id);
```

---

## Estimated Timeline

| Phase | Task | Time | Dependencies |
|-------|------|------|--------------|
| 1 | Support/Oppose API | 1h | None |
| 1 | Support/Oppose UI | 1h | API complete |
| 2 | Comment model update | 0.5h | None |
| 2 | Comment API | 1h | Model update |
| 2 | Comment UI | 0.5h | API complete |
| 3 | Evidence UI (backend exists) | 3h | None |
| 4 | Voting UI (backend exists) | 4h | None |
| 5 | Testing | 1h | All phases |
| 5 | Deployment | 1h | Testing complete |

**Total: 13 hours** (conservative estimate with testing/debugging buffer)

---

## Next Steps

1. Start with **Phase 1: Support/Oppose** (quickest win)
2. Move to **Phase 2: Comments** (high user value)
3. Implement **Phase 3: Evidence** (differentiation feature)
4. Complete **Phase 4: Voting** (core governance flow)
5. Test and deploy **Phase 5**

**Ready to begin implementation?**
