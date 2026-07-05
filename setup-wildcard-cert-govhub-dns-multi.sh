#!/bin/bash
# RECOMMENDED for govhub.live when DNS is on Namecheap (or any non-Cloudflare host).
# Wildcard SSL via certbot-dns-multi + DNS-01.
#
# Domains: govhub.live, *.govhub.live, *.dev.govhub.live
#
# Namecheap: enable API access in dashboard; whitelist this server's public IP for API.
#   Profile → Tools → Namecheap API Access → turn on, add IP whitelist.
# Credentials use your Namecheap username + API key from the same page.
#
# 1) Install plugin (pick what works on your OS):
#    sudo snap install certbot-dns-multi
#    sudo snap set certbot trust-plugin-with-root=ok
#    sudo snap connect certbot:plugin certbot-dns-multi
#    # or: sudo apt install -y certbot python3-certbot-dns-multi
#
# 2) Create /etc/letsencrypt/dns-multi-govhub.ini – example Namecheap:
#    dns_multi_provider = namecheap
#    NAMECHEAP_API_USER = your_username
#    NAMECHEAP_API_KEY = your_api_key
#    (see https://go-acme.github.io/lego/dns/ for env vars per provider)
#
# 3) Run:
#    sudo CERTBOT_EMAIL=you@example.com bash setup-wildcard-cert-govhub-dns-multi.sh
#
# Optional: DRY_RUN=1 for certbot --dry-run

set -e

EMAIL="${CERTBOT_EMAIL:-admin@govhub.live}"
CRED_FILE="${DNS_MULTI_CREDENTIALS:-/etc/letsencrypt/dns-multi-govhub.ini}"
DRY_FLAG=()
if [ -n "$DRY_RUN" ]; then
  DRY_FLAG=(--dry-run)
fi

if [ ! -f "$CRED_FILE" ]; then
    echo "Missing credentials file: $CRED_FILE"
    echo ""
    echo "Example (Namecheap):"
    echo "  sudo tee $CRED_FILE << 'EOF'"
    echo "  dns_multi_provider = namecheap"
    echo "  NAMECHEAP_API_USER = your_username"
    echo "  NAMECHEAP_API_KEY = your_api_key"
    echo "  EOF"
    echo "  sudo chmod 600 $CRED_FILE"
    echo ""
    echo "Then: sudo bash setup-wildcard-cert-govhub-dns-multi.sh"
    echo "Or set DNS_MULTI_CREDENTIALS=/path/to/your.ini"
    exit 1
fi

# Certbot refuses world-readable creds; 600 avoids "Unsafe permissions" warnings.
chmod 600 "$CRED_FILE" 2>/dev/null || true

# Certbot wants: dns_multi_provider = namecheap (ignore Windows CRLF / BOM from nano paste)
if ! tr -d '\r' < "$CRED_FILE" | grep -qiE 'dns_multi_provider[[:space:]]*='; then
    echo "Fix $CRED_FILE: need a line like (no # in front):"
    echo "  dns_multi_provider = namecheap"
    echo "Also: NAMECHEAP_API_USER = ... and NAMECHEAP_API_KEY = ..."
    echo "Debug: sudo tr -d '\\r' < $CRED_FILE | cat -A"
    exit 1
fi

if ! certbot plugins 2>/dev/null | grep -q dns-multi; then
  echo "Installing certbot-dns-multi (if available)..."
  snap install certbot-dns-multi 2>/dev/null || true
  snap set certbot trust-plugin-with-root=ok 2>/dev/null || true
  snap connect certbot:plugin certbot-dns-multi 2>/dev/null || true
  apt-get install -y certbot python3-certbot-dns-multi 2>/dev/null || true
fi

certbot certonly -a dns-multi \
  --dns-multi-credentials="$CRED_FILE" \
  --non-interactive --agree-tos \
  --email "$EMAIL" \
  "${DRY_FLAG[@]}" \
  -d govhub.live \
  -d "*.govhub.live" \
  -d "*.dev.govhub.live"

echo ""
echo "Cert: /etc/letsencrypt/live/govhub.live/"
echo "Reload nginx: sudo nginx -t && sudo systemctl reload nginx"
