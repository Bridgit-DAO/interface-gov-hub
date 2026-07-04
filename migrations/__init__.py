"""Database migrations. Run from init_db() with app context."""
import sqlite3
from datetime import datetime
from uuid import uuid4

from werkzeug.security import generate_password_hash

from extensions import db
from models import User, Submission


def migrate_user_profile_columns(app):
    """Add banner_image, headline, bio, social_links, referral_code to user table."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(user)")
        user_columns = [c[1] for c in cursor.fetchall()]
        for col, col_type in [
            ('banner_image', 'VARCHAR(500)'),
            ('headline', 'VARCHAR(200)'),
            ('bio', 'TEXT'),
            ('social_links', 'TEXT'),
            ('referral_code', 'VARCHAR(50)'),
        ]:
            if col not in user_columns:
                cursor.execute(f"ALTER TABLE user ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"✅ Added {col} column to user table")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error adding profile columns: {e}")


def migrate_public_id(app):
    """Add public_id to tables that need UUID-style URLs. Backfill and index."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        tables = ['user', 'layer', 'submission', 'badge', 'vote', 'claim', 'role', 'working_group', 'role_image', 'cluster', 'badge_cycle', 'one_time_badge', 'guild']
        for table_name in tables:
            try:
                cursor.execute(f"SELECT public_id FROM {table_name} LIMIT 1")
                print(f"✅ public_id already exists on {table_name}")
            except sqlite3.OperationalError:
                print(f"🔄 Adding public_id to {table_name}...")
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN public_id VARCHAR(36)")
                conn.commit()
                cursor.execute(f"SELECT id FROM {table_name} WHERE public_id IS NULL")
                rows = cursor.fetchall()
                for row in rows:
                    cursor.execute(f"UPDATE {table_name} SET public_id = ? WHERE id = ?", (str(uuid4()), row[0]))
                conn.commit()
                print(f"✅ Backfilled {len(rows)} rows in {table_name}")
                try:
                    cursor.execute(f"CREATE UNIQUE INDEX idx_{table_name}_public_id ON {table_name}(public_id)")
                    conn.commit()
                except sqlite3.OperationalError:
                    pass
        conn.close()
    except Exception as e:
        print(f"⚠️  Error adding public_id columns: {e}")


def migrate_entity_image_url(app):
    """Add image_url to layer, waitlist, working_group, guild."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for table in ['layer', 'waitlist', 'working_group', 'guild']:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [c[1] for c in cursor.fetchall()]
                if 'image_url' not in cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN image_url VARCHAR(500)")
                    conn.commit()
                    print(f"✅ Added image_url column to {table} table")
            except sqlite3.OperationalError:
                pass  # Table may not exist yet
        conn.close()
    except Exception as e:
        print(f"⚠️  Error adding image_url columns: {e}")


def migrate_badge_system(app):
    """Create badge_skin, badge_cycle, one_time_badge; add badge columns to role, working_group, role_image; seed default skins."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS badge_skin (
                id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                slug VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                layout_spec TEXT,
                preview_image_url VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS badge_cycle (
                id VARCHAR(50) PRIMARY KEY,
                entity_type VARCHAR(20) NOT NULL,
                entity_id VARCHAR(100) NOT NULL,
                layer_id VARCHAR(50) NOT NULL,
                first_submission_at TIMESTAMP,
                submission_ends_at TIMESTAMP,
                voting_starts_at TIMESTAMP,
                voting_ends_at TIMESTAMP,
                status VARCHAR(20) DEFAULT 'submission',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS one_time_badge (
                id VARCHAR(50) PRIMARY KEY,
                layer_id VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                earliest_start DATE NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                submission_days INTEGER NOT NULL DEFAULT 14,
                delay_days INTEGER DEFAULT 2,
                voting_days INTEGER NOT NULL DEFAULT 7,
                voting_regular BOOLEAN DEFAULT 1,
                voting_time_weighted BOOLEAN DEFAULT 0,
                voting_quadratic BOOLEAN DEFAULT 0,
                badge_skin_id VARCHAR(50),
                status VARCHAR(20) DEFAULT 'draft',
                first_submission_at TIMESTAMP,
                submission_ends_at TIMESTAMP,
                voting_starts_at TIMESTAMP,
                voting_ends_at TIMESTAMP,
                created_by_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        conn.commit()

        role_badge_cols = {
            'badge_submission_days': 'INTEGER DEFAULT 14',
            'badge_voting_days': 'INTEGER DEFAULT 7',
            'badge_delay_days': 'INTEGER DEFAULT 2',
            'badge_earliest_start': 'DATE',
            'badge_cycle_spacing_days': 'INTEGER DEFAULT 365',
            'badge_end_date': 'DATE',
            'badge_end_at_next_closing': 'BOOLEAN DEFAULT 0',
            'badge_voting_regular': 'BOOLEAN DEFAULT 1',
            'badge_voting_time_weighted': 'BOOLEAN DEFAULT 0',
            'badge_voting_quadratic': 'BOOLEAN DEFAULT 0',
            'badge_skin_id': 'VARCHAR(50)',
        }
        cursor.execute("PRAGMA table_info(role)")
        role_cols = [c[1] for c in cursor.fetchall()]
        for col, col_type in role_badge_cols.items():
            if col not in role_cols:
                cursor.execute(f"ALTER TABLE role ADD COLUMN {col} {col_type}")
                conn.commit()

        wg_badge_cols = {
            'badge_enabled': 'BOOLEAN DEFAULT 0',
            'badge_submission_days': 'INTEGER',
            'badge_voting_days': 'INTEGER',
            'badge_delay_days': 'INTEGER',
            'badge_earliest_start': 'DATE',
            'badge_cycle_spacing_days': 'INTEGER DEFAULT 365',
            'badge_end_date': 'DATE',
            'badge_end_at_next_closing': 'BOOLEAN DEFAULT 0',
            'badge_voting_regular': 'BOOLEAN DEFAULT 1',
            'badge_voting_time_weighted': 'BOOLEAN DEFAULT 0',
            'badge_voting_quadratic': 'BOOLEAN DEFAULT 0',
            'badge_skin_id': 'VARCHAR(50)',
        }
        cursor.execute("PRAGMA table_info(working_group)")
        wg_cols = [c[1] for c in cursor.fetchall()]
        for col, col_type in wg_badge_cols.items():
            if col not in wg_cols:
                cursor.execute(f"ALTER TABLE working_group ADD COLUMN {col} {col_type}")
                conn.commit()

        cursor.execute("PRAGMA table_info(role_image)")
        ri_cols = [c[1] for c in cursor.fetchall()]
        for col, col_type in [('entity_type', "VARCHAR(20) DEFAULT 'role'"), ('entity_id', 'VARCHAR(100)'), ('cycle_id', 'VARCHAR(50)')]:
            if col not in ri_cols:
                cursor.execute(f"ALTER TABLE role_image ADD COLUMN {col} {col_type}")
                conn.commit()

        cursor.execute("SELECT COUNT(*) FROM badge_skin")
        if cursor.fetchone()[0] == 0:
            default_skins = [
                ('skin_compact', 'Compact', 'compact', 'Image top, title and claimant below', '{"regions":[{"id":"image","placement":"top","size":"full"},{"id":"title","placement":"center","font_size":"medium"},{"id":"claimant","placement":"footer","font_size":"small"}]}'),
                ('skin_banner', 'Banner', 'banner', 'Wide image, title overlaid at bottom', '{"regions":[{"id":"image","placement":"background","size":"full"},{"id":"title","placement":"overlay_bottom","font_size":"large"},{"id":"claimant","placement":"overlay_bottom_small","font_size":"small"}]}'),
                ('skin_minimal', 'Minimal', 'minimal', 'Clean circular image with name below', '{"regions":[{"id":"image","placement":"center","size":"circle"},{"id":"title","placement":"below_image","font_size":"medium"},{"id":"claimant","placement":"footer","font_size":"small"}]}'),
                ('skin_card', 'Card', 'card', 'Full card with image, title, description row', '{"regions":[{"id":"image","placement":"left","size":"square_sm"},{"id":"title","placement":"right_top","font_size":"large"},{"id":"claimant","placement":"right_bottom","font_size":"small"}]}'),
            ]
            for sid, name, slug, desc, spec in default_skins:
                cursor.execute("INSERT INTO badge_skin (id, name, slug, description, layout_spec) VALUES (?,?,?,?,?)", (sid, name, slug, desc, spec))
            conn.commit()
            print(f"✅ Seeded {len(default_skins)} default badge skins")

        conn.close()
    except Exception as e:
        print(f"⚠️  Error adding badge system columns: {e}")


def migrate_workgroup_links(app):
    """Add optional external_url and document_draft_name to working_group."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        link_cols = {
            'external_url': 'VARCHAR(500)',
            'document_draft_name': 'VARCHAR(255)',
        }
        cursor.execute("PRAGMA table_info(working_group)")
        wg_cols = [c[1] for c in cursor.fetchall()]
        for col, col_type in link_cols.items():
            if col not in wg_cols:
                cursor.execute(f"ALTER TABLE working_group ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"✅ Added working_group.{col}")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error adding workgroup link columns: {e}")


def migrate_coordinator_and_member_requests(app):
    """Ensure coordinator_request, workgroup_member_request tables exist; add user_id to working_group_chair and working_group_member."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(working_group_chair)")
        wgc_columns = [c[1] for c in cursor.fetchall()]
        if 'user_id' not in wgc_columns:
            cursor.execute("ALTER TABLE working_group_chair ADD COLUMN user_id INTEGER REFERENCES user(id)")
            conn.commit()
        cursor.execute("PRAGMA table_info(working_group_member)")
        wgm_columns = [c[1] for c in cursor.fetchall()]
        if 'user_id' not in wgm_columns:
            cursor.execute("ALTER TABLE working_group_member ADD COLUMN user_id INTEGER REFERENCES user(id)")
            conn.commit()
            cursor.execute("SELECT id, group_acronym, user_name FROM working_group_member")
            for row in cursor.fetchall():
                mid, gac, uname = row
                cursor.execute("SELECT id FROM user WHERE username = ? OR name = ? OR displayName = ? OR oauthName = ? LIMIT 1", (uname, uname, uname, uname))
                urow = cursor.fetchone()
                if urow:
                    cursor.execute("UPDATE working_group_member SET user_id = ? WHERE id = ?", (urow[0], mid))
            conn.commit()
        conn.close()
    except Exception as e:
        print(f"Migration coordinator/member_requests: {e}")


def migrate_inscription_order_and_config(app):
    """Create inscription_order, site_config tables; add inscription_order_id to submission, offer_tier_pricing to project."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inscription_order (
                id VARCHAR(36) PRIMARY KEY,
                user_id INTEGER,
                layer_id VARCHAR(50),
                status VARCHAR(30) DEFAULT 'pending_payment',
                content_text TEXT,
                content_filename VARCHAR(255),
                page_count INTEGER DEFAULT 1,
                image_count INTEGER DEFAULT 0,
                phone_number VARCHAR(30),
                country_code VARCHAR(5),
                phone_verified BOOLEAN DEFAULT 0,
                tier INTEGER DEFAULT 1,
                base_price_usd NUMERIC(10,2),
                discount_pct INTEGER DEFAULT 0,
                final_price_usd NUMERIC(10,2),
                stripe_payment_intent_id VARCHAR(100),
                stripe_client_secret VARCHAR(200),
                btc_taproot_address VARCHAR(255),
                unisat_order_id VARCHAR(255),
                inscription_id VARCHAR(255),
                acknowledged_timing BOOLEAN DEFAULT 0,
                notify_when_ready BOOLEAN DEFAULT 0,
                title VARCHAR(255),
                authors TEXT,
                abstract TEXT,
                workgroup VARCHAR(50),
                created_at DATETIME,
                paid_at DATETIME,
                completed_at DATETIME
            )
        """)
        conn.commit()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_config (
                key VARCHAR(100) PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()

        defaults = [
            ('inscribe_price_per_page', '10.00'),
            ('inscribe_price_per_image', '5.00'),
            ('inscribe_tier2_discount', '30'),
            ('inscribe_tier3_discount', '50'),
        ]
        for k, v in defaults:
            cursor.execute("INSERT OR IGNORE INTO site_config (key, value) VALUES (?, ?)", (k, v))
        conn.commit()

        cursor.execute("PRAGMA table_info(submission)")
        sub_cols = [c[1] for c in cursor.fetchall()]
        if 'inscription_order_id' not in sub_cols:
            cursor.execute("ALTER TABLE submission ADD COLUMN inscription_order_id VARCHAR(36)")
            conn.commit()
            print("✅ Added inscription_order_id to submission")

        cursor.execute("PRAGMA table_info(layer)")
        layer_cols = [c[1] for c in cursor.fetchall()]
        if 'offer_tier_pricing' not in layer_cols:
            cursor.execute("ALTER TABLE layer ADD COLUMN offer_tier_pricing BOOLEAN DEFAULT 0")
            conn.commit()
            print("✅ Added offer_tier_pricing to layer")

        for col, col_type in [('meta_domain_inscription_id', 'VARCHAR(255)'), ('meta_domain', 'TEXT'), ('about_content', 'TEXT'), ('carousel_config', 'TEXT')]:
            cursor.execute("PRAGMA table_info(layer)")
            current_cols = [c[1] for c in cursor.fetchall()]
            if col not in current_cols:
                cursor.execute(f"ALTER TABLE layer ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"✅ Added {col} to layer")

        conn.close()
        print("✅ Inscription order and site config migration complete")
    except Exception as e:
        print(f"⚠️  Error in inscription migration: {e}")


def migrate_vote_ballot_order_seed(app):
    """Add ballot_order_seed to vote table for randomized candidate order."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(vote)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'ballot_order_seed' not in cols:
            cursor.execute("ALTER TABLE vote ADD COLUMN ballot_order_seed INTEGER")
            conn.commit()
            print("✅ Added ballot_order_seed to vote")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in vote ballot_order_seed migration: {e}")


def migrate_vote_artifact_id(app):
    """Add artifact_id to vote table; add layer_id if missing (project→layer rename)."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(vote)")
        cols = [c[1] for c in cursor.fetchall()]

        for col, col_type in [
            ('artifact_id', 'VARCHAR(36)'),
            ('layer_id', 'VARCHAR(36)'),
            ('vote_type', 'VARCHAR(20)'),
            ('role_id', 'VARCHAR(36)'),
            ('seats', 'INTEGER'),
        ]:
            if col not in cols:
                cursor.execute(f"ALTER TABLE vote ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"✅ Added {col} to vote table")

        # Backfill layer_id from project_id (project→layer rename)
        cursor.execute("PRAGMA table_info(vote)")
        cols_after = [c[1] for c in cursor.fetchall()]
        if 'project_id' in cols_after and 'layer_id' in cols_after:
            cursor.execute("UPDATE vote SET layer_id = project_id WHERE (layer_id IS NULL OR layer_id = '') AND project_id IS NOT NULL")
            conn.commit()
            print("✅ Backfilled layer_id from project_id")

        conn.close()
    except Exception as e:
        print(f"⚠️  Error adding artifact_id/layer_id to vote: {e}")


def migrate_artifact_spec_fields(app):
    """Add artifact_specification.md fields to artifact table."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(artifact)")
        cols = [c[1] for c in cursor.fetchall()]
        for col, col_type in [
            ('artifact_subtype', 'VARCHAR(50)'),
            ('body', 'TEXT'),
            ('source_language', 'VARCHAR(20)'),
            ('current_language', 'VARCHAR(20)'),
            ('updated_at', 'DATETIME'),
        ]:
            if col not in cols:
                cursor.execute(f"ALTER TABLE artifact ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"✅ Added {col} to artifact")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in artifact spec migration: {e}")


def migrate_submission_draft_name_backfill(app):
    """Backfill draft_name for submissions with NULL (post-UUID migration)."""
    try:
        subs = Submission.query.filter(Submission.draft_name.is_(None)).all()
        for s in subs:
            s.draft_name = s.id
        if subs:
            db.session.commit()
            print(f"✅ Backfilled draft_name for {len(subs)} submission(s)")
    except Exception as e:
        print(f"⚠️  Error in draft_name backfill: {e}")


def migrate_submission_layer_id(app):
    """Add layer_id and artifact_id to submission table."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(submission)")
        cols = [c[1] for c in cursor.fetchall()]
        for col, col_type in [('layer_id', 'VARCHAR(36)'), ('artifact_id', 'VARCHAR(36)')]:
            if col not in cols:
                cursor.execute(f"ALTER TABLE submission ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"✅ Added {col} to submission table")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error adding layer_id/artifact_id to submission: {e}")


def migrate_ordinals_support(app):
    """Add ordinals support columns to existing submission table"""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(submission)")
        columns = [col[1] for col in cursor.fetchall()]

        ordinals_columns = {
            'sourceType': ('TEXT', 'file'),
            'ordinalId': ('TEXT', None),
            'ordinalContentUrl': ('TEXT', None),
            'ordinalContentType': ('TEXT', None),
            'inscriptionNumber': ('INTEGER', None),
            'blockHeight': ('INTEGER', None),
            'inscriptionTimestamp': ('DATETIME', None),
            'doc_type': ('TEXT', 'draft')
        }

        added_columns = []
        for col_name, (col_type, default_value) in ordinals_columns.items():
            if col_name not in columns:
                if default_value:
                    cursor.execute(f"ALTER TABLE submission ADD COLUMN {col_name} {col_type} DEFAULT '{default_value}'")
                else:
                    cursor.execute(f"ALTER TABLE submission ADD COLUMN {col_name} {col_type}")
                added_columns.append(col_name)

        cursor.execute(
            "SELECT s.id, s.ml_number, s.prefix_code, lp.prefix "
            "FROM submission s "
            "LEFT JOIN layer_prefix lp ON lp.layer_id = s.layer_id AND lp.is_default = 1 "
            "WHERE s.ml_number IS NOT NULL"
        )
        submissions = cursor.fetchall()
        migrated_count = 0
        for sub_id, ml_num, prefix_code, layer_default_prefix in submissions:
            if not ml_num:
                continue
            if ml_num.startswith('ML-Draft-') or ml_num.startswith('ML-RFC-'):
                continue
            # Respect per-draft and per-layer prefixes: if a non-ML prefix is
            # in play (either prefix_code on the row or the layer's default),
            # leave the row's ml_number alone. The legacy migration below only
            # applied to rows that didn't yet know about non-ML prefixes.
            effective_prefix = (prefix_code or layer_default_prefix or '').strip().upper()
            if effective_prefix and effective_prefix != 'ML':
                continue
            try:
                num_part = ml_num.split('-')[-1]
                new_ml_num = f"ML-Draft-{num_part}"
                cursor.execute("UPDATE submission SET ml_number = ? WHERE id = ?", (new_ml_num, sub_id))
                migrated_count += 1
            except (ValueError, IndexError):
                pass

        conn.commit()
        conn.close()

        if added_columns:
            print(f"✅ Added columns to submission table: {', '.join(added_columns)}")
        else:
            print("✅ All columns already exist in submission table")

        if migrated_count > 0:
            print(f"✅ Migrated {migrated_count} ML numbers to new format (ML-Draft-XXX)")
    except Exception as e:
        print(f"⚠️  Error migrating ordinals support: {e}")


def migrate_bridge(app):
    """Create bridge and bridge_session tables."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bridge (
                id TEXT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                source_url TEXT NOT NULL,
                source_content_type VARCHAR(20) NOT NULL,
                source_text_excerpt TEXT,
                source_media_url TEXT,
                source_media_alt VARCHAR(500),
                source_name VARCHAR(255),
                source_page_title VARCHAR(500),
                source_selector VARCHAR(500),
                source_video_timestamp INTEGER,
                target_url TEXT NOT NULL,
                target_content_type VARCHAR(20) NOT NULL,
                target_text_excerpt TEXT,
                target_media_url TEXT,
                target_media_alt VARCHAR(500),
                target_name VARCHAR(255),
                target_page_title VARCHAR(500),
                target_selector VARCHAR(500),
                target_video_timestamp INTEGER,
                relationship VARCHAR(50) NOT NULL,
                explanation TEXT,
                created_by TEXT REFERENCES user(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                inscription_id VARCHAR(255),
                inscribed_at DATETIME
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_source_url ON bridge(source_url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_target_url ON bridge(target_url)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_inscription ON bridge(inscription_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bridge_session (
                id TEXT PRIMARY KEY,
                user_id TEXT REFERENCES user(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                source_content TEXT,
                target_content TEXT,
                status VARCHAR(20) DEFAULT 'open'
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_session_user ON bridge_session(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bridge_session_status ON bridge_session(status)")

        conn.commit()
        conn.close()
        print("✅ Bridge and bridge_session tables created")
    except Exception as e:
        print(f"⚠️  Error creating bridge tables: {e}")


def migrate_civic_mason(app):
    """Civic Mason: add civic_mason_eligible to Role; recreate brick table (global); add brick_message."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Add civic_mason_eligible to role
        cursor.execute("PRAGMA table_info(role)")
        role_cols = [c[1] for c in cursor.fetchall()]
        if 'civic_mason_eligible' not in role_cols:
            cursor.execute("ALTER TABLE role ADD COLUMN civic_mason_eligible INTEGER DEFAULT 0")
            conn.commit()
            print("✅ Added civic_mason_eligible to role")

        # 2. Create brick_message table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='brick_message'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE brick_message (
                    id TEXT PRIMARY KEY,
                    brick_id TEXT NOT NULL REFERENCES brick(id),
                    user_id TEXT REFERENCES user(id),
                    message VARCHAR(200) NOT NULL DEFAULT '',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX idx_brick_message_brick_id ON brick_message(brick_id)")
            conn.commit()
            print("✅ Created brick_message table")

        # 3. Recreate brick table if it has old schema (layer_id)
        cursor.execute("PRAGMA table_info(brick)")
        brick_cols = {c[1]: c for c in cursor.fetchall()}
        if brick_cols and 'layer_id' in brick_cols:
            cursor.execute("SELECT COUNT(*) FROM brick")
            count = cursor.fetchone()[0]
            cursor.execute("""
                CREATE TABLE brick_new (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES user(id),
                    grid_x REAL NOT NULL,
                    grid_y REAL NOT NULL,
                    artifact_id TEXT REFERENCES artifact(id),
                    badge_id TEXT REFERENCES badge(id),
                    year INTEGER NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(grid_x, grid_y)
                )
            """)
            if count > 0:
                cursor.execute("""
                    INSERT INTO brick_new (id, user_id, grid_x, grid_y, artifact_id, badge_id, year, created_at)
                    SELECT id, user_id, CAST(grid_x AS REAL), CAST(grid_y AS REAL), artifact_id, badge_id,
                           CAST(strftime('%Y', COALESCE(created_at, datetime('now'))) AS INTEGER),
                           COALESCE(created_at, datetime('now'))
                    FROM brick
                """)
                cursor.execute("SELECT id, message FROM brick WHERE message IS NOT NULL AND message != ''")
                for row in cursor.fetchall():
                    import uuid
                    msg_id = str(uuid.uuid4())
                    cursor.execute(
                        "INSERT INTO brick_message (id, brick_id, user_id, message, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
                        (msg_id, row[0], None, (row[1] or '')[:200])
                    )
            cursor.execute("DROP TABLE brick")
            cursor.execute("ALTER TABLE brick_new RENAME TO brick")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_brick_grid ON brick(grid_x, grid_y)")
            conn.commit()
            print("✅ Migrated brick table to global schema")
        elif brick_cols and 'year' not in brick_cols:
            cursor.execute("ALTER TABLE brick ADD COLUMN year INTEGER")
            cursor.execute("UPDATE brick SET year = CAST(strftime('%Y', COALESCE(created_at, datetime('now'))) AS INTEGER) WHERE year IS NULL")
            conn.commit()
            print("✅ Added year to brick table")

        conn.close()
    except Exception as e:
        print(f"⚠️  Error in civic mason migration: {e}")


def migrate_civic_mason_seed_daveed(app):
    """Seed Civic Mason eligibility for daveed@bridgit.io: role + claim + issued badge."""
    with app.app_context():
        import sqlite3
        from uuid import uuid4
        from datetime import datetime

        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM user WHERE email = ?", ('daveed@bridgit.io',))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            print("⚠️  migrate_civic_mason_seed_daveed: user daveed@bridgit.io not found")
            return

        user_id = user_row[0]

        cursor.execute("SELECT id FROM layer LIMIT 1")
        layer_row = cursor.fetchone()
        if not layer_row:
            cursor.execute("SELECT id FROM project LIMIT 1")
            layer_row = cursor.fetchone()
        if not layer_row:
            conn.close()
            print("⚠️  migrate_civic_mason_seed_daveed: no layer/project found")
            return

        layer_id = layer_row[0]

        role_col = 'layer_id' if any(c[1] == 'layer_id' for c in cursor.execute("PRAGMA table_info(role)").fetchall()) else 'project_id'

        cursor.execute(f"SELECT id FROM role WHERE {role_col} = ? AND (civic_mason_eligible = 1 OR civic_mason_eligible = ?)", (layer_id, True))
        role_row = cursor.fetchone()
        if role_row:
            role_id = role_row[0]
        else:
            cursor.execute(f"SELECT id FROM role WHERE {role_col} = ? LIMIT 1", (layer_id,))
            role_row = cursor.fetchone()
            if role_row:
                role_id = role_row[0]
                cursor.execute("UPDATE role SET civic_mason_eligible = 1 WHERE id = ?", (role_id,))
                conn.commit()
                print("✅ Set civic_mason_eligible=True on existing role")
            else:
                role_id = str(uuid4())
                cursor.execute(f"""
                    INSERT INTO role (id, {role_col}, role_slug, title_guild, title_operational, description, civic_mason_eligible, created_by_id)
                    VALUES (?, ?, 'civic-mason', 'Civic Mason', 'Civic Mason', 'Eligible to place bricks on the Civic Mason wall.', 1, ?)
                """, (role_id, layer_id, user_id))
                conn.commit()
                print("✅ Created Civic Mason role")

        claim_col = 'layer_id' if any(c[1] == 'layer_id' for c in cursor.execute("PRAGMA table_info(claim)").fetchall()) else 'project_id'
        cursor.execute("SELECT id FROM claim WHERE claimant_id = ? AND role_id = ? AND status = 'active'", (user_id, role_id))
        claim_row = cursor.fetchone()
        if claim_row:
            claim_id = claim_row[0]
        else:
            claim_id = str(uuid4())
            cursor.execute(f"INSERT INTO claim (id, {claim_col}, role_id, claimant_id, status) VALUES (?, ?, ?, ?, 'active')",
                           (claim_id, layer_id, role_id, user_id))
            conn.commit()
            print("✅ Created claim for daveed@bridgit.io")

        badge_layer_col = 'layer_id' if any(c[1] == 'layer_id' for c in cursor.execute("PRAGMA table_info(badge)").fetchall()) else 'project_id'
        cursor.execute("SELECT id FROM badge WHERE claimant_id = ? AND role_id = ? AND status = 'issued'", (user_id, role_id))
        if cursor.fetchone():
            print("✅ daveed@bridgit.io already has Civic Mason badge")
        else:
            badge_id = str(uuid4())
            cursor.execute(f"""
                INSERT INTO badge (id, {badge_layer_col}, claim_id, role_id, claimant_id, requested_by_id, status, approved_by_id, approved_at)
                VALUES (?, ?, ?, ?, ?, ?, 'issued', ?, ?)
            """, (badge_id, layer_id, claim_id, role_id, user_id, user_id, user_id, datetime.utcnow().isoformat()))
            conn.commit()
            print("✅ Issued Civic Mason badge to daveed@bridgit.io")

        conn.close()


def migrate_user_linked_account(app):
    """Create user_linked_account table for OAuth-connected social accounts."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_linked_account'")
        if cursor.fetchone():
            conn.close()
            return
        cursor.execute("""
            CREATE TABLE user_linked_account (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL REFERENCES user(id),
                provider VARCHAR(50) NOT NULL,
                provider_user_id VARCHAR(255) NOT NULL,
                profile_url VARCHAR(500),
                avatar_url VARCHAR(500),
                display_name VARCHAR(200),
                access_token TEXT,
                token_expires_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, provider),
                UNIQUE(provider, provider_user_id)
            )
        """)
        cursor.execute("CREATE INDEX idx_user_linked_account_user_id ON user_linked_account(user_id)")
        cursor.execute("CREATE INDEX idx_user_linked_account_provider ON user_linked_account(provider)")
        conn.commit()
        conn.close()
        print("✅ Created user_linked_account table")
    except Exception as e:
        print(f"⚠️  Error creating user_linked_account: {e}")


def migrate_knowledge_layer_integration(app):
    """Add knowledge_form, knowledge_scaffold on artifact; collection tables (briefing §5, collections)."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(artifact)")
        cols = [c[1] for c in cursor.fetchall()]
        for col, col_type in [
            ('knowledge_form', 'VARCHAR(30)'),
            ('knowledge_scaffold', 'TEXT'),
        ]:
            if col not in cols:
                cursor.execute(f"ALTER TABLE artifact ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"✅ Added {col} to artifact")
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_artifact_knowledge_form ON artifact(knowledge_form)")
            conn.commit()
        except sqlite3.OperationalError:
            pass

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_collection'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE artifact_collection (
                    id VARCHAR(36) PRIMARY KEY,
                    layer_id VARCHAR(36) NOT NULL REFERENCES layer(id),
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    creator_user_id VARCHAR(36) REFERENCES user(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_collection_layer ON artifact_collection(layer_id)"
            )
            conn.commit()
            print("✅ Created artifact_collection table")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_collection_item'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE artifact_collection_item (
                    id VARCHAR(36) PRIMARY KEY,
                    collection_id VARCHAR(36) NOT NULL REFERENCES artifact_collection(id),
                    artifact_id VARCHAR(36) NOT NULL REFERENCES artifact(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_id, artifact_id)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_aci_collection ON artifact_collection_item(collection_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_aci_artifact ON artifact_collection_item(artifact_id)"
            )
            conn.commit()
            print("✅ Created artifact_collection_item table")

        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_knowledge_layer_integration: {e}")


def migrate_layer_enabled_features(app):
    """Per-layer product feature overrides (JSON on layer.enabled_features)."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(layer)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'enabled_features' not in cols:
            cursor.execute("ALTER TABLE layer ADD COLUMN enabled_features TEXT")
            conn.commit()
            print("✅ Added enabled_features to layer")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_layer_enabled_features: {e}")


def migrate_layer_nav_pill_config(app):
    """Per-layer nav pill animation + tooltip overrides."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(layer)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'nav_pill_config' not in cols:
            cursor.execute("ALTER TABLE layer ADD COLUMN nav_pill_config TEXT")
            conn.commit()
            print("✅ Added nav_pill_config to layer")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_layer_nav_pill_config: {e}")


def migrate_knowledge_form_conviction_to_claim(app):
    """Rename legacy knowledge_form conviction → claim on artifacts."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(artifact)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'knowledge_form' not in cols:
            conn.close()
            return
        cursor.execute(
            "UPDATE artifact SET knowledge_form = 'claim' WHERE knowledge_form = 'conviction'"
        )
        n = cursor.rowcount
        conn.commit()
        conn.close()
        if n:
            print(f"✅ Renamed knowledge_form conviction → claim on {n} artifact(s)")
    except Exception as e:
        print(f"⚠️  Error in migrate_knowledge_form_conviction_to_claim: {e}")


def migrate_artifact_tags(app):
    """Layer-scoped artifact tags and artifact_tag_link junction."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_tag'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE artifact_tag (
                    id VARCHAR(36) PRIMARY KEY,
                    layer_id VARCHAR(36) NOT NULL REFERENCES layer(id),
                    slug VARCHAR(48) NOT NULL,
                    label VARCHAR(64) NOT NULL,
                    description TEXT,
                    color VARCHAR(7),
                    created_by_user_id VARCHAR(36) REFERENCES user(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(layer_id, slug)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_tag_layer ON artifact_tag(layer_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_tag_layer_slug ON artifact_tag(layer_id, slug)"
            )
            conn.commit()
            print("✅ Created artifact_tag table")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_tag_link'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE artifact_tag_link (
                    id VARCHAR(36) PRIMARY KEY,
                    artifact_id VARCHAR(36) NOT NULL REFERENCES artifact(id),
                    tag_id VARCHAR(36) NOT NULL REFERENCES artifact_tag(id),
                    created_by_user_id VARCHAR(36) REFERENCES user(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(artifact_id, tag_id)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_tag_link_artifact ON artifact_tag_link(artifact_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_tag_link_tag ON artifact_tag_link(tag_id)"
            )
            conn.commit()
            print("✅ Created artifact_tag_link table")

        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_artifact_tags: {e}")


def migrate_layer_tags(app):
    """Unified layer_tag / layer_tag_link; migrate data from artifact_tag tables."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='layer_tag'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE layer_tag (
                    id VARCHAR(36) PRIMARY KEY,
                    layer_id VARCHAR(36) NOT NULL REFERENCES layer(id),
                    slug VARCHAR(48) NOT NULL,
                    label VARCHAR(64) NOT NULL,
                    description TEXT,
                    color VARCHAR(7),
                    created_by_user_id VARCHAR(36) REFERENCES user(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(layer_id, slug)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer_tag_layer ON layer_tag(layer_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer_tag_layer_slug ON layer_tag(layer_id, slug)"
            )
            conn.commit()
            print("✅ Created layer_tag table")

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='layer_tag_link'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE layer_tag_link (
                    id VARCHAR(36) PRIMARY KEY,
                    tag_id VARCHAR(36) NOT NULL REFERENCES layer_tag(id),
                    subject_type VARCHAR(32) NOT NULL,
                    subject_id VARCHAR(36) NOT NULL,
                    created_by_user_id VARCHAR(36) REFERENCES user(id),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(subject_type, subject_id, tag_id)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer_tag_link_tag ON layer_tag_link(tag_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer_tag_link_subject "
                "ON layer_tag_link(subject_type, subject_id)"
            )
            conn.commit()
            print("✅ Created layer_tag_link table")

        cursor.execute("SELECT COUNT(*) FROM layer_tag")
        lt_count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_tag'"
        )
        if cursor.fetchone() and lt_count == 0:
            cursor.execute("""
                INSERT INTO layer_tag (id, layer_id, slug, label, description, color,
                    created_by_user_id, created_at)
                SELECT id, layer_id, slug, label, description, color,
                    created_by_user_id, created_at FROM artifact_tag
            """)
            n = cursor.rowcount
            if n:
                print(f"✅ Migrated {n} row(s) artifact_tag → layer_tag")

        cursor.execute("SELECT COUNT(*) FROM layer_tag_link")
        ltl_count = cursor.fetchone()[0]
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='artifact_tag_link'"
        )
        if cursor.fetchone() and ltl_count == 0:
            cursor.execute("""
                INSERT INTO layer_tag_link (id, tag_id, subject_type, subject_id,
                    created_by_user_id, created_at)
                SELECT id, tag_id, 'artifact', artifact_id,
                    created_by_user_id, created_at FROM artifact_tag_link
            """)
            n = cursor.rowcount
            if n:
                print(f"✅ Migrated {n} row(s) artifact_tag_link → layer_tag_link")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_layer_tags: {e}")


def migrate_submission_document_category(app):
    """Model C document_category on submission."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(submission)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'document_category' not in cols:
            cursor.execute(
                "ALTER TABLE submission ADD COLUMN document_category VARCHAR(32)"
            )
            conn.commit()
            print("✅ Added submission.document_category")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_submission_document_category: {e}")


def migrate_guild_unified_phase1(app):
    """Unified Phase I: guild_layer_link, guild_artifact_link, guild_membership.membership_state."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(guild_membership)")
        gm_cols = [c[1] for c in cursor.fetchall()]
        if gm_cols and 'membership_state' not in gm_cols:
            cursor.execute(
                "ALTER TABLE guild_membership ADD COLUMN membership_state VARCHAR(20) DEFAULT 'active'"
            )
            conn.commit()
            print("✅ Added guild_membership.membership_state")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='guild_layer_link'"
        )
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE guild_layer_link (
                    id VARCHAR(36) PRIMARY KEY,
                    guild_id VARCHAR(36) NOT NULL REFERENCES guild(id),
                    layer_id VARCHAR(36) NOT NULL REFERENCES layer(id),
                    created_by_user_id VARCHAR(36) REFERENCES user(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, layer_id)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_guild_layer_link_guild ON guild_layer_link(guild_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_guild_layer_link_layer ON guild_layer_link(layer_id)"
            )
            conn.commit()
            print("✅ Created guild_layer_link table")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='guild_artifact_link'"
        )
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE guild_artifact_link (
                    id VARCHAR(36) PRIMARY KEY,
                    guild_id VARCHAR(36) NOT NULL REFERENCES guild(id),
                    artifact_id VARCHAR(36) NOT NULL REFERENCES artifact(id),
                    link_type VARCHAR(30) NOT NULL,
                    created_by_user_id VARCHAR(36) REFERENCES user(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, artifact_id, link_type)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_guild_artifact_link_guild ON guild_artifact_link(guild_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_guild_artifact_link_artifact ON guild_artifact_link(artifact_id)"
            )
            conn.commit()
            print("✅ Created guild_artifact_link table")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='guild_quest_link'"
        )
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE guild_quest_link (
                    id VARCHAR(36) PRIMARY KEY,
                    guild_id VARCHAR(36) NOT NULL REFERENCES guild(id),
                    quest_id VARCHAR(36) NOT NULL REFERENCES quest(id),
                    link_type VARCHAR(30) NOT NULL,
                    created_by_user_id VARCHAR(36) REFERENCES user(id),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, quest_id, link_type)
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_guild_quest_link_guild ON guild_quest_link(guild_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_guild_quest_link_quest ON guild_quest_link(quest_id)"
            )
            conn.commit()
            print("✅ Created guild_quest_link table")

        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_guild_unified_phase1: {e}")


def migrate_access_control_v1(app):
    """listing_visibility + join_policy on layer, guild, quest (access policy v1)."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        def add_cols(table: str, columns: list):
            cursor.execute(f"PRAGMA table_info({table})")
            existing = [c[1] for c in cursor.fetchall()]
            if not existing:
                return
            for col_name, ddl in columns:
                if col_name not in existing:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {ddl}")
                    conn.commit()
                    print(f"✅ Added {table}.{col_name}")

        add_cols(
            'layer',
            [
                ("listing_visibility", "VARCHAR(20) DEFAULT 'public'"),
                ("join_policy", "VARCHAR(30) DEFAULT 'open'"),
            ],
        )
        add_cols(
            'guild',
            [
                ("listing_visibility", "VARCHAR(20) DEFAULT 'public'"),
                ("join_policy", "VARCHAR(30) DEFAULT 'open'"),
            ],
        )
        add_cols(
            'quest',
            [
                ("listing_visibility", "VARCHAR(20) DEFAULT 'public'"),
                ("join_policy", "VARCHAR(30) DEFAULT 'open'"),
            ],
        )

        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_access_control_v1: {e}")


def migrate_notifications_stack_v1(app):
    """User notification columns, user_event_subscription, user_notification; drop legacy user_follow if present."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(user)")
        user_cols = [c[1] for c in cursor.fetchall()]
        if user_cols:
            for col_name, ddl in [
                ('notification_unsubscribe_token', 'VARCHAR(64)'),
                ('email_notifications_opt_in', 'INTEGER DEFAULT 1'),
                ('email_digest_mode', "VARCHAR(20) DEFAULT 'immediate'"),
            ]:
                if col_name not in user_cols:
                    cursor.execute(f"ALTER TABLE user ADD COLUMN {col_name} {ddl}")
                    conn.commit()
                    print(f"✅ Added user.{col_name}")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_event_subscription'"
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE user_event_subscription (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL REFERENCES user(id),
                    event_type VARCHAR(80) NOT NULL,
                    subject_type VARCHAR(40) NOT NULL,
                    subject_id VARCHAR(200) NOT NULL,
                    deliver_in_app INTEGER DEFAULT 1,
                    deliver_email INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ues_user ON user_event_subscription(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ues_event ON user_event_subscription(event_type)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ues_subject ON user_event_subscription(subject_type, subject_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ues_user_subject_event ON "
                "user_event_subscription(user_id, subject_type, subject_id, event_type)"
            )
            conn.commit()
            print("✅ Created user_event_subscription")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_notification'"
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE user_notification (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL REFERENCES user(id),
                    event_log_id VARCHAR(36) REFERENCES event_log(id),
                    title VARCHAR(255) NOT NULL,
                    body TEXT,
                    link_url VARCHAR(500),
                    read_at TIMESTAMP,
                    email_sent_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_un_user ON user_notification(user_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_un_created ON user_notification(created_at)"
            )
            conn.commit()
            print("✅ Created user_notification")

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_follow'"
        )
        if cursor.fetchone():
            cursor.execute("DROP TABLE user_follow")
            conn.commit()
            print("✅ Dropped legacy user_follow table")

        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_notifications_stack_v1: {e}")


def migrate_chair_nomination_fields(app):
    """Add nomination contact fields to working_group_chair."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(working_group_chair)")
        columns = {c[1] for c in cursor.fetchall()}
        additions = [
            ('statement', 'TEXT'),
            ('nominated_by_user_id', 'VARCHAR(36)'),
            ('is_self_nomination', 'BOOLEAN DEFAULT 0'),
            ('nominee_email', 'VARCHAR(200)'),
            ('nominee_profile_url', 'VARCHAR(500)'),
        ]
        for col, col_type in additions:
            if col not in columns:
                cursor.execute(f"ALTER TABLE working_group_chair ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"✅ Added working_group_chair.{col}")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_chair_nomination_fields: {e}")


def migrate_workgroup_nomination_flow(app):
    """Add position_key, status, nominee response token columns; backfill existing rows."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(working_group_chair)")
        columns = {c[1] for c in cursor.fetchall()}
        additions = [
            ('position_key', "VARCHAR(40) DEFAULT 'chair'"),
            ('status', "VARCHAR(30) DEFAULT 'pending_nominee'"),
            ('nominee_response_token', 'VARCHAR(64)'),
            ('nominee_token_expires_at', 'DATETIME'),
            ('nominee_responded_at', 'DATETIME'),
            ('nominee_decline_reason', 'TEXT'),
        ]
        for col, col_type in additions:
            if col not in columns:
                cursor.execute(f"ALTER TABLE working_group_chair ADD COLUMN {col} {col_type}")
                conn.commit()
                print(f"✅ Added working_group_chair.{col}")

        cursor.execute("UPDATE working_group_chair SET position_key = 'chair' WHERE position_key IS NULL OR position_key = ''")
        cursor.execute("""
            UPDATE working_group_chair
            SET status = CASE
                WHEN approved IN ('1', 1, 'true', 'TRUE') THEN 'approved'
                ELSE 'nominee_accepted'
            END
            WHERE status IS NULL OR status = ''
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_workgroup_nomination_flow: {e}")


def migrate_workgroup_charter_goals(app):
    """Add charter and goals text columns to working_group."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(working_group)")
        columns = {c[1] for c in cursor.fetchall()}
        for col in ('charter', 'goals'):
            if col not in columns:
                cursor.execute(f"ALTER TABLE working_group ADD COLUMN {col} TEXT")
                conn.commit()
                print(f"✅ Added working_group.{col}")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_workgroup_charter_goals: {e}")


def sync_dp_workgroup_documents(app):
    """Link DP workgroups ↔ DP draft submissions (fills unset links only)."""
    try:
        from extensions import db
        from services.workgroup_links import (
            sync_all_dp_submission_groups,
            sync_all_dp_workgroup_documents,
        )

        with app.app_context():
            wg_stats = sync_all_dp_workgroup_documents(force=False)
            sub_stats = sync_all_dp_submission_groups(force=False)
            if wg_stats['updated'] or sub_stats['updated']:
                db.session.commit()
            if wg_stats['updated']:
                print(
                    f"✅ Linked {wg_stats['updated']} DP workgroup(s) to draft documents "
                    f"(skipped {wg_stats['skipped']}, missing draft {wg_stats['missing_draft']})"
                )
            if sub_stats['updated']:
                print(
                    f"✅ Set workgroup on {sub_stats['updated']} DP document(s) "
                    f"(skipped {sub_stats['skipped']}, missing workgroup {sub_stats['missing_wg']})"
                )
    except Exception as e:
        print(f"⚠️  Error syncing DP workgroup documents: {e}")


def sync_sequential_ml_draft_numbers(app):
    """Renumber ML-Draft-* by creation order when out of sequence (skipped when sealed)."""
    try:
        from extensions import db
        from services.ml_numbering import (
            apply_ml_renumber_plan,
            build_ml_renumber_plan,
            is_ml_numbering_sealed,
            needs_ml_renumber,
        )

        with app.app_context():
            if is_ml_numbering_sealed():
                return
            if not needs_ml_renumber():
                return
            plan = build_ml_renumber_plan()
            updated = apply_ml_renumber_plan(plan)
            if updated:
                db.session.commit()
                print(f"✅ Renumbered {updated} ML-Draft document families into creation order")
    except Exception as e:
        print(f"⚠️  Error renumbering ML draft numbers: {e}")


def migrate_submission_content_hash(app):
    """Add content_hash column and backfill hashes for existing submissions."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(submission)")
        columns = {c[1] for c in cursor.fetchall()}
        if 'content_hash' not in columns:
            cursor.execute("ALTER TABLE submission ADD COLUMN content_hash VARCHAR(64)")
            conn.commit()
            print("✅ Added submission.content_hash")
        conn.close()

        from services.submission_dedup import backfill_submission_content_hashes

        with app.app_context():
            stats = backfill_submission_content_hashes(commit=True)
            if stats['updated']:
                print(
                    f"✅ Backfilled content_hash for {stats['updated']} submission(s) "
                    f"(skipped {stats['skipped']}, failed {stats['failed']})"
                )
    except Exception as e:
        print(f"⚠️  Error in migrate_submission_content_hash: {e}")


def migrate_hardcoded_users(app):
    """Migrate legacy bootstrap users. Passwords are random — use reset-password.py to set one."""
    import secrets

    hardcoded_users = {
        'admin': {'name': 'Admin User', 'email': 'admin@govhub.org', 'role': 'admin', 'theme': 'dark'},
        'info': {'name': 'GovHub Info', 'email': 'info@themetalayer.org', 'role': 'editor', 'theme': 'dark'},
        'daveed': {'name': 'Daveed', 'email': 'daveed@bridgit.io', 'role': 'admin', 'theme': 'dark'},
        'john': {'name': 'John Doe', 'email': 'john@example.com', 'role': 'editor', 'theme': 'dark'},
        'jane': {'name': 'Jane Smith', 'email': 'jane@example.com', 'role': 'user', 'theme': 'dark'},
        'shiftshapr': {'name': 'Shift Shapr', 'email': 'shiftshapr@example.com', 'role': 'editor', 'theme': 'dark'},
    }

    created = 0
    for username, user_data in hardcoded_users.items():
        if User.query.filter_by(username=username).first():
            continue
        user = User(
            username=username,
            password_hash=generate_password_hash(secrets.token_urlsafe(32)),
            name=user_data['name'],
            email=user_data['email'],
            role=user_data.get('role', 'user'),
            theme=user_data.get('theme', 'dark'),
        )
        db.session.add(user)
        created += 1

    if created:
        db.session.commit()
        print(
            f"Migrated {created} bootstrap user(s) with random passwords "
            f"(use reset-password.py to set a known password)"
        )


def migrate_layer_invitations(app):
    """Create layer_invitation table for member email invites."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='layer_invitation'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE layer_invitation (
                    id VARCHAR(36) PRIMARY KEY,
                    layer_id VARCHAR(36) NOT NULL REFERENCES layer(id),
                    inviter_id VARCHAR(36) NOT NULL REFERENCES user(id),
                    invitee_email VARCHAR(255) NOT NULL,
                    invitee_id VARCHAR(36) REFERENCES user(id),
                    message TEXT,
                    status VARCHAR(20) DEFAULT 'pending',
                    outcome_note VARCHAR(255),
                    token VARCHAR(100) NOT NULL UNIQUE,
                    created_at DATETIME,
                    expires_at DATETIME NOT NULL,
                    responded_at DATETIME
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer_invitation_layer ON layer_invitation(layer_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer_invitation_status ON layer_invitation(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer_invitation_email ON layer_invitation(layer_id, invitee_email)"
            )
            conn.commit()
            print("✅ Created layer_invitation table")
        conn.close()
    except Exception as e:
        print(f"⚠️  Error in migrate_layer_invitations: {e}")


def migrate_product_rollout_seed(app):
    """Seed site_config.product_rollout from config/product_rollout.json when missing."""
    try:
        from services.product_rollout_seed import ensure_product_rollout_seeded

        if ensure_product_rollout_seeded():
            print("✅ Seeded product_rollout from config/product_rollout.json")
    except Exception as e:
        print(f"⚠️  Error in migrate_product_rollout_seed: {e}")


def migrate_workgroup_layer_links(app):
    """Create workgroup_layer_link table; link all DP workgroups to The Overweb."""
    try:
        import sqlite3
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workgroup_layer_link (
                id VARCHAR(36) PRIMARY KEY,
                workgroup_id VARCHAR(36) NOT NULL,
                layer_id VARCHAR(36) NOT NULL,
                created_at DATETIME,
                UNIQUE(workgroup_id, layer_id)
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_wg_layer_link_wg ON workgroup_layer_link(workgroup_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_wg_layer_link_layer ON workgroup_layer_link(layer_id)"
        )
        conn.commit()
        conn.close()

        from models import Layer, Workgroup
        from services.workgroup_links import is_dp_workgroup, link_workgroup_secondary_layer

        with app.app_context():
            overweb = Layer.query.filter_by(slug='the-overweb').first()
            if not overweb:
                print("⚠️  migrate_workgroup_layer_links: layer the-overweb not found")
                return
            linked = 0
            for wg in Workgroup.query.filter_by(status='active').all():
                if not is_dp_workgroup(wg):
                    continue
                if wg.layer_id == overweb.id:
                    continue
                if link_workgroup_secondary_layer(wg, overweb.id):
                    linked += 1
            if linked:
                db.session.commit()
                print(f"✅ Linked {linked} DP workgroup(s) to The Overweb (secondary layer)")
    except Exception as e:
        print(f"⚠️  Error in migrate_workgroup_layer_links: {e}")


def migrate_meta_layer_governance_metaweb_link(app):
    """Allow Meta-Layer Governance workgroup on The Metaweb draft assignment dropdown."""
    try:
        from services.workgroup_links import ensure_meta_layer_governance_on_layer

        with app.app_context():
            if ensure_meta_layer_governance_on_layer('the-metaweb'):
                print('✅ Linked Meta-Layer Governance to The Metaweb (secondary layer)')
    except Exception as e:
        print(f'⚠️  Error in migrate_meta_layer_governance_metaweb_link: {e}')


def migrate_dp_proposals(app):
    """Create dp_proposal table; enable dp_proposals rollout flag on dev checkout."""
    try:
        import sqlite3

        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dp_proposal (
                id VARCHAR(36) PRIMARY KEY,
                submission_id VARCHAR(36) NOT NULL,
                scope VARCHAR(20) NOT NULL DEFAULT 'dp',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                anchor_hash VARCHAR(64) NOT NULL,
                context_anchor TEXT,
                original_text TEXT NOT NULL,
                proposed_text TEXT NOT NULL,
                content_hash_at_create VARCHAR(64),
                author_user_id VARCHAR(36),
                reviewed_by_user_id VARCHAR(36),
                reviewed_at DATETIME,
                incorporated_submission_id VARCHAR(36),
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (submission_id) REFERENCES submission(id),
                FOREIGN KEY (author_user_id) REFERENCES user(id),
                FOREIGN KEY (reviewed_by_user_id) REFERENCES user(id),
                FOREIGN KEY (incorporated_submission_id) REFERENCES submission(id)
            )
        """)
        for idx_sql in (
            'CREATE INDEX IF NOT EXISTS idx_dp_proposal_submission ON dp_proposal(submission_id)',
            'CREATE INDEX IF NOT EXISTS idx_dp_proposal_status ON dp_proposal(status)',
            'CREATE INDEX IF NOT EXISTS idx_dp_proposal_anchor ON dp_proposal(anchor_hash)',
            'CREATE INDEX IF NOT EXISTS idx_dp_proposal_author ON dp_proposal(author_user_id)',
            'CREATE INDEX IF NOT EXISTS idx_dp_proposal_created ON dp_proposal(created_at)',
        ):
            cursor.execute(idx_sql)
        conn.commit()
        conn.close()
        print('✅ dp_proposal table ready')

        from config import IS_DEVELOPMENT
        if IS_DEVELOPMENT:
            import json
            from extensions import db
            from models import SiteConfig
            from services.product_rollout import PRODUCT_ROLLOUT_SITE_CONFIG_KEY

            with app.app_context():
                row = SiteConfig.query.filter_by(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY).first()
                cfg = {}
                if row and row.value:
                    try:
                        cfg = json.loads(row.value)
                    except json.JSONDecodeError:
                        cfg = {}
                if 'patches' not in cfg and 'dp_proposals' not in cfg and 'document_edits' not in cfg:
                    cfg['patches'] = True
                    cfg.pop('dp_proposals', None)
                    cfg.pop('document_edits', None)
                    payload = json.dumps(cfg, sort_keys=True)
                    if row:
                        row.value = payload
                    else:
                        db.session.add(SiteConfig(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY, value=payload))
                    db.session.commit()
                    print('✅ Enabled patches in product_rollout (dev)')
    except Exception as e:
        print(f'⚠️  Error in migrate_dp_proposals: {e}')


def migrate_dp_proposal_rationale_reference(app):
    """Add optional rationale and reference_url to dp_proposal."""
    try:
        import sqlite3

        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(dp_proposal)')
        cols = {row[1] for row in cursor.fetchall()}
        if 'rationale' not in cols:
            cursor.execute('ALTER TABLE dp_proposal ADD COLUMN rationale TEXT')
        if 'reference_url' not in cols:
            cursor.execute('ALTER TABLE dp_proposal ADD COLUMN reference_url VARCHAR(2048)')
        conn.commit()
        conn.close()
        print('✅ dp_proposal rationale/reference_url columns ready')
    except Exception as e:
        print(f'⚠️  Error in migrate_dp_proposal_rationale_reference: {e}')


def migrate_platform_invitations(app):
    """Create platform_invitation table; extend workgroup_member_request for invites."""
    try:
        import sqlite3

        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS platform_invitation (
                id VARCHAR(36) PRIMARY KEY,
                invite_type VARCHAR(40) NOT NULL,
                rate_category VARCHAR(20) NOT NULL DEFAULT 'standard',
                inviter_id VARCHAR(36) NOT NULL,
                invitee_email VARCHAR(255) NOT NULL,
                invitee_id VARCHAR(36),
                message TEXT,
                target_json TEXT NOT NULL DEFAULT '{}',
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                outcome_note VARCHAR(255),
                token VARCHAR(100) NOT NULL UNIQUE,
                created_at DATETIME,
                expires_at DATETIME NOT NULL,
                responded_at DATETIME,
                FOREIGN KEY (inviter_id) REFERENCES user(id),
                FOREIGN KEY (invitee_id) REFERENCES user(id)
            )
        """)
        for idx_sql in (
            'CREATE INDEX IF NOT EXISTS idx_platform_invite_type ON platform_invitation(invite_type)',
            'CREATE INDEX IF NOT EXISTS idx_platform_invite_inviter ON platform_invitation(inviter_id)',
            'CREATE INDEX IF NOT EXISTS idx_platform_invite_email ON platform_invitation(invitee_email)',
            'CREATE INDEX IF NOT EXISTS idx_platform_invite_status ON platform_invitation(status)',
            'CREATE INDEX IF NOT EXISTS idx_platform_invite_token ON platform_invitation(token)',
        ):
            cursor.execute(idx_sql)
        cursor.execute('PRAGMA table_info(workgroup_member_request)')
        cols = {row[1] for row in cursor.fetchall()}
        if 'invited_by_user_id' not in cols:
            cursor.execute(
                'ALTER TABLE workgroup_member_request ADD COLUMN invited_by_user_id VARCHAR(36)'
            )
        if 'platform_invitation_id' not in cols:
            cursor.execute(
                'ALTER TABLE workgroup_member_request ADD COLUMN platform_invitation_id VARCHAR(36)'
            )
        conn.commit()
        conn.close()
        print('✅ platform_invitation table ready')
    except Exception as e:
        print(f'⚠️  Error in migrate_platform_invitations: {e}')


def migrate_user_bitcoin_wallet_v1(app):
    """bitcoinAddress on user (badge wallet for ordinals)."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(user)')
        cols = [c[1] for c in cursor.fetchall()]
        if cols and 'bitcoinAddress' not in cols:
            cursor.execute('ALTER TABLE user ADD COLUMN bitcoinAddress VARCHAR(128)')
            conn.commit()
            print('✅ Added user.bitcoinAddress')
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_user_bitcoin_wallet_v1: {e}')


def migrate_custodial_wallet_v1(app):
    """custodial_wallet table for encrypted BTC leaf keys."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='custodial_wallet'"
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE custodial_wallet (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    chain VARCHAR(32) NOT NULL DEFAULT 'btc_taproot',
                    address VARCHAR(128) NOT NULL,
                    derivation_path VARCHAR(64) NOT NULL,
                    encrypted_secret TEXT NOT NULL,
                    created_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES user(id),
                    UNIQUE (user_id, chain)
                )
                """
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_custodial_wallet_user ON custodial_wallet(user_id)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_custodial_wallet_address ON custodial_wallet(address)'
            )
            conn.commit()
            print('✅ Created custodial_wallet table')
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_custodial_wallet_v1: {e}')


def migrate_comment_is_deleted_v1(app):
    """Normalize comment.is_deleted from legacy TEXT '0'/'1' to integer 0/1."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='comment'"
        )
        if not cursor.fetchone():
            conn.close()
            return
        cursor.execute('SELECT id, is_deleted FROM comment')
        rows = cursor.fetchall()
        for cid, val in rows:
            if val is None:
                new = 0
            elif isinstance(val, bool):
                new = 1 if val else 0
            elif isinstance(val, (int, float)):
                new = 1 if int(val) != 0 else 0
            else:
                s = str(val).strip().lower()
                new = 1 if s in ('1', 'true', 'yes', 'on') else 0
            cursor.execute('UPDATE comment SET is_deleted = ? WHERE id = ?', (new, cid))
        conn.commit()
        conn.close()
        print(f'✅ Normalized comment.is_deleted ({len(rows)} rows)')
    except Exception as e:
        print(f'⚠️  Error in migrate_comment_is_deleted_v1: {e}')


def migrate_layer_nft_gate_v1(app):
    """nft_gate_json on layer for NFT-gated join."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(layer)')
        cols = [c[1] for c in cursor.fetchall()]
        if cols and 'nft_gate_json' not in cols:
            cursor.execute('ALTER TABLE layer ADD COLUMN nft_gate_json TEXT')
            conn.commit()
            print('✅ Added layer.nft_gate_json')
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_layer_nft_gate_v1: {e}')


def migrate_canopi_community_sync_v1(app):
    """Layer columns for Gov Hub ↔ Canopi community sync (Revised Option C)."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(layer)')
        cols = [c[1] for c in cursor.fetchall()]
        additions = [
            ('canopi_meta_community_id', 'VARCHAR(36)'),
            ('layer_kind', 'VARCHAR(40)'),
            ('auth_provider', 'VARCHAR(64)'),
            ('stewardship', 'VARCHAR(32)'),
        ]
        for col, col_type in additions:
            if cols and col not in cols:
                cursor.execute(f'ALTER TABLE layer ADD COLUMN {col} {col_type}')
                conn.commit()
                print(f'✅ Added layer.{col}')
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_canopi_community_sync_v1: {e}')


def migrate_comment_like_v1(app):
    """Persisted likes on draft comments (comment_like table)."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='comment_like'"
        )
        if cursor.fetchone():
            conn.close()
            return
        cursor.execute('''
            CREATE TABLE comment_like (
                id VARCHAR(36) PRIMARY KEY,
                comment_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (comment_id) REFERENCES comment(id),
                FOREIGN KEY (user_id) REFERENCES user(id),
                UNIQUE (comment_id, user_id)
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_comment_like_comment ON comment_like(comment_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_comment_like_user ON comment_like(user_id)'
        )
        conn.commit()
        conn.close()
        print('✅ Created comment_like table')
    except Exception as e:
        print(f'⚠️  Error in migrate_comment_like_v1: {e}')


def migrate_invitation_shareable_v1(app):
    """Shareable vs private invitations; multi-use accept log; non-expiring shareable links."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for table, cols in (
            ('platform_invitation', (
                ('binding_mode', "VARCHAR(20) NOT NULL DEFAULT 'private'"),
                ('revoked_at', 'DATETIME'),
            )),
            ('layer_invitation', (
                ('binding_mode', "VARCHAR(20) NOT NULL DEFAULT 'private'"),
                ('revoked_at', 'DATETIME'),
            )),
        ):
            cursor.execute(f'PRAGMA table_info({table})')
            existing = {row[1] for row in cursor.fetchall()}
            for col, col_type in cols:
                if col not in existing:
                    cursor.execute(f'ALTER TABLE {table} ADD COLUMN {col} {col_type}')
                    print(f'✅ Added {table}.{col}')

        # SQLite: allow NULL expires_at for non-expiring shareable links (recreate table).
        for table in ('platform_invitation', 'layer_invitation'):
            cursor.execute(f'PRAGMA table_info({table})')
            info = cursor.fetchall()
            expires_col = next((c for c in info if c[1] == 'expires_at'), None)
            if expires_col and expires_col[3] == 1:
                cursor.execute(f'ALTER TABLE {table} RENAME TO {table}_old')
                if table == 'platform_invitation':
                    cursor.execute("""
                        CREATE TABLE platform_invitation (
                            id VARCHAR(36) PRIMARY KEY,
                            invite_type VARCHAR(40) NOT NULL,
                            rate_category VARCHAR(20) NOT NULL DEFAULT 'standard',
                            inviter_id VARCHAR(36) NOT NULL,
                            invitee_email VARCHAR(255) NOT NULL,
                            invitee_id VARCHAR(36),
                            message TEXT,
                            target_json TEXT NOT NULL DEFAULT '{}',
                            status VARCHAR(20) NOT NULL DEFAULT 'pending',
                            outcome_note VARCHAR(255),
                            token VARCHAR(100) NOT NULL UNIQUE,
                            binding_mode VARCHAR(20) NOT NULL DEFAULT 'private',
                            created_at DATETIME,
                            expires_at DATETIME,
                            revoked_at DATETIME,
                            responded_at DATETIME,
                            FOREIGN KEY (inviter_id) REFERENCES user(id),
                            FOREIGN KEY (invitee_id) REFERENCES user(id)
                        )
                    """)
                    cursor.execute("""
                        INSERT INTO platform_invitation (
                            id, invite_type, rate_category, inviter_id, invitee_email,
                            invitee_id, message, target_json, status, outcome_note, token,
                            binding_mode, created_at, expires_at, revoked_at, responded_at
                        )
                        SELECT
                            id, invite_type, rate_category, inviter_id, invitee_email,
                            invitee_id, message, target_json, status, outcome_note, token,
                            COALESCE(binding_mode, 'private'), created_at, expires_at,
                            revoked_at, responded_at
                        FROM platform_invitation_old
                    """)
                else:
                    cursor.execute("""
                        CREATE TABLE layer_invitation (
                            id VARCHAR(36) PRIMARY KEY,
                            layer_id VARCHAR(36) NOT NULL,
                            inviter_id VARCHAR(36) NOT NULL,
                            invitee_email VARCHAR(255) NOT NULL,
                            invitee_id VARCHAR(36),
                            message TEXT,
                            status VARCHAR(20) DEFAULT 'pending',
                            outcome_note VARCHAR(255),
                            token VARCHAR(100) NOT NULL UNIQUE,
                            binding_mode VARCHAR(20) NOT NULL DEFAULT 'private',
                            created_at DATETIME,
                            expires_at DATETIME,
                            revoked_at DATETIME,
                            responded_at DATETIME
                        )
                    """)
                    cursor.execute("""
                        INSERT INTO layer_invitation (
                            id, layer_id, inviter_id, invitee_email, invitee_id, message,
                            status, outcome_note, token, binding_mode, created_at,
                            expires_at, revoked_at, responded_at
                        )
                        SELECT
                            id, layer_id, inviter_id, invitee_email, invitee_id, message,
                            status, outcome_note, token, COALESCE(binding_mode, 'private'),
                            created_at, expires_at, revoked_at, responded_at
                        FROM layer_invitation_old
                    """)
                cursor.execute(f'DROP TABLE {table}_old')
                print(f'✅ {table}.expires_at now nullable')

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS platform_invitation_acceptance (
                id VARCHAR(36) PRIMARY KEY,
                invitation_id VARCHAR(36) NOT NULL,
                user_id VARCHAR(36) NOT NULL,
                created_at DATETIME NOT NULL,
                FOREIGN KEY (invitation_id) REFERENCES platform_invitation(id),
                FOREIGN KEY (user_id) REFERENCES user(id),
                UNIQUE (invitation_id, user_id)
            )
        """)
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_pi_accept_invite ON platform_invitation_acceptance(invitation_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_pi_accept_user ON platform_invitation_acceptance(user_id)'
        )

        # Backfill shareable binding for open campaign invite types (existing rows stay usable).
        cursor.execute("""
            UPDATE platform_invitation
            SET binding_mode = 'shareable', expires_at = NULL
            WHERE invite_type IN ('participate_dp', 'edit_document', 'edit_document_passage')
              AND status = 'pending'
              AND (binding_mode IS NULL OR binding_mode = '' OR binding_mode = 'private')
        """)

        cursor.execute('SELECT id, listing_visibility FROM layer')
        public_layer_ids = [
            row[0] for row in cursor.fetchall()
            if (row[1] or 'public') == 'public'
        ]
        if public_layer_ids:
            placeholders = ','.join('?' * len(public_layer_ids))
            cursor.execute(
                f"""
                UPDATE layer_invitation
                SET binding_mode = 'shareable', expires_at = NULL
                WHERE layer_id IN ({placeholders})
                  AND status = 'pending'
                """,
                public_layer_ids,
            )

        conn.commit()
        conn.close()
        print('✅ invitation shareable v1 ready')
    except Exception as e:
        print(f'⚠️  Error in migrate_invitation_shareable_v1: {e}')


def migrate_reader_comments_v1(app):
    """Passage-anchored threaded comments on document read pages."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('PRAGMA table_info(comment)')
        cols = {row[1] for row in cursor.fetchall()}
        for col, col_type in (
            ('submission_id', 'VARCHAR(36)'),
            ('comment_scope', "VARCHAR(20) DEFAULT 'document'"),
            ('anchor_hash', 'VARCHAR(64)'),
            ('context_anchor', 'TEXT'),
            ('passage_excerpt', 'TEXT'),
        ):
            if col not in cols:
                cursor.execute(f'ALTER TABLE comment ADD COLUMN {col} {col_type}')
                print(f'✅ Added comment.{col}')
        conn.commit()
        conn.close()
        print('✅ reader comments v1 ready')
    except Exception as e:
        print(f'⚠️  Error in migrate_reader_comments_v1: {e}')


def migrate_layer_org_connections_v1(app):
    """Create layer_connection_type and layer_connection tables (org connections MVP)."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='layer_connection_type'"
        )
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE layer_connection_type (
                    id VARCHAR(36) PRIMARY KEY,
                    layer_id VARCHAR(36) NOT NULL REFERENCES layer(id),
                    title VARCHAR(120) NOT NULL,
                    slug VARCHAR(120) NOT NULL,
                    description TEXT,
                    agreement_text TEXT,
                    requires_approval BOOLEAN DEFAULT 1 NOT NULL,
                    is_open BOOLEAN DEFAULT 1 NOT NULL,
                    sort_order INTEGER DEFAULT 0 NOT NULL,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    terms_version INTEGER DEFAULT 1 NOT NULL,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """)
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_layer_connection_type_layer_slug "
                "ON layer_connection_type(layer_id, slug)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_layer_connection_type_layer_active "
                "ON layer_connection_type(layer_id, is_active)"
            )
            conn.commit()
            print('✅ Created layer_connection_type table')

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='layer_connection'"
        )
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE layer_connection (
                    id VARCHAR(36) PRIMARY KEY,
                    layer_id VARCHAR(36) NOT NULL REFERENCES layer(id),
                    connection_type_id VARCHAR(36) NOT NULL REFERENCES layer_connection_type(id),
                    connector_kind VARCHAR(20) NOT NULL,
                    guild_id VARCHAR(36) REFERENCES guild(id),
                    source_layer_id VARCHAR(36) REFERENCES layer(id),
                    external_name VARCHAR(255),
                    external_url VARCHAR(500),
                    representative_user_id VARCHAR(36) REFERENCES user(id),
                    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
                    message TEXT,
                    agreement_accepted_at DATETIME,
                    agreement_version INTEGER,
                    submitted_by_user_id VARCHAR(36) REFERENCES user(id),
                    reviewed_by_user_id VARCHAR(36) REFERENCES user(id),
                    reviewed_at DATETIME,
                    review_notes TEXT,
                    rejected_reason TEXT,
                    created_at DATETIME,
                    updated_at DATETIME
                )
            """)
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS idx_layer_connection_layer ON layer_connection(layer_id)",
                "CREATE INDEX IF NOT EXISTS idx_layer_connection_type ON layer_connection(connection_type_id)",
                "CREATE INDEX IF NOT EXISTS idx_layer_connection_kind ON layer_connection(connector_kind)",
                "CREATE INDEX IF NOT EXISTS idx_layer_connection_guild ON layer_connection(guild_id)",
                "CREATE INDEX IF NOT EXISTS idx_layer_connection_source_layer ON layer_connection(source_layer_id)",
                "CREATE INDEX IF NOT EXISTS idx_layer_connection_rep ON layer_connection(representative_user_id)",
                "CREATE INDEX IF NOT EXISTS idx_layer_connection_status ON layer_connection(status)",
                "CREATE INDEX IF NOT EXISTS idx_layer_connection_created ON layer_connection(created_at)",
            ):
                cursor.execute(idx_sql)
            conn.commit()
            print('✅ Created layer_connection table')
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_layer_org_connections_v1: {e}')


def migrate_overweb_connection_types_seed(app):
    """Seed default org connection types for The Overweb (idempotent)."""
    try:
        from uuid import uuid4

        from extensions import db
        from models import Layer, LayerConnectionType

        seed_types = (
            {
                'title': 'Community Partner',
                'slug': 'community-partner',
                'description': 'Organizations building alongside The Overweb community.',
                'agreement_text': (
                    'We commit to open collaboration, respectful participation, '
                    'and alignment with The Overweb mission.'
                ),
                'requires_approval': True,
                'is_open': True,
                'sort_order': 10,
            },
            {
                'title': 'Endorser',
                'slug': 'endorser',
                'description': 'Organizations that publicly endorse The Overweb.',
                'agreement_text': (
                    'We endorse The Overweb and agree our endorsement may be displayed '
                    'on layer pages and related materials.'
                ),
                'requires_approval': True,
                'is_open': True,
                'sort_order': 20,
            },
            {
                'title': 'Affiliate Layer',
                'slug': 'affiliate-layer',
                'description': 'A child or sister layer connecting to The Overweb.',
                'agreement_text': (
                    'We connect our layer to The Overweb and accept mutual visibility '
                    'and coordination expectations.'
                ),
                'requires_approval': True,
                'is_open': True,
                'sort_order': 30,
            },
            {
                'title': 'Ambassador',
                'slug': 'ambassador',
                'description': 'Individual representatives acting on behalf of an organization.',
                'agreement_text': (
                    'I represent my organization in good faith and will follow The Overweb '
                    'community standards.'
                ),
                'requires_approval': True,
                'is_open': True,
                'sort_order': 40,
            },
        )

        with app.app_context():
            overweb = Layer.query.filter_by(slug='the-overweb').first()
            if not overweb:
                print('⚠️  migrate_overweb_connection_types_seed: the-overweb not found')
                return
            created = 0
            for spec in seed_types:
                if LayerConnectionType.query.filter_by(layer_id=overweb.id, slug=spec['slug']).first():
                    continue
                db.session.add(
                    LayerConnectionType(
                        id=str(uuid4()),
                        layer_id=overweb.id,
                        title=spec['title'],
                        slug=spec['slug'],
                        description=spec['description'],
                        agreement_text=spec['agreement_text'],
                        requires_approval=spec['requires_approval'],
                        is_open=spec['is_open'],
                        sort_order=spec['sort_order'],
                        is_active=True,
                        terms_version=1,
                    )
                )
                created += 1
            if created:
                db.session.commit()
                print(f'✅ Seeded {created} Overweb connection type(s)')
    except Exception as e:
        print(f'⚠️  Error in migrate_overweb_connection_types_seed: {e}')


def migrate_referral_attribution_v1(app):
    """Create referral_attribution table for scoped conversion records."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referral_attribution (
                id VARCHAR(36) PRIMARY KEY,
                product VARCHAR(20) NOT NULL DEFAULT 'gov_hub',
                referrer_user_id VARCHAR(36) NOT NULL,
                converted_user_id VARCHAR(36),
                scope_type VARCHAR(32) NOT NULL,
                scope_id VARCHAR(36) NOT NULL,
                entity_type VARCHAR(32) NOT NULL,
                entity_id VARCHAR(36) NOT NULL,
                conversion_type VARCHAR(32) NOT NULL,
                channel VARCHAR(32),
                campaign VARCHAR(64),
                share_event_id VARCHAR(36),
                referral_token TEXT,
                legacy_referral_code VARCHAR(50),
                metadata_json TEXT,
                converted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(referrer_user_id) REFERENCES user(id),
                FOREIGN KEY(converted_user_id) REFERENCES user(id)
            )
        """)
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_referral_attr_scope ON referral_attribution(scope_type, scope_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_referral_attr_referrer ON referral_attribution(referrer_user_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_referral_attr_conversion ON referral_attribution(conversion_type)'
        )
        conn.commit()
        conn.close()
        print('✅ referral_attribution table ready')
    except Exception as e:
        print(f'⚠️  Error in migrate_referral_attribution_v1: {e}')


def migrate_referral_landing_v1(app):
    """Create referral_landing table and waitlist_email_signup.referral_token."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referral_landing (
                id VARCHAR(36) PRIMARY KEY,
                referrer_user_id VARCHAR(36),
                scope_type VARCHAR(32) NOT NULL,
                scope_id VARCHAR(36) NOT NULL,
                entity_type VARCHAR(32) NOT NULL,
                entity_id VARCHAR(36) NOT NULL,
                channel VARCHAR(32),
                landing_url VARCHAR(500) NOT NULL,
                referral_token TEXT,
                user_agent VARCHAR(500),
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(referrer_user_id) REFERENCES user(id)
            )
        """)
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_referral_landing_scope ON referral_landing(scope_type, scope_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_referral_landing_referrer ON referral_landing(referrer_user_id)'
        )
        cursor.execute('PRAGMA table_info(waitlist_email_signup)')
        email_cols = [c[1] for c in cursor.fetchall()]
        if 'referral_token' not in email_cols:
            cursor.execute('ALTER TABLE waitlist_email_signup ADD COLUMN referral_token TEXT')
        conn.commit()
        conn.close()
        print('✅ referral_landing table ready')
    except Exception as e:
        print(f'⚠️  Error in migrate_referral_landing_v1: {e}')


def migrate_layer_programs_v1(app):
    """Create layer_program tables and seed DP Challenge on The Metaweb."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS layer_program (
                id VARCHAR(36) PRIMARY KEY,
                layer_id VARCHAR(36) NOT NULL,
                slug VARCHAR(80) NOT NULL,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                hub_path VARCHAR(255),
                hub_mode VARCHAR(32),
                waitlist_id VARCHAR(36),
                workgroup_id VARCHAR(36),
                launched_at TIMESTAMP,
                archived_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(layer_id) REFERENCES layer(id),
                FOREIGN KEY(waitlist_id) REFERENCES waitlist(id),
                FOREIGN KEY(workgroup_id) REFERENCES working_group(id),
                UNIQUE(layer_id, slug)
            )
        """)
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_layer_program_layer ON layer_program(layer_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_layer_program_hub_path ON layer_program(hub_path)'
        )
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS layer_program_submission (
                id VARCHAR(36) PRIMARY KEY,
                program_id VARCHAR(36) NOT NULL,
                submission_id VARCHAR(36) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(program_id) REFERENCES layer_program(id),
                FOREIGN KEY(submission_id) REFERENCES submission(id),
                UNIQUE(program_id, submission_id)
            )
        """)
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_layer_program_submission_program '
            'ON layer_program_submission(program_id)'
        )

        cursor.execute("SELECT id FROM layer WHERE slug = 'the-metaweb' LIMIT 1")
        metaweb = cursor.fetchone()
        if metaweb:
            layer_id = metaweb[0]
            cursor.execute(
                "SELECT id FROM layer_program WHERE layer_id = ? AND slug = 'dp-challenge' LIMIT 1",
                (layer_id,),
            )
            if not cursor.fetchone():
                now = datetime.utcnow().isoformat(sep=' ', timespec='seconds')
                program_id = str(uuid4())
                cursor.execute(
                    """
                    INSERT INTO layer_program (
                        id, layer_id, slug, name, description, status,
                        hub_path, hub_mode, launched_at, created_at, updated_at
                    ) VALUES (?, ?, 'dp-challenge', 'DP Challenge',
                        'Propose patches on the Desirable Property drafts.',
                        'active', '/dp-challenge/', 'dp', ?, ?, ?)
                    """,
                    (program_id, layer_id, now, now, now),
                )
                print('✅ Seeded DP Challenge program on The Metaweb')

        conn.commit()
        conn.close()
        print('✅ layer_program tables ready')
    except Exception as e:
        print(f'⚠️  Error in migrate_layer_programs_v1: {e}')


def migrate_dp_challenge_notify_waitlist_v1(app):
    """DP Challenge notify waitlist + July 16 2026 9:00 AM PT launch schedule."""
    try:
        from zoneinfo import ZoneInfo

        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('PRAGMA table_info(layer_program)')
        prog_cols = [c[1] for c in cursor.fetchall()]
        if 'launch_at' not in prog_cols:
            cursor.execute('ALTER TABLE layer_program ADD COLUMN launch_at TIMESTAMP')
            conn.commit()
            print('✅ Added launch_at to layer_program')

        cursor.execute('PRAGMA table_info(waitlist_entry)')
        entry_cols = [c[1] for c in cursor.fetchall()]
        if 'metadata_json' not in entry_cols:
            cursor.execute('ALTER TABLE waitlist_entry ADD COLUMN metadata_json TEXT')
            conn.commit()
            print('✅ Added metadata_json to waitlist_entry')

        launch_local = datetime(2026, 7, 16, 9, 0, 0, tzinfo=ZoneInfo('America/Los_Angeles'))
        launch_utc = launch_local.astimezone(ZoneInfo('UTC')).replace(tzinfo=None)
        launch_utc_str = launch_utc.isoformat(sep=' ', timespec='seconds')

        cursor.execute("SELECT id FROM layer WHERE slug = 'the-metaweb' LIMIT 1")
        metaweb = cursor.fetchone()
        if not metaweb:
            conn.close()
            return
        layer_id = metaweb[0]

        cursor.execute(
            "SELECT id FROM waitlist WHERE layer_id = ? AND name LIKE 'DP Challenge%' LIMIT 1",
            (layer_id,),
        )
        wl_row = cursor.fetchone()
        if wl_row:
            waitlist_id = wl_row[0]
        else:
            waitlist_id = str(uuid4())
            now = datetime.utcnow().isoformat(sep=' ', timespec='seconds')
            cursor.execute(
                """
                INSERT INTO waitlist (
                    id, layer_id, name, description, public, referrals, active,
                    start_date, closing_date, archived, milestones, show_milestones,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, 1, 0, 1, ?, ?, 0, 0, 'all', ?, ?)
                """,
                (
                    waitlist_id,
                    layer_id,
                    'DP Challenge — notify list',
                    'Get notified when the DP Challenge opens in mid-July. Select the DPs you want to patch.',
                    now,
                    launch_utc_str,
                    now,
                    now,
                ),
            )
            print('✅ Created DP Challenge notify waitlist')

        cursor.execute(
            "SELECT id FROM layer_program WHERE layer_id = ? AND slug = 'dp-challenge' LIMIT 1",
            (layer_id,),
        )
        prog_row = cursor.fetchone()
        if prog_row:
            cursor.execute(
                """
                UPDATE layer_program
                SET status = 'waitlist',
                    waitlist_id = ?,
                    launch_at = ?,
                    launched_at = NULL,
                    description = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    waitlist_id,
                    launch_utc_str,
                    'Propose patches on the Desirable Property drafts. Opens mid-July 2026.',
                    datetime.utcnow().isoformat(sep=' ', timespec='seconds'),
                    prog_row[0],
                ),
            )
            print('✅ Configured DP Challenge program for pre-launch notify waitlist')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_dp_challenge_notify_waitlist_v1: {e}')


def migrate_scoped_email_v1(app):
    """Scoped email campaigns + guild unsubscribe support."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scoped_email_campaign (
                id VARCHAR(36) PRIMARY KEY,
                scope_type VARCHAR(16) NOT NULL,
                scope_id VARCHAR(36) NOT NULL,
                created_by_id VARCHAR(36) NOT NULL,
                subject VARCHAR(255) NOT NULL,
                body TEXT NOT NULL,
                schedule_mode VARCHAR(20) NOT NULL DEFAULT 'immediate',
                scheduled_at TIMESTAMP,
                delay_hours REAL,
                anchor_kind VARCHAR(32),
                recipient_spec_json TEXT NOT NULL DEFAULT '{}',
                status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
                stats_sent INTEGER NOT NULL DEFAULT 0,
                stats_failed INTEGER NOT NULL DEFAULT 0,
                stats_total INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY(created_by_id) REFERENCES user(id)
            )
        """)
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_scoped_email_campaign_scope '
            'ON scoped_email_campaign(scope_type, scope_id)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_scoped_email_campaign_status '
            'ON scoped_email_campaign(status)'
        )
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scoped_email_delivery (
                id VARCHAR(36) PRIMARY KEY,
                campaign_id VARCHAR(36) NOT NULL,
                email VARCHAR(255) NOT NULL,
                user_id VARCHAR(36),
                anchor_at TIMESTAMP,
                send_at TIMESTAMP NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                sent_at TIMESTAMP,
                resend_id VARCHAR(64),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(campaign_id) REFERENCES scoped_email_campaign(id),
                FOREIGN KEY(user_id) REFERENCES user(id)
            )
        """)
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_scoped_email_delivery_send_at '
            'ON scoped_email_delivery(send_at, status)'
        )
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_scoped_email_delivery_campaign '
            'ON scoped_email_delivery(campaign_id)'
        )

        cursor.execute('PRAGMA table_info(email_unsubscribe)')
        cols = {row[1] for row in cursor.fetchall()}
        if 'guild_id' not in cols:
            cursor.execute('ALTER TABLE email_unsubscribe ADD COLUMN guild_id VARCHAR(36)')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_email_unsub_guild_user '
                'ON email_unsubscribe(guild_id, user_id)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_email_unsub_guild_email '
                'ON email_unsubscribe(guild_id, email)'
            )

        conn.commit()
        conn.close()
        print('✅ scoped email campaign tables ready')
    except Exception as e:
        print(f'⚠️  Error in migrate_scoped_email_v1: {e}')


def migrate_user_mfa_v1(app):
    """MFA tables: TOTP devices, recovery codes, login challenges."""
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_mfa_device'"
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE user_mfa_device (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    label VARCHAR(100) NOT NULL DEFAULT 'Authenticator',
                    secret_ciphertext TEXT NOT NULL,
                    confirmed_at DATETIME,
                    last_used_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    revoked_at DATETIME,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )
                """
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_user_mfa_device_user '
                'ON user_mfa_device(user_id)'
            )
            print('✅ Created user_mfa_device table')
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_mfa_recovery_code'"
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE user_mfa_recovery_code (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    code_hash VARCHAR(255) NOT NULL,
                    used_at DATETIME,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )
                """
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_user_mfa_recovery_user '
                'ON user_mfa_recovery_code(user_id)'
            )
            print('✅ Created user_mfa_recovery_code table')
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user_mfa_challenge'"
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE user_mfa_challenge (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    client_id VARCHAR(50) NOT NULL DEFAULT 'govhub',
                    expires_at DATETIME NOT NULL,
                    consumed_at DATETIME,
                    failed_attempts INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )
                """
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_user_mfa_challenge_user '
                'ON user_mfa_challenge(user_id)'
            )
            print('✅ Created user_mfa_challenge table')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_user_mfa_v1: {e}')


def migrate_layer_prefix_v1(app):
    """Layer-scoped two-letter draft prefix table (e.g. "ML", "CL").

    Globally unique per prefix. Seeds "ML" as the default prefix for the
    first existing layer (preserving legacy ML-Draft-NNN references); other
    layers get a deterministic placeholder ("L1", "L2", ...) that admins can
    rename to their real two-letter code via the new Prefixes tab.
    """
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='layer_prefix'"
        )
        if not cursor.fetchone():
            cursor.execute(
                """
                CREATE TABLE layer_prefix (
                    id VARCHAR(36) PRIMARY KEY,
                    layer_id VARCHAR(36) NOT NULL,
                    prefix VARCHAR(2) NOT NULL,
                    is_default VARCHAR(1) NOT NULL DEFAULT '0',
                    created_by VARCHAR(36),
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (layer_id) REFERENCES layer(id),
                    FOREIGN KEY (created_by) REFERENCES user(id),
                    CONSTRAINT uq_layer_prefix_global UNIQUE (prefix)
                )
                """
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_layer_prefix_layer '
                'ON layer_prefix(layer_id)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_layer_prefix_prefix '
                'ON layer_prefix(prefix)'
            )
            print('✅ Created layer_prefix table')

        # Backfill default prefix for every layer that has none (idempotent).
        # Only the first layer gets "ML"; subsequent layers get a stable
        # placeholder so admins can rename in the new Prefixes tab without
        # colliding on the global UNIQUE(prefix) constraint.
        cursor.execute(
            """
            SELECT l.id
            FROM layer l
            LEFT JOIN layer_prefix lp
              ON lp.layer_id = l.id AND lp.is_default = '1'
            WHERE lp.id IS NULL
            ORDER BY l.created_at ASC, l.id ASC
            """
        )
        layers_without_default = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT 1 FROM layer_prefix WHERE prefix = 'ML'")
        ml_taken = cursor.fetchone() is not None

        for layer_id in layers_without_default:
            if not ml_taken:
                chosen_prefix = 'ML'
                ml_taken = True  # ML is now taken for any subsequent layers
            else:
                # Generate the next available "Ln" placeholder deterministically.
                cursor.execute(
                    "SELECT prefix FROM layer_prefix WHERE prefix GLOB 'L?' ORDER BY prefix"
                )
                used = {row[0] for row in cursor.fetchall()}
                chosen_prefix = next(
                    (f'L{n}' for n in range(1, 10)
                     if f'L{n}' not in used),
                    None,
                )
                if chosen_prefix is None:
                    # L1-L9 exhausted (e.g. on rerun with many layers).
                    # Fall back to a stable 2-letter hash of layer_id so the
                    # migration stays idempotent. Deterministic so the same
                    # layer gets the same placeholder across re-runs.
                    digits = ''.join(c for c in layer_id if c.isalnum())
                    if not digits:
                        digits = layer_id or uuid4().hex
                    h1 = sum(ord(c) for c in digits)
                    h2 = sum(ord(c) for c in reversed(digits))
                    cand = '{}{}'.format(
                        chr(ord('A') + (h1 % 26)),
                        chr(ord('A') + (h2 % 26)),
                    )
                    if cand in used:
                        # Try shifting the hash by an increasing offset
                        # before giving up. With 26² codes and 4-letter
                        # aliases this almost never happens in practice.
                        offset = 0
                        while offset < 26 and cand in used:
                            cand = '{}{}'.format(
                                chr(ord('A') + (h1 % 26)),
                                chr(ord('A') + ((h2 + offset) % 26)),
                            )
                            offset += 1
                    if cand in used:
                        print(
                            '⚠️  Could not derive a free hash-based prefix '
                            f'for layer {layer_id} — skipping prefix backfill'
                        )
                        continue
                    chosen_prefix = cand

            cursor.execute(
                """
                INSERT OR IGNORE INTO layer_prefix
                    (id, layer_id, prefix, is_default, created_by, created_at)
                VALUES (?, ?, ?, '1', NULL, CURRENT_TIMESTAMP)
                """,
                (str(uuid4()), layer_id, chosen_prefix),
            )
        if layers_without_default:
            print(
                f'✅ Backfilled default prefix for {len(layers_without_default)}'
                ' layer(s) — rename placeholders in Admin → Prefixes'
            )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_layer_prefix_v1: {e}')


def migrate_submission_prefix_code_v1(app):
    """Add per-draft prefix_code column to submission table.

    Lets a draft use a non-default prefix for its identifier (e.g. a layer
    that has both "ML" and "CL" as prefixes). NULL means "use the layer
    default" (legacy behaviour). Idempotent — safe to re-run.
    """
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(submission)")
        cols = [c[1] for c in cursor.fetchall()]
        if 'prefix_code' not in cols:
            cursor.execute("ALTER TABLE submission ADD COLUMN prefix_code VARCHAR(2)")
            conn.commit()
            print('✅ Added prefix_code column to submission table')
        else:
            print('✅ prefix_code column already present on submission')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_submission_prefix_code ON submission(prefix_code)")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_submission_prefix_code_v1: {e}')


# Tables in the dev DB that carry a `layer_id` column referencing `layer.id`.
# We reassign dependent rows from a duplicate-layer-id to its survivor before
# deleting the duplicate, so no user-facing data (submissions, workgroups,
# prefixes, claims, badges, etc.) is lost.
LAYER_FK_TABLES = (
    'submission',
    'working_group',
    'layer_member',
    'layer_admin',
    'layer_prefix',
    'waitlist',
    'claim',
    'badge',
    'vote',
    'role',
    'cluster',
    'one_time_badge',
    'badge_cycle',
    'role_image',
    'monument',
    'quest',
    'layer_invitation',
    'layer_connection',
    'layer_connection_type',
    'guild_layer_link',
    'workgroup_layer_link',
    'artifact',
    'artifact_collection',
    'artifact_tag',
    'layer_tag',
    'layer_program',
    'email_unsubscribe',
    'event_log',
    'inscription_order',
)


def migrate_layer_unique_v1(app):
    """One-shot: dedupe `layer` rows + enforce UNIQUE(name), UNIQUE(slug).

    Earlier bring-up never added UNIQUE indexes via migration; combined with
    a deterministic slug in ``test_api_add_requires_admin``, this let ~28
    duplicate ``Layer`` rows accumulate on the dev DB. This migration:

    1. For each (name, slug) duplicate group, picks the survivor as the
       minimum-rowid row (oldest insertion). Reassigns every dependent
       ``layer_id`` row in ``LAYER_FK_TABLES`` from the non-survivors to
       the survivor, then deletes the non-survivors.
    2. Adds ``uq_layer_name`` / ``uq_layer_slug`` UNIQUE indexes if they
       are not already present (idempotent via inspector + IF NOT EXISTS).
    3. Verifies the ``name`` / ``slug`` columns are NOT NULL.

    Idempotent: re-running on a clean DB leaves row counts unchanged and
    emits no errors. Safe against concurrent dev use — wraps each group in
    a transaction.
    """
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        # Foreign-key enforcement is OFF by default in SQLite; this is a
        # one-shot cleanup so we don't need it on, but leaving the default
        # avoids accidentally failing if any historical FK is dangling.
        cursor = conn.cursor()

        # ----- Step 1a: dedupe by `name` -----------------------------------
        cursor.execute(
            """
            SELECT name, MIN(rowid) AS survivor_rowid
            FROM layer
            WHERE name IS NOT NULL
            GROUP BY name
            HAVING COUNT(*) > 1
            """
        )
        name_groups = cursor.fetchall()
        total_deleted = 0
        for dup_name, survivor_rowid in name_groups:
            cursor.execute(
                'SELECT id, rowid FROM layer WHERE name = ? ORDER BY rowid',
                (dup_name,),
            )
            rows = cursor.fetchall()
            survivor_id = None
            non_survivors = []
            for layer_id, rowid in rows:
                if rowid == survivor_rowid and survivor_id is None:
                    survivor_id = layer_id
                else:
                    non_survivors.append(layer_id)
            if survivor_id is None or not non_survivors:
                continue
            placeholders = ','.join('?' for _ in non_survivors)
            for tbl in LAYER_FK_TABLES:
                # Use try/except per-table in case the table doesn't exist
                # on a fresh DB or hasn't been migrated in yet.
                try:
                    cursor.execute(
                        f'UPDATE {tbl} SET layer_id = ? '
                        f'WHERE layer_id IN ({placeholders})',
                        [survivor_id, *non_survivors],
                    )
                except sqlite3.OperationalError:
                    # Table doesn't exist or no layer_id column yet.
                    pass
            cursor.execute(
                f'DELETE FROM layer WHERE id IN ({placeholders})',
                non_survivors,
            )
            deleted = cursor.rowcount
            total_deleted += deleted
            print(
                f'  layer.name={dup_name!r}: kept {survivor_id[:8]}... '
                f'reassigned dependents of {len(non_survivors)} duplicate(s)'
            )
        if name_groups:
            conn.commit()
            print(
                f'✅ migrate_layer_unique_v1: deleted {total_deleted} duplicate '
                'layer row(s) (by name)'
            )
        else:
            print('✅ migrate_layer_unique_v1: no name duplicates')

        # ----- Step 1b: dedupe by `slug` -----------------------------------
        # After the name dedupe, a slug clash can only happen if two distinct
        # names happen to share a slug. We apply the same survivor-by-rowid
        # strategy.
        cursor.execute(
            """
            SELECT slug, MIN(rowid) AS survivor_rowid
            FROM layer
            WHERE slug IS NOT NULL
            GROUP BY slug
            HAVING COUNT(*) > 1
            """
        )
        slug_groups = cursor.fetchall()
        slug_deleted = 0
        for dup_slug, survivor_rowid in slug_groups:
            cursor.execute(
                'SELECT id, rowid FROM layer WHERE slug = ? ORDER BY rowid',
                (dup_slug,),
            )
            rows = cursor.fetchall()
            survivor_id = None
            non_survivors = []
            for layer_id, rowid in rows:
                if rowid == survivor_rowid and survivor_id is None:
                    survivor_id = layer_id
                else:
                    non_survivors.append(layer_id)
            if survivor_id is None or not non_survivors:
                continue
            placeholders = ','.join('?' for _ in non_survivors)
            for tbl in LAYER_FK_TABLES:
                try:
                    cursor.execute(
                        f'UPDATE {tbl} SET layer_id = ? '
                        f'WHERE layer_id IN ({placeholders})',
                        [survivor_id, *non_survivors],
                    )
                except sqlite3.OperationalError:
                    pass
            cursor.execute(
                f'DELETE FROM layer WHERE id IN ({placeholders})',
                non_survivors,
            )
            slug_deleted += cursor.rowcount
            print(
                f'  layer.slug={dup_slug!r}: kept {survivor_id[:8]}... '
                f'reassigned dependents of {len(non_survivors)} duplicate(s)'
            )
        if slug_groups:
            conn.commit()
            print(
                f'✅ migrate_layer_unique_v1: deleted {slug_deleted} duplicate '
                'layer row(s) (by slug)'
            )
        else:
            print('✅ migrate_layer_unique_v1: no slug duplicates')

        # ----- Step 2: enforce NOT NULL on name/slug -----------------------
        # SQLite cannot add NOT NULL to an existing column in-place; we
        # instead verify and warn if the column allows NULLs. New rows are
        # already constrained by the model (nullable=False).
        cursor.execute('PRAGMA table_info(layer)')
        layer_cols = {row[1]: row for row in cursor.fetchall()}
        for col in ('name', 'slug'):
            info = layer_cols.get(col)
            if info is None:
                continue
            # PRAGMA table_info: columns are (cid, name, type, notnull, dflt, pk)
            notnull = info[3]
            if not notnull:
                print(
                    f'⚠️  migrate_layer_unique_v1: layer.{col} allows NULL — '
                    'SQLite cannot ALTER to NOT NULL in-place. Backfill and '
                    'recreate the table to enforce.'
                )

        # ----- Step 3: add UNIQUE indexes if missing ----------------------
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='layer'"
        )
        existing_indexes = {row[0] for row in cursor.fetchall()}

        # SQLite supports `CREATE UNIQUE INDEX IF NOT EXISTS` — idempotent.
        # Postgres (if ever swapped in) supports the same syntax; the model
        # declares `unique=True` on both columns.
        if 'uq_layer_name' not in existing_indexes:
            cursor.execute(
                'CREATE UNIQUE INDEX uq_layer_name ON layer(name)'
            )
            print('✅ migrate_layer_unique_v1: created UNIQUE index uq_layer_name')
        else:
            print('✅ migrate_layer_unique_v1: uq_layer_name already present')

        if 'uq_layer_slug' not in existing_indexes:
            cursor.execute(
                'CREATE UNIQUE INDEX uq_layer_slug ON layer(slug)'
            )
            print('✅ migrate_layer_unique_v1: created UNIQUE index uq_layer_slug')
        else:
            print('✅ migrate_layer_unique_v1: uq_layer_slug already present')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_layer_unique_v1: {e}')


def _stub_unused_marker():  # pragma: no cover - keep at end
    pass


# Sentinel key in ``site_config`` that records the first run of
# ``migrate_layer_display_status_v1``. Once the row is present the seed
# rule below is skipped, so a layer admin's manual ``display_status`` flip
# (via ``POST /api/layers/<id>/display-status/``) survives a service
# restart. The schema/column add and the index creation stay unconditional
# (they're already no-ops when the column / index exist).
DISPLAY_STATUS_SEEDED_KEY = 'display_status_seeded_v1'


def migrate_layer_display_status_v1(app):
    """Add ``display_status`` column to ``layer`` and seed it.

    Layer admins (not GovHub super-admins) control whether their own layer
    is publicly listed. The column is independent from ``approval_status``
    (which is the GovHub super-admin gate).

    Two values:
      - ``'pending'`` — layer is hidden from public listings. New layers
        default to this.
      - ``'active'`` — layer is listed publicly. Layer admins flip their
        own layer to active from the Edit Layer modal once ready.

    Seeding rule (per product owner: "Only the AUTH communities should be
    pending. Leave all the rest alone."):

      An existing layer starts as ``'pending'`` only if it matches the
      auth-community rule:
        ``name LIKE '%API guard%' OR slug LIKE 'api-guard-layer-%'``

      Everything else starts as ``'active'``. The seeded value is the
      initial state only — layer admins can flip their own layer at any
      time, and that flip is the source of truth once the seed has run.

    Idempotent: the column / index steps skip when present. The seed step
    runs exactly once per database: on the first call it applies the rule
    and writes the sentinel row in ``site_config``; on every subsequent
    call it sees the sentinel and skips both ``UPDATE`` statements so
    admin-driven ``display_status`` flips are preserved across restarts.
    """
    try:
        db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # ----- Step 1: detect existing column ------------------------------
        cursor.execute('PRAGMA table_info(layer)')
        layer_cols = {row[1] for row in cursor.fetchall()}
        column_added = False
        if 'display_status' in layer_cols:
            print('✅ migrate_layer_display_status_v1: column already present')
        else:
            # ----- Step 2: add column with default 'pending' -----------------
            # The column-level DEFAULT gives new rows 'pending' (the safe
            # default for any freshly created layer). Existing rows are
            # re-seeded in step 3 below.
            cursor.execute(
                "ALTER TABLE layer "
                "ADD COLUMN display_status VARCHAR(32) NOT NULL DEFAULT 'pending'"
            )
            column_added = True
            print(
                '✅ migrate_layer_display_status_v1: added display_status '
                'column (default pending)'
            )

        # ----- Step 3: seed display_status (first run only) ---------------
        # The seed rule below must only run once. After the first run, the
        # admin endpoint ``POST /api/layers/<id>/display-status/`` is the
        # sole source of truth. We persist a sentinel row in ``site_config``
        # to remember we've seeded. If the sentinel is missing we apply the
        # rule and write the row; if it's present we leave existing
        # ``display_status`` values alone (admin flips are sticky).
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='site_config'"
        )
        site_config_exists = cursor.fetchone() is not None
        seeded = False
        if site_config_exists:
            cursor.execute(
                "SELECT value FROM site_config WHERE key = ?",
                (DISPLAY_STATUS_SEEDED_KEY,),
            )
            seeded = cursor.fetchone() is not None

        if seeded:
            # First-run rule already applied. Admin flips (via the API
            # endpoint) are the source of truth from here on.
            print(
                '✅ migrate_layer_display_status_v1: seed already applied '
                '(admin flips are sticky)'
            )
        else:
            # First run (or fresh DB without the sentinel): apply the rule.
            # Auth-community / API-guard layers → 'pending'; everything else
            # → 'active'. The default 'pending' set by the column's NOT NULL
            # DEFAULT would be wrong for curated layers, so this step is
            # required to bring them to 'active'.
            cursor.execute(
                "UPDATE layer "
                "SET display_status = 'active' "
                "WHERE display_status = 'pending' "
                "  AND NOT (name LIKE '%API guard%' OR slug LIKE 'api-guard-layer-%')"
            )
            flipped_active = cursor.rowcount
            cursor.execute(
                "UPDATE layer "
                "SET display_status = 'pending' "
                "WHERE display_status = 'active' "
                "  AND (name LIKE '%API guard%' OR slug LIKE 'api-guard-layer-%')"
            )
            flipped_pending = cursor.rowcount
            if flipped_active or flipped_pending or column_added:
                print(
                    f'✅ migrate_layer_display_status_v1: applied seed rule '
                    f'({flipped_active} → active, {flipped_pending} → pending)'
                )
            else:
                print(
                    '✅ migrate_layer_display_status_v1: no rows needed '
                    'seeding (sentinel absent but rule already satisfied)'
                )

            # Persist the sentinel so we never re-apply the rule. Use
            # ``INSERT OR IGNORE`` defensively in case of a race; the
            # ``SELECT`` above already gated the rest of this block.
            if site_config_exists:
                cursor.execute(
                    "INSERT OR IGNORE INTO site_config (key, value) "
                    "VALUES (?, ?)",
                    (DISPLAY_STATUS_SEEDED_KEY, 'sealed'),
                )

        # ----- Step 4: ensure index exists --------------------------------
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='layer'"
        )
        existing_indexes = {row[0] for row in cursor.fetchall()}
        if 'ix_layer_display_status' not in existing_indexes:
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS ix_layer_display_status '
                'ON layer(display_status)'
            )
            print(
                '✅ migrate_layer_display_status_v1: created index '
                'ix_layer_display_status'
            )
        else:
            print('✅ migrate_layer_display_status_v1: ix_layer_display_status present')

        conn.commit()
        conn.close()
    except Exception as e:
        print(f'⚠️  Error in migrate_layer_display_status_v1: {e}')
