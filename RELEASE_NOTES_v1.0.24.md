# NeuroInsight v1.0.24 Release Notes

## Critical Fix: Job Monitor Race Condition

Fixes race condition where job monitor prematurely fails jobs that are transitioning from PENDING to RUNNING state.

### Problem

When a job was picked up from the queue:
1. `process_job_queue` marked job as RUNNING
2. Set status in database but did NOT set `started_at`
3. Submitted job to Celery task queue
4. Job monitor checked for orphaned containers during gap between submission and execution
5. Found job with status=RUNNING but no `started_at` and no container
6. Grace period check skipped (required `started_at` to exist)
7. Job failed immediately with "Processing interrupted - container stopped unexpectedly"
8. Worker finally picked up task but job already deleted from database

Result: Jobs automatically picked from queue would fail within seconds before processing even started.

### What's Fixed

**Four-part fix (Belt + Suspenders approach):**

1. **Set started_at in ALL queue processing functions** (fixes root cause)
   - `process_job_queue` - Set `started_at` when marking job as RUNNING
   - `_start_next_pending_job` - Set `started_at` when marking job as RUNNING (called by delete)
   - `start_next_pending_job` (worker) - Set `started_at` when marking job as RUNNING
   - Ensures every RUNNING job has a start time regardless of code path
   - Grace period calculated from correct reference point

2. **Add fallback in job monitor** (defensive coding)
   - Use `created_at` as fallback if `started_at` missing
   - Prevents false positives even if `started_at` somehow not set
   - Maintains backward compatibility

3. **Edge case handling in worker** (extra safety)
   - Worker checks if job is RUNNING but `started_at` missing
   - Sets timestamp if needed (shouldn't happen with fix #1)
   - Logs when this defensive code triggers

### Technical Details

**Files Modified:**
- `backend/services/job_service.py` - Set `started_at` in `process_job_queue` and `_start_next_pending_job`
- `backend/services/task_management_service.py` - Use `created_at` as fallback for grace period
- `workers/tasks/processing_web.py` - Set `started_at` in `start_next_pending_job` + handle edge case

**Grace Period Logic:**
- Monitor uses 7-hour grace period (from `processing_timeout` setting)
- Previously: Grace period only applied if `started_at` existed
- Now: Uses `started_at` or falls back to `created_at`
- Jobs get full grace period during startup transition

### Impact

**Before Fix:**
- Jobs picked from queue would fail immediately
- Error: "Processing interrupted - container stopped unexpectedly"
- Race condition between queue processing and job monitor

**After Fix:**
- Jobs transition smoothly from PENDING → RUNNING → Processing
- Grace period properly applied during startup
- No premature failures due to timing gaps

### Testing

Verified with race condition scenario:
1. Upload job while another is running (goes to queue)
2. Delete running job
3. Queued job automatically starts (v1.0.22 fix)
4. Job monitor doesn't interfere during startup (v1.0.24 fix)
5. Job processes successfully

### Upgrade Notes

No database migrations required. Changes are backward compatible.

Existing RUNNING jobs without `started_at` will use `created_at` for grace period calculation.

### Related Issues

- Complements v1.0.22 (race condition in job queue)
- Works with v1.0.23 (native mode path fixes)
- Requires all three fixes for complete queue→processing workflow
