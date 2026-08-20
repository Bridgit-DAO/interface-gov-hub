#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for live in interfacehub.net dev.interfacehub.net; do
  if [ ! -f "/etc/letsencrypt/live/${live}/fullchain.pem" ]; then
    echo "Missing /etc/letsencrypt/live/${live}/fullchain.pem"
    echo "Issue certs first: sudo CLOUDFLARE_API_TOKEN=... bash ${ROOT}/setup-wildcard-cert-interfacehub-net.sh"
    exit 1
  fi
done
sudo cp "$ROOT/docs/nginx-interfacehub-net.conf" /etc/nginx/sites-available/interfacehub.net
sudo ln -sf /etc/nginx/sites-available/interfacehub.net /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
echo "interfacehub.net vhost enabled (prod :8000, dev/staging :8001)."
