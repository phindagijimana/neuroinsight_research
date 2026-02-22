# NeuroInsight Docker for Windows

Docker deployment of NeuroInsight for Windows 10/11 systems.

## System Requirements

- Windows 10 (version 2004+) or Windows 11 (64-bit)
- Docker Desktop for Windows
- 16GB+ RAM (32GB recommended)
- 50GB+ free disk space
- WSL2 (automatically configured by Docker Desktop)

## Quick Start

### 1. Install Docker Desktop

Download and install from: https://www.docker.com/products/docker-desktop/

Docker Desktop automatically installs and configures WSL2. No manual WSL2 setup needed.

### 2. Get FreeSurfer License

Required for MRI processing (free for research):
1. Visit: https://surfer.nmr.mgh.harvard.edu/registration.html
2. Complete registration
3. Save license as `license.txt` in this folder

### 3. Download NeuroInsight

```powershell
# Clone repository
git clone https://github.com/phindagijimana/neuroinsight_local.git
cd neuroinsight_local\neuroinsight_windows
```

Or download ZIP from GitHub and extract to desired location.

### 4. Install NeuroInsight

Open PowerShell or Command Prompt in the neuroinsight_windows folder:

**PowerShell (recommended):**
```powershell
.\neuroinsight-docker.ps1 install
```

**Command Prompt:**
```cmd
install.bat
```

### 5. Access NeuroInsight

Open browser to: http://localhost:8000

(Port may vary if 8000 is in use - check installation output)

## Management Commands

### PowerShell

```powershell
# Core operations
.\neuroinsight-docker.ps1 install       # Install and start
.\neuroinsight-docker.ps1 start         # Start container
.\neuroinsight-docker.ps1 stop          # Stop container
.\neuroinsight-docker.ps1 restart       # Restart
.\neuroinsight-docker.ps1 status        # Check status
.\neuroinsight-docker.ps1 remove        # Uninstall

# Monitoring
.\neuroinsight-docker.ps1 logs          # View all logs
.\neuroinsight-docker.ps1 logs backend  # Backend logs
.\neuroinsight-docker.ps1 logs worker   # Worker logs
.\neuroinsight-docker.ps1 health        # Health check

# Data management
.\neuroinsight-docker.ps1 clean         # Clean old jobs (30+ days)
.\neuroinsight-docker.ps1 clean 7       # Clean jobs older than 7 days
.\neuroinsight-docker.ps1 backup        # Backup all data
.\neuroinsight-docker.ps1 restore backup.tar.gz  # Restore

# Maintenance
.\neuroinsight-docker.ps1 license       # Check FreeSurfer license
.\neuroinsight-docker.ps1 update        # Update to latest
```

### Command Prompt (Batch Scripts)

```cmd
install.bat      REM Install and start
start.bat        REM Start container
stop.bat         REM Stop container
status.bat       REM Check status
logs.bat         REM View logs
```

## Features

- Web-based UI for MRI processing
- FreeSurfer 7.4.1 brain segmentation
- T1-weighted MRI analysis
- Hippocampal volume measurements
- 3D visualization
- PDF report generation
- Automatic backup and restore
- Data persistence across restarts

## Docker Desktop Configuration

Recommended settings (Docker Desktop > Settings):

**Resources:**
- Memory: 16GB (minimum 8GB)
- CPUs: 4-8 cores
- Disk: 50GB+

**General:**
- Use WSL2 based engine
- Start Docker Desktop when you log in

## First Run

When processing your first MRI scan:

1. FreeSurfer image downloads automatically (~7GB, 10-30 minutes)
2. Processing begins (3-7 hours per scan)
3. Subsequent jobs start immediately (no download)

## Troubleshooting

### Docker Not Running
- Start Docker Desktop from Start Menu
- Check Docker Desktop icon in system tray (should be green)

### Port Already in Use
```powershell
# Find what's using port 8000
netstat -ano | findstr :8000

# Or install on different port
.\neuroinsight-docker.ps1 install -Port 8001
```

### License Not Found
- Place `license.txt` in this folder
- Verify with: `.\neuroinsight-docker.ps1 license`
- Restart: `.\neuroinsight-docker.ps1 restart`

### Container Won't Start
```powershell
# Check logs
.\neuroinsight-docker.ps1 logs

# Check Docker Desktop logs
# Docker Desktop > Troubleshoot > Show logs
```

### WSL2 Issues
```powershell
# PowerShell as Administrator
wsl --shutdown
# Wait 10 seconds
# Restart Docker Desktop
```

## Data Persistence

All data stored in Docker volumes persists across:
- Container restarts
- NeuroInsight updates
- System reboots

Includes:
- Uploaded MRI scans
- Processing results
- Visualizations
- Database records

**Backup recommended before updates!**

## Uninstallation

```powershell
# Remove NeuroInsight
.\neuroinsight-docker.ps1 remove

# Remove Docker volumes (deletes all data)
docker volume rm neuroinsight_data
```

## Support

- GitHub Issues: https://github.com/phindagijimana/neuroinsight_local/issues
- Main Repository: https://github.com/phindagijimana/neuroinsight_local
- FreeSurfer Support: https://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferSupport

## Technical Details

- Uses same Linux Docker image via WSL2
- No separate Windows image needed
- Automatic port detection (8000-8050)
- Windows path handling for license detection
- PowerShell with colored output
- Command Prompt compatibility via batch scripts

## License

MIT License. FreeSurfer requires separate license for research use.

---

© 2025 University of Rochester. All rights reserved.
