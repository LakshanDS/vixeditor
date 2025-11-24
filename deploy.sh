#!/bin/bash

###############################################################################
# VixEditor Deployment Script
# Automated deployment script for Ubuntu server
###############################################################################

# Ensure full PATH for minimal environments (systemd / www-data)
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

set -e  # Exit on error

# Configuration
PROJECT_NAME="vixeditor"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
DEPLOY_LOG="$LOG_DIR/deploy.log"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="vixeditor"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$DEPLOY_LOG"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓ $1${NC}" | tee -a "$DEPLOY_LOG"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗ $1${NC}" | tee -a "$DEPLOY_LOG"
}

log_info() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ℹ $1${NC}" | tee -a "$DEPLOY_LOG"
}

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

log_info "========================================"
log_info "Starting deployment for $PROJECT_NAME"
log_info "========================================"

# 1. Pull latest code from git
log_info "Pulling latest code from git..."
if git pull origin main; then
    log_success "Code pulled successfully"
else
    log_error "Failed to pull code from git"
    exit 1
fi

# 2. Activate virtual environment
log_info "Activating virtual environment..."
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
    log_success "Virtual environment activated"
else
    log_error "Virtual environment not found at $VENV_DIR"
    log_info "Please create virtual environment first: python3 -m venv venv"
    exit 1
fi

# 3. Install/Update dependencies
log_info "Installing/updating Python dependencies..."
if pip install -r requirements.txt --quiet; then
    log_success "Dependencies updated successfully"
else
    log_error "Failed to install dependencies"
    exit 1
fi

# 4. Run any database migrations (if applicable)
# Uncomment if you have migrations
# log_info "Running database migrations..."
# python manage.py migrate

# 5. Restart the service
log_info "Restarting $SERVICE_NAME service..."

# Check if systemd service exists
if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    if sudo systemctl restart "$SERVICE_NAME"; then
        log_success "Service restarted via systemd"
    else
        log_error "Failed to restart systemd service"
        exit 1
    fi
# Check if PM2 process exists
elif command -v pm2 &> /dev/null && pm2 list | grep -q "$SERVICE_NAME"; then
    if pm2 restart "$SERVICE_NAME"; then
        log_success "Service restarted via PM2"
    else
        log_error "Failed to restart PM2 process"
        exit 1
    fi
else
    log_error "No service manager found (systemd or PM2)"
    log_info "Please set up a service manager or restart manually"
    exit 1
fi

# 6. Check service status
sleep 2
log_info "Checking service status..."

if systemctl list-unit-files | grep -q "^${SERVICE_NAME}.service"; then
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "Service is running"
    else
        log_error "Service failed to start"
        sudo systemctl status "$SERVICE_NAME" --no-pager | tee -a "$DEPLOY_LOG"
        exit 1
    fi
elif command -v pm2 &> /dev/null; then
    if pm2 list | grep -q "$SERVICE_NAME.*online"; then
        log_success "PM2 process is running"
    else
        log_error "PM2 process failed to start"
        pm2 logs "$SERVICE_NAME" --lines 20 --nostream | tee -a "$DEPLOY_LOG"
        exit 1
    fi
fi

# 7. Deployment complete
log_success "========================================"
log_success "Deployment completed successfully!"
log_success "Service: $SERVICE_NAME"
log_success "Time: $(date '+%Y-%m-%d %H:%M:%S')"
log_success "========================================"

# Deactivate virtual environment
deactivate

exit 0
