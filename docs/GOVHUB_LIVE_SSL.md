# SSL for `govhub.live` + `*.govhub.live` (mirror `themetalayer.org`)

Wildcard certificates **must** use the **DNS-01** challenge (Let’s Encrypt does not issue `*.govhub.live` over HTTP). Your repo already does this for `themetalayer.org` via **Cloudflare** (`setup-wildcard-cert-cloudflare.sh`) or **certbot-dns-multi** (`setup-wildcard-cert-dns-multi.sh` + Namecheap API).

## Troubleshooting `ERR_SSL_PROTOCOL_ERROR`

If some users see this in Chrome/mobile but others do not:

1. **Confirm the exact URL** – must be `https://govhub.live/` (not the raw IP `216.238.91.120`, not a typo domain).
2. **ECDSA certificate** – the current cert uses an ECDSA key (`key_type = ecdsa` in `/etc/letsencrypt/renewal/govhub.live.conf`). Very old Android, some corporate proxies, and legacy TLS stacks can fail with `ERR_SSL_PROTOCOL_ERROR`. Reissue with RSA if needed:
   ```bash
   sudo certbot certonly -a dns-multi \
     --dns-multi-credentials=/etc/letsencrypt/dns-multi-govhub.ini \
     --cert-name govhub.live --force-renewal --key-type rsa \
     -d govhub.live -d "*.govhub.live" -d "*.dev.govhub.live"
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. **IPv6** – govhub nginx blocks should include `listen [::]:443 ssl;` so IPv6 HTTPS does not fall through to the default catch-all vhost. See `docs/nginx-govhub-wildcard-ssl.conf`.
4. **User-side** – VPN, antivirus HTTPS scanning, or stale DNS cache. Ask affected users to try another network/device or `chrome://net-internals/#dns` → Clear host cache.

Quick server checks:
```bash
curl -sI https://govhub.live/
echo | openssl s_client -connect govhub.live:443 -servername govhub.live 2>/dev/null | openssl x509 -noout -dates -subject
dig +short govhub.live A @8.8.8.8
```

## 1. DNS (Namecheap)

In **Advanced DNS** for `govhub.live`:

| Type | Host | Value | Notes |
|------|------|--------|--------|
| **A** | `@` | Your server IPv4 | Apex |
| **A** | `*` | Same IPv4 | Wildcard subdomains (`foo.govhub.live`) |

Optional: **AAAA** for `@` and `*` if you use IPv6.

Propagation: wait until `dig +short govhub.live A` and `dig +short randomname.govhub.live A` return your IP.

## 2. Issue the certificate (pick one path)

### Option A – DNS on **Cloudflare** (same as many `themetalayer.org` setups)

1. Move or **delegate** `govhub.live` to Cloudflare (nameservers), or use a CF-hosted zone with the same records as above.
2. API token: **Edit zone DNS** for `govhub.live`.
3. On the server:

```bash
sudo apt-get install -y certbot python3-certbot-dns-cloudflare

sudo tee /etc/letsencrypt/cloudflare-govhub.ini << 'EOF'
dns_cloudflare_api_token = YOUR_CLOUDFLARE_API_TOKEN
EOF
sudo chmod 600 /etc/letsencrypt/cloudflare-govhub.ini

sudo certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare-govhub.ini \
  --non-interactive --agree-tos \
  --email YOUR_EMAIL \
  -d govhub.live -d "*.govhub.live"
```

Cert files will live under:

`/etc/letsencrypt/live/govhub.live/` (`fullchain.pem`, `privkey.pem`).

**Renewal:** Certbot renews with the same plugin; keep the credentials file and permissions.

### Option B – DNS stays on **Namecheap** (no Cloudflare)

Use **DNS-01** with a plugin that supports Namecheap, e.g. **certbot-dns-multi** (see `setup-wildcard-cert-dns-multi.sh`).

1. Namecheap: Profile → **Tools** → **Namecheap API Access** → enable API, allowlist server IP if required.
2. Create `/etc/letsencrypt/dns-multi.ini`:

```ini
dns_multi_provider = namecheap
NAMECHEAP_API_USER = your_namecheap_username
NAMECHEAP_API_KEY = your_namecheap_api_key
```

```bash
sudo chmod 600 /etc/letsencrypt/dns-multi.ini
```

3. Install plugin (snap or apt – see comments in `setup-wildcard-cert-dns-multi.sh`), then:

```bash
sudo certbot certonly -a dns-multi \
  --dns-multi-credentials=/etc/letsencrypt/dns-multi.ini \
  --non-interactive --agree-tos \
  --email YOUR_EMAIL \
  -d govhub.live -d "*.govhub.live"
```

### Option C – **Manual** DNS-01 (no API)

Possible but painful for renewal every ~90 days; prefer A or B.

```bash
sudo certbot certonly --manual --preferred-challenges dns \
  -d govhub.live -d "*.govhub.live"
```

Add the `_acme-challenge` TXT records Namecheap asks for, wait for `dig TXT _acme-challenge.govhub.live`, then continue.

---

## 3. Nginx (mirror wildcard vhost)

Use the same pattern as `docs/nginx-wildcard-ssl.conf` for `themetalayer.org`:

- `server_name govhub.live *.govhub.live;`
- `ssl_certificate` / `ssl_certificate_key` → `/etc/letsencrypt/live/govhub.live/fullchain.pem` and `privkey.pem`
- Optional: same `/dev/` → `8001` and `/` → `8000` split as in the metalayer file

Example file in this repo: **`docs/nginx-govhub-wildcard-ssl.conf`**.

```bash
sudo cp docs/nginx-govhub-wildcard-ssl.conf /etc/nginx/sites-available/govhub.live
sudo ln -sf /etc/nginx/sites-available/govhub.live /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Adjust `proxy_pass` ports if your Gov-Hub processes differ from `8000` / `8001`.

## 4. Certbot nginx installer?

`certbot --nginx` only does **HTTP-01** by default – it will **not** obtain `*.govhub.live`. Get the cert with **dns-cloudflare** or **dns-multi** first, then point nginx at the paths above (or run `certbot install` only if you’re using a compatible workflow).

## Quick run (on the server)

From the `gov-hub-dev` repo:

```bash
cd /path/to/gov-hub-dev
chmod +x setup-govhub-live.sh

# 1) Optional: see DNS
sudo ./setup-govhub-live.sh check-dns

# 2) Cloudflare: token with DNS edit on govhub.live
sudo CLOUDFLARE_API_TOKEN='your_cloudflare_api_token' ./setup-govhub-live.sh all
```

If the cert already exists and you only need nginx:

```bash
sudo ./setup-govhub-live.sh nginx
```

Namecheap DNS (no Cloudflare): create `/etc/letsencrypt/dns-multi-govhub.ini`, then:

```bash
sudo GOVHUB_DNS_PLUGIN=dns-multi ./setup-govhub-live.sh all
```

## 5. Checklist

- [ ] `A` @ and `A` * → server IP  
- [ ] Wildcard cert issued via DNS-01 (`govhub.live` + `*.govhub.live`)  
- [ ] Nginx `server_name govhub.live *.govhub.live` + correct `ssl_certificate` paths  
- [ ] `sudo certbot renew --dry-run` succeeds  
- [ ] App config / OAuth redirect URIs updated for `https://govhub.live` and any subdomains you use  
