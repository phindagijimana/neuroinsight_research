# Windows Installation Guide

Complete installation guide for NeuroInsight Docker on Windows 10/11.

## Prerequisites

### System Requirements
- Windows 10 (64-bit, version 2004 or higher) or Windows 11
- 16GB RAM minimum (32GB recommended)
- 50GB free disk space
- Internet connection for initial setup

### Required Software
- Docker Desktop for Windows

## Step-by-Step Installation

### Step 1: Install Docker Desktop

1. **Download Docker Desktop**
   - Visit: https://www.docker.com/products/docker-desktop/
   - Download Docker Desktop for Windows

2. **Run Installer**
   - Double-click `Docker Desktop Installer.exe`
   - Follow installation wizard
   - Select "Use WSL 2 instead of Hyper-V" (recommended)
   - Complete installation
   - Restart computer if prompted

3. **Start Docker Desktop**
   - Launch Docker Desktop from Start Menu
   - Wait for Docker to start (green icon in system tray)
   - Docker automatically configures WSL2

4. **Verify Installation**
   Open PowerShell and run:
   ```powershell
   docker --version
   docker ps
   ```
   Both commands should work without errors.

### Step 2: Get FreeSurfer License

Required for MRI processing (free for research use).

1. **Register for License**
   - Visit: https://surfer.nmr.mgh.harvard.edu/registration.html
   - Complete registration form
   - Receive license via email

2. **Save License File**
   - Save license as `license.txt`
   - Place in `neuroinsight_windows` folder
   - Ensure filename is exactly `license.txt`

### Step 3: Download NeuroInsight

**Option 1: Clone Repository (Recommended)**

```powershell
# Clone repository
git clone https://github.com/phindagijimana/neuroinsight_local.git
cd neuroinsight_local\neuroinsight_windows
```

**Option 2: Download ZIP**

1. Visit: https://github.com/phindagijimana/neuroinsight_local
2. Click "Code" > "Download ZIP"
3. Extract to desired location (e.g., `C:\NeuroInsight`)
4. Navigate to `neuroinsight_local\neuroinsight_windows` folder

### Step 4: Install NeuroInsight

1. **Open PowerShell**
   - Right-click Start Menu
   - Select "Windows PowerShell"

2. **Navigate to NeuroInsight Windows Folder**
   ```powershell
   cd C:\path\to\neuroinsight_local\neuroinsight_windows
   ```

3. **Run Installation**
   ```powershell
   .\neuroinsight-docker.ps1 install
   ```

4. **Wait for Installation**
   - Script checks Docker status
   - Detects available port (8000-8050)
   - Searches for FreeSurfer license
   - Pulls Docker image from Docker Hub
   - Starts container
   - Displays access URL

5. **Installation Complete**
   - Note the port shown in output
   - Open browser to http://localhost:8000 (or shown port)

## Alternative Installation Methods

### Using Command Prompt

Instead of PowerShell, use Command Prompt:

```cmd
cd C:\path\to\neuroinsight_windows
install.bat
```

### Custom Port

If port 8000 is in use:

```powershell
.\neuroinsight-docker.ps1 install -Port 8001
```

## Post-Installation

### Verify Installation

1. **Check Container Status**
   ```powershell
   .\neuroinsight-docker.ps1 status
   ```

2. **Check Services**
   ```powershell
   .\neuroinsight-docker.ps1 health
   ```

3. **View Logs**
   ```powershell
   .\neuroinsight-docker.ps1 logs
   ```

### Access Web Interface

1. Open browser
2. Go to http://localhost:8000
3. You should see NeuroInsight interface

### First Job Setup

When processing your first MRI scan:

1. FreeSurfer image downloads automatically (~7GB)
2. Download takes 10-30 minutes (depends on internet speed)
3. Progress shown in logs
4. One-time download - cached for future jobs
5. Processing begins automatically after download

## Configuration

### Docker Desktop Settings

Recommended configuration:

1. **Open Docker Desktop**
2. **Click Settings (gear icon)**

3. **General Tab**
   - [x] Use WSL 2 based engine
   - [x] Start Docker Desktop when you log in

4. **Resources Tab**
   - Memory: 16GB (or 8GB minimum)
   - CPUs: 4-8 cores
   - Disk image size: 50GB+
   - Swap: 2GB

5. **Apply & Restart**

### WSL2 Resource Configuration

Optional: Limit WSL2 resource usage.

Create file: `C:\Users\YourUsername\.wslconfig`

```ini
[wsl2]
memory=16GB
processors=6
swap=4GB
localhostForwarding=true
```

Then restart WSL:
```powershell
wsl --shutdown
```

## Troubleshooting Installation

### Docker Desktop Won't Start

**Issue**: Docker Desktop fails to start or shows errors

**Solutions**:

1. **Enable Virtualization in BIOS**
   - Restart computer
   - Enter BIOS (F2/F12/Del key during boot)
   - Enable Intel VT-x or AMD-V
   - Save and exit

2. **Enable WSL2**
   ```powershell
   # Run as Administrator
   wsl --install
   wsl --set-default-version 2
   ```

3. **Restart Docker Desktop**
   - Right-click Docker icon in system tray
   - Select "Restart"

### Installation Script Fails

**Issue**: PowerShell script execution error

**Solution**:
```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try installation again.

### Port Already in Use

**Issue**: Port 8000 is already occupied

**Solutions**:

1. **Find conflicting process**
   ```powershell
   netstat -ano | findstr :8000
   ```

2. **Stop conflicting service**
   - Or use different port during installation

3. **Install on different port**
   ```powershell
   .\neuroinsight-docker.ps1 install -Port 8001
   ```

### License Not Found

**Issue**: Installation completes but license warning appears

**Solutions**:

1. **Verify license file**
   - Check file is named exactly `license.txt`
   - Check file is in `neuroinsight_windows` folder
   - Verify file contains license text (not empty)

2. **Check license status**
   ```powershell
   .\neuroinsight-docker.ps1 license
   ```

3. **Restart container**
   ```powershell
   .\neuroinsight-docker.ps1 restart
   ```

### Container Won't Start

**Issue**: Container starts then immediately stops

**Solutions**:

1. **Check Docker logs**
   ```powershell
   .\neuroinsight-docker.ps1 logs
   ```

2. **Check Docker Desktop logs**
   - Docker Desktop > Troubleshoot > Show logs

3. **Reinstall**
   ```powershell
   .\neuroinsight-docker.ps1 remove
   .\neuroinsight-docker.ps1 install
   ```

### Slow Performance

**Issue**: NeuroInsight runs slowly

**Solutions**:

1. **Increase Docker resources**
   - Docker Desktop > Settings > Resources
   - Increase Memory to 16GB+
   - Increase CPUs to 6-8 cores

2. **Close other applications**
   - Free up system resources
   - Especially memory-intensive programs

3. **Use SSD storage**
   - Move Docker virtual disk to SSD
   - Docker Desktop > Settings > Resources > Disk image location

## Verification Checklist

Before first use, verify:

- [ ] Docker Desktop running (green icon in system tray)
- [ ] `docker ps` shows neuroinsight container
- [ ] http://localhost:8000 loads NeuroInsight interface
- [ ] `license.txt` file present in folder
- [ ] `.\neuroinsight-docker.ps1 status` shows "running"
- [ ] `.\neuroinsight-docker.ps1 health` shows all services running

## Next Steps

After successful installation:

1. **Read README.md** for management commands
2. **Upload test MRI scan** (T1-weighted NIfTI file)
3. **Monitor first job** (includes FreeSurfer download)
4. **Set up regular backups** using backup command

## Uninstallation

To completely remove NeuroInsight:

1. **Stop and remove container**
   ```powershell
   .\neuroinsight-docker.ps1 remove
   ```

2. **Remove Docker volumes** (deletes all data)
   ```powershell
   docker volume rm neuroinsight_data
   ```

3. **Remove folder**
   - Delete `neuroinsight_windows` folder

4. **Optional: Uninstall Docker Desktop**
   - Settings > Apps > Docker Desktop > Uninstall

## Support

- GitHub Issues: https://github.com/phindagijimana/neuroinsight_local/issues
- Documentation: See README.md
- FreeSurfer: https://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferSupport

---

© 2025 University of Rochester. All rights reserved.
