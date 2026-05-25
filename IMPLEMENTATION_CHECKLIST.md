# Implementation Checklist: Projects, Workgroups, and Guilds

**Feature Branch:** `feature/projects-workgroups-guilds`  
**RFC Document:** `RFC_PROJECTS_WORKGROUPS_GUILDS.md`  
**Status:** Planning Complete - Ready for Implementation

## Phase 1: Models and Migrations (Week 1)

### Database Models - Core
- [ ] Create `Project` model in new `ietf/project/models.py`
- [ ] Create `Workgroup` model in new `ietf/workgroup/models.py`
- [ ] Create `Guild` model in new `ietf/guild/models.py`
- [ ] Create `GuildMembership` model in `ietf/guild/models.py`
- [ ] Create `GuildInvitation` model in `ietf/guild/models.py`
- [ ] Add `project` ForeignKey to `Submission` model (nullable initially)
- [ ] Add `project` ForeignKey to `Document` model (nullable)
- [ ] Add `workgroup` ForeignKey to `Document` model (nullable)

### Database Models - Roles System
- [ ] Create `Cluster` model in new `ietf/roles/models.py`
- [ ] Create `Role` model in `ietf/roles/models.py`
- [ ] Create `Claim` model in `ietf/roles/models.py`
- [ ] Create `Badge` model in `ietf/roles/models.py`
- [ ] Create `StatusChange` model in `ietf/roles/models.py` (audit trail)

### Migrations
- [ ] Create migration for Project model
- [ ] Create migration for Workgroup model
- [ ] Create migration for Guild, GuildMembership, GuildInvitation models
- [ ] Create migration for Cluster model
- [ ] Create migration for Role model
- [ ] Create migration for Claim model
- [ ] Create migration for Badge model
- [ ] Create migration for StatusChange model
- [ ] Create migration to add project field to Submission
- [ ] Create migration to add project/workgroup fields to Document
- [ ] Create migration to add "what_changed" field to Submission/Revision
- [ ] Create data migration for Meta-Layer project
- [ ] Create data migration for Governance workgroup
- [ ] Create data migration for "Legacy" project
- [ ] Create migration to populate legacy data

### Unit Tests - Core
- [ ] Test Project model creation
- [ ] Test Project approval workflow
- [ ] Test Workgroup model creation
- [ ] Test Workgroup status changes
- [ ] Test Guild model creation (instant registration)
- [ ] Test GuildMembership role management
- [ ] Test GuildInvitation email flow
- [ ] Test Project-Submission relationship
- [ ] Test Project-Document relationship
- [ ] Test Workgroup-Document relationship
- [ ] Test member management for Workgroups
- [ ] Test member management for Guilds

### Unit Tests - Roles System
- [ ] Test Cluster model creation
- [ ] Test Role model creation
- [ ] Test Role approval workflow
- [ ] Test Role status transitions
- [ ] Test Claim model creation
- [ ] Test Claim approval (when required)
- [ ] Test Claim status transitions
- [ ] Test Claim term expiration
- [ ] Test Badge model creation
- [ ] Test Badge request workflow
- [ ] Test Badge approval workflow
- [ ] Test Badge issuance with inscription_id
- [ ] Test StatusChange audit trail
- [ ] Test Role JSON import (idempotent)
- [ ] Test anti-spam rate limiting

## Phase 2: API Development (Week 2)

### Roles System API

#### Clusters API
- [ ] Create `ClusterViewSet` in `ietf/roles/views.py`
- [ ] Implement `GET /api/projects/{id}/clusters/`
- [ ] Implement `POST /api/projects/{id}/clusters/`
- [ ] Implement `GET /api/clusters/{id}/`
- [ ] Implement `PATCH /api/clusters/{id}/`
- [ ] Implement `DELETE /api/clusters/{id}/`
- [ ] Add cluster serializer
- [ ] Add cluster filters

#### Roles API
- [ ] Create `RoleViewSet` in `ietf/roles/views.py`
- [ ] Implement `GET /api/projects/{id}/roles/`
- [ ] Implement `POST /api/projects/{id}/roles/`
- [ ] Implement `POST /api/projects/{id}/roles/import/` (JSON import)
- [ ] Implement `GET /api/roles/{id}/`
- [ ] Implement `PATCH /api/roles/{id}/`
- [ ] Implement `POST /api/roles/{id}/approve/`
- [ ] Implement `POST /api/roles/{id}/status/`
- [ ] Add role serializer
- [ ] Add role filters (cluster, status, public_visible)

#### Claims API
- [ ] Create `ClaimViewSet` in `ietf/roles/views.py`
- [ ] Implement `GET /api/projects/{id}/claims/`
- [ ] Implement `GET /api/roles/{id}/claims/`
- [ ] Implement `POST /api/roles/{id}/claims/`
- [ ] Implement `GET /api/claims/{id}/`
- [ ] Implement `PATCH /api/claims/{id}/`
- [ ] Implement `POST /api/claims/{id}/approve/`
- [ ] Implement `POST /api/claims/{id}/status/`
- [ ] Add claim serializer
- [ ] Add claim filters (status, claimant, role)

#### Badges API
- [ ] Create `BadgeViewSet` in `ietf/roles/views.py`
- [ ] Implement `GET /api/projects/{id}/badges/`
- [ ] Implement `GET /api/claims/{id}/badges/`
- [ ] Implement `POST /api/claims/{id}/badges/`
- [ ] Implement `GET /api/badges/{id}/`
- [ ] Implement `PATCH /api/badges/{id}/`
- [ ] Implement `POST /api/badges/{id}/approve/`
- [ ] Implement `POST /api/badges/{id}/issue/`
- [ ] Add badge serializer
- [ ] Add badge filters (status, badge_type)

### Project API
- [ ] Create `ProjectViewSet` in `ietf/project/views.py`
- [ ] Implement `GET /api/projects/`
- [ ] Implement `POST /api/projects/`
- [ ] Implement `GET /api/projects/{id}/`
- [ ] Implement `PATCH /api/projects/{id}/`
- [ ] Implement `DELETE /api/projects/{id}/`
- [ ] Implement `POST /api/projects/{id}/approve/`
- [ ] Implement `POST /api/projects/{id}/reject/`
- [ ] Add project serializer
- [ ] Add project filters

### Workgroup API
- [ ] Create `WorkgroupViewSet` in `ietf/workgroup/views.py`
- [ ] Implement `GET /api/workgroups/`
- [ ] Implement `POST /api/workgroups/`
- [ ] Implement `GET /api/workgroups/{id}/`
- [ ] Implement `PATCH /api/workgroups/{id}/`
- [ ] Implement `DELETE /api/workgroups/{id}/`
- [ ] Implement `POST /api/workgroups/{id}/members/`
- [ ] Implement `DELETE /api/workgroups/{id}/members/{person_id}/`
- [ ] Add workgroup serializer
- [ ] Add workgroup filters

### Guild API
- [ ] Create `GuildViewSet` in `ietf/guild/views.py`
- [ ] Implement `GET /api/guilds/`
- [ ] Implement `POST /api/guilds/` (instant registration, no approval)
- [ ] Implement `GET /api/guilds/{id}/`
- [ ] Implement `PATCH /api/guilds/{id}/`
- [ ] Implement `DELETE /api/guilds/{id}/`
- [ ] Implement `POST /api/guilds/{id}/invite/` (send email invitation)
- [ ] Implement `POST /api/guild-invitations/{token}/accept/`
- [ ] Implement `POST /api/guild-invitations/{token}/decline/`
- [ ] Implement `POST /api/guilds/{id}/members/{person_id}/promote/` (to admin)
- [ ] Implement `DELETE /api/guilds/{id}/members/{person_id}/`
- [ ] Add guild serializer
- [ ] Add guild membership serializer
- [ ] Add guild invitation serializer
- [ ] Add guild filters

### Modified APIs
- [ ] Update Submission API to include project field
- [ ] Update Submission API to require project on creation
- [ ] Update Document API to include project/workgroup fields
- [ ] Update serializers for modified models

### API Tests
- [ ] Test all Project API endpoints
- [ ] Test all Workgroup API endpoints
- [ ] Test all Guild API endpoints
- [ ] Test all Cluster API endpoints
- [ ] Test all Role API endpoints
- [ ] Test all Claim API endpoints
- [ ] Test all Badge API endpoints
- [ ] Test project approval workflow via API
- [ ] Test workgroup approval workflow via API
- [ ] Test guild invitation workflow via API
- [ ] Test role approval workflow via API
- [ ] Test claim approval workflow via API
- [ ] Test badge approval workflow via API
- [ ] Test role JSON import (idempotent)
- [ ] Test member management via API
- [ ] Test permission enforcement (all roles)
- [ ] Test validation rules
- [ ] Test anti-spam rate limiting

### API Documentation
- [ ] Document Project API endpoints
- [ ] Document Workgroup API endpoints
- [ ] Document Guild API endpoints
- [ ] Update Submission API documentation
- [ ] Update Document API documentation
- [ ] Add example requests/responses

## Phase 3: UI Development (Week 3)

### Templates - Core
- [ ] Create `ietf/project/templates/project/list.html`
- [ ] Create `ietf/project/templates/project/detail.html`
- [ ] Create `ietf/project/templates/project/create.html`
- [ ] Create `ietf/workgroup/templates/workgroup/list.html`
- [ ] Create `ietf/workgroup/templates/workgroup/detail.html`
- [ ] Create `ietf/workgroup/templates/workgroup/create.html`
- [ ] Create `ietf/guild/templates/guild/list.html`
- [ ] Create `ietf/guild/templates/guild/detail.html`
- [ ] Create `ietf/guild/templates/guild/create.html`
- [ ] Create `ietf/guild/templates/guild/invite.html`
- [ ] Create `ietf/guild/templates/guild/invitation_accept.html`

### Templates - Roles System
- [ ] Create `ietf/roles/templates/roles/directory.html` (role directory)
- [ ] Create `ietf/roles/templates/roles/detail.html` (role detail)
- [ ] Create `ietf/roles/templates/roles/create.html`
- [ ] Create `ietf/roles/templates/claims/create.html`
- [ ] Create `ietf/roles/templates/claims/detail.html`
- [ ] Create `ietf/roles/templates/badges/request.html`
- [ ] Create `ietf/roles/templates/badges/detail.html`
- [ ] Create `ietf/roles/templates/admin/roles_queue.html`
- [ ] Create `ietf/roles/templates/admin/claims_queue.html`
- [ ] Create `ietf/roles/templates/admin/badges_queue.html`

### Templates - Onboarding
- [ ] Create `ietf/templates/start_here.html`
- [ ] Create `ietf/templates/inscriptions.html`

### Forms - Core
- [ ] Create `ProjectForm` in `ietf/project/forms.py`
- [ ] Create `WorkgroupForm` in `ietf/workgroup/forms.py`
- [ ] Create `GuildForm` in `ietf/guild/forms.py`
- [ ] Create `GuildInvitationForm` in `ietf/guild/forms.py`
- [ ] Update `SubmissionForm` to include project selection (default Meta-Layer)
- [ ] Add workgroup selection to submission form (filtered by project, approved only)
- [ ] Add "what_changed" field to revision form

### Forms - Roles System
- [ ] Create `ClusterForm` in `ietf/roles/forms.py`
- [ ] Create `RoleForm` in `ietf/roles/forms.py`
- [ ] Create `RoleImportForm` in `ietf/roles/forms.py` (JSON upload)
- [ ] Create `ClaimForm` in `ietf/roles/forms.py`
- [ ] Create `BadgeRequestForm` in `ietf/roles/forms.py`
- [ ] Create `BadgeApprovalForm` in `ietf/roles/forms.py`

### Views
- [ ] Create project list view
- [ ] Create project detail view
- [ ] Create project create view
- [ ] Create project update view
- [ ] Create project approve/reject views
- [ ] Create workgroup list view
- [ ] Create workgroup detail view
- [ ] Create workgroup create view
- [ ] Create workgroup update view
- [ ] Create guild list view
- [ ] Create guild detail view
- [ ] Create guild create view
- [ ] Create guild update view
- [ ] Create guild approve/reject views
- [ ] Update submission views for project selection

### URL Configuration
- [ ] Add project URLs to `ietf/project/urls.py`
- [ ] Add workgroup URLs to `ietf/workgroup/urls.py`
- [ ] Add guild URLs to `ietf/guild/urls.py`
- [ ] Include new URLs in main `urls.py`

### Navigation
- [ ] Add "Projects" to main navigation
- [ ] Add "Workgroups" to main navigation
- [ ] Add "Guilds" to main navigation
- [ ] Update breadcrumbs for new pages

### Terminology Changes (Chair → Coordinator)
- [ ] Search all templates for "chair" references
- [ ] Replace "chair" with "coordinator" in templates
- [ ] Search all Python files for "chair" references
- [ ] Update field labels in forms
- [ ] Update display text in views
- [ ] Update help text in models
- [ ] Update API documentation
- [ ] Update user documentation

## Phase 4: Testing and Refinement (Week 4)

### Integration Tests
- [ ] Test complete project creation workflow
- [ ] Test project approval workflow
- [ ] Test workgroup creation within project
- [ ] Test guild creation workflow
- [ ] Test guild approval workflow
- [ ] Test submission with project association
- [ ] Test document association with project/workgroup
- [ ] Test member management workflows
- [ ] Test permission enforcement across workflows

### UI Tests
- [ ] Test project list page rendering
- [ ] Test project detail page rendering
- [ ] Test project creation form
- [ ] Test workgroup list page rendering
- [ ] Test workgroup detail page rendering
- [ ] Test workgroup creation form
- [ ] Test guild list page rendering
- [ ] Test guild detail page rendering
- [ ] Test guild creation form
- [ ] Test submission form with project selection
- [ ] Test all coordinator labels (no "chair")
- [ ] Test responsive design on all new pages
- [ ] Test accessibility compliance

### Performance Testing
- [ ] Test project list query performance
- [ ] Test workgroup list query performance
- [ ] Test guild list query performance
- [ ] Test submission form load time with project dropdown
- [ ] Verify indexes are being used
- [ ] Test caching effectiveness

### Bug Fixes
- [ ] Address any issues found in testing
- [ ] Fix any UI/UX issues
- [ ] Resolve any performance bottlenecks
- [ ] Fix any accessibility issues

## Phase 5: Migration and Deployment (Week 5)

### Data Migration
- [ ] Create backup of production database
- [ ] Test migration script on copy of production data
- [ ] Create "Legacy" project
- [ ] Migrate existing submissions to Legacy project
- [ ] Migrate existing documents to Legacy project
- [ ] Verify data integrity after migration
- [ ] Test rollback procedure

### Deployment Preparation
- [ ] Update deployment scripts
- [ ] Update environment configuration
- [ ] Prepare deployment documentation
- [ ] Schedule deployment window
- [ ] Notify stakeholders

### Staging Deployment
- [ ] Deploy to staging environment
- [ ] Run data migration on staging
- [ ] Test all functionality on staging
- [ ] Verify performance on staging
- [ ] Get stakeholder approval

### Production Deployment
- [ ] Deploy to production
- [ ] Run data migration on production
- [ ] Verify all services are running
- [ ] Test critical workflows
- [ ] Monitor error logs
- [ ] Monitor performance metrics

### Post-Deployment
- [ ] Verify zero data loss
- [ ] Monitor system performance
- [ ] Address any immediate issues
- [ ] Collect user feedback
- [ ] Document lessons learned

## Documentation

### User Documentation
- [ ] Write "How to Create a Project" guide
- [ ] Write "How to Create a Workgroup" guide
- [ ] Write "How to Create a Guild" guide
- [ ] Write "Understanding Approval Workflows" guide
- [ ] Write "Managing Members" guide
- [ ] Update submission documentation
- [ ] Create FAQ document

### Developer Documentation
- [ ] Document new models and relationships
- [ ] Document API endpoints with examples
- [ ] Create migration guide
- [ ] Create model relationship diagrams
- [ ] Document permission system
- [ ] Update architecture documentation

### Admin Documentation
- [ ] Write project approval process guide
- [ ] Write guild approval process guide
- [ ] Write member management guide
- [ ] Document admin tools
- [ ] Create troubleshooting guide

## Success Metrics

- [ ] All tests passing (100% pass rate)
- [ ] Zero data loss during migration
- [ ] API response times < 200ms for list endpoints
- [ ] API response times < 100ms for detail endpoints
- [ ] Page load times < 2 seconds
- [ ] Zero critical bugs in production
- [ ] User satisfaction score > 4/5
- [ ] Documentation completeness > 95%

## Risk Mitigation

### Backup Strategy
- [ ] Create full database backup before migration
- [ ] Test restore procedure
- [ ] Document rollback steps
- [ ] Keep backups for 30 days

### Monitoring
- [ ] Set up error tracking
- [ ] Set up performance monitoring
- [ ] Set up usage analytics
- [ ] Configure alerts for critical issues

### Communication
- [ ] Notify users of upcoming changes
- [ ] Provide training materials
- [ ] Set up support channels
- [ ] Schedule Q&A sessions

## Notes

- Feature branch created: `feature/projects-workgroups-guilds`
- RFC document location: `/home/ubuntu/datatracker/RFC_PROJECTS_WORKGROUPS_GUILDS.md`
- PM Agent engaged: RFC Project Manager (9e2eef24-6131-41f1-b110-742b5ba9f1f1)
- All "chair" terminology must be replaced with "coordinator"
- Projects are REQUIRED for all new submissions
- Guilds are cross-project by design (no project association)

## Next Actions

1. Review RFC with stakeholders
2. Get approval to proceed
3. Set up development environment
4. Begin Phase 1: Models and Migrations
5. Schedule daily standups during implementation
