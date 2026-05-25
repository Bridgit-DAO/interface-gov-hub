#!/bin/bash
# Force restart dev service (port 8001)
# Runs force-restart-dev.sh
cd "$(dirname "$0")"
exec ./force-restart-dev.sh
