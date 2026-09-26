# Validation — 2026-09-25

All databases used for feature and regression tests were freshly created disposable SQLite files, using `fixtures/isolated_app.py`. No deployed database was read or migrated.

## Feature tests

```sh
FLASK_ENV=development GOVHUB_SKIP_SHARED_DB_MIGRATIONS=1 \
  .venv-community/bin/python -m pytest test_community_intelligence.py -q --disable-warnings
```

**15 passed.** Coverage includes:

- Three synthetic organizations, proposed → confirmed evidence, citations, two need/offer matches, venue retirement, historical retrieval and duplicate newsletter replay.
- Private source content, titles, originals and counts hidden from another organization, a global/layer administrator without organization access, outsiders and other layers.
- Tentative wording retained; corrections reflected in answers; disputed claims excluded; stale reviews rejected.
- Removal propagation and replay guards; interrupted workers cannot recreate withdrawn content.
- Independent reviewed evidence retained after another source is removed.
- Visibility and membership revocation; a revocation during answer preparation discards the prepared citations before delivery.
- Contributor limitations, CSRF, malformed values, unsupported files, upload size and URL rejection.
- Explicit OCR failure and bounded retry; malicious text remains unconfirmed data.
- Text PDF/DOCX extraction and scanned-PDF failure.
- Additive repeatable migration, opt-in layer navigation, and durable CLI queue draining.

## Existing application regression checks

```sh
.venv-community/bin/python scripts/community_regression.py
```

**13 passed.** Runs the repository's existing core feature, access-policy, navigation and knowledge-layer test modules against a synthetic administrator and layer. The fixture enables the existing artifacts feature required by the knowledge-layer checks. Initial execution with the default disabled artifact flag failed two tests; after explicitly configuring the disposable fixture for those tests, all passed. The inherited anonymous artifact-patch test follows its existing authentication-skip path; the core feature test executed with a seeded administrator.

Existing SQLAlchemy/deprecation warnings remain. No complete repository-wide suite or deployment tests were run; many legacy tests target configured/deployed databases or the vendored Django project.

## Browser check

Viewed the real Flask page inside the Codex browser on loopback. Confirmed:

- Layout uses the existing Gov Hub shell and responsive cards.
- The seeded overview shows five accessible sources, one pending review and two possible connections.
- “Who offers training?” returns cited reviewed passages from the three fictional organizations.
- A pending newsletter opens with its original tentative wording and proposed status.
- Confirming that synthetic claim changes its status to organization-confirmed while preserving the tentative statement.

## Unverified / intentionally not claimed

- Configured-model extraction/recommendation quality, live Hermes runtime or provider retention/costs.
- Successful OCR, public web ingestion, vector or graph retrieval.
- Group conversations, room-audience expansion, persisted response invalidation, governance handoff, connectors and federation.
- Production/staging deployment, large-scale performance, worker process sandboxing or secure physical backup erasure.
