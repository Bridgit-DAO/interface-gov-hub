#!/usr/bin/env python3
import os
import signal
import subprocess
import time
import sys

print("=== Force Restart Script ===")

# 1. Find and kill running processes
print("\n1. Finding running processes...")
try:
    result = subprocess.run(['pgrep', '-f', 'run.py'], 
                          capture_output=True, text=True)
    if result.stdout:
        pids = result.stdout.strip().split('\n')
        print(f"   Found {len(pids)} process(es): {pids}")
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
                print(f"   Killed PID {pid}")
            except:
                pass
        time.sleep(2)
    else:
        print("   No running processes found")
except Exception as e:
    print(f"   Error: {e}")

# 2. Check database schema
print("\n2. Checking database schema...")
try:
    result = subprocess.run([
        'sqlite3', 
        '/home/ubuntu/datatracker/instance/datatracker.db',
        'PRAGMA table_info(submission);'
    ], capture_output=True, text=True)
    
    columns = [line.split('|')[1] for line in result.stdout.strip().split('\n') if '|' in line]
    
    ordinal_columns = ['sourceType', 'ordinalId', 'ordinalContentUrl', 'ordinalContentType', 
                       'inscriptionNumber', 'blockHeight', 'inscriptionTimestamp']
    
    missing = [col for col in ordinal_columns if col not in columns]
    
    if missing:
        print(f"   ❌ Missing columns: {missing}")
    else:
        print(f"   ✅ All ordinal columns present")
        
    print(f"   Total columns: {len(columns)}")
    
except Exception as e:
    print(f"   Error checking schema: {e}")

# 3. Start server (dev: 8001)
print("\n3. Starting server...")
try:
    os.chdir('/home/ubuntu/datatracker')
    env = os.environ.copy()
    env['FLASK_ENV'] = 'development'
    env['FLASK_PORT'] = '8001'
    
    with open('/home/ubuntu/datatracker/restart.log', 'w') as f:
        proc = subprocess.Popen(
            ['python3', 'run.py'],
            stdout=f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env
        )
    
    print(f"   Started with PID {proc.pid}")
    time.sleep(3)
    
    # Check if it's still running
    try:
        os.kill(proc.pid, 0)
        print(f"   ✅ Process is running")
    except:
        print(f"   ❌ Process died")
        
    # Show first 30 lines of log
    print("\n4. Server startup log:")
    with open('/home/ubuntu/datatracker/restart.log', 'r') as f:
        lines = f.readlines()[:30]
        for line in lines:
            print(f"   {line.rstrip()}")
            
except Exception as e:
    print(f"   Error starting server: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Done ===")
