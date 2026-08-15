#!/usr/bin/env python3
"""Analyze or prune Zoho Mail export ZIPs before building invite snapshots."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import INSTANCE_DIR
from services.zoho_mail import admin_contacts_snapshot_path, normalize_admin_email
from services.zoho_mail_ingest import (
    _DEFAULT_INCLUDE_FOLDERS,
    analyze_export,
    build_snapshot,
    inspect_export_metadata,
    iter_export_messages,
    prune_snapshot_payload,
    prompt_export_password_if_needed,
    resolve_export_password,
    resolve_export_inputs,
)


def _format_bytes(num: int) -> str:
    if num >= 1024 ** 3:
        return f'{num / (1024 ** 3):.2f} GB'
    if num >= 1024 ** 2:
        return f'{num / (1024 ** 2):.1f} MB'
    if num >= 1024:
        return f'{num / 1024:.1f} KB'
    return f'{num} B'


def _print_metadata_report(report: dict) -> None:
    print('Zoho export metadata')
    print(f"- Zip files: {report.get('zip_count', 0)}")
    print(f"- Corrupt zips: {len(report.get('corrupt_zips') or [])}")
    print(f"- EML entries: {report.get('total_eml_entries', 0):,}")
    print(f"- Encrypted EML entries: {report.get('encrypted_eml_entries', 0):,}")
    compressed = sum(int(row.get('compressed_bytes') or 0) for row in report.get('zips') or [])
    print(f"- Compressed total: {_format_bytes(compressed)}")
    print('- Top folders:')
    for folder, count in list((report.get('folder_counts') or {}).items())[:8]:
        print(f'  - {folder}: {count:,}')
    if report.get('corrupt_zips'):
        print('- Corrupt files:')
        for row in report['corrupt_zips']:
            print(f"  - {row['path']}: {row['error']}")


def _print_analysis_report(report: dict) -> None:
    _print_metadata_report(report)
    if report.get('password_error'):
        print()
        if report.get('password_rejected'):
            print('Export password rejected.')
        else:
            print('Password required before content analysis.')
        print(report['password_error'])
        return

    print('\nFiltered analysis')
    print(f"- Owner: {report.get('owner_email') or '(none)'}")
    print(f"- Include folders: {', '.join(report.get('include_folders') or []) or '(all)'}")
    if report.get('sample_per_zip'):
        print(f"- Sample per zip: {report['sample_per_zip']}")
    print(f"- Scanned EML: {report.get('scanned_eml', 0):,}")
    print(f"- Matched EML: {report.get('matched_eml', 0):,}")
    print(f"- Keyword matches: {report.get('matched_by_keyword', 0):,}")
    print(f"- Allowlist-only matches: {report.get('matched_by_allowlist_only', 0):,}")
    print(f"- Estimated snapshot contacts: {report.get('estimated_snapshot_contacts', 0)}")

    top_contacts = report.get('top_contacts') or []
    if top_contacts:
        print('\nTop contacts preview')
        for row in top_contacts[:10]:
            subjects = '; '.join((row.get('subjects') or [])[:2])
            print(
                f"- {row.get('name') or row.get('email')} <{row.get('email')}> "
                f"msgs={row.get('message_count')} last={row.get('last_contact') or 'unknown'} "
                f"subjects={subjects[:120]}",
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--input',
        action='append',
        required=True,
        help='ZIP path, directory, or glob. Repeat for multiple inputs.',
    )
    parser.add_argument(
        '--owner',
        default='daveed@bridgit.io',
        help='Mailbox owner email (excluded from contacts)',
    )
    parser.add_argument(
        '--password',
        default='',
        help='Zoho export ZIP password (or set ZOHO_MAIL_EXPORT_PASSWORD)',
    )
    parser.add_argument(
        '--metadata-only',
        action='store_true',
        help='Inspect zip structure only; do not decrypt or parse EML content',
    )
    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Report match stats and top contacts without writing a snapshot',
    )
    parser.add_argument(
        '--prune',
        action='store_true',
        help='Build a slim per-admin snapshot JSON from filtered messages',
    )
    parser.add_argument(
        '--output',
        default='',
        help='Snapshot output path (default: instance_dev/invite_zoho_snapshots/{admin_key}.json)',
    )
    parser.add_argument(
        '--include-folders',
        default=','.join(_DEFAULT_INCLUDE_FOLDERS),
        help='Comma-separated top-level folders to scan (default skips NewsLetter bulk)',
    )
    parser.add_argument(
        '--all-folders',
        action='store_true',
        help='Scan every folder, including NewsLetter',
    )
    parser.add_argument(
        '--sample-per-zip',
        type=int,
        default=0,
        help='Only parse the first N EML files per zip (quick preview)',
    )
    parser.add_argument(
        '--max-contacts',
        type=int,
        default=0,
        help='Cap contacts written to snapshot JSON (0 = all relevant contacts)',
    )
    args = parser.parse_args()

    input_paths = resolve_export_inputs(args.input)
    if not input_paths:
        raise SystemExit('No input paths resolved.')

    owner_email = normalize_admin_email(args.owner)
    password = resolve_export_password(args.password)
    include_folders = None if args.all_folders else [
        folder.strip() for folder in args.include_folders.split(',') if folder.strip()
    ]

    needs_password = (
        not args.metadata_only
        and (args.analyze_only or args.prune or (not args.prune and not args.analyze_only))
    )
    if needs_password:
        password = prompt_export_password_if_needed(input_paths, password)

    if args.metadata_only or (not args.prune and not args.analyze_only):
        report = inspect_export_metadata(input_paths)
        _print_metadata_report(report)
        if args.metadata_only:
            return 0

    if args.analyze_only or (not args.prune and not args.metadata_only):
        print(
            f'Analyzing {len(input_paths)} input(s)… (progress on stderr)',
            flush=True,
        )
        report = analyze_export(
            input_paths,
            password=password,
            owner_email=owner_email,
            include_folders=include_folders,
            sample_per_zip=args.sample_per_zip,
            report_progress=True,
        )
        _print_analysis_report(report)
        if args.analyze_only:
            return 0

    if args.prune:
        if not password:
            raise SystemExit(
                'Prune requires the Zoho export password via --password or ZOHO_MAIL_EXPORT_PASSWORD.',
            )
        print(
            f'Pruning {len(input_paths)} input(s)… (progress on stderr)',
            flush=True,
        )
        messages = list(
            iter_export_messages(
                input_paths,
                password=password,
                include_folders=include_folders,
                sample_per_zip=args.sample_per_zip,
                report_progress=True,
            ),
        )
        payload = prune_snapshot_payload(
            messages,
            owner_email=owner_email,
            max_contacts=args.max_contacts,
        )
        output_raw = (args.output or '').strip()
        output_path = (
            Path(output_raw).expanduser().resolve()
            if output_raw
            else Path(admin_contacts_snapshot_path(owner_email)).resolve()
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        print(
            f"Wrote {len(payload['contacts'])} contacts from {payload['message_count']} "
            f"matched messages to {output_path}",
        )
        if INSTANCE_DIR not in output_path.parents and output_path.parent != Path(INSTANCE_DIR):
            print('Set ZOHO_MAIL_CONTACTS_SNAPSHOT if you store the file elsewhere.')
        return 0

    if len(input_paths) == 1 and input_paths[0].suffix.lower() == '.zip':
        output_raw = (args.output or '').strip()
        output_path = (
            Path(output_raw).expanduser().resolve()
            if output_raw
            else Path(admin_contacts_snapshot_path(owner_email)).resolve()
        )
        payload = build_snapshot(
            input_path=input_paths[0],
            owner_email=owner_email,
            output_path=output_path,
            password=password,
            include_folders=include_folders,
            max_contacts=args.max_contacts,
        )
        print(
            f"Wrote {len(payload['contacts'])} contacts from {payload['message_count']} "
            f"matched messages to {output_path}",
        )
        return 0

    raise SystemExit('Use --analyze-only, --metadata-only, or --prune for multi-input runs.')


if __name__ == '__main__':
    raise SystemExit(main())
