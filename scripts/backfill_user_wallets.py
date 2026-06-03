#!/usr/bin/env python3
"""Provision custodial Bitcoin badge wallets for all users missing them."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from run import app  # noqa: E402
from extensions import db  # noqa: E402
from models import User  # noqa: E402
from services.custodial_btc_wallet import (  # noqa: E402
    provision_custodial_btc_wallet,
    reprovision_custodial_btc_wallet,
)


def main():
    dry_run = '--dry-run' in sys.argv
    rekey = '--rekey' in sys.argv
    with app.app_context():
        users = User.query.order_by(User.created_at).all()
        created = skipped = errors = 0
        for user in users:
            has_btc = bool((getattr(user, 'bitcoinAddress', None) or '').strip())
            try:
                if dry_run:
                    from services.custodial_btc_wallet import derive_taproot_wallet

                    addr, path, _wif = derive_taproot_wallet(user.id)
                    action = 'rekey ->' if rekey and has_btc else (
                        'would create' if not has_btc else 'would ensure row'
                    )
                    print(f'{action}: {user.username or user.id} -> {addr} ({path})')
                    continue
                if rekey and has_btc:
                    was_created, addr = reprovision_custodial_btc_wallet(user, commit=False)
                else:
                    was_created, addr = provision_custodial_btc_wallet(user, commit=False)
                if was_created:
                    created += 1
                    label = 'rekeyed' if rekey and has_btc else 'created'
                    print(f'{label}: {user.username or user.id} -> {addr}')
                else:
                    skipped += 1
            except Exception as exc:
                errors += 1
                print(f'error: {user.username or user.id}: {exc}')
        if not dry_run:
            db.session.commit()
        print(
            f'\nDone. users={len(users)} created={created} skipped={skipped} errors={errors}'
        )
        if not os.environ.get('GOVHUB_BTC_CUSTODY_MNEMONIC') and not os.environ.get(
            'GOVHUB_BTC_CUSTODY_XPRV'
        ):
            print(
                'Note: using SECRET_KEY-derived dev master. '
                'Set GOVHUB_BTC_CUSTODY_MNEMONIC in production.'
            )


if __name__ == '__main__':
    main()
