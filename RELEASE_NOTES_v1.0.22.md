# NeuroInsight v1.0.22 Release Notes

## Critical Fix: Eliminate Duplicate Job Submissions

Fixes critical race condition where queued jobs were submitted to Celery multiple times but never actually processed, causing jobs to stay at 0% and eventually fail.

### Problem

When a running job was deleted or failed, the next pending job would:
1. Be submitted to Celery 3 times from redundant code paths
2. Not actually process because all 3 workers skipped it
3. Stay at 0% progress then fail

Root cause: Multiple functions calling "start next job" logic simultaneously:
- `JobService.fail_job()` was called twice (inner and outer exception handlers)  
- Each call triggered `process_job_queue()` which submitted to Celery
- Finally block also called `start_next_pending_job()` for a 3rd submission
- `process_job_queue()` didn't mark job as RUNNING before submission
- All workers saw job as RUNNING and skipped it

### What's Fixed

**Eliminated redundant fail_job calls:**
- Removed duplicate call from inner exception handler
- Only outer exception handler calls `fail_job()` once

**Made process_job_queue atomic:**
- Now marks job as RUNNING before submitting to Celery
- Prevents race conditions between multiple queue processing attempts

**Removed duplicate start logic:**
- Finally block no longer calls `start_next_pending_job()`  
- Job queue processing is now handled exclusively by `JobService.fail_job()` and `JobService.complete_job()`

**Updated worker idempotency:**
- Workers now accept jobs in RUNNING status (previously only PENDING)
- Added check to skip if job is already being processed by another task

### Changes

**Files Modified:**
- `workers/tasks/processing_web.py` - Removed duplicate fail_job call, removed finally block queue start, updated idempotency logic
- `backend/services/job_service.py` - Added atomic status update in process_job_queue

### Upgrade

Docker (recommended):
```bash
cd deploy
docker pull phindagijimana321/neuroinsight:latest
./neuroinsight-docker restart
```

### Verification

Test the fix:
1. Upload 2+ MRI scans
2. Delete the first job while it's running (RUNNING status)
3. Verify second job immediately starts processing and progresses normally
4. Check logs show only ONE "job_started_celery_mode" message per job

### Details

Before v1.0.22, when job A was deleted:
```
[Worker-3] fail_job called (1st time) → process_job_queue → Submit job B (1st)
[Worker-3] fail_job called (2nd time) → process_job_queue → Submit job B (2nd)  
[Worker-3] finally block → start_next_pending_job → Submit job B (3rd)
[Worker-5] Received job B → Status: RUNNING → Skip
[Worker-6] Received job B → Status: RUNNING → Skip
[Worker-7] Received job B → Status: RUNNING → Skip
```

After v1.0.22:
```
[Worker-3] fail_job called once → process_job_queue → Mark RUNNING → Submit job B
[Worker-5] Received job B → Status: RUNNING → Process normally
```

This completes the race condition fix started in v1.0.21.
