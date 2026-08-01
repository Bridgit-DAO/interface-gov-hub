# Gov Hub layer vanity on hub.themetalayer.org

Production and development layer sites use the same Flask layer-resolution middleware as `*.govhub.live`, on preferred hostnames that avoid ISP blocks on the word “gov”.

## Hostnames

| Environment | Apex (no layer) | Layer vanity |
|-------------|-----------------|--------------|
| **Production** | `https://hub.themetalayer.org` | `https://[layer-slug].hub.themetalayer.org` |
| **Development** | `https://dev.hub.themetalayer.org` | `https://[layer-slug].dev.hub.themetalayer.org` |

Examples: `https://the-metaweb.hub.themetalayer.org`, `https://canopi.dev.hub.themetalayer.org`.

Legacy `*.govhub.live` and `*.dev.govhub.live` continue to work.

**Retired:** `dev.rfc.themetalayer.org` — removed; no redirect. Use `dev.hub.themetalayer.org` only.

## Flask

`BASE_DOMAINS` in `config.py` includes `hub.themetalayer.org` and `dev.hub.themetalayer.org` (longest suffix wins). Middleware: `middleware/__init__.py` → `_do_resolve_layer_from_host()`.

Run tests:

```bash
python3 test_layer_resolution.py
```

## DNS (themetalayer.org)

| Type | Host | Value |
|------|------|-------|
| A | `hub` | VPS IPv4 |
| A | `*.hub` | VPS IPv4 |
| A | `dev.hub` | VPS IPv4 |
| A | `*.dev.hub` | VPS IPv4 |

Or use existing wildcard `*` → VPS if your registrar supports nested wildcards.

Remove any DNS records for `dev.rfc.themetalayer.org` when decommissioning the old hostname.

## TLS

`*.themetalayer.org` covers only **one** label (e.g. `foo.themetalayer.org`), **not** `canopi.hub.themetalayer.org`.

Issue two DNS-01 wildcard certs:

```bash
sudo bash setup-wildcard-cert-hub-themetalayer-org.sh
```

Certs:

- `/etc/letsencrypt/live/hub.themetalayer.org/` — `hub.themetalayer.org` + `*.hub.themetalayer.org`
- `/etc/letsencrypt/live/dev.hub.themetalayer.org/` — `dev.hub.themetalayer.org` + `*.dev.hub.themetalayer.org`

## Nginx

```bash
sudo bash docs/install-hub-themetalayer-org.sh
```

Configs:

- `docs/nginx-hub-themetalayer-org.conf` — prod apex → `:8000`
- `docs/nginx-dev-hub-themetalayer-org.conf` — dev apex + layer vanity → `:8001`

Both pass browser `Host` through (required for layer slug resolution).

## OAuth

Register redirect URIs on apex hosts — see `docs/OAUTH_REDIRECT_URIS.md`.

Remove `dev.rfc.themetalayer.org` from all OAuth provider dashboards.

## Canopi

Set per environment:

- Prod: `GOV_HUB_PUBLIC_URL=https://hub.themetalayer.org`
- Dev/staging: `GOV_HUB_PUBLIC_URL=https://dev.hub.themetalayer.org`

Logo URL rewrites map legacy `*.govhub.live` → `*.hub.themetalayer.org` in `canopi/server/lib/govHubAssetUrl.js`.
