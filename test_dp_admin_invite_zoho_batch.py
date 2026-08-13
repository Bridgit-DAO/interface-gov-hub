"""Per-admin Zoho snapshot isolation and DP admin invite send logging."""
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app import app
from extensions import db
from models import User
from models.dp_admin_invite_send import DpAdminInviteSendRecord
from services.dp_admin_invite_store import list_admin_invite_sends, record_admin_invite_send
from services.zoho_mail import (
    admin_contacts_snapshot_path,
    admin_snapshot_key,
    search_meta_layer_contacts,
)
from services.zoho_mail_ingest import build_snapshot


def _unique(prefix: str) -> str:
    return f'{prefix}-{uuid4().hex[:8]}'


def test_admin_snapshot_key_normalizes_email():
    assert admin_snapshot_key('Daveed@Bridgit.io') == 'daveed_at_bridgit.io'


def test_search_meta_layer_contacts_isolated_by_admin(tmp_path, monkeypatch):
    snapshots_dir = tmp_path / 'invite_zoho_snapshots'
    snapshots_dir.mkdir()
    daveed_path = snapshots_dir / 'daveed_at_example.com.json'
    other_path = snapshots_dir / 'other_at_example.com.json'
    daveed_path.write_text(
        json.dumps(
            {
                'owner_email': 'daveed@example.com',
                'exported_at': '2026-01-01T00:00:00+00:00',
                'message_count': 1,
                'contacts': [{'email': 'kevin@example.com', 'name': 'Kevin', 'message_count': 1}],
            },
        ),
        encoding='utf-8',
    )
    other_path.write_text(
        json.dumps(
            {
                'owner_email': 'other@example.com',
                'exported_at': '2026-01-01T00:00:00+00:00',
                'message_count': 1,
                'contacts': [{'email': 'secret@example.com', 'name': 'Secret', 'message_count': 1}],
            },
        ),
        encoding='utf-8',
    )

    monkeypatch.setattr('services.zoho_mail.INSTANCE_DIR', str(tmp_path))
    monkeypatch.setattr('services.zoho_mail.admin_snapshots_dir', lambda: str(snapshots_dir))
    monkeypatch.setattr(
        'services.zoho_mail.admin_contacts_snapshot_path',
        lambda email: str(snapshots_dir / f'{admin_snapshot_key(email)}.json'),
    )
    monkeypatch.delenv('ZOHO_MAIL_REFRESH_TOKEN', raising=False)

    daveed_payload = search_meta_layer_contacts(admin_email='daveed@example.com')
    other_payload = search_meta_layer_contacts(admin_email='other@example.com')

    assert daveed_payload['contacts'][0]['email'] == 'kevin@example.com'
    assert other_payload['contacts'][0]['email'] == 'secret@example.com'
    assert daveed_payload['snapshot_path'] == str(daveed_path)


def test_build_snapshot_writes_owner_and_output(tmp_path):
    eml = tmp_path / 'msg.eml'
    eml.write_text(
        '\n'.join(
            [
                'From: Kevin <kevin@example.com>',
                'To: Daveed <daveed@example.com>',
                'Subject: Meta-layer workshop follow-up',
                'Date: Mon, 2 Jan 2026 12:00:00 +0000',
                '',
                'Thanks for the desirable properties conversation about Gov Hub.',
            ],
        ),
        encoding='utf-8',
    )
    output = tmp_path / 'snapshots' / 'daveed_at_example.com.json'
    payload = build_snapshot(
        input_path=eml,
        owner_email='daveed@example.com',
        output_path=output,
    )
    assert output.is_file()
    assert payload['owner_email'] == 'daveed@example.com'
    assert payload['contacts'][0]['email'] == 'kevin@example.com'


def test_send_records_are_scoped_to_admin(monkeypatch):
    admin_a = f'{_unique("admin-a")}@example.com'
    admin_b = f'{_unique("admin-b")}@example.com'
    monkeypatch.setattr('config.DP_ADMIN_EMAILS', (admin_a, admin_b))

    with app.app_context():
        user_a = User(
            username=_unique('user-a'),
            handle=_unique('user-a'),
            email=admin_a,
            role='user',
        )
        user_b = User(
            username=_unique('user-b'),
            handle=_unique('user-b'),
            email=admin_b,
            role='user',
        )
        db.session.add_all([user_a, user_b])
        db.session.commit()

        try:
            record_admin_invite_send(
                admin={'id': user_a.id, 'email': user_a.email},
                recipient_email='kevin@example.com',
                recipient_name='Kevin',
                workgroup_ids=['wg-1'],
                body='Hello Kevin',
                status='sent',
                source='zoho_batch',
            )
            record_admin_invite_send(
                admin={'id': user_b.id, 'email': user_b.email},
                recipient_email='secret@example.com',
                recipient_name='Secret',
                workgroup_ids=['wg-2'],
                body='Hello Secret',
                status='sent',
                source='manual',
            )

            rows_a = list_admin_invite_sends({'id': user_a.id, 'email': user_a.email})
            rows_b = list_admin_invite_sends({'id': user_b.id, 'email': user_b.email})

            assert len(rows_a) == 1
            assert rows_a[0]['recipient_email'] == 'kevin@example.com'
            assert rows_a[0]['draft_hash']
            assert rows_a[0]['source'] == 'zoho_batch'
            assert len(rows_b) == 1
            assert rows_b[0]['recipient_email'] == 'secret@example.com'
        finally:
            DpAdminInviteSendRecord.query.filter(
                DpAdminInviteSendRecord.admin_id.in_([user_a.id, user_b.id]),
            ).delete(synchronize_session=False)
            db.session.delete(user_a)
            db.session.delete(user_b)
            db.session.commit()
