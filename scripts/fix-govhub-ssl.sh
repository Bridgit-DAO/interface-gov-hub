#!/bin/bash
# Fix govhub.live TLS when other vhosts on the same IP work (canopi, desirableproperties).
# Run on the Vultr server: sudo bash scripts/fix-govhub-ssl.sh
set -euo pipefail

REPO="${REPO_ROOT:-/home/ubuntu/gov-hub-prod}"
NGINX_SITE="/etc/nginx/sites-available/govhub.live"
CRED="${DNS_MULTI_CREDENTIALS:-/etc/letsencrypt/dns-multi-govhub.ini}"

echo "==> 1. Deploy nginx config (no default_server on 443)"
cp "$REPO/docs/nginx-govhub-wildcard-ssl.conf" "$NGINX_SITE"
grep -n 'listen.*443' "$NGINX_SITE" || true

echo "==> 2. Reissue cert as ECDSA (same chain family as canopi.live YE2)"
if [[ -f "$CRED" ]]; then
  chmod 600 "$CRED" 2>/dev/null || true
  certbot certonly --cert-name govhub.live --key-type ecdsa --force-renewal \
    -a dns-multi --dns-multi-credentials="$CRED" \
    --non-interactive --agree-tos --email "${CERTBOT_EMAIL:-admin@govhub.live}" \
    -d govhub.live -d '*.govhub.live' -d '*.dev.govhub.live'
else
  echo "WARN: $CRED missing — skipping cert renew. Fix nginx only."
fi

echo "==> 3. Restart nginx"
nginx -t
systemctl restart nginx

echo "==> 4. Verify locally"
for s in govhub.live canopi.live; do
  echo "--- $s ---"
  echo | openssl s_client -connect 127.0.0.1:443 -servername "$s" 2>/dev/null \
    | grep -E 'subject=|issuer=|Protocol|Verify return'
done

echo
echo "Done. From your Mac: curl -4 -vI https://govhub.live"
