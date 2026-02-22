#!/bin/bash
# Quick fix script for WSL systemd path issues
# Run this if you installed NeuroInsight in a non-default directory

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "  NeuroInsight WSL Path Fix"
echo "=========================================="
echo ""

# Get current directory
CURRENT_DIR=$(pwd)
echo -e "${GREEN}[INFO]${NC} Current installation directory: $CURRENT_DIR"

# Check if .env exists
if [ -f "$CURRENT_DIR/.env" ]; then
    echo -e "${GREEN}✓${NC} Found .env file in current directory"
else
    echo -e "${RED}✗${NC} .env file not found!"
    echo "  → Expected: $CURRENT_DIR/.env"
    echo "  → Run './neuroinsight install' first"
    exit 1
fi

# Check if systemd directory exists
if [ ! -d "$CURRENT_DIR/systemd" ]; then
    echo -e "${RED}✗${NC} systemd directory not found!"
    echo "  → Are you in the NeuroInsight project directory?"
    exit 1
fi

# Reinstall systemd services
echo ""
echo -e "${YELLOW}[FIX]${NC} Reinstalling systemd services with correct paths..."
if [ -f "$CURRENT_DIR/systemd/install_systemd.sh" ]; then
    $CURRENT_DIR/systemd/install_systemd.sh
    echo -e "${GREEN}✓${NC} Systemd services reinstalled"
else
    echo -e "${RED}✗${NC} systemd/install_systemd.sh not found!"
    exit 1
fi

# Reload systemd daemon
echo ""
echo -e "${YELLOW}[RELOAD]${NC} Reloading systemd daemon..."
systemctl --user daemon-reload
echo -e "${GREEN}✓${NC} Systemd daemon reloaded"

# Verify the fix
echo ""
echo -e "${YELLOW}[VERIFY]${NC} Verifying systemd service configuration..."
BACKEND_SERVICE="$HOME/.config/systemd/user/neuroinsight-backend.service"

if [ -f "$BACKEND_SERVICE" ]; then
    ENV_PATH=$(grep "EnvironmentFile=" "$BACKEND_SERVICE" | cut -d'=' -f2)
    WORKING_DIR=$(grep "WorkingDirectory=" "$BACKEND_SERVICE" | cut -d'=' -f2)
    
    echo "  EnvironmentFile: $ENV_PATH"
    echo "  WorkingDirectory: $WORKING_DIR"
    
    # Check if paths are correct
    if [[ "$ENV_PATH" == *"$CURRENT_DIR"* ]] || [[ "$WORKING_DIR" == "$CURRENT_DIR" ]]; then
        echo -e "${GREEN}✓${NC} Service file paths look correct!"
    else
        echo -e "${YELLOW}⚠${NC} Service file paths may not match current directory"
        echo "  Current dir: $CURRENT_DIR"
    fi
else
    echo -e "${RED}✗${NC} Backend service file not found"
    exit 1
fi

# Try starting services
echo ""
echo "=========================================="
echo "  Fix Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Start NeuroInsight: ./neuroinsight start"
echo "  2. Check status: ./neuroinsight status"
echo "  3. View logs: journalctl --user -u neuroinsight-backend -f"
echo ""
echo "If you still have issues:"
echo "  - Run: ./neuroinsight check-wsl"
echo "  - Check logs: journalctl --user -u neuroinsight-backend -n 50"
