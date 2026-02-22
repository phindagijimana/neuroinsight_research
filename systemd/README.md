# NeuroInsight Systemd Services

User-level systemd services for NeuroInsight. **No sudo required!**

## Features

[YES] **Automatic restart on failure** - Services automatically recover from crashes  
[YES] **No sudo required** - User-level services run under your account  
[YES] **Boot persistence** - Services start automatically on login  
[YES] **Professional logging** - Integrated with systemd journal  
[YES] **Clean management** - Standard `systemctl` commands  
[YES] **Dependency management** - Services start in correct order  

## Prerequisites

Before installing systemd services, ensure:

1. **Linux with systemd** - Most modern Linux distributions (Ubuntu 16.04+, Debian 8+, Fedora, CentOS 7+, Arch, etc.)
2. **Docker installed** - For FreeSurfer processing and infrastructure containers
3. **User in docker group** - Required for worker to access Docker:
   ```bash
   sudo usermod -aG docker $USER
   # Then logout/login, or run: newgrp docker
   ```
4. **Python virtual environment** - Already set up in `venv/` directory

The installation script will check these requirements and guide you through any missing steps.

## Quick Start

### 1. Install Services

```bash
cd systemd
./install_systemd.sh
```

This will:
- Copy service files to `~/.config/systemd/user/`
- Enable auto-start on login
- Enable user linger (services run even after logout)

### 2. Start Docker Infrastructure

Before starting NeuroInsight services, ensure Docker containers are running:

```bash
# Start PostgreSQL, Redis, MinIO
cd ..
./neuroinsight start-docker
```

Or manually:

```bash
docker run -d --name neuroinsight-postgres \
  -e POSTGRES_DB=neuroinsight \
  -e POSTGRES_USER=neuroinsight \
  -e POSTGRES_PASSWORD=JkBTFCoM0JepvhEjvoWtQlfuy4XBXFTnzwExLxe1rg \
  -p 5432:5432 --restart unless-stopped \
  postgres:15-alpine

docker run -d --name neuroinsight-redis \
  -p 6379:6379 --restart unless-stopped \
  redis:7-alpine redis-server --appendonly yes --requirepass redis_secure_password

docker run -d --name neuroinsight-minio \
  -e MINIO_ROOT_USER=neuroinsight_minio \
  -e MINIO_ROOT_PASSWORD=minio_secure_password \
  -p 9000:9000 -p 9001:9001 --restart unless-stopped \
  minio/minio:latest server /data --console-address :9001
```

### 3. Start NeuroInsight Services

```bash
# Start all services
systemctl --user start neuroinsight-backend
systemctl --user start neuroinsight-worker
systemctl --user start neuroinsight-beat
systemctl --user start neuroinsight-monitor

# Or use helper script
cd ..
./neuroinsight start-systemd
```

### 4. Check Status

```bash
# Check all services
systemctl --user status neuroinsight-*

# Check individual service
systemctl --user status neuroinsight-worker

# Or use helper
./neuroinsight status-systemd
```

## Service Management

### Start Services

```bash
systemctl --user start neuroinsight-backend   # Backend API
systemctl --user start neuroinsight-worker    # Celery worker
systemctl --user start neuroinsight-beat      # Periodic task scheduler
systemctl --user start neuroinsight-monitor   # Job monitor

# Start all at once
systemctl --user start neuroinsight-*
```

### Stop Services

```bash
systemctl --user stop neuroinsight-backend
systemctl --user stop neuroinsight-worker
systemctl --user stop neuroinsight-beat
systemctl --user stop neuroinsight-monitor

# Stop all at once
systemctl --user stop neuroinsight-*
```

### Restart Services

```bash
# Restart individual service
systemctl --user restart neuroinsight-worker

# Restart all
systemctl --user restart neuroinsight-*
```

### Enable/Disable Auto-Start

```bash
# Enable (start on login)
systemctl --user enable neuroinsight-*

# Disable (don't start on login)
systemctl --user disable neuroinsight-*
```

## View Logs

### Using journalctl (recommended)

```bash
# Follow backend logs (live)
journalctl --user -u neuroinsight-backend -f

# Follow worker logs (live)
journalctl --user -u neuroinsight-worker -f

# View last 100 lines
journalctl --user -u neuroinsight-worker -n 100

# View logs since specific time
journalctl --user -u neuroinsight-worker --since "1 hour ago"

# View all NeuroInsight logs
journalctl --user -u neuroinsight-* -f
```

### Using log files

Logs are also written to the project directory:

```bash
tail -f ~/src/desktop_alone_web_1/celery_worker.log
tail -f ~/src/desktop_alone_web_1/celery_beat.log
tail -f ~/src/desktop_alone_web_1/neuroinsight.log
tail -f ~/src/desktop_alone_web_1/job_monitor.log
```

## Troubleshooting

### Services not starting?

```bash
# Check status
systemctl --user status neuroinsight-worker

# View detailed logs
journalctl --user -u neuroinsight-worker -n 50

# Check if Docker containers are running
docker ps | grep neuroinsight
```

### Worker keeps restarting?

```bash
# Check worker logs
journalctl --user -u neuroinsight-worker -f

# Common issues:
# 1. Redis not running → Start Redis container
# 2. Database not running → Start PostgreSQL container
# 3. Configuration error → Check environment variables
```

### Change configuration

Edit service files in `~/.config/systemd/user/`, then reload:

```bash
systemctl --user daemon-reload
systemctl --user restart neuroinsight-*
```

### Completely remove systemd services

```bash
cd systemd
./uninstall_systemd.sh
```

## User Linger

User linger allows your services to run even when you're logged out.

```bash
# Enable linger (may require sudo)
sudo loginctl enable-linger $USER

# Check linger status
loginctl show-user $USER | grep Linger

# Disable linger
sudo loginctl disable-linger $USER
```

Without linger, services stop when you log out (like closing SSH session).

## Service Dependencies

Services start in this order:

1. **neuroinsight-backend** - Backend API (first)
2. **neuroinsight-worker** - Celery worker (requires backend)
3. **neuroinsight-beat** - Beat scheduler (requires worker)
4. **neuroinsight-monitor** - Job monitor (optional)

Systemd automatically manages these dependencies.

## Comparison: Systemd vs Manual Start

| Feature | Systemd | Manual (`./neuroinsight start`) |
|---------|---------|---------------------|
| Auto-restart on crash | [YES] Yes | [NO] No |
| Start on boot | [YES] Yes | [NO] No |
| Run after logout | [YES] Yes (with linger) | [NO] No |
| Logging | [YES] journalctl + files | [WARNING] Files only |
| Process supervision | [YES] systemd | [WARNING] Manual |
| Production ready | [YES] Yes | [WARNING] Development |

## Best Practices

1. **Development**: Use `./neuroinsight start` for quick iterations
2. **Production**: Use systemd services for robust deployment
3. **Testing**: Use systemd to ensure services recover from failures
4. **Distribution**: Include systemd installer in your app package

## Advanced Configuration

### Custom environment variables

Edit `~/.config/systemd/user/neuroinsight-worker.service`:

```ini
[Service]
Environment="MY_VARIABLE=value"
Environment="ANOTHER_VAR=123"
```

Then reload:

```bash
systemctl --user daemon-reload
systemctl --user restart neuroinsight-worker
```

### Resource limits

Add to service file:

```ini
[Service]
MemoryLimit=4G
CPUQuota=200%
```

### Email alerts on failure

Install mail handler:

```ini
[Unit]
OnFailure=status-email@%n.service
```

## Uninstall

```bash
./uninstall_systemd.sh
```

This stops all services, disables them, and removes service files.

## Support

For issues:
1. Check logs: `journalctl --user -u neuroinsight-worker`
2. Verify Docker: `docker ps`
3. Check status: `systemctl --user status neuroinsight-*`
