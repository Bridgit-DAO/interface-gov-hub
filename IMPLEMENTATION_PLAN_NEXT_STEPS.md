# Implementation Plan: Next Steps for Projects/Workgroups/Guilds

**Created:** 2026-02-10  
**Current Completion:** ~40%  
**Target:** Full MVP completion

---

## Quick Reference: What's Done vs. What's Left

### ✅ Complete (40%)
- All 10 database models
- All helper functions
- Projects API (5 endpoints)
- Workgroups API (5 endpoints)
- Guilds API (4 endpoints)
- Role Images feature (11 endpoints + 2 pages)

### ❌ Remaining (60%)
- Role/Claim/Badge APIs (~20 endpoints)
- All UI pages (~12 pages)
- Admin dashboards (4 pages)

---

## Recommended Implementation Order

### Session 1: Role/Claim/Badge APIs (4-6 hours)

**Priority: CRITICAL** - Complete API layer before building UI

#### Step 1: Clusters API (1 hour)
```python
# 6 endpoints to implement:
GET    /api/projects/<id>/clusters/
POST   /api/projects/<id>/clusters/
GET    /api/clusters/<id>/
PATCH  /api/clusters/<id>/
DELETE /api/clusters/<id>/
GET    /api/clusters/<id>/roles/
```

#### Step 2: Roles API (1.5 hours)
```python
# 8 endpoints to implement:
GET    /api/projects/<id>/roles/
POST   /api/projects/<id>/roles/
POST   /api/projects/<id>/roles/import/  # JSON import
GET    /api/roles/<id>/
PATCH  /api/roles/<id>/
POST   /api/roles/<id>/approve/
POST   /api/roles/<id>/status/
GET    /api/roles/<id>/claims/
```

#### Step 3: Claims API (1 hour)
```python
# 6 endpoints to implement:
GET    /api/projects/<id>/claims/
POST   /api/roles/<id>/claims/
GET    /api/claims/<id>/
PATCH  /api/claims/<id>/
POST   /api/claims/<id>/approve/
POST   /api/claims/<id>/status/
```

#### Step 4: Badges API (1 hour)
```python
# 6 endpoints to implement:
GET    /api/projects/<id>/badges/
GET    /api/claims/<id>/badges/
POST   /api/claims/<id>/badges/
GET    /api/badges/<id>/
POST   /api/badges/<id>/approve/
POST   /api/badges/<id>/issue/
```

**Deliverable:** Full API coverage (40+ total endpoints)

---

### Session 2: Core Directory Pages (3-4 hours)

**Priority: HIGH** - Users need to browse entities

#### Step 1: Projects Directory (1 hour)
- URL: `/projects/`
- Features:
  - List all approved projects
  - Filter by status
  - Search by name
  - Card grid layout
  - "Create Project" button (auth required)

#### Step 2: Workgroups Directory (1 hour)
- URL: `/projects/<slug>/workgroups/`
- Features:
  - List workgroups for project
  - Filter by status
  - Show coordinator
  - "Create Workgroup" button

#### Step 3: Guilds Directory (1 hour)
- URL: `/guilds/`
- Features:
  - List all active guilds
  - Show member count
  - Search by name
  - "Create Guild" button

**Deliverable:** Users can browse all entities

---

### Session 3: Detail Pages (3-4 hours)

**Priority: HIGH** - Users need to see entity details

#### Step 1: Project Detail (1 hour)
- URL: `/projects/<slug>/`
- Sections:
  - Project info (status, description, initiator)
  - Workgroups list
  - Roles list
  - Activity timeline
  - Edit button (initiator/admin)

#### Step 2: Workgroup Detail (1 hour)
- URL: `/workgroups/<slug>/`
- Sections:
  - Workgroup info
  - Coordinator
  - Members list
  - Associated documents/drafts
  - Edit button (coordinator/admin)

#### Step 3: Guild Detail (1 hour)
- URL: `/guilds/<slug>/`
- Sections:
  - Guild info
  - Members list with roles
  - Invite button (admin/initiator)
  - Leave guild button

**Deliverable:** Full entity viewing experience

---

### Session 4: Creation Forms (2-3 hours)

**Priority: MEDIUM** - Users need to create entities

#### Step 1: Create Project Form (45 min)
- URL: `/projects/create/`
- Fields: name, description
- Submit → pending approval
- Redirect to project detail

#### Step 2: Create Workgroup Form (45 min)
- URL: `/projects/<slug>/workgroups/create/`
- Fields: name, description
- Submit → pending approval
- Redirect to workgroup detail

#### Step 3: Create Guild Form (30 min)
- URL: `/guilds/create/`
- Fields: name, description
- Submit → instant activation
- Redirect to guild detail

#### Step 4: Claim Role Form (45 min)
- URL: `/roles/<slug>/claim/`
- Fields: intent, evidence links
- Submit → active or pending
- Redirect to claim detail

**Deliverable:** Full creation workflows

---

### Session 5: Admin Dashboards (2-3 hours)

**Priority: MEDIUM** - Admins need approval interfaces

#### Step 1: Projects Approval (45 min)
- URL: `/admin/projects/`
- List pending projects
- Approve/reject buttons
- View project details

#### Step 2: Workgroups Approval (45 min)
- URL: `/admin/workgroups/`
- List pending workgroups
- Approve/reject buttons
- Filter by project

#### Step 3: Roles Approval (45 min)
- URL: `/admin/roles/`
- List pending roles
- Approve/reject buttons
- Filter by project

#### Step 4: Badges Issuance (45 min)
- URL: `/admin/badges/`
- List pending badge requests
- Approve/issue buttons
- Add inscription ID field

**Deliverable:** Full admin workflow

---

## Code Organization Strategy

### Current State
- Single file: `ietf_data_viewer_simple.py` (~9000 lines)
- All models, APIs, and pages in one file

### Recommended: Keep Single File for Now
**Reasons:**
1. Easier to navigate during active development
2. No import issues
3. Can refactor after feature complete
4. Flask supports large single-file apps

### Future Refactoring (Post-MVP)
```
datatracker/
├── app.py                 # Main app initialization
├── models/
│   ├── __init__.py
│   ├── projects.py
│   ├── workgroups.py
│   ├── guilds.py
│   └── roles.py
├── api/
│   ├── __init__.py
│   ├── projects.py
│   ├── workgroups.py
│   ├── guilds.py
│   └── roles.py
├── views/
│   ├── __init__.py
│   ├── projects.py
│   ├── workgroups.py
│   ├── guilds.py
│   └── roles.py
└── utils/
    ├── __init__.py
    ├── auth.py
    └── helpers.py
```

---

## Testing Strategy

### Manual Testing Checklist

#### Projects
- [ ] Create project
- [ ] View project list
- [ ] View project detail
- [ ] Update project (initiator)
- [ ] Approve project (admin)
- [ ] Reject project (admin)
- [ ] Filter projects by status

#### Workgroups
- [ ] Create workgroup
- [ ] View workgroup list
- [ ] View workgroup detail
- [ ] Update workgroup (coordinator)
- [ ] Approve workgroup (editor)
- [ ] Change workgroup status

#### Guilds
- [ ] Create guild (instant)
- [ ] View guild list
- [ ] View guild detail with members
- [ ] Invite member (admin)
- [ ] Accept invitation
- [ ] Leave guild

#### Roles/Claims/Badges
- [ ] Create role
- [ ] Approve role (admin)
- [ ] Claim role
- [ ] Approve claim (if required)
- [ ] Request badge
- [ ] Approve badge (project admin)
- [ ] Issue badge with inscription ID

### Automated Testing (Future)
- Unit tests for models
- API integration tests
- UI end-to-end tests with Playwright

---

## Common Patterns to Reuse

### API Endpoint Pattern
```python
@app.route('/api/entities/<id>/', methods=['GET'])
def api_get_entity(id):
    """Get entity details"""
    entity = Entity.query.get_or_404(id)
    return jsonify(entity.to_dict())
```

### List Page Pattern
```python
@app.route('/entities/')
def entities_list():
    """List entities"""
    entities = Entity.query.filter_by(status='active').all()
    
    content = f"""
    <div class="container mt-4">
        <h1>Entities</h1>
        <div class="row">
            {render_entity_cards(entities)}
        </div>
    </div>
    """
    
    return render_page("Entities", content)
```

### Detail Page Pattern
```python
@app.route('/entities/<slug>/')
def entity_detail(slug):
    """Entity detail page"""
    entity = Entity.query.filter_by(slug=slug).first_or_404()
    
    content = f"""
    <div class="container mt-4">
        <h1>{entity.name}</h1>
        <p>{entity.description}</p>
        {render_entity_details(entity)}
    </div>
    """
    
    return render_page(entity.name, content)
```

---

## Key Design Decisions

### 1. Approval Workflows
- **Projects:** Admin approval required
- **Workgroups:** Editor/Admin approval required
- **Guilds:** No approval (instant registration)
- **Roles:** Admin approval required
- **Claims:** Optional (per role configuration)
- **Badges:** Project Admin approval required

### 2. Permission Levels
- **User:** Create projects, guilds, workgroups, roles, claims, badges
- **Editor:** Approve workgroups
- **Admin:** Approve projects, roles, badges; all editor permissions
- **Project Admin:** Approve badges for their project
- **Initiator/Coordinator:** Edit their own entities

### 3. Slug Generation
- Automatic from name
- Collision handling with counter suffix
- URL-safe (lowercase, alphanumeric, hyphens)

### 4. Status Change Tracking
- All status changes recorded in StatusChange model
- Includes: entity_type, entity_id, field_name, from/to values
- User attribution and timestamps

---

## Quick Start Commands

### Create Tables
```bash
cd /home/ubuntu/datatracker
python3 create_projects_tables.py
```

### Test API Endpoints
```bash
# List projects
curl http://localhost:8001/api/projects/

# Create project (requires auth)
curl -X POST http://localhost:8001/api/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Project", "description": "Testing"}'
```

### Restart Dev Server
```bash
./simple-restart.sh
```

---

## Estimated Timeline

### Aggressive (Full Focus)
- **Week 1:** Complete all APIs and core UI pages
- **Week 2:** Admin dashboards, testing, refinement
- **Total:** 2 weeks

### Moderate (Part-Time)
- **Week 1-2:** Complete all APIs
- **Week 3-4:** Core UI pages
- **Week 5:** Admin dashboards
- **Week 6:** Testing and refinement
- **Total:** 6 weeks

### Conservative (Incremental)
- **Month 1:** APIs and basic pages
- **Month 2:** Advanced features and admin tools
- **Month 3:** Testing, documentation, deployment
- **Total:** 3 months

---

## Success Criteria

### MVP Complete
- All APIs functional
- All directory and detail pages working
- Basic creation forms functional
- Admin approval workflows working
- Can create, view, and manage all entities

### Production Ready
- All MVP criteria met
- Email system functional
- Automated tests passing
- Documentation complete
- Security review done
- Performance tested

---

## Contact & Questions

For questions about implementation:
1. Review RFC documents in repo
2. Check IMPLEMENTATION_CHECKLIST.md
3. Consult PROJECTS_WORKGROUPS_GUILDS_STATUS.md

---

**Ready to continue? Start with Session 1: Role/Claim/Badge APIs**
