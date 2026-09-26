# Personal opportunity tracking

Builds on coordination commit `b76a446`. Members can now save a suggestion, mark it exploring, dismiss it, and restore it through the Opportunities screen. These are private personal workflow states, not organizational decisions or partnership commitments.

## Evidence and access

Each record belongs to exactly one user and layer. The API filters by both before reading or changing it; administrators do not bypass ownership. Sources must be layer-shared, confirmed evidence from active programs, with a complementary need and offer from different organizations on the same reviewed topic.

Saving includes the exact evidence revisions shown to the member. A correction between display and save returns a conflict instead of accepting unseen evidence. The same member saving the same version again gets the existing record. Status updates require the current record revision; concurrent stale updates return a conflict.

The table stores dependency IDs and revisions, status, owner and update time. It does not copy source titles, passages, or free-text notes. Every read reconstructs content from currently authorized evidence. Changed, restricted, removed or retired evidence produces a generic stale notice with no status, citations or title. Republishing does not revive the old version; a current suggestion may be saved as a new record. Prepared responses are checked again before delivery.

Tracked suggestions leave the new-suggestion list, including dismissed items. Dismissed items remain in the personal tracker with a restore control. Starting a discussion from a tracked item uses the existing fixed-audience room workflow. It does not automatically change the personal status or imply consent.

## Data and API

The additive `community-migrate` command now creates `ci_opportunity` alongside the existing tables. Back up and use the development database when applying it. This task used only disposable synthetic databases; no existing or deployed database was migrated.

All routes use existing session, active layer membership, CSRF and no-store boundaries:

- `GET /api/layers/<layer_id>/community/opportunities/`: the current member's tracker.
- `POST .../opportunities/`: save with `claim_ids` and exact `evidence` snapshots supplied by the overview API.
- `PATCH .../opportunities/<id>/`: change `status` with the current integer `revision`.

The pilot supports up to 200 records per member per layer, including stale records. New suggestions retain the existing 20-match/200-claim candidate limits. Pagination and pruning are follow-up work.

## Validation

26 feature tests passed, including five new lifecycle/security scenarios, and 13 existing regression checks passed. Tests cover duplicate saves, restore, update conflicts, member/admin/cross-layer isolation, changed/private/retired/removed evidence, revoked membership, and revocation before response delivery.

Browser verification also confirmed saving a synthetic suggestion and changing it to exploring, with the saved item removed from new suggestions.

Run in an isolated development environment:

```sh
FLASK_ENV=development GOVHUB_SKIP_SHARED_DB_MIGRATIONS=1 \
  .venv-community/bin/python -m pytest test_community_intelligence.py test_community_rooms.py test_community_opportunities.py -q --disable-warnings
.venv-community/bin/python scripts/community_regression.py
```

Live Hermes integration and configured-model evaluation, OCR, safe URL ingestion, organizational decision authority, direct governed proposal submission, newsletters/digests, and federation remain separate work. No live model calls or deployment were performed.
