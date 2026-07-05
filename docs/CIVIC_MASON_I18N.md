# Civic Mason – client-side i18n

## Locales

- Copy lives in `static/i18n/civic-mason/{locale}.json` (e.g. `en`, `ar`).
- Runtime loader: `static/js/govhub-i18n.js` (`GovHubI18n` / `CMI18n` alias). Legacy `cm-i18n.js` is a thin shim.

**Note:** See `.gitignore` for tracked `govhub-i18n.js`, `cm-i18n.js`, `static/i18n/shell/*.json`, and `static/i18n/civic-mason/*.json`. New locales: add shell + civic-mason JSON files and extend `SUPPORTED_LOCALES` in `services/locale.py`.

## Switching language

- Visit any page with `?lang=` (e.g. `/civic-mason/?lang=ar`); preference is stored in session as `locale` (see `services/locale.py`). Legacy `cm_locale` is migrated once if present.

## API errors

Endpoints return `error_code` (e.g. `BADGE_REQUIRED`, `POSITION_OCCUPIED`). The page maps codes to strings via `api.errors.*` in the JSON catalogs.

## RTL

For `ar`, `#civic-mason-page` gets `dir="rtl"` and class `cm-rtl`. Arabic is a right-to-left script.

## Adding a locale

1. Add `static/i18n/civic-mason/xx.json` (copy `en.json` structure).
2. Allow it in `services/locale.py`: `SUPPORTED_LOCALES`.
3. `git add -f static/i18n/civic-mason/xx.json`
