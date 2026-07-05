#!/usr/bin/env python3
"""
UUID Primary Key Migration (Phase 6 – PLANNING_FULL_PICTURE.md)

Migrates primary keys from int/string to UUID for all major entities.
LARGE MIGRATION – requires maintenance window. Full backup before running.

Execution order (topological):
1. User (int → UUID)
2. Layer (string → UUID)
3. Submission (string → UUID)
4. Cluster, Role, Claim, Badge, Guild, etc.
5. Vote, Ballot, VoteEligibilitySnapshot, etc.
6. Remaining tables

Per-table: add id_new (UUID), backfill, update child FKs, drop old PK, rename.
SQLite: uses table recreation (CREATE new, COPY, DROP old, RENAME).

Usage: python migrate_uuid_pk.py [--dry-run] [--db path] [--phase N]
Phases: 1=User, 2=Layer, 3=Submission, 4=Role/Claim/Badge/Cluster/Guild, 5=Vote/Ballot, 6=Rest
        all=run all phases (default)
"""
import os
import sys
import shutil
import sqlite3
from datetime import datetime
from uuid import uuid4


def get_db_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    instance = os.path.join(script_dir, 'instance_dev')
    return os.path.join(instance, 'datatracker_dev.db')


def run_migration(db_path, dry_run=False, phase='all'):
    import sqlite3

    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False

    backup_path = f"{db_path}.backup_pre_uuid_pk_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if not dry_run:
        shutil.copy2(db_path, backup_path)
        print(f"✅ Backed up to {backup_path}")
    else:
        print(f"[DRY RUN] Would backup to {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    cursor = conn.cursor()

    # Mappings: old_id -> new_uuid (populated as we migrate)
    user_map = {}
    layer_map = {}
    submission_map = {}
    role_map = {}
    claim_map = {}
    cluster_map = {}
    guild_map = {}
    vote_map = {}

    def table_exists(name):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return cursor.fetchone() is not None

    def get_columns(table):
        cursor.execute(f"PRAGMA table_info({table})")
        return cursor.fetchall()

    def pk_is_uuid(table):
        return _pk_is_uuid(cursor, table)

    def get_create_sql(table):
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
        row = cursor.fetchone()
        return row[0] if row else None

    try:
        if dry_run:
            print("[DRY RUN] Would migrate User, Layer, Submission, Role, Claim, Badge, Vote, etc. to UUID PKs")
            conn.close()
            return True

        # ========== Phase 1: User (int → UUID) ==========
        if phase in ('all', '1'):
            print("\n--- Phase 1: User ---")
            if not table_exists('user'):
                print("⏭️  user table does not exist")
            elif pk_is_uuid('user'):
                print("⏭️  user already has UUID PK, skipping")
            else:
                cols = get_columns('user')
                col_names = [c[1] for c in cols]
                # Create user_new with id as TEXT (UUID)
                col_defs = []
                for c in cols:
                    n = _quote_col(c[1])
                    if c[1] == 'id':
                        col_defs.append(f"{n} TEXT PRIMARY KEY")
                    else:
                        col_defs.append(f"{n} {_sqlite_type(c[2])}")
                cursor.execute("CREATE TABLE user_new (" + ", ".join(col_defs) + ")")
                conn.commit()

                cursor.execute("SELECT * FROM user")
                rows = cursor.fetchall()
                for row in rows:
                    old_id = row[0]
                    new_id = str(uuid4())
                    user_map[old_id] = new_id
                    new_row = (new_id,) + row[1:]
                    placeholders = ",".join("?" * len(new_row))
                    cursor.execute(f"INSERT INTO user_new VALUES ({placeholders})", new_row)
                conn.commit()

                cursor.execute("DROP TABLE user")
                cursor.execute("ALTER TABLE user_new RENAME TO user")
                conn.commit()
                print(f"✅ User: migrated {len(rows)} rows to UUID PK")

                # Update all tables with user_id FK
                # layer's initiator_id/approved_by_id updated when we recreate layer in Phase 2
                user_fk_tables = [
                    ('inscription_order', 'user_id'),
                    ('session', 'user_id'),
                    ('wallet_binding', 'user_id'),
                    ('coordinator_request', 'user_id'),
                    ('workgroup_member_request', 'user_id'),
                    ('hypothesis_account', 'user_id'),
                    ('layer_member', 'user_id'),
                    ('layer_member', 'referred_by_id'),
                    ('layer_admin', 'user_id'),
                    ('waitlist_entry', 'user_id'),
                    ('waitlist_entry', 'referred_by_id'),
                    ('email_unsubscribe', 'user_id'),
                    ('working_group', 'coordinator_id'),
                    ('working_group', 'approved_by_id'),
                    ('guild_membership', 'user_id'),
                    ('guild_invitation', 'inviter_id'),
                    ('guild_invitation', 'invitee_id'),
                    ('cluster', 'created_by_id'),
                    ('role', 'created_by_id'),
                    ('role', 'approved_by_id'),
                    ('role_image', 'promoted_by_id'),
                    ('role_image', 'submitted_by_id'),
                    ('role_image_vote', 'user_id'),
                    ('one_time_badge', 'created_by_id'),
                    ('claim', 'claimant_id'),
                    ('claim', 'approved_by_id'),
                    ('badge', 'claimant_id'),
                    ('badge', 'requested_by_id'),
                    ('badge', 'approved_by_id'),
                    ('status_change', 'changed_by_id'),
                    ('event_log', 'actor_user_id'),
                    ('artifact', 'creator_user_id'),
                    ('quest', 'creator_user_id'),
                    ('quest_submission', 'submitter_user_id'),
                    ('quest_submission', 'reviewed_by_user_id'),
                    ('monument', 'steward_user_id'),
                    ('vote', 'created_by_id'),
                    ('vote_eligibility_snapshot', 'person_id'),
                    ('vote_candidate', 'user_id'),
                    ('ballot', 'person_id'),
                    ('working_group_member', 'user_id'),
                ]
                for tbl, fk_col in user_fk_tables:
                    if not table_exists(tbl):
                        continue
                    _update_fk_column(cursor, conn, tbl, fk_col, user_map, 'INTEGER')
                print("✅ Updated user_id FKs in child tables")

        # ========== Phase 2: Layer (string → UUID) ==========
        if phase in ('all', '2'):
            print("\n--- Phase 2: Layer ---")
            if not table_exists('layer'):
                print("⏭️  layer table does not exist")
            elif pk_is_uuid('layer'):
                print("⏭️  layer already has UUID PK, skipping")
            else:
                cols = get_columns('layer')
                col_defs = []
                for c in cols:
                    n = _quote_col(c[1])
                    if c[1] == 'id':
                        col_defs.append(f"{n} TEXT PRIMARY KEY")
                    elif c[1] in ('initiator_id', 'approved_by_id'):
                        col_defs.append(f"{n} TEXT")
                    elif c[1] == 'superseded_by_id':
                        col_defs.append(f"{n} TEXT")
                    else:
                        col_defs.append(f"{n} {_sqlite_type(c[2])}")
                cursor.execute("CREATE TABLE layer_new (" + ", ".join(col_defs) + ")")
                conn.commit()

                col_names = [c[1] for c in cols]
                cursor.execute("SELECT * FROM layer")
                rows = cursor.fetchall()
                for row in rows:
                    old_id = row[0]
                    new_id = str(uuid4())
                    layer_map[old_id] = new_id
                    # Map initiator_id, approved_by_id, superseded_by_id
                    row_list = list(row)
                    idx_init = next((i for i, c in enumerate(cols) if c[1] == 'initiator_id'), None)
                    idx_approv = next((i for i, c in enumerate(cols) if c[1] == 'approved_by_id'), None)
                    idx_super = next((i for i, c in enumerate(cols) if c[1] == 'superseded_by_id'), None)
                    row_list[0] = new_id
                    if idx_init is not None and row[idx_init]:
                        row_list[idx_init] = user_map.get(row[idx_init], row[idx_init])
                    if idx_approv is not None and row[idx_approv]:
                        row_list[idx_approv] = user_map.get(row[idx_approv], row[idx_approv])
                    if idx_super is not None and row[idx_super]:
                        row_list[idx_super] = layer_map.get(row[idx_super], row[idx_super])
                    placeholders = ",".join("?" * len(row_list))
                    cursor.execute(f"INSERT INTO layer_new VALUES ({placeholders})", tuple(row_list))
                conn.commit()

                # Fix superseded_by_id - second pass (layer_map now has all)
                cursor.execute("SELECT id, superseded_by_id FROM layer_new WHERE superseded_by_id IS NOT NULL")
                for rid, super_old in cursor.fetchall():
                    super_new = layer_map.get(super_old)
                    if super_new:
                        cursor.execute("UPDATE layer_new SET superseded_by_id=? WHERE id=?", (super_new, rid))
                conn.commit()

                cursor.execute("DROP TABLE layer")
                cursor.execute("ALTER TABLE layer_new RENAME TO layer")
                conn.commit()
                print(f"✅ Layer: migrated {len(rows)} rows to UUID PK")

                layer_fk_tables = [
                    ('submission', 'layer_id'),
                    ('inscription_order', 'layer_id'),
                    ('badge_cycle', 'layer_id'),
                    ('one_time_badge', 'layer_id'),
                    ('layer_member', 'layer_id'),
                    ('layer_admin', 'layer_id'),
                    ('waitlist', 'layer_id'),
                    ('email_unsubscribe', 'layer_id'),
                    ('working_group', 'layer_id'),
                    ('cluster', 'layer_id'),
                    ('role', 'layer_id'),
                    ('claim', 'layer_id'),
                    ('badge', 'layer_id'),
                    ('event_log', 'layer_id'),
                    ('artifact', 'layer_id'),
                    ('quest', 'layer_id'),
                    ('monument', 'layer_id'),
                    ('vote', 'layer_id'),
                ]
                for tbl, fk_col in layer_fk_tables:
                    if not table_exists(tbl):
                        continue
                    _update_fk_column(cursor, conn, tbl, fk_col, layer_map, 'TEXT')
                print("✅ Updated layer_id FKs in child tables")

        # ========== Phase 3: Submission (string → UUID) ==========
        if phase in ('all', '3'):
            print("\n--- Phase 3: Submission ---")
            if not table_exists('submission'):
                print("⏭️  submission table does not exist")
            elif pk_is_uuid('submission'):
                print("⏭️  submission already has UUID PK, skipping")
            else:
                cols = get_columns('submission')
                col_defs = []
                for c in cols:
                    n = _quote_col(c[1])
                    if c[1] == 'id':
                        col_defs.append(f"{n} TEXT PRIMARY KEY")
                    elif c[1] == 'layer_id':
                        col_defs.append(f"{n} TEXT")
                    else:
                        col_defs.append(f"{n} {_sqlite_type(c[2])}")
                cursor.execute("CREATE TABLE submission_new (" + ", ".join(col_defs) + ")")
                conn.commit()

                cursor.execute("SELECT * FROM submission")
                rows = cursor.fetchall()
                for row in rows:
                    old_id = row[0]
                    new_id = str(uuid4())
                    submission_map[old_id] = new_id
                    row_list = list(row)
                    row_list[0] = new_id
                    idx_layer = next((i for i, c in enumerate(cols) if c[1] == 'layer_id'), None)
                    if idx_layer is not None and row[idx_layer]:
                        row_list[idx_layer] = layer_map.get(row[idx_layer], row[idx_layer])
                    placeholders = ",".join("?" * len(row_list))
                    cursor.execute(f"INSERT INTO submission_new VALUES ({placeholders})", tuple(row_list))
                conn.commit()

                cursor.execute("DROP TABLE submission")
                cursor.execute("ALTER TABLE submission_new RENAME TO submission")
                conn.commit()
                print(f"✅ Submission: migrated {len(rows)} rows to UUID PK")

                submission_fk_tables = [('vote', 'submission_id')]
                for tbl, fk_col in submission_fk_tables:
                    if not table_exists(tbl):
                        continue
                    _update_fk_column(cursor, conn, tbl, fk_col, submission_map, 'TEXT')
                print("✅ Updated submission_id FKs")

        # ========== Phase 4: Cluster, Role, Claim, Badge, Guild ==========
        if phase in ('all', '4'):
            print("\n--- Phase 4: Cluster, Role, Claim, Badge, Guild ---")
            # Cluster
            if table_exists('cluster'):
                _migrate_string_pk_table(cursor, conn, 'cluster', 'cluster', cluster_map,
                    fk_updates=[('role', 'cluster_id')], parent_maps={'layer_id': layer_map, 'created_by_id': user_map})
            # Role
            if table_exists('role'):
                _migrate_string_pk_table(cursor, conn, 'role', 'role', role_map,
                    fk_updates=[('claim', 'role_id'), ('badge', 'role_id'), ('vote', 'role_id')],
                    parent_maps={'layer_id': layer_map, 'cluster_id': cluster_map, 'created_by_id': user_map, 'approved_by_id': user_map})
            # Claim
            if table_exists('claim'):
                _migrate_string_pk_table(cursor, conn, 'claim', 'claim', claim_map,
                    fk_updates=[('badge', 'claim_id')],
                    parent_maps={'layer_id': layer_map, 'role_id': role_map, 'claimant_id': user_map, 'approved_by_id': user_map})
            # Badge
            if table_exists('badge'):
                _migrate_string_pk_table(cursor, conn, 'badge', 'badge', {},
                    fk_updates=[],
                    parent_maps={'layer_id': layer_map, 'claim_id': claim_map, 'role_id': role_map, 'claimant_id': user_map, 'requested_by_id': user_map, 'approved_by_id': user_map})
            # Guild
            if table_exists('guild'):
                _migrate_string_pk_table(cursor, conn, 'guild', 'guild', guild_map,
                    fk_updates=[('guild_membership', 'guild_id'), ('guild_invitation', 'guild_id')],
                    parent_maps={'initiator_id': user_map})

        # ========== Phase 5: Vote, Ballot, etc. ==========
        if phase in ('all', '5'):
            print("\n--- Phase 5: Vote, Ballot ---")
            if table_exists('vote'):
                _migrate_int_pk_table(cursor, conn, 'vote', 'vote', vote_map,
                    fk_updates=[('vote_eligibility_snapshot', 'vote_id'), ('vote_candidate', 'vote_id'), ('ballot', 'vote_id')],
                    parent_maps={'layer_id': layer_map, 'submission_id': submission_map, 'created_by_id': user_map, 'role_id': role_map})
            if table_exists('ballot'):
                _migrate_int_pk_table(cursor, conn, 'ballot', 'ballot', {},
                    fk_updates=[],
                    parent_maps={'vote_id': vote_map, 'person_id': user_map})

        # ========== Phase 6: Remaining integer-PK tables ==========
        waitlist_map = {}
        if phase in ('all', '6'):
            print("\n--- Phase 6: Waitlist, Comment, VoteEligibilitySnapshot, VoteCandidate, etc. ---")
            if table_exists('waitlist'):
                _migrate_int_pk_table(cursor, conn, 'waitlist', 'waitlist', waitlist_map,
                    fk_updates=[('waitlist_entry', 'waitlist_id'), ('waitlist_email_signup', 'waitlist_id'), ('waitlist_milestone', 'waitlist_id')],
                    parent_maps={'layer_id': layer_map})
            if table_exists('comment'):
                cursor.execute("SELECT id FROM comment")
                comment_map = {r[0]: str(uuid4()) for r in cursor.fetchall()}
                _migrate_int_pk_table(cursor, conn, 'comment', 'comment', comment_map,
                    fk_updates=[], parent_maps={'parent_id': comment_map})
            if table_exists('vote_eligibility_snapshot'):
                _migrate_int_pk_table(cursor, conn, 'vote_eligibility_snapshot', 'vote_eligibility_snapshot', {},
                    fk_updates=[], parent_maps={'vote_id': vote_map, 'person_id': user_map})
            if table_exists('vote_candidate'):
                _migrate_int_pk_table(cursor, conn, 'vote_candidate', 'vote_candidate', {},
                    fk_updates=[], parent_maps={'vote_id': vote_map, 'user_id': user_map})
            quest_map = {}
            role_image_map = {}
            if table_exists('role_image'):
                _migrate_string_pk_table(cursor, conn, 'role_image', 'role_image', role_image_map,
                    fk_updates=[('role_image_vote', 'image_id')],
                    parent_maps={'layer_id': layer_map, 'promoted_by_id': user_map, 'submitted_by_id': user_map})
            if table_exists('quest'):
                _migrate_int_pk_table(cursor, conn, 'quest', 'quest', quest_map,
                    fk_updates=[('quest_submission', 'quest_id')],
                    parent_maps={'layer_id': layer_map, 'creator_user_id': user_map})
            for tbl, pmap in [
                ('layer_member', {'layer_id': layer_map, 'user_id': user_map, 'referred_by_id': user_map}),
                ('layer_admin', {'layer_id': layer_map, 'user_id': user_map}),
                ('working_group', {'layer_id': layer_map, 'coordinator_id': user_map, 'approved_by_id': user_map}),
                ('guild_membership', {'guild_id': guild_map, 'user_id': user_map}),
                ('guild_invitation', {'guild_id': guild_map, 'inviter_id': user_map, 'invitee_id': user_map}),
                ('coordinator_request', {'user_id': user_map}),
                ('workgroup_member_request', {'user_id': user_map}),
                ('hypothesis_account', {'user_id': user_map}),
                ('document_history', {}),
                ('role_image_vote', {'image_id': role_image_map, 'user_id': user_map}),
                ('event_log', {'layer_id': layer_map, 'actor_user_id': user_map}),
                ('quest_submission', {'quest_id': quest_map, 'submitter_user_id': user_map, 'reviewed_by_user_id': user_map}),
                ('monument', {'layer_id': layer_map, 'steward_user_id': user_map}),
                ('working_group_member', {'user_id': user_map}),
                ('working_group_chair', {'user_id': user_map}),
                ('artifact_relation', {'created_by_user_id': user_map}),
            ]:
                if table_exists(tbl):
                    try:
                        _migrate_int_pk_table(cursor, conn, tbl, tbl, {}, fk_updates=[], parent_maps=pmap)
                    except Exception as ex:
                        print(f"   ⚠️  {tbl}: {ex}")

        # ========== Phase 7: String(50) PK tables → UUID ==========
        badge_skin_map = {}
        badge_cycle_map = {}
        if phase in ('all', '6', '7'):
            print("\n--- Phase 7: BadgeSkin, BadgeCycle, OneTimeBadge, GuildInvitation, StatusChange ---")
            if table_exists('badge_skin'):
                _migrate_string_pk_table(cursor, conn, 'badge_skin', 'badge_skin', badge_skin_map,
                    fk_updates=[('role', 'badge_skin_id'), ('working_group', 'badge_skin_id'), ('one_time_badge', 'badge_skin_id')],
                    parent_maps={})
            if table_exists('badge_cycle'):
                _migrate_string_pk_table(cursor, conn, 'badge_cycle', 'badge_cycle', badge_cycle_map,
                    fk_updates=[('role_image', 'cycle_id')],
                    parent_maps={'layer_id': layer_map})
            if table_exists('one_time_badge'):
                _migrate_string_pk_table(cursor, conn, 'one_time_badge', 'one_time_badge', {},
                    fk_updates=[],
                    parent_maps={'layer_id': layer_map, 'badge_skin_id': badge_skin_map, 'created_by_id': user_map})
            if table_exists('guild_invitation'):
                _migrate_string_pk_table(cursor, conn, 'guild_invitation', 'guild_invitation', {},
                    fk_updates=[],
                    parent_maps={'guild_id': guild_map, 'inviter_id': user_map, 'invitee_id': user_map})
            if table_exists('status_change'):
                _migrate_string_pk_table(cursor, conn, 'status_change', 'status_change', {},
                    fk_updates=[],
                    parent_maps={'changed_by_id': user_map})

        conn.execute("PRAGMA foreign_keys = ON")
        print("\n✅ UUID PK migration complete")
        return True

    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


SQL_RESERVED = frozenset({'group', 'order', 'index', 'table', 'select', 'from', 'where', 'key'})


def _pk_is_uuid(cursor, table):
    """Return True if table's id column is already TEXT (UUID)."""
    cols = cursor.execute(f"PRAGMA table_info({table})").fetchall()
    for c in cols:
        if c[1] == 'id' and (c[5] if len(c) > 5 else 0) == 1:
            return (c[2] or '').upper() == 'TEXT'
    return False


def _quote_col(name):
    """Quote column name if reserved word."""
    return f'"{name}"' if name.lower() in SQL_RESERVED else name

def _sqlite_type(affinity):
    """Map SQLite type affinity to storage class."""
    if affinity == 0: return "TEXT"   # NONE
    if affinity == 1: return "INTEGER"
    if affinity == 2: return "INTEGER"
    if affinity == 3: return "INTEGER"
    if affinity == 4: return "REAL"
    if affinity == 5: return "NUMERIC"
    return "TEXT"


def _update_fk_column(cursor, conn, table, fk_col, id_map, old_type):
    """Recreate table with FK column as TEXT (UUID)."""
    try:
        cursor.execute(f"PRAGMA table_info({table})")
        cols = cursor.fetchall()
        col_names = [c[1] for c in cols]
        fk_idx = col_names.index(fk_col) if fk_col in col_names else None
        if fk_idx is None:
            return

        # Build new schema: fk_col becomes TEXT (quote reserved words)
        col_defs = []
        for c in cols:
            name, typ = c[1], c[2]
            pk = c[5] if len(c) > 5 else 0
            n = _quote_col(name)
            if name == fk_col:
                col_defs.append(f"{n} TEXT" + (" PRIMARY KEY" if pk else ""))
            else:
                col_defs.append(f"{n} {_sqlite_type(typ)}" + (" PRIMARY KEY" if pk else ""))

        cursor.execute(f"CREATE TABLE {table}_fk_new (" + ", ".join(col_defs) + ")")
        conn.commit()

        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        for row in rows:
            row_list = list(row)
            old_fk = row[fk_idx]
            if old_fk is not None and old_fk in id_map:
                row_list[fk_idx] = id_map[old_fk]
            placeholders = ",".join("?" * len(row_list))
            cursor.execute(f"INSERT INTO {table}_fk_new VALUES ({placeholders})", tuple(row_list))
        conn.commit()

        cursor.execute(f"DROP TABLE {table}")
        cursor.execute(f"ALTER TABLE {table}_fk_new RENAME TO {table}")
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"   ⚠️  {table}.{fk_col}: {e}")


def _migrate_string_pk_table(cursor, conn, table, map_name, id_map, fk_updates, parent_maps):
    """Migrate a string-PK table to UUID. parent_maps: {col: map} for FK columns to remap."""
    if _pk_is_uuid(cursor, table):
        print(f"   ⏭️  {table} already has UUID PK, skipping")
        return
    cols = cursor.execute(f"PRAGMA table_info({table})").fetchall()
    col_defs = []
    for c in cols:
        n = _quote_col(c[1])
        if c[1] == 'id':
            col_defs.append(f"{n} TEXT PRIMARY KEY")
        elif c[1] in parent_maps:
            col_defs.append(f"{n} TEXT")
        else:
            col_defs.append(f"{n} {_sqlite_type(c[2])}")
    cursor.execute(f"CREATE TABLE {table}_new (" + ", ".join(col_defs) + ")")
    conn.commit()

    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()
    for row in rows:
        old_id = row[0]
        new_id = str(uuid4())
        id_map[old_id] = new_id
        row_list = list(row)
        row_list[0] = new_id
        for i, c in enumerate(cols):
            if c[1] in parent_maps and row[i] and row[i] in parent_maps[c[1]]:
                row_list[i] = parent_maps[c[1]][row[i]]
        placeholders = ",".join("?" * len(row_list))
        cursor.execute(f"INSERT INTO {table}_new VALUES ({placeholders})", tuple(row_list))
    conn.commit()

    cursor.execute(f"DROP TABLE {table}")
    cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
    conn.commit()
    print(f"✅ {table}: migrated {len(rows)} rows")

    for tbl, fk_col in fk_updates:
        try:
            cursor.execute(f"PRAGMA table_info({tbl})")
            tc = cursor.fetchall()
            if not any(c[1] == fk_col for c in tc):
                continue
            _update_fk_column(cursor, conn, tbl, fk_col, id_map, 'TEXT')
        except sqlite3.OperationalError:
            pass


def _migrate_int_pk_table(cursor, conn, table, map_name, id_map, fk_updates, parent_maps):
    """Migrate an int-PK table to UUID. id_map can be pre-populated (e.g. for self-ref FKs)."""
    if _pk_is_uuid(cursor, table):
        print(f"   ⏭️  {table} already has UUID PK, skipping")
        return
    cols = cursor.execute(f"PRAGMA table_info({table})").fetchall()
    col_defs = []
    for c in cols:
        n = _quote_col(c[1])
        if c[1] == 'id':
            col_defs.append(f"{n} TEXT PRIMARY KEY")
        elif c[1] in parent_maps:
            col_defs.append(f"{n} TEXT")
        else:
            col_defs.append(f"{n} {_sqlite_type(c[2])}")
    cursor.execute(f"CREATE TABLE {table}_new (" + ", ".join(col_defs) + ")")
    conn.commit()

    cursor.execute(f"SELECT * FROM {table}")
    rows = cursor.fetchall()
    for row in rows:
        old_id = row[0]
        new_id = id_map.get(old_id) or str(uuid4())
        id_map[old_id] = new_id
        row_list = list(row)
        row_list[0] = new_id
        for i, c in enumerate(cols):
            if c[1] in parent_maps and row[i] is not None and row[i] in parent_maps[c[1]]:
                row_list[i] = parent_maps[c[1]][row[i]]
        placeholders = ",".join("?" * len(row_list))
        cursor.execute(f"INSERT INTO {table}_new VALUES ({placeholders})", tuple(row_list))
    conn.commit()

    cursor.execute(f"DROP TABLE {table}")
    cursor.execute(f"ALTER TABLE {table}_new RENAME TO {table}")
    conn.commit()
    print(f"✅ {table}: migrated {len(rows)} rows")

    for tbl, fk_col in fk_updates:
        try:
            _update_fk_column(cursor, conn, tbl, fk_col, id_map, 'INTEGER')
        except sqlite3.OperationalError:
            pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description='UUID PK migration (maintenance window)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--db', default=None)
    parser.add_argument('--phase', default='all', choices=['all', '1', '2', '3', '4', '5', '6', '7'])
    args = parser.parse_args()
    db_path = args.db or get_db_path()
    ok = run_migration(db_path, dry_run=args.dry_run, phase=args.phase)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
