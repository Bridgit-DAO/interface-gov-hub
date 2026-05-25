#!/bin/bash

# Web3Auth Production Deployment Script
# Deploys the Web3Auth integration with minimal downtime

set -e

echo "=========================================="
echo "Web3Auth Production Deployment"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. Backup production database
print_info "Step 1: Backing up production database..."
BACKUP_DIR="/home/ubuntu/datatracker/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/datatracker_prod_before_web3auth_${TIMESTAMP}.db"

if [ -f "/home/ubuntu/datatracker/instance/datatracker.db" ]; then
    cp /home/ubuntu/datatracker/instance/datatracker.db "$BACKUP_FILE"
    print_info "Database backed up to: $BACKUP_FILE"
else
    print_warning "Production database not found at expected location"
fi

# 2. Check if production service is running
print_info "Step 2: Checking production service status..."
if systemctl --user is-active --quiet datatracker.service; then
    print_info "Production service is running"
    PROD_RUNNING=true
else
    print_warning "Production service is not running"
    PROD_RUNNING=false
fi

# 3. Verify the main Python file exists
print_info "Step 3: Verifying application file..."
if [ ! -f "/home/ubuntu/datatracker/run.py" ]; then
    print_error "Application file not found!"
    exit 1
fi

# 4. Test the dev version first
print_info "Step 4: Verifying dev version is working..."
if systemctl --user is-active --quiet datatracker-dev.service; then
    print_info "Dev service is running on port 8001"
    
    # Test dev endpoint
    if curl -f -s http://localhost:8001/ > /dev/null; then
        print_info "Dev service is responding correctly"
    else
        print_error "Dev service is not responding!"
        exit 1
    fi
else
    print_error "Dev service is not running! Please test on dev first."
    exit 1
fi

# 5. Ask for confirmation
print_warning "About to deploy Web3Auth integration to PRODUCTION"
print_warning "This will restart the production service on port 8000"
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    print_info "Deployment cancelled"
    exit 0
fi

# 6. Reload systemd daemon (in case service file changed)
print_info "Step 5: Reloading systemd daemon..."
systemctl --user daemon-reload

# 7. Restart production service
print_info "Step 6: Restarting production service..."
systemctl --user restart datatracker.service

# 8. Wait for service to start
print_info "Waiting for service to start..."
sleep 5

# 9. Verify production service is running
print_info "Step 7: Verifying production service..."
if systemctl --user is-active --quiet datatracker.service; then
    print_info "✓ Production service is running"
else
    print_error "✗ Production service failed to start!"
    print_error "Check logs with: journalctl --user -u datatracker.service -n 50"
    exit 1
fi

# 10. Test production endpoint
print_info "Step 8: Testing production endpoint..."
sleep 2

if curl -f -s http://localhost:8000/ > /dev/null; then
    print_info "✓ Production service is responding"
else
    print_error "✗ Production service is not responding!"
    print_error "Check logs with: journalctl --user -u datatracker.service -n 50"
    exit 1
fi

# 11. Display service status
print_info "Step 9: Service status..."
systemctl --user status datatracker.service --no-pager | head -20

echo ""
print_info "=========================================="
print_info "Deployment completed successfully!"
print_info "=========================================="
print_info ""
print_info "Production: http://localhost:8000"
print_info "Dev: http://localhost:8001"
print_info ""
print_info "Backup location: $BACKUP_FILE"
print_info ""
print_info "To check logs: journalctl --user -u datatracker.service -f"
print_info "To rollback: systemctl --user restart datatracker.service"
print_info ""
print_warning "IMPORTANT: Test the Web3Auth login in production!"
print_warning "1. Go to https://rfc.themetalayer.org"
print_warning "2. Click 'Sign In'"
print_warning "3. Test Google, Twitter, and Email logins"
print_warning "4. Verify dark theme modal"
print_warning "5. Check that user profile displays correctly"
echo ""
