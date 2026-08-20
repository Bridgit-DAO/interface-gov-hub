# Gov Hub layer vanity (Interface Hub)

Production and development layer sites use Flask layer-resolution middleware. Canonical hosts are on **interfacehub.net**. Legacy `*.hub.themetalayer.org` and `*.govhub.live` continue until nginx redirects.

## Hostnames

| Environment | Apex (no layer) | Layer vanity |
|-------------|-----------------|--------------|
| **Production** | `https://interfacehub.net` | `https://[layer-slug].interfacehub.net` |
| **Development** | `https://dev.interfacehub.net` | `https://[layer-slug].dev.interfacehub.net` |
| Legacy | `https://hub.themetalayer.org` | `https://[layer-slug].hub.themetalayer.org` |

Examples: `https://the-metaweb.interfacehub.net`, `https://canopi.dev.interfacehub.net`.

## Flask

`BASE_DOMAINS` in `config.py` includes `interfacehub.net` and `dev.interfacehub.net` (longest suffix wins). Middleware: `middleware/__init__.py` → `_do_resolve_layer_from_host()`.

Run tests:

```bash
python3 test_layer_resolution.py
```

## DNS (interfacehub.net, Cloudflare)

See `docs/INTERFACEHUB-NET.md`. Grey-cloud A records to the VPS for `@`, `www`, `*`, `dev`, `*.dev`.

## TLS

Issue two DNS-01 wildcard certs:

```bash
sudo CLOUDFLARE_API_TOKEN='...' bash setup-wildcard-cert-interfacehub-net.sh
```

Certs:

- `/etc/letsencrypt/live/interfacehub.net/` — apex + `www` + `*.interfacehub.net`
- `/etc/letsencrypt/live/dev.interfacehub.net/` — `dev.interfacehub.net` + `*.dev.interfacehub.net`

## Nginx

```bash
sudo bash docs/install-interfacehub-net.sh
```

Config: `docs/nginx-interfacehub-net.conf`. Passes browser `Host` through (required for layer slug resolution).

After the new origin is verified, install `docs/nginx-hub-themetalayer-org-redirect-to-interfacehub.conf`.

## OAuth

Register redirect URIs on apex hosts — see `docs/OAUTH_REDIRECT_URIS.md`.

## Canopi

Set per environment:

- Prod: `GOV_HUB_PUBLIC_URL=https://interfacehub.net`
- Dev/staging: `GOV_HUB_PUBLIC_URL=https://dev.interfacehub.net`

Logo URL rewrites map legacy `*.govhub.live` and `hub.themetalayer.org` → the current public origin in `canopi/server/lib/govHubAssetUrl.js`.
