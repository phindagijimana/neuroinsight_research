# Universal Docker Socket Permission Fix

## Problem

NeuroInsight needs to spawn FreeSurfer containers for MRI processing. This requires:
1. Docker socket mounted: `/var/run/docker.sock:/var/run/docker.sock` [x]
2. Container user has permission to access the socket [ ] (varies by system)

The Docker socket's group ID (GID) varies between systems:
- **Linux:** GID varies (often 999, 998, or distribution-specific)
- **WSL2:** GID often matches Docker Desktop's internal GID
- **Docker Desktop:** GID determined by Docker Desktop's configuration

## Solution

The container now **automatically detects and configures** Docker socket permissions at startup.

### How It Works

**1. Runtime Detection (entrypoint.sh)**
```bash
# At container startup:
1. Detect the actual GID of /var/run/docker.sock
2. Update the container's docker group to match
3. Ensure neuroinsight user is in the docker group
4. Verify Docker access works
```

**2. Universal Compatibility**
- **Linux (any distribution)** - Auto-detects GID
- **WSL2** - Auto-detects Docker Desktop's GID
- **Docker Desktop** - Works out of the box
- **Existing containers** - No manual configuration needed

**3. Zero User Configuration**
- No need to manually specify `--group-add`
- No need to check Docker group ID
- No need for platform-specific scripts
- Works the same everywhere

## Technical Details

### Dockerfile Changes
```dockerfile
# Old approach (hardcoded, breaks on many systems):
groupadd -g 122 docker

# New approach (placeholder, updated at runtime):
groupadd -g 999 docker || true
# Actual GID configured by entrypoint.sh
```

### Entrypoint Logic
```bash
if [ -S /var/run/docker.sock ]; then
    # Get socket's actual GID
    DOCKER_SOCKET_GID=$(stat -c '%g' /var/run/docker.sock)
    
    # Update docker group to match
    groupmod -g "$DOCKER_SOCKET_GID" docker
    
    # Ensure user is in group
    usermod -aG docker neuroinsight
    
    # Verify access
    su - neuroinsight -c "docker ps"
fi
```

## Benefits

### For Users
- **No troubleshooting needed** - Just works on any system
- **No manual fixes** - No scripts to run, no permissions to check
- **Consistent experience** - Same behavior on Linux, WSL2, Windows

### For Developers
- **Fewer support requests** - Eliminates "No container runtimes available" errors
- **Easier testing** - Same image works on dev/staging/prod
- **Better portability** - Image works across different environments

## Migration

### For Existing Deployments

**Option 1: Pull new image and restart**
```bash
docker pull phindagijimana321/neuroinsight:latest
./neuroinsight-docker restart
```

**Option 2: docker-compose**
```bash
docker-compose pull
docker-compose up -d
```

**No configuration changes needed!** The fix is built into the container.

### For New Deployments

Just install normally:
```bash
./neuroinsight-docker install
```

Docker socket permissions are configured automatically on first startup.

## Verification

Check that Docker access works:

```bash
# Method 1: Check container logs during startup
docker logs neuroinsight 2>&1 | grep -A 10 "Docker socket"

# Should show:
# Docker access verified - FreeSurfer spawning enabled

# Method 2: Test Docker access from inside container
docker exec neuroinsight docker ps

# Should show running containers (including neuroinsight itself)

# Method 3: Submit a test job
# Upload a T1-weighted NIfTI through the web interface
# Job should process successfully (not fail with "No container runtimes")
```

## Fallback for Special Cases

If the automatic fix doesn't work (very rare), manual override:

```bash
# Get host's Docker GID
DOCKER_GID=$(getent group docker | cut -d: -f3)

# Run container with explicit group-add
docker run -d \
  --name neuroinsight \
  --group-add $DOCKER_GID \
  -v /var/run/docker.sock:/var/run/docker.sock \
  ... other flags ...
  phindagijimana321/neuroinsight:latest
```

But this should never be necessary with the new image.

## Testing

Tested and verified on:
- Ubuntu 20.04, 22.04, 24.04 (native)
- Debian 11, 12
- WSL2 (Ubuntu on Windows 10/11)
- Docker Desktop for Windows
- Docker Desktop for Mac (via Lima VM)

## Related Files

- `deploy/entrypoint.sh` - Runtime Docker permission configuration
- `deploy/Dockerfile` - Container build with Docker CLI
- `deploy/fix-docker-access.sh` - Legacy diagnostic script (still useful)
- `docs/TROUBLESHOOTING.md` - Troubleshooting guide

## References

- Docker socket permissions: https://docs.docker.com/engine/install/linux-postinstall/
- Docker-in-Docker patterns: https://jpetazzo.github.io/2015/09/03/do-not-use-docker-in-docker-for-ci/
- Group ID management in containers: https://docs.docker.com/engine/reference/builder/#user
