# Campaign hero configuration

Gov Hub campaign home pages can render a full-bleed hero with image, copy overlay, and CTAs. Configuration lives in the nested `hero` object inside `campaign-seed.json` or Monument `presentation_json`.

Schema reference for builders and import scripts.

## Where to configure

| Source | Path |
|--------|------|
| Dev seed | `static/campaign/<slug>/campaign-seed.json` |
| Production Monument | `presentation_json.hero` (imported from seed) |
| Parser | `services/campaign_pages.py` → `normalize_hero_config()` |
| Renderer | `services/campaign_render.py` → `_campaign_hero_section()` |
| Styles | `static/css/campaign-pages.css` |

Re-import after seed changes:

```bash
python scripts/import_teilhard_monument.py
systemctl --user restart datatracker.service   # production
# or datatracker-dev on dev (:8001)
```

## JSON schema

```json
{
  "hero": {
    "imageUrl": "/static/campaign/<slug>/assets/hero.jpg",
    "fullBleed": true,
    "fit": "cover",
    "kicker": "Eyebrow label",
    "headline": "Main question or title",
    "quote": "Optional pull quote under the headline",
    "quoteAttribution": "Author, work title",
    "overlay": {
      "scrim": "gradient-left",
      "textAlign": "left",
      "primaryCta": {
        "label": "Primary button label",
        "href": "/docs/paper"
      },
      "ghostLinks": [
        { "label": "Secondary link", "href": "/docs/statement" }
      ]
    }
  }
}
```

### Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `imageUrl` | string | (none) | Hero image path under `/static/campaign/<slug>/assets/` or absolute URL |
| `fullBleed` | boolean | `true` | Edge-to-edge hero band (breaks out of main content width) |
| `fit` | `"cover"` \| `"contain"` | `"cover"` | `cover` fills the hero frame at center; `contain` shows the entire image |
| `kicker` | string | campaign `title` | Uppercase eyebrow above headline |
| `headline` | string | campaign `title` | `<h1>` text |
| `quote` | string | (none) | Optional blockquote under headline |
| `quoteAttribution` | string | (none) | `<cite>` under quote |
| `overlay.mode` | string | `full` | `full` renders copy and CTAs; `nav-only` shows only the hero image (site nav remains in the header) |
| `overlay.scrim` | string | `gradient-left` | Legibility overlay: `gradient-left`, `gradient-bottom`, `gradient-full`, `panel-left`, `none` |
| `overlay.textAlign` | string | `left` | `left`, `center`, or `right` |
| `overlay.primaryCta` | object | `primaryCta` at root | Primary button `{ label, href }` |
| `overlay.ghostLinks` | array | `secondaryCtas` | Text links under primary CTA (max 2 rendered) |

### Image behavior

- **No `object-position` hacks.** The hero uses a real `<img>` with `object-fit: cover` and `object-position: center center` so the image is not artificially shifted to hide on-image text.
- **`fit: contain`** shows the full image inside the hero frame (letterboxed on dark background). Use when the artwork must remain fully visible.
- **`overlay.mode: nav-only`** shows only the hero image with no HTML headline, quote, scrim panel, or hero CTAs. Use when artwork includes baked-in text. Site navigation links remain in the header.
- **`overlay.scrim: panel-left`** puts copy on a semi-transparent left panel instead of a full-image gradient.
- **`fullBleed: true`** spans viewport width; pair with `contain` + `panel-left` to preserve artwork.

### Legacy flat keys (still supported)

Older seeds may use top-level fields; `normalize_hero_config()` merges them into `hero`:

| Legacy key | Maps to |
|------------|---------|
| `heroImageUrl`, `heroImage` | `hero.imageUrl` |
| `heroQuestion` | `hero.headline` |
| `heroKicker` | `hero.kicker` |
| `heroQuote` | `hero.quote` |
| `heroQuoteAttribution` | `hero.quoteAttribution` |
| `heroGhostLinks` | `hero.overlay.ghostLinks` |
| `primaryCta` | `hero.overlay.primaryCta` |

Do **not** use `heroImagePosition`; it is ignored by the current renderer.

## Teilhard example

From `static/campaign/teilhard/campaign-seed.json`:

```json
"hero": {
  "imageUrl": "/static/campaign/teilhard/assets/hero.png",
  "fullBleed": true,
  "fit": "contain",
  "overlay": {
    "mode": "nav-only",
    "scrim": "none"
  }
}
```

Hero asset: agent drop UUID `755a4341-720a-4462-ad12-0daf5f6f8955` → `static/campaign/teilhard/assets/hero.png`.

Hero configuration: see [CAMPAIGN_HERO_CONFIG.md](CAMPAIGN_HERO_CONFIG.md).

Page theme (background gradient, footer colors): see [CAMPAIGN_THEME_CONFIG.md](CAMPAIGN_THEME_CONFIG.md).

Document embeds: see [CAMPAIGN_ARTIFACTS_CONFIG.md](CAMPAIGN_ARTIFACTS_CONFIG.md).

## Verify

```bash
cd gov-hub-prod
pytest test_campaign_embeds.py -q
curl -sS https://teilhardtest.com/ | grep -E 'gh-campaign-hero-full-bleed|hero.jpg'
```

Home HTML should include `gh-campaign-hero-full-bleed`, `gh-campaign-hero-image`, and the configured headline/quote. It should **not** include `--gh-campaign-hero-position` or `heroImagePosition`.
