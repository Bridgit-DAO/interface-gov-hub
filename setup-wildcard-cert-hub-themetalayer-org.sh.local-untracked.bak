#!/bin/bash
# Wildcard TLS for Gov Hub layer vanity on themetalayer.org (DNS-01 required).
#
# Covers:
#   hub.themetalayer.org + *.hub.themetalayer.org
#   dev.hub.themetalayer.org + *.dev.hub.themetalayer.org
#
# Prerequisite: /etc/letsencrypt/dns-multi.ini (same as setup-wildcard-cert-dns-multi.sh)
#
# Usage:
#   sudo bash setup-wildcard-cert-hub-themetalayer-org.sh

set -e

CRED_FILE="/etc/letsencrypt/dns-multi.ini"

if [ ! -f "$CRED_FILE" ]; then
    echo "Create $CRED_FILE first (see setup-wildcard-cert-dns-multi.sh)."
    exit 1
fi

if ! certbot plugins 2>/dev/null | grep -q dns-multi; then
    echo "Install certbot-dns-multi first (see setup-wildcard-cert-dns-multi.sh)."
    exit 1
fi

EMAIL="${CERTBOT_EMAIL:-admin@themetalayer.org}"

echo "Issuing prod hub cert (hub + *.hub)..."
certbot certonly -a dns-multi \
  --dns-multi-credentials="$CRED_FILE" \
  --cert-name hub.themetalayer.org \
  --non-interactive --agree-tos \
  --email "$EMAIL" \
  -d hub.themetalayer.org -d "*.hub.themetalayer.org"

echo "Issuing dev hub cert (dev.hub + *.dev.hub)..."
certbot certonly -a dns-multi \
  --dns-multi-credentials="$CRED_FILE" \
  --cert-name dev.hub.themetalayer.org \
  --non-interactive --agree-tos \
  --email "$EMAIL" \
  -d dev.hub.themetalayer.org -d "*.dev.hub.themetalayer.org"

echo ""
echo "Done. Install nginx vhost:"
echo "  sudo bash docs/install-hub-themetalayer-org.sh"
echo "  sudo nginx -t && sudo systemctl reload nginx"
