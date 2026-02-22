# NeuroInsight v1.0.25 Release Notes

## Critical Fix: Orphaned Container Cleanup

Fixes issue where deleted jobs left FreeSurfer containers running, blocking new jobs from starting despite showing 0 running jobs in database.

### Problem

When a job was deleted from the UI:
1. `delete_job` called `docker stop` to terminate the container
2. Container stopped but was NOT removed (`docker rm` not called)
3. Job record deleted from database
4. Container became "orphaned" (running/stopped but no database record)
5. Orphaned containers counted toward max_concurrent_jobs limit
6. New pending jobs couldn't start (blocked by orphan)
7. Jobs stuck at 0% even though database showed capacity

**Result:** Manually had to find and remove orphaned containers to unblock queue.

### What's Fixed

**Three-part cleanup strategy:**

1. **Complete container removal in delete_job**
   - Now calls both `docker stop` AND `docker rm -f`
   - Ensures container fully removed when job deleted
   - Prevents containers from becoming orphaned

2. **Automatic orphaned container detection**
   - New function `_cleanup_orphaned_containers()`
   - Lists all FreeSurfer containers via `docker ps -a`
   - Compares against active jobs in database
   - Removes any containers without active database records
   - Runs automatically before starting next job

3. **Cleanup called from all queue processing paths**
   - `process_job_queue()` - 60-second periodic check
   - `_start_next_pending_job()` - Called by delete/complete/fail
   - `start_next_pending_job()` - Worker function
   - Ensures orphans cleaned up regardless of code path

### Changes

**Files Modified:**
- `backend/services/job_service.py`
  - Added `docker rm -f` after `docker stop` in delete_job
  - Added `_cleanup_orphaned_containers()` function
  - Call cleanup in `process_job_queue()`
  - Call cleanup in `_start_next_pending_job()`
- `workers/tasks/processing_web.py`
  - Call cleanup in `start_next_pending_job()`

### Technical Details

**Container naming pattern:**
- FreeSurfer containers: `freesurfer-job-{job_id}`
- Easy to match container names to database job IDs

**Orphan detection logic:**
```python
1. Get all containers matching "freesurfer-job-*"
2. Extract job IDs from container names
3. Query database for PENDING/RUNNING jobs
4. Find containers with no matching active job
5. Remove orphaned containers with docker rm -f
```

**Why this works:**
- Only checks against PENDING/RUNNING jobs (active jobs)
- Completed/failed jobs have no container (already cleaned up by worker)
- Deleted jobs have no database record (orphans)
- Safe to remove any container not in active job list

### Impact

**Before:**
- Deleting a job → orphaned container
- Next pending job stuck at 0%
- Manual cleanup required: find container ID → docker rm -f
- Production users blocked without terminal access

**After:**
- Deleting a job → container fully removed
- Next pending job starts immediately (1-2 seconds)
- Automatic orphan cleanup if any slip through
- No manual intervention needed

### Upgrade Instructions

**For Docker Deployment:**
```bash
cd neuroinsight_local
git pull origin master
docker build -t phindagijimana321/neuroinsight:latest .
docker push phindagijimana321/neuroinsight:latest

# Update running instance
./deploy/neuroinsight-docker stop
./deploy/neuroinsight-docker remove
./deploy/neuroinsight-docker install
```

**For Native Deployment:**
```bash
cd /path/to/neuroinsight_local
git pull origin master
./neuroinsight restart
```

### Verification

**Test the fix:**
1. Upload and start a job
2. Delete the running job from UI
3. Upload another job (should be queued)
4. Verify next job starts within 2 seconds (no 0% hang)
5. Check no orphaned containers: `docker ps -a | grep freesurfer-job`

**Expected behavior:**
- Deleted job's container removed immediately
- Next pending job picks up automatically
- No orphaned containers remain
- Queue processes smoothly

### Related Issues

**Complements v1.0.24:**
- v1.0.24: Fixed race condition (job monitor killing jobs)
- v1.0.25: Fixed orphaned containers (blocking queue)
- Together: Complete robust queue processing

**Why both fixes needed:**
- v1.0.24: Ensures job gets started_at timestamp
- v1.0.25: Ensures no orphans block concurrency
- Both required for reliable job queue

## Files Changed

- `backend/services/job_service.py`
- `workers/tasks/processing_web.py`

## Version

v1.0.25
