# Plan: Layer View Fixes

## Summary of Issues

1. **Admin view should not show** – Layer-centric view (`/layer/<slug>/`) should show title + carousel only, not admin content
2. **No About/Admin row** – Removed; never desired (no such row in codebase)
3. **About in menu doesn't go to About page** – Governance → About link may be broken or pointing to wrong URL
4. **Nav links take user out of layer view** – Clicking Governance items (Roles, Workgroups, Votes, Artifacts) navigates to global view (`/layers/`) instead of staying in layer view (`/layer/<slug>/`)
5. **Artifacts and Votes** – Need filtering, search, list matching; when in layer view, only show entries for that layer
6. **Workgroups** – When in layer view, only show entries for that layer (already has Layer filter; needs layer-context awareness)

---

## 1. Admin View & About/Admin Row

### Current State
- `layer_detail_render.py`: Admin tab is already hidden when `standalone=True` (lines 32–44)
- No `standalone_links` row in current code (removed per comment at line 47)
- Layer-centric view uses `tabs_hidden_class = ' d-none'` so tabs (Overview, Workgroups, etc.) are hidden

### Likely Cause
- **Deployment lag** – Dev may be serving an older build that still has `standalone_links` and Admin tab
- Or a different code path (e.g. subdomain) is rendering the global view instead of standalone

### Plan
1. **Verify deployment** – Ensure latest `layer_detail_render.py` is deployed to dev.hub.themetalayer.org
2. **Confirm no regressions** – Search codebase for any remaining `standalone_links` or `About | Admin` strings
3. **Standalone content** – Ensure when `standalone=True`, only `displayProjectHeader` (title + badges) and carousel are shown in the overview; no admin content anywhere

---

## 2. About Link in Governance Menu

### Current State
- `services/rendering.py` `generate_governance_nav(layer_slug, standalone=True)`:
  - `about_href = '/layer/' + layer_slug + '/about/'` when standalone
- Route exists: `pages.layer_standalone_about` at `/layer/<layer_ref>/about/`

### Possible Causes
- `standalone=True` not passed when rendering (e.g. wrong template or `g.layer_slug` not set)
- Base URL / SCRIPT_NAME / proxy prefix breaking relative links
- About link in nav is correct but another link (e.g. from a different template) is wrong

### Plan
1. **Trace rendering** – Confirm `render_layer_standalone_page` is used for `/layer/<slug>/` and passes `standalone=True` to `generate_governance_nav`
2. **Inspect nav HTML** – Log or inspect the rendered `governance_nav` HTML to verify About href is `/layer/<slug>/about/`
3. **Fix base URL** – If behind a proxy (e.g. `/dev/`), ensure links use correct base path

---

## 3. Nav Links Take User Out of Layer View

### Root Cause
In `generate_governance_nav`, when `layer_slug` is set, **only About** uses `/layer/<slug>/` when `standalone=True`. All other links use `/layers/<slug>/`:

```python
# Current (problematic):
'<li><a class="dropdown-item" href="/layers/' + layer_slug + '/#roles">Roles</a></li>',
'<li><a class="dropdown-item" href="/layers/' + layer_slug + '/#workgroups">Workgroups</a></li>',
# etc.
```

- `/layers/<slug>/` = global view (g.layer_slug not set by middleware)
- `/layer/<slug>/` = layer-centric view (g.layer_slug set)

So clicking Roles, Workgroups, Votes, Artifacts, Opportunities navigates to `/layers/` and leaves layer view.

### Plan
1. **Update `generate_governance_nav`** – When `standalone=True`, use `/layer/<slug>/` for all layer-scoped links:
   - Roles: `/layer/<slug>/#roles`
   - Workgroups: `/layer/<slug>/#workgroups`
   - Votes: `/layer/<slug>/#votes`
   - Artifacts: `/layer/<slug>/#artifacts`
   - Opportunities: `/layer/<slug>/#opportunities`
2. **Layer view tabs** – In standalone mode, tabs are hidden (`d-none`). Decide:
   - **Option A**: Keep tabs hidden; nav links become no-ops or scroll to a section (if any)
   - **Option B**: Show tabs in layer view so these fragment links switch tabs as intended
3. **Other nav items** – Contribute, Community, Recognition, Learn: ensure links stay layer-scoped when in layer view (e.g. `/layer/<slug>/...` where applicable)

---

## 4. Artifacts & Votes: Filtering, Search, Layer-Scoped View

### Current State
- **Votes** (`/votes/`): Landing page only – "Browse layers to find votes", no list, no filters
- **Artifacts** (`/artifacts/`): Same – "Browse layers to find artifacts", no list, no filters
- **Workgroups** (`/workgroups/`): Has Layer filter, Status filter, Search; loads from `/api/layers/<id>/workgroups/`

### Plan

#### 4a. Layer context awareness
- When `g.layer_slug` is set (from `/layer/<slug>/` or subdomain), directory pages should:
  - Pre-select that layer in filters, or
  - Redirect to a layer-scoped URL, or
  - Render a layer-scoped view by default

#### 4b. Votes directory
1. Add a **list of votes** (similar to workgroups) with:
   - Layer filter (dropdown)
   - Status filter (active, closed, etc.)
   - Search (title, description)
2. When `g.layer_slug` is set: pre-select that layer and show only its votes
3. Use existing API: `GET /api/layers/<layer_id>/votes/`

#### 4c. Artifacts directory
1. Add a **list of artifacts** with:
   - Layer filter
   - Status/type filter
   - Search (title, ref, etc.)
2. When `g.layer_slug` is set: pre-select that layer and show only its artifacts
3. Use existing API: `GET /api/layers/<layer_id>/artifacts/`

#### 4d. Opportunities directory
- Same pattern: list + filters + search; layer-scoped when `g.layer_slug` is set

---

## 5. Workgroups: Layer-Scoped When in Layer View

### Current State
- `/workgroups/` has Layer, Status, Search filters
- Loads workgroups from API; when Layer filter is set, uses `/api/layers/<id>/workgroups/`

### Plan
1. **Layer context** – When `g.layer_slug` is set:
   - Pre-select that layer in the Layer dropdown
   - Call `loadWorkgroups()` with that layer so only that layer’s workgroups are shown
2. **URL option** – Consider `/layer/<slug>/workgroups/` as a layer-scoped workgroups page that:
   - Uses layer template
   - Shows only that layer’s workgroups
   - Keeps user in layer view

---

## 6. Implementation Order

| Phase | Task | Files |
|-------|------|-------|
| 1 | Fix governance nav links to use `/layer/` when standalone | `services/rendering.py` |
| 2 | Verify/fix About link and Admin/About row removal | `layer_detail_render.py`, deployment |
| 3 | Decide: show or hide tabs in layer view; adjust nav behavior | `layer_detail_render.py`, `rendering.py` |
| 4 | Add Votes directory list + filters + search + layer pre-select | `routes/directory.py` |
| 5 | Add Artifacts directory list + filters + search + layer pre-select | `routes/directory.py` |
| 6 | Add Opportunities directory list (if needed) | `routes/directory.py` |
| 7 | Workgroups: pre-select layer when `g.layer_slug` set | `routes/directory.py` |
| 8 | Optional: layer-scoped routes `/layer/<slug>/votes/`, `/layer/<slug>/artifacts/`, etc. | `routes/pages.py`, `directory.py` |

---

## 7. Testing Checklist

- [ ] On `/layer/the-metaweb/`: no Admin tab, no About/Admin row
- [ ] On `/layer/the-metaweb/`: title + carousel visible
- [ ] Governance → About goes to `/layer/the-metaweb/about/`
- [ ] Governance → Roles stays on `/layer/the-metaweb/` (or switches to Roles tab if tabs shown)
- [ ] Same for Workgroups, Votes, Artifacts, Opportunities
- [ ] `/votes/` with `g.layer_slug` set: shows only that layer’s votes
- [ ] `/artifacts/` with `g.layer_slug` set: shows only that layer’s artifacts
- [ ] `/workgroups/` with `g.layer_slug` set: Layer filter pre-selected, only that layer’s workgroups
- [ ] Filtering and search work on Votes, Artifacts, Workgroups

---

## 8. Open Questions

1. **Tabs in layer view** – Should layer view show tabs (Overview, Workgroups, Roles, etc.) or only title + carousel? Current code hides them.
2. **Layer-scoped directory URLs** – Prefer `/workgroups/?layer=the-metaweb` or `/layer/the-metaweb/workgroups/`?
3. **Subdomain behavior** – When on `the-metaweb.rfc.themetalayer.org`, should home go to `/layer/the-metaweb/` or `/layers/the-metaweb/`? Currently it redirects to `/layers/`.
