#!/bin/bash
# Enable HTTPS for layer subdomains (overweb.themetalayer.org, the-overweb.themetalayer.org, etc.)
# Run with: sudo bash setup-layer-subdomain-ssl.sh

set -e

echo "=== Layer Subdomain SSL Setup ==="

# Check if wildcard cert exists
if [ -f /etc/letsencrypt/live/themetalayer.org/fullchain.pem ]; then
    echo "✓ Wildcard cert exists"
else
    echo "✗ Wildcard cert NOT found. You need to create it first."
    echo ""
    echo "Option A - Cloudflare DNS (recommended):"
    echo "  sudo apt install certbot python3-certbot-dns-cloudflare -y"
    echo "  sudo tee /etc/letsencrypt/cloudflare.ini << 'EOF'"
    echo "  dns_cloudflare_api_token = YOUR_CLOUDFLARE_API_TOKEN"
    echo "  EOF"
    echo "  sudo chmod 600 /etc/letsencrypt/cloudflare.ini"
    echo "  sudo certbot certonly --dns-cloudflare \\"
    echo "    --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \\"
    echo "    -d themetalayer.org -d \"*.themetalayer.org\""
    echo ""
    echo "Option B - Manual DNS:"
    echo "  sudo certbot certonly --manual --preferred-challenges=dns \\"
    echo "    -d themetalayer.org -d \"*.themetalayer.org\""
    echo ""
    exit 1
fi

# Install SSL-enabled nginx config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/docs/nginx-wildcard-ssl.conf" /etc/nginx/sites-available/themetalayer.org
echo "✓ Updated nginx config"

# Test and reload
nginx -t && systemctl reload nginx
echo "✓ Nginx reloaded"

echo ""
echo "Done. Try: https://the-overweb.themetalayer.org"
