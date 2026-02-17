#!/bin/bash
# Simple restart - dev only (gov-hub dev, port 8001)

systemctl --user stop datatracker-dev.service
sleep 3
systemctl --user start datatracker-dev.service
sleep 5
systemctl --user status datatracker-dev.service --no-pager | head -10
