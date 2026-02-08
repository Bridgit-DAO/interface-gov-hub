# RFC: Projects, Workgroups, and Guilds Feature

**Status:** Planning  
**Feature Branch:** `feature/projects-workgroups-guilds`  
**PM Agent:** RFC Project Manager (9e2eef24-6131-41f1-b110-742b5ba9f1f1)  
**Date:** 2026-02-08

## Executive Summary

This RFC proposes adding three new organizational entities to the datatracker system: **Projects**, **Workgroups**, and **Guilds**. Projects will become the central organizing principle of the schema, with all submissions, documents, and workgroups required to be associated with a project. Guilds will provide cross-project collaboration structures.

## Requirements

### 1. Projects
Projects are the **primary driver** of the schema. Every submission, document, and workgroup must be associated with a project.

**Schema:**
- `name` (string, required) - Project name
- `submitted_by` (ForeignKey to Person) - User who submitted the project
- `approval_status` (choice field) - Status of project approval
- `description` (text, optional) - Project description
- `created_at` (datetime) - Creation timestamp
- `updated_at` (datetime) - Last update timestamp

**Status Options (Descriptive, not evaluative):**
- `proposed` - Registered but little/no active work yet
- `active` - Actively hosting drafts, workgroups, or deliberation
- `stabilizing` - Focused on stabilizing drafts for RFC promotion
- `maintaining` - Published RFCs, focused on stewardship and evolution
- `dormant` - Currently inactive but preserved for future resumption
- `concluded` - Intentionally completed its scope
- `archived` - No longer active, kept for historical reference

**Additional Fields:**
- `status_reason` (text) - Free-text explanation of current status
- `last_activity` (datetime) - Timestamp of last activity
- `superseded_by` (ForeignKey to Project, optional) - Link to successor project
- `approval_status` (choice) - Admin approval state (pending/approved/rejected)

**Relationships:**
- One-to-many with Submissions
- One-to-many with Documents
- One-to-many with Workgroups
- Many-to-many with Users (project members)

### 2. Workgroups
Workgroups are task-focused groups within a project.

**Schema:**
- `name` (string, required) - Workgroup name
- `project` (ForeignKey to Project, required) - Associated project
- `status` (choice field) - Current workgroup status
- `coordinator` (ForeignKey to Person) - Workgroup coordinator (formerly "chair")
- `description` (text, optional) - Workgroup description
- `created_at` (datetime) - Creation timestamp
- `updated_at` (datetime) - Last update timestamp

**Status Options:**
- `active` - Currently working
- `inactive` - Paused
- `completed` - Work finished
- `archived` - Historical record

**Approval:**
- Workgroups require approval by editor or admin
- Only approved workgroups in a project are displayed as submission options
- Promotion of Draft to RFC requires an associated Workgroup
- Workgroups assess and signal rough consensus (do not exercise unilateral authority)
- Coordinators facilitate but do not decide outcomes

**Relationships:**
- Many-to-one with Project (required)
- Many-to-many with Users (workgroup members)
- One-to-many with Documents (workgroup outputs)

### 3. Guilds
Guilds are cross-project collaboration groups. They are **NOT** tied to specific projects.

**Schema:**
- `name` (string, required) - Guild name
- `submitted_by` (ForeignKey to Person) - User who created the guild
- `approval_status` (choice field) - Status of guild approval
- `description` (text, optional) - Guild description
- `created_at` (datetime) - Creation timestamp
- `updated_at` (datetime) - Last update timestamp

**Guild Roles:**
- `initiator` - User who created the guild (automatically becomes admin)
- `admin` - Can manage guild membership and add other admins
- `member` - Regular guild member

**Approval:**
- ✅ No approval required - instant registration
- Initiator can add/remove members
- Initiator can promote members to admin
- Admins can add/remove members and other admins

**Membership:**
- Invitation-based: Initiator/admin sends email invitation
- Recipient must approve invitation to join
- Members can leave at any time

**Relationships:**
- Many-to-many with Users (guild members with roles)
- No direct relationship to Projects (cross-project by design)

### 4. Terminology Change
Replace all instances of "chair" with "coordinator" in the interface:
- Database field names
- UI labels
- API responses
- Documentation

## Schema Changes

### New Models

#### Project Model
```python
class Project(models.Model):
    name = models.CharField(max_length=255, unique=True)
    initiator = ForeignKey(Person, related_name='initiated_projects')
    
    # Status (descriptive, not evaluative)
    status = models.CharField(
        max_length=20,
        choices=[
            ('proposed', 'Proposed'),
            ('active', 'Active'),
            ('stabilizing', 'Stabilizing'),
            ('maintaining', 'Maintaining'),
            ('dormant', 'Dormant'),
            ('concluded', 'Concluded'),
            ('archived', 'Archived'),
        ],
        default='proposed'
    )
    status_reason = models.TextField(blank=True, help_text="Explanation of current status")
    
    # Admin approval
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Admin Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )
    
    description = models.TextField(blank=True)
    last_activity = models.DateTimeField(default=timezone.now)
    superseded_by = ForeignKey('self', null=True, blank=True, related_name='supersedes')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['approval_status', 'status']),
            models.Index(fields=['-last_activity']),
        ]
```

#### Workgroup Model
```python
class Workgroup(models.Model):
    name = models.CharField(max_length=255)
    project = ForeignKey(Project, related_name='workgroups')
    coordinator = ForeignKey(Person, related_name='coordinated_workgroups', null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('completed', 'Completed'),
            ('archived', 'Archived'),
        ],
        default='active'
    )
    
    # Editor/Admin approval required
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Approval'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        default='pending'
    )
    
    description = models.TextField(blank=True)
    members = models.ManyToManyField(Person, related_name='workgroup_memberships', blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['project', 'name']
        unique_together = [['project', 'name']]
        indexes = [
            models.Index(fields=['project', 'approval_status']),
            models.Index(fields=['project', 'status']),
        ]
    
    def is_available_for_submission(self):
        """Only approved workgroups can be selected during submission"""
        return self.approval_status == 'approved'
```

#### Guild Model
```python
class Guild(models.Model):
    name = models.CharField(max_length=255, unique=True)
    initiator = ForeignKey(Person, related_name='initiated_guilds')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
        ]

class GuildMembership(models.Model):
    """Guild membership with roles"""
    ROLE_CHOICES = [
        ('initiator', 'Initiator'),
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]
    
    guild = ForeignKey(Guild, related_name='memberships')
    person = ForeignKey(Person, related_name='guild_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = [['guild', 'person']]
        indexes = [
            models.Index(fields=['guild', 'role']),
        ]

class GuildInvitation(models.Model):
    """Email-based guild invitations"""
    guild = ForeignKey(Guild, related_name='invitations')
    invited_by = ForeignKey(Person, related_name='sent_guild_invitations')
    invited_email = models.EmailField()
    invited_person = ForeignKey(Person, null=True, blank=True, related_name='received_guild_invitations')
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('declined', 'Declined'),
            ('expired', 'Expired'),
        ],
        default='pending'
    )
    
    invitation_token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    responded_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['invitation_token']),
            models.Index(fields=['invited_email', 'status']),
        ]
```

### Modified Models

#### Submission Model Changes
Add required project foreign key:
```python
class Submission(models.Model):
    # ... existing fields ...
    project = ForeignKey('Project', related_name='submissions')  # NEW - REQUIRED
```

#### Document Model Changes
Add optional project foreign key (documents can exist without projects initially):
```python
# In ietf/doc/models.py
class Document(models.Model):
    # ... existing fields ...
    project = ForeignKey('Project', related_name='documents', null=True, blank=True)  # NEW
    workgroup = ForeignKey('Workgroup', related_name='documents', null=True, blank=True)  # NEW
```

## Migration Strategy

### Phase 1: Add New Models (Non-Breaking)
1. Create Project, Workgroup, and Guild models
2. Add nullable project/workgroup fields to existing models
3. Create database migrations
4. Deploy to dev environment

### Phase 2: Data Migration
1. Create initial "Meta-Layer" project (initiator: daveed@bridgit.io, status: active, approved)
2. Create initial "Governance" workgroup under Meta-Layer (approved)
3. Create default "Legacy" project for existing data
4. Associate all existing submissions/documents with "Legacy" project
5. Migrate existing Group data to Workgroups where appropriate
6. Test data integrity

### Phase 3: Make Projects Required
1. Update Submission model to require project
2. Update forms and validation
3. Update API endpoints
4. Deploy to production

### Phase 4: UI Updates
1. Add project selection to submission forms
2. Add workgroup management interface
3. Add guild management interface
4. Update all "chair" references to "coordinator"

## API Changes

### New Endpoints

#### Projects
- `GET /api/projects/` - List all projects
- `POST /api/projects/` - Create new project
- `GET /api/projects/{id}/` - Get project details
- `PATCH /api/projects/{id}/` - Update project
- `DELETE /api/projects/{id}/` - Archive project
- `POST /api/projects/{id}/approve/` - Approve project
- `POST /api/projects/{id}/reject/` - Reject project

#### Workgroups
- `GET /api/workgroups/` - List all workgroups
- `POST /api/workgroups/` - Create new workgroup
- `GET /api/workgroups/{id}/` - Get workgroup details
- `PATCH /api/workgroups/{id}/` - Update workgroup
- `DELETE /api/workgroups/{id}/` - Archive workgroup
- `POST /api/workgroups/{id}/members/` - Add member
- `DELETE /api/workgroups/{id}/members/{person_id}/` - Remove member

#### Guilds
- `GET /api/guilds/` - List all guilds
- `POST /api/guilds/` - Create new guild
- `GET /api/guilds/{id}/` - Get guild details
- `PATCH /api/guilds/{id}/` - Update guild
- `DELETE /api/guilds/{id}/` - Archive guild
- `POST /api/guilds/{id}/approve/` - Approve guild
- `POST /api/guilds/{id}/reject/` - Reject guild
- `POST /api/guilds/{id}/members/` - Add member
- `DELETE /api/guilds/{id}/members/{person_id}/` - Remove member

### Modified Endpoints
- `POST /api/submissions/` - Now requires `project` field
- `GET /api/submissions/` - Include project information
- `GET /api/documents/` - Include project and workgroup information

## UI Changes

### New Pages
1. **Projects List** (`/projects/`)
   - List all approved projects with filtering by status
   - Highlight "Meta-Layer" as foundational project
   - Search functionality
   - Create new project button (with clear messaging about stewardship responsibility)

2. **Project Detail** (`/projects/{id}/`)
   - Project information
   - List of submissions
   - List of documents
   - List of workgroups
   - Member management

3. **Workgroups List** (`/workgroups/`)
   - List all workgroups with filtering
   - Grouped by project

4. **Workgroup Detail** (`/workgroups/{id}/`)
   - Workgroup information
   - Coordinator information (not "chair")
   - Member list
   - Associated documents

5. **Guilds List** (`/guilds/`)
   - List all guilds with filtering by approval status
   - Create new guild button

6. **Guild Detail** (`/guilds/{id}/`)
   - Guild information
   - Member list
   - Activity feed

### Modified Pages
1. **Submission Form**
   - Add project selection dropdown (required, defaults to Meta-Layer)
   - Add workgroup selection (filtered by selected project, only approved workgroups shown)
   - Clear messaging: "Most users submit to existing projects like Meta-Layer"

2. **Document Detail**
   - Display associated project
   - Display associated workgroup

3. **All Pages with "Chair" terminology**
   - Replace with "Coordinator"

## Testing Requirements

### Unit Tests
- [ ] Project model CRUD operations
- [ ] Workgroup model CRUD operations
- [ ] Guild model CRUD operations
- [ ] Project approval workflow
- [ ] Guild approval workflow
- [ ] Member management for workgroups
- [ ] Member management for guilds
- [ ] Submission requires project validation

### Integration Tests
- [ ] Create project and associate submissions
- [ ] Create workgroup within project
- [ ] Create guild and add members
- [ ] Approve/reject project workflow
- [ ] Approve/reject guild workflow
- [ ] Migration from legacy data

### UI Tests
- [ ] Project creation form
- [ ] Workgroup creation form
- [ ] Guild creation form
- [ ] Project detail page
- [ ] Workgroup detail page
- [ ] Guild detail page
- [ ] Submission form with project selection
- [ ] All "coordinator" labels (no "chair")

## Security Considerations

### Permissions
1. **Project Creation**
   - Any authenticated user can create a project
   - Projects require admin approval before becoming active
   - Project initiator becomes project steward automatically

2. **Project Approval**
   - Only admins can approve projects
   - Approval is required before project can host submissions

3. **Workgroup Management**
   - Project members can create workgroups
   - Workgroups require editor or admin approval
   - Only approved workgroups appear in submission forms
   - Coordinators can manage workgroup members

4. **Guild Creation**
   - Any authenticated user can create a guild
   - ✅ No approval required - instant registration
   - Guild initiator automatically becomes admin

5. **Guild Membership**
   - Initiator/admins send email invitations
   - Recipients must accept invitation to join
   - Initiator/admins can add other admins
   - Admins can manage membership

### Data Access
- Users can view all approved projects, workgroups, and guilds
- Users can only edit projects/workgroups/guilds they created or coordinate
- Admins can edit all entities

## Performance Considerations

1. **Indexing**
   - Add indexes on `approval_status` fields
   - Add indexes on foreign keys (project, workgroup)
   - Add composite indexes for common queries

2. **Caching**
   - Cache project lists
   - Cache guild lists
   - Cache workgroup lists by project

3. **Query Optimization**
   - Use `select_related` for project/workgroup queries
   - Use `prefetch_related` for member lists

## Documentation Requirements

1. **User Documentation**
   - How to create a project
   - How to create a workgroup
   - How to create a guild
   - Understanding approval workflows

2. **Developer Documentation**
   - API documentation for new endpoints
   - Migration guide
   - Model relationship diagrams

3. **Admin Documentation**
   - Project approval process
   - Guild approval process
   - Member management

## Timeline Estimate

### Week 1: Models and Migrations
- Create new models
- Write migrations
- Unit tests for models

### Week 2: API Development
- Create API endpoints
- API tests
- API documentation

### Week 3: UI Development
- Create new pages
- Update existing pages
- Replace "chair" with "coordinator"

### Week 4: Testing and Refinement
- Integration testing
- UI testing
- Bug fixes

### Week 5: Migration and Deployment
- Data migration scripts
- Staging deployment
- Production deployment

## Design Decisions (Resolved)

1. **Project Hierarchy:** ❌ No - Projects are flat, no parent/child relationships
2. **Workgroup Limits:** ❌ No - Projects can have unlimited workgroups
3. **Guild Membership:** ✅ Invitation-based - Submitter sends email invitation, recipient must approve
4. **Legacy Data:** Will maintain "Legacy" project indefinitely for historical data
5. **Permissions:** Project creators become project stewards automatically

## Meta-Layer Governance Principles

### Core Philosophy
- **Projects are optional stewardship containers**, not prerequisites for participation
- Most users will NOT create projects
- Most users will: submit drafts to existing projects, comment on drafts/RFCs, join workgroups or guilds
- Projects exist to provide scope, continuity, and stewardship for long-lived bodies of work

### Participation Model
- ✅ Anyone can submit an ML-Draft
- ✅ Anyone can comment on drafts and RFCs
- ✅ Anyone can create or join a Guild
- ⚠️ A Project is only required when stewarding an ongoing body of governance work
- ✅ Every draft and RFC must be associated with a Project (most users attach to existing)

### Approval Workflows
- **Projects:** Require admin approval
- **Workgroups:** Require editor or admin approval
- **Guilds:** No approval required (instant registration)

### Initial Data
- **Project:** Meta-Layer (initiator: daveed@bridgit.io, status: active)
- **Workgroup:** Governance (project: Meta-Layer)

## Success Criteria

- [ ] All new models created and migrated
- [ ] All existing data migrated to new schema
- [ ] All API endpoints functional
- [ ] All UI pages created and functional
- [ ] All "chair" references replaced with "coordinator"
- [ ] All tests passing (unit, integration, UI)
- [ ] Documentation complete
- [ ] Zero data loss during migration
- [ ] Performance metrics within acceptable ranges

## Risks and Mitigations

### Risk 1: Data Migration Complexity
**Mitigation:** Create comprehensive backup before migration, test on dev/staging first

### Risk 2: Breaking Existing Workflows
**Mitigation:** Phase migrations, maintain backward compatibility where possible

### Risk 3: Performance Impact
**Mitigation:** Proper indexing, caching strategy, query optimization

### Risk 4: User Confusion
**Mitigation:** Clear documentation, gradual rollout, user training

## Next Steps

1. Review and approve this RFC
2. Create detailed technical specifications
3. Set up development environment
4. Begin Phase 1 implementation
5. Schedule regular check-ins with stakeholders
