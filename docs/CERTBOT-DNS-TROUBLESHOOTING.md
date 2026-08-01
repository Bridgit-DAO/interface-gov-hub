# Certbot DNS Challenge Troubleshooting

## Error: "No TXT record found at _acme-challenge.themetalayer.org"

### 1. Verify the TXT record exists

Run this **before** pressing Enter in certbot:

```bash
# Check what Let's Encrypt sees
dig TXT _acme-challenge.themetalayer.org +short

# Or use nslookup
nslookup -type=TXT _acme-challenge.themetalayer.org
```

You should see the exact value certbot gave you (e.g. `"abc123xyz..."`). If empty or wrong, the record isn't set correctly.

### 2. Add the record correctly

At your DNS provider (Cloudflare, Namecheap, etc.):

| Field | Value |
|-------|-------|
| **Type** | TXT |
| **Name** | `_acme-challenge` (or `_acme-challenge.themetalayer.org` - some providers want just the subdomain part) |
| **Content** | The exact string certbot showed (in quotes if your provider requires it) |
| **TTL** | 300 or Auto |

**Common mistakes:**
- Name `_acme-challenge.themetalayer.org` when provider expects just `_acme-challenge`
- Name `themetalayer.org` when it should be `_acme-challenge`
- Typo in the value – copy/paste from certbot
- Forgetting to save/publish the record

### 3. Wait for propagation

DNS can take 5–60 minutes. Check every few minutes:

```bash
dig TXT _acme-challenge.themetalayer.org +short
```

When you see the value, press Enter in certbot.

### 4. Manual DNS (works with any provider)

No API token needed. Add the TXT record yourself in your DNS provider's control panel:

```bash
sudo certbot certonly --manual --preferred-challenges dns \
  -d dev.hub.themetalayer.org -d "*.dev.hub.themetalayer.org"
```

Certbot will pause and show a TXT record. Add it at your DNS provider, wait 1–2 min, run `dig TXT _acme-challenge.dev.hub.themetalayer.org +short` to verify, then press Enter. You'll repeat this at renewal (~90 days).

### 5. Cloudflare plugin (optional, if you use Cloudflare)

If you use Cloudflare for DNS, the plugin automates this:

```bash
sudo apt install certbot python3-certbot-dns-cloudflare -y
sudo nano /etc/letsencrypt/cloudflare.ini
# Add: dns_cloudflare_api_token = YOUR_TOKEN
sudo chmod 600 /etc/letsencrypt/cloudflare.ini

sudo certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  -d themetalayer.org -d "*.themetalayer.org"
```

No manual TXT records needed.

### 6. Retry certbot

```bash
sudo certbot certonly --manual --preferred-challenges=dns \
  -d themetalayer.org -d "*.themetalayer.org"
```

Add the TXT record, verify with `dig`, then press Enter.
