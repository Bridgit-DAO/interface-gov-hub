#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sudo cp "$ROOT/docs/nginx-hub-themetalayer-org.conf" /etc/nginx/sites-available/hub.themetalayer.org
sudo ln -sf /etc/nginx/sites-available/hub.themetalayer.org /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
echo "hub.themetalayer.org vhost enabled."
