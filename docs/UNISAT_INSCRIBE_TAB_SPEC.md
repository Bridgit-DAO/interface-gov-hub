# Unisat Inscription Capability — Specification

**Version:** 0.3  
**Date:** February 2026  
**Status:** Phase 1 Implemented  
**Scope:** Inscribe tab on Submit page + top-level Inscribe; standalone + document-integrated flows

### Phase 1 Implementation (Complete)

- **Submit page**: Inscribe tab added (Upload File | From Ordinal | Inscribe)
- **Standalone**: `/inscribe/` route + nav link
- **API**: `/api/inscription/create`, `/api/inscription/status/<id>`, `/api/inscription/search-duplicate/text`, `/api/inscription/search-duplicate/image`
- **Config**: `UNISAT_API_KEY` (env), `UNISAT_TESTNET` (optional, for testnet)
- **Duplicate search**: Placeholder — returns "API access pending" for both text and image endpoints

---

## 1. Executive Summary

Add an **Inscribe** capability to the MLTF Datatracker with two entry points:

1. **Submit page**: Inscribe tab alongside **Upload File** and **From Ordinal**
2. **Top-level nav**: Standalone "Inscribe" page for users who only want on-chain storage

The capability enables users to create Bitcoin Ordinal inscriptions via Unisat's API, with:

- **Standalone use**: Create inscriptions without submitting a draft
- **Document-integrated use**: Inscribe → preview → pay → optional "Submit as Draft"
- **Reinscription flow**: Add metadata to existing inscriptions
- **Content preview**: All content fetching uses `https://ordinals.com/` as the canonical source
- **Duplicate check**: Optional pre-inscription search to avoid re-inscribing identical content (see §11)

---

## 2. Current State (Baseline)

### 2.1 Submit Page Tabs (Today)

| Tab | Purpose |
|-----|---------|
| **Upload File** | User uploads TXT/PDF/DOCX; draft created from file |
| **From Ordinal** | User enters inscription ID; system fetches content via ordinals.com API; draft created from ordinal |

### 2.2 Existing Ordinals Infrastructure

- **Read path**: Ordinals loading (preview, convert markdown, display) — ~75% complete per UNISAT_INSCRIPTION_FEASIBILITY.md
- **Schema**: `sourceType`, `ordinalId`, `inscriptionNumber`, `blockHeight`, `inscriptionTimestamp`, `ordinalContentUrl`, `ordinalContentType` on submission
- **Size limit**: **390KB** (Unisat limit) — applies to both draft and standalone inscriptions
- **Unisat feasibility**: Create-order API analyzed; payment flow, order tracking, status polling designed but not implemented

### 2.3 Gaps

- No **write** path: users cannot create inscriptions from the datatracker
- No child-parent or reinscription support
- No metadata (tag 5) support
- No standalone "inscribe only" flow

---

## 3. Capability Definitions

### 3.1 Basic Inscription (Create New)

**Definition**: User provides content (file or paste); system creates a new inscription via Unisat API; user pays; inscription is created on Bitcoin.

**Inputs**: Content (file upload or text paste), receive address, optional fee rate  
**Outputs**: Inscription ID, ordinals.com link, optional link to submit draft from this ordinal

**Constraints**: Unisat limit **390KB** per file; supported content types (text, markdown, images, HTML).

---

### 3.2 Child-Parent Inscription

**Definition**: User creates a **child** inscription that references an existing **parent** inscription. The child is provably linked to the parent on-chain (Ordinals tag 3).

**Use cases**:
- **Revisions**: Parent = original draft; child = revised version. Establishes provenance chain.
- **Collections**: Parent = collection manifest; children = collection items.
- **Comments/annotations**: Parent = document; child = structured comment or annotation (alternative to Hypothesis for on-chain attestation).
- **Metadata attestation**: Child carries metadata that attests to the parent (e.g., "approved by MLTF", "version 2").

**Inputs**: Parent inscription ID, child content, receive address  
**Outputs**: Child inscription ID; parent-child relationship verifiable on-chain

**Technical note**: Child inscription transaction must spend the parent UTXO as an input. Unisat API support for parent-child needs verification (check `/v2/inscribe/order/create` for `parentInscriptionId` or equivalent).

---

### 3.3 Reinscription (Metadata on Existing)

**Definition**: Add **metadata** to an existing inscription. Reinscription = inscribing additional content onto the **same satoshi** (spend the UTXO, inscribe again). Multiple inscriptions can be layered on one satoshi.

**Use cases**:
- **Status updates**: Add `{"status": "approved", "approvedBy": "MLTF", "date": "..."}` to a draft inscription.
- **Version info**: Add `{"version": 2, "replaces": "inscription-id-xxx"}`.
- **Attribution**: Add author, license, or provenance metadata.
- **Schema compliance**: Add structured fields (e.g., MLTF-specific metadata schema).

**Inputs**: Target inscription ID (must be owned by user), metadata (JSON or structured key-value), receive address  
**Outputs**: New inscription (reinscription) on same satoshi; original content unchanged; metadata layered on-chain

**Technical note**: Unisat create-order API does **not** support reinscription (inscribing onto existing UTXO). Requires alternative: custom transaction construction, ord/bitcoin-core, or specialized inscribe service. See §6.1.

---

### 3.4 Metadata (Structured)

**Definition**: Attach structured metadata to any new inscription at creation time (not reinscription). Uses Ordinals metadata field (tag 5).

**Use cases**:
- **Draft metadata**: `{"title": "...", "authors": [...], "abstract": "...", "workgroup": "..."}` — enables on-chain discovery without relying on datatracker DB.
- **Schema version**: `{"schema": "mltf-draft-v1", ...}` for future compatibility.
- **Licensing**: `{"license": "CC-BY-4.0"}`.

**Inputs**: Content + metadata object (key-value or JSON)  
**Outputs**: Inscription with content and metadata both on-chain

**Technical note**: Unisat create-order API may support metadata in the file payload or as a separate field. Needs API review.

---

## 4. Submit Page UX — Inscribe Tab

### 4.1 Tab Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Submit Draft                                                    │
├─────────────┬─────────────┬─────────────┐                        │
│ Upload File │ From Ordinal │  Inscribe   │  ← New tab            │
└─────────────┴─────────────┴─────────────┘                        │
```

### 4.2 Inscribe Tab — Modes (Sub-tabs or Accordion)

| Mode | Description | Primary action |
|------|-------------|----------------|
| **Create New** | Inscribe content (file or paste) as a new ordinal | "Create Inscription" |
| **Create Child** | Inscribe content as child of an existing parent | "Create Child Inscription" |
| **Add Metadata** | Reinscribe metadata onto an existing inscription | "Add Metadata" |

**Design decision**: Whether these are sub-tabs, a dropdown, or a stepped wizard. Recommendation: **stepped flow** — user selects mode first, then sees mode-specific form.

---

### 4.3 Create New Flow (Standalone)

1. **Content input**
   - Option A: File upload (same types as Upload File tab)
   - Option B: Paste text / markdown
   - Size indicator (e.g., "12 KB / 390 KB max" — Unisat limit)

2. **Preview**
   - **Required step** before proceeding
   - **Canonical source**: All inscription content and metadata API calls use **`https://ordinals.com/`** as the base (e.g. `https://ordinals.com/content/{id}`, `https://ordinals.com/inscription/{id}`)
   - For new content (file/paste): render preview locally (same UX as From Ordinal)
   - For existing inscriptions (parent, reinscription target): fetch from ordinals.com
   - **Duplicate check** (optional): Before inscribing, call duplicate-search API (see §11) — if identical content exists, warn user and optionally link to existing inscription

3. **Optional metadata** (if metadata capability enabled)
   - Collapsible "Add metadata" section
   - Key-value pairs or JSON editor
   - Suggested keys: title, authors, abstract, workgroup

4. **Receive address**
   - User enters Bitcoin address (or connects wallet if Web3/UniSat wallet integration exists)
   - Validation: valid Bitcoin address format

5. **Fee options**
   - Fee rate selector (e.g., 5 / 10 / 20 / 50 sat/byte) or "Use recommended"
   - Cost estimate: "~3,745 sats (~$X.XX)" — update when fee rate changes

6. **Create Inscription**
   - Button triggers backend: create Unisat order
   - Redirect or inline to **Payment** step

7. **Payment step**
   - QR code + payment address + amount
   - "Pay with UniSat Wallet" deep link (if supported)
   - Status polling: "Waiting for payment..." → "Inscribing..." → "Confirmed"
   - On success: show inscription ID, `https://ordinals.com/inscription/{id}` link, **"Submit as Draft"** button (optional CTA to continue to document flow)

**Flow summary**: File/paste → **Preview** (ordinals.com for all content APIs) → receive address → fee → pay → inscription ID → optional "Submit as Draft"

---

### 4.4 Create New Flow (Document-Integrated)

Same as standalone, but with explicit **continuation** into draft submission:

- After inscription confirmed: "Your inscription is ready. Submit it as an MLTF draft?"
- **Yes** → Pre-fill "From Ordinal" flow with the new inscription ID; user adds title, authors, abstract, workgroup, terms; submits.
- **No** → User exits; inscription exists standalone.

**Alternative**: Inscribe tab could have a checkbox "Submit as draft after inscription" — if checked, after payment confirmation, user is taken directly to the draft metadata form with ordinal pre-filled.

---

### 4.5 Create Child Flow

1. **Parent inscription**
   - Input: Parent inscription ID
   - Fetch from **`https://ordinals.com/content/{id}`** and **`https://ordinals.com/inscription/{id}`**
   - "Verify" button: show preview, confirm user owns it (or has permission)
   - Display: parent content preview, parent metadata

2. **Child content**
   - Same as Create New: file upload or paste
   - Optional: "This is a revision of the parent" checkbox — could auto-add metadata `{"type": "revision", "parent": "..."}`

3. **Receive address, fee, Create Child**
   - Same payment flow as Create New

4. **Post-success**
   - Show child inscription ID; link to parent; optional "Submit child as draft" (child as source for new draft)

---

### 4.6 Add Metadata (Reinscription) Flow — Required

Reinscription flow is **required** in the spec. Implementation will need an alternative to Unisat (see §6.1).

1. **Target inscription**
   - Input: Inscription ID
   - Fetch content/metadata from **`https://ordinals.com/content/{id}`** and **`https://ordinals.com/inscription/{id}`**
   - Verify: confirm user owns the inscription (controls the UTXO)
   - Display: current content, current metadata (if any)

2. **Metadata input**
   - Key-value form or JSON editor
   - Validation: valid JSON, size limit for metadata
   - Suggested keys: status, approvedBy, version, license

3. **Receive address, fee, Add Metadata**
   - Same payment flow as Create New

4. **Post-success**
   - New inscription (reinscription) on same satoshi; original content unchanged; metadata layered
   - Optional: "Update draft status" if target inscription is linked to an MLTF submission

---

## 5. Standalone vs Integrated

### 5.1 Standalone

**Definition**: User can inscribe without creating or linking an MLTF draft.

**Entry points** (both):
- **Submit page** — Inscribe tab with "Create New" / "Create Child" / "Add Metadata"
- **Top-level nav** — Standalone "Inscribe" page for users who only want on-chain storage (no draft workflow)

**Output**: Inscription ID, `https://ordinals.com/inscription/{id}` link. No submission record in datatracker.

**Use case**: Users who want permanent on-chain storage of documents before or without MLTF submission.

---

### 5.2 Integrated

**Definition**: Inscription is part of the document lifecycle.

**Flows**:
1. **Inscribe → Submit**: Create inscription in Inscribe tab → continue to submit draft from that ordinal.
2. **Submit → Inscribe**: From a draft (e.g., uploaded file), user chooses "Inscribe this draft" — creates ordinal from draft content, then links submission to ordinal (or replaces file source with ordinal).
3. **Reinscription for status**: When a draft is approved, optionally create a reinscription with `{"status": "approved"}` on the draft's ordinal.

**Data model**: Submission can have `sourceType: 'ordinal'` and `ordinalId`; optionally `parentOrdinalId`, `reinscriptionIds[]`, `metadataInscriptionId` for advanced cases.

---

## 6. Technical Considerations

### 6.1 Unisat API — Research Findings

| Capability | Unisat API support | Notes |
|------------|--------------------|-------|
| Basic create order | ✅ Documented | Use `/v2/inscribe/order/create` — payload: `receiveAddress`, `feeRate`, `outputValue`, `files[]` (filename, dataURL only) |
| Parent-child | ❌ Not in create-order | Create-order payload has no `parentInscriptionId`. Child inscriptions require spending parent UTXO as input; Unisat API does not expose this. **Workaround**: Custom tx construction or alternative inscribe service. |
| Metadata (tag 5) | ❌ Not in create-order | Files object only has `filename` and `dataURL`. No metadata envelope field. **Workaround**: Encode metadata in content (e.g. JSON file) or use separate inscription. |
| Reinscription | ❌ Not documented | Reinscription = inscribing additional content onto same satoshi (spend UTXO, inscribe again). Unisat create-order does not support "inscribe onto existing UTXO." **Workaround**: May require ord/bitcoin-core or specialized service. |

**Recommendation**: Phase 1 = Basic create only. Phase 2+ = Child-parent and reinscription require alternative implementation (custom tx, or different API).

---

### 6.2 Backend Components

- **Inscription order service**: Create order, poll status, persist `inscription_order` (or equivalent)
- **Unisat config**: API key, environment (**mainnet** | **testnet**), fee defaults
- **Testnet support**: **Yes** — Use `https://open-api-testnet.unisat.io` for dev/staging. Config flag to switch environments.
- **Wallet/receive address**: User provides address; no custody. Future: UniSat wallet connect for address auto-fill
- **Payment flow**: Stateless polling or webhook (if Unisat supports) for order status

---

### 6.3 Database / Schema

- **inscription_order**: order_id, unisat_order_id, status, pay_address, amount, inscription_id, submission_id (nullable for standalone), created_at, etc.
- **submission**: Add `parent_ordinal_id`, `metadata_inscription_id` if child/reinscription supported
- **Standalone inscriptions**: Optional `standalone_inscription` table for inscriptions not tied to submissions (audit, user history)

---

### 6.4 Security & Trust

- **API key**: Unisat API key stored encrypted; server-side only
- **Payment**: User pays to Unisat-generated address; no MLTF custody of funds
- **Ownership**: For reinscription, verify user owns the inscription (via address control)
- **Rate limits**: Respect Unisat free tier (5 req/s, 2000/day); consider paid tier for production

---

## 7. Phasing

### Phase 1 — Basic Inscribe (MVP)

- Inscribe tab + top-level Inscribe page
- **Create New** only: File/paste → Preview (ordinals.com) → receive address → fee → pay → inscription ID → optional "Submit as Draft"
- Optional duplicate check (OrdinalsBot or similar)
- Testnet support for dev/staging
- Size limit: 390KB (Unisat)

### Phase 2 — Reinscription Flow

- Add **Add Metadata** mode (reinscription)
- **Note**: Unisat API does not support reinscription. Requires alternative: custom tx construction, ord/bitcoin-core, or other inscribe service.
- Flow: Target inscription ID → verify ownership → metadata input → pay → create reinscription
- Schema: `metadata_inscription_id` on submission

### Phase 3 — Child-Parent

- Add **Create Child** mode
- **Note**: Unisat API does not support parent-child. Requires alternative implementation.
- Parent inscription ID input, verification, child content
- Schema: `parent_ordinal_id` on submission
- Use case: revisions, provenance chains

### Phase 4 — Polish

- UniSat wallet connect (address auto-fill)
- Batch inscription (multiple files in one order)
- Inscription history / "My Inscriptions" page
- Admin: inscription analytics, fee reporting

---

## 8. Resolved Decisions

| Question | Decision |
|----------|----------|
| Unisat API parent-child & metadata | **Research complete** — Not supported in create-order. See §6.1. |
| Reinscription mechanism | **Research complete** — Reinscription = inscribing onto same satoshi (spend UTXO, inscribe again). Unisat API does not support. See §6.1. |
| Standalone entry point | **Both** — Inscribe tab under Submit + top-level "Inscribe" nav. |
| Testnet | **Yes** — Use testnet API for dev/staging. |
| Size limit | **Unisat 390KB** — Use Unisat's limit for all inscriptions. |
| Duplicate content search | See §11. |

---

## 9. Success Criteria

- User can create a new inscription from the Submit page or top-level Inscribe
- Flow: File/paste → Preview (ordinals.com) → receive address → fee → pay → inscription ID → optional "Submit as Draft"
- Reinscription flow available (Add Metadata mode)
- Payment flow is clear (QR, amount, status)
- Standalone use does not require draft submission
- No security regressions (API key, payment, ownership)

---

## 10. References

- UNISAT_INSCRIPTION_FEASIBILITY.md — Unisat API analysis, create-order flow
- ORDINALS_USER_GUIDE.md — Current From Ordinal UX
- Ordinals protocol: parent (tag 3), metadata (tag 5) — docs.ordinals.com
- Unisat Open API: https://open-api.unisat.io (Swagger)
- Unisat Testnet: https://open-api-testnet.unisat.io

---

## 11. Duplicate Content Search — Can We Avoid Re-Inscribing Identical Content?

### 11.1 Question

Can we use an API to check whether identical content is already inscribed (or in mempool) before creating a new inscription?

### 11.2 Research Findings

| Source | Content-hash search | Mempool | Notes |
|--------|---------------------|---------|-------|
| **Unisat API** | ❌ No | ❌ No | Unisat has `Get Inscription Content` (by ID), `Get Address Inscriptions` (by address). No search-by-content or search-by-hash. |
| **OrdinalsBot API** | ✅ Yes | ❌ No | `GET https://api.ordinalsbot.com/search` — search by content hash. You SHA256 the file content, API compares against previous inscriptions. Results sorted by inscription number (earliest first). **Requires**: API key or allowlisted domain (request via Discord). |
| **ordinals.com** | ❌ No | ❌ No | Content endpoint is fetch-by-ID only. No search. |
| **Mempool** | N/A | ❌ Not indexed | Inscriptions in mempool are unconfirmed until mined. No public API indexes mempool inscriptions for content-hash search. |

### 11.3 Recommendation

**Yes, duplicate detection is possible** — but not via Unisat:

1. **OrdinalsBot Search API** — Primary option. SHA256 the content before inscribing, call OrdinalsBot search with the hash. If match found, warn user: "This content may already be inscribed. [View existing inscription]. Proceed anyway?"
2. **Mempool** — Cannot be checked. If someone is inscribing the same content right now, we cannot detect it until confirmed.
3. **Implementation** — Add optional "Check for duplicates" step before Create Inscription. If enabled, compute content hash, call OrdinalsBot (or similar) API, show result. User can proceed or cancel.

### 11.4 Open Items

- OrdinalsBot API key / allowlist — need to request access
- Fallback: If OrdinalsBot unavailable, skip duplicate check or use alternative indexer (Hiro, Ordiscan) if they support content-hash search
- UX: Make duplicate check optional (checkbox) — some users may want to inscribe a copy intentionally

### 11.5 Implementation Note (Phase 1)

Duplicate search uses **two different endpoints**:
- **Text**: `POST /api/inscription/search-duplicate/text` — body: `{ text: "..." }` — for regular text content
- **Image**: `POST /api/inscription/search-duplicate/image` — body: `{ contentHash: "sha256..." }` — for image content (hash-based)

Placeholder implementation returns `{ placeholder: true, message: "..." }` until API access is granted.
