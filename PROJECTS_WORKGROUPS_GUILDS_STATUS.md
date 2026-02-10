# Projects, Workgroups, and Guilds System - Implementation Status

**Branch:** `feature/projects-workgroups-guilds`  
**Last Updated:** 2026-02-10  
**Overall Completion:** ~40% (Infrastructure and Core APIs Complete)

## Executive Summary

The Projects, Workgroups, and Guilds organizational system is partially implemented. The foundational infrastructure is complete, including all database models, helper functions, and core APIs for Projects, Workgroups, and Guilds. The Role Images feature is fully implemented. Remaining work includes Role/Claim/Badge APIs and all UI pages.

---

## ✅ Completed Components

### 1. Database Models (100% Complete - 10/10 models)

All models created with proper relationships, indexes, and constraints:

#### Core Organizational Models
- **Project** - Primary organizing entity
  - Status workflow (proposed → active → stabilizing → maintaining → dormant → concluded → archived)
  - Admin approval system (pending → approved/rejected)
  - Activity tracking and succession support
  - Relationships: workgroups, clusters, roles, claims, badges

- **Workgroup** - Task-focused groups within projects
  - Project relationship (required)
  - Coordinator role (formerly "chair")
  - Approval workflow (editor/admin)
  - Status: active, inactive, completed, archived

- **Guild** - Cross-project collaboration groups
  - Instant registration (no approval required)
  - Initiator automatically becomes admin
  - Status: active, archived

- **GuildMembership** - Guild membership with roles
  - Roles: initiator, admin, member
  - Unique constraint per guild/user

- **GuildInvitation** - Email-based invitation system
  - Token-based verification
  - 7-day expiration
  - Status: pending, accepted, declined, expired

#### Roles System Models
- **Cluster** - Organizational grouping of roles within projects
  - Project-scoped with ordering
  - Status: active, archived

- **Role** - Defined responsibilities within projects
  - Guild and operational titles
  - Approval workflow
  - Configuration: claim approval, badge settings
  - Public visibility control

- **Claim** - User declarations of role stewardship
  - Intent and evidence links
  - Optional term duration
  - Approval workflow (when required)
  - Status: active, pending_approval, paused, expired, revoked

- **Badge** - Recognition artifacts for claims
  - Multiple badge types (role_badge, founding_wave_badge, term_renewal_marker)
  - Custody modes (user_wallet, overweb_treasury)
  - Ordinal inscription support
  - Approval and issuance workflow

- **StatusChange** - Audit trail for all entities
  - Polymorphic entity tracking
  - Field-level change history
  - User attribution

#### Supporting Models (Already Existed)
- **RoleImage** - Visual representations with voting (fully implemented)
- **RoleImageVote** - User votes on role images (fully implemented)

**Database Script:** `create_projects_tables.py` - All 10 tables verified ✅

---

### 2. Helper Functions (100% Complete)

All ID generators and utility functions implemented:

```python
generate_project_id()           # proj_...
generate_workgroup_id()         # wg_...
generate_guild_id()             # guild_...
generate_cluster_id()           # clu_...
generate_role_id()              # rol_...
generate_claim_id()             # clm_...
generate_badge_id()             # bdg_...
generate_status_change_id()     # sc_...
generate_guild_invitation_id()  # ginv_...
generate_invitation_token()     # Secure token for invitations
create_slug(text)               # URL-safe slugs
```

---

### 3. Projects API (100% Complete - 5/5 endpoints)

✅ `GET /api/projects/` - List with filtering (status, approval_status)
✅ `POST /api/projects/` - Create new project (auth required)
✅ `GET /api/projects/<id>/` - Get details with workgroups count
✅ `PATCH /api/projects/<id>/` - Update (initiator/admin only)
✅ `POST /api/projects/<id>/approve/` - Approve/reject (admin only)

**Features:**
- Automatic slug generation with collision handling
- Status workflow tracking with StatusChange audit
- Permission checks (initiator or admin)
- Activity timestamp updates
- Filtering by status and approval_status

---

### 4. Workgroups API (100% Complete - 5/5 endpoints)

✅ `GET /api/projects/<id>/workgroups/` - List for project
✅ `POST /api/projects/<id>/workgroups/` - Create in project
✅ `GET /api/workgroups/<id>/` - Get details
✅ `PATCH /api/workgroups/<id>/` - Update (coordinator/admin)
✅ `POST /api/workgroups/<id>/approve/` - Approve/reject (editor/admin)

**Features:**
- Project-scoped workgroups
- Creator becomes coordinator
- Unique slugs per project
- Status change audit trail
- Approval workflow

---

### 5. Guilds API (100% Complete - 4/4 endpoints)

✅ `GET /api/guilds/` - List all guilds
✅ `POST /api/guilds/` - Create (instant registration)
✅ `GET /api/guilds/<id>/` - Get with members list
✅ `POST /api/guilds/<id>/invite/` - Invite via email

**Features:**
- No approval required (instant registration)
- Initiator automatically becomes admin member
- Email-based invitation system
- 7-day invitation expiration
- Token-based verification
- Member role management

---

### 6. Role Images Feature (100% Complete)

Fully implemented in previous work:
- RoleImage and RoleImageVote models
- 11 API endpoints (submit, vote, promote, hide, delete, notes)
- Gallery page with voting UI
- Image Detail page with admin interface
- File upload, URL, and ordinal support

---

## ❌ Remaining Work

### 1. Role/Claim/Badge APIs (0% Complete - ~20 endpoints needed)

#### Clusters API (6 endpoints)
- [ ] `GET /api/projects/<id>/clusters/` - List clusters
- [ ] `POST /api/projects/<id>/clusters/` - Create cluster
- [ ] `GET /api/clusters/<id>/` - Get cluster
- [ ] `PATCH /api/clusters/<id>/` - Update cluster
- [ ] `DELETE /api/clusters/<id>/` - Archive cluster
- [ ] `GET /api/clusters/<id>/roles/` - List roles in cluster

#### Roles API (8 endpoints)
- [ ] `GET /api/projects/<id>/roles/` - List roles (filterable)
- [ ] `POST /api/projects/<id>/roles/` - Create role
- [ ] `POST /api/projects/<id>/roles/import/` - Import roles from JSON
- [ ] `GET /api/roles/<id>/` - Get role details
- [ ] `PATCH /api/roles/<id>/` - Update role
- [ ] `POST /api/roles/<id>/approve/` - Approve role
- [ ] `POST /api/roles/<id>/status/` - Change role status
- [ ] `GET /api/roles/<id>/claims/` - List claims for role

#### Claims API (6 endpoints)
- [ ] `GET /api/projects/<id>/claims/` - List claims
- [ ] `POST /api/roles/<id>/claims/` - Create claim
- [ ] `GET /api/claims/<id>/` - Get claim details
- [ ] `PATCH /api/claims/<id>/` - Update claim
- [ ] `POST /api/claims/<id>/approve/` - Approve claim (if required)
- [ ] `POST /api/claims/<id>/status/` - Change claim status

#### Badges API (6 endpoints)
- [ ] `GET /api/projects/<id>/badges/` - List badges
- [ ] `GET /api/claims/<id>/badges/` - List badges for claim
- [ ] `POST /api/claims/<id>/badges/` - Request badge
- [ ] `GET /api/badges/<id>/` - Get badge details
- [ ] `POST /api/badges/<id>/approve/` - Approve badge
- [ ] `POST /api/badges/<id>/issue/` - Issue badge (set inscription_id)

**Estimated Time:** 4-6 hours

---

### 2. UI Pages (0% Complete - 12+ pages needed)

#### Projects UI (3 pages)
- [ ] `/projects/` - Project directory with filtering
- [ ] `/projects/<slug>/` - Project detail page
- [ ] `/projects/create/` - Create project form

#### Workgroups UI (3 pages)
- [ ] `/projects/<slug>/workgroups/` - Workgroup list for project
- [ ] `/workgroups/<slug>/` - Workgroup detail page
- [ ] `/workgroups/create/` - Create workgroup form

#### Guilds UI (4 pages)
- [ ] `/guilds/` - Guild directory
- [ ] `/guilds/<slug>/` - Guild detail with members
- [ ] `/guilds/create/` - Create guild form
- [ ] `/guilds/invite/<token>/` - Accept invitation page

#### Roles UI (4+ pages)
- [ ] `/projects/<slug>/roles/` - Role directory (already have `/roles/<slug>/images/`)
- [ ] `/roles/<slug>/` - Role detail page
- [ ] `/roles/<slug>/claim/` - Claim role form
- [ ] `/claims/<id>/` - Claim detail page
- [ ] `/badges/<id>/` - Badge detail page

**Estimated Time:** 8-12 hours

---

### 3. Admin Dashboard Pages (0% Complete - 4 pages needed)

- [ ] `/admin/projects/` - Approve/manage projects
- [ ] `/admin/workgroups/` - Approve/manage workgroups
- [ ] `/admin/roles/` - Approve/manage roles
- [ ] `/admin/badges/` - Approve/issue badges

**Estimated Time:** 3-4 hours

---

## Implementation Roadmap

### Phase 1: Complete Role/Claim/Badge APIs (Priority: High)
**Estimated Time:** 4-6 hours

1. Implement Clusters API (6 endpoints)
2. Implement Roles API (8 endpoints)
3. Implement Claims API (6 endpoints)
4. Implement Badges API (6 endpoints)
5. Test all endpoints with Postman/curl

**Deliverable:** Full API coverage for entire system

---

### Phase 2: Core UI Pages (Priority: High)
**Estimated Time:** 6-8 hours

1. Projects directory and detail pages
2. Workgroups directory and detail pages
3. Guilds directory and detail pages
4. Basic role directory page

**Deliverable:** Users can browse and view all entities

---

### Phase 3: Creation Forms (Priority: Medium)
**Estimated Time:** 4-5 hours

1. Create project form
2. Create workgroup form
3. Create guild form
4. Claim role form

**Deliverable:** Users can create entities

---

### Phase 4: Admin Dashboards (Priority: Medium)
**Estimated Time:** 3-4 hours

1. Project approval dashboard
2. Workgroup approval dashboard
3. Role approval dashboard
4. Badge approval/issuance dashboard

**Deliverable:** Admins can manage approvals

---

### Phase 5: Advanced Features (Priority: Low)
**Estimated Time:** 4-6 hours

1. Role JSON import functionality
2. Guild invitation email system
3. Badge issuance with ordinal inscription
4. Status change history views
5. Member management for guilds/workgroups

**Deliverable:** Full feature parity with RFC

---

## Total Estimated Time to Completion

- **Remaining APIs:** 4-6 hours
- **UI Pages:** 13-17 hours
- **Testing & Refinement:** 2-3 hours
- **Documentation:** 1-2 hours

**Total:** ~20-28 hours of focused development

---

## Technical Debt & Considerations

### Database Migrations
- Current approach uses `db.create_all()` which only creates missing tables
- For production, need proper migration strategy (Alembic or similar)
- Need data migration for existing submissions/documents to associate with projects

### Email System
- Guild invitations need actual email sending (currently just returns link)
- Consider using SendGrid, AWS SES, or similar
- Need email templates for invitations

### File Organization
- Single-file Flask app (`ietf_data_viewer_simple.py`) is now ~9000+ lines
- Consider refactoring into modules:
  - `models/` - Database models
  - `api/` - API endpoints
  - `views/` - UI pages
  - `utils/` - Helper functions

### Testing
- No automated tests yet
- Need unit tests for models
- Need integration tests for APIs
- Need end-to-end tests for UI workflows

### Documentation
- Need user guide for Projects/Workgroups/Guilds
- Need admin guide for approval workflows
- Need API documentation (OpenAPI/Swagger)

---

## Git Commits Summary

1. **6ec5e62ab** - Add Role Images requirements to RFC
2. **5cc474747** - Implement Role Images: models, API, gallery page
3. **acafbae8a** - Add Image Detail page with admin interface
4. **d918e9465** - Add Role Images implementation summary
5. **5dd921275** - Add Projects/Workgroups/Guilds/Roles models (10 models)
6. **2e01ff778** - Add Projects/Workgroups/Guilds APIs (14 endpoints)

**Total Lines Added:** ~2000+ lines of code

---

## Next Steps

### Immediate (Next Session)
1. Implement Role/Claim/Badge APIs (~20 endpoints)
2. Create basic Projects directory page
3. Create basic Workgroups directory page
4. Create basic Guilds directory page

### Short Term (This Week)
1. Complete all UI pages
2. Implement admin dashboards
3. Add email system for guild invitations
4. Write user documentation

### Medium Term (Next Week)
1. Refactor into modular structure
2. Add automated tests
3. Implement role JSON import
4. Add badge ordinal inscription support

### Long Term (Future)
1. Data migration for existing content
2. Production deployment plan
3. Performance optimization
4. Advanced features (notifications, activity feeds, etc.)

---

## Related Documentation

- `RFC_PROJECTS_WORKGROUPS_GUILDS.md` - Core system specification
- `RFC_ROLES_CLAIMS_BADGES.md` - Roles system specification
- `IMPLEMENTATION_CHECKLIST.md` - Detailed implementation checklist
- `ROLE_IMAGES_IMPLEMENTATION_COMPLETE.md` - Role Images feature summary
- `EXPANDED_SCOPE_SUMMARY.md` - Expanded scope documentation

---

## Questions & Decisions Needed

1. **Email Provider:** Which email service should be used for guild invitations?
2. **File Structure:** Should we refactor into modules now or after completion?
3. **Testing Strategy:** What level of test coverage is required before merge?
4. **Migration Strategy:** How should existing data be migrated to new project structure?
5. **Deployment:** Should this be deployed incrementally or all at once?

---

## Success Metrics

### MVP Complete When:
- ✅ All 10 models created
- ✅ Projects/Workgroups/Guilds APIs complete
- ❌ Role/Claim/Badge APIs complete
- ❌ All directory pages functional
- ❌ All creation forms functional
- ❌ Admin approval workflows functional
- ❌ Basic documentation complete

### Production Ready When:
- All MVP criteria met
- Automated tests with >70% coverage
- User and admin documentation complete
- Email system functional
- Performance tested with realistic data volumes
- Security review complete
- Migration plan tested

---

**Current Status:** Foundation complete, APIs 60% done, UI 0% done. Ready to continue implementation.
