# Campaign artifacts and embed configuration

Campaign documents (paper, slides, statement) and their iframe/PDF embeds are driven from `campaign-seed.json` or Monument `presentation_json`. Embed URLs are **auto-derived** from document bindings when `embeds` is absent.

## Where to configure

| Source | Path |
|--------|------|
| Dev seed | `static/campaign/<slug>/campaign-seed.json` |
| Production Monument | `presentation_json.embeds` (imported from seed) |
| Parser | `services/campaign_pages.py` → `build_embeds_from_seed()`, `resolve_document_embed()` |
| Renderer | `services/campaign_render.py` |
| Routes | `routes/campaign_pages.py` |

Re-import after seed changes:

```bash
python scripts/import_teilhard_monument.py
systemctl --user restart datatracker.service
```

## JSON schema

```json
{
  "documents": [
    {
      "slug": "paper",
      "type": "paper",
      "draftRef": "8a37qe9r",
      "isPrimary": true
    },
    {
      "slug": "slides",
      "type": "slide_deck",
      "deckPath": "static/campaign/teilhard/incoming/The_Teilhard_Test_Synthesis.pdf"
    }
  ],
  "embeds": {
    "paper": {
      "mode": "iframe",
      "src": "/embed/draft/{draftRef}/read/",
      "modalTheme": "dark"
    },
    "slides": {
      "mode": "pdf",
      "src": "/embed/campaign/{slug}/slides/",
      "pdfSrc": "/embed/campaign/{slug}/slides/file/"
    }
  }
}
```

### Template placeholders

| Token | Replaced with |
|-------|----------------|
| `{slug}` | Campaign slug |
| `{draftRef}` | Document `draftRef` |
| `{deckPath}` | Document `deckPath` |

### Auto-derivation (when `embeds.<slug>` is omitted)

| Document type | `mode` | Default `src` | Notes |
|---------------|--------|---------------|-------|
| `paper` with `draftRef` | `iframe` | `/embed/draft/{draftRef}/read/` | Sets `modalTheme: dark` |
| `slide_deck` / `slides` with `deckPath` | `pdf` | `/embed/campaign/{slug}/slides/` | `pdfSrc` under `/embed/` for iframe-safe PDF |

### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `mode` | `iframe` \| `pdf` | Embed strategy |
| `src` | string | Iframe `src` on campaign doc page |
| `pdfSrc` | string | PDF bytes URL (must be under `/embed/` for SAMEORIGIN framing) |
| `modalTheme` | `dark` \| `light` | Onboarding modal theme in draft reader embed |

## Routes

| URL | Purpose |
|-----|---------|
| `/docs/paper/` | Campaign page; iframes `embeds.paper.src` |
| `/docs/slides/` | Campaign page; iframes `embeds.slides.src` |
| `/embed/draft/<draftRef>/read/` | Draft reader embed (onboarding modal respects `modalTheme`) |
| `/embed/campaign/<slug>/slides/` | PDF viewer shell |
| `/embed/campaign/<slug>/slides/file/` | PDF bytes (iframe-safe; `X-Frame-Options: SAMEORIGIN`) |
| `/docs/slides/file/` | Direct PDF download/view (not iframe-safe) |

Vanity hosts pass through `/embed/` without campaign path rewrite.

## Teilhard example

See `static/campaign/teilhard/campaign-seed.json` for the live `embeds` block bound to draft `8a37qe9r` and the synthesis deck PDF.

## Verify

```bash
cd gov-hub-prod
pytest test_campaign_embeds.py -q
curl -sS -I https://teilhardtest.com/embed/campaign/teilhard/slides/file/ | grep -i x-frame-options
```

Expected: `X-Frame-Options: SAMEORIGIN` on embed PDF route.
