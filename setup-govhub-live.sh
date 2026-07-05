#!/usr/bin/env bash
# One-shot: wildcard cert + nginx for govhub.live (mirror themetalayer.org pattern).
#
# Prerequisites (Namecheap DNS):
#   - A record @ -> your server IPv4
#   - A record * -> same IPv4   (required for *.govhub.live)
#
# DNS must be on Cloudflare for the default path, OR use dns-multi + Namecheap API.
#
# Examples:
#   cd /path/to/gov-hub-dev
#
#   # Cloudflare API token with DNS:Edit on zone govhub.live
#   sudo CLOUDFLARE_API_TOKEN='your_token' ./setup-govhub-live.sh all
#
#   # Or credentials file already on disk:
#   #   /etc/letsencrypt/cloudflare-govhub.ini  ->  dns_cloudflare_api_token = ...
#   sudo ./setup-govhub-live.sh all
#
#   # Namecheap / other DNS (lego via certbot-dns-multi):
#   # Create /etc/letsencrypt/dns-multi-govhub.ini (see setup-wildcard-cert-dns-multi.sh)
#   sudo GOVHUB_DNS_PLUGIN=dns-multi ./setup-govhub-live.sh all
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EMAIL="${CERTBOT_EMAIL:-admin@govhub.live}"
CF_FILE="${CLOUDFLARE_GOVHUB_CREDENTIALS:-/etc/letsencrypt/cloudflare-govhub.ini}"
DM_FILE="${DNS_MULTI_CREDENTIALS:-/etc/letsencrypt/dns-multi-govhub.ini}"
NGINX_SRC="${REPO_ROOT}/docs/nginx-govhub-wildcard-ssl.conf"
NGINX_DST="/etc/nginx/sites-available/govhub.live"
EXPECTED_IP="${EXPECTED_SERVER_IP:-}"

TOKEN="${CLOUDFLARE_API_TOKEN:-${CLOUDFLARE_GOVHUB_TOKEN:-}}"

die() { echo "ERROR: $*" >&2; exit 1; }

need_root() {
  [[ "$(id -u)" -eq 0 ]] || die "Run with sudo"
}

check_dns() {
  echo "=== DNS checks ==="
  local apex sub
  apex="$(dig +short govhub.live A @8.8.8.8 | head -1 || true)"
  sub="$(dig +short "probe-$RANDOM.govhub.live" A @8.8.8.8 | head -1 || true)"
  echo "govhub.live A (Google DNS): ${apex:-<empty>}"
  echo "random *.govhub.live A:       ${sub:-<empty> (wildcard A record missing?)}"
  if [[ -n "$EXPECTED_IP" && -n "$apex" && "$apex" != "$EXPECTED_IP" ]]; then
    echo "WARN: govhub.live A ($apex) != EXPECTED_SERVER_IP ($EXPECTED_IP)"
  fi
  if [[ -z "$sub" ]]; then
    echo "WARN: No A record for *.govhub.live – add Host '*' Type A in Namecheap (same IP as @)."
    echo "      Wildcard TLS still works (DNS-01), but subdomains will not reach this server until '*' exists."
  fi
  echo ""
}

cmd_cert_cloudflare() {
  need_root
  apt-get update -qq
  apt-get install -y certbot python3-certbot-dns-cloudflare

  if [[ -n "$TOKEN" ]]; then
    umask 077
    printf 'dns_cloudflare_api_token = %s\n' "$TOKEN" > "$CF_FILE"
    chmod 600 "$CF_FILE"
    echo "Wrote $CF_FILE (from env token)"
  fi
  [[ -f "$CF_FILE" ]] || die "Missing $CF_FILE – set CLOUDFLARE_API_TOKEN or create file with: dns_cloudflare_api_token = ..."

  certbot certonly --dns-cloudflare \
    --dns-cloudflare-credentials "$CF_FILE" \
    --non-interactive --agree-tos \
    --email "$EMAIL" \
    -d govhub.live -d "*.govhub.live"

  echo ""
  echo "Cert OK: /etc/letsencrypt/live/govhub.live/"
}

cmd_cert_dns_multi() {
  need_root
  [[ -f "$DM_FILE" ]] || die "Missing $DM_FILE – see setup-wildcard-cert-dns-multi.sh (namecheap, etc.)"
  certbot certonly -a dns-multi \
    --dns-multi-credentials="$DM_FILE" \
    --non-interactive --agree-tos \
    --email "$EMAIL" \
    -d govhub.live -d "*.govhub.live"
  echo ""
  echo "Cert OK: /etc/letsencrypt/live/govhub.live/"
}

cmd_cert() {
  need_root
  local plugin="${GOVHUB_DNS_PLUGIN:-cloudflare}"
  case "$plugin" in
    cloudflare) cmd_cert_cloudflare ;;
    dns-multi)  cmd_cert_dns_multi ;;
    *) die "Unknown GOVHUB_DNS_PLUGIN=$plugin (use cloudflare or dns-multi)" ;;
  esac
}

cmd_nginx() {
  need_root
  [[ -f "$NGINX_SRC" ]] || die "Missing $NGINX_SRC"
  [[ -f "/etc/letsencrypt/live/govhub.live/fullchain.pem" ]] || die "No cert yet – run: sudo $0 cert"

  cp -a "$NGINX_SRC" "$NGINX_DST"
  ln -sf "$NGINX_DST" /etc/nginx/sites-enabled/govhub.live
  nginx -t
  systemctl reload nginx
  echo ""
  echo "Nginx enabled: $NGINX_DST"
  echo "Test: curl -sI https://govhub.live | head -5"
}

cmd_dry_run_renew() {
  need_root
  certbot renew --dry-run
}

cmd_all() {
  check_dns
  need_root
  if [[ ! -f /etc/letsencrypt/live/govhub.live/fullchain.pem ]]; then
    cmd_cert
  else
    echo "Cert already present at /etc/letsencrypt/live/govhub.live/ – skip cert (delete dir to force re-issue)"
  fi
  cmd_nginx
  echo ""
  echo "=== Suggested: renewal dry-run ==="
  certbot renew --dry-run || true
}

usage() {
  sed -n '2,35p' "$0" | sed 's/^# \{0,1\}//'
}

case "${1:-}" in
  cert)       check_dns; cmd_cert ;;
  nginx)      cmd_nginx ;;
  all)        cmd_all ;;
  check-dns)  check_dns ;;
  renew-test) cmd_dry_run_renew ;;
  ""|help|-h) usage ;;
  *) die "Unknown command: $1 (cert|nginx|all|check-dns|renew-test|help)" ;;
esac
