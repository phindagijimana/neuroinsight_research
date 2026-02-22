"""
Stale Job Reaper

Detects and finalises orphaned jobs whose Docker containers have exited
but whose database records are still marked as "running" or "pending".

This happens when a Celery worker is killed while monitoring a container
(e.g. during a restart).  The container finishes independently, but no
process is left to write the final status back to the DB.

Usage:
    from backend.core.stale_job_reaper import reap_stale_jobs

    # One-shot sweep (called at startup or on a schedule)
    reaped = reap_stale_jobs()
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def reap_stale_jobs(
    stale_threshold_minutes: int = 5,
) -> List[Dict[str, Any]]:
    """Find jobs stuck in running/pending and reconcile with Docker.

    For each job marked running/pending in the DB:
      1. If it has a backend_job_id (container short-id), check if that
         container still exists and what its exit status is.
      2. If the container has exited, update the job to completed/failed.
      3. If no container can be found and the job has been "running" for
         longer than *stale_threshold_minutes*, mark it failed.

    Returns:
        List of dicts describing each reaped job.
    """
    try:
        import docker as _docker
    except ImportError:
        logger.warning("docker SDK not available; skipping stale-job reap")
        return []

    from backend.core.database import get_db_context
    from backend.models.job import Job

    reaped: List[Dict[str, Any]] = []
    now = datetime.utcnow()
    threshold = now - timedelta(minutes=stale_threshold_minutes)

    try:
        client = _docker.from_env()
    except Exception as e:
        logger.warning("Cannot connect to Docker daemon for stale-job reap: %s", e)
        return []

    with get_db_context() as db:
        stuck_jobs = (
            db.query(Job)
            .filter(Job.deleted == False)  # noqa: E712
            .filter(Job.status.in_(["running", "pending"]))
            .all()
        )

        if not stuck_jobs:
            return []

        logger.info("Stale-job reaper: checking %d running/pending jobs", len(stuck_jobs))

        all_containers = {}
        try:
            for c in client.containers.list(all=True, filters={"label": "managed-by=neuroinsight"}):
                short_id = c.id[:12]
                all_containers[short_id] = c
        except Exception as e:
            logger.warning("Could not list containers: %s", e)

        for job in stuck_jobs:
            container_id = job.backend_job_id
            reason = None
            exit_code = None

            if container_id and container_id in all_containers:
                container = all_containers[container_id]
                status = container.status  # "running", "exited", "created", etc.

                if status == "running":
                    continue

                exit_code = container.attrs.get("State", {}).get("ExitCode", -1)
                finished_at_str = container.attrs.get("State", {}).get("FinishedAt", "")

                if status == "exited":
                    reason = f"Container exited with code {exit_code} (orphaned)"

                    try:
                        logs = container.logs(tail=50).decode("utf-8", errors="replace")
                        from pathlib import Path
                        log_dir = Path(job.output_dir) / "logs"
                        log_dir.mkdir(parents=True, exist_ok=True)
                        (log_dir / "container_reaper.log").write_text(logs)
                    except Exception:
                        pass

                elif status in ("dead", "removing"):
                    reason = f"Container in terminal state: {status}"
                    exit_code = -1

                else:
                    continue

            elif container_id is None and job.started_at and job.started_at < threshold:
                reason = "No container ID recorded and job exceeded stale threshold"
                exit_code = -1

            elif container_id and container_id not in all_containers:
                if job.started_at and job.started_at < threshold:
                    reason = f"Container {container_id} no longer exists (removed or lost)"
                    exit_code = -1
                else:
                    continue

            else:
                continue

            if reason:
                final_status = "completed" if exit_code == 0 else "failed"
                job.status = final_status
                job.exit_code = exit_code
                job.error_message = reason
                job.completed_at = now

                db.commit()

                reaped.append({
                    "job_id": job.id,
                    "previous_status": "running",
                    "new_status": final_status,
                    "exit_code": exit_code,
                    "reason": reason,
                })
                logger.info(
                    "Reaped stale job %s: %s -> %s (%s)",
                    job.id[:8], "running", final_status, reason,
                )

    if reaped:
        logger.info("Stale-job reaper: finalised %d orphaned jobs", len(reaped))
    else:
        logger.debug("Stale-job reaper: no orphaned jobs found")

    return reaped
