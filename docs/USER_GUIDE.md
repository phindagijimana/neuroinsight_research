# NeuroInsight User Guide

Complete guide for deploying and using NeuroInsight for hippocampal MRI analysis.

## Prerequisites

- Ubuntu 20.04+ Linux system
- 16GB+ RAM (32GB recommended)
- 4+ CPU cores, 50GB storage
- Docker and Docker Compose
- FreeSurfer license (free for research)
- **System sleep timeout set to 7+ hours** (critical for long-running processing)

### System Verification Commands

Check if your system meets the requirements:

```bash
# Check CPU cores
nproc

# Check available RAM (in GB)
free -h

# Check available storage (in GB)
df -h /

# Check Ubuntu version
lsb_release -a
```

## WSL Setup (Windows Users)

If you're using Windows, you can run NeuroInsight using Windows Subsystem for Linux (WSL). Here's how to set it up:

### Enable WSL Feature

1. **Open PowerShell as Administrator**:
   - Press `Win + X` and select "Windows PowerShell (Admin)" or "Terminal (Admin)"

2. **Enable WSL feature**:
   ```powershell
   dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
   ```

3. **Enable Virtual Machine Platform** (required for WSL 2):
   ```powershell
   dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
   ```

4. **Restart your computer** when prompted.

### Install WSL and Ubuntu

1. **Open PowerShell/Terminal as Administrator** again after restart.

2. **Set WSL 2 as default version**:
   ```powershell
   wsl --set-default-version 2
   ```

3. **Install Ubuntu distribution**:
   ```powershell
   wsl --install -d Ubuntu
   ```

4. **Set up Ubuntu**:
   - The Ubuntu installation will start automatically
   - Create a username and password when prompted
   - Wait for installation to complete

### Verify WSL Installation

1. **Open Ubuntu from Start Menu** or run `wsl` in PowerShell/Terminal.

2. **Update Ubuntu packages**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

3. **Verify WSL version**:
   ```bash
   wsl --version
   ```

### Important WSL Notes

- **File Access**: Windows files are accessible at `/mnt/c/` from WSL
- **Performance**: Keep project files inside WSL for better Docker performance
- **Memory**: WSL may need memory allocation adjustments in `.wslconfig`
- **Integration**: Docker Desktop integrates with WSL for container operations

Once WSL is set up, continue with the Docker installation instructions below.

## Docker Installation

Docker is required for NeuroInsight to run PostgreSQL, Redis, and MinIO services. Choose the appropriate installation method for your platform.

### For Linux (Native Ubuntu/Debian)

#### Step 1: Install Docker Engine

```bash
# Download Docker installation script
curl -fsSL https://get.docker.com -o get-docker.sh

# Run installation script
sudo sh get-docker.sh

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker
```

#### Step 2: Add User to Docker Group (REQUIRED)

```bash
# Add current user to docker group
sudo usermod -aG docker $USER

# Verify you were added
groups $USER
```

**IMPORTANT:** You MUST log out and log back in for the group change to take effect.

```bash
# Log out
exit

# Then log back in and verify Docker works without sudo
docker ps
```

#### Step 3: Verify Installation

```bash
# Check Docker version
docker --version

# Check Docker Compose version
docker compose version

# Test Docker (should work without sudo)
docker run hello-world
```

**Troubleshooting:**

If you get "permission denied" errors:
```bash
# Verify you're in docker group
groups

# If "docker" is not listed, you haven't logged out/in yet
# Log out completely and log back in
```

### For Windows (WSL2)

#### Step 1: Install Docker Desktop for Windows

1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop/
2. Run the installer: `Docker Desktop Installer.exe`
3. During installation, ensure "Use WSL 2 instead of Hyper-V" is checked
4. Complete installation and restart if prompted

#### Step 2: Configure Docker Desktop for WSL

After Docker Desktop starts:

1. Click the Docker icon in the system tray
2. Go to Settings (gear icon)
3. Navigate to: **Resources** → **WSL Integration**
4. Enable: "Enable integration with my default WSL distro"
5. Enable your Ubuntu distribution
6. Click "Apply & Restart"

#### Step 3: Enable Systemd in WSL (REQUIRED)

Open Ubuntu from Start Menu:

```bash
# Create/edit WSL configuration
sudo nano /etc/wsl.conf

# Add these lines:
[boot]
systemd=true

# Save and exit (Ctrl+O, Enter, Ctrl+X)
```

**IMPORTANT:** Shutdown WSL completely for changes to take effect.

Exit Ubuntu terminal, then in PowerShell:

```powershell
# Shutdown WSL
wsl --shutdown

# Wait 10 seconds, then reopen Ubuntu from Start Menu
```

#### Step 4: Verify Docker in WSL

Open Ubuntu terminal:

```bash
# Check Docker version
docker --version

# Check Docker Compose
docker compose version

# Test Docker connectivity
docker ps

# Run test container
docker run hello-world
```

**Troubleshooting:**

If you get "permission denied":
```bash
# Add user to docker group in WSL
sudo usermod -aG docker $USER

# Exit WSL terminal completely
exit
```

Then in PowerShell:
```powershell
wsl --shutdown
```

Reopen Ubuntu and test again.

#### Step 5: Configure WSL Resources (Optional but Recommended)

Create/edit `C:\Users\YourUsername\.wslconfig` in Windows:

```ini
[wsl2]
memory=12GB
processors=6
swap=4GB
localhostForwarding=true
```

Restart WSL:
```powershell
wsl --shutdown
```

### Verification Checklist

Before installing NeuroInsight, verify:

**Linux:**
- `docker --version` shows v20.10+ or v24.0+
- `docker compose version` shows v2.0+
- `docker ps` works WITHOUT sudo
- `docker run hello-world` succeeds
- You logged out and back in after adding user to docker group

**WSL:**
- Docker Desktop is running (green icon in Windows system tray)
- `wsl --list --verbose` shows VERSION 2 for Ubuntu
- Systemd enabled: `systemctl --version` works in Ubuntu
- WSL was shut down after systemd configuration
- `docker ps` works in Ubuntu terminal without errors

## Deployment Options

NeuroInsight offers four deployment methods:

| Type | Best For | Requirements |
|------|----------|--------------|
| **Desktop App** | Researchers, clinicians | Windows 10/11 or Linux, Docker Desktop |
| **Native Linux** | Direct Ubuntu/Debian installation | Ubuntu 20.04+, systemd |
| **Linux Docker** | Isolated containerized environment | Docker + Docker Compose |
| **Windows Docker** | Windows 10/11 systems | Docker Desktop + WSL2 |

**New to NeuroInsight?** Start with the [Desktop App](https://github.com/phindagijimana/neuroinsight_desktop/releases) for the easiest installation.

Choose Docker/Native deployment for servers, HPC clusters, or multi-user environments.

---

## Installation

### Option 0: Desktop Application (Recommended for Most Users)

**Best for:** Researchers, clinicians, desktop users wanting the easiest setup

**Download:** [NeuroInsight Desktop v1.0.0](https://github.com/phindagijimana/neuroinsight_desktop/releases/tag/v1.0.0)

**Platforms:**
- Windows 10/11 (Setup.exe or Portable.exe)
- Linux (AppImage or DEB package)

**Prerequisites:**
- Docker Desktop installed (see Docker Installation section above)
- 16GB+ RAM, 50GB+ disk space

**Quick Start:**

**Windows:**
1. Download `NeuroInsight-Setup-1.0.0.exe`
2. Run installer and follow wizard
3. Launch from Start Menu

**Linux (AppImage):**
```bash
wget https://github.com/phindagijimana/neuroinsight_desktop/releases/download/v1.0.0/NeuroInsight-1.0.0.AppImage
chmod +x NeuroInsight-1.0.0.AppImage
./NeuroInsight-1.0.0.AppImage
```

**Linux (DEB - Ubuntu/Debian):**
```bash
wget https://github.com/phindagijimana/neuroinsight_desktop/releases/download/v1.0.0/NeuroInsight-1.0.0.deb
sudo dpkg -i NeuroInsight-1.0.0.deb
neuroinsight
```

**First Run:**
1. Ensure Docker Desktop is running
2. Launch NeuroInsight
3. First run downloads FreeSurfer image (~7GB, one-time)
4. Upload T1-weighted MRI files and start processing

**Documentation:** See [Desktop App Documentation](https://github.com/phindagijimana/neuroinsight_desktop) for full details, troubleshooting, and advanced features.

**Note:** Desktop App uses Docker containers under the hood. For server deployments or advanced configurations, use the options below.

---

### Option 1: Native Linux Installation

**Best for:** Direct Ubuntu/Debian systems with systemd

**Prerequisites:** 
- Docker installed (see Docker Installation section above)
- Ubuntu 20.04+ with systemd

### 1. Clone Repository

```bash
git clone https://github.com/phindagijimana/neuroinsight_local.git
cd neuroinsight_local
```

### 2. Get FreeSurfer License

**REQUIRED:** FreeSurfer requires a free license for research use.

1. Visit: https://surfer.nmr.mgh.harvard.edu/registration.html
2. Complete the registration form
3. Save the license file as `license.txt` in the project directory

### 3. Verify Docker Installation (REQUIRED)

```bash
docker --version  # Should show Docker version
docker run hello-world  # Should run successfully
```

### 4. Install Docker (if not already installed)

#### Ubuntu/Debian Installation:

```bash
# Update package index
sudo apt update

# Install required packages
sudo apt install apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up the stable repository
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Update package index again
sudo apt update

# Install Docker Engine
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start and enable Docker service:
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (optional, avoids using sudo):
sudo usermod -aG docker $USER
# Log out and back in, or run: newgrp docker

# Verify Docker works:
docker --version
docker run hello-world
```

### 5. WSL (Windows Subsystem for Linux) Users

If you're using WSL on Windows, Docker installation is different:

#### Install Docker Desktop on Windows:
1. **Download Docker Desktop for Windows**: Visit https://www.docker.com/products/docker-desktop
2. **Install the .exe file** and follow the installation wizard
3. **Enable WSL Integration**:
   - Open Docker Desktop
   - Go to Settings → Resources → WSL Integration
   - Enable integration with your WSL distribution
   - Click "Apply & Restart"

#### Verify WSL Docker Access:
```bash
# In your WSL terminal, verify Docker works:
docker --version
docker run hello-world

# If you get connection errors, restart WSL:
exit
# Then reopen WSL terminal
```

#### Important Notes for WSL:
- **File permissions**: WSL files are accessible at `/mnt/c/` from Windows
- **Performance**: Docker volumes work better when files are inside WSL, not `/mnt/c/`
- **Memory**: Docker Desktop may need memory allocation in Windows settings
- **Updates**: Keep both Windows Docker Desktop and WSL distribution updated

### 5. Troubleshooting

For installation issues on WSL or native Linux, see the **Troubleshooting** section at the end of this guide or refer to `docs/TROUBLESHOOTING.md`.

**Common WSL issues:**

- **Upload directory missing** - Run `./neuroinsight install` to create directories
- **Docker permission denied** - Log out and back in after adding to docker group
- **Database schema errors** - Run `alembic upgrade head` in backend folder
- **systemd services not starting** - Reinstall services with `./systemd/install_systemd.sh`

**For detailed solutions:** See `docs/TROUBLESHOOTING.md`

---

### Option 2: Linux Docker Installation

**Best for:** Isolated containerized environment on Linux/WSL2

**Prerequisites:**
- Docker Engine 20.10+ or Docker Desktop (see Docker Installation above)
- Docker Compose 2.0+
- 16GB+ RAM, 50GB disk space
- Ubuntu 20.04+ or WSL2

#### Installation Steps

```bash
# 1. Clone repository
git clone https://github.com/phindagijimana/neuroinsight_local.git
cd neuroinsight_local/deploy

# 2. Install and start
./neuroinsight-docker install

# Access at http://localhost:8000
```

The install command will:
- Auto-detect FreeSurfer license in parent directory
- Pull Docker image from Docker Hub
- Create Docker volume for data persistence
- Start all services in one container

#### Docker Management Commands

```bash
cd neuroinsight_local/deploy

# Service management
./neuroinsight-docker start            # Start services
./neuroinsight-docker stop             # Stop services
./neuroinsight-docker restart          # Restart services
./neuroinsight-docker status           # Check status

# Maintenance
./neuroinsight-docker logs             # View logs
./neuroinsight-docker backup           # Backup data
./neuroinsight-docker restore backup.tar.gz  # Restore from backup
./neuroinsight-docker update           # Update to latest version

# Advanced
./neuroinsight-docker shell            # Access container shell
./neuroinsight-docker clean            # Remove container and data
```

#### What's Included

The Docker container includes all components:
- PostgreSQL 15 (database)
- Redis 7 (task queue)
- MinIO (S3-compatible storage)
- FastAPI backend (port 8000)
- Celery worker (MRI processing)
- React frontend

#### Data Persistence

All data is stored in Docker volume `neuroinsight-data`:
- MRI uploads
- Processing results
- Database
- Logs

Use `./neuroinsight-docker backup` for regular backups.

---

### Option 3: Windows Docker Installation

**Best for:** Windows 10/11 users

**Prerequisites:**
- Windows 10/11 (64-bit, version 2004+)
- Docker Desktop for Windows (see Docker Installation above)
- 16GB+ RAM, 50GB disk space
- WSL2 (auto-installed by Docker Desktop)

#### Installation Steps

**1. Install Docker Desktop**
- Download: https://www.docker.com/products/docker-desktop/
- Install and restart if prompted
- Docker Desktop automatically configures WSL2

**2. Install NeuroInsight**

```powershell
# Clone repository
git clone https://github.com/phindagijimana/neuroinsight_local.git
cd neuroinsight_local\neuroinsight_windows

# Install and start
.\neuroinsight-docker.ps1 install

# Access at http://localhost:8000
```

The install command will:
- Auto-detect FreeSurfer license
- Pull Docker image
- Create volume for data
- Start container

**3. Verify Installation**

Open browser and navigate to: http://localhost:8000

#### Windows Management Commands

**PowerShell:**
```powershell
cd neuroinsight_windows

# Service management
.\neuroinsight-docker.ps1 start        # Start services
.\neuroinsight-docker.ps1 stop         # Stop services  
.\neuroinsight-docker.ps1 restart      # Restart services
.\neuroinsight-docker.ps1 status       # Check status

# Maintenance
.\neuroinsight-docker.ps1 logs         # View logs
.\neuroinsight-docker.ps1 backup       # Backup data
.\neuroinsight-docker.ps1 restore backup.tar.gz  # Restore
.\neuroinsight-docker.ps1 update       # Update to latest

# Advanced
.\neuroinsight-docker.ps1 shell        # Access container
.\neuroinsight-docker.ps1 clean        # Remove all data
```

**Batch Scripts (Alternative):**
```cmd
cd neuroinsight_windows\scripts

start.bat          # Start services
stop.bat           # Stop services
status.bat         # Check status
logs.bat           # View logs
```

#### Docker Desktop Configuration

Recommended settings (Docker Desktop → Settings):

**Resources:**
- Memory: 16GB (minimum 8GB)
- CPUs: 4-8 cores
- Disk: 50GB+

**General:**
- Use WSL2 based engine
- Start Docker Desktop when you log in

#### Windows-Specific Notes
- Uses same Linux Docker image via WSL2
- No separate Windows image needed
- Automatic port detection (8000-8050)
- FreeSurfer license auto-detection
- PowerShell scripts provide colored output

---

### Deployment Comparison

| Feature | Native Linux | Linux Docker | Windows Docker | Desktop App |
|---------|--------------|--------------|----------------|-------------|
| **Installation** | Direct on system | Containerized | Containerized via WSL2 | One-click installer |
| **Updates** | Manual | One command | One command | Auto-update |
| **Backup/Restore** | Manual | Built-in | Built-in | Built-in |
| **Isolation** | System-wide | Containerized | Containerized | Containerized |
| **Performance** | Direct | Minimal overhead | WSL2 overhead | Minimal overhead |
| **Portability** | System-specific | Portable | Portable | Portable |
| **Dependencies** | Manual install | Pre-packaged | Pre-packaged | Pre-packaged |

---

## Quick Docker Deployment (Direct Pull)

For advanced users who want to pull and run the Docker image directly without installation scripts:

### Linux

```bash
# Pull image
docker pull phindagijimana321/neuroinsight:latest

# Run container
docker run -d \
  --name neuroinsight \
  -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v neuroinsight-data:/data \
  -v $(pwd)/license.txt:/app/license.txt:ro \
  phindagijimana321/neuroinsight:latest

# Access at http://localhost:8000
```

### Windows (PowerShell)

```powershell
# Pull image
docker pull phindagijimana321/neuroinsight:latest

# Run container
docker run -d `
  --name neuroinsight `
  -p 8000:8000 `
  -v /var/run/docker.sock:/var/run/docker.sock `
  -v neuroinsight-data:/data `
  -v ${PWD}/license.txt:/app/license.txt:ro `
  phindagijimana321/neuroinsight:latest

# Access at http://localhost:8000
```

**Note:** For full features and easier management, use the installation methods above (Option 0, 2, or 3).

---

## Configuration

### Environment Variables

NeuroInsight can be configured using the `.env` file in the project root (Native Linux deployment) or through environment variables passed to Docker containers.

**Key Configuration Options:**

**Processing:**
- `CELERY_WORKER_CONCURRENCY` - Number of concurrent MRI processing jobs (default: 1)
- `FREESURFER_LICENSE_PATH` - Path to FreeSurfer license file

**Storage:**
- `HOST_UPLOAD_DIR` - Directory for uploaded MRI files
- `HOST_OUTPUT_DIR` - Directory for processing outputs
- `MINIO_ENDPOINT` - S3-compatible storage endpoint (optional)

**Resources:**
- `MAX_WORKERS` - Maximum parallel Celery workers
- `MEMORY_LIMIT` - Container memory limit (Docker deployments)

**Network:**
- `BACKEND_PORT` - API server port (default: 8000)
- `CORS_ORIGINS` - Allowed CORS origins for API access

For detailed configuration, see your deployment's specific documentation:
- **Option 0 (Desktop App)**: Uses default configuration, customizable through UI
- **Option 1 (Native Linux)**: Edit `.env` in project root
- **Option 2/3 (Docker)**: Configuration embedded in container, customize via docker-compose.yml or Docker run parameters

---

## Understanding NeuroInsight

### Concurrency Limits

NeuroInsight processes one MRI scan at a time to ensure system stability and prevent resource exhaustion. This means:

- **Sequential Processing**: Jobs are queued and processed one after another
- **Queue Management**: New uploads are automatically added to the processing queue
- **Resource Allocation**: Each job gets dedicated CPU, memory, and storage resources
- **Status Monitoring**: Real-time progress updates show current job status and queue position

**Why this limitation?**
- FreeSurfer processing is computationally intensive (3-7 hours per scan depending on image characteristics)
- Prevents system overload and ensures accurate results
- Maintains data integrity during parallel filesystem operations

### User Workflow

#### Typical User Journey:

1. **Preparation**:
   - Ensure T1-weighted MRI files are in NIfTI format (.nii or .nii.gz)
   - Verify filenames contain T1 indicators (t1, mprage, etc.)
   - Confirm file sizes are under 500MB limit

2. **Upload**:
   - Access NeuroInsight at http://localhost:8000
   - Enter patient name in the upload form
   - Select and upload your T1 NIfTI file
   - Job automatically enters processing queue

3. **Monitoring**:
   - View job status in the main dashboard
   - Track progress through FreeSurfer pipeline stages
   - Monitor for any error messages or failed jobs

4. **Results**:
   - Successful jobs show anatomical and segmentation overlays
   - View hippocampus regions with interactive controls
   - Adjust zoom (50-500%), opacity (0-100%), and rotation (0-360 degrees)
   - Switch between axial, coronal, and sagittal views

5. **Export & Analysis**:
   - Results are automatically saved for future access
   - Compare multiple scans in the job history
   - Re-upload or reprocess if needed

## Usage

### File Requirements

#### Supported File Formats
NeuroInsight accepts NIfTI files for T1-weighted MRI scans:

1. **NIfTI Uncompressed** (`.nii`) - Direct processing
2. **NIfTI Compressed** (`.nii.gz`) - Direct processing

**Note:** DICOM files must be converted to NIfTI format before upload using tools like `dcm2niix`.

#### T1 Filename Requirements
**All uploaded files must have T1-related keywords in their filenames.** This ensures only appropriate T1-weighted images are processed for accurate hippocampus analysis.

**Required T1 Indicators (one of these must be in the filename):**
- Basic: `t1`, `t1w`, `t1-weighted`
- Sequences: `mprage`, `spgr`, `tfl`, `tfe`, `fspgr`, `mpr`
- Compound: `t1_mprage`, `t1_spgr`, `t1_tfe`, `fspgr_t1`, `t1w_mprage`

#### File Size Limits
- Maximum file size: **500MB**
- Recommended: Scans under 100MB for optimal processing

#### Valid Examples
```
- sub-01_T1w.nii.gz
- patient_mprage.nii
- brain_t1_mprage.nii
- t1w_mprage.nii.gz
```

#### Invalid Examples
```
- brain_scan.nii      (missing T1 indicator)
- t2_image.nii        (T2, not T1)
- flair.nii          (FLAIR sequence)
- scan.dcm           (DICOM not supported - convert to NIfTI first)
- scan.zip           (ZIP archives not supported)
```

#### File Selection Tips

**Mac Users:**

If your NIfTI files are not selectable in the file picker dialog:

1. **Click "Options"** in the file selection dialog (bottom-left)
2. **Change from "Custom Files" to "All Files"** in the dropdown
3. **Select your T1-weighted NIfTI image** (.nii or .nii.gz)

This issue occurs because macOS may not recognize the NIfTI file extension by default. Using "All Files" allows you to select any file regardless of extension.

**Windows Users:**

If your NIfTI files are not visible in the file picker dialog:

1. **Click the file type dropdown** at the bottom of the dialog (shows "Custom Files" or similar)
2. **Select "All Files (*.*)"** from the dropdown menu
3. **Select your T1-weighted NIfTI image** (.nii or .nii.gz)

Windows may filter out unrecognized file extensions by default. Switching to "All Files" displays all files in the directory.

### Detailed File Format Guide

#### NIfTI Files (.nii, .nii.gz)
- **Recommended format** for NeuroInsight
- Direct processing without conversion
- Must contain T1-weighted MRI data
- Filename must include T1 indicators


#### Processing Pipeline
1. **NIfTI files**: Direct FreeSurfer processing
2. **Output**: Hippocampal volumes, asymmetry analysis, visualizations

### Web Interface
1. **Upload**: Select T1-weighted MRI files
2. **Monitor**: Track processing progress in real-time
3. **View Results**: Examine hippocampal volumes and asymmetry
4. **Generate Reports**: Download PDF reports with visualizations

## Management Commands

### Start Services
```bash
./neuroinsight start
```
**What it does:** Launches all NeuroInsight services including the web interface, Celery workers, Redis cache, and database. The system will be accessible at http://localhost:8000 once fully started.

### Stop Services
```bash
./neuroinsight stop
```
**What it does:** Gracefully shuts down all NeuroInsight services and **disables no‑sleep mode** if it is active. This ensures proper cleanup of running processes and returns the system to normal sleep behavior. Wait for confirmation that all services have stopped.

**Container handling:** Stopping the app stops any running FreeSurfer containers, but does not immediately remove stopped containers. Maintenance cleans stopped FreeSurfer containers older than 5 days.

**Note:** The stop script removes the PostgreSQL/Redis/MinIO containers. If you want job data to persist across restarts, configure persistent volumes or external services.

### Check Status
```bash
./neuroinsight status
```
**What it does:** Displays the current state of all services including:
- Web server (FastAPI) status
- Celery worker processes
- Redis cache connectivity
- Database availability
- Docker containers status
- Current job queue information

### Verify License
```bash
./neuroinsight license
```
**What it does:** Validates your FreeSurfer license file. Checks that `license.txt` exists in the project directory and contains valid FreeSurfer credentials. Required before processing any MRI scans.

### Delete Specific Job
```bash
./neuroinsight delete <job_id>
```
**What it does:** Permanently deletes a specific job by ID, including:
- Database record
- Uploaded MRI file
- Output directory and all results
- Associated metrics

**Examples:**
```bash
# Interactive deletion (asks for confirmation)
./neuroinsight delete d1a2c36e

# Force deletion (no confirmation)
./neuroinsight delete d1a2c36e --force
```

**Finding Job IDs:**
- View job IDs in web interface (in URL or job details)
- Or list jobs: `./neuroinsight status` shows active jobs

**Docker deployments:**
```bash
# Linux/WSL Docker
./neuroinsight-docker delete d1a2c36e

# Windows Docker
.\neuroinsight-docker.ps1 delete d1a2c36e
```

**Note:** This only deletes COMPLETED or FAILED jobs. Running/pending jobs should be cancelled through the web interface first.

### Advanced Monitoring
```bash
./neuroinsight monitor
```
**What it does:** Provides detailed system monitoring including:
- Real-time resource usage (CPU, memory, disk)
- Active job progress and queue status
- Docker container health
- System logs and error tracking
- Performance metrics and alerts

### Failure Handling and Queue Behavior
When a job fails:
- The job is marked **failed** with an error message.
- The FreeSurfer container is **stopped** (not removed).
- The queue immediately starts the next pending job if capacity allows.

Stopped FreeSurfer containers are cleaned up automatically by maintenance after **5 days**. Job result cleanup is still controlled by the user via `./neuroinsight clean`.

### Prevent System Sleep
```bash
./neuroinsight nosleep
```
**What it does:** Uses `systemd-inhibit` to prevent the machine from sleeping while jobs run. Run this after `./neuroinsight start`. It will be stopped automatically when you run `./neuroinsight stop`.

### Clean Old Jobs
```bash
./neuroinsight clean
```
Use the default 90-day retention when you want routine cleanup without fine-tuning.

```bash
./neuroinsight clean --days 30
```
Use a short retention window when storage is tight or you only need recent results.

```bash
./neuroinsight clean --months 6
```
Use month-based retention for scheduled or quarterly cleanup policies.

```bash
./neuroinsight clean --days 30 --keep d56a321c
```
Use this when you want aggressive cleanup but must preserve a specific job.

**What it does:** Removes completed/failed jobs older than the retention window and deletes their files. Also cleans orphaned job directories (files on disk without database records). Use `--keep` to preserve specific jobs.

**Additional Examples:**

```bash
# Keep specific jobs (comma-separated):
./neuroinsight clean --days 30 --keep job1,job2,job3

# Or use multiple --keep flags:
./neuroinsight clean --days 30 --keep job1 --keep job2 --keep job3

# Clean by months:
./neuroinsight clean --months 3 --keep important_job

# Default (90 days):
./neuroinsight clean

# Clean both database AND orphaned files (default):
./neuroinsight clean --days 30 --keep 912e32e7,e3463efb

# Clean ONLY orphaned files (skip database):
./neuroinsight clean --days 30 --orphaned-only --keep 912e32e7,e3463efb

# Clean ONLY database jobs (skip orphaned):
./neuroinsight clean --days 30 --skip-orphaned --keep 912e32e7,e3463efb
```

**Options:**
- `--days N`: Retention period in days (default: 90)
- `--months N`: Retention period in months (alternative to --days)
- `--keep ID`: Job IDs to preserve (comma-separated or repeatable)
- `--orphaned-only`: Only clean orphaned files on disk, skip database jobs
- `--skip-orphaned`: Only clean database jobs, skip orphaned files on disk

### Recover a Completed Job
```bash
./neuroinsight bring <job_id>
```
**What it does:** Reconstructs a completed job from on-disk output files. If no outputs exist for the ID, the script reports that it cannot recover the job.

### View System Logs
```bash
./neuroinsight logs
```
**What it does:** Provides a unified interface to view logs from different NeuroInsight components. You can view logs interactively through a menu or directly specify which component logs to view.

**Interactive Menu (no arguments):**
```bash
./neuroinsight logs
```
Displays an interactive menu where you can select:
1. **backend** - Backend API server logs (FastAPI requests, responses, errors)
2. **celery** - Celery worker logs (job processing, task execution)
3. **beat** - Celery beat scheduler logs (periodic tasks, scheduling)
4. **monitor** - Job monitoring service logs (progress tracking, status updates)
5. **freesurfer** - FreeSurfer processing logs (requires job ID, recon-all logs)
6. **database** - PostgreSQL database logs (queries, connections, errors)
7. **redis** - Redis message broker logs (queue operations, cache)
8. **All logs** - Show all available logs sequentially

**Direct Log Access (specify component):**
```bash
# View backend API logs
./neuroinsight logs backend

# View Celery worker logs
./neuroinsight logs celery

# View database logs
./neuroinsight logs database

# View Redis logs
./neuroinsight logs redis

# View FreeSurfer logs for specific job (requires job ID)
./neuroinsight logs freesurfer --job-id abc123
```

**Options:**

**Follow mode** (`-f` or `--follow`): Stream logs in real-time (like `tail -f`)
```bash
# Follow backend logs in real-time
./neuroinsight logs backend --follow

# Follow Celery worker logs
./neuroinsight logs celery -f
```

**Line limit** (`-n` or `--lines N`): Show last N lines (default: 100)
```bash
# Show last 50 lines of backend logs
./neuroinsight logs backend -n 50

# Show last 200 lines of Celery logs
./neuroinsight logs celery --lines 200
```

**Job-specific FreeSurfer logs** (`--job-id ID`): View FreeSurfer processing logs for a specific job
```bash
# View FreeSurfer logs for job abc123
./neuroinsight logs freesurfer --job-id abc123

# Follow FreeSurfer logs in real-time
./neuroinsight logs freesurfer --job-id abc123 --follow

# Show last 500 lines of FreeSurfer logs
./neuroinsight logs freesurfer --job-id abc123 -n 500
```

**Combine options:**
```bash
# Follow last 50 lines of backend logs
./neuroinsight logs backend -f -n 50

# Show last 20 lines of Celery logs
./neuroinsight logs celery --lines 20
```

**Common Use Cases:**

1. **Troubleshooting failed jobs:**
   ```bash
   # Check Celery worker logs for errors
   ./neuroinsight logs celery -n 100
   
   # View FreeSurfer logs for failed job
   ./neuroinsight logs freesurfer --job-id <failed_job_id>
   ```

2. **Monitoring active processing:**
   ```bash
   # Follow backend logs in real-time
   ./neuroinsight logs backend --follow
   
   # Follow FreeSurfer progress for running job
   ./neuroinsight logs freesurfer --job-id <running_job_id> --follow
   ```

3. **Checking system health:**
   ```bash
   # Check database logs
   ./neuroinsight logs database -n 50
   
   # Check Redis broker logs
   ./neuroinsight logs redis -n 50
   ```

4. **Debugging API issues:**
   ```bash
   # View recent backend API requests
   ./neuroinsight logs backend -n 100
   
   # Follow backend logs while testing
   ./neuroinsight logs backend --follow
   ```

**Help:**
```bash
./neuroinsight logs --help
```

**Notes:**
- Log files are stored in the NeuroInsight project directory
- Database and Redis logs are retrieved from Docker containers
- FreeSurfer logs are job-specific and stored in each job's output directory
- Press `Ctrl+C` to exit follow mode or interrupt log viewing
- All output is plain text without emojis for better compatibility with log parsers

### Additional Commands

#### Reinstall (for troubleshooting)
```bash
./neuroinsight reinstall
```
**Use when:** Persistent issues with services or corrupted installations. This command provides step-by-step guidance to completely remove and reinstall NeuroInsight, including backup of user data when possible.

**Note:** All management commands should be run from the NeuroInsight project root directory where the `neuroinsight` script is located.

## Troubleshooting

### Common Issues

**Jobs stuck in pending:**
- Check `./neuroinsight status` to verify all services are running (including Celery workers)
- Ensure Redis is running: `redis-cli ping`
- Check Celery worker logs: `ps aux | grep celery`
- If workers not running, restart services: `./neuroinsight stop && ./neuroinsight start`
- For detailed troubleshooting, see [TROUBLESHOUTING.md](TROUBLESHOUTING.md#jobs-stuck-in-pending-status)

**Processing fails:**
- **T1 Validation**: Ensure filename contains T1 indicators (t1, mprage, spgr, etc.)
- **File Format**: Only .nii and .nii.gz files accepted
- **File Size**: Must be under 500MB limit
- Check RAM (16GB+ required)
- Ensure license.txt is present
- **Failed jobs display detailed error messages** explaining exactly what went wrong (FreeSurfer issues, validation failures, etc.)

**Web interface won't load:**
- Confirm services are running (`./neuroinsight status`)
- Check port 8000 availability
- Clear browser cache

**Jobs interrupted or fail unexpectedly:**
- **System Sleep/Hibernation**: FreeSurfer processing takes 3-7 hours depending on image characteristics. **Set sleep timeout to 7+ hours** during processing to prevent interruptions.
- **Power Settings**: Set power management to 7+ hours sleep when plugged in
- **Screen Lock**: Disable automatic screen lock during long processing jobs
- **Virtual Machines**: Ensure host system won't sleep while VM is running
- **Docker Containers**: Containerized processing may be interrupted by system sleep

### Important System Configuration

#### Sleep/Hibernation Prevention
**Critical for successful processing:** FreeSurfer jobs run for extended periods (3-7 hours) depending on image resolution and quality. System sleep or hibernation will interrupt processing and cause job failures.

**Recommended Settings:**
- **Ubuntu**: System Settings → Power → Set to 7+ hours sleep when inactive
- **VMWare/VirtualBox**: Host power settings to 7+ hours sleep
- **Laptop Users**: Keep system plugged in and prevent lid close actions
- **Server Environments**: Configure power management policies for 7+ hour timeouts

**Warning:** Jobs interrupted by sleep/hibernation cannot be resumed and must be restarted from the beginning.

#### Memory Stability Tuning (Recommended)
These host-level tweaks reduce memory spikes and improve stability during CA Reg and other heavy FreeSurfer steps.

**1) Allow overcommit (helps large allocations succeed):**
```bash
sudo sysctl -w vm.overcommit_memory=1
```

Persist across reboot:
```bash
echo 'vm.overcommit_memory=1' | sudo tee /etc/sysctl.d/99-neuroinsight.conf
sudo sysctl --system
```

**2) Lower swappiness (use swap only when needed):**
```bash
sudo sysctl -w vm.swappiness=10
```

Persist across reboot:
```bash
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.d/99-neuroinsight.conf
sudo sysctl --system
```

**3) Disable Transparent Huge Pages (reduces fragmentation stalls):**
Immediate (runtime):
```bash
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/defrag
```

Persist via systemd:
```bash
sudo tee /etc/systemd/system/disable-thp.service >/dev/null <<'EOF'
[Unit]
Description=Disable Transparent Huge Pages (THP)

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'echo never > /sys/kernel/mm/transparent_hugepage/enabled; echo never > /sys/kernel/mm/transparent_hugepage/defrag'

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now disable-thp
```

**Notes:**
- `vm.swappiness` is a 0-100 tuning value (not GB or %); 10-20 is a balanced range.
- Use `sudo sysctl vm.overcommit_memory vm.swappiness` to verify active values.

## FAQ

### What is NeuroInsight?
Automated platform for hippocampal segmentation and analysis from T1-weighted MRI scans using FreeSurfer.

### System requirements?
Ubuntu 20.04+, 16GB+ RAM, 4+ CPU cores, 50GB storage, Docker, FreeSurfer license.

### How long does processing take?
3-7 hours per scan, depending on hardware, scan quality, and image resolution. **Important:** Set system sleep timeout to 7+ hours to prevent interruptions during processing.

### Is it free?
Yes, MIT licensed. FreeSurfer license is free for research use.

### Can I process multiple scans?
Yes, supports queuing system with configurable concurrency limits.

### What's processed?
Hippocampal volume measurements, shape analysis, asymmetry calculations, quality metrics.

### File formats supported?
NIfTI (.nii, .nii.gz) only. DICOM files must be converted to NIfTI format before upload using tools like `dcm2niix`.

### Can I export results?
Yes: PDF reports, CSV data, PNG/PDF images.

### Is it FDA approved?
No, research software only. Not for clinical diagnosis.


## Connecting to HPC (SLURM Cluster)

NeuroInsight can submit neuroimaging jobs to a remote HPC cluster via SSH and SLURM, running containerized tools (Singularity/Apptainer) on cluster nodes instead of locally.

### Prerequisites

Before connecting, ensure you have:

1. **An HPC account** with SSH access to a login node
2. **SLURM** scheduler running on the cluster
3. **Singularity or Apptainer** installed on the cluster (for containerized tools)
4. **SSH key-based authentication** configured (see Step 1 below)

### Step 1: Set Up SSH Key Authentication

The NeuroInsight server needs passwordless SSH access to your HPC login node. You must copy the server's public key to your HPC account.

#### 1a. Get the server's public key

On the NeuroInsight server, display the public key:

```bash
cat ~/.ssh/id_ed25519.pub
```

Copy the output (starts with `ssh-ed25519 ...`).

If no key exists, generate one:

```bash
ssh-keygen -t ed25519 -C "neuroinsight" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
```

#### 1b. Add the key to your HPC account

From a machine that can reach the HPC (your laptop, or the HPC terminal itself), add the key:

```bash
ssh <your-username>@<hpc-login-node> "mkdir -p ~/.ssh && echo '<paste-public-key-here>' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"
```

Or log into the HPC directly and append the key manually to `~/.ssh/authorized_keys`.

#### 1c. Verify it works

From the NeuroInsight server:

```bash
ssh -o BatchMode=yes <your-username>@<hpc-login-node> hostname
```

If this prints the HPC hostname without asking for a password, you're ready.

### Step 2: Network Access (If HPC Is Behind a Firewall)

If NeuroInsight runs on an external server (e.g., AWS) and the HPC is on a private university network, the server cannot reach the HPC directly. You need a **reverse SSH tunnel** from a machine that has VPN/network access.

#### Architecture

```
NeuroInsight Server (AWS)                    Your Laptop (VPN)                   HPC Login Node
      localhost:2222  ──── reverse tunnel ────→  laptop ──── VPN ────→  hpc-login.university.edu:22
```

#### Set up the reverse tunnel

On your **local machine** (with VPN connected), run:

```bash
ssh -i /path/to/server-key.pem \
    -L 3000:localhost:3000 \
    -L 8000:localhost:8000 \
    -R 2222:<hpc-login-node>:22 \
    ubuntu@<neuroinsight-server-ip>
```

| Flag | Purpose |
|------|---------|
| `-L 3000:localhost:3000` | Forward the UI to your browser |
| `-L 8000:localhost:8000` | Forward the API to your browser |
| `-R 2222:<hpc-login-node>:22` | Reverse tunnel: server port 2222 reaches HPC via your VPN |

Keep this terminal open while using NeuroInsight.

**When using the reverse tunnel**, enter these values in the UI:
- **Host**: `localhost`
- **Port**: `2222`
- **Username**: your HPC username

**If NeuroInsight can reach the HPC directly** (same network, or VPN on the server), use the actual hostname:
- **Host**: `hpc-login.university.edu`
- **Port**: `22`
- **Username**: your HPC username

### Step 3: Connect in the NeuroInsight UI

1. Open NeuroInsight in your browser
2. In the top toolbar, click the **HPC** tab (purple server icon)
3. Fill in the SSH connection fields:
   - **Host** — HPC login node hostname (or `localhost` if using a reverse tunnel)
   - **Username** — your HPC username
   - **Port** — `22` (or `2222` if using a reverse tunnel)
4. Click **Connect**
5. A green "Connected" badge appears on success

### Step 4: Configure SLURM Settings

After connecting:

1. Set the **Work Directory** — the path on the HPC where jobs will run (e.g., `/scratch/<username>` or `/home/<username>/neuroinsight`)
2. Click **Show SLURM Settings** to expand advanced options:
   - **Partition** — dropdown auto-populated from the cluster's `sinfo` output
   - **Account** — your SLURM allocation/account name (if required by your cluster)
   - **QoS** — quality of service tier (optional)
   - **Modules** — comma-separated list of modules to load before each job (e.g., `singularity/3.8, cuda/11.8`)
3. Click **Activate SLURM Backend**

All subsequent neuroimaging jobs will be submitted to the cluster via `sbatch`.

### Step 5: Monitor Jobs

Once connected, the **SLURM Queue Monitor** panel appears automatically, showing:
- Your SLURM jobs with status (RUNNING, PENDING, COMPLETED, FAILED)
- Auto-refreshes every 10 seconds
- Color-coded status indicators

You can also browse remote files on the HPC using the **File Browser** panel in HPC mode.

### Switching Back to Local

To return to local Docker execution:
- Click the **Local** tab in the backend selector, or
- Click **Disconnect** in the HPC panel

### Troubleshooting HPC Connection

| Problem | Solution |
|---------|----------|
| **"Connection timed out"** | HPC is unreachable — check VPN/firewall, verify hostname, set up reverse tunnel |
| **"Authentication failed"** | SSH key not on HPC — follow Step 1b to add the public key |
| **"Connection refused"** | Wrong port, or the hostname is a web portal (OOD) not an SSH server — use the actual login node |
| **"No SLURM partitions found"** | SLURM not available on this node — verify `sinfo` works when you SSH in manually |
| **Reverse tunnel not working** | Ensure your VPN is active and the SSH session with `-R` flag is still open |

### Important Notes

- **Open OnDemand (OOD)**: OOD servers are web portals and typically do not accept SSH connections. Use the underlying HPC login node hostname instead. You can find it by opening a terminal session within the OOD web interface.
- **SSH Agent Forwarding**: Not required — NeuroInsight uses key-based auth directly from the server.
- **Multiple Users**: Each user needs their own SSH key added to their HPC account.

---

## Connecting to XNAT

NeuroInsight can browse, download, and process data directly from any XNAT instance (CIDUR, CNDA, NITRC, Central, or your own).

### Prerequisites

1. **An XNAT account** with read access to at least one project
2. **Network access** from the NeuroInsight server to the XNAT instance (see "XNAT Behind a Firewall" below)

### Step 1: Connect to XNAT

1. Open NeuroInsight and click **Get Started**
2. Under **Data Source**, click the **XNAT** tab
3. Fill in:
   - **XNAT URL** — the full URL of the XNAT instance (e.g., `https://xnat.example.edu`)
   - **Username** — your XNAT username
   - **Password** — your XNAT password
4. Click **Connect**
5. A green "Connected" badge confirms the connection

### Step 2: Browse Data

After connecting, click **Browse** in the input section to open the XNAT Data Browser. The XNAT hierarchy is:

```
Project
 └── Subject
      └── Experiment (session)
           └── Scan
                └── Resource (NIFTI, DICOM, etc.)
                     └── Files
```

1. **Projects** — select the project containing your data
2. **Subjects** — click a subject to view their sessions
3. **Experiments** — click a session to view scans
4. **Scans** — click a scan to view available resources (NIFTI, DICOM, etc.)
5. **Resources** — click a resource to see individual files
6. **Files** — select the files you want to process, then click **Select for Processing**

Use the breadcrumb navigation at the top to go back to any level.

### Step 3: Process Data

After selecting files from XNAT, the files are downloaded to the NeuroInsight server and submitted to your chosen compute backend (Local Docker, Remote Server, or HPC/SLURM) for processing.

### XNAT Behind a Firewall (SSH Tunnel)

If NeuroInsight runs on an external server (e.g., AWS EC2) and the XNAT instance is on a private institutional network, the server cannot reach XNAT directly. Use an **SSH local port forward** through an intermediary that can reach both networks.

#### Architecture

```
NeuroInsight Server (AWS)                    Intermediary (HPC/VPN)                   XNAT Instance
      localhost:8443  ──── SSH tunnel ────→  hpc-login  ──── network ────→  xnat.university.edu:443
```

The intermediary can be any machine that:
- Is reachable from the NeuroInsight server via SSH
- Can reach the XNAT instance over the network (e.g., on the same campus network or VPN)

An HPC login node you are already connected to is a common choice.

#### Set up the tunnel

On the **NeuroInsight server**, run:

```bash
ssh -L 8443:<xnat-hostname>:443 <username>@<intermediary-host> -N
```

| Parameter | Example | Purpose |
|-----------|---------|---------|
| `8443` | `8443` | Local port on the NeuroInsight server that will proxy to XNAT |
| `<xnat-hostname>` | `xnat.university.edu` | The XNAT hostname as reachable from the intermediary |
| `443` | `443` | XNAT's HTTPS port (use `80` for HTTP, or `8080` if non-standard) |
| `<intermediary-host>` | `hpc-login.university.edu` | The SSH-accessible intermediary machine |
| `-N` | | Don't open a shell, just forward ports |

Keep this terminal open while using XNAT.

**Example** (tunneling through an HPC login node):

```bash
ssh -L 8443:xnat.your-institution.edu:443 youruser@hpc-login.your-institution.edu -N
```

#### Connect in the UI

When using the tunnel, enter:
- **XNAT URL**: `https://localhost:8443`
- **Skip SSL verification**: **checked** (required — see below)
- **Username / Password**: your XNAT credentials

### SSL Certificate Verification

When connecting through an SSH tunnel, the browser/server connects to `localhost:8443` but the XNAT server's SSL certificate was issued for its real hostname (e.g., `xnat.university.edu`). This hostname mismatch causes SSL verification to fail with an error like:

```
SSL certificate verification failed for https://localhost:8443
```

**Solution**: Check the **"Skip SSL verification"** checkbox in the XNAT Login form before clicking Connect. This is safe when using an SSH tunnel because the tunnel itself provides encrypted transport to the intermediary.

When connecting directly to an XNAT instance (no tunnel), leave SSL verification **enabled** unless the XNAT instance uses a self-signed certificate.

### XNAT on the Transfer Page

The XNAT connection is also available on the **Transfer** page for downloading/uploading data without processing. Click the **XNAT** tab in either the source or destination pane, enter credentials, and browse the same Project → Subject → Experiment → Scan hierarchy.

### Troubleshooting XNAT Connection

| Problem | Solution |
|---------|----------|
| **"Connection timed out"** | XNAT is unreachable — check network/VPN, set up an SSH tunnel if on a different network |
| **"SSL certificate verification failed"** | Check **"Skip SSL verification"** if using an SSH tunnel or self-signed certificate |
| **"Authentication failed (401)"** | Wrong username or password |
| **"Access denied (403)"** | Account lacks permission for this XNAT instance — contact your XNAT admin |
| **"XNAT REST API not found (404)"** | Incorrect URL — verify the URL points to the XNAT web root (not a sub-path) |
| **Empty project list** | Your account may not have read access to any projects — verify in the XNAT web UI |
| **Tunnel connection refused** | SSH tunnel may have closed — check and restart the `ssh -L` command |

### Important Notes

- **Session timeout**: XNAT sessions expire after inactivity (typically 15-30 minutes). If you get errors after being idle, click **Disconnect** and reconnect.
- **Large downloads**: When downloading many files or large datasets, ensure sufficient disk space on the NeuroInsight server.
- **XNAT versions**: NeuroInsight uses the standard XNAT REST API and works with XNAT 1.7+ instances.
- **No uploads during processing**: File uploads to XNAT require the experiment and resource to already exist. Use the XNAT web interface to create them first.

---

## Support

- **GitHub Issues**: Report bugs and request features
- **Documentation**: Check troubleshooting guide
- **FreeSurfer**: https://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferSupport


---

© 2025 NeuroInsight Research. All rights reserved.
