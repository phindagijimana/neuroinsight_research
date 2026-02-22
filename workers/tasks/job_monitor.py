"""
Job Monitor for NeuroInsight

Monitors running jobs and marks orphaned ones as failed.
Should be run periodically (e.g., every 5 minutes) via cron.
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.core.database import SessionLocal
from backend.models.job import Job, JobStatus
from backend.core.logging import get_logger

logger = get_logger(__name__)

def cleanup_orphaned_jobs():
    """
    Find jobs that have been RUNNING for too long (orphaned) and mark them as failed.
    
    A job is considered orphaned if:
    - Status is RUNNING
    - Started more than 5 hours ago (timeout for MRI processing)
    """
    db = SessionLocal()
    try:
        # Find orphaned jobs (running for more than 5 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=5)
        
        orphaned_jobs = db.query(Job).filter(
            Job.status == JobStatus.RUNNING,
            Job.started_at < cutoff_time
        ).all()
        
        for job in orphaned_jobs:
            logger.warning("marking_orphaned_job_as_failed", 
                         job_id=str(job.id), 
                         started_at=job.started_at)
            
            job.status = JobStatus.FAILED
            job.error_message = "Job was orphaned (worker crashed) - automatically marked as failed"
            job.completed_at = datetime.utcnow()
        
        if orphaned_jobs:
            db.commit()
            logger.info("orphaned_jobs_cleaned_up", count=len(orphaned_jobs))
        else:
            logger.debug("no_orphaned_jobs_found")
            
    except Exception as e:
        logger.error("job_cleanup_failed", error=str(e))
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_orphaned_jobs()
