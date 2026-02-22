#!/bin/bash
# NeuroInsight Docker Release Management Script
# Handles versioning, building, tagging, and publishing releases

set -e

IMAGE_NAME="phindagijimana321/neuroinsight"

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

# Show help
show_help() {
    cat << 'EOF'
NeuroInsight Docker Release Management

Usage: ./release.sh <command> [version]

Commands:
  build <version>    - Build a versioned image (e.g., v1.0.0)
  publish <version>  - Build and push to Docker Hub
  list               - List all local images
  tag <from> <to>    - Create new tag from existing
  delete <version>   - Delete local image
  latest <version>   - Tag version as latest

Examples:
  # Build a new version
  ./release.sh build v1.0.0

  # Build and publish to Docker Hub
  ./release.sh publish v1.0.0

  # List all versions
  ./release.sh list

  # Tag a version as latest
  ./release.sh latest v1.0.0

  # Create additional tags
  ./release.sh tag v1.0.0 v1.0
  ./release.sh tag v1.0.0 stable

Version Naming:
  - Semantic versioning: v1.0.0, v1.1.0, v2.0.0
  - Pre-release: v1.0.0-beta, v1.0.0-rc1
  - Testing: test, dev
  - Production: latest, stable

EOF
}

# Build a version
cmd_build() {
    local version="$1"
    
    if [ -z "$version" ]; then
        log_error "Please specify version"
        echo "Usage: ./release.sh build <version>"
        echo "Example: ./release.sh build v1.0.0"
        exit 1
    fi
    
    log_info "Building version: $version"
    ./build.sh "$version"
}

# Publish to Docker Hub
cmd_publish() {
    local version="$1"
    
    if [ -z "$version" ]; then
        log_error "Please specify version"
        echo "Usage: ./release.sh publish <version>"
        echo "Example: ./release.sh publish v1.0.0"
        exit 1
    fi
    
    echo "======================================"
    echo "Publishing NeuroInsight $version"
    echo "======================================"
    echo ""
    
    # Check if logged in to Docker Hub
    log_info "Checking Docker Hub authentication..."
    if ! docker info 2>/dev/null | grep -q "Username"; then
        log_warning "Not logged in to Docker Hub"
        echo ""
        log_info "Please login to Docker Hub:"
        docker login
    else
        log_success "Already logged in to Docker Hub"
    fi
    
    # Build the image
    log_info "Building image..."
    ./build.sh "$version"
    
    # Push version tag
    log_info "Pushing ${IMAGE_NAME}:${version} to Docker Hub..."
    docker push "${IMAGE_NAME}:${version}"
    log_success "Pushed ${IMAGE_NAME}:${version}"
    
    # Push latest tag if this is a production version
    if [[ ! "$version" =~ (beta|alpha|rc|dev|test) ]]; then
        log_info "This is a production version, also pushing as 'latest'..."
        docker push "${IMAGE_NAME}:latest"
        log_success "Pushed ${IMAGE_NAME}:latest"
    else
        log_warning "Pre-release version, not updating 'latest' tag"
    fi
    
    echo ""
    log_success "Release published successfully!"
    echo ""
    echo "Users can now run:"
    echo "  docker pull ${IMAGE_NAME}:${version}"
    echo ""
    echo "Docker Hub: https://hub.docker.com/r/${IMAGE_NAME}"
    echo ""
}

# List all images
cmd_list() {
    echo "======================================"
    echo "NeuroInsight Docker Images"
    echo "======================================"
    echo ""
    
    docker images "${IMAGE_NAME}" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
    
    echo ""
    log_info "To see Docker Hub versions:"
    echo "  Visit: https://hub.docker.com/r/${IMAGE_NAME}/tags"
}

# Tag an image
cmd_tag() {
    local from_version="$1"
    local to_version="$2"
    
    if [ -z "$from_version" ] || [ -z "$to_version" ]; then
        log_error "Please specify source and target versions"
        echo "Usage: ./release.sh tag <from_version> <to_version>"
        echo "Example: ./release.sh tag v1.0.0 stable"
        exit 1
    fi
    
    log_info "Creating tag: ${IMAGE_NAME}:${to_version} from ${IMAGE_NAME}:${from_version}"
    docker tag "${IMAGE_NAME}:${from_version}" "${IMAGE_NAME}:${to_version}"
    log_success "Tag created successfully"
    
    cmd_list
}

# Delete an image
cmd_delete() {
    local version="$1"
    
    if [ -z "$version" ]; then
        log_error "Please specify version to delete"
        echo "Usage: ./release.sh delete <version>"
        exit 1
    fi
    
    if [ "$version" == "latest" ]; then
        log_error "Cannot delete 'latest' tag. Delete specific versions only."
        exit 1
    fi
    
    log_warning "This will delete ${IMAGE_NAME}:${version} locally"
    read -p "Continue? (y/n): " confirm
    if [ "$confirm" != "y" ]; then
        exit 0
    fi
    
    docker rmi "${IMAGE_NAME}:${version}"
    log_success "Image deleted"
}

# Tag version as latest
cmd_latest() {
    local version="$1"
    
    if [ -z "$version" ]; then
        log_error "Please specify version"
        echo "Usage: ./release.sh latest <version>"
        echo "Example: ./release.sh latest v1.0.0"
        exit 1
    fi
    
    log_info "Tagging ${version} as latest..."
    docker tag "${IMAGE_NAME}:${version}" "${IMAGE_NAME}:latest"
    log_success "Tagged as latest"
    
    log_info "To push to Docker Hub:"
    echo "  docker push ${IMAGE_NAME}:latest"
}

# Main command dispatcher
case "${1:-help}" in
    build)
        cmd_build "$2"
        ;;
    publish)
        cmd_publish "$2"
        ;;
    list|ls)
        cmd_list
        ;;
    tag)
        cmd_tag "$2" "$3"
        ;;
    delete|remove)
        cmd_delete "$2"
        ;;
    latest)
        cmd_latest "$2"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
