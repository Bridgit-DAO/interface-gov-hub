#!/bin/bash
# OPTIONAL – only if govhub.live DNS is hosted on Cloudflare.
#
# If you use Namecheap (or most other registrars) for DNS, do NOT use this script.
# Use: setup-wildcard-cert-govhub-dns-multi.sh
#
# ---
# One-time (or renew) wildcard SSL for Gov Hub on govhub.live:
#   govhub.live, *.govhub.live, *.dev.govhub.live
# Uses Cloudflare DNS-01. Renewals use the same credentials file.
#
# Prereq: govhub.live zone must exist on Cloudflare (nameservers point to CF).
# Token: Cloudflare Dashboard → My Profile → API Tokens → Create Token
#        Template "Edit zone DNS", Zone Resources → Include → Specific zone → govhub.live
#
# Usage:
#   CLOUDFLARE_TOKEN=your_token sudo -E bash setup-wildcard-cert-govhub-cloudflare.sh
#
# Optional:
#   CERTBOT_EMAIL=you@example.com
#   DRY_RUN=1   # append --dry-run to certbot (no cert issued)

set -e

EMAIL="${CERTBOT_EMAIL:-admin@govhub.live}"
CRED_FILE="/etc/letsencrypt/cloudflare-govhub.ini"
DRY_FLAG=()
if [ -n "$DRY_RUN" ]; then
  DRY_FLAG=(--dry-run)
fi

if [ -z "$CLOUDFLARE_TOKEN" ]; then
  echo "Set your Cloudflare API token (scoped to zone govhub.live):"
  echo "  CLOUDFLARE_TOKEN=your_token sudo -E bash setup-wildcard-cert-govhub-cloudflare.sh"
  echo ""
  echo "Cloudflare → My Profile → API Tokens → Create Token → Edit zone DNS"
  exit 1
fi

apt-get install -y certbot python3-certbot-dns-cloudflare 2>/dev/null || true

mkdir -p /etc/letsencrypt
umask 077
cat > "$CRED_FILE" << EOF
dns_cloudflare_api_token = $CLOUDFLARE_TOKEN
EOF
chmod 600 "$CRED_FILE"

certbot certonly --dns-cloudflare \
  --dns-cloudflare-credentials "$CRED_FILE" \
  --non-interactive --agree-tos \
  --email "$EMAIL" \
  "${DRY_FLAG[@]}" \
  -d govhub.live \
  -d "*.govhub.live" \
  -d "*.dev.govhub.live"

echo ""
echo "Cert paths (use in nginx):"
echo "  ssl_certificate     /etc/letsencrypt/live/govhub.live/fullchain.pem;"
echo "  ssl_certificate_key /etc/letsencrypt/live/govhub.live/privkey.pem;"
echo ""
echo "Reload nginx: sudo nginx -t && sudo systemctl reload nginx"
