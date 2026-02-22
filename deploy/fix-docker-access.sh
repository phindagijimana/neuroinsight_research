#!/bin/bash
# Fix Docker-in-Docker Access for NeuroInsight
# This script diagnoses and fixes Docker socket permission issues

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "========================================"
echo "NeuroInsight Docker-in-Docker Fix"
echo "========================================"
echo ""

# Check if running on WSL
if grep -qi microsoft /proc/version 2>/dev/null; then
    log_info "Detected WSL environment"
    IS_WSL=true
else
    log_info "Detected native Linux environment"
    IS_WSL=false
fi

# Step 1: Check Docker is running
log_info "Step 1: Checking Docker daemon..."
if ! docker ps &>/dev/null; then
    log_error "Docker is not running or not accessible"
    echo ""
    if [ "$IS_WSL" = true ]; then
        echo "WSL Fix:"
        echo "  1. Ensure Docker Desktop is running on Windows"
        echo "  2. Check Docker Desktop → Settings → Resources → WSL Integration"
        echo "  3. Enable integration for your WSL distribution"
        echo "  4. Run: wsl --shutdown (in PowerShell)"
        echo "  5. Restart WSL and Docker Desktop"
    else
        echo "Linux Fix:"
        echo "  sudo systemctl start docker"
        echo "  sudo systemctl enable docker"
    fi
    exit 1
fi
log_success "Docker daemon is running"

# Step 2: Get Docker group ID
log_info "Step 2: Detecting Docker group..."
if ! getent group docker &>/dev/null; then
    log_error "Docker group not found"
    echo ""
    echo "Fix: sudo groupadd docker"
    exit 1
fi

DOCKER_GID=$(getent group docker | cut -d: -f3)
log_success "Docker group ID: $DOCKER_GID"

# Step 3: Check if user is in docker group
log_info "Step 3: Checking user permissions..."
if ! groups | grep -q docker; then
    log_warning "Current user is NOT in docker group"
    echo ""
    echo "Fix:"
    echo "  sudo usermod -aG docker $USER"
    echo "  Then log out and log back in"
    echo ""
    read -p "Add user to docker group now? (y/n): " confirm
    if [ "$confirm" = "y" ]; then
        sudo usermod -aG docker $USER
        log_success "User added to docker group"
        log_warning "You must log out and log back in for changes to take effect"
    fi
else
    log_success "User is in docker group"
fi

# Step 4: Check if container exists
log_info "Step 4: Checking NeuroInsight container..."
CONTAINER_NAME="neuroinsight"

if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_warning "NeuroInsight container does not exist"
    echo ""
    echo "Run: ./neuroinsight-docker install"
    exit 0
fi

# Step 5: Test Docker access from inside container
log_info "Step 5: Testing Docker access from container..."

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    # Container is running - test access
    if docker exec ${CONTAINER_NAME} docker ps &>/dev/null; then
        log_success "Container CAN access Docker socket - DinD is working!"
        echo ""
        log_info "Your setup is correct. If jobs still fail, check:"
        echo "  1. FreeSurfer license: ./neuroinsight-docker license"
        echo "  2. Container logs: ./neuroinsight-docker logs worker"
        exit 0
    else
        log_error "Container CANNOT access Docker socket - DinD is broken"
        echo ""
        log_warning "Fixing by recreating container with docker group access..."
    fi
else
    log_warning "Container is not running"
    echo ""
    log_info "Recreating container with docker group access..."
fi

# Step 6: Fix by recreating container
log_info "Step 6: Recreating container with proper permissions..."

# Stop and remove existing container
if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_info "Stopping container..."
    docker stop ${CONTAINER_NAME} || true
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    log_info "Removing old container..."
    docker rm ${CONTAINER_NAME} || true
fi

# Recreate using the script (which now includes --group-add)
log_info "Reinstalling with Docker group access..."
./neuroinsight-docker install

echo ""
echo "========================================"
echo "Fix Complete!"
echo "========================================"
echo ""
log_success "Container recreated with Docker group access"
echo ""
echo "Next steps:"
echo "  1. Check status: ./neuroinsight-docker status"
echo "  2. Verify Docker access: docker exec neuroinsight docker ps"
echo "  3. Test with a job upload"
echo ""
log_info "If issues persist, check TROUBLESHOOTING.md"
