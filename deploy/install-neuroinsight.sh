#!/bin/bash
# NeuroInsight One-Click Installer
# Distributed via landing page

set -e

VERSION="v1.0.0"
IMAGE="neuroinsight/allinone"

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

# Banner
clear
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║                     NEUROINSIGHT INSTALLER                    ║
║                                                               ║
║        Automated Hippocampal Segmentation & Analysis          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo ""

# Check Docker
log_info "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed"
    echo ""
    echo "Please install Docker first:"
    echo "  Linux: curl -fsSL https://get.docker.com | sh"
    echo "  Mac: https://docs.docker.com/desktop/install/mac-install/"
    echo "  Windows: https://docs.docker.com/desktop/install/windows-install/"
    exit 1
fi

if ! docker ps &> /dev/null; then
    log_error "Docker is not running or you don't have permissions"
    echo ""
    echo "Solutions:"
    echo "  1. Start Docker Desktop (Mac/Windows)"
    echo "  2. Run: sudo usermod -aG docker $USER (Linux, then log out/in)"
    echo "  3. Run: sudo systemctl start docker (Linux)"
    exit 1
fi

log_success "Docker is ready"
echo ""

# System requirements
log_info "Checking system requirements..."
total_mem=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || echo "unknown")
if [ "$total_mem" != "unknown" ] && [ "$total_mem" -lt 12 ]; then
    log_warning "System has ${total_mem}GB RAM. 16GB+ recommended for optimal performance."
fi

available_space=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$available_space" -lt 50 ]; then
    log_warning "Available disk space: ${available_space}GB. 50GB+ recommended."
fi
echo ""

# Pull image
log_info "Downloading NeuroInsight ${VERSION}..."
log_info "This may take a few minutes (image size: ~1.5GB)..."
echo ""

if docker pull ${IMAGE}:${VERSION}; then
    log_success "Download complete"
else
    log_error "Failed to download image"
    exit 1
fi
echo ""

# Find available port
log_info "Finding available port..."
port=8000
for candidate_port in {8000..8050}; do
    if ! lsof -i:${candidate_port} -sTCP:LISTEN -t >/dev/null 2>&1 && \
       ! netstat -tln 2>/dev/null | grep -q ":${candidate_port} "; then
        port=$candidate_port
        break
    fi
done
log_success "Using port: ${port}"
echo ""

# Check for license
license_mount=""
if [ -f "./license.txt" ]; then
    log_success "Found FreeSurfer license in current directory"
    license_mount="-v $(pwd)/license.txt:/app/license.txt:ro"
elif [ -f "$HOME/license.txt" ]; then
    log_success "Found FreeSurfer license in home directory"
    license_mount="-v $HOME/license.txt:/app/license.txt:ro"
else
    log_warning "FreeSurfer license not found (will run in demo mode)"
    echo ""
    echo "To enable full FreeSurfer functionality:"
    echo "  1. Get free license: https://surfer.nmr.mgh.harvard.edu/registration.html"
    echo "  2. Save as 'license.txt' in current directory"
    echo "  3. Restart container"
fi
echo ""

# Create and start container
log_info "Starting NeuroInsight..."
docker run -d \
    --name neuroinsight \
    -p ${port}:8000 \
    -v neuroinsight-data:/data \
    ${license_mount} \
    --restart unless-stopped \
    ${IMAGE}:${VERSION}

# Wait for startup
log_info "Initializing services (this may take 30-60 seconds)..."
sleep 30

# Check health
max_attempts=12
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if curl -s http://localhost:${port}/health > /dev/null 2>&1; then
        log_success "NeuroInsight is ready!"
        break
    fi
    sleep 5
    attempt=$((attempt + 1))
done

echo ""
cat << EOF
╔═══════════════════════════════════════════════════════════════╗
║                    INSTALLATION COMPLETE!                     ║
╚═══════════════════════════════════════════════════════════════╝

Access NeuroInsight at: http://localhost:${port}

Management Commands:
  docker stop neuroinsight      Stop the application
  docker start neuroinsight     Start the application
  docker restart neuroinsight   Restart the application
  docker logs neuroinsight      View logs

Need Help?
  Documentation: https://neuroinsight.example.com/docs
  Support: support@neuroinsight.example.com

Thank you for using NeuroInsight!

EOF
