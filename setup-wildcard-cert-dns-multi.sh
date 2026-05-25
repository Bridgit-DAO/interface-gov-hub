#!/bin/bash
# Get wildcard SSL cert - NO manual TXT records.
# Uses certbot-dns-multi: 117+ DNS providers (Vultr, DigitalOcean, Namecheap, etc.)
#
# 1. Install: sudo snap install certbot-dns-multi
#    sudo snap set certbot trust-plugin-with-root=ok
#    sudo snap connect certbot:plugin certbot-dns-multi
#
# 2. Create /etc/letsencrypt/dns-multi.ini with your provider:
#
#    Hostinger:
#    ---
#    dns_multi_provider = hostinger
#    HOSTINGER_API_TOKEN = your_api_token
#    ---
#
#    Vultr:
#    ---
#    dns_multi_provider = vultr
#    VULTR_API_KEY = your_vultr_api_key
#    ---
#
#    DigitalOcean:
#    ---
#    dns_multi_provider = digitalocean
#    DO_AUTH_TOKEN = your_do_token
#    ---
#
#    Namecheap:
#    ---
#    dns_multi_provider = namecheap
#    NAMECHEAP_API_USER = your_username
#    NAMECHEAP_API_KEY = your_api_key
#    ---
#
#    Full list: https://go-acme.github.io/lego/dns/
#
# 3. Run: sudo bash setup-wildcard-cert-dns-multi.sh

set -e

CRED_FILE="/etc/letsencrypt/dns-multi.ini"

if [ ! -f "$CRED_FILE" ]; then
    echo "Create $CRED_FILE first. Example for Hostinger:"
    echo ""
    echo "  sudo tee $CRED_FILE << 'EOF'"
    echo "  dns_multi_provider = hostinger"
    echo "  HOSTINGER_API_TOKEN = your_api_token"
    echo "  EOF"
    echo "  sudo chmod 600 $CRED_FILE"
    echo ""
    echo "Other providers: vultr, digitalocean, namecheap, porkbun, etc."
    echo "See: https://go-acme.github.io/lego/dns/"
    exit 1
fi

# Install certbot-dns-multi if not present
if ! certbot plugins 2>/dev/null | grep -q dns-multi; then
    echo "Installing certbot-dns-multi..."
    sudo snap install certbot-dns-multi 2>/dev/null || sudo apt install -y certbot python3-certbot-dns-multi 2>/dev/null || pip install certbot-dns-multi
    sudo snap set certbot trust-plugin-with-root=ok 2>/dev/null || true
    sudo snap connect certbot:plugin certbot-dns-multi 2>/dev/null || true
fi

certbot certonly -a dns-multi \
  --dns-multi-credentials="$CRED_FILE" \
  --non-interactive --agree-tos \
  --email "${CERTBOT_EMAIL:-admin@themetalayer.org}" \
  -d themetalayer.org -d "*.themetalayer.org"

echo ""
echo "Done. Run: sudo bash setup-layer-subdomain-ssl.sh"
