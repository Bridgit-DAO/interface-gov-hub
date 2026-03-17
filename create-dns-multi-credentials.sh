#!/bin/bash
# Create /etc/letsencrypt/dns-multi.ini for Hostinger
# Usage: HOSTINGER_API_TOKEN=your_token sudo -E bash create-dns-multi-credentials.sh

if [ -z "$HOSTINGER_API_TOKEN" ]; then
    echo "Set your Hostinger API token:"
    echo "  HOSTINGER_API_TOKEN=your_token sudo -E bash create-dns-multi-credentials.sh"
    echo ""
    echo "Get token: Hostinger hPanel → Advanced → API → Generate token (with DNS permissions)"
    exit 1
fi

sudo tee /etc/letsencrypt/dns-multi.ini << EOF
dns_multi_provider = hostinger
HOSTINGER_API_TOKEN = $HOSTINGER_API_TOKEN
EOF
sudo chmod 600 /etc/letsencrypt/dns-multi.ini
echo "Created /etc/letsencrypt/dns-multi.ini"
echo "Run: sudo certbot certonly -a dns-multi --dns-multi-credentials=/etc/letsencrypt/dns-multi.ini -d themetalayer.org -d \"*.themetalayer.org\""
