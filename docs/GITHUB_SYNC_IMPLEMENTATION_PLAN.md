# Gov Hub → GitHub Document Sync: Implementation Plan

**Project:** gov-hub-dev  
**Date:** 2026-04-13  
**Status:** Planned — not yet started  

---

## Decision Context

- **Pattern A**: Gov Hub commits directly to `main` (no PR for RFC paths).
- **Auth model**: GitHub App (org-level, installed on target repo only).
- **Paths**: `m-draft/**` (working drafts) and `ml-rfc/**` (formal RFCs).
- **User experience**: Single Save button in Gov Hub; no GitHub UI interaction required.
- **Drafts are public**: everything committed to the repo is publicly visible.
- **Conflict policy**: 409 → reject B's save, surface "refresh" message — no silent overwrite.
- **Future**: IPFS CID and Ordinal inscription IDs written into Markdown frontmatter; GitHub = index of record across all three content-addressed copies.

---

## Phase 0 — Foundation (pre-code decisions)

### 0.1 GitHub Repo
- Confirm target repo (existing `Bridgit-DAO/interface-gov-hub` or new `Bridgit-DAO/ml-documents`).
- Default branch: `main`.
- Folder layout:
  ```
  m-draft/     ← working / low-ceremony drafts
  ml-rfc/      ← formal RFC-shaped documents
  archive/     ← superseded / withdrawn (optional)
  ```

### 0.2 GitHub App Creation
- Create GitHub App under Bridgit org.
- Permissions: `Contents: Read & Write`, `Metadata: Read`.
- Install on **target repo only** (least privilege).
- Store private key (`.pem`) as env var / secrets manager — never committed.

### 0.3 Repo Ruleset (Branch Protection)
- `main` blocked for all direct pushes **except** the GitHub App.
- **Path filter bypass**: App may push only to `m-draft/**` and `ml-rfc/**`.
- All other paths remain human-PR-gated.
- Validate with a test commit from the app installation.

### 0.4 Gov Hub Config Additions
New keys in `.env` / `config.py`:
```
GITHUB_APP_ID
GITHUB_APP_PRIVATE_KEY        # PEM string or path
GITHUB_APP_INSTALLATION_ID    # for target repo
GITHUB_RFC_REPO               # org/repo
GITHUB_DRAFT_PREFIX           # m-draft/
GITHUB_RFC_PREFIX             # ml-rfc/
```
Feature flag: if `GITHUB_APP_ID` is absent, skip GitHub sync silently.

---

## Phase 1 — GitHub Service Layer

New module: `services/github_sync.py` — pure API calls, no Flask dependency.

### 1.1 Authentication
- GitHub App JWT flow: sign short-lived JWT with private key + app ID.
- Exchange for installation access token (1-hour TTL).
- Cache token in-process; refresh before expiry.

### 1.2 Core Operations

| Operation | GitHub API | Notes |
|-----------|-----------|-------|
| `get_file(path)` | `GET /repos/{repo}/contents/{path}` | Returns content + blob SHA |
| `put_file(path, content, sha, message, author)` | `PUT /repos/{repo}/contents/{path}` | `sha=None` for new; blob SHA for update |
| `delete_file(path, sha, message)` | `DELETE /repos/{repo}/contents/{path}` | Used during draft → RFC promote |
| `list_files(prefix)` | `GET /repos/{repo}/contents/{prefix}` | Returns tree listing |

### 1.3 Conflict Handling
- HTTP 409 or SHA mismatch → raise `GitConflictError(current_sha)`.
- Caller catches and returns user-facing "refresh" message.

### 1.4 Author Attribution
- Every `put_file` carries `author = {"name": user.displayName, "email": noreply_or_fallback}`.
- GitHub noreply format: `{github_user_id}+{login}@users.noreply.github.com`
  - Use if user has linked GitHub account (already stored via `social_connect`).
  - Fall back to a Gov Hub noreply address otherwise.
- Committer = GitHub App bot identity (set automatically by the installation token).

### 1.5 Commit Message Format
```
draft(m-draft): update {slug} — {user.username}
rfc(ml-rfc): publish {slug} v{version} — {user.username}
promote: m-draft/{slug} → ml-rfc/{slug} — {user.username}
archive(ml-rfc): withdraw {slug} — {user.username}
```

---

## Phase 2 — Document Model Extensions

New migration: `migrate_github_sync_v1`

### 2.1 New DB Columns on Submission / draft table
| Column | Type | Purpose |
|--------|------|---------|
| `github_path` | `TEXT` | Canonical path in repo (e.g. `m-draft/foo.md`), nullable |
| `github_sha` | `TEXT` | Last known blob SHA; used for conflict detection |
| `github_synced_at` | `DATETIME` | Timestamp of last successful sync |
| `github_sync_error` | `TEXT` | Last error message if sync failed; null if clean |

### 2.2 SHA Lifecycle
- On successful `put_file` → store returned SHA in `github_sha`.
- On open for editing → re-confirm SHA (from DB or re-fetch from GitHub).
- Pass SHA to editor as hidden field; read it back on save POST.

---

## Phase 3 — Route Integration

### 3.1 Save / Update Draft (`m-draft/**`)
1. Existing save handler runs (DB upsert).
2. Calls `github_sync.put_file(...)` **after** DB write.
3. On success → update `github_sha`, clear `github_sync_error`.
4. On `GitConflictError` → HTTP 409 → "Someone else updated this; please refresh."
5. On other error → log, set `github_sync_error`, return warning ("saved locally; GitHub sync failed").

### 3.2 Publish / Promote to RFC (`ml-rfc/**`)
1. Commit final content to `ml-rfc/{slug}.md`.
2. If previously existed at `m-draft/{slug}.md` → `delete_file` that path.
3. Update DB: `github_path = ml-rfc/...`, clear old draft path.
- Two sequential API calls (no atomic transaction on Contents API; acceptable).

### 3.3 Slug / Filename Policy
- `slug` from existing Gov Hub submission slug (kebab-case already enforced).
- File = `{prefix}/{slug}.md`.
- No renames without delete + create cycle; keep slug stable from first save.

### 3.4 Read Path (Phase 1: optional)
- Gov Hub DB remains source of truth for rendering.
- Later option: serve RFC content directly from GitHub API (with caching) so repo is canonical for reads. Not in Phase 1.

---

## Phase 4 — Conflict UX

### 4.1 Hidden SHA in Editor
- On open: server confirms current `github_sha`; injects into editor page as hidden input.

### 4.2 Conflict Response
- On save POST: compare submitted SHA to current DB/GitHub SHA before calling `put_file`.
- On mismatch: HTTP 409 + JSON:
  ```json
  {
    "error": "conflict",
    "message": "Someone else updated this; refresh to see latest version.",
    "github_url": "https://github.com/..."
  }
  ```
- Frontend shows modal/toast with message + "View on GitHub" link for manual diff.

---

## Phase 5 — IPFS and Ordinals (Future-Ready Hooks)

### 5.1 Model Fields (add now or confirm existing)
| Field | Type | Purpose |
|-------|------|---------|
| `ipfs_cid` | `TEXT` | IPFS content identifier |
| `ordinal_id` | `TEXT` | Bitcoin ordinal inscription ID |
| `github_path` | `TEXT` | As above |

### 5.2 Markdown Frontmatter on Commit
When IPFS/ordinal data exists, include in committed file:
```yaml
---
slug: gov-hub-foo
author: username
ipfs: bafybeig...
ordinal: abc123i0
github: https://github.com/Bridgit-DAO/ml-documents/blob/main/ml-rfc/gov-hub-foo.md
---
```
GitHub becomes the **index of record** across all three content-addressed copies.

---

## Phase 6 — Operations and Observability

### 6.1 Sync Queue
- Phase 1: synchronous call on save (no queue; acceptable for low traffic).
- Future: background task (Celery or DB-backed job queue) if latency becomes user-facing.

### 6.2 Monitoring
- Log every GitHub API call: `{path, sha_before, sha_after, latency_ms, status}`.
- Admin view surfaces `github_sync_error` across all docs.

### 6.3 CLI Resync
New `cli/github_resync.py`:
- Iterate all docs with `github_path` set.
- Fetch current content; push if SHA diverged.
- Use case: DB restore, server migration, partial outage recovery.

---

## Save Draft — Full Sequence

```
User clicks "Save"
  → Gov Hub validates form
  → DB: upsert Submission / draft row
  → github_sync.put_file(
        path      = m-draft/{slug}.md,
        content   = markdown,
        sha       = submitted_sha  (None if new),
        message   = "draft(m-draft): update ...",
        author    = {name, email}
    )
    ├─ 200 OK   → update github_sha in DB → success to user
    ├─ 409      → "conflict; refresh" to user  (DB save kept)
    └─ other    → log, set github_sync_error, warning to user
```

---

## Milestone Order

| Milestone | Deliverable |
|-----------|------------|
| **M1** | GitHub App + repo ruleset + config keys + `services/github_sync.py` (no UI yet) |
| **M2** | DB migration + save hook for `m-draft/`; admin shows sync status |
| **M3** | Conflict detection + UX (hidden SHA, 409 modal) |
| **M4** | Promote to `ml-rfc/` on publish; frontmatter with Gov Hub metadata |
| **M5** | IPFS/ordinal CIDs written into frontmatter on existing publish flows |
| **M6** | CLI resync + background task (only if sync latency becomes a problem) |
