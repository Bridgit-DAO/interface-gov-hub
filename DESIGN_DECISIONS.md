# Design Decisions Summary

**Date:** 2026-02-08  
**Status:** ✅ Finalized

## Key Decisions

### 1. Project Hierarchy: NO ❌
- Projects are flat with no parent/child relationships
- Keeps structure simple and clear
- Projects can link to successors via `superseded_by` field

### 2. Workgroup Limits: NO ❌
- No limit on workgroups per project
- Allows organic growth and flexibility
- Projects can scale as needed

### 3. Guild Membership: Invitation-Based ✅
- Initiator/admins send email invitations
- Recipients must explicitly accept
- Prevents spam and maintains quality
- Implementation via `GuildInvitation` model with tokens

### 4. Approval Workflows

#### Projects
- **Require admin approval** before becoming active
- Prevents spam and maintains quality
- Initiator becomes project steward automatically

#### Workgroups
- **Require editor or admin approval**
- Only approved workgroups appear in submission forms
- Ensures quality control for governance bodies
- Workgroups assess rough consensus but don't exercise unilateral authority

#### Guilds
- **No approval required** - instant registration
- Encourages community formation
- Initiator becomes admin automatically
- Can add other admins from members

### 5. Terminology
- **"Working Groups" → "Workgroups"** (single word)
- **"Chair" → "Coordinator"** (throughout entire system)
- **"Submitted by" → "Initiator"** (for projects and guilds)

## Meta-Layer Governance Philosophy

### Core Principles
1. **Projects are optional stewardship containers**, not prerequisites
2. Most users will NOT create projects
3. Most users will submit to existing projects (especially Meta-Layer)
4. Projects exist for long-lived governance work

### Participation Model
- ✅ Anyone can submit ML-Drafts
- ✅ Anyone can comment on drafts/RFCs
- ✅ Anyone can create/join Guilds
- ⚠️ Projects only needed for stewarding ongoing governance work
- ✅ Every draft/RFC must associate with a project (but most use existing)

### Project Status (Descriptive, Not Evaluative)
1. **proposed** - Registered but little/no active work
2. **active** - Actively hosting drafts, workgroups, deliberation
3. **stabilizing** - Focused on stabilizing drafts for RFC promotion
4. **maintaining** - Published RFCs, focused on stewardship
5. **dormant** - Inactive but preserved for resumption
6. **concluded** - Intentionally completed scope
7. **archived** - Historical reference only

Each status includes:
- `status_reason` - Free-text explanation
- `last_activity` - Timestamp
- Optional `superseded_by` link

## Initial Data

### Meta-Layer Project
- **Name:** Meta-Layer
- **Initiator:** daveed@bridgit.io
- **Status:** active
- **Approval:** approved (pre-approved)
- **Purpose:** Foundational project for Meta-Layer governance

### Governance Workgroup
- **Name:** Governance
- **Project:** Meta-Layer
- **Coordinator:** daveed@bridgit.io
- **Status:** active
- **Approval:** approved (pre-approved)
- **Purpose:** Core governance workgroup for Meta-Layer

## Schema Summary

### Project Model
```
- name (unique)
- initiator (Person FK)
- status (proposed/active/stabilizing/maintaining/dormant/concluded/archived)
- status_reason (text)
- approval_status (pending/approved/rejected)
- description
- last_activity
- superseded_by (self FK, optional)
- timestamps
```

### Workgroup Model
```
- name
- project (Project FK, required)
- coordinator (Person FK)
- status (active/inactive/completed/archived)
- approval_status (pending/approved/rejected)
- description
- members (M2M with Person)
- timestamps
```

### Guild Model
```
- name (unique)
- initiator (Person FK)
- description
- timestamps
```

### GuildMembership Model
```
- guild (Guild FK)
- person (Person FK)
- role (initiator/admin/member)
- joined_at
```

### GuildInvitation Model
```
- guild (Guild FK)
- invited_by (Person FK)
- invited_email
- invited_person (Person FK, optional)
- status (pending/accepted/declined/expired)
- invitation_token (unique)
- timestamps
- expires_at
```

## UI Design Intent

### Make It Easy To:
1. Submit a draft **without** creating a project
2. Browse existing projects and attach drafts
3. See project status at a glance
4. Understand that Meta-Layer is the default/foundational project

### Project Creation Should Feel Like:
- Taking on **stewardship responsibility**
- NOT a mandatory setup step
- A deliberate choice for long-lived work

### Status Changes Should Be:
- Visible in UI
- Explainable (via status_reason)
- Part of public record

## Submission Flow

1. User navigates to submission form
2. Project dropdown shows approved projects (Meta-Layer at top)
3. User selects project (defaults to Meta-Layer)
4. Workgroup dropdown populates with **only approved** workgroups for that project
5. User selects workgroup (optional but recommended)
6. User submits draft

**Key:** Most users will select Meta-Layer + Governance without creating anything new.

## RFC Promotion Flow

1. Draft exists in a project
2. Draft must be associated with a workgroup
3. Workgroup deliberates and assesses rough consensus
4. Coordinator facilitates but doesn't decide
5. If consensus reached, draft can be promoted to RFC
6. RFC remains associated with project and workgroup

## Guild Flow

1. User creates guild (instant, no approval)
2. User becomes initiator + admin
3. User invites members via email
4. Recipients receive invitation email with token
5. Recipients click link and accept/decline
6. Accepted members join guild
7. Initiator/admins can promote members to admin
8. Admins can invite more members

## Permission Matrix

| Action | Who Can Do It |
|--------|---------------|
| Create project | Any authenticated user |
| Approve project | Admin only |
| Create workgroup | Project members |
| Approve workgroup | Editor or Admin |
| Submit draft | Any authenticated user (to approved projects) |
| Create guild | Any authenticated user |
| Invite to guild | Initiator or guild admin |
| Accept guild invitation | Invited person |
| Promote to guild admin | Initiator or guild admin |
| Comment on draft | Any authenticated user |
| Join approved workgroup | Project members |

## Migration Strategy

### Phase 1: Create Models
- Add nullable foreign keys to existing models
- No breaking changes

### Phase 2: Initial Data
- Create Meta-Layer project (approved)
- Create Governance workgroup (approved)
- Create Legacy project for old data

### Phase 3: Migrate Data
- Associate existing submissions with Legacy project
- Associate existing documents with Legacy project

### Phase 4: Make Required
- Make project field required on Submission
- Update forms and validation

### Phase 5: Deploy
- Staging first
- Production after verification

## Success Metrics

- ✅ Meta-Layer project created and approved
- ✅ Governance workgroup created and approved
- ✅ Zero data loss during migration
- ✅ All existing data migrated to Legacy project
- ✅ Submission form defaults to Meta-Layer
- ✅ Only approved workgroups appear in dropdowns
- ✅ Guild creation is instant
- ✅ Guild invitations work via email
- ✅ All "chair" references replaced with "coordinator"
- ✅ All "working group" references replaced with "workgroup"

## Documentation Requirements

### User Docs
- "How to submit a draft to Meta-Layer"
- "When to create a project (stewardship guide)"
- "How to create and manage a guild"
- "Understanding project status"
- "How workgroups assess consensus"

### Admin Docs
- "Approving projects"
- "Approving workgroups"
- "Managing project status"
- "Handling abuse/spam"

### Developer Docs
- API endpoints for all models
- Permission system
- Invitation flow
- Migration guide

## Open Items

### Resolved ✅
- [x] Project hierarchy? → No
- [x] Workgroup limits? → No
- [x] Guild membership? → Invitation-based
- [x] Approval workflows? → Projects/workgroups require approval, guilds don't
- [x] Initial data? → Meta-Layer project + Governance workgroup

### Still Open ❓
- [ ] How long to keep Legacy project visible?
- [ ] Should Legacy project be filterable/hideable in UI?
- [ ] Invitation email templates and content
- [ ] Invitation expiration period (suggest 30 days)
- [ ] Maximum number of guild admins (suggest unlimited)

## Next Steps

1. ✅ Update RFC with all decisions
2. ✅ Create INITIAL_DATA.md with migration script
3. ⏳ Review with stakeholders
4. ⏳ Get final approval
5. ⏳ Begin implementation Phase 1
