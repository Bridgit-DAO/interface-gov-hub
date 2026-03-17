#!/bin/bash
# One-time setup: Get wildcard SSL cert for themetalayer.org + *.themetalayer.org
# Uses Cloudflare API - NO manual TXT records. Run once, cert auto-renews.
#
# Prereq: themetalayer.org DNS must be on Cloudflare
# Get token: Cloudflare Dashboard → My Profile → API Tokens → Create Token
#            Use "Edit zone DNS" template, scope to themetalayer.org
#
# Usage:
#   CLOUDFLARE_TOKEN=your_token sudo -E bash setup-wildcard-cert-cloudflare.sh
#
# Optional: CERTBOT_EMAIL=you@example.com (default: admin@themetalayer.org)

set -e

EMAIL="${CERTBOT_EMAIL:-admin@themetalayer.org}"

if [ -z "$CLOUDFLARE_TOKEN" ]; then
    echo "Set your Cloudflare API token:"
    echo "  CLOUDFLARE_TOKEN=your_token sudo -E bash setup-wildcard-cert-cloudflare.sh"
    echo ""
    echo "Get token: Cloudflare → My Profile → API Tokens → Create Token"
    echo "Use 'Edit zone DNS' template for themetalayer.org"
    exit 1
fi

apt-get install -y certbot python3-certbot-dns-cloudflare 2>/dev/null || true

mkdir -p /etc/letsencrypt
cat > /etc/letsencrypt/cloudflare.ini << EOF
dns_cloudflare_api_token = $CLOUDFLARE_TOKEN
EOF
chmod 600 /etc/letsencrypt/cloudflare.ini

certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  --non-interactive --agree-tos \
  --email "$EMAIL" \
  -d themetalayer.org -d "*.themetalayer.org"

echo ""
echo "Done. Cert at /etc/letsencrypt/live/themetalayer.org/"
echo "Run: sudo bash setup-layer-subdomain-ssl.sh"
