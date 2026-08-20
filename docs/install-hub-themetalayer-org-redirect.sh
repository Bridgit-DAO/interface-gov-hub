#!/usr/bin/env bash
# Replace hub.themetalayer.org vhost with 301s to interfacehub.net.
# Run only after https://interfacehub.net/ is live and Web3Auth origins are added.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/docs/nginx-hub-themetalayer-org-redirect-to-interfacehub.conf"
DEST=/etc/nginx/sites-available/hub.themetalayer.org
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
if [ ! -f "$SRC" ]; then
  echo "Missing $SRC"
  exit 1
fi
if [ -f "$DEST" ]; then
  sudo cp -a "$DEST" "${DEST}.bak-${STAMP}"
  echo "Backed up $DEST to ${DEST}.bak-${STAMP}"
fi
sudo cp "$SRC" "$DEST"
sudo ln -sf "$DEST" /etc/nginx/sites-enabled/hub.themetalayer.org
sudo nginx -t
sudo systemctl reload nginx
echo "hub.themetalayer.org now 301s to interfacehub.net"
echo "Verify:"
echo "  curl -4 -sI https://hub.themetalayer.org/"
echo "  curl -4 -sI https://canopi.hub.themetalayer.org/"
echo "  curl -4 -sI https://dev.hub.themetalayer.org/"
