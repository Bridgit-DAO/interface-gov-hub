#!/usr/bin/env python3
"""Test script to see what ordinals.com HTML actually looks like"""
import requests
import re

inscription_id = "0d89c52f64ae2f27c9964ecce23a6489870775f54cefe578a26daf8cfef23773i0"
url = f"https://ordinals.com/inscription/{inscription_id}"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

print(f"Fetching: {url}")
print()

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        html = response.text
        print(f"HTML length: {len(html)} characters")
        print()
        
        # Save full HTML for inspection
        with open('/home/ubuntu/datatracker/ordinals_page.html', 'w') as f:
            f.write(html)
        print("✅ Saved full HTML to ordinals_page.html")
        print()
        
        # Try to find the relevant sections
        print("=== Looking for metadata patterns ===")
        print()
        
        # Look for dt/dd pairs
        dt_dd_pairs = re.findall(r'<dt>([^<]+)</dt>\s*<dd>([^<]+(?:<[^>]+>[^<]*</[^>]+>)?[^<]*)</dd>', html, re.DOTALL)
        if dt_dd_pairs:
            print("Found dt/dd pairs:")
            for dt, dd in dt_dd_pairs[:20]:  # First 20
                print(f"  {dt.strip()}: {dd.strip()[:100]}")
        else:
            print("❌ No dt/dd pairs found")
        
        print()
        
        # Try current regex patterns
        print("=== Testing current regex patterns ===")
        print()
        
        match_num = re.search(r'<dt>number</dt>\s*<dd>(\d+)</dd>', html)
        print(f"Inscription number pattern: {'✅ FOUND: ' + match_num.group(1) if match_num else '❌ NOT FOUND'}")
        
        match_block = re.search(r'<dt>genesis height</dt>\s*<dd><a[^>]*>(\d+)</a></dd>', html)
        print(f"Block height pattern: {'✅ FOUND: ' + match_block.group(1) if match_block else '❌ NOT FOUND'}")
        
        match_time = re.search(r'<dt>timestamp</dt>\s*<dd><time>([^<]+)</time></dd>', html)
        print(f"Timestamp pattern: {'✅ FOUND: ' + match_time.group(1) if match_time else '❌ NOT FOUND'}")
        
    else:
        print(f"❌ Failed to fetch: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
