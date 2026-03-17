#!/bin/bash
echo "=== Checking server status ==="
ps aux | grep "python3 run.py" | grep -v grep

echo ""
echo "=== Killing old processes ==="
pkill -9 -f "python3 run.py"
sleep 2

echo ""
echo "=== Starting server ==="
cd /home/ubuntu/datatracker
python3 run.py > /home/ubuntu/datatracker/server.log 2>&1 &
NEW_PID=$!
echo "Started with PID: $NEW_PID"

sleep 3

echo ""
echo "=== Checking if running ==="
ps aux | grep "python3 run.py" | grep -v grep

echo ""
echo "=== First 50 lines of server log ==="
head -50 /home/ubuntu/datatracker/server.log

echo ""
echo "=== Done ==="
