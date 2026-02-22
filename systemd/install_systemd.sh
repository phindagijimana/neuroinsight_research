#!/bin/bash
# NeuroInsight Systemd Installation Script
# Installs user-level systemd services (no sudo required)

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

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

echo "=========================================="
echo "  NeuroInsight Systemd Installation"
echo "=========================================="
echo ""

# Get absolute paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

# Get relative path from HOME for %h substitution
RELATIVE_PROJECT_DIR="${PROJECT_DIR#$HOME/}"

log_info "Project directory: $PROJECT_DIR"
log_info "Relative to home: ~/$RELATIVE_PROJECT_DIR"
log_info "Systemd user directory: $SYSTEMD_USER_DIR"

# Check if systemd is available
if ! command -v systemctl &> /dev/null; then
    log_error "systemd is not available on this system"
    echo ""
    echo "Your system doesn't use systemd. Consider:"
    echo "  1. Use Docker Compose (recommended for non-systemd systems)"
    echo "  2. Use manual start/stop scripts"
    exit 1
fi

log_success "systemd detected"

# Check if user is in docker group (required for worker)
if groups "$USER" | grep -q '\bdocker\b'; then
    log_success "Docker group membership confirmed"
else
    log_warning "User '$USER' is not in the 'docker' group"
    log_warning "The worker service requires Docker access to process MRI scans"
    echo ""
    echo "To add yourself to the docker group, run:"
    echo "  ${GREEN}sudo usermod -aG docker \$USER${NC}"
    echo ""
    echo "Then logout and login again, or run:"
    echo "  ${GREEN}newgrp docker${NC}"
    echo ""
    read -p "Continue installation anyway? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "Installation cancelled"
        exit 1
    fi
fi

# Create systemd user directory if it doesn't exist
if [ ! -d "$SYSTEMD_USER_DIR" ]; then
    log_info "Creating systemd user directory..."
    mkdir -p "$SYSTEMD_USER_DIR"
    log_success "Created $SYSTEMD_USER_DIR"
fi

# Update service files with correct paths
log_info "Installing service files..."

for service_file in neuroinsight-backend.service neuroinsight-worker.service neuroinsight-beat.service neuroinsight-monitor.service; do
    if [ -f "$SCRIPT_DIR/$service_file" ]; then
        # Replace hardcoded path with actual project directory
        # First replace the hardcoded src/desktop_alone_web_1 with actual relative path
        sed "s|%h/src/desktop_alone_web_1|$PROJECT_DIR|g" "$SCRIPT_DIR/$service_file" | \
        sed "s|%h|$HOME|g" > "$SYSTEMD_USER_DIR/$service_file"
        log_success "Installed $service_file (using $RELATIVE_PROJECT_DIR)"
    else
        log_warning "$service_file not found, skipping"
    fi
done

# Reload systemd daemon
log_info "Reloading systemd daemon..."
systemctl --user daemon-reload
log_success "Systemd daemon reloaded"

# Enable services (they will start on login)
log_info "Enabling services..."
systemctl --user enable neuroinsight-backend.service
systemctl --user enable neuroinsight-worker.service
systemctl --user enable neuroinsight-beat.service
systemctl --user enable neuroinsight-monitor.service
log_success "Services enabled"

# Enable linger (allows services to run even when user is logged out)
log_info "Enabling user linger (services will run even after logout)..."
if loginctl enable-linger "$USER" 2>/dev/null; then
    log_success "User linger enabled"
else
    log_warning "Could not enable linger (may require sudo)"
    log_warning "Services will stop when you log out unless you run:"
    log_warning "  sudo loginctl enable-linger $USER"
fi

echo ""
echo "=========================================="
log_success "Installation complete!"
echo "=========================================="
echo ""
echo "Service Management Commands:"
echo "  ${GREEN}systemctl --user start neuroinsight-backend${NC}   # Start backend"
echo "  ${GREEN}systemctl --user start neuroinsight-worker${NC}    # Start worker"
echo "  ${GREEN}systemctl --user start neuroinsight-beat${NC}      # Start beat"
echo "  ${GREEN}systemctl --user start neuroinsight-monitor${NC}   # Start monitor"
echo ""
echo "Or start all services at once:"
echo "  ${GREEN}$PROJECT_DIR/neuroinsight start-systemd${NC}"
echo ""
echo "Check status:"
echo "  ${GREEN}systemctl --user status neuroinsight-*${NC}"
echo "  ${GREEN}$PROJECT_DIR/neuroinsight status-systemd${NC}"
echo ""
echo "View logs:"
echo "  ${GREEN}journalctl --user -u neuroinsight-backend -f${NC}"
echo "  ${GREEN}journalctl --user -u neuroinsight-worker -f${NC}"
echo ""
echo "Stop services:"
echo "  ${GREEN}systemctl --user stop neuroinsight-*${NC}"
echo "  ${GREEN}$PROJECT_DIR/neuroinsight stop-systemd${NC}"
echo ""
echo "Disable services (prevent auto-start):"
echo "  ${GREEN}systemctl --user disable neuroinsight-*${NC}"
echo ""
echo "=========================================="
