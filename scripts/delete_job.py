#!/usr/bin/env python3
"""
NeuroInsight job deletion utility.
Delete a specific job by ID from command line.
"""

import argparse
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import SessionLocal
from backend.services.job_service import JobService


def main():
    parser = argparse.ArgumentParser(
        description="Delete a specific NeuroInsight job by ID",
        epilog="This permanently deletes the job record and all associated files."
    )
    parser.add_argument(
        "job_id",
        help="Job ID to delete (e.g., d1a2c36e)"
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    args = parser.parse_args()
    job_id = args.job_id.strip()
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Get job info first
        from backend.models.job import Job
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            print(f"Error: Job not found: {job_id}")
            print(f"")
            print(f"To list all jobs, run:")
            print(f"  ./neuroinsight status")
            return 1
        
        # Show job info
        print("=" * 50)
        print("Job Information")
        print("=" * 50)
        print(f"Job ID:       {job.id}")
        print(f"Patient:      {job.patient_name}")
        print(f"Status:       {job.status.value}")
        print(f"File:         {job.original_filename}")
        print(f"Uploaded:     {job.created_at}")
        if job.completed_at:
            print(f"Completed:    {job.completed_at}")
        if job.error_message:
            print(f"Error:        {job.error_message[:100]}")
        print("=" * 50)
        print()
        
        # Confirm deletion (unless --force)
        if not args.force:
            response = input(f"Delete this job? This action cannot be undone. (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("Deletion cancelled.")
                return 0
        
        # Delete the job
        print(f"Deleting job {job_id}...")
        deleted = JobService.delete_job(db, job_id)
        
        if deleted:
            print(f"[OK] Job {job_id} deleted successfully")
            print(f"  - Database record removed")
            print(f"  - Uploaded file removed")
            print(f"  - Output directory removed")
            print(f"  - Associated metrics removed")
            return 0
        else:
            print(f"Error: Failed to delete job {job_id}")
            return 1
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
