# Interface Hub domain (`interfacehub.net`)

Canonical public host for Gov Hub is **https://interfacehub.net**.

`hub.themetalayer.org` remains a legacy alias until nginx redirects are installed.

## Hostnames

| Environment | Apex | Layer vanity |
|-------------|------|----------------|
| Production | `https://interfacehub.net` | `https://[layer-slug].interfacehub.net` |
| Development | `https://dev.interfacehub.net` | `https://[layer-slug].dev.interfacehub.net` |
| Staging | `https://staging.interfacehub.net` | (same app as dev, `:8001`) |

Legacy (keep working, then 301):

- `https://hub.themetalayer.org` → `https://interfacehub.net`
- `https://[layer].hub.themetalayer.org` → `https://[layer].interfacehub.net`
- `https://dev.hub.themetalayer.org` → `https://dev.interfacehub.net`

`govhub.live` stays as a compatibility host (ISP “gov” blocks were the original reason for `hub.themetalayer.org`).

## Activate (ops)

1. **Cloudflare zone** `interfacehub.net` must be **Active** (NS already `everton` / `paige`). Grey-cloud (DNS-only) A records to `216.238.91.120`:
   - `@`, `www`, `*`, `dev`, `*.dev`, `staging`
   - Helper: `CLOUDFLARE_API_TOKEN=... python3 scripts/ensure-interfacehub-cloudflare-dns.py`
2. **TLS** (needs sudo + Cloudflare token with Zone:DNS:Edit). Do not list `www` on the cert request; `*.interfacehub.net` already covers it:
   - `sudo CLOUDFLARE_API_TOKEN=... bash setup-wildcard-cert-interfacehub-net.sh`
3. **nginx**:
   - `sudo bash docs/install-interfacehub-net.sh`
4. **Verify**:
   - `curl -4 -sI https://interfacehub.net/` (Flask/Gov Hub, not `govhub.live` cert)
   - `curl -4 -sI https://www.interfacehub.net/` → 301 to apex
   - `curl -4 -sI --resolve canopi.interfacehub.net:443:216.238.91.120 https://canopi.interfacehub.net/`
5. **Web3Auth dashboard** (manual, no API): add origins
   - `https://interfacehub.net`
   - `https://dev.interfacehub.net`
   - Keep `https://hub.themetalayer.org` until redirects and sessions settle.
6. **Env** (already in tree defaults; confirm on disk, do not commit values):
   - Prod Gov Hub: `PUBLIC_BASE_URL=https://interfacehub.net`
   - Dev Gov Hub: `PUBLIC_BASE_URL=https://dev.interfacehub.net`
   - Canopi: `GOV_HUB_PUBLIC_URL=https://interfacehub.net` (prod) / `https://dev.interfacehub.net` (dev)
7. Restart: `systemctl --user restart datatracker.service datatracker-dev.service`
8. **Mail**: leave Resend `RESEND_FROM` on the verified `hub.themetalayer.org` sender until SPF/DKIM/DMARC exist for `interfacehub.net`. Then switch to `no-reply@interfacehub.net`.
9. **Legacy redirect** (after 5–7 work): install `docs/nginx-hub-themetalayer-org-redirect-to-interfacehub.conf`.

## Flask

`BASE_DOMAINS` includes `dev.interfacehub.net` and `interfacehub.net` (longest suffix wins). Layer hosts: `[slug].interfacehub.net`.
