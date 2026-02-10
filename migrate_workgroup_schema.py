#!/usr/bin/env python3
"""
Migrate workgroup schema: Extend working_group table with new functionality
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from ietf_data_viewer_simple import db, app
from datetime import datetime

def migrate():
    with app.app_context():
        print("=" * 60)
        print("Workgroup Schema Migration - Extend working_group table")
        print("=" * 60)
        
        conn = db.engine.raw_connection()
        cursor = conn.cursor()
        
        # Check current schema
        cursor.execute("PRAGMA table_info(working_group)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        print(f"\nExisting columns: {existing_columns}")
        
        # Add new columns if they don't exist
        new_columns = [
            ("slug", "VARCHAR(255)"),
            ("project_id", "VARCHAR(50)"),
            ("coordinator_id", "INTEGER"),
            ("status", "VARCHAR(20)"),
            ("approval_status", "VARCHAR(20)"),
            ("approved_by_id", "INTEGER"),
            ("approved_at", "DATETIME"),
            ("updated_at", "DATETIME"),
        ]
        
        print("\n=== Adding New Columns ===")
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                sql = f"ALTER TABLE working_group ADD COLUMN {col_name} {col_type}"
                print(f"Adding column: {col_name} ({col_type})")
                cursor.execute(sql)
            else:
                print(f"Column {col_name} already exists, skipping")
        
        conn.commit()
        
        # Populate new fields for existing working groups
        print("\n=== Populating New Fields for Existing Groups ===")
        
        # Set slug = acronym for existing groups
        cursor.execute("""
            UPDATE working_group 
            SET slug = acronym 
            WHERE slug IS NULL AND acronym IS NOT NULL
        """)
        print(f"✓ Set slug from acronym: {cursor.rowcount} rows")
        
        # Set status based on old state field
        cursor.execute("""
            UPDATE working_group 
            SET status = CASE 
                WHEN state = 'Active' THEN 'active'
                WHEN state = 'Concluded' THEN 'concluded'
                ELSE 'active'
            END
            WHERE status IS NULL
        """)
        print(f"✓ Set status from state: {cursor.rowcount} rows")
        
        # Set approval_status = 'approved' for legacy groups
        cursor.execute("""
            UPDATE working_group 
            SET approval_status = 'approved'
            WHERE approval_status IS NULL
        """)
        print(f"✓ Set approval_status to 'approved': {cursor.rowcount} rows")
        
        # Set approved_at = created_at for legacy groups
        cursor.execute("""
            UPDATE working_group 
            SET approved_at = created_at
            WHERE approved_at IS NULL AND created_at IS NOT NULL
        """)
        print(f"✓ Set approved_at from created_at: {cursor.rowcount} rows")
        
        conn.commit()
        
        # Create indexes
        print("\n=== Creating Indexes ===")
        indexes = [
            ("idx_working_group_slug", "slug"),
            ("idx_working_group_project_id", "project_id"),
            ("idx_working_group_status", "status"),
            ("idx_working_group_approval_status", "approval_status"),
        ]
        
        for idx_name, col_name in indexes:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON working_group ({col_name})")
                print(f"✓ Created index: {idx_name}")
            except Exception as e:
                print(f"⚠ Index {idx_name} already exists or error: {e}")
        
        conn.commit()
        
        # Verify migration
        print("\n=== Verification ===")
        cursor.execute("SELECT COUNT(*) FROM working_group")
        total = cursor.fetchone()[0]
        print(f"✓ Total working groups: {total}")
        
        cursor.execute("SELECT COUNT(*) FROM working_group WHERE slug IS NOT NULL")
        with_slug = cursor.fetchone()[0]
        print(f"✓ Groups with slug: {with_slug}")
        
        cursor.execute("SELECT COUNT(*) FROM working_group WHERE project_id IS NULL")
        global_groups = cursor.fetchone()[0]
        print(f"✓ Global working groups (no project): {global_groups}")
        
        cursor.execute("SELECT COUNT(*) FROM working_group WHERE project_id IS NOT NULL")
        project_groups = cursor.fetchone()[0]
        print(f"✓ Project-specific working groups: {project_groups}")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("Migration Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Update Workgroup model to use 'working_group' table")
        print("2. Update all API endpoints")
        print("3. Drop the empty 'workgroup' table")

if __name__ == '__main__':
    migrate()
