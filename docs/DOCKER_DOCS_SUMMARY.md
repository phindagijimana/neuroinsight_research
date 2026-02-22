# Docker Documentation Summary

## Overview
Updated USER_GUIDE.md and TROUBLESHOOTING.md to include comprehensive Docker deployment information for both Linux and Windows platforms.

---

## USER_GUIDE.md Updates

### 1. Added Deployment Options Section
**Location:** After "Prerequisites", before "Installation"

**Content:**
- Comparison table of 3 deployment types (Native, Linux Docker, Windows Docker)
- Best use cases for each deployment
- Requirements summary

### 2. Added Option 2: Linux Docker Installation
**Location:** After native installation section

**Includes:**
- Prerequisites (Docker Engine, Docker Compose, system requirements)
- Step-by-step installation commands
- 15+ management commands with examples:
  - Core operations (start, stop, restart, status, health)
  - Logs and monitoring (logs, logs backend, logs worker)
  - Data management (clean, backup, restore)
  - Maintenance (update, license)
- What's included in the container
- Data persistence explanation
- Backup recommendations

### 3. Added Option 3: Windows Docker Installation
**Location:** After Linux Docker section

**Includes:**
- Prerequisites (Windows version, Docker Desktop, WSL2)
- Docker Desktop installation steps
- FreeSurfer license setup
- Installation commands (PowerShell + Command Prompt)
- 12+ management commands in PowerShell syntax
- Docker Desktop configuration recommendations
- Windows-specific notes:
  - WSL2 integration
  - Port detection
  - Colored PowerShell output
  - Same Linux image usage

### 4. Added Deployment Comparison Table
**Location:** End of installation options

**Compares:**
- Installation method
- Update process
- Backup/restore capabilities
- Isolation level
- Performance characteristics
- Portability
- Dependency management

---

## TROUBLESHOOTING.md Updates

### 1. Added Deployment-Specific Issues Section
**Location:** After "Quick Diagnosis", before "Common Issues"

**New Subsection: Docker Deployment Issues**

Covers 9 major Docker issue categories:

#### Container Won't Start
- Diagnosis commands
- Solutions for Linux Docker
- Solutions for Windows Docker

#### Port Already in Use
- How to find conflicting services
- Linux netstat commands
- Windows netstat commands
- Alternative port installation

#### License Not Detected
- Linux Docker license location (parent folder)
- Windows Docker license location (same folder)
- Verification commands
- Restart procedures

#### Docker Permissions (Linux)
- User group membership
- Permission fixes
- Verification steps

#### WSL2 Issues (Windows)
- Quick fixes (wsl --shutdown)
- WSL integration enable steps
- Systemd configuration
- Docker Desktop restart

#### Docker Volume Issues
- Volume inspection commands
- Volume recreation steps
- Data persistence troubleshooting

#### FreeSurfer Container Spawn Failures
- Docker-in-Docker diagnostics
- Socket permission checks
- Solutions for both platforms

#### Update Failures
- Backup procedures
- Force pull commands
- Reinstallation steps

### 2. Updated Processing Failures Section
**Location:** "MRI Processing Issues"

**Added:**
- Docker-specific license check commands
- FreeSurfer container status check
- Platform-specific troubleshooting

### 3. Added Quick Diagnostic Commands Section
**Location:** Before "Support"

**Organized by deployment type:**
- **Native Linux**: 5 diagnostic commands
- **Linux Docker**: 5 diagnostic commands
- **Windows Docker**: 4 diagnostic commands (PowerShell syntax)

### 4. Updated Support Section
**Enhanced with:**
- Deployment-specific log commands
- Docker-specific diagnostic tools
- Platform-appropriate syntax examples

---

## Key Features

### Concise Organization
- Clear section headings
- Bullet-point format
- Code blocks with syntax highlighting
- Platform-specific examples

### Comprehensive Coverage
- Installation procedures for all deployment types
- Management commands for daily operations
- Troubleshooting for common Docker issues
- Quick diagnostic commands

### User-Friendly
- Step-by-step instructions
- Copy-paste ready commands
- Platform-specific syntax (bash vs PowerShell)
- Clear explanations of what each command does

### Cross-Platform Consistency
- Parallel structure for Linux/Windows sections
- Same information presented for both platforms
- Easy comparison between deployment methods

---

## Statistics

### USER_GUIDE.md
- **Added:** ~450 lines
- **New Sections:** 3 major sections (Options 2, 3, and comparison)
- **Commands Documented:** 25+ management commands
- **Code Blocks:** 20+ examples

### TROUBLESHOOTING.md
- **Added:** ~350 lines
- **New Sections:** 1 major section (Docker Deployment Issues)
- **Issue Categories:** 9 Docker-specific issues
- **Diagnostic Commands:** 15+ quick fixes

### Total Impact
- **Combined Lines Added:** ~800 lines
- **Total Sections:** 4 major new sections
- **Commands Documented:** 40+ across both files
- **Platforms Covered:** Linux native, Linux Docker, Windows Docker

---

## Navigation

### USER_GUIDE.md Structure
```
1. Prerequisites
2. WSL Setup (Windows Users)
3. Docker Installation
4. Deployment Options ← NEW
5. Installation
   → Option 1: Native Linux ← EXISTING
   → Option 2: Linux Docker ← NEW
   → Option 3: Windows Docker ← NEW
   → Deployment Comparison ← NEW
6. Understanding NeuroInsight
7. Usage
8. Management Commands
9. Troubleshooting
10. FAQ
11. Support
```

### TROUBLESHOOTING.md Structure
```
1. Quick Diagnosis
2. Deployment-Specific Issues ← NEW
   → Docker Deployment Issues ← NEW
3. Common Issues
4. Memory Limitations
5. Application Won't Start
6. FreeSurfer License Issues
7. MRI Processing Issues ← UPDATED
8. Web Interface Issues
9. Performance Issues
10. Recovery Procedures
11. Quick Diagnostic Commands ← NEW
12. Support ← UPDATED
```

---

## Benefits

### For Users
- **Clear Choices**: Easy comparison of deployment options
- **Platform Support**: Windows users now have full documentation
- **Self-Service**: Comprehensive troubleshooting for Docker issues
- **Quick Reference**: Diagnostic commands organized by platform

### For Maintainers
- **Consistency**: Parallel structure for all deployment types
- **Completeness**: All major Docker issues documented
- **Searchability**: Clear section headings and keywords
- **Maintenance**: Modular structure for easy updates

### For Support
- **Reduced Questions**: Common Docker issues pre-documented
- **Better Bug Reports**: Users can run diagnostics first
- **Platform Clarity**: Clear separation of platform-specific issues
- **Reference Links**: Easy to point users to specific sections

---

**Result:** Both documents now provide complete, concise coverage of all NeuroInsight deployment options with platform-specific guidance and troubleshooting.
