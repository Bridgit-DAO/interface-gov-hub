# Referral Attribution Schema (Additive)

All changes are **additive**. Existing `referral_code`, `referred_by_id`, and Canopi `referredByUserId` remain authoritative for legacy reads until reporting migrates.

## Canopi (PostgreSQL)

Migration: [`canopi/migrations/007_referral_attribution_v1.sql`](../../canopi/migrations/007_referral_attribution_v1.sql)

### `share_events` — new columns

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `product` | TEXT | `'canopi'` | `canopi` \| `gov_hub` |
| `scope_type` | TEXT | `'platform'` | Scoped context type |
| `scope_id` | TEXT | `'canopi'` | Layer/waitlist/org id |
| `campaign` | TEXT | NULL | Optional campaign slug |

Existing rows: backfilled implicitly by column defaults.

### `referral_attributions` — new table

Canonical conversion log. See [contract.json](./contract.json) `referralAttribution` definition.

Indexes: `(scope_type, scope_id)`, `(referrer_user_id)`, `(converted_user_id, conversion_type)`.

Prisma model: `canopi/prisma/schema.prisma` → `referral_attributions`.

---

## Gov Hub (SQLite)

Migration: `migrate_referral_attribution_v1()` in [`gov-hub-prod/migrations/__init__.py`](../../gov-hub-prod/migrations/__init__.py)

### `referral_attribution` — new table

| Column | Type | Notes |
|--------|------|-------|
| `id` | VARCHAR(36) PK | UUID |
| `product` | VARCHAR(20) | Always `gov_hub` for GH conversions |
| `referrer_user_id` | FK → user | Required |
| `converted_user_id` | FK → user | Nullable (anonymous landings N/A here) |
| `scope_type` | VARCHAR(32) | layer, waitlist, org, … |
| `scope_id` | VARCHAR(36) | Layer or waitlist id |
| `entity_type` | VARCHAR(32) | layer, waitlist, … |
| `entity_id` | VARCHAR(36) | Same as scope target typically |
| `conversion_type` | VARCHAR(32) | layer_member_join, waitlist_join, … |
| `channel` | VARCHAR(32) | Optional |
| `campaign` | VARCHAR(64) | Optional |
| `share_event_id` | VARCHAR(36) | Cross-ref to Canopi share_events when synced |
| `referral_token` | TEXT | Signed token used |
| `legacy_referral_code` | VARCHAR(50) | Original `?ref=` code |
| `metadata_json` | TEXT | JSON blob |
| `converted_at` | DATETIME | Conversion timestamp |

Model: [`gov-hub-prod/models/referral_attribution.py`](../../gov-hub-prod/models/referral_attribution.py)

### Unchanged (denormalized)

- `user.referral_code`
- `layer_member.referred_by_id`, `layer_member.referral_code`
- `waitlist_entry.referred_by_id`, `waitlist_entry.referral_code`
- `waitlist.referrals` toggle

---

## Shared secret

Both products verify tokens with the same HMAC secret:

| Env var (Canopi) | Env var (Gov Hub) |
|------------------|-------------------|
| `SHARE_REF_HMAC_SECRET` | `REFERRAL_TOKEN_SECRET` or `SHARE_REF_HMAC_SECRET` |

Minimum 16 characters.

---

## Backfill strategy

No automatic backfill of historical joins into `referral_attribution`. Optional one-off scripts can populate from `layer_member` / `waitlist_entry` where `referred_by_id IS NOT NULL` with `legacy_referral_code` set and `scope_*` inferred from row context.
