"""Database migrations. Run from init_db() with app context."""
import sqlite3
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

        cursor.execute("SELECT id, ml_number FROM submission WHERE ml_number IS NOT NULL")
        submissions = cursor.fetchall()
        migrated_count = 0
        for sub_id, ml_num in submissions:
            if ml_num and not ml_num.startswith('ML-Draft-') and not ml_num.startswith('ML-RFC-'):
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
    """Migrate hardcoded users to database"""
    hardcoded_users = {
        'admin': {'password': 'admin123', 'name': 'Admin User', 'email': 'admin@metalayer.org', 'role': 'admin', 'theme': 'dark'},
        'daveed': {'password': 'admin123', 'name': 'Daveed', 'email': 'daveed@bridgit.io', 'role': 'admin', 'theme': 'dark'},
        'john': {'password': 'password123', 'name': 'John Doe', 'email': 'john@example.com', 'role': 'editor', 'theme': 'dark'},
        'jane': {'password': 'password123', 'name': 'Jane Smith', 'email': 'jane@example.com', 'role': 'user', 'theme': 'dark'},
        'shiftshapr': {'password': 'mynewpassword123', 'name': 'Shift Shapr', 'email': 'shiftshapr@example.com', 'role': 'editor', 'theme': 'dark'}
    }

    for username, user_data in hardcoded_users.items():
        if not User.query.filter_by(username=username).first():
            user = User(
                username=username,
                password_hash=generate_password_hash(user_data['password']),
                name=user_data['name'],
                email=user_data['email'],
                role=user_data.get('role', 'user'),
                theme=user_data.get('theme', 'dark')
            )
            db.session.add(user)

    db.session.commit()
    print(f"Migrated {len(hardcoded_users)} hardcoded users to database")


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
                if 'dp_proposals' not in cfg:
                    cfg['dp_proposals'] = True
                    payload = json.dumps(cfg, sort_keys=True)
                    if row:
                        row.value = payload
                    else:
                        db.session.add(SiteConfig(key=PRODUCT_ROLLOUT_SITE_CONFIG_KEY, value=payload))
                    db.session.commit()
                    print('✅ Enabled dp_proposals in product_rollout (dev)')
    except Exception as e:
        print(f'⚠️  Error in migrate_dp_proposals: {e}')
