# Campaign theme configuration

Gov Hub campaign pages use a dark shell with a scroll-linked page gradient and a footer band. Colors and gradient stops are configured in the nested `theme` object inside `campaign-seed.json` or Monument `presentation_json`.

Schema reference for builders and import scripts.

## Where to configure

| Source | Path |
|--------|------|
| Dev seed | `static/campaign/<slug>/campaign-seed.json` |
| Production Monument | `presentation_json.theme` (imported from seed) |
| Parser | `services/campaign_pages.py` → `normalize_theme_config()` |
| Renderer | `services/campaign_render.py` → `_campaign_theme_style()` (public shell) and `campaign_admin_shell()` (admin pages) |
| Styles | `static/css/campaign-pages.css` (defaults; overridden per campaign) |

The `theme` block applies **site-wide** on a campaign vanity host: home, docs, monument pages, and admin routes (`/admin/thumbnails/`, `/admin/endorsements/`). Admin pages use a compact shell with the same CSS custom properties; they do not render the scroll gradient wrapper.

Re-import after seed changes:

```bash
python scripts/import_teilhard_monument.py
systemctl --user restart datatracker.service   # production
# or datatracker-dev on dev (:8001)
```

## JSON schema

```json
{
  "theme": {
    "pageBackground": "#020408",
    "footerBackground": "#0a1224",
    "gradient": {
      "enabled": true,
      "heightVh": 300,
      "stops": [
        {"at": 0, "color": "#020408"},
        {"at": 25, "color": "#030610"},
        {"at": 55, "color": "#050b1a"},
        {"at": 85, "color": "#0a1224"},
        {"at": 100, "color": "#0a1224"}
      ]
    }
  }
}
```

### Fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `pageBackground` | string (hex) | `#020408` | Hero/top page tone; also sets `--gh-campaign-gradient-top` |
| `footerBackground` | string (hex) | `#0a1224` | Footer surface, body fallback below gradient, gradient end color |
| `gradient.enabled` | boolean | `true` | When false, only solid footer background is used |
| `gradient.heightVh` | integer | `300` | Vertical span of the gradient (`background-size: 100% Nvh`) |
| `gradient.stops` | array | see defaults | `{ at: 0–100, color: "#rrggbb" }` stops for `linear-gradient(180deg, …)` |

### Rendering behavior

- **Body fallback** uses `footerBackground`, not `pageBackground`. This prevents a pitch-black band when scroll height exceeds the gradient span.
- **Gradient end stops** should match `footerBackground` so the page transitions into the footer without a visible seam.
- **Footer** uses `footerBackground` explicitly (not transparent).
- When `theme` is omitted, defaults match the Teilhard campaign palette.

Hero configuration: see [CAMPAIGN_HERO_CONFIG.md](CAMPAIGN_HERO_CONFIG.md).

Document embeds: see [CAMPAIGN_ARTIFACTS_CONFIG.md](CAMPAIGN_ARTIFACTS_CONFIG.md).

## Teilhard example

From `static/campaign/teilhard/campaign-seed.json`:

```json
"theme": {
  "pageBackground": "#020408",
  "footerBackground": "#0a1224",
  "gradient": {
    "enabled": true,
    "heightVh": 300,
    "stops": [
      {"at": 0, "color": "#020408"},
      {"at": 25, "color": "#030610"},
      {"at": 55, "color": "#050b1a"},
      {"at": 85, "color": "#0a1224"},
      {"at": 100, "color": "#0a1224"}
    ]
  }
}
```

## Verify

```bash
cd gov-hub-prod
pytest test_campaign_embeds.py -q
curl -sS https://teilhardtest.com/ | grep -E 'gh-campaign-footer-bg|--gh-campaign-footer-bg|campaign-pages.css?v=18'
curl -sS https://teilhardtest.com/admin/thumbnails/ | grep -E 'gh-campaign-body|gh-campaign-admin|--gh-campaign-footer-bg|campaign-pages.css?v=18'
```

Home HTML should include an inline `<style>` block setting `--gh-campaign-footer-bg: #0a1224` and `background-color: #0a1224` on `.gh-campaign-body-gradient`. The footer should not sit on `#020408` black below the gradient cutoff.
