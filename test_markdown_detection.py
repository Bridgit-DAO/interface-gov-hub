#!/usr/bin/env python3
"""Test markdown detection for ordinal content"""
import requests

inscription_id = "8e24de515cc0dc305188f3c4a0e563466723bf9cf8d4576184bf3d13e287615bi0"
content_url = f"https://ordinals.com/content/{inscription_id}"

print(f"🔍 Testing markdown detection for: {inscription_id}\n")

# Fetch content
print(f"📥 Fetching content from: {content_url}")
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
response = requests.get(content_url, headers=headers)
print(f"   Status: {response.status_code}")
print(f"   Content-Type: {response.headers.get('Content-Type')}")
print(f"   Content-Length: {len(response.text)} chars\n")

text = response.text

# Show first 500 chars
print(f"📄 First 500 chars of content:")
print("=" * 80)
print(text[:500])
print("=" * 80)
print()

# Test markdown detection (same logic as frontend)
print(f"🧪 Testing markdown detection patterns:\n")

patterns = {
    'headers': text.count('#') > 0 or text.count('##') > 0 or text.count('###') > 0,
    'bold': '**' in text or '__' in text,
    'bullets': '* ' in text or '- ' in text or '1. ' in text,
    'images': '![' in text,
    'links': '[' in text and '](' in text
}

for pattern, found in patterns.items():
    status = "✅ FOUND" if found else "❌ NOT FOUND"
    print(f"   {status} - {pattern}")

# Overall detection
is_markdown = any(patterns.values())
print(f"\n{'✅ IS MARKDOWN' if is_markdown else '❌ NOT MARKDOWN'}")

# Show specific markdown elements found
print(f"\n🔍 Markdown elements found:")
if patterns['images']:
    import re
    images = re.findall(r'!\[([^\]]*)\]\(([^\)]+)\)', text)
    print(f"   Images: {len(images)}")
    for alt, url in images[:3]:
        print(f"      - alt='{alt}' url='{url}'")

if patterns['headers']:
    headers = re.findall(r'^#+\s+(.+)$', text, re.MULTILINE)
    print(f"   Headers: {len(headers)}")
    for header in headers[:3]:
        print(f"      - {header}")

print(f"\n✅ Test complete!")
