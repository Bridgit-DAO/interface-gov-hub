# Civic Mason — client-side i18n

## Locales

- Copy lives in `static/i18n/civic-mason/{locale}.json` (e.g. `en`, `ar`).
- Runtime loader: `static/js/cm-i18n.js` (`CMI18n`).

**Note:** `.gitignore` allows only `static/js/cm-i18n.js` and `static/i18n/civic-mason/*.json`; other paths under `static/` stay ignored. New locales: add `xx.json` under `static/i18n/civic-mason/` and extend `.gitignore` exceptions if needed.

## Switching language

- Visit `/civic-mason/?lang=ar` or `?lang=en` once; preference is stored in session as `cm_locale`.

## API errors

Endpoints return `error_code` (e.g. `BADGE_REQUIRED`, `POSITION_OCCUPIED`). The page maps codes to strings via `api.errors.*` in the JSON catalogs.

## RTL

For `ar`, `#civic-mason-page` gets `dir="rtl"` and class `cm-rtl`. Arabic is a right-to-left script.

## Adding a locale

1. Add `static/i18n/civic-mason/xx.json` (copy `en.json` structure).
2. Allow it in `routes/civic_mason_pages.py`: `_CM_LOCALES`.
3. `git add -f static/i18n/civic-mason/xx.json`
