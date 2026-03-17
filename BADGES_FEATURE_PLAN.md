# Badges Feature Plan

## Overview

Transform the Images page into a full **Badges** system with configurable submission/voting periods, conviction vs regular voting, and support for both recurring (role/workgroup) and one-time badges. Terminology: "designs" replaces "images" in the UI.

---

## 1. Role & Workgroup Badge Settings

### 1.1 New/Extended Fields

**Role** (already has `badge_enabled`, `badge_requires_approval`):
- `badge_enabled` (existing) – whether this role gives a badge
- `badge_submission_days` (new) – length of submission period in days
- `badge_voting_days` (new) – length of voting period in days
- `badge_delay_days` (new) – delay between end of submission and start of voting
- `badge_earliest_start` (new) – `DATE` – earliest date the badge cycle can start
- `badge_voting_type` (new) – `'regular'` | `'time_weighted'` | `'quadratic'` (or flags for multiple)
- `badge_voting_time_weighted` (new) – boolean
- `badge_voting_quadratic` (new) – boolean
- `badge_trigger` (new) – `'first_submission'` – cycle starts when first design is submitted
- `badge_cycle_spacing_days` (new) – default 365; min days before next cycle can open
- `badge_end_date` (new) – optional; no new cycles after this date
- `badge_end_at_next_closing` (new) – boolean; if true, end_date = next voting_end
- `badge_skin_id` (new) – FK to badge_skin; layout template for rendered badge

**Workgroup** (add badge support):
- `badge_enabled` (new)
- `badge_submission_days` (new)
- `badge_voting_days` (new)
- `badge_delay_days` (new)
- `badge_earliest_start` (new)
- `badge_voting_type` (new)
- `badge_voting_time_weighted` (new), `badge_voting_quadratic` (new)
- `badge_trigger` (new)
- `badge_cycle_spacing_days` (new), `badge_end_date` (new), `badge_end_at_next_closing` (new)
- `badge_skin_id` (new)

### 1.2 Timeline Logic

```
earliest_start (date) ──────────────────────────────────────────────►
                    │
                    │  (wait until first submission)
                    │
first_submission ───┼──► submission_period (N days) ──► submission_end
                    │
                    │  delay_period (M days)
                    │
voting_start ───────┼─────────────────────────────────► voting_period (K days) ──► voting_end
```

- **Earliest start**: Badge cycle cannot begin before this date.
- **Trigger**: Cycle starts on first submission (after earliest_start).
- **Submission period**: From first submission, lasts `badge_submission_days`.
- **Delay**: From submission_end, wait `badge_delay_days` before voting.
- **Voting period**: Lasts `badge_voting_days`.

---

## 2. Badge Types

### 2.1 Recurring Badges (Role / Workgroup)

- Attached to a role or workgroup.
- Multiple cycles over time.
- Each cycle: submission → delay → voting → winner(s).

### 2.2 One-Time Badges

- For a specific one-time task.
- **New model** `OneTimeBadge`:
  - `id`, `project_id`, `title`, `description`
  - `earliest_start` (DATE)
  - `quantity` – number of badges to award (# given)
  - `elapse_from_first` – e.g. "7 days from first submission" (submission period)
  - `voting_days`, `delay_days`
  - `voting_type` – regular | conviction
  - `status` – draft | upcoming | submission | delay | voting | completed

---

## 3. Badges Page (formerly Images Page)

### 3.1 Rename & Structure

- **Nav**: "Images" → "Badges"
- **Route**: `/role-images/` → `/badges/` (or keep `/role-images/` with redirect for backward compat)
- **Terminology**: "designs" instead of "images" in UI copy

### 3.2 Filter Tabs

- **Upcoming** – earliest_start in future; show countdown
- **Current** – in submission, delay, or voting
- **Past** – voting ended

### 3.3 Badge Card Display

Each badge (role, workgroup, or one-time) shows:

**Upcoming:**
- Countdown to `earliest_start` (e.g. "Starts in 12 days")
- Role/workgroup name or one-time badge title
- Layer (project) name

**Current:**
- Phase: Submission | Delay | Voting
- Dates: first submission, submission end, voting start, voting end
- Progress indicator (e.g. "Submission ends in 3 days")
- Link to submit designs / vote

**Past:**
- "Completed" label
- Winner(s) / primary design
- Dates

### 3.4 Design vs Image Terminology

- API and DB can keep `RoleImage` / `role_image` for now.
- UI: "design", "designs", "Submit design", "View designs", "Design gallery".

---

## 4. Voting Types

### 4.1 Regular Voting

- Current behavior: upvote/downvote, net score.
- Winner: highest net score (or primary chosen by admin).
- Always available.

### 4.2 Time-Weighted Voting (checkbox)

- Votes gain weight the longer they're held.
- Longer commitment = more influence on outcome.

### 4.3 Quadratic Voting (checkbox)

- Cost scales with square of support (e.g. 2 votes cost 4× 1 vote).
- Reduces dominance by large stakeholders.

### 4.4 Combination

- Regular + time-weighted, regular + quadratic, or all three can be enabled per badge.

---

## 5. Database Migrations

### 5.1 Role

```sql
ALTER TABLE role ADD COLUMN badge_submission_days INTEGER DEFAULT 14;
ALTER TABLE role ADD COLUMN badge_voting_days INTEGER DEFAULT 7;
ALTER TABLE role ADD COLUMN badge_delay_days INTEGER DEFAULT 2;
ALTER TABLE role ADD COLUMN badge_earliest_start DATE;
ALTER TABLE role ADD COLUMN badge_voting_type VARCHAR(20) DEFAULT 'regular';
ALTER TABLE role ADD COLUMN badge_voting_time_weighted BOOLEAN DEFAULT FALSE;
ALTER TABLE role ADD COLUMN badge_voting_quadratic BOOLEAN DEFAULT FALSE;
ALTER TABLE role ADD COLUMN badge_trigger VARCHAR(30) DEFAULT 'first_submission';
ALTER TABLE role ADD COLUMN badge_cycle_spacing_days INTEGER DEFAULT 365;
ALTER TABLE role ADD COLUMN badge_end_date DATE;
ALTER TABLE role ADD COLUMN badge_end_at_next_closing BOOLEAN DEFAULT FALSE;
ALTER TABLE role ADD COLUMN badge_skin_id VARCHAR(50);
```

### 5.2 Workgroup

```sql
ALTER TABLE working_group ADD COLUMN badge_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE working_group ADD COLUMN badge_submission_days INTEGER;
ALTER TABLE working_group ADD COLUMN badge_voting_days INTEGER;
ALTER TABLE working_group ADD COLUMN badge_delay_days INTEGER;
ALTER TABLE working_group ADD COLUMN badge_earliest_start DATE;
ALTER TABLE working_group ADD COLUMN badge_voting_type VARCHAR(20) DEFAULT 'regular';
ALTER TABLE working_group ADD COLUMN badge_voting_time_weighted BOOLEAN DEFAULT FALSE;
ALTER TABLE working_group ADD COLUMN badge_voting_quadratic BOOLEAN DEFAULT FALSE;
ALTER TABLE working_group ADD COLUMN badge_trigger VARCHAR(30) DEFAULT 'first_submission';
ALTER TABLE working_group ADD COLUMN badge_cycle_spacing_days INTEGER DEFAULT 365;
ALTER TABLE working_group ADD COLUMN badge_end_date DATE;
ALTER TABLE working_group ADD COLUMN badge_end_at_next_closing BOOLEAN DEFAULT FALSE;
ALTER TABLE working_group ADD COLUMN badge_skin_id VARCHAR(50);
```

### 5.3 One-Time Badge (new table)

```sql
CREATE TABLE one_time_badge (
  id VARCHAR(50) PRIMARY KEY,
  project_id VARCHAR(50) NOT NULL REFERENCES project(id),
  title VARCHAR(255) NOT NULL,
  description TEXT,
  earliest_start DATE NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  submission_days INTEGER NOT NULL DEFAULT 14,
  delay_days INTEGER DEFAULT 2,
  voting_days INTEGER NOT NULL DEFAULT 7,
  voting_type VARCHAR(20) DEFAULT 'regular',
  voting_time_weighted BOOLEAN DEFAULT FALSE,
  voting_quadratic BOOLEAN DEFAULT FALSE,
  badge_skin_id VARCHAR(50),
  status VARCHAR(20) DEFAULT 'draft',
  first_submission_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP
);
```

### 5.4 Badge Cycle Tracking (for recurring badges)

Tracks current/active cycle; next cycle can start only after `badge_cycle_spacing_days` from previous `voting_ends_at`, and only if before `badge_end_date` (if set).

```sql
CREATE TABLE badge_cycle (
  id VARCHAR(50) PRIMARY KEY,
  entity_type VARCHAR(20) NOT NULL,  -- 'role' | 'workgroup'
  entity_id VARCHAR(100) NOT NULL,   -- role_slug or workgroup id
  project_id VARCHAR(50) NOT NULL,
  first_submission_at TIMESTAMP,
  submission_ends_at TIMESTAMP,
  voting_starts_at TIMESTAMP,
  voting_ends_at TIMESTAMP,
  status VARCHAR(20),  -- submission | delay | voting | completed
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.5 Badge Skin (layout templates)

```sql
CREATE TABLE badge_skin (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  slug VARCHAR(100) UNIQUE NOT NULL,
  description TEXT,
  layout_spec JSONB,
  preview_image_url VARCHAR(500),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.6 Design Model (polymorphic extension)

Extend `role_image` to support roles, workgroups, one-time badges:

```sql
ALTER TABLE role_image ADD COLUMN entity_type VARCHAR(20) DEFAULT 'role';  -- 'role' | 'workgroup' | 'one_time_badge'
ALTER TABLE role_image ADD COLUMN entity_id VARCHAR(100);  -- role_slug, workgroup id, or one_time_badge id
-- role_slug remains for backward compat; entity_type+entity_id take precedence when set
ALTER TABLE role_image ADD COLUMN cycle_id VARCHAR(50);  -- FK to badge_cycle when applicable
```

---

## 6. API Changes

### 6.1 New Endpoints

- `GET /api/badges/` – list badges (roles, workgroups, one-time) with status, dates, filters
- `GET /api/badges/upcoming/` – upcoming only
- `GET /api/badges/current/` – in progress
- `GET /api/badges/past/` – completed
- `GET /api/badges/<entity_type>/<entity_id>/cycle/` – current cycle for role/workgroup
- `POST /api/one-time-badges/` – create one-time badge (admin)
- `GET /api/one-time-badges/<id>/` – one-time badge detail

### 6.2 Modified Endpoints

- Role/workgroup `to_dict()` – include new badge fields
- `GET /api/role-images/roles-with-stats/` – extend to include badge config, cycle status, earliest_start

---

## 7. UI Components

### 7.1 Badges Directory Page

- Tabs: Upcoming | Current | Past
- Badge cards with:
  - Countdown (upcoming)
  - Phase + dates (current)
  - Winner + dates (past)
- Actions: Add design (from Actions box, as modal)

### 7.2 Role/Workgroup Admin

- Badge settings section:
  - Badge enabled (checkbox)
  - Earliest start (date picker)
  - Submission days, delay days, voting days
  - Voting: Regular (default) + Time-weighted (checkbox) + Quadratic (checkbox)
  - Cycle spacing (days, default 365)
  - End date (optional date picker)
  - "Set end date to next closing date" (checkbox)
  - Badge skin (dropdown with preview)
  - Trigger: First submission

### 7.3 One-Time Badge Admin

- Create/edit form:
  - Title, description
  - Earliest start
  - Quantity (# to award)
  - Submission days, delay days, voting days
  - Voting: Regular + Time-weighted + Quadratic (checkboxes)
  - Badge skin (dropdown with preview)

---

## 8. Implementation Phases

### Phase 1: Model & Settings (no UI)
- Add Role badge fields + migration
- Add Workgroup badge fields + migration
- Update Role/Workgroup `to_dict()`
- Admin UI for badge settings (role/workgroup edit)

### Phase 2: Badges Page Rename & Filters
- Rename Images → Badges in nav and routes
- Terminology: designs instead of images
- Tabs: Upcoming | Current | Past (stub logic)

### Phase 3: Cycle Logic & Display
- Badge cycle computation (earliest_start, first_submission, dates)
- BadgeCycle model or computed view
- Badge cards with countdown, phase, dates

### Phase 4: One-Time Badges
- OneTimeBadge model + migration
- CRUD API
- Admin UI
- Display on Badges page

### Phase 5: Time-Weighted & Quadratic Voting
- Voting model extensions for time-weighted and quadratic
- Allocation UI for each type
- Result calculation when combined

### Phase 6: Badge Skins
- BadgeSkin model + seed default skins
- Skin picker in badge creation with preview
- Render badge with selected skin + winning design

---

## 9. Resolved Design Decisions

### 9.1 Workgroup Designs
**Decision: A** – Workgroups can have their own designs, separate from roles.
- Workgroups get their own design gallery and voting flow.
- Extend design model with `entity_type` ('role' | 'workgroup') and `entity_id`.

### 9.2 Multiple Cycles & Recurrence
**Decision: C** – One active cycle at a time; role/workgroup controls when next cycle can open.
- **Cycle spacing**: Role/workgroup specifies minimum time between when design submission can open again.
  - Default: 1 year (365 days) from previous cycle's voting end.
  - Configurable (e.g. 30 days, 90 days, 1 year).
- **End date**: Optional hard end date after which no more cycles.
- **Checkbox**: "Set end date to next closing date" – when checked, the end date is set to the voting_end of the current (or next) cycle. Useful for "this badge runs until we close the current round."

**New fields:**
- `badge_cycle_spacing_days` (default 365) – minimum days before next cycle can start
- `badge_end_date` (optional) – no new cycles after this date
- `badge_end_at_next_closing` (boolean) – if true, end_date = next voting_end

### 9.3 Voting Types
**Decision:** Offer **A (time-weighted)** and **B (quadratic)** as options; users can enable one or both via checkboxes.
- **Regular** – existing upvote/downvote (always available).
- **Time-weighted** (checkbox) – votes gain weight the longer they're held.
- **Quadratic** (checkbox) – cost scales with square of support; reduces whale dominance.
- Both can be enabled for a single badge (e.g. quadratic + time-weighted combined).

### 9.4 Design Storage & Badge Skins
**Decision: B** – Reuse/extend design model with `entity_type` + `entity_id` (polymorphic).
- Single design table for roles, workgroups, and one-time badges.
- **Badge skins**: Multiple polymorphic layout templates ("skins") that define placement of:
  - Role/workgroup/badge title
  - Design image
  - Claimant name
  - Dates, etc.
- **Selection**: Chosen during badge creation (role, workgroup, or one-time).
- **Preview**: Selected skin can be previewed with the winning design(s) before/after creation.
- Skins are reusable templates (e.g. "compact", "banner", "card", "minimal").

---

## 10. Badge Skins (Layout Templates)

### 10.1 Concept
A **skin** defines how badge information is laid out – where the image, title, claimant, and other fields appear. Each badge (role, workgroup, one-time) can select a skin.

### 10.2 Skin Model
```python
# BadgeSkin – layout template
- id, name, slug
- description (e.g. "Compact badge with image top, title below")
- layout_spec (JSON or template reference) – defines regions/placements
- preview_image_url (optional) – thumbnail for skin picker
```

### 10.3 Layout Spec (example)
```json
{
  "regions": [
    {"id": "image", "placement": "top", "size": "full"},
    {"id": "title", "placement": "below_image", "font_size": "large"},
    {"id": "claimant", "placement": "footer", "font_size": "small"}
  ]
}
```

### 10.4 Badge Creation Flow
1. Create badge (role/workgroup/one-time).
2. Select skin from dropdown (with preview thumbnails).
3. Preview: render selected skin with placeholder or sample design.
4. After designs are submitted and winner chosen: final badge uses that skin + winning design.

### 10.5 Database
```sql
CREATE TABLE badge_skin (
  id VARCHAR(50) PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  slug VARCHAR(100) UNIQUE NOT NULL,
  description TEXT,
  layout_spec JSONB,
  preview_image_url VARCHAR(500),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add to role, workgroup, one_time_badge:
ALTER TABLE role ADD COLUMN badge_skin_id VARCHAR(50) REFERENCES badge_skin(id);
ALTER TABLE working_group ADD COLUMN badge_skin_id VARCHAR(50) REFERENCES badge_skin(id);
ALTER TABLE one_time_badge ADD COLUMN badge_skin_id VARCHAR(50) REFERENCES badge_skin(id);
```

---

## 11. File Changes Summary

| Area | Files |
|------|-------|
| Models | `ietf_data_viewer_simple.py` (Role, Workgroup, OneTimeBadge, BadgeCycle, BadgeSkin; extend RoleImage with entity_type/entity_id) |
| Migrations | New migration script |
| Routes | `/role-images/` → `/badges/`, `/roles/<slug>/images/` → `/badges/role/<slug>/` or keep for compatibility |
| API | New `/api/badges/`, `/api/badge-skins/`, extend roles-with-stats |
| Templates/HTML | Badges page, role/workgroup admin, one-time badge admin, skin picker with preview |
