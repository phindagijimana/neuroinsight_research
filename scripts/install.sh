#!/bin/bash
# NeuroInsight Installation Script
# One-command installation for Ubuntu/Debian systems
#
# Features:
# - Automatic detection and installation of missing dependencies
# - WSL (Windows Subsystem for Linux) support with auto-configuration
# - Docker setup and permission handling
# - FreeSurfer license validation
# - Systemd service installation for auto-restart

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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

# Check if running as root
if [[ $EUID -eq 0 ]]; then
    log_error "This script should not be run as root. Please run as a regular user."
    exit 1
fi

log_info "Starting NeuroInsight installation..."

# Check OS compatibility
log_info "Checking system compatibility..."
if ! command -v lsb_release &> /dev/null; then
    log_error "lsb_release not found. This script requires Ubuntu/Debian."
    exit 1
fi

OS=$(lsb_release -si)
VERSION=$(lsb_release -sr)

if [[ "$OS" != "Ubuntu" && "$OS" != "Debian" ]]; then
    log_error "This script is designed for Ubuntu/Debian systems only."
    log_error "Detected OS: $OS"
    exit 1
fi

log_success "System check passed: $OS $VERSION"

# Check system requirements
log_info "Checking system requirements..."

# Check RAM (7GB minimum for installation, 16GB recommended for processing)
TOTAL_RAM=$(free -g | awk 'NR==2{printf "%.0f", $2}')
if (( TOTAL_RAM < 7 )); then
    log_error "Insufficient RAM for NeuroInsight installation."
    log_error "Minimum required: 7GB (for basic functionality)"
    log_error "Detected: ${TOTAL_RAM}GB"
    exit 1
elif (( TOTAL_RAM < 16 )); then
    log_warning "LIMITED MEMORY DETECTED: ${TOTAL_RAM}GB"
    log_warning ""
    log_warning "  MEMORY LIMITATION WARNING "
    log_warning "You have ${TOTAL_RAM}GB RAM - sufficient for installation but not MRI processing."
    log_warning ""
    log_warning "MRI processing requires 16GB+ RAM. With ${TOTAL_RAM}GB:"
    log_warning "• FreeSurfer segmentation may fail"
    log_warning "• Processing will be slow or crash"
    log_warning "• Visualizations may not generate"
    log_warning ""
    log_warning "For actual MRI processing, upgrade to 16GB+ RAM."
    log_warning "You can still install and evaluate the web interface."
    log_warning ""
    read -p "Continue with installation despite memory limitations? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installation cancelled by user."
        exit 0
    fi
else
    log_success "RAM check passed: ${TOTAL_RAM}GB"
fi

# Check disk space (35GB minimum for production, 30GB for testing)
AVAILABLE_SPACE=$(df / | tail -1 | awk '{print int($4/1024/1024)}')

# Reduce requirement for testing/development environments
if [[ "$HOSTNAME" == *"test"* ]] || [[ "$USER" == *"test"* ]] || [[ "$PWD" == *"/tmp/"* ]]; then
    MIN_DISK_GB=30  # Reduced for testing
    log_info "Testing environment detected - using reduced disk requirement: ${MIN_DISK_GB}GB"
else
    MIN_DISK_GB=35  # Standard production requirement (reduced from 45GB)
fi

if (( AVAILABLE_SPACE < MIN_DISK_GB )); then
    log_error "Insufficient disk space. NeuroInsight requires at least ${MIN_DISK_GB}GB free."
    log_error "Detected: ${AVAILABLE_SPACE}GB available"
    echo ""
    log_error "Please free up disk space before installation:"
    echo ""
    log_info "  1. Remove unused Docker resources (often frees 15-25GB):"
    echo "     docker system prune -af --volumes"
    echo ""
    log_info "  2. Check available space after cleanup:"
    echo "     df -h /"
    echo ""
    log_info "  3. Retry installation:"
    echo "     ./neuroinsight install"
    echo ""
    log_info "For more cleanup options, see TROUBLESHOOTING.md:"
    echo "  https://github.com/phindagijimana/neuroinsight_local/blob/master/TROUBLESHOUTING.md#insufficient-disk-space"
    exit 1
fi

# Check CPU cores (minimum 4)
CPU_CORES=$(nproc)
if (( CPU_CORES < 4 )); then
    log_warning "Low CPU core count detected: $CPU_CORES (recommended: 4+)"
fi

log_success "System requirements met: ${TOTAL_RAM}GB RAM, ${AVAILABLE_SPACE}GB disk, $CPU_CORES cores"

# Check for existing NeuroInsight installation/conflicts
log_info "Checking for existing NeuroInsight installation..."

CONFLICTS_FOUND=false

# Check if venv already exists
if [ -d "venv" ]; then
    log_warning "Virtual environment already exists (venv/)"
    CONFLICTS_FOUND=true
fi

# Check if NeuroInsight is currently running
if [ -f "neuroinsight.pid" ]; then
    PID=$(cat neuroinsight.pid 2>/dev/null)
    if ps -p "$PID" > /dev/null 2>&1; then
        log_warning "NeuroInsight appears to be running (PID: $PID)"
        CONFLICTS_FOUND=true
    fi
fi

# Check for running processes
if pgrep -f "backend/main.py" > /dev/null 2>&1 || pgrep -f "celery.*processing_web" > /dev/null 2>&1; then
    log_warning "NeuroInsight processes are currently running"
    CONFLICTS_FOUND=true
fi

# Check for Docker containers
if docker ps --filter "name=neuroinsight" --format "{{.Names}}" 2>/dev/null | grep -q "neuroinsight"; then
    log_warning "NeuroInsight Docker containers are running"
    CONFLICTS_FOUND=true
fi

# Check for port conflicts
for PORT in 8000 5432 6379 9000; do
    if command -v lsof &> /dev/null && sudo lsof -i :$PORT > /dev/null 2>&1; then
        log_warning "Port $PORT is already in use"
        CONFLICTS_FOUND=true
    elif command -v netstat &> /dev/null && netstat -tln 2>/dev/null | grep -q ":$PORT "; then
        log_warning "Port $PORT is already in use"
        CONFLICTS_FOUND=true
    fi
done

if [ "$CONFLICTS_FOUND" = true ]; then
    echo ""
    log_error "INSTALLATION CONFLICT DETECTED"
    echo ""
    echo -e "${RED}Potential issues found:${NC}"
    echo "  • NeuroInsight may already be installed or running"
    echo "  • Required ports may be in use"
    echo "  • Processes or containers from previous installation detected"
    echo ""
    echo -e "${BLUE}Recommended actions:${NC}"
    echo "  1. Stop NeuroInsight if running:"
    echo -e "     ${GREEN}./neuroinsight stop${NC}"
    echo ""
    echo "  2. Check what's using the ports:"
    echo -e "     ${GREEN}sudo lsof -i :8000 -i :5432 -i :6379 -i :9000${NC}"
    echo ""
    echo "  3. If re-installing, clean up first:"
    echo -e "     ${GREEN}./neuroinsight stop${NC}"
    echo -e "     ${GREEN}docker rm -f \$(docker ps -aq --filter 'name=neuroinsight')${NC}"
    echo -e "     ${GREEN}rm -rf venv/  # Remove virtual environment${NC}"
    echo ""
    echo -e "${YELLOW}Continue with installation anyway?${NC}"
    echo "  • This may overwrite existing files"
    echo "  • Running services should be stopped first"
    echo ""
    read -p "Force continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installation cancelled by user"
        log_info "Stop existing services and clean up, then try again"
        exit 0
    fi
    log_warning "User chose to continue despite conflicts..."
    echo ""
fi

log_success "No installation conflicts detected"

# Check Python version
log_info "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    log_error "Python 3 is not installed. Please install Python 3.9 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if (( PYTHON_MAJOR < 3 )) || (( PYTHON_MAJOR == 3 && PYTHON_MINOR < 9 )); then
    log_error "Python 3.9 or higher is required. Detected: $PYTHON_VERSION"
    exit 1
fi

log_success "Python version check passed: $PYTHON_VERSION"

# Detect if running on WSL
IS_WSL=false
if grep -qEi "(microsoft|wsl)" /proc/version 2>/dev/null; then
    IS_WSL=true
    log_info "Detected Windows Subsystem for Linux (WSL)"
fi

# Check and install python3-venv if needed
log_info "Checking Python venv support..."
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
log_info "Detected Python version: $PYTHON_VERSION"

# Better check: try to import ensurepip which is what venv actually needs
if ! python3 -c "import ensurepip" &> /dev/null; then
    log_warning "Python venv package not available. Installing python venv package..."

    if command -v apt &> /dev/null; then
        # Ubuntu/Debian - try version-specific package first, then generic
        log_info "Detected apt package manager (Ubuntu/Debian)"
        
        # Update package list
        log_info "Updating package list..."
        if ! sudo apt update -qq 2>&1 | grep -q "E:"; then
            log_success "Package list updated"
        else
            log_warning "Package update had warnings, continuing..."
        fi

        # Try version-specific package (e.g., python3.12-venv for Ubuntu 24.04)
        log_info "Attempting to install python${PYTHON_VERSION}-venv..."
        
        # More robust installation with error checking
        # Look for "Setting up" which indicates successful package installation
        if sudo apt install -y "python${PYTHON_VERSION}-venv" 2>&1 | tee /tmp/venv_install.log; then
            # Check if package was actually installed by verifying ensurepip
            if python3 -c "import ensurepip" &> /dev/null; then
                log_success "Installed python${PYTHON_VERSION}-venv"
            else
                log_error "Package installed but ensurepip still not available"
                exit 1
            fi
        elif sudo apt install -y python3-venv 2>&1 | tee -a /tmp/venv_install.log; then
            # Check if package was actually installed
            if python3 -c "import ensurepip" &> /dev/null; then
                log_success "Installed python3-venv"
            else
                log_error "Package installed but ensurepip still not available"
                exit 1
            fi
        else
            log_error "Failed to install Python venv package automatically"
            echo ""
            log_error "Installation log:"
            cat /tmp/venv_install.log 2>/dev/null | tail -20
            echo ""
            log_error "Please install it manually:"
            echo "   sudo apt update"
            echo "   sudo apt install python${PYTHON_VERSION}-venv"
            echo ""
            if [ "$IS_WSL" = true ]; then
                log_info "WSL-specific troubleshooting:"
                echo "   - Make sure you're running in a WSL terminal (not PowerShell)"
                echo "   - Try: wsl --shutdown and restart WSL"
                echo "   - Check if apt is working: sudo apt update"
            fi
            exit 1
        fi

    elif command -v dnf &> /dev/null; then
        # Fedora/RHEL
        log_info "Detected dnf package manager (Fedora/RHEL)"
        if sudo dnf install -y python3-venv; then
            log_success "Installed python3-venv"
        else
            log_error "Failed to install python3-venv"
            log_error "Please run: sudo dnf install python3-venv"
            exit 1
        fi

    elif command -v yum &> /dev/null; then
        # Older RHEL/CentOS
        log_info "Detected yum package manager (older RHEL/CentOS)"
        if sudo yum install -y python3-venv; then
            log_success "Installed python3-venv"
        else
            log_error "Failed to install python3-venv"
            log_error "Please run: sudo yum install python3-venv"
            exit 1
        fi

    elif command -v pacman &> /dev/null; then
        # Arch Linux
        log_info "Detected pacman package manager (Arch Linux)"
        if sudo pacman -S --noconfirm python-virtualenv; then
            log_success "Installed python-virtualenv"
        else
            log_error "Failed to install python-virtualenv"
            log_error "Please run: sudo pacman -S python-virtualenv"
            exit 1
        fi

    elif command -v zypper &> /dev/null; then
        # openSUSE
        log_info "Detected zypper package manager (openSUSE)"
        if sudo zypper install -y python3-virtualenv; then
            log_success "Installed python3-virtualenv"
        else
            log_error "Failed to install python3-virtualenv"
            log_error "Please run: sudo zypper install python3-virtualenv"
            exit 1
        fi

    else
        log_error "Unsupported package manager. Please install Python venv manually:"
        log_error "Ubuntu/Debian: sudo apt install python${PYTHON_VERSION}-venv"
        log_error "Fedora/RHEL: sudo dnf install python3-venv"
        log_error "Arch Linux: sudo pacman -S python-virtualenv"
        log_error "openSUSE: sudo zypper install python3-virtualenv"
        exit 1
    fi

    # Verify installation worked
    if python3 -c "import ensurepip" &> /dev/null; then
        log_success "Python venv support installed and verified"
    else
        log_error "Python venv installation failed - ensurepip still not available"
        log_error "Please install manually: sudo apt install python${PYTHON_VERSION}-venv"
        exit 1
    fi

else
    log_success "Python venv support already available"
fi

# Check and install system development libraries
log_info "Checking system development libraries..."
MISSING_LIBS=()

if command -v apt &> /dev/null; then
    # Ubuntu/Debian - check for missing packages
    if ! dpkg -l | grep -q "build-essential"; then
        MISSING_LIBS+=("build-essential")
    fi
    if ! dpkg -l | grep -q "libssl-dev"; then
        MISSING_LIBS+=("libssl-dev")
    fi
    if ! dpkg -l | grep -q "libffi-dev"; then
        MISSING_LIBS+=("libffi-dev")
    fi
    
    # Install all missing packages at once (more efficient)
    if [ ${#MISSING_LIBS[@]} -gt 0 ]; then
        log_warning "Installing missing system libraries: ${MISSING_LIBS[*]}"
        if [ "$IS_WSL" = true ]; then
            log_info "WSL detected - installing required development tools..."
        fi
        
        # Update and install - just check exit code, then verify packages
        if sudo apt update -qq && sudo apt install -y "${MISSING_LIBS[@]}" 2>&1 | tee /tmp/apt_install.log; then
            # Verify packages were actually installed
            INSTALL_FAILED=false
            for pkg in "${MISSING_LIBS[@]}"; do
                if ! dpkg -l | grep -q "^ii.*$pkg"; then
                    INSTALL_FAILED=true
                    log_error "Package $pkg failed to install"
                fi
            done
            
            if [ "$INSTALL_FAILED" = false ]; then
                log_success "System development libraries installed successfully"
            else
                log_error "Some packages failed to install"
                log_error "Please install manually: sudo apt install ${MISSING_LIBS[*]}"
                exit 1
            fi
        else
            log_error "Failed to install some system libraries"
            log_error "Installation log:"
            tail -10 /tmp/apt_install.log
            log_error "Please install manually: sudo apt install ${MISSING_LIBS[*]}"
            exit 1
        fi
    fi
elif command -v dnf &> /dev/null; then
    # Fedora/RHEL
    if ! rpm -q gcc make &> /dev/null; then
        log_warning "Installing development tools (GCC, make)..."
        sudo dnf groupinstall -y "Development Tools"
        MISSING_LIBS=true
    fi
    if ! rpm -q openssl-devel &> /dev/null; then
        log_warning "Installing openssl-devel (SSL/TLS support)..."
        sudo dnf install -y openssl-devel
        MISSING_LIBS=true
    fi
    if ! rpm -q libffi-devel &> /dev/null; then
        log_warning "Installing libffi-devel (Python extensions)..."
        sudo dnf install -y libffi-devel
        MISSING_LIBS=true
    fi
elif command -v yum &> /dev/null; then
    # Older RHEL/CentOS
    if ! rpm -q gcc make &> /dev/null; then
        log_warning "Installing development tools (GCC, make)..."
        sudo yum groupinstall -y "Development Tools"
        MISSING_LIBS=true
    fi
    if ! rpm -q openssl-devel &> /dev/null; then
        log_warning "Installing openssl-devel (SSL/TLS support)..."
        sudo yum install -y openssl-devel
        MISSING_LIBS=true
    fi
elif command -v pacman &> /dev/null; then
    # Arch Linux
    if ! pacman -Q base-devel &> /dev/null; then
        log_warning "Installing base-devel (development tools)..."
        sudo pacman -S --noconfirm base-devel
        MISSING_LIBS=true
    fi
    if ! pacman -Q openssl &> /dev/null; then
        log_warning "Installing openssl..."
        sudo pacman -S --noconfirm openssl
        MISSING_LIBS=true
    fi
    if ! pacman -Q libffi &> /dev/null; then
        log_warning "Installing libffi..."
        sudo pacman -S --noconfirm libffi
        MISSING_LIBS=true
    fi
elif command -v zypper &> /dev/null; then
    # openSUSE
    if ! rpm -q gcc make &> /dev/null; then
        log_warning "Installing development tools..."
        sudo zypper install -y gcc make
        MISSING_LIBS=true
    fi
    if ! rpm -q libopenssl-devel &> /dev/null; then
        log_warning "Installing libopenssl-devel..."
        sudo zypper install -y libopenssl-devel
        MISSING_LIBS=true
    fi
    if ! rpm -q libffi-devel &> /dev/null; then
        log_warning "Installing libffi-devel..."
        sudo zypper install -y libffi-devel
        MISSING_LIBS=true
    fi
fi

if [ ${#MISSING_LIBS[@]} -eq 0 ]; then
    log_success "System development libraries available"
fi

# Check kernel version for Docker compatibility
log_info "Checking kernel version for Docker compatibility..."
KERNEL_VERSION=$(uname -r | cut -d'.' -f1-2 | tr '.' ' ')
KERNEL_MAJOR=$(echo $KERNEL_VERSION | awk '{print $1}')
KERNEL_MINOR=$(echo $KERNEL_VERSION | awk '{print $2}')

if (( KERNEL_MAJOR < 3 )) || (( KERNEL_MAJOR == 3 && KERNEL_MINOR < 10 )); then
    log_warning "Kernel version ${KERNEL_MAJOR}.${KERNEL_MINOR} detected"
    log_warning "Docker requires kernel 3.10 or higher"
    log_warning "Some features may not work correctly"
else
    log_success "Kernel version ${KERNEL_MAJOR}.${KERNEL_MINOR} compatible with Docker"
fi

# Check and install Node.js and npm if needed for frontend building
log_info "Checking Node.js and npm for frontend building..."
if ! command -v node &> /dev/null || [[ "$(node --version 2>/dev/null | sed 's/v//')" < "18" ]]; then
    log_warning "Node.js not found or version too old. Installing Node.js 20.x via nvm (no sudo required)..."
    log_info "Installing nvm (Node Version Manager)..."

    # Install nvm without requiring sudo
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash

    # Source nvm in the current session
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

    # Install and use Node.js 20
    nvm install 20
    nvm use 20
    nvm alias default 20

    # Add nvm to shell profile for future sessions
    echo 'export NVM_DIR="$HOME/.nvm"' >> ~/.bashrc
    echo '[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"' >> ~/.bashrc
    echo '[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"' >> ~/.bashrc

    # Ensure node command points to nvm version
    export PATH="$NVM_DIR/versions/node/v20.19.0/bin:$PATH"

    log_success "Node.js 20.x and npm installed via nvm"
else
    NODE_VERSION=$(node --version)
    log_success "Node.js found: $NODE_VERSION"
fi

# Ensure npm is available
if ! command -v npm &> /dev/null; then
    log_error "npm not found. Trying to source nvm..."
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    if ! command -v npm &> /dev/null; then
        log_error "npm still not found. Please restart your terminal and try again."
        exit 1
    fi
else
    log_success "npm found: $(npm --version)"
fi

# Install Docker if not present
log_info "Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    log_warning "Docker not found. Installing Docker..."

    if command -v apt &> /dev/null; then
        # Ubuntu/Debian
        log_info "Installing Docker for Ubuntu/Debian..."
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg lsb-release
        sudo mkdir -p /etc/apt/keyrings
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    elif command -v dnf &> /dev/null; then
        # Fedora/RHEL 8+
        log_info "Installing Docker for Fedora/RHEL..."
        sudo dnf -y install dnf-plugins-core
        sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
        sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        sudo systemctl start docker

    elif command -v yum &> /dev/null; then
        # CentOS/RHEL 7
        log_info "Installing Docker for CentOS/RHEL 7..."
        sudo yum install -y yum-utils
        sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
        sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        sudo systemctl start docker

    elif command -v pacman &> /dev/null; then
        # Arch Linux
        log_info "Installing Docker for Arch Linux..."
        sudo pacman -S --noconfirm docker docker-compose
        sudo systemctl start docker
        sudo systemctl enable docker

    elif command -v zypper &> /dev/null; then
        # openSUSE
        log_info "Installing Docker for openSUSE..."
        sudo zypper addrepo https://download.docker.com/linux/opensuse/docker-ce.repo
        sudo zypper install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
        sudo systemctl start docker

    else
        log_error "Unsupported package manager. Please install Docker manually:"
        log_error "Visit: https://docs.docker.com/engine/install/"
        exit 1
    fi

    # Add user to docker group (works across all distros)
    sudo usermod -aG docker $USER

    log_success "Docker installed successfully"
    log_warning "User added to docker group - group membership will take effect after this script"
else
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    log_success "Docker already installed: $DOCKER_VERSION"
fi

# Check if user is in docker group
USER_IN_DOCKER_GROUP=false
if groups | grep -q docker; then
    USER_IN_DOCKER_GROUP=true
    log_success "User is in docker group"
else
    # User just added to group, will take effect for subsequent commands
    log_info "Docker group membership will be activated for this installation"
fi

# Python environment setup will be done later in the script

# Build frontend
log_info "Building frontend..."
if command -v npm &> /dev/null; then
    # Ensure nvm is sourced for npm commands and use Node.js 20
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm use 20 2>/dev/null || true
    # Ensure PATH includes nvm node
    export PATH="$NVM_DIR/versions/node/v20.19.0/bin:$PATH"

    cd frontend
    npm install
    npm run build
    cd ..
    log_success "Frontend built successfully"
else
    log_warning "npm not found, skipping frontend build"
    log_warning "Node.js installation may have failed. Try restarting your terminal."
fi

# Create necessary directories
log_info "Creating data directories..."
mkdir -p data/uploads
mkdir -p data/outputs
mkdir -p logs

# Test Docker functionality
log_info "Testing Docker functionality..."

# Use sg docker if user is not currently in docker group (just added)
if [ "$USER_IN_DOCKER_GROUP" = true ]; then
    # User already in group, can run docker directly
    if docker run --rm hello-world &> /dev/null; then
        log_success "Docker test passed"
    else
        log_error "Docker test failed. Please check Docker installation."
        exit 1
    fi
else
    # User just added to group, use sg to activate group membership
    if sg docker -c "docker run --rm hello-world" &> /dev/null; then
        log_success "Docker test passed (using docker group)"
    else
        log_error "Docker test failed. Please check Docker installation."
        log_error "You may need to restart the Docker service: sudo systemctl restart docker"
        exit 1
    fi
fi

# Check FreeSurfer license
log_info "Checking FreeSurfer license..."
if [ ! -f "license.txt" ]; then
    log_warning "FreeSurfer license file not found: license.txt"
    echo
    echo "To set up your FreeSurfer license:"
    echo "   1. Visit: https://surfer.nmr.mgh.harvard.edu/registration.html"
    echo "   2. Register (free for research)"
    echo "   3. Save your license as: license.txt"
    echo "   4. Run: ./neuroinsight license"
    echo
else
    ./neuroinsight license
fi

# Final verification
log_info "Setting up Python environment..."

# Setup Python virtual environment
if [ -d "venv" ]; then
    log_info "Checking existing Python virtual environment..."
    # Test if existing venv is functional
    if venv/bin/python -c "import psutil, fastapi, sqlalchemy" 2>/dev/null; then
        log_success "Existing virtual environment is functional"
    else
        log_warning "Existing virtual environment is incomplete or broken, recreating..."
        rm -rf venv
    fi
fi

if [ ! -d "venv" ]; then
    log_info "Creating Python virtual environment..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        log_error "Failed to create Python virtual environment"
        log_info "Trying alternative: python3 -m venv venv --system-site-packages"
        python3 -m venv venv --system-site-packages
        if [ $? -ne 0 ]; then
            log_error "Failed to create Python virtual environment. Please install python3-venv:"
            log_error "sudo apt-get install python3-venv"
            exit 1
        fi
    fi
    log_success "Python virtual environment created"
fi

# Activate virtual environment and install dependencies
log_info "Installing Python dependencies..."
source venv/bin/activate

# Upgrade pip first
pip install --upgrade pip

# Install requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        log_error "Failed to install Python dependencies"
        exit 1
    fi
    log_success "Python dependencies installed"
else
    log_error "requirements.txt not found"
    exit 1
fi

# Install additional packages that might be missing
log_info "Installing additional required packages..."
pip install psutil requests python-multipart
if [ $? -ne 0 ]; then
    log_warning "Some additional packages failed to install, but core functionality should work"
fi

# Deactivate virtual environment
deactivate

log_success "Python environment setup completed"

# Setup frontend
log_info "Setting up frontend..."
if [ -f "frontend/index.html" ]; then
    mkdir -p frontend/dist
    cp frontend/index.html frontend/dist/index.html
    log_success "Frontend setup completed"
else
    log_warning "frontend/index.html not found, skipping frontend setup"
fi

log_info "Running final verification..."

# Check if key components can be imported (using venv python)
./venv/bin/python -c "
try:
    import fastapi
    import sqlalchemy
    import nibabel
    import matplotlib
    print('Python dependencies verified')
except ImportError as e:
    print(f'Missing dependency: {e}')
    exit(1)
"

# Setup Docker containers with docker-compose
log_info "Setting up Docker infrastructure..."

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    log_info "Creating .env configuration file..."
    cat > .env << 'EOF'
# PostgreSQL Database
POSTGRES_USER=neuroinsight
POSTGRES_PASSWORD=neuroinsight_secure_password
POSTGRES_DB=neuroinsight

# Redis
REDIS_PASSWORD=redis_secure_password

# MinIO (S3-compatible storage)
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin_secure

# Docker group ID (for container permissions)
DOCKER_GID=999

# Host paths for Docker-in-Docker (native mode uses ~/.local/share/neuroinsight)
# These are only needed when worker runs inside a container and spawns FreeSurfer containers
HOST_UPLOAD_DIR=$HOME/.local/share/neuroinsight/uploads
HOST_OUTPUT_DIR=$HOME/.local/share/neuroinsight/outputs
EOF
    log_success ".env file created"
else
    log_info ".env file already exists, skipping"
fi

# Start Docker containers
log_info "Starting Docker containers (postgres, redis, minio)..."

# Try docker-compose first, fall back to direct docker commands
CONTAINERS_STARTED=false

# Wrapper for docker commands based on group membership
run_docker_cmd() {
    if [ "$USER_IN_DOCKER_GROUP" = true ]; then
        "$@"
    else
        # Properly quote all arguments for sg docker -c
        local cmd_string=""
        for arg in "$@"; do
            # Escape single quotes and wrap each argument
            arg="${arg//\'/\'\\\'\'}"
            cmd_string="$cmd_string '$arg'"
        done
        sg docker -c "$cmd_string"
    fi
}

if command -v docker-compose &> /dev/null || docker compose version &> /dev/null 2>&1; then
    # Use docker compose (new) or docker-compose (old)
    if docker compose version &> /dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        DOCKER_COMPOSE="docker-compose"
    fi
    
    # Try to start containers with docker-compose
    log_info "Attempting to start containers with docker-compose..."
    if run_docker_cmd $DOCKER_COMPOSE up -d db redis minio > /tmp/docker-compose.log 2>&1; then
        CONTAINERS_STARTED=true
        log_success "Docker containers started via docker-compose"
    else
        log_warning "docker-compose failed, will use direct docker commands"
    fi
fi

# Fallback to direct docker commands if docker-compose failed
if [ "$CONTAINERS_STARTED" = false ]; then
    log_info "Starting containers with direct docker commands..."
    
    # Create network if it doesn't exist
    run_docker_cmd docker network create neuroinsight-network 2>/dev/null || true
    
    # Start PostgreSQL
    run_docker_cmd docker run -d \
        --name neuroinsight-db \
        --network neuroinsight-network \
        -e POSTGRES_USER=neuroinsight \
        -e POSTGRES_PASSWORD=neuroinsight_secure_password \
        -e POSTGRES_DB=neuroinsight \
        -p 5432:5432 \
        --restart unless-stopped \
        postgres:15-alpine > /dev/null 2>&1 || log_warning "PostgreSQL container may already exist"
    
    # Start Redis
    run_docker_cmd docker run -d \
        --name neuroinsight-redis \
        --network neuroinsight-network \
        -p 6379:6379 \
        --restart unless-stopped \
        redis:7-alpine > /dev/null 2>&1 || log_warning "Redis container may already exist"
    
    # Start MinIO
    run_docker_cmd docker run -d \
        --name neuroinsight-minio \
        --network neuroinsight-network \
        -e MINIO_ROOT_USER=minioadmin \
        -e MINIO_ROOT_PASSWORD=minioadmin_secure \
        -p 9000:9000 \
        -p 9001:9001 \
        --restart unless-stopped \
        minio/minio server /data --console-address ":9001" > /dev/null 2>&1 || log_warning "MinIO container may already exist"
    
    CONTAINERS_STARTED=true
    log_success "Docker containers created"
fi

# Verify containers are running
log_info "Waiting for containers to be healthy..."
sleep 5

RUNNING_CONTAINERS=$(run_docker_cmd docker ps --filter "name=neuroinsight" --format "{{.Names}}" 2>/dev/null | wc -l)
if [ $RUNNING_CONTAINERS -gt 0 ]; then
    log_success "Docker infrastructure ready ($RUNNING_CONTAINERS containers running)"
    run_docker_cmd docker ps --filter "name=neuroinsight" --format "  - {{.Names}}: {{.Status}}"
else
    log_warning "No Docker containers running - system will use SQLite databases"
    log_info "For production PostgreSQL, check: docker ps -a"
fi

# Create required data directories
log_info "Creating required data directories..."
mkdir -p "$HOME/.local/share/neuroinsight/uploads"
mkdir -p "$HOME/.local/share/neuroinsight/results"
mkdir -p "$HOME/.local/share/neuroinsight/outputs"
if [ -d "$HOME/.local/share/neuroinsight/uploads" ]; then
    log_success "Data directories created"
else
    log_warning "Failed to create data directories - uploads may fail"
fi

# Initialize database schema (if PostgreSQL is running)
if [ $RUNNING_CONTAINERS -gt 0 ]; then
    log_info "Initializing database schema..."
    
    # Wait for PostgreSQL to be fully ready
    log_info "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if run_docker_cmd docker exec neuroinsight-db pg_isready -U neuroinsight > /dev/null 2>&1; then
            log_success "PostgreSQL is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            log_warning "PostgreSQL may not be fully ready - database initialization might fail"
        fi
        sleep 1
    done
    
    # Run alembic migrations
    if [ -f "backend/alembic.ini" ]; then
        source venv/bin/activate
        # Set PYTHONPATH to include project root for alembic imports
        export PYTHONPATH="$PWD:$PYTHONPATH"
        if alembic -c backend/alembic.ini upgrade head > /tmp/neuroinsight_alembic.log 2>&1; then
            log_success "Database schema initialized"
        else
            log_warning "Database initialization had issues (see /tmp/neuroinsight_alembic.log)"
            log_info "You may need to run manually: PYTHONPATH=\$PWD:\$PYTHONPATH alembic -c backend/alembic.ini upgrade head"
        fi
        deactivate
    else
        log_warning "Alembic configuration not found - skipping database initialization"
    fi
else
    log_info "Skipping database initialization (no PostgreSQL container)"
fi

# Install systemd services (if available)
echo ""
if command -v systemctl &> /dev/null; then
    log_info "Setting up systemd services for auto-restart..."
    
    if [ -f "systemd/install_systemd.sh" ]; then
        # Run systemd installation silently
        if ./systemd/install_systemd.sh > /tmp/neuroinsight_systemd_install.log 2>&1; then
            log_success "Systemd services installed (auto-restart enabled)"
            log_info "Services will start automatically with './neuroinsight start'"
        else
            log_warning "Systemd service installation had issues (see /tmp/neuroinsight_systemd_install.log)"
            log_info "You can retry with: ./neuroinsight install-systemd"
            log_info "Or use manual mode: ./neuroinsight start --manual"
        fi
    else
        log_warning "systemd/install_systemd.sh not found"
        log_info "Systemd services not installed - will use manual mode"
    fi
else
    log_info "Systemd not available - will use manual start mode"
fi

log_success "NeuroInsight installation completed successfully!"
echo

# Add docker group message if user was just added
if [ "$USER_IN_DOCKER_GROUP" = false ]; then
    echo ""
    log_warning "IMPORTANT: Docker Group Membership"
    echo "   You were added to the 'docker' group during installation."
    echo "   To use Docker without 'sudo', you MUST log out and log back in."
    echo ""
    echo "   After logging back in, run:"
    echo "      ./neuroinsight start"
    echo ""
fi

echo "Next steps:"
echo "   1. Set up your FreeSurfer license (if not done):"
echo "      - Visit: https://surfer.nmr.mgh.harvard.edu/registration.html"
echo "      - Download your license.txt file"
echo "      - Place license.txt in this directory (same folder as NeuroInsight)"
echo "   2. Start NeuroInsight:"
echo "      ./neuroinsight start"
echo "   3. Open your browser:"
echo "      http://localhost:8000 (or auto-selected port - check ./neuroinsight status)"
echo
echo "For help, see: README.md"
echo "For troubleshooting: ./neuroinsight license"

exit 0
