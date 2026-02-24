#!/bin/bash
# WSL Environment Check Script
# Validates WSL environment before NeuroInsight installation

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "=========================================="
echo "  NeuroInsight WSL Environment Check"
echo "=========================================="
echo ""

ISSUES_FOUND=0
WARNINGS_FOUND=0

# Detect if running on WSL
IS_WSL=false
if grep -qEi "(microsoft|wsl)" /proc/version 2>/dev/null; then
    IS_WSL=true
    echo -e "${GREEN}[OK]${NC} Running on Windows Subsystem for Linux (WSL)"
    
    # Detect WSL version
    if grep -qEi "microsoft-standard-WSL2" /proc/version 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC} WSL2 detected"
    else
        echo -e "${YELLOW}[WARN]${NC} WSL1 detected (WSL2 recommended for better Docker performance)"
        WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
    fi
else
    echo -e "${YELLOW}[WARN]${NC} Not running on WSL (this script is designed for WSL environments)"
    exit 0
fi

echo ""
echo "Checking WSL Configuration..."
echo "----------------------------"

# Check systemd
if systemctl --version &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} systemd is available"
    
    # Check if systemd is enabled in wsl.conf
    if [ -f /etc/wsl.conf ]; then
        if grep -q "systemd=true" /etc/wsl.conf 2>/dev/null; then
            echo -e "${GREEN}[OK]${NC} systemd is enabled in /etc/wsl.conf"
        else
            echo -e "${YELLOW}[WARN]${NC} systemd not explicitly enabled in /etc/wsl.conf"
            WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
        fi
    else
        echo -e "${YELLOW}[WARN]${NC} /etc/wsl.conf not found"
        WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
    fi
else
    echo -e "${RED}[FAIL]${NC} systemd is not available"
    echo "  → NeuroInsight requires systemd for auto-restart functionality"
    echo "  → Enable systemd in /etc/wsl.conf:"
    echo "    [boot]"
    echo "    systemd=true"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Check Docker
echo ""
echo "Checking Docker..."
echo "------------------"

if command -v docker &> /dev/null; then
    echo -e "${GREEN}[OK]${NC} Docker is installed"
    
    # Check if Docker is running
    if docker ps &> /dev/null; then
        echo -e "${GREEN}[OK]${NC} Docker daemon is running"
    elif sg docker -c "docker ps" &> /dev/null; then
        echo -e "${GREEN}[OK]${NC} Docker daemon is running (via docker group)"
    else
        echo -e "${RED}[FAIL]${NC} Docker daemon is not running"
        echo "  → Start Docker Desktop for Windows"
        echo "  → Or install Docker Engine in WSL"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
    
    # Check docker group membership
    if groups | grep -q docker; then
        echo -e "${GREEN}[OK]${NC} User is in docker group"
    else
        echo -e "${YELLOW}[WARN]${NC} User is not in docker group"
        echo "  → Add with: sudo usermod -aG docker \$USER"
        echo "  → Then logout/login or run: newgrp docker"
        WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
    fi
else
    echo -e "${RED}[FAIL]${NC} Docker is not installed"
    echo "  → Install Docker Desktop for Windows (recommended for WSL)"
    echo "  → Or install Docker Engine in WSL"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Check memory
echo ""
echo "Checking System Resources..."
echo "----------------------------"

TOTAL_RAM=$(free -g | awk 'NR==2{printf "%.0f", $2}')
if (( TOTAL_RAM >= 16 )); then
    echo -e "${GREEN}[OK]${NC} RAM: ${TOTAL_RAM}GB (sufficient for MRI processing)"
elif (( TOTAL_RAM >= 11 )); then
    echo -e "${YELLOW}[WARN]${NC} RAM: ${TOTAL_RAM}GB (minimum for testing, 16GB+ recommended)"
    WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
else
    echo -e "${RED}[FAIL]${NC} RAM: ${TOTAL_RAM}GB (insufficient - need 11GB minimum)"
    echo "  → Configure WSL memory in .wslconfig:"
    echo "    [wsl2]"
    echo "    memory=12GB"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Check disk space
AVAILABLE_SPACE=$(df / | tail -1 | awk '{print int($4/1024/1024)}')
if (( AVAILABLE_SPACE >= 35 )); then
    echo -e "${GREEN}[OK]${NC} Disk space: ${AVAILABLE_SPACE}GB available"
else
    echo -e "${RED}[FAIL]${NC} Disk space: ${AVAILABLE_SPACE}GB (need 35GB minimum)"
    echo "  → Free up disk space in WSL"
    echo "  → Or increase WSL disk size"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Check CPU
CPU_CORES=$(nproc)
if (( CPU_CORES >= 4 )); then
    echo -e "${GREEN}[OK]${NC} CPU cores: $CPU_CORES"
else
    echo -e "${YELLOW}[WARN]${NC} CPU cores: $CPU_CORES (4+ recommended)"
    WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
fi

# Check Python
echo ""
echo "Checking Development Tools..."
echo "------------------------------"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    echo -e "${GREEN}[OK]${NC} Python: $PYTHON_VERSION"
    
    # Check python3-venv
    if python3 -c "import ensurepip" &> /dev/null; then
        echo -e "${GREEN}[OK]${NC} python3-venv is installed"
    else
        echo -e "${YELLOW}[WARN]${NC} python3-venv is not installed"
        echo "  → Will be auto-installed during NeuroInsight installation"
        WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
    fi
else
    echo -e "${RED}[FAIL]${NC} Python 3 is not installed"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo -e "${GREEN}[OK]${NC} Node.js: $NODE_VERSION"
else
    echo -e "${YELLOW}[WARN]${NC} Node.js not found"
    echo "  → Will be auto-installed via nvm during installation"
    WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
fi

# Check WSL-specific paths
echo ""
echo "Checking WSL Integration..."
echo "---------------------------"

# Check if Windows filesystem is accessible
if [ -d "/mnt/c" ]; then
    echo -e "${GREEN}[OK]${NC} Windows filesystem accessible at /mnt/c"
else
    echo -e "${YELLOW}[WARN]${NC} Windows filesystem not mounted"
    WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
fi

# Check for common WSL issues
if [ -f /proc/sys/fs/binfmt_misc/WSLInterop ]; then
    echo -e "${GREEN}[OK]${NC} WSL interop is enabled"
else
    echo -e "${YELLOW}[WARN]${NC} WSL interop is disabled"
    WARNINGS_FOUND=$((WARNINGS_FOUND + 1))
fi

# Summary
echo ""
echo "=========================================="
echo "  Summary"
echo "=========================================="
echo ""

if [ $ISSUES_FOUND -eq 0 ] && [ $WARNINGS_FOUND -eq 0 ]; then
    echo -e "${GREEN}[OK] All checks passed!${NC}"
    echo ""
    echo "Your WSL environment is ready for NeuroInsight installation."
    echo ""
    echo "Next steps:"
    echo "  1. Get FreeSurfer license: https://surfer.nmr.mgh.harvard.edu/registration.html"
    echo "  2. Save license as: license.txt"
    echo "  3. Run: ./neuroinsight install"
    exit 0
elif [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${YELLOW}[WARN] $WARNINGS_FOUND warning(s) found${NC}"
    echo ""
    echo "Your WSL environment should work, but some optimizations are recommended."
    echo "Review the warnings above and consider addressing them."
    echo ""
    echo "You can proceed with installation, but may need to manually install some dependencies."
    exit 0
else
    echo -e "${RED}[FAIL] $ISSUES_FOUND critical issue(s) found${NC}"
    if [ $WARNINGS_FOUND -gt 0 ]; then
        echo -e "${YELLOW}[WARN] $WARNINGS_FOUND warning(s) found${NC}"
    fi
    echo ""
    echo "Please fix the critical issues above before installing NeuroInsight."
    echo ""
    echo "Common fixes:"
    echo "  1. Enable systemd in /etc/wsl.conf"
    echo "  2. Install Docker Desktop for Windows"
    echo "  3. Restart WSL: wsl --shutdown (from PowerShell/CMD)"
    exit 1
fi
