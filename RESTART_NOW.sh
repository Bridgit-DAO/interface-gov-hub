#!/bin/bash
exec > /home/ubuntu/datatracker/RESTART_OUTPUT.log 2>&1

echo "=== Starting restart at $(date) ==="

bash /home/ubuntu/datatracker/force-restart-dev.sh

echo ""
echo "=== Completed at $(date) ==="
echo "Check the log at: /home/ubuntu/datatracker/RESTART_OUTPUT.log"
