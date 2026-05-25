# RFC: Roles, Claims, Badges, and Inscriptions System

**Status:** Planning  
**Feature Branch:** `feature/projects-workgroups-guilds`  
**Related RFC:** RFC_PROJECTS_WORKGROUPS_GUILDS.md  
**Date:** 2026-02-08

## Executive Summary

This RFC extends the Projects, Workgroups, and Guilds system with a comprehensive **Roles, Claims, and Badges** framework. This supports guild-style stewardship without hierarchy, enabling:

- Project-scoped role definitions (anyone can propose)
- Role claiming by any contributor
- Badge requests tied to specific claims
- Approval workflows with clear permissions
- Status transitions for roles, claims, and badges
- Optional ordinal metadata (Bitcoin inscription IDs)

## Core Principles

1. **Anyone can propose a role** for a project
   - Initially, newly proposed roles will not be linked from public pages
   
2. **Preload canonical role sets**
   - Import roles from JSON (idempotent)
   - Initial scope: Meta-Layer project roles

3. **Anyone can claim a role**
   - Whether claim requires approval depends on role configuration
   - Most roles will not require claim approval

4. **Badge issuance is separate from claiming**
   - Anyone can request a badge for a specific claim
   - Badge approval requires project permissions

## Definitions

- **Project**: Namespace/context (e.g., Meta-Layer, Overweb, a Layer, a workgroup, or guild)
- **Role**: Defined unit of responsibility scoped to a specific project (e.g., "Bridger" in Meta-Layer)
- **Claim**: User's declaration that they are stewarding a Role
- **Badge**: Recognition artifact linked to a Claim
- **Ordinal badge**: Badge with on-chain inscription metadata (optional)
- **Cluster**: Organizational grouping of roles within a project
- **Role Image**: Visual representation (image or media) proposed for a role, subject to community voting and Project Admin approval

## Schema Design

### Cluster Model

```python
class Cluster(models.Model):
    """Organizational grouping of roles within a project"""
    id = models.CharField(max_length=50, primary_key=True)  # clu_...
    project = ForeignKey(Project, related_name='clusters')
    cluster_slug = models.SlugField(max_length=100)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('archived', 'Archived'),
        ],
        default='active'
    )
    
    created_by = ForeignKey(Person, related_name='created_clusters')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['project', 'cluster_slug']]
        ordering = ['project', 'order', 'name']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['project', 'order']),
        ]
```

### Role Model

```python
class Role(models.Model):
    """Defined unit of responsibility scoped to a project"""
    id = models.CharField(max_length=50, primary_key=True)  # rol_...
    project = ForeignKey(Project, related_name='roles')
    role_slug = models.SlugField(max_length=100)
    
    # Titles
    title_guild = models.CharField(max_length=255, help_text="Guild-facing title")
    title_operational = models.CharField(max_length=255, blank=True, help_text="Optional operational title")
    
    description = models.TextField()
    image_url = models.URLField(blank=True, help_text="Role image/icon")
    
    # Organization
    cluster = ForeignKey(Cluster, related_name='roles', null=True, blank=True)
    order = models.IntegerField(default=0)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('approved', 'Approved'),
            ('deprecated', 'Deprecated'),
            ('archived', 'Archived'),
        ],
        default='draft'
    )
    
    # Visibility
    public_visible = models.BooleanField(default=False)
    
    # Configuration
    claim_requires_approval = models.BooleanField(default=False)
    badge_enabled = models.BooleanField(default=True)
    badge_requires_approval = models.BooleanField(default=True)
    
    # Audit
    created_by = ForeignKey(Person, related_name='created_roles')
    approved_by = ForeignKey(Person, null=True, blank=True, related_name='approved_roles')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['project', 'role_slug']]
        ordering = ['project', 'cluster', 'order', 'title_guild']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['project', 'public_visible']),
            models.Index(fields=['status', 'public_visible']),
        ]
```

### Claim Model

```python
class Claim(models.Model):
    """User's declaration of stewarding a role"""
    id = models.CharField(max_length=50, primary_key=True)  # clm_...
    project = ForeignKey(Project, related_name='claims')
    role = ForeignKey(Role, related_name='claims')
    claimant = ForeignKey(Person, related_name='role_claims')
    
    # Intent and evidence
    intent = models.TextField(blank=True, help_text="Why claiming this role")
    evidence_links = models.JSONField(default=list, help_text="List of evidence URLs")
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('pending_approval', 'Pending Approval'),
            ('paused', 'Paused'),
            ('expired', 'Expired'),
            ('revoked', 'Revoked'),
        ],
        default='active'
    )
    
    # Approval (if required)
    approval_required = models.BooleanField(default=False)  # Snapshot from role at creation
    approved_by = ForeignKey(Person, null=True, blank=True, related_name='approved_claims')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Term (optional time-bounding)
    term_start = models.DateField(null=True, blank=True)
    term_end = models.DateField(null=True, blank=True)
    term_duration_days = models.IntegerField(null=True, blank=True)
    term_status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('expired', 'Expired'),
            ('paused', 'Paused'),
            ('canceled', 'Canceled'),
        ],
        default='active',
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['role', 'status']),
            models.Index(fields=['claimant', 'status']),
            models.Index(fields=['-created_at']),
        ]
    
    @property
    def badge_summary(self):
        """Get latest badge status for this claim"""
        latest_badge = self.badges.order_by('-created_at').first()
        if not latest_badge:
            return {'state': 'not_requested', 'latest_badge_id': None}
        return {
            'state': latest_badge.status,
            'latest_badge_id': latest_badge.id
        }
```

### Badge Model

```python
class Badge(models.Model):
    """Recognition artifact linked to a claim"""
    id = models.CharField(max_length=50, primary_key=True)  # bdg_...
    project = ForeignKey(Project, related_name='badges')
    claim = ForeignKey(Claim, related_name='badges')
    role = ForeignKey(Role, related_name='badges')
    claimant = ForeignKey(Person, related_name='badges_received')
    requested_by = ForeignKey(Person, related_name='badges_requested')
    
    # Badge type
    badge_type = models.CharField(
        max_length=50,
        choices=[
            ('role_badge', 'Role Badge'),
            ('founding_wave_badge', 'Founding Wave Badge'),
            ('term_renewal_marker', 'Term Renewal Marker'),
        ],
        default='role_badge'
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('requested', 'Requested'),
            ('needs_info', 'Needs Info'),
            ('approved', 'Approved'),
            ('issued', 'Issued'),
            ('denied', 'Denied'),
            ('canceled', 'Canceled'),
        ],
        default='requested'
    )
    
    # Evidence
    evidence_links = models.JSONField(default=list)
    
    # Custody
    custody_mode = models.CharField(
        max_length=20,
        choices=[
            ('user_wallet', 'User Wallet'),
            ('overweb_treasury', 'Overweb Treasury'),
        ],
        default='user_wallet'
    )
    btc_taproot_address = models.CharField(max_length=255, blank=True)
    
    # Approval
    approved_by = ForeignKey(Person, null=True, blank=True, related_name='badges_approved')
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_note = models.TextField(blank=True)
    
    # Issuance (ordinal metadata)
    issuance_kind = models.CharField(
        max_length=20,
        choices=[
            ('offchain', 'Off-chain'),
            ('ordinal', 'Bitcoin Ordinal'),
        ],
        default='offchain'
    )
    inscription_id = models.CharField(max_length=255, blank=True, help_text="Bitcoin inscription ID")
    tx_ref = models.CharField(max_length=255, blank=True, help_text="Transaction reference")
    chain = models.CharField(max_length=50, default='bitcoin', blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['project', 'status']),
            models.Index(fields=['claim', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['-created_at']),
        ]
```

### Status Change Audit Model

```python
class StatusChange(models.Model):
    """Audit trail for status changes across all entities"""
    id = models.CharField(max_length=50, primary_key=True)
    
    # Polymorphic reference
    entity_type = models.CharField(
        max_length=20,
        choices=[
            ('role', 'Role'),
            ('claim', 'Claim'),
            ('badge', 'Badge'),
            ('cluster', 'Cluster'),
        ]
    )
    entity_id = models.CharField(max_length=50)
    
    # Change details
    field_name = models.CharField(max_length=50)  # e.g., 'status', 'term_status'
    from_value = models.CharField(max_length=100)
    to_value = models.CharField(max_length=100)
    note = models.TextField(blank=True)
    
    # Audit
    changed_by = ForeignKey(Person, related_name='status_changes')
    changed_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['-changed_at']),
        ]
```

### RoleImage Model

```python
class RoleImage(db.Model):
    """Visual representation proposed for a role"""
    id = db.Column(db.String(50), primary_key=True)  # rimg_...
    project_id = db.Column(db.String(50), db.ForeignKey('project.id'), nullable=False, index=True)
    role_id = db.Column(db.String(50), db.ForeignKey('role.id'), nullable=False, index=True)
    
    # Source
    source_type = db.Column(db.String(20), nullable=False)  # 'upload', 'url', 'ordinal'
    image_url = db.Column(db.String(500), nullable=True)  # For upload or URL source
    file_path = db.Column(db.String(500), nullable=True)  # For uploaded files
    
    # Ordinal metadata (optional)
    chain = db.Column(db.String(50), nullable=True)  # 'bitcoin', etc.
    inscription_id = db.Column(db.String(255), nullable=True)
    content_type = db.Column(db.String(100), nullable=True)  # MIME type
    
    # Status and promotion
    is_primary = db.Column(db.Boolean, default=False)  # Primary role image
    is_hidden = db.Column(db.Boolean, default=False)  # Hidden by admin
    
    # Voting (aggregated)
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    net_score = db.Column(db.Integer, default=0)  # upvotes - downvotes
    
    # Admin actions
    admin_note = db.Column(db.Text, nullable=True)
    promoted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    promoted_at = db.Column(db.DateTime, nullable=True)
    
    # Audit
    submitted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    project = db.relationship('Project', backref=db.backref('role_images', lazy=True))
    role = db.relationship('Role', backref=db.backref('images', lazy=True))
    submitted_by = db.relationship('User', foreign_keys=[submitted_by_id], backref='submitted_role_images')
    promoted_by = db.relationship('User', foreign_keys=[promoted_by_id], backref='promoted_role_images')
    
    __table_args__ = (
        db.Index('idx_role_image_project_role', 'project_id', 'role_id'),
        db.Index('idx_role_image_primary', 'role_id', 'is_primary'),
        db.Index('idx_role_image_net_score', 'role_id', 'net_score'),
    )
```

### RoleImageVote Model

```python
class RoleImageVote(db.Model):
    """User vote on a role image proposal"""
    id = db.Column(db.Integer, primary_key=True)
    image_id = db.Column(db.String(50), db.ForeignKey('role_image.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    # Vote value: 1 (upvote) or -1 (downvote)
    value = db.Column(db.Integer, nullable=False)  # 1 or -1
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    image = db.relationship('RoleImage', backref=db.backref('votes', lazy=True))
    user = db.relationship('User', backref=db.backref('role_image_votes', lazy=True))
    
    __table_args__ = (
        db.UniqueConstraint('image_id', 'user_id', name='unique_user_image_vote'),
        db.Index('idx_vote_image', 'image_id'),
        db.Index('idx_vote_user', 'user_id'),
    )
```

## Functional Requirements: Role Images and Media Proposals

### 2.6 Role Images and Media Proposals

**Purpose:** Enable community-driven visual representation of roles through proposals, voting, and Project Admin approval.

**Core Flow:**

1. **Any authenticated user can submit a Role Image proposal** for a role (project-scoped)
   - Submitter selects project + role
   - Provides image via:
     - **Upload** (image file)
     - **URL** (external image URL)
     - **Ordinal** (reference to Bitcoin inscription containing image or HTML)

2. **Community voting**
   - Any authenticated user can upvote or downvote any role image proposal
   - One vote per user per image
   - Users can change their vote (update from upvote to downvote or vice versa)
   - Net score = upvotes - downvotes

3. **Project Admin promotion**
   - Project Admin can promote an image to become the **primary role image**
   - Promoting an image populates `Role.image_url` with the image URL
   - Only one primary image per role at a time
   - Project Admin can also:
     - Hide/remove inappropriate images
     - Add admin notes to images
     - Demote a primary image (revert to no primary)

**Ordinal Support:**
- When source is 'ordinal', the system stores:
  - `chain` (e.g., 'bitcoin')
  - `inscription_id` (inscription ID)
  - `content_type` (MIME type from ordinal metadata)
- The image preview uses the ordinal content URL (e.g., `https://ordinals.com/content/{inscription_id}`)

## Additional UI Requirements

### 7.1b Role Images Page

**URL:** `/projects/{project_id}/roles/{role_slug}/images/`

**Purpose:** Gallery of proposed images for a role, with voting and admin actions.

**Features:**
- **Gallery view** of all non-hidden role image proposals
- **Sorting:** By net score (default), date submitted, or upvotes
- **Each image card shows:**
  - Image preview (or ordinal preview)
  - Submitter name and submission date
  - Vote counts: upvotes, downvotes, net score
  - Upvote/downvote buttons (authenticated users)
  - "Primary" badge if `is_primary = true`
- **Voting:**
  - Click upvote → adds +1 vote (or changes from downvote)
  - Click downvote → adds -1 vote (or changes from upvote)
  - Click same button again → removes vote
  - Vote updates are instant (AJAX)
- **Project Admin actions** (shown on each card for admins):
  - "Promote to primary" button
  - "Hide image" button
  - "Add note" link
- **Submit new image** button at top (for authenticated users)

### 7.1c Image Detail Page

**URL:** `/projects/{project_id}/roles/{role_slug}/images/{image_id}/`

**Purpose:** Detailed view of a single role image proposal.

**Sections:**

1. **Image Display**
   - Large preview of the image
   - For ordinals: iframe or direct content embed
   - For uploads/URLs: `<img>` tag

2. **Metadata**
   - Submitter name (linked to profile if available)
   - Submission timestamp
   - Source type (upload / URL / ordinal)
   - If ordinal: chain, inscription ID (linked to explorer), content type

3. **Voting**
   - Current vote counts: upvotes, downvotes, net score
   - Upvote/downvote buttons (authenticated users)
   - Visual indicator of current user's vote (if any)

4. **Project Admin Actions** (permission-gated)
   - "Promote to primary role image" button
   - "Hide image" button (with confirmation)
   - "Remove image" button (with confirmation)
   - "Add admin note" text area + save button
   - Display existing admin note if present

5. **Status Indicators**
   - "Primary role image" badge if `is_primary = true`
   - "Hidden" badge if `is_hidden = true` (only visible to admins)

### Start Here Page

**Purpose:** Onboarding page for new users

**Content:**
- Welcome message
- Overview of the system (Projects, Workgroups, Guilds, Roles)
- Quick actions:
  - Submit a draft to Meta-Layer
  - Browse existing projects
  - Claim a role
  - Join a guild
- Getting started guide
- FAQ links

**URL:** `/start-here/`

### Inscriptions Page

**Purpose:** Explain Bitcoin inscriptions and ordinal badges

**Content:**
- What are inscriptions?
- How ordinal badges work
- Custody options (user wallet vs Overweb treasury)
- How to provide a BTC Taproot address
- Badge issuance process
- FAQ about inscriptions

**URL:** `/inscriptions/`

### Role Directory Page

**URL:** `/projects/{project_id}/roles/`

**Features:**
- Search (type-to-filter)
- Cluster dropdown filter
- Sort by cluster order and role order
- Each role shows:
  - Role image (if present)
  - Guild-facing title (primary)
  - Operational title (secondary)
  - Short description
  - Claim approval required indicator
  - Badge enabled indicator
- "Claim Role" button (links to external form with role preselected)

### Role Detail Page

**URL:** `/projects/{project_id}/roles/{role_slug}/`

**Sections:**
1. **Role Header**
   - Image
   - Guild title
   - Operational title
   - Description
   - Cluster

2. **Role Configuration**
   - Claim approval required
   - Badge enabled
   - Badge approval required

3. **Claims for This Role**
   - List all claims (paginated)
   - Show: claimant, status, created date, term status, badge summary
   - Filter by status

4. **Badge Statistics**
   - Counts by status (requested, needs_info, approved, issued, denied, canceled)

5. **Admin Actions** (permission-gated)
   - Approve role
   - Change role status
   - Review claims
   - Review badge requests

### Submission Form Updates

**New Field: "What changed since last revision?"**

**Field Configuration:**
- **Label:** "What changed since the last revision?"
- **Helper text:** "Optional but recommended. Briefly describe substantive changes so reviewers and future readers can understand what evolved and why. Not required for minor or editorial edits."
- **Placeholder:** "Example: Clarified workgroup role in determining rough consensus; added glossary; no change to core governance principles."
- **Validation:** Optional, never blocks submission
- **Storage:** Part of revision's public context
- **Display:** Prominently in revision history

## Permissions Matrix

| Action | User | Editor | Admin | Project Admin |
|--------|------|--------|-------|---------------|
| Create role | ✅ | ✅ | ✅ | ✅ |
| Approve role | ❌ | ✅ | ✅ | ✅ |
| Change role status (limited) | ✅ (own draft) | ✅ | ✅ | ✅ |
| Change role status (any) | ❌ | ✅ | ✅ | ✅ |
| Create claim | ✅ | ✅ | ✅ | ✅ |
| Approve claim | ❌ | ✅ | ✅ | ✅ |
| Change claim status (own) | ✅ (pause) | ✅ | ✅ | ✅ |
| Change claim status (any) | ❌ | ✅ | ✅ | ✅ |
| Request badge | ✅ | ✅ | ✅ | ✅ |
| Approve badge | ❌ | ❌ | ❌ | ✅ |
| Issue badge | ❌ | ❌ | ❌ | ✅ |
| Manage clusters | ❌ | ❌ | ❌ | ✅ |
| **Submit role image** | ✅ | ✅ | ✅ | ✅ |
| **Vote on role image** | ✅ | ✅ | ✅ | ✅ |
| **Promote role image to primary** | ❌ | ❌ | ❌ | ✅ |
| **Hide/unhide role image** | ❌ | ❌ | ❌ | ✅ |
| **Remove role image** | ❌ | ❌ | ❌ | ✅ |
| **Add admin note to role image** | ❌ | ❌ | ❌ | ✅ |

## JSON Import Schema

### Role Import Format

```json
{
  "roles": [
    {
      "roleSlug": "bridger",
      "titleGuild": "Bridger",
      "titleOperational": "Director",
      "clusterSlug": "core-stewardship",
      "description": "Steward strategic, ethical, and narrative coherence across layers.",
      "imageUrl": "https://.../roles/bridger.png",
      "claimRequiresApproval": false,
      "badgeEnabled": true,
      "badgeRequiresApproval": true,
      "publicVisible": true
    }
  ]
}
```

### Import Behavior

- **Idempotent:** Safe to re-run
- **Matching:** By `roleSlug` within project
- **Update:** If role exists, update fields
- **No duplication:** Never creates duplicates

## API Endpoints

### Clusters

- `GET /api/projects/{id}/clusters/` - List clusters
- `POST /api/projects/{id}/clusters/` - Create cluster
- `GET /api/clusters/{id}/` - Get cluster
- `PATCH /api/clusters/{id}/` - Update cluster
- `DELETE /api/clusters/{id}/` - Archive cluster

### Roles

- `GET /api/projects/{id}/roles/` - List roles (filterable by cluster, status)
- `POST /api/projects/{id}/roles/` - Create role
- `POST /api/projects/{id}/roles/import/` - Import roles from JSON
- `GET /api/roles/{id}/` - Get role details
- `PATCH /api/roles/{id}/` - Update role
- `POST /api/roles/{id}/approve/` - Approve role
- `POST /api/roles/{id}/status/` - Change role status

### Claims

- `GET /api/projects/{id}/claims/` - List claims
- `GET /api/roles/{id}/claims/` - List claims for role
- `POST /api/roles/{id}/claims/` - Create claim
- `GET /api/claims/{id}/` - Get claim details
- `PATCH /api/claims/{id}/` - Update claim
- `POST /api/claims/{id}/approve/` - Approve claim (if required)
- `POST /api/claims/{id}/status/` - Change claim status

### Badges

- `GET /api/projects/{id}/badges/` - List badges
- `GET /api/claims/{id}/badges/` - List badges for claim
- `POST /api/claims/{id}/badges/` - Request badge
- `GET /api/badges/{id}/` - Get badge details
- `PATCH /api/badges/{id}/` - Update badge
- `POST /api/badges/{id}/approve/` - Approve badge
- `POST /api/badges/{id}/issue/` - Issue badge (set inscription_id)

### Role Images

- `GET /api/roles/{id}/images/` - List role image proposals (with vote counts, sortable)
- `POST /api/roles/{id}/images/` - Submit role image proposal
- `GET /api/role-images/{id}/` - Get role image details
- `POST /api/role-images/{id}/vote/` - Vote on role image (upvote/downvote)
- `DELETE /api/role-images/{id}/vote/` - Remove vote
- `POST /api/role-images/{id}/promote/` - Promote to primary (Project Admin only)
- `POST /api/role-images/{id}/hide/` - Hide image (Project Admin only)
- `POST /api/role-images/{id}/unhide/` - Unhide image (Project Admin only)
- `DELETE /api/role-images/{id}/` - Remove image (Project Admin only)
- `PATCH /api/role-images/{id}/note/` - Add/update admin note (Project Admin only)

## API Schemas

### 9.4.5 RoleImage Schema

```json
{
  "id": "rimg_abc123",
  "project_id": "proj_metalayer",
  "role_id": "rol_bridger",
  "source_type": "ordinal",
  "image_url": "https://ordinals.com/content/a455e1c4...e9aa72i0",
  "file_path": null,
  "chain": "bitcoin",
  "inscription_id": "a455e1c4ca82bc15c2b0bde0eb647f09d5117e8203054bbb729f48f0d9e9aa72i0",
  "content_type": "image/png",
  "is_primary": false,
  "is_hidden": false,
  "upvotes": 12,
  "downvotes": 3,
  "net_score": 9,
  "admin_note": null,
  "submitted_by_id": 42,
  "submitted_by_name": "Alice",
  "submitted_at": "2026-02-09T12:00:00Z",
  "promoted_by_id": null,
  "promoted_at": null,
  "updated_at": "2026-02-09T15:30:00Z"
}
```

**Source Types:**
- `upload`: Image uploaded to server (stored in `file_path`, served via `image_url`)
- `url`: External image URL (stored in `image_url`)
- `ordinal`: Bitcoin inscription reference (metadata in `chain`, `inscription_id`, `content_type`)

**Ordinal Metadata:**
- Optional for `upload` and `url` sources
- Required for `ordinal` source
- Supports images, HTML, or other visual content types

### 9.4.6 RoleImageVote Schema

```json
{
  "id": 123,
  "image_id": "rimg_abc123",
  "user_id": 42,
  "value": 1,
  "created_at": "2026-02-09T12:05:00Z",
  "updated_at": "2026-02-09T12:05:00Z"
}
```

**Vote Values:**
- `1`: Upvote
- `-1`: Downvote

**Vote Updates:**
- Users can change their vote at any time
- Changing vote updates the existing `RoleImageVote` record
- Aggregated counts (`upvotes`, `downvotes`, `net_score`) are recalculated on each vote change

## Anti-Spam Controls

### Role Creation
1. **Email verification required** (baseline)
2. **Rate limiting:** Max 5 roles per user per day
3. **Account age:** Must be > 24 hours old
4. **Friction for new accounts:** Require one approved claim before creating roles

### Claim Creation
1. **Email verification required**
2. **Rate limiting:** Max 10 claims per user per day
3. **One claim per role per user** (can't claim same role twice)

### Badge Requests
1. **Rate limiting:** Max 5 badge requests per user per day
2. **Must have active claim** to request badge

### Role Image Submissions
1. **Email verification required**
2. **Rate limiting:** Max 10 image proposals per user per day
3. **File size limit:** Max 10MB for uploads
4. **Content validation:** Images must be valid image formats (PNG, JPG, GIF, WebP, SVG)
5. **Ordinal validation:** Inscription ID must be valid and content must be accessible

## MVP Acceptance Criteria

MVP is complete when:

1. ✅ Admin can import roles JSON into a project without duplication
2. ✅ Any user can propose a new role (draft)
3. ✅ Editor/Admin/Project Admin can approve a role
4. ✅ Any user can claim an approved role
5. ✅ Claims respect role setting: approval required vs not
6. ✅ Any user can request a badge for a claim
7. ✅ Project Admin can approve and issue badge, including setting inscription_id
8. ✅ Roles, claims, and badges all support status changes with audit trails
9. ✅ Role directory page with search and cluster filtering
10. ✅ Role detail page showing all claims and badge stats
11. ✅ Start Here page for onboarding
12. ✅ Inscriptions page explaining ordinal badges
13. ✅ Submission form includes "what changed" field for revisions
14. ✅ **Users can submit role image proposals** (upload, URL, or ordinal) and vote (upvote/downvote)
15. ✅ **Project Admin can promote a primary image** for a role
16. ✅ **Role Images page** displays gallery with vote totals, sortable by net score
17. ✅ **Image Detail page** shows image, submitter, timestamps, voting interface, and admin actions

## Implementation Phases

### Phase 1: Core Models (Week 1)
- Create Cluster, Role, Claim, Badge, StatusChange models
- Create RoleImage and RoleImageVote models
- Write migrations
- Unit tests

### Phase 2: JSON Import (Week 1)
- Role import endpoint
- Idempotent import logic
- Import validation

### Phase 3: API Development (Week 2)
- All CRUD endpoints for clusters, roles, claims, badges
- Role image submission, voting, and admin endpoints
- Approval endpoints
- Status change endpoints
- Permission enforcement

### Phase 4: UI - Directory & Detail (Week 3)
- Role directory page with search/filter
- Role detail page with claims and badges
- Role Images page with gallery and voting
- Image Detail page with voting and admin actions
- Claim role flow
- Badge request flow

### Phase 5: UI - Admin & Onboarding (Week 3)
- Admin review dashboards
- Role image promotion and moderation UI
- Start Here page
- Inscriptions page
- Submission form updates

### Phase 6: Testing & Refinement (Week 4)
- Integration tests
- UI tests for role images and voting
- Anti-spam controls (including image submissions)
- Performance optimization

### Phase 7: Initial Data (Week 5)
- Import Meta-Layer roles
- Create initial clusters
- Documentation

## Open Questions

### Resolved ✅
- [x] Term model for claims? → Yes, optional fields added
- [x] Anti-spam controls? → Email verification + rate limiting + account age
- [x] Public directory at launch? → Yes, per project
- [x] Badge approval scope? → Project Admin only

### Still Open ❓
- [ ] Invitation expiration period for badges? (suggest 30 days)
- [ ] Should we support badge transfers between users?
- [ ] Should claims be transferable?
- [ ] Maximum number of active claims per user per project?

## Success Metrics

- ✅ Meta-Layer roles imported successfully
- ✅ Users can discover and claim roles without friction
- ✅ Badge request and approval workflow is clear
- ✅ Admin dashboards provide efficient review queues
- ✅ Audit trails capture all status changes
- ✅ Anti-spam controls prevent abuse
- ✅ Ordinal inscription IDs properly stored and displayed
- ✅ Start Here page reduces onboarding confusion
- ✅ Revision history clearly shows "what changed"
