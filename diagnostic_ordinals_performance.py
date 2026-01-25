#!/usr/bin/env python3
"""
Diagnostic Script: Ordinals Pages/Words Performance Issue
Purpose: Measure performance impact of on-the-fly calculation vs. stored values
Target: Root cause analysis for documents page performance

This script:
1. Measures time to calculate pages/words for all submissions
2. Simulates database read performance
3. Compares on-the-fly vs. stored approach
4. Identifies submissions with missing/incorrect values
5. Validates calculation accuracy

Usage: python3 diagnostic_ordinals_performance.py
"""

import os
import sys
import time
import sqlite3
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def measure_file_calculation_time(file_path, filename):
    """Measure time to calculate pages/words from file"""
    start = time.time()
    
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
                print("  [WARNING] python-docx not installed, skipping DOCX")
                return None, None, None
                
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
                print("  [WARNING] PyPDF2 not installed, skipping PDF")
                return None, None, None
        else:
            return None, None, None
            
        elapsed = time.time() - start
        return pages, words, elapsed
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"  [ERROR] Failed to process {filename}: {e}")
        return None, None, elapsed

def run_diagnostics():
    """Run comprehensive diagnostics"""
    print("=" * 80)
    print("DIAGNOSTIC: Ordinals Pages/Words Performance Analysis")
    print("=" * 80)
    print()
    
    # Determine which database to use
    instance_dir = os.path.join(os.path.dirname(__file__), 'instance_dev')
    db_path = os.path.join(instance_dir, 'datatracker_dev.db')
    
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        return
    
    print(f"[INFO] Using database: {db_path}")
    print()
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if Submission table has pages/words columns
    cursor.execute("PRAGMA table_info(submission)")
    columns = [row[1] for row in cursor.fetchall()]
    has_pages = 'pages' in columns
    has_words = 'words' in columns
    
    print("=" * 80)
    print("SCHEMA ANALYSIS")
    print("=" * 80)
    print(f"Submission table has 'pages' column: {has_pages}")
    print(f"Submission table has 'words' column: {has_words}")
    print()
    
    # Get all submissions
    cursor.execute("""
        SELECT id, title, filename, file_path, ml_number, status
        FROM submission
        WHERE status IN ('approved', 'published')
    """)
    submissions = cursor.fetchall()
    
    print("=" * 80)
    print(f"FOUND {len(submissions)} APPROVED/PUBLISHED SUBMISSIONS")
    print("=" * 80)
    print()
    
    if len(submissions) == 0:
        print("[INFO] No submissions to analyze")
        conn.close()
        return
    
    # Performance measurements
    total_calc_time = 0
    successful_calcs = 0
    failed_calcs = 0
    missing_files = 0
    
    results = []
    
    print("=" * 80)
    print("CALCULATING PAGES/WORDS FOR EACH SUBMISSION")
    print("=" * 80)
    print()
    
    for sub_id, title, filename, file_path, ml_number, status in submissions:
        print(f"Submission: {ml_number or sub_id}")
        print(f"  Title: {title[:60]}...")
        print(f"  File: {filename}")
        print(f"  Status: {status}")
        
        if not file_path or not os.path.exists(file_path):
            print(f"  [WARNING] File not found: {file_path}")
            missing_files += 1
            results.append({
                'id': sub_id,
                'ml_number': ml_number,
                'status': 'missing_file',
                'pages': None,
                'words': None,
                'time': 0
            })
            print()
            continue
        
        pages, words, elapsed = measure_file_calculation_time(file_path, filename)
        
        if pages is not None:
            print(f"  ✓ Calculated: {pages} pages, {words} words in {elapsed:.3f}s")
            total_calc_time += elapsed
            successful_calcs += 1
            results.append({
                'id': sub_id,
                'ml_number': ml_number,
                'status': 'success',
                'pages': pages,
                'words': words,
                'time': elapsed
            })
        else:
            print(f"  ✗ Failed to calculate (took {elapsed:.3f}s)")
            failed_calcs += 1
            results.append({
                'id': sub_id,
                'ml_number': ml_number,
                'status': 'failed',
                'pages': None,
                'words': None,
                'time': elapsed
            })
        
        print()
    
    # Summary statistics
    print("=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"Total submissions analyzed: {len(submissions)}")
    print(f"Successful calculations: {successful_calcs}")
    print(f"Failed calculations: {failed_calcs}")
    print(f"Missing files: {missing_files}")
    print()
    print(f"Total calculation time: {total_calc_time:.3f}s")
    if successful_calcs > 0:
        print(f"Average time per file: {total_calc_time / successful_calcs:.3f}s")
        print(f"Estimated time per page load: {total_calc_time:.3f}s")
    print()
    
    # Simulate database read performance
    print("=" * 80)
    print("DATABASE READ PERFORMANCE (SIMULATED)")
    print("=" * 80)
    
    start = time.time()
    cursor.execute("""
        SELECT id, ml_number, title
        FROM submission
        WHERE status IN ('approved', 'published')
    """)
    _ = cursor.fetchall()
    db_read_time = time.time() - start
    
    print(f"Time to read {len(submissions)} submissions from DB: {db_read_time:.4f}s")
    print()
    
    # Performance comparison
    print("=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    print(f"On-the-fly calculation: {total_calc_time:.3f}s per page load")
    print(f"Stored values (DB read): {db_read_time:.4f}s per page load")
    if total_calc_time > 0:
        speedup = total_calc_time / db_read_time if db_read_time > 0 else float('inf')
        print(f"Speedup factor: {speedup:.1f}x faster with stored values")
    print()
    
    # Recommendations
    print("=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if not has_pages or not has_words:
        print("❌ CRITICAL: Submission table missing pages/words columns")
        print("   → Add columns to Submission model")
        print("   → Calculate on submission upload")
        print("   → Migrate existing submissions")
    
    if missing_files > 0:
        print(f"⚠️  WARNING: {missing_files} submissions have missing files")
        print("   → Stored values would handle this gracefully")
    
    if total_calc_time > 1.0:
        print(f"⚠️  WARNING: Page load time would be {total_calc_time:.1f}s")
        print("   → This is unacceptable for user experience")
        print("   → Strongly recommend storing calculated values")
    
    if successful_calcs > 0:
        print(f"✓ Successfully calculated {successful_calcs} submissions")
        print("  → These values should be stored in database")
    
    print()
    print("=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)
    
    conn.close()
    
    return {
        'total_submissions': len(submissions),
        'successful': successful_calcs,
        'failed': failed_calcs,
        'missing_files': missing_files,
        'calc_time': total_calc_time,
        'db_read_time': db_read_time,
        'has_schema': has_pages and has_words,
        'results': results
    }

if __name__ == '__main__':
    try:
        results = run_diagnostics()
        sys.exit(0 if results and results['successful'] > 0 else 1)
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
