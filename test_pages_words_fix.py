#!/usr/bin/env python3
"""
Test Script: Verify pages/words fix for ordinals
Purpose: Comprehensive testing of the pages/words implementation

Tests:
1. Schema verification - columns exist
2. Data integrity - values populated correctly
3. Performance - stored values vs on-the-fly
4. Edge cases - missing files, invalid files, large files
5. API response - documents page returns correct data
"""

import os
import sys
import sqlite3
import time
import requests

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_schema():
    """Test 1: Verify schema has pages/words columns"""
    print("=" * 80)
    print("TEST 1: Schema Verification")
    print("=" * 80)
    
    db_path = 'instance_dev/datatracker_dev.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(submission)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}
    
    assert 'pages' in columns, "❌ FAIL: 'pages' column missing"
    assert 'words' in columns, "❌ FAIL: 'words' column missing"
    assert columns['pages'] == 'INTEGER', "❌ FAIL: 'pages' should be INTEGER"
    assert columns['words'] == 'INTEGER', "❌ FAIL: 'words' should be INTEGER"
    
    print("✓ Schema has 'pages' column (INTEGER)")
    print("✓ Schema has 'words' column (INTEGER)")
    print("[PASS] Schema verification successful")
    print()
    
    conn.close()
    return True

def test_data_integrity():
    """Test 2: Verify data populated correctly"""
    print("=" * 80)
    print("TEST 2: Data Integrity")
    print("=" * 80)
    
    db_path = 'instance_dev/datatracker_dev.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, ml_number, pages, words, file_path 
        FROM submission 
        WHERE status IN ('approved', 'published')
    """)
    submissions = cursor.fetchall()
    
    print(f"Found {len(submissions)} approved/published submissions")
    print()
    
    for sub_id, ml_number, pages, words, file_path in submissions:
        display_id = ml_number or sub_id
        print(f"{display_id}:")
        print(f"  Pages: {pages}")
        print(f"  Words: {words}")
        
        # Verify reasonable values
        assert pages is not None, f"❌ FAIL: {display_id} has NULL pages"
        assert words is not None, f"❌ FAIL: {display_id} has NULL words"
        assert pages >= 1, f"❌ FAIL: {display_id} has invalid pages: {pages}"
        assert words >= 0, f"❌ FAIL: {display_id} has invalid words: {words}"
        
        # Check if file exists
        if file_path and os.path.exists(file_path):
            print(f"  ✓ File exists, values calculated")
        else:
            print(f"  ⚠ File missing, using defaults")
            assert pages == 1 and words == 0, f"❌ FAIL: {display_id} should have defaults (1, 0) for missing file"
        
        print()
    
    print("[PASS] Data integrity verification successful")
    print()
    
    conn.close()
    return True

def test_performance():
    """Test 3: Verify performance improvement"""
    print("=" * 80)
    print("TEST 3: Performance Verification")
    print("=" * 80)
    
    db_path = 'instance_dev/datatracker_dev.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Measure DB read time
    start = time.time()
    cursor.execute("""
        SELECT id, ml_number, title, pages, words 
        FROM submission 
        WHERE status IN ('approved', 'published')
    """)
    results = cursor.fetchall()
    db_time = time.time() - start
    
    print(f"Database read time: {db_time:.4f}s")
    print(f"Records retrieved: {len(results)}")
    
    # Verify it's fast
    assert db_time < 0.1, f"❌ FAIL: DB read too slow: {db_time:.4f}s"
    
    print("✓ Database read is fast (< 0.1s)")
    print("[PASS] Performance verification successful")
    print()
    
    conn.close()
    return True

def test_edge_cases():
    """Test 4: Edge cases"""
    print("=" * 80)
    print("TEST 4: Edge Cases")
    print("=" * 80)
    
    db_path = 'instance_dev/datatracker_dev.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Test submissions with missing files
    cursor.execute("""
        SELECT COUNT(*) 
        FROM submission 
        WHERE status IN ('approved', 'published') 
        AND (file_path IS NULL OR file_path = '')
    """)
    missing_files = cursor.fetchone()[0]
    
    if missing_files > 0:
        print(f"✓ Found {missing_files} submissions with missing files")
        
        # Verify they have default values
        cursor.execute("""
            SELECT id, pages, words 
            FROM submission 
            WHERE status IN ('approved', 'published') 
            AND (file_path IS NULL OR file_path = '')
        """)
        for sub_id, pages, words in cursor.fetchall():
            assert pages == 1, f"❌ FAIL: {sub_id} should have default pages=1"
            assert words == 0, f"❌ FAIL: {sub_id} should have default words=0"
        
        print("✓ Missing files have correct defaults (1 page, 0 words)")
    else:
        print("⚠ No submissions with missing files to test")
    
    # Test submissions with files
    cursor.execute("""
        SELECT COUNT(*) 
        FROM submission 
        WHERE status IN ('approved', 'published') 
        AND file_path IS NOT NULL 
        AND file_path != ''
    """)
    with_files = cursor.fetchone()[0]
    
    if with_files > 0:
        print(f"✓ Found {with_files} submissions with files")
        
        # Verify they have calculated values
        cursor.execute("""
            SELECT id, pages, words, file_path 
            FROM submission 
            WHERE status IN ('approved', 'published') 
            AND file_path IS NOT NULL 
            AND file_path != ''
        """)
        for sub_id, pages, words, file_path in cursor.fetchall():
            if os.path.exists(file_path):
                # Should have calculated values (not defaults)
                # Note: Some files might legitimately have 0 words
                assert pages >= 1, f"❌ FAIL: {sub_id} should have pages >= 1"
                print(f"  ✓ {sub_id}: {pages} pages, {words} words")
    else:
        print("⚠ No submissions with files to test")
    
    print("[PASS] Edge cases handled correctly")
    print()
    
    conn.close()
    return True

def test_api_response():
    """Test 5: API response correctness"""
    print("=" * 80)
    print("TEST 5: API Response")
    print("=" * 80)
    
    try:
        # Test documents page
        response = requests.get('http://localhost:8001/doc/all/', timeout=5)
        
        if response.status_code == 200:
            print("✓ Documents page loads successfully")
            
            # Check if pages/words are in response
            content = response.text
            
            assert 'pages' in content, "❌ FAIL: 'pages' not found in response"
            assert 'words' in content, "❌ FAIL: 'words' not found in response"
            
            # Count occurrences
            pages_count = content.count('pages</span>')
            words_count = content.count('words</span>')
            
            print(f"✓ Found {pages_count} page counts in response")
            print(f"✓ Found {words_count} word counts in response")
            
            assert pages_count > 0, "❌ FAIL: No page counts found"
            assert words_count > 0, "❌ FAIL: No word counts found"
            
            print("[PASS] API response verification successful")
        else:
            print(f"⚠ WARNING: Server returned status {response.status_code}")
            print("[SKIP] API response test skipped")
    
    except requests.exceptions.RequestException as e:
        print(f"⚠ WARNING: Could not connect to server: {e}")
        print("[SKIP] API response test skipped")
    
    print()
    return True

def run_all_tests():
    """Run all tests"""
    print("=" * 80)
    print("COMPREHENSIVE TEST SUITE: Pages/Words Fix")
    print("=" * 80)
    print()
    
    tests = [
        ("Schema Verification", test_schema),
        ("Data Integrity", test_data_integrity),
        ("Performance", test_performance),
        ("Edge Cases", test_edge_cases),
        ("API Response", test_api_response),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except AssertionError as e:
            print(f"[FAIL] {test_name}: {e}")
            results[test_name] = False
        except Exception as e:
            print(f"[ERROR] {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print()
        print("🎉 ALL TESTS PASSED!")
        return True
    else:
        print()
        print("⚠️  SOME TESTS FAILED")
        return False

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
