#!/usr/bin/env python3
"""Add build_number parameter to all BASE_TEMPLATE.format() calls"""

with open('ietf_data_viewer_simple.py', 'r') as f:
    content = f.read()

# Split by BASE_TEMPLATE.format to process each occurrence
parts = content.split('BASE_TEMPLATE.format(')
result = [parts[0]]  # First part before any format call

for part in parts[1:]:
    # Check if build_number is already in this format call
    # Find the closing paren for this format call
    paren_count = 1
    i = 0
    while i < len(part) and paren_count > 0:
        if part[i] == '(':
            paren_count += 1
        elif part[i] == ')':
            paren_count -= 1
        i += 1
    
    format_call = part[:i-1]  # Everything up to but not including the closing )
    rest = part[i-1:]  # The closing ) and everything after
    
    # Check if build_number is already there
    if 'build_number' not in format_call:
        # Add it
        format_call = format_call.rstrip()
        if format_call and not format_call.endswith(','):
            format_call += ', '
        format_call += 'build_number=BUILD_NUMBER'
    
    result.append(format_call + rest)

content = 'BASE_TEMPLATE.format('.join(result)

with open('ietf_data_viewer_simple.py', 'w') as f:
    f.write(content)

print("Fixed all BASE_TEMPLATE.format() calls")
