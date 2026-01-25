#!/usr/bin/env python3
"""
Migration Script: Add pages and words columns to Submission table
Purpose: Add pages/words columns and populate for existing submissions

This script:
1. Adds pages and words columns to Submission table
2. Calculates pages/words for all existing submissions
3. Updates database with calculated values
4. Provides rollback capability

Usage: python3 migrate_add_pages_words.py [--rollback]
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def calculate_pages_and_words(file_path, filename):
    """Calculate pages and words from a file"""
    try:
        _, ext = os.path.splitext(filename.lower())
        words = 0
        pages = 1
        
        if ext in ['.txt', '.xml']:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            words = len(content.split())
            pages = max(1, (words + 499) // 500)
            
        elif ext == '.docx':
            try:
                from docx import Document
                doc = Document(file_path)
                content_parts = []
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        content_parts.append(paragraph.text)
                content = '\n\n'.join(content_parts)
                words = len(content.split())
                pages = max(1, (words + 499) // 500)
            except ImportError:
                print("  [WARNING] python-docx not installed")
                return (1, 0)
                
        elif ext == '.pdf':
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path)
                content_parts = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        content_parts.append(text)
                content = '\n\n'.join(content_parts)
                words = len(content.split())
                pages = len(reader.pages) if reader.pages else max(1, (words + 499) // 500)
            except ImportError:
                print("  [WARNING] PyPDF2 not installed")
                return (1, 0)
        
        return (pages, words)
        
    except Exception as e:
        print(f"  [ERROR] Failed to calculate for {filename}: {e}")
        return (1, 0)

def run_migration(db_path, rollback=False):
    """Run the migration"""
    print("=" * 80)
    print("MIGRATION: Add pages/words columns to Submission table")
    print("=" * 80)
    print()
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        return False
    
    print(f"[INFO] Using database: {db_path}")
    print()
    
    # Create backup
    backup_path = f"{db_path}.backup.pages_words_migration"
    print(f"[INFO] Creating backup: {backup_path}")
    import shutil
    shutil.copy2(db_path, backup_path)
    print("[OK] Backup created")
    print()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        if rollback:
            print("=" * 80)
            print("ROLLBACK MODE")
            print("=" * 80)
            print()
            
            # Check if columns exist
            cursor.execute("PRAGMA table_info(submission)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'pages' in columns or 'words' in columns:
                print("[INFO] Dropping pages and words columns...")
                
                # SQLite doesn't support DROP COLUMN directly, need to recreate table
                # For simplicity, just set them to NULL or keep them
                # In production, you'd recreate the table
                print("[WARNING] SQLite doesn't support DROP COLUMN easily")
                print("[INFO] To rollback, restore from backup:")
                print(f"  cp {backup_path} {db_path}")
                return True
            else:
                print("[INFO] Columns don't exist, nothing to rollback")
                return True
        
        # Forward migration
        print("=" * 80)
        print("ADDING COLUMNS")
        print("=" * 80)
        print()
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(submission)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'pages' not in columns:
            print("[INFO] Adding 'pages' column...")
            cursor.execute("ALTER TABLE submission ADD COLUMN pages INTEGER DEFAULT 1")
            print("[OK] Added 'pages' column")
        else:
            print("[INFO] 'pages' column already exists")
        
        if 'words' not in columns:
            print("[INFO] Adding 'words' column...")
            cursor.execute("ALTER TABLE submission ADD COLUMN words INTEGER DEFAULT 0")
            print("[OK] Added 'words' column")
        else:
            print("[INFO] 'words' column already exists")
        
        conn.commit()
        print()
        
        # Calculate and update values for existing submissions
        print("=" * 80)
        print("CALCULATING VALUES FOR EXISTING SUBMISSIONS")
        print("=" * 80)
        print()
        
        cursor.execute("SELECT id, filename, file_path FROM submission")
        submissions = cursor.fetchall()
        
        print(f"[INFO] Found {len(submissions)} submissions")
        print()
        
        updated = 0
        skipped = 0
        
        for sub_id, filename, file_path in submissions:
            print(f"Processing: {sub_id}")
            
            if not file_path or not os.path.exists(file_path):
                print(f"  [SKIP] File not found: {file_path}")
                skipped += 1
                # Set defaults
                cursor.execute("""
                    UPDATE submission 
                    SET pages = 1, words = 0 
                    WHERE id = ?
                """, (sub_id,))
                continue
            
            pages, words = calculate_pages_and_words(file_path, filename)
            print(f"  ✓ Calculated: {pages} pages, {words} words")
            
            cursor.execute("""
                UPDATE submission 
                SET pages = ?, words = ? 
                WHERE id = ?
            """, (pages, words, sub_id))
            
            updated += 1
        
        conn.commit()
        print()
        
        print("=" * 80)
        print("MIGRATION SUMMARY")
        print("=" * 80)
        print(f"Total submissions: {len(submissions)}")
        print(f"Updated: {updated}")
        print(f"Skipped (missing files): {skipped}")
        print()
        print("[OK] Migration completed successfully!")
        print()
        print(f"Backup saved at: {backup_path}")
        print("To rollback, run:")
        print(f"  cp {backup_path} {db_path}")
        print()
        
        return True
        
    except Exception as e:
        print()
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        print()
        print("[INFO] Rolling back changes...")
        conn.rollback()
        print("[INFO] Restoring from backup...")
        import shutil
        shutil.copy2(backup_path, db_path)
        print("[OK] Rollback complete")
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    rollback = '--rollback' in sys.argv
    
    # Determine which database to use
    instance_dir = os.path.join(os.path.dirname(__file__), 'instance_dev')
    db_path = os.path.join(instance_dir, 'datatracker_dev.db')
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        sys.exit(1)
    
    success = run_migration(db_path, rollback=rollback)
    sys.exit(0 if success else 1)
