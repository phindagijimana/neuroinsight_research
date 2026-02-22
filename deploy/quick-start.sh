#!/bin/bash
# Quick start script for NeuroInsight all-in-one Docker container

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

echo "======================================"
echo "NeuroInsight Quick Start"
echo "======================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed."
    echo ""
    echo "Please install Docker first:"
    echo "  Linux: curl -fsSL https://get.docker.com | sh"
    echo "  macOS/Windows: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if container already exists
if docker ps -a --format '{{.Names}}' | grep -q '^neuroinsight$'; then
    log_warning "NeuroInsight container already exists."
    echo ""
    echo "Would you like to:"
    echo "  1) Start existing container"
    echo "  2) Remove and recreate"
    echo "  3) Exit"
    echo ""
    read -p "Enter choice (1-3): " choice
    
    case $choice in
        1)
            log_info "Starting existing container..."
            docker start neuroinsight
            ;;
        2)
            log_info "Removing existing container..."
            docker rm -f neuroinsight
            ;;
        3)
            exit 0
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac
fi

# Check if image exists locally
if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q 'neuroinsight/allinone:latest'; then
    log_warning "Image not found locally."
    echo ""
    echo "Would you like to:"
    echo "  1) Pull from Docker Hub (requires internet)"
    echo "  2) Build locally (requires source code)"
    echo "  3) Exit"
    echo ""
    read -p "Enter choice (1-3): " choice
    
    case $choice in
        1)
            log_info "Pulling image from Docker Hub..."
            docker pull neuroinsight/allinone:latest
            ;;
        2)
            log_info "Building image locally..."
            ./build.sh
            ;;
        3)
            exit 0
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac
fi

# Check for FreeSurfer license
log_info "Checking for FreeSurfer license..."
LICENSE_PATH=""

if [ -f "./license.txt" ]; then
    LICENSE_PATH="./license.txt"
    log_success "Found license.txt in current directory"
elif [ -f "../neuroinsight_local/license.txt" ]; then
    LICENSE_PATH="../neuroinsight_local/license.txt"
    log_success "Found license.txt in neuroinsight_local directory"
else
    log_warning "FreeSurfer license not found."
    echo ""
    echo "The application will run in demo mode with mock processing."
    echo ""
    echo "To enable full FreeSurfer functionality:"
    echo "  1. Visit: https://surfer.nmr.mgh.harvard.edu/registration.html"
    echo "  2. Register (free for research)"
    echo "  3. Download license.txt"
    echo "  4. Place it in this directory and restart"
    echo ""
    read -p "Continue without license? (y/n): " continue_without_license
    
    if [ "$continue_without_license" != "y" ]; then
        exit 0
    fi
fi

# Start the container
log_info "Starting NeuroInsight container..."
echo ""

if [ -n "$LICENSE_PATH" ]; then
    docker run -d \
        --name neuroinsight \
        -p 8000:8000 \
        -p 9000:9000 \
        -p 9001:9001 \
        -v neuroinsight-data:/data \
        -v "$(pwd)/$LICENSE_PATH:/app/license.txt:ro" \
        --restart unless-stopped \
        neuroinsight/allinone:latest
else
    docker run -d \
        --name neuroinsight \
        -p 8000:8000 \
        -p 9000:9000 \
        -p 9001:9001 \
        -v neuroinsight-data:/data \
        --restart unless-stopped \
        neuroinsight/allinone:latest
fi

log_success "Container started!"
echo ""

# Wait for services to be ready
log_info "Waiting for services to start (this may take 30-60 seconds)..."
for i in {1..30}; do
    if docker exec neuroinsight /app/healthcheck.sh > /dev/null 2>&1; then
        log_success "All services are ready!"
        break
    fi
    echo -n "."
    sleep 2
done
echo ""

# Display status
log_info "Container status:"
docker ps --filter name=neuroinsight --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

log_success "NeuroInsight is now running!"
echo ""
echo "======================================"
echo "Access Information"
echo "======================================"
echo ""
echo "Web Interface:      http://localhost:8000"
echo "MinIO Console:      http://localhost:9001"
echo ""
echo "======================================"
echo "Management Commands"
echo "======================================"
echo ""
echo "View logs:          docker logs -f neuroinsight"
echo "Check health:       docker exec neuroinsight /app/healthcheck.sh"
echo "Stop:               docker stop neuroinsight"
echo "Start:              docker start neuroinsight"
echo "Remove:             docker rm -f neuroinsight"
echo ""
echo "For more help, see: README.md"
echo ""
