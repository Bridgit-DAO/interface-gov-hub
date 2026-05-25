#!/bin/bash
# Debug script
echo "=== Checking gov-hub-prod ==="
ls -la /home/ubuntu/ | grep gov
echo "=== Worktree add ==="
cd /home/ubuntu/gov-hub-dev
git worktree add /home/ubuntu/gov-hub-prod main 2>&1
echo "=== After add ==="
ls -la /home/ubuntu/gov-hub-prod 2>&1 | head -5
