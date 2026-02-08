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

**Approval Status Options:**
- `pending` - Awaiting approval
- `approved` - Active project
- `rejected` - Not approved
- `archived` - Completed/inactive

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

**Approval Status Options:**
- `pending` - Awaiting approval
- `approved` - Active guild
- `rejected` - Not approved
- `archived` - Inactive

**Relationships:**
- Many-to-many with Users (guild members)
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
    submitted_by = ForeignKey(Person, related_name='submitted_projects')
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('archived', 'Archived'),
        ],
        default='pending'
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['approval_status']),
            models.Index(fields=['-created_at']),
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
    description = models.TextField(blank=True)
    members = models.ManyToManyField(Person, related_name='workgroup_memberships', blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['project', 'name']
        unique_together = [['project', 'name']]
        indexes = [
            models.Index(fields=['project', 'status']),
        ]
```

#### Guild Model
```python
class Guild(models.Model):
    name = models.CharField(max_length=255, unique=True)
    submitted_by = ForeignKey(Person, related_name='submitted_guilds')
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
            ('archived', 'Archived'),
        ],
        default='pending'
    )
    description = models.TextField(blank=True)
    members = models.ManyToManyField(Person, related_name='guild_memberships', blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['approval_status']),
            models.Index(fields=['-created_at']),
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
1. Create default "Legacy" project for existing data
2. Associate all existing submissions/documents with "Legacy" project
3. Migrate existing Group data to Workgroups where appropriate
4. Test data integrity

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
   - List all projects with filtering by approval status
   - Search functionality
   - Create new project button

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
   - Add project selection dropdown (required)
   - Add optional workgroup selection

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
   - Projects require approval before becoming active

2. **Project Approval**
   - Only admins/staff can approve projects

3. **Workgroup Management**
   - Project members can create workgroups
   - Coordinators can manage workgroup members

4. **Guild Creation**
   - Any authenticated user can create a guild
   - Guilds require approval before becoming active

5. **Guild Approval**
   - Only admins/staff can approve guilds

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

## Open Questions

1. **Project Hierarchy:** Should projects support parent/child relationships?
2. **Workgroup Limits:** Should there be a limit on workgroups per project?
3. **Guild Membership:** Should guild membership be automatic or require approval?
4. **Legacy Data:** How long should we maintain the "Legacy" project?
5. **Permissions:** Should project creators automatically become coordinators?

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
