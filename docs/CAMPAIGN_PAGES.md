# Gov Hub campaign pages – builder guide

Public campaign sites (e.g. `teilhardtest.com`) are served from **gov-hub-dev** via the campaign module. Each campaign is a presentation layer over an Overweb **Monument** record.

## Architecture

| Piece | Location |
|-------|----------|
| Seed config (dev / import source) | `static/campaign/<slug>/campaign-seed.json` |
| Campaign assets (markdown, PDFs) | `static/campaign/<slug>/` |
| Shared campaign CSS | `static/css/campaign-pages.css` |
| HTML rendering | `services/campaign_render.py` |
| Route handlers | `routes/campaign_pages.py` |
| Custom domain rewrite | `middleware/campaign_host_wsgi.py` |
| DB-backed config | `Monument.presentation_json`, `structure_json`, `custom_domains_json` |

Import a seed into the Monument record:

```bash
python scripts/import_teilhard_monument.py
```

## Configuring content (seed JSON)

`campaign-seed.json` controls copy, routes, and domain mapping:

| Field | Purpose |
|-------|---------|
| `slug` | URL prefix `/campaign/<slug>/` and host map key |
| `title`, `subtitle`, `heroQuestion` | Hero and header branding |
| `layerSlug` | Owning Gov Hub layer (e.g. `the-overweb`) |
| `customDomains` | Production vanity hosts (nginx → :8001) |
| `devHost` | Dev vanity host |
| `documents[]` | Paper (draft ref), statement (markdown path), slides (PDF path) |
| `externalLinks[]` | Outbound cards (Substack, YouTube, etc.) |
| `primaryCta`, `secondaryCtas` | Home page buttons |

Each item in `documents[]` and `externalLinks[]` may include optional card visuals for the **Read, watch, discuss** grid:

| Field | Purpose |
|-------|---------|
| `thumbnailUrl` | Image URL for the card (16:9). Path under `/static/campaign/<slug>/assets/` or absolute URL. |
| `thumbnail` | Alias for `thumbnailUrl` (either field works). |
| `icon` | Fallback when no thumbnail: `document`, `quote`, `slides`, or `link`. If omitted, inferred from `type`. |

**Resolution order:** `thumbnailUrl` / `thumbnail` first; for external links with a YouTube URL, auto-fetches `img.youtube.com` poster; otherwise the type-based icon renders in the same 16:9 frame.

**Teilhard examples** (in seed):

```json
{ "slug": "paper", "type": "paper", "thumbnailUrl": "/static/campaign/teilhard/assets/paper-thumb.jpg" }
{ "slug": "statement", "type": "statement", "icon": "quote" }
{ "slug": "slides", "type": "slide_deck", "thumbnailUrl": "/static/campaign/teilhard/assets/slides-thumb.jpg" }
{ "slug": "substack", "url": "https://...", "thumbnailUrl": "/static/campaign/teilhard/assets/substack-thumb.jpg" }
```

Static thumbnails live in `static/campaign/<slug>/assets/`. Re-import after seed changes:

```bash
python scripts/import_teilhard_monument.py
systemctl --user restart datatracker-dev
```

**Deferred (future builder UI):** PDF first-page auto-extract, draft hero passthrough, artifact upload picker for thumbnails.

Content changes: edit the seed (or Monument `presentation_json` / `structure_json` in admin) and restart or call `reload_campaign_cache()`.

## Configuring styling

Campaign pages use a **shared dark theme** in `static/css/campaign-pages.css`, aligned with Gov Hub design tokens (`--text-primary`, `--text-secondary`, accent blue).

### What builders can do today

1. **Rely on the shared theme** – all campaigns inherit readable contrast from `campaign-pages.css`. No per-campaign CSS file is required for the default look.

2. **Layer context** – set `layerSlug` so campaign nav and “Hosted on Gov Hub” footer tie to the correct layer (The Overweb, etc.).

3. **Home sections** – `presentation_json.homeSections` (from seed import) selects which blocks appear on the home page: `turing_teilhard`, `four_criteria`, `doc_grid`.

4. **Assets** – hero images, PDFs, and card thumbnails under `static/campaign/<slug>/` (see `static/campaign/teilhard/incoming/README.md` and `assets/` for grid thumbs).

### Planned / manual extensions

Per-campaign CSS is not yet wired through `presentation_json`. To customize before that ships:

- Add rules scoped under `.gh-campaign-body` in `campaign-pages.css`, or
- Extend `campaign_shell()` in `campaign_render.py` to read `presentation.customCssUrl` (future field) and inject a `<link>` tag.

When adding custom CSS, override Bootstrap utilities explicitly on dark backgrounds:

```css
.gh-campaign-body .text-muted {
  color: var(--gh-campaign-muted) !important;
}
```

Bootstrap’s default `text-muted` is gray for **light** pages and is illegible on the campaign dark shell.

## Dev URLs

| Page | Path |
|------|------|
| Home | `/campaign/teilhard/` or `https://teilhard.dev.govhub.live/` |
| Monument tree | `/campaign/teilhard/monument/` |
| Custom domain | `https://teilhardtest.com/` (nginx → datatracker-dev :8001) |

After CSS or Python changes: `systemctl --user restart datatracker-dev`.

## Checklist for new campaigns

1. Create `static/campaign/<slug>/campaign-seed.json` and assets.
2. Run import script (or create Monument via admin).
3. Point DNS / nginx at dev (:8001) or prod (:8000).
4. Verify monument tree, footer, and muted copy on `/monument/` and `/docs/statement/`.
5. Confirm contrast: subtitles, footer, tree badges (`chapter`, `page`, `stub`), text selection.
