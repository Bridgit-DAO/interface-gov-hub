# DP Proposals: Rationale, Reference URL & Unified Invitations

**Status:** Sprint A + B/C implemented on dev (2026-05-27)  
**Last updated:** 2026-05-27  
**Repo:** `gov-hub-dev` (mirror to `gov-hub-prod` on deploy)

This spec implements decisions from planning (May 2026). It extends [DP_PROPOSALS_SPEC.md](./DP_PROPOSALS_SPEC.md) and reuses patterns from `LayerInvitation` / `services/layer_invitations.py`.

---

## 1. Goals

| # | Feature |
|---|---------|
| P1 | Optional **rationale** (public text) and **reference_url** (single https URL) on DP / document proposals |
| P1 | **Mini-hover panel**: one row per proposal (with rationale excerpt), wider panel; full rationale + link in opened proposal view |
| P2 | **Unified invitation service** for all invite scenarios |
| P2 | **Rate limit**: 10 standard invites / user / UTC day; participation invites **excluded** |
| P3 | Workgroup, document (passage + whole), review (non-DP edits off), DP Challenge participation |

---

## 2. Phase 1 — Proposal rationale & reference

### 2.1 Database (`dp_proposal`)

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `rationale` | `TEXT` | Yes | Public; max **4000** chars after normalize |
| `reference_url` | `VARCHAR(2048)` | Yes | https/http only; never fetched server-side |

**Migration:** `migrate_dp_proposal_rationale_reference(app)` in `migrations/__init__.py`; call from `init_db`.

### 2.2 Validation (`services/dp_proposals.py`)

Add `validate_reference_url(url: str) -> Optional[str]`:

- Strip; empty → `None` (allowed)
- Parse with `urllib.parse`; scheme in `http`, `https` only
- Reject `javascript:`, `data:`, `//`, credentials in netloc
- Max length 2048

Extend `validate_create_payload`:

```python
# optional fields
'rationale': normalize_rationale(data.get('rationale')),  # strip, collapse ws, cap 4000
'reference_url': validate_reference_url(data.get('reference_url')),
```

Extend `create_dp_proposal(..., rationale=None, reference_url=None)`.

Extend `DpProposal.to_dict()` → include `rationale`, `reference_url`.

### 2.3 API

`POST /api/doc/draft/<ref>/proposals/` — accept optional `rationale`, `reference_url` in JSON (no change to route shape).

`GET` list — returns new fields on each proposal.

### 2.4 Compose modal (`services/dp_proposal_reader.py` + `reader.js`)

After **Proposed text** textarea:

```html
<label for="dpProposalRationale">Rationale (optional)</label>
<textarea id="dpProposalRationale" rows="3" maxlength="4000"
  placeholder="Why this change improves the standard…"></textarea>
<label for="dpProposalReferenceUrl">Reference URL (optional)</label>
<input type="url" id="dpProposalReferenceUrl" class="form-control"
  placeholder="https://…" inputmode="url">
```

`submitProposal()` payload adds `rationale`, `reference_url`.

### 2.5 List / detail modal (opened proposal)

In `renderListModal` / proposal detail block (`proposal-display.js` or `reader.js`):

- **Rationale:** full text, `white-space: pre-wrap`, public
- **Reference:** link with hostname label, `rel="noopener noreferrer" target="_blank"`
- If empty, omit sections (no placeholders)

Accept/decline controls unchanged; reviewers see rationale + link.

### 2.6 Mini-hover panel (try rationale + double width)

**CSS** (`static/css/dp-proposals-reader.css`):

```css
.dp-proposal-hover-panel {
  min-width: 14rem;
  max-width: min(36rem, calc(100vw - 1.5rem)); /* was 18rem */
  max-height: min(18rem, calc(100vh - 1.5rem)); /* slightly taller */
}
```

**Row structure** (`renderHoverPanelBody` in `reader.js`):

One `<li>` per proposal — single clickable row:

```
[icon] Author · Status · +N −M · "Rationale excerpt…"
```

| Part | Rule |
|------|------|
| Author | `p.author_name` or "Someone" |
| Status | short: `pending` → mode label |
| Delta | existing `proposalCharDeltaHtml` |
| Rationale | If present: ` · ` + truncate to **~80 chars** (ellipsis); CSS `text-overflow: ellipsis; white-space: nowrap; overflow: hidden` on row |
| No rationale | Row = author · status · delta only |
| **No reference URL** in hover | |

Click row → `openListModal(hash, proposalId)` (same as today).

**Actions row** (below `<ul>`):

```html
<div class="dp-proposal-hover-actions">
  <button class="… dp-proposal-create-btn">Suggest a change</button>
  <button class="… dp-proposal-invite-passage-btn">Invite to edit</button>
</div>
```

Stack or side-by-side `btn-sm` on narrow panel; full width stack under 20rem.

### 2.7 Security (reference URL)

| Rule | Implementation |
|------|----------------|
| Store only | No HTTP client fetch of URL |
| https/http only | `validate_reference_url` |
| XSS | Escape in server HTML; JS use `esc()` for text, validated href only |
| Public | Rationale and link visible to all read-page visitors |

---

## 3. Phase 2 — Unified invitations

### 3.1 Model `platform_invitation` (new table)

Avoid overloading `layer_invitation`. New model in `models/platform_invitation.py`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `invite_type` | `VARCHAR(40)` | see §3.2 |
| `inviter_id` | FK `user.id` | required |
| `invitee_email` | `VARCHAR(255)` | indexed, normalized lower |
| `invitee_id` | FK `user.id` | set on accept if matched |
| `message` | `TEXT` | optional personal note |
| `target_json` | `TEXT` | JSON payload per type |
| `status` | `VARCHAR(20)` | `pending`, `accepted`, `declined`, `expired`, `revoked`, `duplicate` |
| `outcome_note` | `VARCHAR(255)` | |
| `token` | `VARCHAR(100)` | unique, indexed |
| `rate_category` | `VARCHAR(20)` | `standard` \| `participation` |
| `created_at` | datetime | |
| `expires_at` | datetime | default **+7 days** |
| `responded_at` | datetime | |

Indexes: `(invite_type, status)`, `(inviter_id, created_at)`, `(invitee_email)`.

**`target_json` schemas:**

```json
// participate_dp
{}

// edit_document
{ "submission_id": "…", "draft_ref": "ML-Draft-002" }

// edit_document_passage
{ "submission_id": "…", "draft_ref": "…", "anchor_hash": "…", "context_anchor": {…} }

// review_document  (document_edits OFF)
{ "submission_id": "…", "draft_ref": "…" }

// join_workgroup
{ "workgroup_id": "…", "workgroup_slug": "…", "layer_id": "…" }
```

### 3.2 Invite types

| `invite_type` | `rate_category` | Landing path |
|---------------|-----------------|--------------|
| `participate_dp` | `participation` | `/dp-challenge/?invite=<token>` |
| `edit_document` | `standard` | `/doc/draft/<ref>/read/?invite=<token>` |
| `edit_document_passage` | `standard` | same + server resolves anchor → scroll/highlight |
| `review_document` | `standard` | `/doc/draft/<ref>/read/?invite=<token>` |
| `join_workgroup` | `standard` | `/workgroups/<slug>/?invite=<token>` |

### 3.3 Service `services/platform_invitations.py`

Single entry points (all scenarios):

```python
INVITE_TYPES = frozenset({...})
STANDARD_DAILY_LIMIT = 10
INVITE_TTL_DAYS = 7

def normalize_invitee_email(email: str) -> str: ...
def validate_invitee_email(email: str) -> bool: ...

def count_standard_invites_today(inviter_id: str) -> int: ...
def check_rate_limit(inviter_id: str, rate_category: str) -> Optional[str]:
    """None ok; else error message."""

def can_invite(inviter_id: str, invite_type: str, target: dict) -> Tuple[bool, str]:
    """Type-specific permission check."""

def build_landing_path(inv: PlatformInvitation) -> str: ...

def create_invitation(
    *,
    invite_type: str,
    inviter_id: str,
    invitee_email: str,
    message: Optional[str],
    target: dict,
) -> Tuple[dict, int]:
    """
    Shared pipeline:
    1. Auth implied (caller is route)
    2. can_invite
    3. check_rate_limit (skip if participation)
    4. Resolve review_document vs edit_document from submission + flags
    5. Upsert pending row / refresh token (like layer)
    6. send_platform_invitation_email
    7. Return { invitation, invite_path, email_sent }
    """

def preview_invitation(token: str) -> Tuple[dict, int]: ...
def accept_invitation(token: str, user_id: str) -> Tuple[dict, int]: ...
def decline_invitation(token: str, user_id: str) -> Tuple[dict, int]: ...
```

**Type handlers** (internal, registered dict):

| Handler | `can_invite` | `accept` |
|---------|--------------|----------|
| `participate_dp` | any authenticated user | mark accepted; optional analytics event |
| `edit_document` | user can view draft (approved submission) | redirect context stored; banner on read page |
| `edit_document_passage` | same | + stash anchor in session/`localStorage` for reader |
| `review_document` | same; **only if** `document_edits` off for submission | banner “review”; no compose |
| `join_workgroup` | active WG **member** OR **layer admin** for WG’s layer | if `members_require_approval`: create `WorkgroupMemberRequest` with `invited_by_user_id`, `invitation_id`; else `join_workgroup` insert |

### 3.4 Workgroup member request extension

Add nullable columns to `WorkgroupMemberRequest` (migration):

| Column | Type |
|--------|------|
| `invited_by_user_id` | `VARCHAR(36)` FK user |
| `platform_invitation_id` | `VARCHAR(36)` FK |

Existing approve flow unchanged; UI shows “Invited by {name}”.

### 3.5 Permissions detail

**`join_workgroup`:**

- `WorkingGroupMember` active for `group_acronym` → can invite
- OR `is_layer_admin(layer, user)` for workgroup’s linked layer

**`edit_document` / `edit_document_passage`:**

- Inviter authenticated
- Submission `status == 'approved'`
- If DP: `is_mode_enabled('dp')`
- If non-DP and `document_edits` off: coerce type to `review_document` at create time (option **B**)

**`participate_dp`:**

- Any authenticated user; no target validation

### 3.6 Email `services/platform_invitation_mail.py`

Mirror `layer_invitation_mail.py`:

- Resend template per `invite_type`
- Variables: inviter name, target title (doc title / WG name / “DP Challenge”), `invite_url`, personal message
- `PUBLIC_BASE_URL` from config

### 3.7 API routes `routes/platform_invitations.py`

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/invitations/` | required |
| GET | `/api/invitations/by-token/<token>/` | public preview |
| POST | `/api/invitations/by-token/<token>/accept/` | required |
| POST | `/api/invitations/by-token/<token>/decline/` | required |

**POST body:**

```json
{
  "type": "edit_document_passage",
  "email": "colleague@example.com",
  "message": "optional note",
  "target": {
    "submission_id": "j64tnris",
    "draft_ref": "ML-Draft-002",
    "anchor_hash": "abc…",
    "context_anchor": { "textQuote": { "exact": "…" } }
  }
}
```

Register blueprint in `app.py`. Add rollout-exempt paths for `/api/invitations/by-token/` preview.

### 3.8 Landing UX (read page)

**Storage:** `session['pending_invite_token']` or query `?invite=` → JS `gh_invite` like `gh_layer_invite`.

**Banner** (`#gh-invite-banner` on read page / workgroup / dp-challenge):

```
{inviter} invited you to {action label} on {target title}.
[Dismiss]
```

**After login:** `accept` via API or auto-accept on landing when email matches.

**Passage invite:** reader boot reads `meta.pending_invite` → `locateAnchor` → open compose optional.

### 3.9 UI entry points (Phase 2–3)

| Surface | Action | `invite_type` |
|---------|--------|---------------|
| Hover actions row | Invite to edit | `edit_document_passage` |
| Read toolbar | Invite to edit document | `edit_document` or `review_document` |
| Draft record header | Invite to review/edit | `edit_document` / `review_document` |
| Workgroup page modal | Invite member | `join_workgroup` |
| DP Challenge header | Invite to participate | `participate_dp` |
| Compose modal footer (optional P3) | Invite collaborator | `edit_document_passage` |

Shared modal component: email + message → `POST /api/invitations/`.

### 3.10 Rate limiting

```python
# services/platform_invitations.py
def count_standard_invites_today(inviter_id: str) -> int:
    # UTC midnight boundary
    # WHERE inviter_id AND rate_category='standard' AND created_at >= today

def check_rate_limit(inviter_id, rate_category):
    if rate_category == 'participation':
        return None
    if count_standard_invites_today(inviter_id) >= 10:
        return 'Invitation limit reached for today (10). Try again tomorrow.'
```

Use existing `check_rate_limit` helper from `services/utils` if compatible, or dedicated counter.

---

## 4. Implementation order (coding checklist)

### Sprint A — Rationale (ship first)

- [x] Migration + model columns
- [x] `validate_reference_url`, `validate_create_payload`, `create_dp_proposal`, `to_dict`
- [x] Compose modal HTML + `submitProposal` payload
- [x] List/detail modal: rationale + reference link
- [x] Hover: double width CSS + one-line rows with rationale excerpt
- [x] Tests: `test_dp_proposals.py` — create with rationale/url, reject `javascript:`
- [x] Cache-bust reader CSS/JS query params

### Sprint B — Invitation core

- [x] Model `PlatformInvitation` + migration
- [x] `services/platform_invitations.py` (create/preview/accept/decline/rate limit)
- [x] `services/platform_invitation_mail.py`
- [x] `routes/platform_invitations.py` + `app.py` register
- [x] `test_platform_invitations.py`
- [x] `static/js/gh-invite.js` (banner + modal) in base template

### Sprint C — Wire surfaces

- [x] Hover + read toolbar invite → API
- [x] Workgroup page Invite button (members)
- [x] DP Challenge “Invite a colleague”
- [x] `WorkgroupMemberRequest` invited_by columns + accept path
- [x] Read-page banner via `?invite=` + Accept

### Sprint D — Polish

- [ ] Admin list/revoke invitations (optional)
- [ ] Product rollout docs update
- [ ] Deploy prod: migration + SiteConfig unchanged

---

## 5. Files to create / modify

### New files

| Path |
|------|
| `models/platform_invitation.py` |
| `services/platform_invitations.py` |
| `services/platform_invitation_mail.py` |
| `routes/platform_invitations.py` |
| `static/js/gh-invite.js` (banner + modal helper) |
| `test_platform_invitations.py` |
| `test_dp_proposal_rationale.py` (or extend `test_dp_proposals.py`) |

### Modified files (Phase 1)

| Path |
|------|
| `models/dp_proposal.py` |
| `migrations/__init__.py` |
| `models/__init__.py` |
| `services/dp_proposals.py` |
| `routes/dp_proposals.py` (pass-through only if needed) |
| `services/dp_proposal_reader.py` |
| `static/js/dp-proposals/reader.js` |
| `static/js/dp-proposals/proposal-display.js` (if detail render lives here) |
| `static/css/dp-proposals-reader.css` |
| `test_dp_proposals.py` |

### Modified files (Phase 2+)

| Path |
|------|
| `app.py` |
| `models/coordination.py` (`WorkgroupMemberRequest` columns) |
| `migrations/__init__.py` |
| `routes/workgroups_pages.py` |
| `routes/dp_challenge_pages.py` |
| `routes/documents.py` (toolbar invite button) |
| `services/product_rollout.py` (exempt paths) |
| `templates/html_templates.py` (optional global invite banner hook) |

---

## 6. Test plan

### Rationale

- Create proposal with rationale + https URL → 201, fields in GET
- `javascript:alert(1)` → 400
- Empty rationale/url → OK
- Hover HTML contains truncated rationale, not full URL

### Invitations

- Member invites to WG → 201, email mock/log
- 11th standard invite same day → 429
- 11th `participate_dp` same day → 201
- Non-member cannot `join_workgroup` invite → 403
- `review_document` when `document_edits` off
- Accept WG with approval → pending request with `invited_by_user_id`
- Token expired → 410 on accept

---

## 7. Open items (non-blocking)

- Deep-link scroll to passage on accept (use existing `locate` + `anchor_hash`)
- i18n keys for invite strings (shell JSON later)
- Refactor `LayerInvitation` to use `platform_invitations` long-term (out of scope; keep parallel)

---

## 8. Reference: current hover CSS baseline

```145:151:gov-hub-dev/static/css/dp-proposals-reader.css
.dp-proposal-hover-panel {
  min-width: 14rem;
  max-width: min(18rem, calc(100vw - 1.5rem));
  max-height: min(14rem, calc(100vh - 1.5rem));
  ...
}
```

**Target:** `max-width: min(36rem, calc(100vw - 1.5rem))`, `max-height: min(18rem, …)`.

---

## 9. Ready-to-code: first PR slice

Implement **Sprint A only** as first PR:

1. Migration
2. Backend validation + API
3. Compose + list/detail UI
4. Hover width + rationale rows (no invite button yet)

Second PR: Sprint B + C (invitations).

This matches “try mini-hover with rationale and double width” before inviting complexity on the hover panel.
