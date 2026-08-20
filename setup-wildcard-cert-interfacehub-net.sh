#!/bin/bash
# Wildcard TLS for Interface Hub (interfacehub.net) via DNS-01.
#
# Covers:
#   interfacehub.net + *.interfacehub.net  (www is included by the wildcard; LE rejects both)
#   dev.interfacehub.net + *.dev.interfacehub.net
#
# DNS for this zone is Cloudflare. dns-multi.ini on this VPS is for other
# zones (Namecheap/Vultr) and will not issue these names unless the provider
# is Cloudflare with Zone:DNS:Edit on interfacehub.net.
#
# Usage:
#   sudo CLOUDFLARE_API_TOKEN='...' bash setup-wildcard-cert-interfacehub-net.sh
#
# Or write /etc/letsencrypt/dns-multi-interfacehub.ini:
#   dns_multi_provider = cloudflare
#   CLOUDFLARE_DNS_API_TOKEN = ...
# then:
#   sudo DNS_MULTI_CREDENTIALS=/etc/letsencrypt/dns-multi-interfacehub.ini \
#     bash setup-wildcard-cert-interfacehub-net.sh

set -euo pipefail

EMAIL="${CERTBOT_EMAIL:-admin@interfacehub.net}"
CRED_FILE="${DNS_MULTI_CREDENTIALS:-/etc/letsencrypt/dns-multi-interfacehub.ini}"
DEFAULT_CRED="/etc/letsencrypt/dns-multi.ini"

if [ ! -f "$CRED_FILE" ] && [ -n "${CLOUDFLARE_API_TOKEN:-}" ]; then
    CRED_FILE="/etc/letsencrypt/dns-multi-interfacehub.ini"
    umask 077
    cat > "$CRED_FILE" << EOF
dns_multi_provider = cloudflare
CLOUDFLARE_DNS_API_TOKEN = ${CLOUDFLARE_API_TOKEN}
EOF
    chmod 600 "$CRED_FILE"
    echo "Wrote $CRED_FILE from CLOUDFLARE_API_TOKEN"
fi

if [ ! -f "$CRED_FILE" ] && [ -f "$DEFAULT_CRED" ]; then
    echo "Missing $CRED_FILE"
    echo "Pass CLOUDFLARE_API_TOKEN or create a Cloudflare dns-multi credentials file."
    echo "Will not fall back to $DEFAULT_CRED (likely a different DNS provider)."
    exit 1
fi

if [ ! -f "$CRED_FILE" ]; then
    echo "Missing credentials file: $CRED_FILE"
    exit 1
fi

chmod 600 "$CRED_FILE" 2>/dev/null || true

if ! certbot plugins 2>/dev/null | grep -q dns-multi; then
    echo "Install certbot-dns-multi first (see docs/DNS-PROVIDER-SETUP.md)."
    exit 1
fi

DRY_FLAG=()
if [ -n "${DRY_RUN:-}" ]; then
    DRY_FLAG=(--dry-run)
fi

echo "Issuing prod cert (apex + *)..."
certbot certonly -a dns-multi \
  --dns-multi-credentials="$CRED_FILE" \
  --cert-name interfacehub.net \
  --non-interactive --agree-tos \
  --email "$EMAIL" \
  "${DRY_FLAG[@]}" \
  -d interfacehub.net -d "*.interfacehub.net"

echo "Issuing dev cert (dev + *.dev)..."
certbot certonly -a dns-multi \
  --dns-multi-credentials="$CRED_FILE" \
  --cert-name dev.interfacehub.net \
  --non-interactive --agree-tos \
  --email "$EMAIL" \
  "${DRY_FLAG[@]}" \
  -d dev.interfacehub.net -d "*.dev.interfacehub.net"

echo ""
echo "Done. Install nginx vhost:"
echo "  sudo bash docs/install-interfacehub-net.sh"
