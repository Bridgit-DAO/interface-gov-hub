# DP Proposals – specification

**Status:** Scaffolding (dev)  
**Last updated:** 2026-05-25

## Terminology

| Concept | UI label | Notes |
|---------|----------|--------|
| Sentence-level change on a DP | **DP Proposal** | Created by any authenticated reader |
| Generic document change (future) | **Suggested edit** | Same mechanics, `scope=document` |
| Editor accepted proposal | **Amendment** | Ready for next whole **Revision** |
| Editor rejected proposal | **Declined** | Visible on read page (muted) |
| Whole-document publish | **Revision** | Existing ML-Draft rev 01/02 flow |

## Status lifecycle

| Status | UI label |
|--------|----------|
| `pending` | DP Proposal |
| `accepted` | Amendment |
| `declined` | Declined |
| `incorporated` | Published in Revision NN |
| `orphaned` | Original text not found |

Multiple **competing proposals** per anchor are allowed. Accepting one does not auto-decline others.

## Permissions

| Action | Who |
|--------|-----|
| Create DP Proposal | Authenticated user (approved DP only) |
| Accept → Amendment | Workgroup coordinator, approved chair, layer admin, site admin/editor |
| Decline | Same as accept |

Future: dedicated editor role via `can_manage_amendments`.

## Badge & visibility (UI – later phases)

Badge counts **all** statuses: pending, declined, amendments, incorporated (optional), orphaned.

Three display modes (Canopi-style): Hidden · Proximity · Show all.

## Anchor stability

- Anchor identity: W3C `TextQuoteSelector` + `anchor_hash` from `submission_id`, `content_hash`, normalized `exact`.
- On new whole **Revision** approve: re-resolve anchors; unchanged text → proposal bubbles up; changed → `orphaned`.

## API (scaffolding)

- `GET/POST /api/doc/draft/<ref>/proposals/`
- `POST /api/doc/draft/<ref>/proposals/<id>/accept/`
- `POST /api/doc/draft/<ref>/proposals/<id>/decline/`
- `GET /admin/dp-proposals/` – activity dashboard (placeholder)

## Product rollout

Feature flag: `dp_proposals` (off by default in prod; enabled on dev checkout via migration).
