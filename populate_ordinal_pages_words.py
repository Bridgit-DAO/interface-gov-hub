#!/usr/bin/env python3
"""
Populate pages/words for existing ordinals
Purpose: Fetch content from ordinalContentUrl and calculate pages/words for ordinals with defaults

This script:
1. Finds all ordinals with pages=1 and words=0 (defaults)
2. Fetches content from ordinalContentUrl
3. Calculates pages and words
4. Updates database

Usage: python3 populate_ordinal_pages_words.py
"""

import os
import sys
import sqlite3
import requests
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def calculate_pages_words_from_text(text):
    """Calculate pages and words from text content"""
    if not text or not text.strip():
        return (1, 0)
    
    words = len(text.split())
    pages = max(1, (words + 499) // 500)  # ~500 words per page
    return (pages, words)

def fetch_ordinal_content(url, timeout=30):
    """Fetch content from ordinal URL"""
    try:
        print(f"  Fetching: {url}")
        
        # Add headers to avoid 403 Forbidden
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            # Removed Accept-Encoding to avoid compression issues that cause wrong word counts
        }
        
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
        
        # Try to decode as text
        try:
            content = response.text
            return content
        except Exception as e:
            print(f"  [WARNING] Could not decode as text: {e}")
            return None
            
    except requests.exceptions.Timeout:
        print(f"  [ERROR] Timeout fetching URL")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  [ERROR] Failed to fetch URL: {e}")
        return None

def populate_ordinals(db_path, dry_run=False):
    """Populate pages/words for ordinals"""
    print("=" * 80)
    print("POPULATE ORDINAL PAGES/WORDS")
    print("=" * 80)
    print()
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        return False
    
    print(f"[INFO] Using database: {db_path}")
    print(f"[INFO] Dry run: {dry_run}")
    print()
    
    # Create backup
    if not dry_run:
        backup_path = f"{db_path}.backup.ordinal_populate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"[INFO] Creating backup: {backup_path}")
        import shutil
        shutil.copy2(db_path, backup_path)
        print("[OK] Backup created")
        print()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Find ordinals with default pages/words
        cursor.execute("""
            SELECT id, ml_number, title, ordinalContentUrl, sourceType, pages, words
            FROM submission
            WHERE sourceType = 'ordinal'
            AND (pages = 1 OR pages IS NULL)
            AND (words = 0 OR words IS NULL)
            AND ordinalContentUrl IS NOT NULL
            AND ordinalContentUrl != ''
        """)
        
        ordinals = cursor.fetchall()
        
        print("=" * 80)
        print(f"FOUND {len(ordinals)} ORDINALS TO UPDATE")
        print("=" * 80)
        print()
        
        if len(ordinals) == 0:
            print("[INFO] No ordinals need updating")
            conn.close()
            return True
        
        updated = 0
        failed = 0
        
        for sub_id, ml_number, title, url, source_type, current_pages, current_words in ordinals:
            print(f"Ordinal: {ml_number or sub_id}")
            print(f"  Title: {title}")
            print(f"  Current: {current_pages} pages, {current_words} words")
            print(f"  URL: {url}")
            
            # Fetch content
            content = fetch_ordinal_content(url)
            
            if content:
                # Calculate pages/words
                pages, words = calculate_pages_words_from_text(content)
                print(f"  ✓ Calculated: {pages} pages, {words} words")
                
                if not dry_run:
                    cursor.execute("""
                        UPDATE submission
                        SET pages = ?, words = ?
                        WHERE id = ?
                    """, (pages, words, sub_id))
                    print(f"  ✓ Updated in database")
                else:
                    print(f"  [DRY RUN] Would update to: {pages} pages, {words} words")
                
                updated += 1
            else:
                print(f"  ✗ Failed to fetch content")
                failed += 1
            
            print()
        
        if not dry_run:
            conn.commit()
            print("[OK] Changes committed to database")
        else:
            print("[DRY RUN] No changes made to database")
        
        print()
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total ordinals found: {len(ordinals)}")
        print(f"Successfully updated: {updated}")
        print(f"Failed: {failed}")
        print()
        
        if not dry_run and updated > 0:
            print(f"[OK] Populated {updated} ordinals")
            print(f"Backup saved at: {backup_path}")
        
        return True
        
    except Exception as e:
        print()
        print(f"[ERROR] Failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Populate pages/words for ordinals')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without updating database')
    args = parser.parse_args()
    
    # Determine which database to use
    instance_dir = os.path.join(os.path.dirname(__file__), 'instance_dev')
    db_path = os.path.join(instance_dir, 'datatracker_dev.db')
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        sys.exit(1)
    
    success = populate_ordinals(db_path, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
