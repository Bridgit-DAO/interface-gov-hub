#!/usr/bin/env bash
# Deploy reader-guide modal animations. Files MUST be real GIF (not JPEG/PNG).
# Pasting GIFs into Cursor chat strips animation — copy .gif files to incoming/ via scp instead.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INCOMING="$ROOT/static/images/reader-guide/incoming"
OUT="$ROOT/static/images/reader-guide"
MANIFEST="$OUT/manifest.json"
ENV="${1:-production}"

require_gif() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "Missing $label: $path" >&2
    exit 1
  fi
  if ! file -b "$path" | grep -qi '^GIF image'; then
    echo "Not a GIF (refusing to deploy): $path" >&2
    echo "  file says: $(file -b "$path")" >&2
    exit 1
  fi
}

comment_src="${COMMENT_GIF:-$INCOMING/comment.gif}"
propose_src="${PROPOSE_GIF:-$INCOMING/propose.gif}"
invite_src="${INVITE_GIF:-$INCOMING/invite.gif}"

require_gif "$comment_src" "comment"
require_gif "$propose_src" "propose"
require_gif "$invite_src" "invite"

comment_hash="$(md5sum "$comment_src" | awk '{print $1}' | cut -c1-8)"
propose_hash="$(md5sum "$propose_src" | awk '{print $1}' | cut -c1-8)"
invite_hash="$(md5sum "$invite_src" | awk '{print $1}' | cut -c1-8)"

comment_name="comment-${comment_hash}.gif"
propose_name="propose-${propose_hash}.gif"
invite_name="invite-${invite_hash}.gif"

cp "$comment_src" "$OUT/$comment_name"
cp "$propose_src" "$OUT/$propose_name"
cp "$invite_src" "$OUT/$invite_name"

python3 - "$MANIFEST" "$comment_name" "$propose_name" "$invite_name" <<'PY'
import json, sys
path, comment, propose, invite = sys.argv[1:5]
with open(path, "w", encoding="utf-8") as f:
    json.dump({"comment": comment, "propose": propose, "invite": invite}, f, indent=2)
    f.write("\n")
PY

bash "$ROOT/scripts/update_build_number.sh" "$ENV"

echo "Deployed reader guide GIFs:"
echo "  comment -> $comment_name"
echo "  propose -> $propose_name"
echo "  invite  -> $invite_name"
echo "Manifest: $MANIFEST"
echo "Restart datatracker.service to pick up BUILD_NUMBER."
