# Global shell i18n (Gov-Hub)

- **Locales:** `en`, `ar`, `fr`, `pt`, `zh-Hans` (Simplified Chinese), `ja`, `ru`.
- **Session:** `?lang=<code>` on any page sets `session['locale']` (whitelist in `services/locale.py`).
- **JSON:** `static/i18n/shell/{locale}.json` – navbar, governance menu, user menu, footer, theme strings.
- **Loader:** `static/js/govhub-i18n.js` – `GovHubI18n.init(locale, extraBaseOrNull)` merges shell + optional second bundle (e.g. Civic Mason).
- **Markup:** `data-gh-i18n`, `data-gh-i18n-placeholder`, `data-gh-i18n-aria`, `data-gh-i18n-title` (same pattern as Civic Mason `data-cm-*`).
- **Civic Mason:** `body` includes `data-i18n-extra-base="/static/i18n/civic-mason/"`; init runs once at top of `<body>` and loads both bundles. Page script `await window.__GH_I18N_READY__`.
- **Layer standalone footer:** `data-footer-mode="layer"` and `data-layer-name` for translated “Build … | {layer}”.
- **Tracked files:** see `.gitignore` exceptions for `govhub-i18n.js`, `static/i18n/shell/*.json`, and civic-mason locale JSON.

Legacy `static/js/cm-i18n.js` is a shim; the implementation lives in `govhub-i18n.js`.
