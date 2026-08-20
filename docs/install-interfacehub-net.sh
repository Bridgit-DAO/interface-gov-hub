#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sudo cp "$ROOT/docs/nginx-interfacehub-net.conf" /etc/nginx/sites-available/interfacehub.net
sudo ln -sf /etc/nginx/sites-available/interfacehub.net /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
echo "interfacehub.net vhost enabled (prod :8000, dev/staging :8001)."
