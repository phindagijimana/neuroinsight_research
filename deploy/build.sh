#!/bin/bash
# Build script for NeuroInsight all-in-one Docker image

set -e

echo "======================================"
echo "NeuroInsight All-in-One Docker Build"
echo "======================================"
echo ""

# Configuration
IMAGE_NAME="phindagijimana321/neuroinsight"
VERSION="${1:-latest}"
DOCKERFILE="Dockerfile"
CONTEXT=".."  # Parent directory (neuroinsight_local)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if we're in the correct directory
if [ ! -f "$DOCKERFILE" ]; then
    log_error "Dockerfile not found. Please run this script from the deploy/ directory."
    exit 1
fi

# Check if source code exists
if [ ! -d "$CONTEXT" ]; then
    log_error "Source code directory not found: $CONTEXT"
    log_error "Make sure you're running this from the deploy/ directory."
    exit 1
fi

log_info "Building Docker image..."
log_info "Image: $IMAGE_NAME:$VERSION"
log_info "Context: $CONTEXT"
echo ""

# Build the image
log_info "Running docker build..."
docker build \
    -t "$IMAGE_NAME:$VERSION" \
    -f "$DOCKERFILE" \
    "$CONTEXT"

# Tag as latest if building a version
if [ "$VERSION" != "latest" ]; then
    log_info "Tagging as latest..."
    docker tag "$IMAGE_NAME:$VERSION" "$IMAGE_NAME:latest"
fi

log_success "Build completed successfully!"
echo ""

# Display image info
log_info "Image details:"
docker images "$IMAGE_NAME" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
echo ""

log_info "To run the container:"
echo "  docker run -d --name neuroinsight -p 8000:8000 -v neuroinsight-data:/data $IMAGE_NAME:$VERSION"
echo ""

log_info "Or using docker-compose:"
echo "  docker-compose up -d"
echo ""

log_info "To push to Docker Hub:"
echo "  docker login"
echo "  docker push $IMAGE_NAME:$VERSION"
if [ "$VERSION" != "latest" ]; then
    echo "  docker push $IMAGE_NAME:latest"
fi
echo ""

log_success "Done!"
