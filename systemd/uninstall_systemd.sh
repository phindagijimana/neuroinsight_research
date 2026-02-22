#!/bin/bash
# NeuroInsight Systemd Uninstallation Script
# Removes user-level systemd services

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

echo "=========================================="
echo "  NeuroInsight Systemd Uninstallation"
echo "=========================================="
echo ""

SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

# Stop all services
log_info "Stopping all services..."
systemctl --user stop neuroinsight-backend.service 2>/dev/null || true
systemctl --user stop neuroinsight-worker.service 2>/dev/null || true
systemctl --user stop neuroinsight-beat.service 2>/dev/null || true
systemctl --user stop neuroinsight-monitor.service 2>/dev/null || true
log_success "Services stopped"

# Disable all services
log_info "Disabling all services..."
systemctl --user disable neuroinsight-backend.service 2>/dev/null || true
systemctl --user disable neuroinsight-worker.service 2>/dev/null || true
systemctl --user disable neuroinsight-beat.service 2>/dev/null || true
systemctl --user disable neuroinsight-monitor.service 2>/dev/null || true
log_success "Services disabled"

# Remove service files
log_info "Removing service files..."
rm -f "$SYSTEMD_USER_DIR/neuroinsight-backend.service"
rm -f "$SYSTEMD_USER_DIR/neuroinsight-worker.service"
rm -f "$SYSTEMD_USER_DIR/neuroinsight-beat.service"
rm -f "$SYSTEMD_USER_DIR/neuroinsight-monitor.service"
log_success "Service files removed"

# Reload systemd daemon
log_info "Reloading systemd daemon..."
systemctl --user daemon-reload
log_success "Systemd daemon reloaded"

echo ""
log_success "Uninstallation complete!"
echo ""
echo "You can still use manual start/stop scripts:"
echo "  ./neuroinsight start"
echo "  ./neuroinsight stop"
echo ""
