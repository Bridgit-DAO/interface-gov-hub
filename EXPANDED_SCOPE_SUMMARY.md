# Expanded Scope Summary: Roles, Claims, Badges & Inscriptions

**Date:** 2026-02-08  
**Status:** ✅ Planning Complete - Expanded Scope  
**Feature Branch:** `feature/projects-workgroups-guilds`

## Scope Expansion

The original RFC for Projects, Workgroups, and Guilds has been significantly expanded to include a comprehensive **Roles, Claims, and Badges** system with Bitcoin inscription support.

## What's Been Added

### 1. Roles System (5 New Models)

#### Cluster Model
- Organizational grouping of roles within projects
- Project-scoped with ordering
- Status: active/archived

#### Role Model
- Defined units of responsibility scoped to projects
- Dual titles: guild-facing + operational
- Configurable approval requirements
- Status: draft/approved/deprecated/archived
- Public visibility control

#### Claim Model
- User declarations of stewarding a role
- Optional approval workflow
- Term-based (time-bounded) support
- Status: active/pending_approval/paused/expired/revoked
- Badge summary integration

#### Badge Model
- Recognition artifacts linked to claims
- Types: role badge, founding wave badge, term renewal marker
- Bitcoin ordinal inscription support
- Custody modes: user wallet or Overweb treasury
- Status: requested/needs_info/approved/issued/denied/canceled

#### StatusChange Model
- Comprehensive audit trail
- Tracks all status changes across entities
- Records who, when, what, and why

### 2. Guild System Enhancements

**New Models:**
- `GuildMembership` - Role-based membership (initiator/admin/member)
- `GuildInvitation` - Email-based invitation system with tokens

**Key Changes:**
- Guilds no longer require approval (instant registration)
- Invitation-based membership (must accept to join)
- Role hierarchy: initiator → admin → member
- Admins can invite and promote members

### 3. New UI Pages

#### Start Here Page (`/start-here/`)
- Onboarding for new users
- System overview
- Quick actions
- Getting started guide

#### Inscriptions Page (`/inscriptions/`)
- Explains Bitcoin inscriptions
- Ordinal badges overview
- Custody options
- Badge issuance process

#### Role Directory (`/projects/{id}/roles/`)
- Search and filter roles
- Cluster-based organization
- Claim role action
- Links to role detail pages

#### Role Detail Page (`/projects/{id}/roles/{slug}/`)
- Role information and configuration
- All claims for the role
- Badge statistics
- Admin actions (permission-gated)

### 4. Submission Form Enhancement

**New Field: "What changed since last revision?"**
- Optional but recommended
- Helps reviewers understand evolution
- Stored in revision history
- Never blocks submission

### 5. JSON Import System

**Role Import:**
- Idempotent import from JSON
- Safe to re-run (no duplicates)
- Updates existing roles
- Initial data: Meta-Layer roles

### 6. Permissions System

**New Permission Levels:**
- **User:** Create roles, claims, badge requests
- **Editor:** Approve roles, claims
- **Admin:** All editor permissions + system admin
- **Project Admin:** Project-scoped admin, approve badges

### 7. Anti-Spam Controls

**Rate Limiting:**
- Roles: 5 per user per day
- Claims: 10 per user per day
- Badges: 5 requests per user per day

**Account Requirements:**
- Email verification required
- Account age > 24 hours for role creation
- One approved claim before creating roles

## Updated Schema Counts

### Original Scope
- 3 new models (Project, Workgroup, Guild)
- 2 modified models (Submission, Document)

### Expanded Scope
- **8 new models total:**
  - Project
  - Workgroup
  - Guild
  - GuildMembership
  - GuildInvitation
  - Cluster
  - Role
  - Claim
  - Badge
  - StatusChange

- **3 modified models:**
  - Submission (add project, what_changed)
  - Document (add project, workgroup)

## API Endpoints Summary

### Original Scope
- 21 endpoints (7 per entity: Project, Workgroup, Guild)

### Expanded Scope
- **60+ endpoints:**
  - Projects: 7
  - Workgroups: 8
  - Guilds: 10 (added invitations)
  - Clusters: 6
  - Roles: 8 (includes import)
  - Claims: 8
  - Badges: 8

## UI Pages Summary

### Original Scope
- 9 pages (3 per entity)

### Expanded Scope
- **20+ pages:**
  - Projects: 3
  - Workgroups: 3
  - Guilds: 4 (added invitation pages)
  - Roles: 4 (directory, detail, create, admin queue)
  - Claims: 2 (create, detail)
  - Badges: 2 (request, detail)
  - Onboarding: 2 (Start Here, Inscriptions)
  - Admin: 3 (roles queue, claims queue, badges queue)

## Implementation Timeline Update

### Original Timeline: 5 Weeks
- Week 1: Models & Migrations
- Week 2: API Development
- Week 3: UI Development
- Week 4: Testing & Refinement
- Week 5: Migration & Deployment

### Revised Timeline: 7-8 Weeks
- **Week 1-2:** Models & Migrations (expanded)
  - Core models (Project, Workgroup, Guild)
  - Guild enhancements (Membership, Invitation)
  - Roles system (Cluster, Role, Claim, Badge, StatusChange)
  
- **Week 3-4:** API Development (expanded)
  - Core APIs (Project, Workgroup, Guild)
  - Guild invitation APIs
  - Roles system APIs (Cluster, Role, Claim, Badge)
  - JSON import endpoint
  
- **Week 5-6:** UI Development (expanded)
  - Core UI (Project, Workgroup, Guild)
  - Guild invitation flow
  - Role directory and detail pages
  - Claim and badge flows
  - Start Here and Inscriptions pages
  - Admin dashboards
  
- **Week 7:** Testing & Refinement
  - Integration tests
  - UI tests
  - Anti-spam controls
  - Performance optimization
  
- **Week 8:** Migration & Deployment
  - Import Meta-Layer roles
  - Data migration
  - Staging deployment
  - Production deployment

## Task Count Update

### Original Scope
- 200+ tasks

### Expanded Scope
- **400+ tasks** (estimated)
  - Core system: 200 tasks
  - Roles system: 150 tasks
  - Guild enhancements: 30 tasks
  - UI expansions: 50 tasks
  - Testing additions: 70 tasks

## Key Design Principles

### 1. Guild-Style Stewardship
- No hierarchy implied
- Anyone can propose roles
- Claims are declarations, not appointments
- Badges are recognition, not authority

### 2. Separation of Concerns
- Claiming ≠ Badge issuance
- Role approval ≠ Claim approval
- Badge request ≠ Badge approval

### 3. Flexibility
- Roles can require claim approval or not
- Badges can be on-chain (ordinal) or off-chain
- Terms can be time-bounded or open-ended
- Clusters organize but don't restrict

### 4. Transparency
- All status changes audited
- Public role directories
- Clear permission boundaries
- Visible approval workflows

## Bitcoin Inscription Integration

### Ordinal Badge Support
- Optional inscription IDs on badges
- BTC Taproot address collection
- Custody mode selection (user wallet vs treasury)
- Transaction reference tracking
- Chain specification (bitcoin)

### Issuance Flow
1. User requests badge for claim
2. Optionally provides BTC Taproot address
3. Project Admin approves badge
4. Badge issued (on-chain or off-chain)
5. If on-chain: inscription_id recorded
6. Badge status updated to "issued"

## Success Metrics (Updated)

### Original Metrics
- Zero data loss
- All tests passing
- Performance targets met

### Expanded Metrics
- ✅ Meta-Layer roles imported successfully
- ✅ Role directory functional with search/filter
- ✅ Users can claim roles without friction
- ✅ Badge request workflow is clear
- ✅ Inscription IDs properly stored
- ✅ Guild invitations work via email
- ✅ Anti-spam controls prevent abuse
- ✅ Audit trails capture all changes
- ✅ Start Here page reduces onboarding time
- ✅ Revision history shows "what changed"
- ✅ Admin dashboards provide efficient queues

## Risk Assessment (Updated)

### New Risks

#### High Risk
1. **Complexity Increase** - 10 models vs 3 original
   - Mitigation: Phased implementation, thorough testing

2. **Bitcoin Integration** - Inscription IDs and wallet addresses
   - Mitigation: Optional feature, clear documentation, validation

3. **Email Invitation System** - Token management, expiration
   - Mitigation: Standard patterns, security review

#### Medium Risk
1. **JSON Import Idempotency** - Must not create duplicates
   - Mitigation: Comprehensive testing, transaction handling

2. **Permission Complexity** - 4 permission levels
   - Mitigation: Clear permission matrix, automated tests

3. **Anti-Spam Effectiveness** - Rate limiting and controls
   - Mitigation: Monitor abuse patterns, adjust limits

### Existing Risks (Still Relevant)
- Data migration complexity
- Performance impact
- User adoption

## Open Questions (Updated)

### Newly Added
- [ ] Badge invitation expiration period? (suggest 30 days)
- [ ] Support badge transfers between users?
- [ ] Support claim transfers?
- [ ] Maximum active claims per user per project?
- [ ] Should role images be uploaded or URL only?
- [ ] Ordinal inscription service integration details?

### Original (Still Open)
- [ ] How long to keep Legacy project visible?
- [ ] Should Legacy project be filterable/hideable?

## Documentation Requirements (Updated)

### User Documentation (Expanded)
- Original: 3 guides
- **Expanded: 10+ guides**
  - How to submit to Meta-Layer
  - When to create a project
  - How to create and manage guilds
  - How to claim a role
  - How to request a badge
  - Understanding inscriptions
  - Using the role directory
  - Understanding project status
  - Guild invitation process
  - What changed field guide

### Admin Documentation (Expanded)
- Original: 3 guides
- **Expanded: 7+ guides**
  - Approving projects
  - Approving workgroups
  - Approving roles
  - Approving claims
  - Approving and issuing badges
  - Managing clusters
  - Importing roles from JSON

### Developer Documentation (Expanded)
- Original: 3 guides
- **Expanded: 8+ guides**
  - All API endpoints (60+)
  - Permission system
  - Invitation flow
  - Badge issuance flow
  - JSON import format
  - Ordinal integration
  - Anti-spam controls
  - Migration guide

## Files Created/Updated

### New RFC Documents
1. **RFC_PROJECTS_WORKGROUPS_GUILDS.md** - Original RFC (updated)
2. **RFC_ROLES_CLAIMS_BADGES.md** - New comprehensive RFC
3. **IMPLEMENTATION_CHECKLIST.md** - Updated with 400+ tasks
4. **DESIGN_DECISIONS.md** - All finalized decisions
5. **INITIAL_DATA.md** - Meta-Layer initial data
6. **PLANNING_SUMMARY.md** - Original scope summary
7. **EXPANDED_SCOPE_SUMMARY.md** - This document

## Next Steps

1. **Review expanded scope** with stakeholders
2. **Validate timeline** (7-8 weeks vs original 5)
3. **Confirm resource allocation** for expanded scope
4. **Get approval** to proceed with implementation
5. **Begin Phase 1** (Models and Migrations - expanded)

## Conclusion

The scope has **doubled** from the original RFC, adding significant value:

- **Guild-style stewardship** without hierarchy
- **Bitcoin inscription** support for badges
- **Comprehensive role system** with claims and badges
- **Enhanced guild system** with invitations
- **Better onboarding** with Start Here page
- **Clearer revision tracking** with "what changed" field

The expanded system provides a complete governance framework while maintaining the original principles of optional participation and stewardship responsibility.

**Status:** ✅ Ready for stakeholder review and approval
