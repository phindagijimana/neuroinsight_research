# NeuroInsight Docker Deployment

All-in-one Docker container for easy deployment and distribution.

## What's Included

Single container with all services:
- PostgreSQL 15 (Database)
- Redis 7 (Message broker)
- MinIO (Object storage)
- FastAPI Backend (REST API)
- Celery Workers (Job processing)
- React Frontend (Web UI)

**FreeSurfer Processing:**
- Spawns separate FreeSurfer containers per job (Docker-in-Docker)
- First job downloads FreeSurfer image (~20GB, one-time)
- Containers automatically cleaned up after processing

## Quick Start

### 1. Build the Image

```bash
cd /path/to/neuroinsight_local/deploy
./build.sh v1.0.0
```

### 2. Install and Run

```bash
./neuroinsight-docker install
```

That's it! The system will:
- Automatically find an available port (8000-8050)
- Auto-detect your FreeSurfer license
- Create persistent data storage
- Start all services

### 3. Access Application

Open browser to the URL shown (e.g., http://localhost:8000)

## Basic Commands

```bash
# Start/Stop
./neuroinsight-docker start
./neuroinsight-docker stop
./neuroinsight-docker restart

# Status & Health
./neuroinsight-docker status
./neuroinsight-docker health

# View Logs
./neuroinsight-docker logs
./neuroinsight-docker logs backend
./neuroinsight-docker logs worker

# Data Management
./neuroinsight-docker clean              # Clean old jobs (30+ days)
./neuroinsight-docker clean --days 7     # Clean jobs older than 7 days
./neuroinsight-docker bring <job_id>     # Recover specific job

# Backup & Restore
./neuroinsight-docker backup
./neuroinsight-docker restore /path/to/backup.tar.gz

# Updates
./neuroinsight-docker update             # Update to latest version

# Advanced
./neuroinsight-docker shell              # Access container shell
./neuroinsight-docker remove             # Remove everything
```

## Requirements

- Docker 20.10 or later
- 8GB RAM minimum (16GB recommended)
- 15GB disk space (additional ~20GB for FreeSurfer image)
- FreeSurfer license (free for research)
- Docker socket access (for FreeSurfer container spawning)

## Features

### Automatic Port Selection
Finds available port in 8000-8050 range automatically.

### Automatic License Detection
Detects `license.txt` in:
- Current directory
- Parent directory
- Home directory

### Data Persistence
All data stored in `neuroinsight-data` Docker volume:
- Uploaded MRI files
- Processing results
- Database
- Logs

Data persists across restarts and updates.

## Building & Publishing

### Build Specific Version

```bash
./build.sh v1.0.0        # Build v1.0.0
./build.sh               # Build as 'latest'
```

### Publish to Docker Hub

```bash
docker login
./release.sh publish v1.0.0
```

Creates:
- `neuroinsight/allinone:v1.0.0`
- `neuroinsight/allinone:latest`

### List Versions

```bash
./release.sh list
```

## For End Users

End users can pull from Docker Hub without needing source code:

```bash
# Pull latest version
docker pull neuroinsight/allinone:latest

# Or specific version
docker pull neuroinsight/allinone:v1.0.0

# Then install
./neuroinsight-docker install
```

## Documentation

- **README_DOCKER.md** - This file (quick reference)
- **DEPLOYMENT_GUIDE.md** - Complete deployment guide with troubleshooting
- **Main README** - See `../README.md` for overall project documentation
- **User Guide** - See `../USER_GUIDE.md` for usage instructions
- **Troubleshooting** - See `../TROUBLESHOOTING.md` for common issues

## Support

For detailed information:
1. See `DEPLOYMENT_GUIDE.md` in this directory
2. Check main repository `README.md`
3. Review `USER_GUIDE.md` for usage
4. Check `TROUBLESHOOTING.md` for common issues

For issues:
```bash
./neuroinsight-docker logs        # Check logs
./neuroinsight-docker health      # Check service health
./neuroinsight-docker status      # Check overall status
```

---

© 2025 University of Rochester. All rights reserved.
