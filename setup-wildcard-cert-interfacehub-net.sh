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
# Usage (do not put the token in chat or in a copied command from docs):
#   read -s CLOUDFLARE_API_TOKEN && export CLOUDFLARE_API_TOKEN
#   sudo -E bash setup-wildcard-cert-interfacehub-net.sh
#
# Or write /etc/letsencrypt/dns-multi-interfacehub.ini (mode 600):
#   dns_multi_provider = cloudflare
#   CLOUDFLARE_DNS_API_TOKEN = <token from Cloudflare API Tokens>
# then:
#   sudo bash setup-wildcard-cert-interfacehub-net.sh

set -euo pipefail

EMAIL="${CERTBOT_EMAIL:-admin@interfacehub.net}"
CRED_FILE="${DNS_MULTI_CREDENTIALS:-/etc/letsencrypt/dns-multi-interfacehub.ini}"
DEFAULT_CRED="/etc/letsencrypt/dns-multi.ini"
TOKEN="${CLOUDFLARE_API_TOKEN:-}"

if [ -n "$TOKEN" ]; then
    case "$TOKEN" in
      '...'|'paste-real-token-here'|'YOUR_TOKEN'|'your-token'|*' '* )
        echo "CLOUDFLARE_API_TOKEN is a placeholder or contains spaces."
        echo "Create a token: Cloudflare dashboard → profile → API Tokens → Create Token."
        echo "Use the Edit zone DNS template, zone interfacehub.net only."
        echo "Then: read -s CLOUDFLARE_API_TOKEN && export CLOUDFLARE_API_TOKEN && sudo -E bash $0"
        exit 1
        ;;
    esac
    if [ "${#TOKEN}" -lt 32 ]; then
        echo "CLOUDFLARE_API_TOKEN is too short (${#TOKEN} chars). Real tokens are ~40+."
        echo "Do not use Global API Key. Use API Tokens."
        exit 1
    fi
    CRED_FILE="/etc/letsencrypt/dns-multi-interfacehub.ini"
    umask 077
    cat > "$CRED_FILE" << EOF
dns_multi_provider = cloudflare
CLOUDFLARE_DNS_API_TOKEN = ${TOKEN}
EOF
    chmod 600 "$CRED_FILE"
    echo "Wrote $CRED_FILE from CLOUDFLARE_API_TOKEN (${#TOKEN} chars)"
    code=$(curl -sS -o /tmp/cf-zone-check.json -w '%{http_code}' \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Content-Type: application/json" \
      "https://api.cloudflare.com/client/v4/zones?name=interfacehub.net&per_page=1")
    ok=$(python3 -c "import json; d=json.load(open('/tmp/cf-zone-check.json')); print('yes' if d.get('success') and d.get('result') else 'no')" 2>/dev/null || echo no)
    rm -f /tmp/cf-zone-check.json
    if [ "$code" != "200" ] || [ "$ok" != "yes" ]; then
        echo "Cloudflare token cannot read zone interfacehub.net (HTTP ${code})."
        echo "Need API Token with Zone.Zone Read + Zone.DNS Edit on that zone, not Global API Key."
        exit 1
    fi
    echo "Cloudflare zone interfacehub.net is reachable with this token."
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
