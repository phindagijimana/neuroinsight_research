# Troubleshooting Guide

## Quick Diagnosis

```bash
# Basic system check
./neuroinsight status        # Check all services
./neuroinsight health        # Quick health overview

# Docker diagnostics
./fix_docker.sh             # Comprehensive Docker check
./quick_docker_fix.sh       # Quick Docker fix

# Detailed logs
docker-compose logs          # View container logs
tail -f neuroinsight.log     # Follow application logs
```

## Deployment-Specific Issues

### Desktop Application Issues

#### App Won't Start or Crashes

**Symptoms:**
- Desktop app doesn't launch
- App opens then immediately closes
- Error message about Docker

**Solutions:**

**Check Docker is Running:**
```bash
# Linux
docker ps

# Windows
# Check Docker Desktop system tray icon (should be green)
```

**Restart Docker:**
```bash
# Linux
sudo systemctl restart docker

# Windows
# Right-click Docker Desktop icon → Restart
```

**Check App Logs:**

Linux AppImage:
```bash
# Run from terminal to see errors
./NeuroInsight-1.0.0.AppImage
```

Windows:
- Check logs in: `%APPDATA%\NeuroInsight\logs\`

**Reinstall:**
- Delete app and download fresh installer from [releases](https://github.com/phindagijimana/neuroinsight_desktop/releases)

#### Port Already in Use (Desktop App)

**Symptoms:**
- App shows "Port 8000 in use"
- Can't access web interface

**Solution:**

Desktop app automatically finds available ports (8000-8050). If all ports are in use:

```bash
# Linux - Find what's using ports
sudo netstat -tlnp | grep :800

# Windows - Find processes
netstat -ano | findstr :800

# Stop conflicting services
docker stop neuroinsight  # If another instance running
```

#### Docker Image Download Fails

**Symptoms:**
- App stuck on "Pulling NeuroInsight image"
- Download very slow or fails

**Solutions:**
- Check internet connection
- Image is large (~2GB for NeuroInsight container)
- First FreeSurfer image is ~7GB (one-time download)
- Retry: Restart the app

**For more Desktop App issues:** See [Desktop App Repository](https://github.com/phindagijimana/neuroinsight_desktop/issues)

---

### Docker Deployment Issues

#### Container Won't Start

**Symptoms:**
- `docker ps` shows no neuroinsight container
- Installation completes but container exits
- `neuroinsight-docker status` shows "not running"

**Diagnosis:**
```bash
# Check container status
docker ps -a | grep neuroinsight

# View container logs
docker logs neuroinsight

# Check Docker daemon
systemctl status docker  # Linux
# or Docker Desktop status icon (Windows)
```

**Solutions:**

**For Linux Docker:**
```bash
# Restart Docker daemon
sudo systemctl restart docker

# Remove and recreate container
cd neuroinsight_local/deploy
./neuroinsight-docker stop
docker rm -f neuroinsight
./neuroinsight-docker install

# Check logs for errors
./neuroinsight-docker logs
```

**For Windows Docker:**
```powershell
# Restart Docker Desktop
# System tray → Docker → Restart

# Remove and recreate
cd neuroinsight_windows
.\neuroinsight-docker.ps1 stop
docker rm -f neuroinsight
.\neuroinsight-docker.ps1 install
```

#### Port Already in Use

**Symptoms:**
- Installation fails with "port 8000 already in use"
- Container starts but not accessible

**Solutions:**

**Linux Docker:**
```bash
# Find what's using port 8000
sudo netstat -tlnp | grep :8000

# Stop conflicting service
sudo systemctl stop <service-name>

# Or use different port
./neuroinsight-docker install --port 8001
```

**Windows Docker:**
```powershell
# Find what's using port
netstat -ano | findstr :8000

# Kill process (use PID from output)
taskkill /PID <pid> /F

# Or install on different port
.\neuroinsight-docker.ps1 install -Port 8001
```

#### License Not Detected

**Symptoms:**
- Container logs show "WARNING: FreeSurfer license not found"
- Jobs fail with license errors

**Solutions:**

**Linux Docker:**
```bash
# Check license location
ls -la ../license.txt

# License should be in neuroinsight_local/ (parent of deploy/)
# Not in deploy/ folder

# Verify mount in logs
./neuroinsight-docker logs | grep license

# Restart after adding license
./neuroinsight-docker restart
```

**Windows Docker:**
```powershell
# Place license.txt in neuroinsight_windows/ folder
# Same location as neuroinsight-docker.ps1

# Check detection
.\neuroinsight-docker.ps1 license

# Restart container
.\neuroinsight-docker.ps1 restart
```

#### Docker Permissions (Linux)

**Symptoms:**
- "permission denied" when running docker commands
- Must use sudo for docker

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or:
newgrp docker

# Verify
docker ps
```

#### WSL2 Issues (Windows)

**Symptoms:**
- Docker Desktop shows "WSL integration failed"
- "There was a problem with WSL" error
- Containers become unresponsive

**Solutions:**

**Quick Fix:**
```powershell
# PowerShell as Administrator
wsl --shutdown
# Wait 10 seconds
# Restart Docker Desktop
```

**Enable WSL Integration:**
1. Docker Desktop → Settings
2. Resources → WSL Integration
3. Enable for your Ubuntu distribution
4. Apply & Restart

**Enable Systemd (if needed):**
```bash
# In WSL terminal
sudo nano /etc/wsl.conf

# Add:
[boot]
systemd=true

# Save, then:
exit
```

```powershell
# PowerShell
wsl --shutdown
wsl
```

#### Docker Volume Issues

**Symptoms:**
- Data not persisting between restarts
- "volume not found" errors

**Solutions:**

**Linux Docker:**
```bash
# List volumes
docker volume ls | grep neuroinsight

# Inspect volume
docker volume inspect neuroinsight_data

# Recreate if corrupted
./neuroinsight-docker stop
docker volume rm neuroinsight_data
./neuroinsight-docker install
```

**Windows Docker:**
```powershell
# Same commands work in PowerShell
docker volume ls | Select-String neuroinsight
.\neuroinsight-docker.ps1 stop
docker volume rm neuroinsight_data
.\neuroinsight-docker.ps1 install
```

#### FreeSurfer Container Spawn Failures

**Symptoms:**
- Jobs fail with: "No container runtimes available"
- Jobs fail with: "Failed to spawn FreeSurfer container"
- Error: "FreeSurfer processing failed"
- Works during install but fails when processing jobs

**This is a Docker-in-Docker (DinD) permission issue** - the NeuroInsight container can't access Docker to spawn FreeSurfer containers.

**Quick Fix:**

```bash
cd /path/to/neuroinsight_local/deploy

# Run automated fix script
./fix-docker-access.sh

# This will:
# 1. Diagnose the issue
# 2. Detect your Docker group ID
# 3. Recreate container with proper permissions
# 4. Verify Docker access
```

**Manual Diagnosis:**

```bash
# 1. Check Docker socket permissions
ls -la /var/run/docker.sock

# 2. Get Docker group ID
getent group docker | cut -d: -f3

# 3. Test if container can access Docker
docker exec neuroinsight docker ps

# If this fails → DinD is broken, follow fix below
```

**Manual Fix for Linux/WSL:**

```bash
cd neuroinsight_local/deploy

# Stop and remove container
./neuroinsight-docker stop
./neuroinsight-docker remove

# Get Docker group ID
DOCKER_GID=$(getent group docker | cut -d: -f3)
echo "Docker GID: $DOCKER_GID"

# Reinstall (script now auto-adds docker group)
./neuroinsight-docker install

# Verify Docker access from inside container
docker exec neuroinsight docker ps
# Should show running containers if working
```

**For WSL2 Specific Issues:**

```bash
# Ensure Docker Desktop integration is enabled
# 1. Docker Desktop → Settings → Resources → WSL Integration
# 2. Enable for your Ubuntu distribution
# 3. Apply & Restart

# Restart WSL completely (in PowerShell as Admin)
wsl --shutdown

# Restart Docker Desktop
# Reopen WSL and try again
```

**For docker-compose users:**

Before running `docker-compose up`, set the Docker GID:

```bash
# Export Docker group ID
export DOCKER_GID=$(getent group docker | cut -d: -f3)

# Now run docker-compose
docker-compose up -d

# Verify
docker exec neuroinsight docker ps
```

**Verification:**

After applying the fix, test:

```bash
# 1. Check container can access Docker
docker exec neuroinsight docker ps

# 2. Check container can pull images
docker exec neuroinsight docker pull hello-world

# 3. Submit a test job through the web interface
```

**Why This Happens:**

The NeuroInsight container needs to spawn FreeSurfer containers for processing. This requires:
1. Docker socket mounted: `/var/run/docker.sock:/var/run/docker.sock` ✓
2. Container user has permission to access socket ✗ (missing)

The fix adds the Docker group to the container, giving it permission to use Docker.

#### Update Failures

**Symptoms:**
- `update` command fails
- New version not pulling

**Solutions:**

**Linux Docker:**
```bash
# Backup first
./neuroinsight-docker backup

# Force pull new image
docker pull phindagijimana321/neuroinsight:latest

# Reinstall
./neuroinsight-docker stop
docker rm -f neuroinsight
./neuroinsight-docker install
```

**Windows Docker:**
```powershell
# Backup first
.\neuroinsight-docker.ps1 backup

# Force pull
docker pull phindagijimana321/neuroinsight:latest

# Reinstall
.\neuroinsight-docker.ps1 stop
docker rm -f neuroinsight
.\neuroinsight-docker.ps1 install
```

---

## Common Issues

### Jobs Stuck in "Pending" Status

#### Symptom
- Jobs remain in "pending" status indefinitely
- Upload completes successfully but processing never starts
- Frontend continuously polls but status never changes from "pending"
- Jobs appear in queue but never transition to "running"

#### Diagnosis Steps

1. **Check if Celery worker is running:**
   ```bash
   ps aux | grep celery
   # Should show celery worker processes
   ```

2. **Check Redis connection:**
   ```bash
   redis-cli ping
   # Should respond with "PONG"
   ```

3. **Check Celery worker logs:**
   ```bash
   tail -f celery_worker.log
   # Look for connection errors or task pickup messages
   ```

4. **Test Celery connectivity:**
   ```bash
   # Activate virtual environment first
   source venv/bin/activate

   # Test task submission
   python -c "
   from workers.tasks.processing_web import celery_app
   result = celery_app.send_task('process_mri_task', args=['test-job-id'])
   print('Task sent successfully - check worker logs')
   "
   ```

#### Common Solutions

**Solution 1: Start Celery Worker**
If Celery worker is not running:
```bash
# Navigate to NeuroInsight directory
cd neuroinsight_local

# Activate virtual environment
source venv/bin/activate

# Start Celery worker (run in background or separate terminal)
celery -A workers.tasks.processing_web worker --loglevel=info --concurrency=1

# Or use the NeuroInsight management script
./neuroinsight start
```

**Solution 2: Redis Connection Issues**
If Redis is not running or accessible:
```bash
# Check if Redis is installed and running
sudo systemctl status redis-server

# If not running, start it
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Or install Redis if missing
sudo apt update && sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server

# Test connection
redis-cli ping
```

**Solution 3: Environment Variables**
Ensure proper environment variables are set:
```bash
# Check current settings
echo $REDIS_URL
echo $REDIS_PASSWORD

# Set defaults if needed
export REDIS_URL="redis://:redis_secure_password@localhost:6379/0"
export REDIS_PASSWORD="redis_secure_password"

# Restart services after changing environment
./neuroinsight stop
./neuroinsight start
```

**Solution 4: Restart All Services**
If nothing else works, restart the entire NeuroInsight stack:
```bash
./neuroinsight stop
sleep 5
./neuroinsight start
```

#### Prevention
- Always check `./neuroinsight status` after installation
- Ensure Redis is running before starting NeuroInsight
- Monitor Celery worker logs during initial testing
- Keep Celery worker running continuously

### Insufficient Disk Space

**"Insufficient disk space" during installation:**
```bash
# Error: Insufficient disk space. NeuroInsight requires at least 45GB free.
# Error: Detected: XXgB available
```

**Impact:**
- NeuroInsight requires 45GB+ free disk space
- FreeSurfer processing needs substantial temporary storage
- Docker images (FreeSurfer 7.4.1) require ~20GB
- Job outputs can accumulate over time

**Solutions:**

**Quick Fix - Free Up Space:**
```bash
# 1. Clean Docker resources (most effective)
docker system prune -af --volumes
# This removes:
# - All stopped containers
# - Unused images
# - Unused networks
# - Dangling build cache
# Typically frees: 15-25GB

# 2. Check space after cleanup
df -h /

# 3. Retry installation
./neuroinsight install
```

**Additional Cleanup Options:**
```bash
# Clean old job outputs (if previously installed)
rm -rf ~/.local/share/neuroinsight/outputs/old-job-*

# Clean system caches
sudo apt clean
sudo apt autoclean

# Clean journal logs (keeps last 7 days)
sudo journalctl --vacuum-time=7d

# Clean pip cache
rm -rf ~/.cache/pip
```

**Check Disk Usage:**
```bash
# Overall disk usage
df -h /

# Find large directories
du -h ~ | sort -rh | head -20

# Docker space usage
docker system df
```

**Prevention:**
```bash
# Regular maintenance (run monthly)
docker system prune -a --volumes

# Monitor disk usage
df -h /
```

### Docker Installation Issues

**"Input/output error" during installation:**
```bash
# Error: /usr/bin/docker: Input/output error
# Error: Docker test failed. Please check Docker installation.
```

**Causes:**
- Docker daemon not running
- Docker daemon crashed or unresponsive
- User not in docker group
- Permission issues with Docker socket

**Solutions:**

**Option 1: Quick Fix Script (Recommended)**
```bash
# Get latest fixes
git pull origin master

# Run comprehensive diagnostic
./fix_docker.sh

# Or use quick fix
./quick_docker_fix.sh

# Then retry installation
./neuroinsight install
```

**Option 2: Manual Fix**
```bash
# 1. Restart Docker daemon
sudo systemctl restart docker
sudo systemctl enable docker

# 2. Add user to docker group
sudo usermod -aG docker $USER

# 3. Apply group changes (or logout/login)
newgrp docker

# 4. Test Docker
docker run --rm hello-world

# 5. Retry installation
./neuroinsight install
```

**Option 3: Temporary Bypass (if Docker works manually)**
```bash
# If Docker works but install check fails
sed -i '473,477s/^/# /' scripts/install.sh  # Comment out Docker test
./neuroinsight install                       # Run installation
git checkout scripts/install.sh              # Restore original file
```

**Verification:**
```bash
# Test Docker is working
docker --version
docker run --rm hello-world
sudo systemctl status docker
```

### WSL/Docker Desktop Issues

**"There was a problem with WSL" or "wsl.exe --unmount docker_data.vhdx" errors:**
```bash
# Error symptoms:
# - Docker Desktop shows WSL integration errors
# - wsl.exe --unmount docker_data.vhdx: exit status 0xffffffff
# - Docker becomes unresponsive during processing
# - NeuroInsight jobs fail mid-processing
```

**Causes:**
- Docker Desktop WSL integration becomes unstable
- Virtual hard disk (VHDX) unmount failures
- Resource conflicts during heavy processing
- Windows/WSL updates interrupting Docker

**Solutions:**

**Option 1: Automated Fix Scripts (Recommended)**
```bash
# Get latest fixes
git pull origin master

# Windows PowerShell (run as Administrator):
.\fix_wsl_docker.ps1

# Then in WSL terminal:
./fix_docker_wsl.sh

# Restart NeuroInsight
./neuroinsight start
```

**Option 2: Windows PowerShell Reset**
```powershell
# Run in PowerShell as Administrator
Stop-Process -Name "*docker*" -Force
wsl --shutdown
Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
```

**Option 3: Complete WSL Reset**
```bash
# On Windows - PowerShell as Administrator
wsl --shutdown
wsl --unregister docker-desktop  # Removes Docker data - use carefully!

# Restart Docker Desktop
# Re-enable WSL integration in Docker Desktop settings
```

**Option 4: Factory Reset (Last Resort)**
- Docker Desktop → Settings → Reset to Factory Defaults
- Restart Docker Desktop completely
- Re-enable WSL integration

**Prevention:**
```bash
# Regular maintenance
docker system prune -a --volumes

# Monitor WSL resources
wsl --list --verbose

# Keep Docker Desktop updated
# Avoid Windows updates during processing
```

**Verification:**
```bash
# Test Docker in WSL
docker run --rm hello-world

# Check WSL integration
wsl --list --verbose

# Restart NeuroInsight
./neuroinsight status
```

### Memory Limitations

**"LIMITED MEMORY DETECTED" warning during installation:**
```
[WARNING] LIMITED MEMORY DETECTED: 7GB
[WARNING] MRI processing requires 16GB+ RAM
```

**Impact:**
- Web interface works with 8GB+ RAM
- MRI processing requires 16GB+ minimum
- Large datasets need 32GB+ RAM
- Processing may fail or crash with insufficient memory

**Solutions:**

**For Evaluation/Testing (8GB+ RAM):**
```bash
# Continue with installation despite warnings
# Web interface and basic features work
./neuroinsight install  # Answer 'y' to continue
```

**For Production MRI Processing (16GB+ RAM):**
```bash
# Upgrade system RAM
# Or use cloud instance with adequate memory
# AWS: t3.large (16GB), c5.xlarge (32GB)
# GCP: n1-standard-4 (15GB), n1-standard-8 (30GB)
```

**Memory Monitoring:**
```bash
# Check current usage
free -h
docker stats  # Container memory usage

# Monitor during processing
./neuroinsight monitor
```

### Application Won't Start

**Backend fails with import errors:**
```bash
# Ensure you're in correct directory
pwd  # Should show neuroinsight_local

# Check Python virtual environment
source venv/bin/activate
pip list | grep fastapi
```

**Database connection failed:**
```bash
# Check PostgreSQL container
docker-compose ps postgres

# Reset database
docker-compose down -v
docker-compose up -d db
```

### FreeSurfer License Issues

**License not found:**
- Verify `license.txt` exists in project root
- Check file permissions: `ls -la license.txt`
- Run: `./neuroinsight license`

**Processing shows mock data:**
- License file missing or invalid
- FreeSurfer container cannot access license
- Check container logs: `docker-compose logs freesurfer`

### MRI Processing Issues

**Jobs stuck in pending:**
- See "Jobs Stuck in 'Pending' Status" section above
- Check worker status: `./neuroinsight status`
- Verify Redis running: `redis-cli ping`
- Restart workers: `./neuroinsight stop && ./neuroinsight start`

**Processing fails:**
- Verify T1 indicators in filename (t1, mprage, etc.)
- Check RAM (16GB+ required, 32GB+ recommended)
- Ensure file format supported (.nii, .nii.gz only)
- Check FreeSurfer license: `./neuroinsight license` (native) or `./neuroinsight-docker license` (Docker)
- **Docker:** Ensure FreeSurfer container can spawn: `docker ps -a | grep freesurfer`

**Out of memory errors:**
- Increase system RAM to 32GB+ for large datasets
- Process one job at a time
- Close other applications during processing
- Monitor memory usage: `free -h`

**File format issues:**
- Only NIfTI files (.nii, .nii.gz) are supported
- DICOM files must be converted locally first
- Verify T1 sequence indicators in filename

### Web Interface Issues

**Interface won't load:**
- Confirm port 8000 available: `netstat -tlnp | grep 8000`
- Check backend running: `./neuroinsight status`
- Clear browser cache, try different browser

**Upload fails:**
- Verify file size < 1GB
- Check T1 indicators in filename
- Ensure supported format (.nii, .nii.gz only)

### Performance Issues

**Processing slow:**
- Check CPU usage: `top`
- Verify adequate RAM (32GB+ recommended)
- Ensure SSD storage for data directory

**System unresponsive:**
- Limit concurrent jobs to 1
- Monitor resources: `docker stats`
- Restart services during off-peak hours

## Recovery Procedures

### Reset Database
```bash
./neuroinsight stop
docker-compose down -v  # Removes all data
./neuroinsight start  # Recreates fresh database
```

### Clear Job Queue
```bash
# Stop workers first
./neuroinsight stop

# Clear Redis queue
docker-compose exec redis redis-cli FLUSHALL

# Restart
./neuroinsight start
```

### Full System Reset
```bash
./neuroinsight stop
docker-compose down -v --remove-orphans
docker system prune -a  # Careful: removes all unused containers
./neuroinsight reinstall  # Get complete reinstallation guide
```

## Quick Diagnostic Commands

### Native Linux
```bash
./neuroinsight status        # Overall status
./neuroinsight logs          # View logs
./neuroinsight license       # Check license
ps aux | grep celery         # Check workers
docker ps                    # Check containers
```

### Linux Docker
```bash
./neuroinsight-docker status      # Container status
./neuroinsight-docker health      # Health check
./neuroinsight-docker logs        # View logs
./neuroinsight-docker logs worker # Worker logs
docker ps -a | grep neuroinsight  # Container list
```

### Windows Docker
```powershell
.\neuroinsight-docker.ps1 status       # Container status
.\neuroinsight-docker.ps1 health       # Health check
.\neuroinsight-docker.ps1 logs         # View logs
docker ps -a | Select-String neuroinsight  # Container list
```

## Support

- **Native Linux logs:** `tail -f neuroinsight.log` or `./neuroinsight logs`
- **Docker logs:** `./neuroinsight-docker logs` or `.\neuroinsight-docker.ps1 logs`
- **Docker issues (Linux):** Run `./fix_docker.sh` or `./quick_docker_fix.sh`
- **System diagnostics:** `./neuroinsight status` or `./neuroinsight-docker status`
- **GitHub Issues:** Report bugs with diagnostic output
- **FreeSurfer Support:** https://surfer.nmr.mgh.harvard.edu/fswiki/FreeSurferSupport

---

© 2025 University of Rochester. All rights reserved.
