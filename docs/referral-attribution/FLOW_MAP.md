# Referral Flow Map (Gov Hub + Canopi)

Maps existing product flows to the scoped attribution contract in [contract.json](./contract.json).

## Legend

| Field | Meaning |
|-------|---------|
| **Share event** | Link created / copied (top of funnel) |
| **Landing** | Anonymous visit before auth |
| **Conversion** | Authenticated outcome (join, signup) |
| **Denorm** | Existing per-row fields kept for compatibility |

---

## Canopi flows

### 1. Phase 1 user signup (`?ref=` / `referredByUserId`)

| Stage | Storage | Contract mapping |
|-------|---------|------------------|
| Share | — | Legacy UUID in query |
| Conversion | `AppUser.referred_by_user_id` | `conversion_type=user_signup`, `scope_type=platform`, `scope_id=canopi` |
| Denorm | User row FK | Same referrer |

**Handler:** `canopi/services/userService.js` → `getOrCreateUser()`

**Gap:** Web3Auth embed path records embed attribution but not `referredByUserId`. Future: call `insertReferralAttribution` on signup.

### 2. Signed message/profile share (`ref_token`)

| Stage | Storage | Contract mapping |
|-------|---------|------------------|
| Share | `share_events` | `entity_type=message|profile|…`, optional `scope_type=community` |
| Landing | `share_landings` | UTM + referrer from token |
| Conversion | Install / signup (partial) | `install_click` or `user_signup` when captured |

**Handlers:** `canopi/routes/share.js`, `canopi/app.js` (`GET /get-canopi`)

### 3. Embed instance referral

| Stage | Storage | Contract mapping |
|-------|---------|------------------|
| Share | Embed `referral_code` on instance | `scope_type=embed`, `scope_id=<instance_id>` |
| Conversion | `canopi_signup_attributions` | `embed_signup` / `embed_visit` |

**Handlers:** `canopi/routes/embeds.js`, `canopi/lib/embedSignupAttribution.js`

---

## Gov Hub flows

### 4. Layer join (`?ref=` / `?ref_token=`)

| Stage | Storage | Contract mapping |
|-------|---------|------------------|
| Share | User link or scoped token | `entity_type=layer`, `scope_type=layer`, `scope_id=<layer_id>` |
| Conversion | `layer_member.referred_by_id` | `conversion_type=layer_member_join` |
| Canonical | `referral_attribution` | Full scoped record |
| Denorm | `layer_member.referral_code` | Legacy code or token trace |

**Handlers:** `gov-hub-prod/routes/layers.py` → `join_layer()`, `services/referral_attribution.py`

**Rules unchanged:** `join_policy` (open / invitation / NFT) still enforced; referral does not bypass access.

### 5. Waitlist join (referrals enabled)

| Stage | Storage | Contract mapping |
|-------|---------|------------------|
| Share | Waitlist URL with `ref` or `ref_token` | `entity_type=waitlist`, `scope_type=waitlist`, `scope_id=<waitlist_id>` |
| Conversion | `waitlist_entry.referred_by_id` | `conversion_type=waitlist_join` |
| Side effect | May create `layer_member` | Same referrer on layer if not member |
| Denorm | `waitlist_entry.referral_code` | Legacy code |

**Handlers:** `gov-hub-prod/routes/waitlists.py` → `join_waitlist()`

**Gap:** Embed email join (`join-email`) has `source`/`source_url` only — no referrer yet (Phase 3).

### 6. Layer invitation accept

| Stage | Storage | Contract mapping |
|-------|---------|------------------|
| Share | Invite link | `legacy_referral_code=invite:{token}` |
| Conversion | `layer_member.referred_by_id` | `conversion_type=layer_member_join`, `channel=invitation` |

**Handler:** `gov-hub-prod/services/layer_invitations.py`

---

## Cross-product identity note

Gov Hub `User.id` and Canopi `AppUser.id` are **not assumed equal**. Scoped tokens for Gov Hub use Gov Hub user UUIDs. Canopi↔Gov Hub sync flows (MetaCommunity, workgroups) should map identities when recording cross-product attributions.

---

## Resolution order (Gov Hub join endpoints)

1. `ref_token` — verify HMAC, use `referrerUserId` from payload  
2. `referral_code` — lookup `User.referral_code`  
3. Self-referral blocked; existing `referred_by_id` preserved on rejoin (layer only)
