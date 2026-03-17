#!/usr/bin/env python3
"""
NUKE AND RESTART - Complete system reset
"""

import subprocess
import time
import os
import shutil
import signal
import sys

def run_cmd(cmd, timeout=None):
    """Run command with timeout"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    except Exception as e:
        return False, "", str(e)

def main():
    print("=" * 80)
    print("NUKE AND RESTART - COMPLETE SYSTEM RESET")
    print("=" * 80)

    # Step 1: Kill EVERYTHING
    print("\n[1] KILLING EVERYTHING...")
    try:
        # Kill by process name
        subprocess.run(['pkill', '-9', '-f', 'python.*run.py'], stderr=subprocess.DEVNULL)
        subprocess.run(['pkill', '-9', '-f', 'python.*8001'], stderr=subprocess.DEVNULL)

        # Kill by port
        success, stdout, stderr = run_cmd("lsof -ti:8001 | xargs kill -9 2>/dev/null || true")
        success, stdout, stderr = run_cmd("lsof -ti:8000 | xargs kill -9 2>/dev/null || true")

        # Stop services
        run_cmd("systemctl --user stop datatracker-dev.service")
        run_cmd("systemctl --user stop datatracker.service")

        print("   ✓ All processes killed")
    except Exception as e:
        print(f"   ⚠ Kill error (continuing): {e}")

    time.sleep(3)

    # Step 2: Clear ALL cache
    print("\n[2] CLEARING ALL CACHE...")
    cache_count = 0
    for root, dirs, files in os.walk('/home/ubuntu/datatracker'):
        for d in dirs[:]:
            if d == '__pycache__':
                try:
                    shutil.rmtree(os.path.join(root, d))
                    cache_count += 1
                except:
                    pass
        for f in files[:]:
            if f.endswith('.pyc'):
                try:
                    os.remove(os.path.join(root, f))
                    cache_count += 1
                except:
                    pass

    # Also clear any .pyo files
    run_cmd("find /home/ubuntu/datatracker -name '*.pyo' -delete")

    print(f"   ✓ Cleared {cache_count} cache files")

    # Step 3: Verify code
    print("\n[3] VERIFYING CODE...")
    try:
        with open('/home/ubuntu/datatracker/app.py', 'r') as f:
            content = f.read()

        checks = [
            ('Governance Hub', 'Homepage text'),
            ('DEPLOYMENT TEST SUCCESSFUL', 'Red test box'),
            ('Version: 2026-01-17-final', 'Version marker')
        ]

        for check_text, description in checks:
            if check_text in content:
                print(f"   ✓ {description} found")
            else:
                print(f"   ✗ {description} NOT found!")
                return False

    except Exception as e:
        print(f"   ✗ Error reading code: {e}")
        return False

    # Step 4: Start service
    print("\n[4] STARTING SERVICE...")
    success, stdout, stderr = run_cmd("systemctl --user start datatracker-dev.service")
    if success:
        print("   ✓ Service started")
    else:
        print(f"   ✗ Service failed: {stderr}")
        return False

    # Step 5: Wait longer than usual
    print("\n[5] WAITING FOR SERVICE...")
    time.sleep(15)

    # Check status
    success, stdout, stderr = run_cmd("systemctl --user is-active datatracker-dev.service")
    if success and 'active' in stdout.lower():
        print("   ✓ Service is ACTIVE")
    else:
        print(f"   ✗ Service not active: {stdout}")
        return False

    # Step 6: Reload nginx
    print("\n[6] RELOADING NGINX...")
    success, stdout, stderr = run_cmd("sudo nginx -t", timeout=10)
    if success:
        run_cmd("sudo systemctl reload nginx")
        print("   ✓ Nginx reloaded")
    else:
        print(f"   ⚠ Nginx config error: {stderr}")
        print("   Continuing anyway...")

    # Step 7: Test multiple times
    print("\n[7] TESTING CONNECTIONS...")

    # Test localhost
    time.sleep(5)
    try:
        import urllib.request
        response = urllib.request.urlopen('http://localhost:8001/', timeout=20)
        content_local = response.read().decode('utf-8')
        print(f"   ✓ Localhost: HTTP {response.getcode()}")
    except Exception as e:
        print(f"   ✗ Localhost error: {e}")
        content_local = ""

    # Test dev subdomain
    time.sleep(3)
    try:
        response = urllib.request.urlopen('https://dev.rfc.themetalayer.org/', timeout=20)
        content_dev = response.read().decode('utf-8')
        print(f"   ✓ Dev subdomain: HTTP {response.getcode()}")
    except Exception as e:
        print(f"   ✗ Dev subdomain error: {e}")
        content_dev = ""

    # Step 8: Check for our markers
    print("\n[8] CHECKING FOR MARKERS...")

    markers = [
        ('DEPLOYMENT TEST SUCCESSFUL', 'Red test box'),
        ('Governance Hub', 'Homepage text'),
        ('Version: 2026-01-17-final', 'Version marker')
    ]

    results = {}

    for content, source in [(content_local, 'localhost'), (content_dev, 'dev subdomain')]:
        if not content:
            results[source] = False
            continue

        found_markers = []
        for marker, description in markers:
            if marker in content:
                found_markers.append(description)

        results[source] = len(found_markers) == len(markers)
        print(f"   {source.upper()}: {len(found_markers)}/{len(markers)} markers found")

    # Step 9: Final result
    print("\n" + "=" * 80)
    if results.get('dev subdomain', False):
        print("🎉🎉🎉 SUCCESS! ALL MARKERS FOUND ON DEV SUBDOMAIN! 🎉🎉🎉")
        print("\nVisit: https://dev.rfc.themetalayer.org")
        print("You should see a BIG RED BOX at the top of the page!")
        print("=" * 80)
        return True
    elif results.get('localhost', False):
        print("⚠️  PARTIAL SUCCESS - Working on localhost but nginx issue")
        print("\nTry: http://216.238.91.120:8001")
        print("Or fix nginx proxy settings")
        print("=" * 80)
        return True
    else:
        print("❌ FAILED - No markers found")
        print("\nDEBUG INFO:")

        for content, source in [(content_local, 'localhost'), (content_dev, 'dev subdomain')]:
            if content:
                import re
                match = re.search(r'<title>(.*?)</title>', content)
                if match:
                    print(f"{source.upper()} title: {match.group(1)}")

                # Look for any p.lead
                match = re.search(r'<p class="lead">(.*?)</p>', content)
                if match:
                    print(f"{source.upper()} lead text: {repr(match.group(1))}")

        print("\nCheck service status:")
        print("systemctl --user status datatracker-dev.service")
        print("=" * 80)
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)