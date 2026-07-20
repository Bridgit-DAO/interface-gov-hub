# Gov Hub connectivity outage (Spectrum / hostname filtering)

Use this when **govhub.live fails on one network** (e.g. Spectrum residential IPv4) but **canopi.live on the same Mac/IP works**, and **tcpdump on the VPS shows zero packets** for govhub requests.

## What we know (2026-07-20)

| Check | Result |
|-------|--------|
| Server health | OK — SSL Labs A+, nginx `[::]:443`, app on `:8000` |
| DNS A `@` / `*` | `216.238.91.120` (propagated) |
| DNS AAAA `@` / `*` | `2001:19f0:b400:2783:5400:5ff:fe38:d135` (propagated on 8.8.8.8, 1.1.1.1, registrar) |
| DNS AAAA `dev.govhub.live` | **Missing** (A only) |
| DNS AAAA `canopi.live` | **None** (IPv4-only — why canopi works on broken paths) |
| `curl -6 https://govhub.live/` from VPS | **Works** (TLS 1.3, valid cert) |
| `curl -4 https://govhub.live/` from VPS | **Works** |
| `hub.canopi.live` | **Not deployed** (no DNS, no cert, nginx vhost not enabled) |

**Likely root cause:** Something on the user's **IPv4 path** (ISP middlebox, DNS filter, or TLS SNI block on hostnames containing `gov`) drops or mishandles traffic to `govhub.live` **before it reaches the VPS**. The server and certificate are fine.

## Why AAAA “did nothing”

Adding AAAA records does **not** fix this unless the client **successfully connects over IPv6 end-to-end**:

1. **Happy Eyeballs** — macOS/curl try IPv4 and IPv6 in parallel; a broken IPv4 path can still win or cause failure first.
2. **Spectrum IPv6** — many residential accounts have no IPv6, broken IPv6, or IPv6 that never routes to Vultr.
3. **canopi.live has no AAAA** — the working hostname uses **IPv4 only**, so comparing to canopi is apples-to-oranges unless you force IPv6 tests.
4. **AAAA is live on DNS** — propagation is not the issue; `@` and `*` both resolve on public resolvers.

### User-side tests (run on the affected Mac)

```bash
# Force IPv6 only — if this fails, AAAA cannot help on that network
curl -6 -vI --connect-timeout 10 https://govhub.live/

# Force IPv4 only — reproduces the broken path
curl -4 -vI --connect-timeout 10 https://govhub.live/

# Default (Happy Eyeballs)
curl -vI --connect-timeout 10 https://govhub.live/

# Control — should work (same VPS, different hostname)
curl -4 -vI --connect-timeout 10 https://canopi.live/
```

Interpretation:

- `-4` fails, `-6` works → use IPv6-only workaround or fix ISP IPv6; most users need the **hub.canopi.live** alias instead.
- Both fail → local DNS/VPN/firewall; flush DNS (`sudo dscacheutil -flushcache`), try phone hotspot.
- `-4` fails for govhub but `-4` works for canopi → **hostname/SNI filtering** → deploy **hub.canopi.live** (below).

## Fixes ranked (fastest to work today)

### 0. hub.themetalayer.org alias (same VPS, themetalayer wildcard TLS)

If **govhub.live** fails but **themetalayer.org** hostnames work on the same network, use:

`https://hub.themetalayer.org` (A or wildcard `*` → `216.238.91.120`).

Dedicated nginx vhost: `docs/nginx-hub-themetalayer-org.conf` (proxies to `:8000` with `Host: govhub.live`).
Install: `sudo bash docs/install-hub-themetalayer-org.sh`.

---

### 1. hub.canopi.live alias (recommended — same IPv4 path as canopi)

canopi.live already works from the affected Mac. Serve Gov Hub on a **canopi** subdomain with nginx `Host: govhub.live` upstream.

**Namecheap → Advanced DNS for `canopi.live`:**

| Type | Host | Value |
|------|------|--------|
| A | `hub` | `216.238.91.120` |

Do **not** add AAAA for `hub` unless you intentionally want IPv6 on that alias.

**On the VPS:**

```bash
cd /home/ubuntu/gov-hub-prod

# TLS (HTTP-01 is fine — hub is not a wildcard)
sudo certbot certonly --nginx -d hub.canopi.live \
  --non-interactive --agree-tos -m admin@govhub.live

sudo cp docs/nginx-hub-canopi-live.conf /etc/nginx/sites-available/hub.canopi.live
sudo ln -sf /etc/nginx/sites-available/hub.canopi.live /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Verify from Mac:**

```bash
curl -4 -vI https://hub.canopi.live/
```

Use `https://hub.canopi.live/` in the browser until govhub.live IPv4 path is fixed. OAuth redirect URIs may need `https://hub.canopi.live/...` if users sign in via the alias.

Config file: `docs/nginx-hub-canopi-live.conf`.

### 2. Phone hotspot / VPN (immediate workaround)

Confirms ISP path issue. Not a permanent fix.

### 3. IPv6-only (only if `curl -6` works on Mac)

If test 1 shows IPv6 works, user can temporarily use:

```bash
# /etc/hosts line (IPv6 only — remove when govhub IPv4 is fixed)
2001:19f0:b400:2783:5400:5ff:fe38:d135 govhub.live
```

Fragile — do not recommend for general users.

### 4. Cloudflare proxy (longer-term for govhub.live)

Move **govhub.live** to Cloudflare (orange-cloud proxy). Traffic would enter Cloudflare’s network first, which can bypass some ISP SNI/DPI blocks. Requires NS change, wildcard cert via DNS-01 on CF, and nginx real-IP headers. See `docs/GOVHUB_LIVE_SSL.md` Option A.

### 5. Optional DNS hygiene

- Add **AAAA** for `dev` if you use `dev.govhub.live` over IPv6.
- Keep **AAAA** on `@` and `*` for users who do have working IPv6.

## Server checklist (already verified 2026-07-20)

- [x] nginx listens on `0.0.0.0:443` and `[::]:443`
- [x] govhub vhost includes `listen [::]:443 ssl`
- [x] AAAA DNS propagated
- [ ] UFW: confirm `443/tcp` allowed (requires sudo — `sudo ufw status verbose`; `ufw allow 443/tcp` covers v4+v6)
- [ ] hub.canopi.live DNS + cert + nginx enabled

## What is NOT the fix

- Restarting nginx (already healthy)
- Re-issuing govhub cert (valid; SSL Labs A+)
- Adding more AAAA on apex (already present; user path is IPv4 or no v6)
