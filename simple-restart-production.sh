#!/bin/bash
# Simple restart - production only (datatracker.service, port 8000)
# Use simple-restart.sh for dev (datatracker-dev.service, port 8001)

systemctl --user stop datatracker.service
sleep 3
systemctl --user start datatracker.service
sleep 5
systemctl --user status datatracker.service --no-pager | head -10
