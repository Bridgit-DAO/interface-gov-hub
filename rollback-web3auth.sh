#!/bin/bash

# Web3Auth Rollback Script
# Restores the previous database backup if needed

set -e

echo "=========================================="
echo "Web3Auth Rollback"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. Find the most recent backup
BACKUP_DIR="/home/ubuntu/datatracker/backups"
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/datatracker_prod_before_web3auth_*.db 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    print_error "No backup found in $BACKUP_DIR"
    exit 1
fi

print_info "Found backup: $LATEST_BACKUP"
print_warning "This will restore the database to the state before Web3Auth deployment"
read -p "Continue with rollback? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    print_info "Rollback cancelled"
    exit 0
fi

# 2. Stop production service
print_info "Stopping production service..."
systemctl --user stop datatracker.service

# 3. Restore database
print_info "Restoring database..."
cp "$LATEST_BACKUP" /home/ubuntu/datatracker/instance/datatracker.db
print_info "Database restored"

# 4. Restart production service
print_info "Restarting production service..."
systemctl --user start datatracker.service

sleep 3

# 5. Verify
if systemctl --user is-active --quiet datatracker.service; then
    print_info "✓ Production service is running"
else
    print_error "✗ Service failed to start"
    exit 1
fi

print_info "Rollback completed successfully"
