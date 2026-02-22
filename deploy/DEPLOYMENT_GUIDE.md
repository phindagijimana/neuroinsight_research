# NeuroInsight Docker Deployment Guide

Complete guide for deploying NeuroInsight using the all-in-one Docker container.

## Overview

The all-in-one Docker deployment packages the entire NeuroInsight application into a single container, including:
- PostgreSQL 15 (Database)
- Redis 7 (Message broker)
- MinIO (Object storage)
- FastAPI Backend (REST API)
- Celery Workers (Job processing)
- React Frontend (Web UI)

## Prerequisites

- Docker 20.10 or later
- 8GB RAM minimum (16GB recommended)
- 15GB disk space (additional ~20GB for FreeSurfer image on first use)
- FreeSurfer license (free for research use)
- Docker socket access (automatically configured for FreeSurfer processing)

## Quick Start

### Step 1: Build the Image

```bash
cd /path/to/neuroinsight_local/deploy
./build.sh v1.0.0
```

### Step 2: Install and Run

```bash
./neuroinsight-docker install
```

This will:
- Find an available port (8000-8050)
- Detect FreeSurfer license automatically
- Create data volume
- Start all services
- Show access URL

### Step 3: Access Application

Open your browser to the URL shown (e.g., http://localhost:8000)

## Management Commands

### Basic Operations

```bash
# Start the application
./neuroinsight-docker start

# Stop the application
./neuroinsight-docker stop

# Restart services
./neuroinsight-docker restart

# Check status
./neuroinsight-docker status

# View logs
./neuroinsight-docker logs
./neuroinsight-docker logs backend
./neuroinsight-docker logs worker
```

### Health & Monitoring

```bash
# Check all services health
./neuroinsight-docker health

# Check FreeSurfer license
./neuroinsight-docker license
```

### Data Management

```bash
# Clean old jobs (older than 30 days)
./neuroinsight-docker clean

# Clean jobs with custom days
./neuroinsight-docker clean --days 7

# Recover a specific job
./neuroinsight-docker bring <job_id>
```

### Backup & Restore

```bash
# Backup all data
./neuroinsight-docker backup

# Restore from backup
./neuroinsight-docker restore /path/to/backup.tar.gz
```

### Updates

```bash
# Update to latest version
./neuroinsight-docker update
```

### Advanced

```bash
# Access container shell
./neuroinsight-docker shell

# Remove everything (including data)
./neuroinsight-docker remove
```

## Features

### Automatic Port Selection

The system automatically finds an available port in the 8000-8050 range. No manual configuration needed.

### Automatic License Detection

FreeSurfer license (`license.txt`) is automatically detected in:
1. Current directory
2. Parent directory (neuroinsight_local/)
3. Grandparent directory
4. Home directory

Just place your license in any of these locations.

### FreeSurfer Processing Architecture

The all-in-one container uses **Docker-in-Docker** for MRI processing:

**Main Container:** Application services (API, workers, database, Redis, MinIO)
**FreeSurfer Containers:** Spawned dynamically per job
- Image: `freesurfer/freesurfer:7.4.1` (~20GB)
- Naming: `freesurfer-job-{job_id}`
- Lifecycle: Automatically cleaned up after processing

**First Job Note:** The FreeSurfer image downloads automatically on first use (~20GB, one-time). Subsequent jobs use the cached image.

**Docker Socket:** The container mounts `/var/run/docker.sock` to enable spawning FreeSurfer containers. This is configured automatically.

### Data Persistence

All data is stored in a Docker volume (`neuroinsight-data`):
- Uploaded MRI files
- Processing results
- Database
- Logs

Data persists across container restarts and updates.

## Building & Publishing

### Build a Specific Version

```bash
./build.sh v1.0.0
```

### Publish to Docker Hub

```bash
# Login to Docker Hub
docker login

# Build and publish
./release.sh publish v1.0.0
```

This creates:
- `neuroinsight/allinone:v1.0.0`
- `neuroinsight/allinone:latest`

### List All Versions

```bash
./release.sh list
```

## Troubleshooting

### Container Won't Start

```bash
# Check Docker is running
docker ps

# Check logs
./neuroinsight-docker logs

# Check health
./neuroinsight-docker health
```

### Port Already in Use

The system automatically finds an available port. If you get a port error:

```bash
# Check what's using ports
lsof -i :8000-8050

# Or specify a different port range by editing neuroinsight-docker
```

### License Not Detected

```bash
# Check license status
./neuroinsight-docker license

# Manually mount license
docker stop neuroinsight
docker rm neuroinsight
docker run -d --name neuroinsight \
  -p 8000:8000 \
  -v neuroinsight-data:/data \
  -v /path/to/license.txt:/app/license.txt:ro \
  neuroinsight/allinone:latest
```

### Services Not Healthy

```bash
# Check individual service status
./neuroinsight-docker shell
supervisorctl status

# Restart a specific service
supervisorctl restart backend
supervisorctl restart worker
```

### Low Disk Space

```bash
# Clean old Docker images
docker system prune -a

# Clean old jobs
./neuroinsight-docker clean --days 7

# Check volume size
docker system df
```

## File Structure

```
deploy/
├── Dockerfile              # Container definition
├── docker-compose.yml      # Compose configuration
├── supervisord.conf        # Service management
├── entrypoint.sh          # Initialization script
├── healthcheck.sh         # Health check script
├── build.sh               # Build images
├── release.sh             # Publish to Docker Hub
├── neuroinsight-docker    # Management CLI
├── quick-start.sh         # Interactive setup
├── README_DOCKER.md       # This file
└── DEPLOYMENT_GUIDE.md    # Complete guide
```

## Technical Details

### Container Architecture

All services run in a single container, managed by Supervisord:

1. **PostgreSQL** (localhost:5432) - Database
2. **Redis** (localhost:6379) - Message broker
3. **MinIO** (localhost:9000) - Object storage
4. **Backend** (localhost:8000) - FastAPI API
5. **Worker** - Celery job processor
6. **Beat** - Task scheduler
7. **Monitor** - Job monitoring

### Data Directories

Inside container:
- `/data/uploads` - Uploaded MRI files
- `/data/outputs` - Processing results
- `/data/logs` - Application logs
- `/data/postgresql` - Database files
- `/data/redis` - Redis persistence
- `/data/minio` - Object storage

### Environment Variables

Auto-configured in container:
- `POSTGRES_HOST=localhost`
- `REDIS_HOST=localhost`
- `MINIO_ENDPOINT=localhost:9000`
- `UPLOAD_DIR=/data/uploads`
- `OUTPUT_DIR=/data/outputs`

### Network

Container exposes:
- Port 8000 (mapped to host port 8000-8050)

All internal services communicate via localhost.

## Advanced Usage

### Custom Port

Edit `neuroinsight-docker` script to change port range or force specific port.

### Multiple Instances

Run multiple instances on different ports:

```bash
docker run -d --name neuroinsight-8001 \
  -p 8001:8000 \
  -v neuroinsight-data-1:/data \
  neuroinsight/allinone:latest

docker run -d --name neuroinsight-8002 \
  -p 8002:8000 \
  -v neuroinsight-data-2:/data \
  neuroinsight/allinone:latest
```

### Docker Compose

```yaml
version: '3.8'
services:
  neuroinsight:
    image: neuroinsight/allinone:latest
    ports:
      - "8000:8000"
    volumes:
      - neuroinsight-data:/data
      - ./license.txt:/app/license.txt:ro
    restart: unless-stopped

volumes:
  neuroinsight-data:
```

```bash
docker-compose up -d
```

### Development Mode

Mount source code for live development:

```bash
docker run -d --name neuroinsight-dev \
  -p 8000:8000 \
  -v neuroinsight-data:/data \
  -v $(pwd)/../backend:/app/backend \
  -v $(pwd)/../frontend:/app/frontend \
  neuroinsight/allinone:latest
```

## Version Management

### Semantic Versioning

- **v1.0.0** - First stable release
- **v1.1.0** - New features (minor)
- **v1.0.1** - Bug fixes (patch)
- **v2.0.0** - Breaking changes (major)

### Release Channels

- `latest` - Most recent stable
- `v1.0.0` - Specific version
- `stable` - Long-term stable
- `v1.1.0-beta` - Pre-release

### Update Strategy

Users on `latest` tag get automatic updates:

```bash
./neuroinsight-docker update
```

Users on specific versions need to manually update:

```bash
docker pull neuroinsight/allinone:v1.1.0
# Then recreate container
```

## Security

### Default Security

- Services only accessible via localhost inside container
- Only port 8000 exposed to host
- Data isolated in Docker volume
- No default passwords in production

### Recommendations

- Keep Docker updated
- Run container as non-root (done by default)
- Don't expose container port to internet without reverse proxy
- Regular backups
- Monitor disk space

## Support

For issues:
1. Check logs: `./neuroinsight-docker logs`
2. Check health: `./neuroinsight-docker health`
3. Review main repository README and troubleshooting guides

## License

FreeSurfer license required for MRI processing. Free for research use.

Get license: https://surfer.nmr.mgh.harvard.edu/registration.html

---

© 2025 University of Rochester. All rights reserved.
