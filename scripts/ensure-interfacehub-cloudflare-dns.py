#!/usr/bin/env python3
"""Upsert Cloudflare A records for interfacehub.net (DNS-only / grey cloud).

Requires CLOUDFLARE_API_TOKEN with Zone:DNS:Edit on interfacehub.net.
Does not print the token.

Records:
  @, www, *, dev, *.dev, staging  →  216.238.91.120
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ZONE_NAME = "interfacehub.net"
VPS_IPV4 = os.environ.get("INTERFACEHUB_IPV4", "216.238.91.120")
API = "https://api.cloudflare.com/client/v4"

RECORDS = (
    ("@", "@"),
    ("www", "www"),
    ("*", "*"),
    ("dev", "dev"),
    ("*.dev", "*.dev"),
    ("staging", "staging"),
)


def _request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()[:400]
        raise SystemExit(f"Cloudflare HTTP {exc.code} {path}: {detail}") from exc


def main() -> int:
    token = (os.environ.get("CLOUDFLARE_API_TOKEN") or "").strip()
    if not token:
        print("CLOUDFLARE_API_TOKEN is not set; skip DNS upsert.", file=sys.stderr)
        print("Create these A records (grey cloud) to 216.238.91.120:", file=sys.stderr)
        for _label, name in RECORDS:
            print(f"  A  {name}  {VPS_IPV4}", file=sys.stderr)
        return 2

    listed = _request(token, "GET", "/zones?" + urllib.parse.urlencode({"name": ZONE_NAME, "per_page": 5}))
    zones = listed.get("result") or []
    if not zones:
        print(f"Zone {ZONE_NAME} not found on this Cloudflare token.", file=sys.stderr)
        print("Confirm the zone is Active in Cloudflare (nameservers already CF).", file=sys.stderr)
        return 1
    zone = zones[0]
    zone_id = zone["id"]
    print(f"Zone {ZONE_NAME} status={zone.get('status')} paused={zone.get('paused')}")

    existing = _request(
        token,
        "GET",
        f"/zones/{zone_id}/dns_records?" + urllib.parse.urlencode({"per_page": 100, "type": "A"}),
    )
    by_name: dict[str, dict] = {}
    for rec in existing.get("result") or []:
        by_name[rec.get("name", "")] = rec

    wanted_fqdn = {
        "@": ZONE_NAME,
        "www": f"www.{ZONE_NAME}",
        "*": f"*.{ZONE_NAME}",
        "dev": f"dev.{ZONE_NAME}",
        "*.dev": f"*.dev.{ZONE_NAME}",
        "staging": f"staging.{ZONE_NAME}",
    }

    for key, dns_name in RECORDS:
        fqdn = wanted_fqdn[key]
        payload = {
            "type": "A",
            "name": dns_name,
            "content": VPS_IPV4,
            "ttl": 1,
            "proxied": False,
        }
        current = by_name.get(fqdn)
        if current and current.get("content") == VPS_IPV4 and current.get("proxied") is False:
            print(f"ok  A {dns_name} already {VPS_IPV4} (DNS-only)")
            continue
        if current:
            _request(token, "PUT", f"/zones/{zone_id}/dns_records/{current['id']}", payload)
            print(f"upd A {dns_name} → {VPS_IPV4} (DNS-only)")
        else:
            _request(token, "POST", f"/zones/{zone_id}/dns_records", payload)
            print(f"add A {dns_name} → {VPS_IPV4} (DNS-only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
