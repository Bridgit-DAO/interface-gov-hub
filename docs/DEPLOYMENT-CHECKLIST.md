# Deployment Checklist: Wildcard Subdomain + Nginx

## 1. DNS (You already did this ✓)

You created:
```
A    *    0    216.238.91.120    300
```

This routes `*.themetalayer.org` and `themetalayer.org` to your server.

**Verify:** `dig overweb.themetalayer.org` or `nslookup overweb.themetalayer.org` should return 216.238.91.120.

---

## 2. Wildcard SSL Certificate

HTTP-01 challenge **cannot** issue wildcard certs. You must use **DNS-01** challenge.

### Option A: Cloudflare (if you use it)

```bash
# Install certbot and the Cloudflare plugin
sudo apt install certbot python3-certbot-dns-cloudflare -y

# Create credentials file (chmod 600)
sudo tee /etc/letsencrypt/cloudflare.ini << 'EOF'
dns_cloudflare_api_token = YOUR_CLOUDFLARE_API_TOKEN
EOF
sudo chmod 600 /etc/letsencrypt/cloudflare.ini

# Get wildcard cert
sudo certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  -d themetalayer.org \
  -d "*.themetalayer.org"
```

### Option B: Manual DNS (any provider)

```bash
sudo certbot certonly --manual --preferred-challenges=dns \
  -d themetalayer.org -d "*.themetalayer.org"
```

Certbot will ask you to add a TXT record. Add it at your DNS provider, wait for propagation, then continue.

---

## 3. Nginx Configuration

### Create the site config

```bash
# Copy config (use full path so it works from any directory)
sudo cp /home/ubuntu/gov-hub-dev/docs/nginx-wildcard-config.conf /etc/nginx/sites-available/themetalayer.org

# Verify the file exists before creating symlink
ls -la /etc/nginx/sites-available/themetalayer.org

# Enable the site
sudo ln -sf /etc/nginx/sites-available/themetalayer.org /etc/nginx/sites-enabled/
```

**If you get "open() ... themetalayer.org failed (2: No such file or directory)":** The symlink exists but the target file is missing. Run the `sudo cp` command above first, then `sudo nginx -t`.

### If you already have certs, edit to add SSL

```bash
sudo nano /etc/nginx/sites-available/themetalayer.org
```

Add after `listen 80;`:

```nginx
listen 443 ssl;
ssl_certificate /etc/letsencrypt/live/themetalayer.org/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/themetalayer.org/privkey.pem;
include /etc/letsencrypt/options-ssl-nginx.conf;
```

### Or run Certbot to auto-configure SSL

```bash
sudo certbot --nginx -d themetalayer.org -d "*.themetalayer.org"
```

### Test and reload

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

## 4. Existing Sites (dev, rfc)

Your existing configs (`dev.rfc.themetalayer.org`, `rfc.themetalayer.org`) use **exact** server_name, so they take precedence over the wildcard. Order in `sites-enabled` can matter: more specific server_names usually match first.

If `rfc.themetalayer.org` and `dev.rfc.themetalayer.org` already work, keep those configs. The wildcard will handle `overweb.themetalayer.org`, `canopi.themetalayer.org`, etc.

---

## 5. Local Testing (no SSL)

Add to `/etc/hosts`:

```
216.238.91.120  overweb.themetalayer.org
216.238.91.120  canopi.themetalayer.org
```

Then visit `http://overweb.themetalayer.org` (port 80) or `http://overweb.themetalayer.org:8000` if proxying isn't set up yet.

---

## 6. Summary Commands

```bash
# 1. Verify DNS
dig overweb.themetalayer.org +short
# Should show: 216.238.91.120

# 2. Get wildcard cert (Cloudflare)
sudo certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  -d themetalayer.org -d "*.themetalayer.org"

# 3. Install Nginx config
sudo cp /home/ubuntu/gov-hub-dev/docs/nginx-wildcard-config.conf /etc/nginx/sites-available/themetalayer.org
sudo ln -sf /etc/nginx/sites-available/themetalayer.org /etc/nginx/sites-enabled/

# 4. Let Certbot add SSL to the config (or add manually)
sudo certbot --nginx -d themetalayer.org -d "*.themetalayer.org"

# 5. Reload
sudo nginx -t && sudo systemctl reload nginx
```
