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

## Additional UI Requirements

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

## Implementation Phases

### Phase 1: Core Models (Week 1)
- Create Cluster, Role, Claim, Badge, StatusChange models
- Write migrations
- Unit tests

### Phase 2: JSON Import (Week 1)
- Role import endpoint
- Idempotent import logic
- Import validation

### Phase 3: API Development (Week 2)
- All CRUD endpoints for clusters, roles, claims, badges
- Approval endpoints
- Status change endpoints
- Permission enforcement

### Phase 4: UI - Directory & Detail (Week 3)
- Role directory page with search/filter
- Role detail page with claims and badges
- Claim role flow
- Badge request flow

### Phase 5: UI - Admin & Onboarding (Week 3)
- Admin review dashboards
- Start Here page
- Inscriptions page
- Submission form updates

### Phase 6: Testing & Refinement (Week 4)
- Integration tests
- UI tests
- Anti-spam controls
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
