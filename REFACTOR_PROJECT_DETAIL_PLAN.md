# Project Detail Page Refactor Plan

**Project:** gov-hub-dev  
**Scope:** Project detail page (`/projects/<slug>/`)  
**Source:** `ietf_data_viewer_simple.py` – `_render_project_detail()`, `project_detail()`, `project_detail_waitlist()`

---

## Current Structure

```
┌─────────────────────────────────────────────────────────────┐
│  project-header (above tabs)                                │
│  - Project name, description, status, image                  │
│  - Actions: Join, Create Waitlist, Create Vote, Back, Edit   │
├─────────────────────────────────────────────────────────────┤
│  Tabs: Overview | Workgroups | Clusters | Roles | Claims |   │
│        Votes | Admin | Waitlists                            │
├─────────────────────────────────────────────────────────────┤
│  Tab content                                                 │
│  - Overview: Layer Information + Quick Stats cards           │
│  - Workgroups, Clusters, Roles, Claims, Votes, Admin, etc.  │
└─────────────────────────────────────────────────────────────┘
```

---

## Requirements

1. **Move tabs to the top** – Tabs become the first element on the page.
2. **New first tab "Overview" (default)** – Overview is the first tab and opens by default.
3. **Overview = current main content** – The project header (name, description, image, actions) + current overview content (Layer Information, Quick Stats) move into the Overview tab pane.
4. **Record current and previous tabs** – Persist tab state.
5. **Restore tab on return** – When returning to the page, open the last active tab.

---

## Refactor Plan

### 1. Layout Change: Tabs First, Header Inside Overview

**Before:**
```
[project-header]
[tabs]
[tab-content]
```

**After:**
```
[tabs]  ← at top
[tab-content]
  Overview pane: [project-header + overview cards]
  Other panes: unchanged
```

**Changes:**
- Move the `<ul class="nav nav-tabs">` to be the first visible content in the container (before any tab content).
- Move `#project-header` from above the tabs into `#overview-content` (or a wrapper inside the Overview tab pane).
- `displayProjectHeader()` will target an element inside the Overview pane instead of a sibling of the tabs.

### 2. Overview Tab Content

**Current Overview content:**
- Layer Information card (status, approval, created, last activity)
- Quick Stats card (workgroups, roles, claims counts)

**New Overview content (in order):**
1. Project header block (name, description, status badges, image, actions card)
2. Layer Information card
3. Quick Stats card

**Implementation:**
- `loadOverview()` builds: header HTML + existing cards.
- `displayProjectHeader()` either:
  - (A) Writes into a dedicated `#project-header` div inside `#overview-content`, or
  - (B) Is merged into `loadOverview()` so the header is part of the overview HTML.
- Option (B) is simpler: `loadOverview()` calls a helper that returns header HTML, then appends the cards. `displayProjectHeader()` updates that same container (e.g. `#overview-header` inside `#overview-content`).

### 3. Tab State Persistence

**Storage:** `localStorage`  
**Key:** `projectDetailTab_${projectSlug}` (or `projectDetailTab_${projectId}` for stability if slug can change)

**Stored value:**
```json
{
  "current": "votes",
  "previous": "overview"
}
```

Or a simpler format: `"votes"` for current only; previous can be derived from the last two tab switches.

**Simpler approach:**
- `projectDetailTab_current` = tab id (e.g. `"overview"`, `"votes"`, `"waitlist-123"`)
- `projectDetailTab_previous` = previous tab id  
- Use project-scoped keys: `projectDetailTab_${projectSlug}_current` and `projectDetailTab_${projectSlug}_previous`

### 4. Tab Switch Handling

**On tab switch (Bootstrap `shown.bs.tab`):**
1. Read the newly shown tab’s id (e.g. from `event.target.id` → `overview-tab`, `votes-tab`, `waitlist-tab-42`).
2. Map to a stable tab key: `overview`, `workgroups`, `clusters`, `roles`, `claims`, `votes`, `admin`, `waitlist-42`.
3. Update `projectDetailTab_${projectSlug}_previous` = current value of `_current`.
4. Update `projectDetailTab_${projectSlug}_current` = new tab key.

**On page load (after `loadProject`):**
1. After `displayProjectHeader()`, `loadOverview()`, `buildWaitlistTabs()`.
2. Check `initialWaitlistId` (URL `/projects/<slug>/waitlist/<id>/`) – if set, open that waitlist tab (existing behavior).
3. Else read `projectDetailTab_${projectSlug}_current` from localStorage.
4. If valid and that tab exists, programmatically activate it (e.g. `document.getElementById('votes-tab')?.click()`).
5. Otherwise keep default (Overview).

### 5. Edge Cases

| Case | Behavior |
|------|----------|
| First visit | Overview (default) |
| Return to same project | Last active tab |
| Return to different project | That project’s last tab (or Overview if none) |
| URL has `waitlist/<id>` | Open that waitlist tab (override stored tab) |
| Stored tab no longer exists | Fall back to Overview |
| Waitlist tabs dynamic | Waitlist tab ids like `waitlist-tab-42`; store `waitlist-42` and resolve after `buildWaitlistTabs()` |

### 6. File Changes Summary

| Location | Change |
|----------|--------|
| `_render_project_detail()` HTML | Move tabs above header; put `#project-header` inside Overview pane |
| `displayProjectHeader()` | Target element inside Overview pane |
| `loadProject()` | After building waitlists, apply stored tab or `initialWaitlistId` |
| New JS | `getProjectTabKey(buttonId)`, `saveTabState(current, previous)`, `restoreTabState()` |
| Tab listeners | Add logic to record current/previous on `shown.bs.tab` |

### 7. Implementation Order

1. Move `#project-header` into Overview pane; adjust `displayProjectHeader()` target.
2. Move tabs to the top (they may already be above content; ensure they are the first visible element).
3. Add `saveTabState` / `restoreTabState` and wire into tab `shown.bs.tab`.
4. On load, call `restoreTabState()` after `buildWaitlistTabs()`, respecting `initialWaitlistId`.
5. Test: first visit, switch tabs, reload, different projects, waitlist URL.

---

## Notes

- **Overview already exists** – The Overview tab is already first and default. The main change is moving the project header into it.
- **Waitlist URL** – `/projects/<slug>/waitlist/<id>/` should still open the specific waitlist tab; this overrides stored state.
- **Admin tab** – Conditionally rendered; ensure stored tab is validated before activation.
