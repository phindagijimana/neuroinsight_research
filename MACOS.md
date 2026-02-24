# macOS Support Implementation Guide

**Status:** Not yet implemented  
**Target Version:** v2.0.0 or later  
**Effort:** 1-2 hours implementation + 2-3 hours testing

---

## Problem: Docker-in-Docker on macOS

### Why Current Implementation Breaks on macOS

Docker Desktop on macOS runs in a VM. Volume paths are translated:

```
Linux Native:
  /var/lib/docker/volumes/... → Exists on host filesystem

macOS Docker Desktop:
  /var/lib/docker/volumes/... → Exists inside VM, NOT on macOS
  
Result: FreeSurfer container can't find files
```

### Current Code (Breaks on macOS)

```python
# mri_processor.py ~line 2620
host_upload_dir = os.getenv('HOST_UPLOAD_DIR')
# = /var/lib/docker/volumes/neuroinsight-data/_data/uploads

docker_cmd = [
    "-v", f"{host_upload_dir}:/input:ro",  # Path doesn't exist on macOS
]
```

---

## Solution 1: Volume Sharing with `--volumes-from`

### Concept

Instead of mounting host paths, share volumes directly between containers:

```bash
# Current (breaks on macOS)
docker run -v /var/lib/docker/volumes/.../uploads:/input ...

# Solution (works everywhere)
docker run --volumes-from neuroinsight ...
```

### How It Works

```
NeuroInsight Container (parent)
  └─ Volume: neuroinsight-data:/data
      └─ /data/uploads/file.nii
      └─ /data/outputs/

FreeSurfer Container (child)
  └─ --volumes-from neuroinsight
       Automatically gets same /data volume
      No path translation needed
      Works on Linux, Windows, macOS
```

---

## Implementation

### File to Modify

**`neuroinsight_local/pipeline/processors/mri_processor.py`**

### Code Changes

#### 1. Add Detection Function (around line 2614)

```python
def _get_volume_mount_strategy(self):
    """Determine volume mounting strategy for FreeSurfer container."""
    in_container = os.path.exists('/.dockerenv')
    
    if not in_container:
        # Native mode
        return {'strategy': 'absolute_paths', 'use_volumes_from': False}
    
    # Check for explicit host paths (Linux traditional mode)
    host_upload = os.getenv('HOST_UPLOAD_DIR')
    host_output = os.getenv('HOST_OUTPUT_DIR')
    
    if host_upload and host_upload.strip() and host_output and host_output.strip():
        # Use host paths (backward compatible)
        return {
            'strategy': 'host_paths',
            'use_volumes_from': False,
            'input_dir': host_upload,
            'output_dir': host_output
        }
    
    # Modern approach: volumes-from (works on all platforms)
    parent_container = os.getenv('HOSTNAME', 'neuroinsight')
    return {
        'strategy': 'volumes_from',
        'use_volumes_from': True,
        'parent_container': parent_container,
        'input_dir': '/data/uploads',
        'output_dir': '/data/outputs'
    }
```

#### 2. Modify Docker Command (around line 2713)

```python
# Get mount strategy
mount_strategy = self._get_volume_mount_strategy()

# Adjust paths based on strategy
if mount_strategy['use_volumes_from']:
    abs_input_dir = mount_strategy['input_dir']        # /data/uploads
    abs_freesurfer_dir = Path(mount_strategy['output_dir']) / str(self.job_id)
    abs_freesurfer_dir = str(abs_freesurfer_dir)
    
    docker_cmd = [
        "docker", "run",
        "--volumes-from", mount_strategy['parent_container'],  # Key change
        "-v", f"{abs_license_path}:/usr/local/freesurfer/license.txt:ro",
        ...
        FREESURFER_CONTAINER_IMAGE,
        "/bin/bash", "-c",
        f"recon-all -i {abs_input_dir}/{nifti_path.name} -s {subject_id} "
        f"-sd {abs_freesurfer_dir} ..."
    ]
else:
    # Traditional host path mounting (existing behavior)
    docker_cmd = [
        "docker", "run",
        "-v", f"{abs_input_dir}:/input:ro",
        "-v", f"{abs_freesurfer_dir}:/subjects",
        ...
    ]
```

#### 3. Update docker-compose.yml (Optional)

Make `HOST_*` variables optional:

```yaml
environment:
  # Optional: Only set if you want explicit host paths (Linux)
  # If omitted, will use --volumes-from (works on all platforms)
  # - HOST_UPLOAD_DIR=/var/lib/docker/volumes/neuroinsight-data/_data/uploads
  # - HOST_OUTPUT_DIR=/var/lib/docker/volumes/neuroinsight-data/_data/outputs
```

---

## Platform Behavior

| Platform | HOST_* Set? | Behavior |
|----------|-------------|----------|
| Linux | Yes | Uses host paths (current) |
| Linux | No | Uses --volumes-from (new) |
| Windows | Yes/No | Uses --volumes-from |
| macOS | Yes/No | Uses --volumes-from **FIXED** |

---

## Testing Checklist

### Linux
- [ ] With `HOST_*` env vars → Works (no regression)
- [ ] Without `HOST_*` env vars → Works (new behavior)
- [ ] Process MRI file → Completes successfully
- [ ] Output files accessible

### macOS
- [ ] Start container → No errors
- [ ] Upload MRI file → Saves successfully
- [ ] Process job → FreeSurfer finds input file
- [ ] Job completes → Output accessible
- [ ] Check logs → No path errors

### Windows
- [ ] Start container → Works
- [ ] Process MRI → Works (no regression)

---

## Backward Compatibility

**100% Backward Compatible**

- Existing deployments with `HOST_*` → No changes
- New deployments without `HOST_*` → Uses --volumes-from
- No breaking changes
- Easy rollback: Just set `HOST_*` env vars

---

## Additional UI Fixes for macOS Electron

### Bug: System Tray Notification Crash

**File:** `neuroinsight_electron/src/main/main.js` line 87-90

**Current (crashes on macOS):**
```javascript
tray.displayBalloon({  // Windows-only API!
  title: 'NeuroInsight',
  content: 'App is still running'
});
```

**Fix:**
```javascript
if (process.platform === 'win32' && tray) {
  tray.displayBalloon({
    title: 'NeuroInsight',
    content: 'App is still running'
  });
}
```

### Other Minor Issues

1. **Tray icon format** - Use Template.png for native macOS look
2. **App menu structure** - Add macOS-style app menu (optional)
3. **Code signing** - Requires Apple Developer account ($99/yr)

---

## Deployment Strategy

### Phase 1: Fix DinD (This Document)
1. Implement Solution 1 in `mri_processor.py`
2. Test on Linux (verify no regression)
3. Commit and push to `main`
4. Build new Docker image `v1.0.15`

### Phase 2: Test macOS
1. Have macOS user test Docker deployment
2. Verify FreeSurfer processing works
3. Collect feedback

### Phase 3: Electron macOS Build (Optional)
1. Fix UI bugs (displayBalloon, icons)
2. Add macOS to GitHub Actions workflow
3. Test build locally
4. Decide on code signing

---

## Notes

- **MinIO:** Already supports macOS (no changes needed)
- **Storage strategy:** Hybrid local+MinIO works on macOS
- **Same container:** Electron uses same Docker image, fix applies automatically
- **Cost:** No Apple Developer account needed for Docker deployment
- **Priority:** Low-Medium (most research institutions use Linux)

---

## Reference Links

- Issue: Docker-in-Docker path translation on macOS
- Solution: `--volumes-from` container volume sharing
- Docker docs: https://docs.docker.com/engine/reference/run/#volume-shared-filesystems
- Alternative: MinIO-based architecture (more complex, v2.0.0)

---

**Last Updated:** 2026-02-06  
**Decision:** Implement for v2.0.0 if macOS user demand exists
