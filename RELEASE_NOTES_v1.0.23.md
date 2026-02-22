# NeuroInsight v1.0.23 Release Notes

## Critical Fix: Native Mode Path Configuration

Fixes incorrect HOST_UPLOAD_DIR and HOST_OUTPUT_DIR paths in native Linux installation that prevented FreeSurfer from accessing input files.

### Problem

Native installation (using `./neuroinsight install`) was setting environment variables incorrectly:

```bash
# Before (in .env file)
HOST_UPLOAD_DIR=$(pwd)/data/uploads  # Literal string, not expanded!
HOST_OUTPUT_DIR=$(pwd)/data/outputs  # Shell substitution not performed
```

Issues:
1. `$(pwd)` was written literally to `.env` file (not expanded during install)
2. Docker rejected volume mount: "includes invalid characters"
3. Even if accepted, paths pointed to wrong location (install directory instead of actual data directory)
4. Native app stores data in `~/.local/share/neuroinsight/` (XDG standard)
5. All FreeSurfer jobs failed immediately with exit code 125

### What's Fixed

**Updated install script** (`scripts/install.sh`):

Changed from:
```bash
HOST_UPLOAD_DIR=$(pwd)/data/uploads
HOST_OUTPUT_DIR=$(pwd)/data/outputs
```

To:
```bash
HOST_UPLOAD_DIR=$HOME/.local/share/neuroinsight/uploads
HOST_OUTPUT_DIR=$HOME/.local/share/neuroinsight/outputs
```

**Why this works:**
- `$HOME` expands during installation to user's home directory
- Matches where native backend actually stores data (`Path.home()` in Python)
- Points to correct location: `/home/username/.local/share/neuroinsight/`
- Works for any user on any system

### Technical Details

**Native Mode Data Storage:**
- Backend uses: `Path.home() / ".local" / "share" / "neuroinsight"` (XDG standard)
- Example: `/home/alice/.local/share/neuroinsight/uploads/`
- Workers spawn FreeSurfer containers that need to mount these directories
- HOST paths must match actual storage location

**Docker Mode (not affected):**
- Docker deployment uses auto-detection (v1.0.20)
- Inspects container mounts to find actual host paths
- No `.env` file used in Docker all-in-one container
- Already working correctly

**Files Modified:**
- `scripts/install.sh` - Fixed HOST path environment variables

### Impact

**Before Fix:**
```
Error: "$(pwd)/data/uploads" includes invalid characters for a local volume name
OR
Error: cannot find /input/filename.nii.gz
```
All native installations failed to process MRI files.

**After Fix:**
```
FreeSurfer container mounts: /home/user/.local/share/neuroinsight/uploads
Jobs process successfully with correct file access
```

### Platform Compatibility

**Works for any user:**
- User `alice` → `/home/alice/.local/share/neuroinsight/`
- User `bob` → `/home/bob/.local/share/neuroinsight/`
- User `ubuntu` → `/home/ubuntu/.local/share/neuroinsight/`

**Deployment modes:**
- Native Linux: Fixed (uses $HOME expansion)
- Docker: Already working (uses auto-detection)
- Windows/Mac: Uses different paths (APPDATA/Application Support)

### Upgrade Notes

**For existing native installations:**
1. Stop services: `./neuroinsight stop`
2. Update code: `git pull`
3. Manually fix `.env` file:
   ```bash
   sed -i "s|HOST_UPLOAD_DIR=.*|HOST_UPLOAD_DIR=$HOME/.local/share/neuroinsight/uploads|" .env
   sed -i "s|HOST_OUTPUT_DIR=.*|HOST_OUTPUT_DIR=$HOME/.local/share/neuroinsight/outputs|" .env
   ```
4. Restart: `./neuroinsight start`

**For fresh installations:**
- Install script automatically creates correct paths
- No manual intervention needed

### Related Issues

- Complements v1.0.18 (removed hardcoded Docker paths)
- Complements v1.0.20 (auto-detection for Docker mode)
- Only affects native Linux installations
