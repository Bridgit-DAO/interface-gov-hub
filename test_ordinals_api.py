#!/usr/bin/env python3
"""Test different ways to call the ordinals.com API"""
import requests

inscription_id = "0d89c52f64ae2f27c9964ecce23a6489870775f54cefe578a26daf8cfef23773i0"
url = f"https://ordinals.com/inscription/{inscription_id}"

print("Testing ordinals.com API endpoint")
print(f"URL: {url}")
print()

# Test 1: With Accept: application/json header
print("=== Test 1: Accept: application/json ===")
headers1 = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json'
}
try:
    r1 = requests.get(url, headers=headers1, timeout=10)
    print(f"Status: {r1.status_code}")
    if r1.status_code == 200:
        print(f"Content-Type: {r1.headers.get('Content-Type')}")
        print(f"Response: {r1.text[:200]}")
    else:
        print(f"Error: {r1.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print()

# Test 2: Without Accept header (default)
print("=== Test 2: No Accept header (HTML) ===")
headers2 = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}
try:
    r2 = requests.get(url, headers=headers2, timeout=10)
    print(f"Status: {r2.status_code}")
    print(f"Content-Type: {r2.headers.get('Content-Type')}")
    print(f"Response length: {len(r2.text)} chars")
except Exception as e:
    print(f"Error: {e}")

print()

# Test 3: Try different API endpoints
api_endpoints = [
    f"https://ordinals.com/api/inscription/{inscription_id}",
    f"https://api.ordinals.com/inscription/{inscription_id}",
]

for endpoint in api_endpoints:
    print(f"=== Testing: {endpoint} ===")
    try:
        r = requests.get(endpoint, headers=headers1, timeout=10)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            print(f"Content-Type: {r.headers.get('Content-Type')}")
            print(f"Response: {r.text[:200]}")
        else:
            print(f"Error response")
    except Exception as e:
        print(f"Error: {e}")
    print()
