"""
Task management service for canceling/revoking Celery tasks and stopping processes.

This service handles graceful cancellation of running or pending jobs.
Extended with job monitoring for desktop mode.
"""

import os
import signal
import subprocess as subprocess_module
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from backend.core.logging import get_logger
from backend.core.config import get_settings
# Celery only available in server mode
try:
    from workers.celery_app import celery_app
except ImportError:
    celery_app = None

logger = get_logger(__name__)


class TaskManagementService:
    """Service for managing task cancellation and process termination."""
    
    @staticmethod
    def revoke_celery_task(task_id: str, terminate: bool = False) -> bool:
        """
        Revoke a Celery task.
        
        Args:
            task_id: Celery task ID
            terminate: If True, terminate running task; if False, only revoke pending tasks
            
        Returns:
            True if revocation was successful
        """
        try:
            celery_app.control.revoke(task_id, terminate=terminate)
            logger.info("celery_task_revoked", task_id=task_id, terminate=terminate)
            return True
        except Exception as e:
            logger.warning("celery_task_revoke_failed", task_id=task_id, error=str(e))
            return False
    
    @staticmethod
    def find_celery_task_id(job_id: UUID) -> Optional[str]:
        """
        Find the Celery task ID for a given job.
        
        This searches active and scheduled tasks to find the task ID.
        
        Args:
            job_id: Job UUID
            
        Returns:
            Celery task ID if found, None otherwise
        """
        try:
            inspect = celery_app.control.inspect()
            
            # Check active tasks
            active = inspect.active()
            if active:
                for worker, tasks in active.items():
                    for task in tasks:
                        args = task.get('args', [])
                        if args and len(args) > 0 and str(args[0]) == str(job_id):
                            task_id = task.get('id')
                            logger.info("celery_task_found_active", job_id=str(job_id), task_id=task_id)
                            return task_id
            
            # Check scheduled/reserved tasks
            scheduled = inspect.scheduled()
            if scheduled:
                for worker, tasks in scheduled.items():
                    for task in tasks:
                        request = task.get('request', {})
                        args = request.get('args', [])
                        if args and len(args) > 0 and str(args[0]) == str(job_id):
                            task_id = request.get('id')
                            logger.info("celery_task_found_scheduled", job_id=str(job_id), task_id=task_id)
                            return task_id
            
            logger.warning("celery_task_not_found", job_id=str(job_id))
            return None
            
        except Exception as e:
            logger.warning("celery_task_search_failed", job_id=str(job_id), error=str(e))
            return None
    
    @staticmethod
    def terminate_fastsurfer_process(job_id: UUID) -> bool:
        """
        Find and terminate FastSurfer processes for a given job.
        
        Args:
            job_id: Job UUID
            
        Returns:
            True if processes were found and terminated
        """
        try:
            import psutil
            
            job_id_str = str(job_id)
            terminated_count = 0
            
            # Find processes related to this job
            for proc in psutil.process_iter(['pid', 'cmdline', 'name']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    cmdline_str = ' '.join(cmdline) if cmdline else ''
                    
                    # Check if this process is related to our job
                    if job_id_str in cmdline_str or (job_id_str.split('-')[0] in cmdline_str and 'fastsurfer' in cmdline_str.lower()):
                        logger.info(
                            "fastsurfer_process_found",
                            job_id=job_id_str,
                            pid=proc.info['pid'],
                            cmdline=cmdline_str[:200]
                        )
                        
                        # Terminate the process
                        try:
                            proc.terminate()
                            terminated_count += 1
                        except psutil.NoSuchProcess:
                            pass
                        except Exception as e:
                            logger.warning("fastsurfer_terminate_failed", pid=proc.info['pid'], error=str(e))
                    
                    # Also check for parent-child relationships
                    try:
                        parent = proc.parent()
                        if parent:
                            parent_cmdline = ' '.join(parent.info.get('cmdline', [])) if parent.info.get('cmdline') else ''
                            if job_id_str in parent_cmdline or 'fastsurfer' in parent_cmdline.lower():
                                proc.terminate()
                                terminated_count += 1
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if terminated_count > 0:
                logger.info("fastsurfer_processes_terminated", job_id=job_id_str, count=terminated_count)
                
                # Give processes a moment to terminate gracefully
                import time
                time.sleep(2)
                
                # Force kill if still running
                for proc in psutil.process_iter(['pid', 'cmdline']):
                    try:
                        cmdline = ' '.join(proc.info.get('cmdline', [])) if proc.info.get('cmdline') else ''
                        if job_id_str in cmdline and 'fastsurfer' in cmdline.lower():
                            proc.kill()
                            logger.info("fastsurfer_process_killed", pid=proc.info['pid'])
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                return True
            else:
                logger.info("no_fastsurfer_processes_found", job_id=job_id_str)
                return False
                
        except ImportError:
            logger.warning("psutil_not_available", note="Cannot terminate FastSurfer processes without psutil")
            # Fallback: try using pgrep and pkill
            try:
                job_id_str = str(job_id)
                result = subprocess_module.run(
                    ['pgrep', '-f', job_id_str],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            logger.info("fastsurfer_process_terminated_fallback", pid=pid)
                        except (ProcessLookupError, ValueError):
                            pass
                    
                    return len(pids) > 0
                
                return False
            except Exception as e:
                logger.warning("fastsurfer_termination_fallback_failed", error=str(e))
                return False
        except Exception as e:
            logger.error("fastsurfer_termination_failed", job_id=str(job_id), error=str(e))
            return False
    
    @staticmethod
    def cancel_job_task(job_id: UUID, job_status: str) -> bool:
        """
        Cancel a job's Celery task and terminate associated processes.
        
        Args:
            job_id: Job UUID
            job_status: Current job status (to determine cancellation strategy)
            
        Returns:
            True if cancellation was attempted
        """
        from backend.models.job import JobStatus
        
        cancelled = False
        
        # Find and revoke Celery task
        task_id = TaskManagementService.find_celery_task_id(job_id)
        if task_id:
            # Terminate if running, just revoke if pending
            terminate = (job_status == JobStatus.RUNNING.value)
            cancelled = TaskManagementService.revoke_celery_task(task_id, terminate=terminate)
        
        # Terminate FastSurfer processes if job is running
        if job_status == JobStatus.RUNNING.value:
            TaskManagementService.terminate_fastsurfer_process(job_id)
        
        return cancelled

    @staticmethod
    def check_for_container_job_mismatches(db_session=None) -> List[dict]:
        """
        Check for jobs marked as RUNNING but whose Docker containers are not actually running.
        This detects jobs that were interrupted by system sleep/shutdown.

        Returns:
            List of jobs that were marked as failed due to container mismatch
        """
        from sqlalchemy.orm import Session
        from backend.core.database import SessionLocal
        from backend.models.job import Job, JobStatus
        from backend.services import JobService

        db = db_session or SessionLocal()
        settings = get_settings()
        mismatch_grace_seconds = settings.processing_timeout
        try:
            # Find all running jobs
            running_jobs = db.query(Job).filter(Job.status == JobStatus.RUNNING).all()

            failed_jobs = []
            for job in running_jobs:
                # Determine expected container name (stored or derived)
                container_name = job.docker_container_id or f"{settings.freesurfer_container_prefix}{job.id}"

                # Avoid false positives right after job start
                # Use created_at as fallback if started_at not yet set (defensive coding)
                reference_time = job.started_at or job.created_at
                if reference_time:
                    elapsed_seconds = (datetime.utcnow() - reference_time).total_seconds()
                    if elapsed_seconds < mismatch_grace_seconds:
                        continue

                # Check if the container is running
                if container_name:
                    try:
                        # Check if container is actually running
                        import subprocess
                        result = subprocess.run(
                            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
                            capture_output=True, text=True, timeout=10
                        )

                        # If container name is not in output, container is not running
                        if container_name not in result.stdout:
                            logger.warning(
                                "container_job_mismatch_detected",
                                job_id=str(job.id),
                                container_id=container_name,
                                reason="Container not running but job status is RUNNING"
                            )

                            # Mark job as failed
                            error_message = "Processing interrupted - container or task stopped unexpectedly. Job remained in running state."
                            JobService.fail_job(db, job.id, error_message)

                            # Best-effort cleanup of any leftover container
                            try:
                                subprocess.run(
                                    ["docker", "rm", "-f", container_name],
                                    capture_output=True,
                                    text=True,
                                    timeout=10
                                )
                            except Exception as cleanup_error:
                                logger.warning("failed_to_cleanup_stopped_container",
                                               job_id=str(job.id),
                                               container_id=container_name,
                                               error=str(cleanup_error))

                            elapsed_minutes = (datetime.utcnow() - job.started_at).total_seconds() / 60 if job.started_at else 0
                            failed_jobs.append({
                                "job_id": str(job.id),
                                "container_id": container_name,
                                "started_at": job.started_at.isoformat() if job.started_at else None,
                                "elapsed_minutes": elapsed_minutes,
                                "reason": "container_stopped"
                            })

                    except subprocess.TimeoutExpired:
                        logger.warning("container_check_timeout", job_id=str(job.id), container_id=container_name)
                    except Exception as e:
                        logger.error("container_check_failed", job_id=str(job.id), container_id=container_name, error=str(e))

            if failed_jobs:
                logger.info("container_job_mismatches_resolved", count=len(failed_jobs))

            return failed_jobs

        except Exception as e:
            logger.error("container_job_mismatch_check_failed", error=str(e))
            return []
        finally:
            if not db_session:
                db.close()

    @staticmethod
    def check_for_stuck_jobs(db_session=None, timeout_minutes: int = 420) -> List[dict]:
        """
        Check for jobs that have been processing too long and mark them as failed.

        Args:
            db_session: Optional database session (will create one if not provided)
            timeout_minutes: Minutes after which a job is considered stuck (default 7 hours for desktop)

        Returns:
            List of jobs that were marked as failed
        """
        from sqlalchemy.orm import Session
        from backend.core.database import SessionLocal
        from backend.models.job import Job, JobStatus
        from backend.services import JobService

        db = db_session or SessionLocal()
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)

            # Find jobs that are processing but started too long ago
            stuck_jobs = db.query(Job).filter(
                Job.status == JobStatus.RUNNING,
                Job.started_at < cutoff_time
            ).all()

            failed_jobs = []
            for job in stuck_jobs:
                elapsed_minutes = (datetime.utcnow() - job.started_at).total_seconds() / 60
                logger.warning(
                    "stuck_job_detected",
                    job_id=str(job.id),
                    started_at=job.started_at.isoformat(),
                    elapsed_minutes=round(elapsed_minutes, 1)
                )

                # Mark as failed
                error_message = f"Job processing timeout after {timeout_minutes} minutes ({elapsed_minutes:.1f} minutes elapsed)"
                JobService.fail_job(db, job.id, error_message)
                failed_jobs.append({
                    "job_id": str(job.id),
                    "started_at": job.started_at.isoformat(),
                    "elapsed_minutes": elapsed_minutes
                })

            if failed_jobs:
                logger.info("stuck_jobs_cleaned_up", count=len(failed_jobs))

            return failed_jobs

        finally:
            if not db_session:
                db.close()

    @staticmethod
    def cleanup_old_jobs(db_session=None, retention_days: int = 90) -> int:
        """
        Clean up old completed/failed jobs and their files (desktop mode - keep longer).

        Args:
            db_session: Optional database session
            retention_days: Days to keep jobs before cleanup (default 90 for desktop)

        Returns:
            Number of jobs cleaned up
        """
        from sqlalchemy.orm import Session
        from backend.core.database import SessionLocal
        from backend.models.job import Job, JobStatus
        from backend.services import StorageService

        db = db_session or SessionLocal()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

            # Find old jobs
            old_jobs = db.query(Job).filter(
                Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]),
                Job.created_at < cutoff_date
            ).all()

            storage_service = StorageService()
            cleaned_count = 0

            for job in old_jobs:
                try:
                    # Clean up files
                    if job.file_path and storage_service.delete_file(job.file_path):
                        logger.info("job_files_cleaned", job_id=str(job.id))

                    # Clean up result directory if it exists
                    if job.result_path:
                        import shutil
                        from pathlib import Path
                        result_dir = Path(job.result_path)
                        if result_dir.exists():
                            shutil.rmtree(result_dir, ignore_errors=True)
                            logger.info("job_result_dir_cleaned", job_id=str(job.id))

                    # Delete job record
                    db.delete(job)
                    cleaned_count += 1

                except Exception as e:
                    logger.warning("job_cleanup_failed", job_id=str(job.id), error=str(e))

            if cleaned_count > 0:
                db.commit()
                logger.info("old_jobs_cleaned_up", count=cleaned_count)

            return cleaned_count

        finally:
            if not db_session:
                db.close()

    @staticmethod
    def get_system_stats() -> dict:
        """Get system statistics for monitoring"""
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent if os.path.exists('/') else None,
                "process_count": len(psutil.pids()),
            }
        except ImportError:
            logger.warning("psutil_not_available_for_stats")
            return {
                "cpu_percent": None,
                "memory_percent": None,
                "disk_usage": None,
                "process_count": None,
            }

    @staticmethod
    def run_maintenance(db_session=None):
        """Run periodic maintenance tasks for desktop mode"""
        try:
            # Check for container-job mismatches (jobs running but containers stopped)
            container_mismatches = TaskManagementService.check_for_container_job_mismatches(db_session)

            # Check for stuck jobs (timeout after 5 hours for desktop)
            stuck_jobs = TaskManagementService.check_for_stuck_jobs(db_session, timeout_minutes=300)

            # Clean up old jobs (keep for 90 days in desktop mode)
            cleaned_count = TaskManagementService.cleanup_old_jobs(db_session, retention_days=90)

            # Clean up orphaned containers (containers without corresponding jobs)
            from backend.services.job_service import JobService
            orphaned_containers_cleaned = JobService.cleanup_orphaned_containers(db_session, logger)

            # Clean up stopped containers older than retention window
            stopped_containers_cleaned = JobService.cleanup_stopped_containers(logger, retention_days=5)

            # Log system stats
            stats = TaskManagementService.get_system_stats()
            logger.info("maintenance_completed",
                       container_mismatches=len(container_mismatches),
                       stuck_jobs=len(stuck_jobs),
                       cleaned_jobs=cleaned_count,
                       **stats)

            return {
                "container_mismatches": container_mismatches,
                "stuck_jobs": stuck_jobs,
                "cleaned_jobs": cleaned_count,
                "orphaned_containers_cleaned": orphaned_containers_cleaned,
                "stopped_containers_cleaned": stopped_containers_cleaned,
                "system_stats": stats
            }

        except Exception as e:
            logger.error("maintenance_failed", error=str(e))
            return {"error": str(e)}














