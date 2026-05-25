#!/usr/bin/env bash
# Bump INSTANCE_DIR/build_number.txt by 1. Run from deploy/restart scripts — not manually.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV="${1:-production}"

if [ "$ENV" == "development" ]; then
  INST="$SCRIPT_DIR/instance_dev"
else
  INST="$SCRIPT_DIR/instance"
fi

mkdir -p "$INST"
FILE="$INST/build_number.txt"

prev=$(cat "$FILE" 2>/dev/null || echo "73")
case "$prev" in
  ''|*[!0-9]*) prev=73 ;;
esac

next=$((prev + 1))
echo "$next" > "$FILE"
echo "GOV_HUB_BUILD_NUMBER updated: $prev -> $next ($FILE)"
