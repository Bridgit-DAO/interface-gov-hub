#!/usr/bin/env python3
"""Build a one-time Zoho Mail contacts snapshot from an exported ZIP of EML files."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import INSTANCE_DIR
from services.zoho_mail import admin_contacts_snapshot_path, contacts_snapshot_path, normalize_admin_email
from services.zoho_mail_ingest import (
    build_snapshot,
    prompt_export_password_if_needed,
    resolve_export_password,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--input',
        required=True,
        help='Path to a Zoho export ZIP, a directory of .eml files, or a single .eml file',
    )
    parser.add_argument(
        '--owner',
        default=os.environ.get('ZOHO_MAIL_OWNER_EMAIL', ''),
        help='Your mailbox address (used to exclude self from contacts)',
    )
    parser.add_argument(
        '--password',
        default='',
        help='Zoho export ZIP password (or set ZOHO_MAIL_EXPORT_PASSWORD)',
    )
    parser.add_argument(
        '--output',
        default='',
        help='Output JSON path (default: per-admin snapshot under instance/invite_zoho_snapshots/)',
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    output_raw = (args.output or '').strip()
    owner_email = normalize_admin_email(args.owner or os.environ.get('ZOHO_MAIL_OWNER_EMAIL', ''))
    if output_raw:
        output_path = Path(output_raw).expanduser().resolve()
    elif owner_email:
        output_path = Path(admin_contacts_snapshot_path(owner_email)).resolve()
    else:
        output_path = Path(contacts_snapshot_path()).resolve()

    if not input_path.exists():
        raise SystemExit(f'Input path does not exist: {input_path}')

    password = resolve_export_password(args.password)
    password = prompt_export_password_if_needed([input_path], password)
    if input_path.suffix.lower() == '.zip' and not password:
        from services.zoho_mail_ingest import inspect_export_metadata

        metadata = inspect_export_metadata([input_path])
        if int(metadata.get('encrypted_eml_entries') or 0) > 0:
            raise SystemExit(
                'Encrypted export requires --password, ZOHO_MAIL_EXPORT_PASSWORD, '
                'or an interactive prompt.',
            )

    payload = build_snapshot(
        input_path=input_path,
        owner_email=owner_email,
        output_path=output_path,
        password=password,
    )
    print(
        f'Wrote {len(payload["contacts"])} contacts from {payload["message_count"]} '
        f'meta-layer messages to {output_path}',
    )
    if owner_email:
        print(f'Owner: {owner_email}')
    if INSTANCE_DIR not in output_path.parents and output_path.parent != Path(INSTANCE_DIR):
        print('Set ZOHO_MAIL_CONTACTS_SNAPSHOT if you store the file elsewhere.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
