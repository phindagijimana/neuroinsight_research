"""
Local Docker Backend

Executes neuroimaging pipeline jobs locally using Docker containers.
Mimics HPC behavior for development and testing.

Architecture:
    - Jobs are submitted via Celery tasks (async) or run in-thread (sync fallback)
    - Docker container lifecycle: create -> start -> monitor -> stop -> cleanup
    - Output stored in data_dir/outputs/<job_id>/
    - Progress tracked via container log parsing + phase milestones

Thread Safety:
    - Job tracking dict is protected by a threading lock
    - Each job runs in its own Celery task or thread
"""
import json
import logging
import os
import shutil
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.core.execution import (
    ExecutionBackend,
    ExecutionError,
    JobNotFoundError,
    BackendUnavailableError,
    JobStatus,
    JobSpec,
    JobInfo,
    JobLogs,
    ResourceSpec,
)

logger = logging.getLogger(__name__)


class LocalDockerBackend(ExecutionBackend):
    """Docker-based local execution backend.

    Runs neuroimaging containers on the local machine.
    Suitable for development, testing, and single-machine production.
    """

    def __init__(self, data_dir: str = "./data", max_concurrent_jobs: int = 2):
        """Initialize local Docker backend.

        Args:
            data_dir: Base directory for job data (inputs, outputs, logs)
            max_concurrent_jobs: Maximum number of concurrent Docker containers
        """
        self.data_dir = Path(data_dir)
        self.max_concurrent_jobs = max_concurrent_jobs
        self._jobs: Dict[str, dict] = {}  # job_id -> tracking info
        self._lock = threading.Lock()
        self._docker_client = None

        # Ensure directories exist
        (self.data_dir / "outputs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "uploads").mkdir(parents=True, exist_ok=True)

        logger.info(
            f"LocalDockerBackend initialized: data_dir={self.data_dir}, "
            f"max_concurrent={self.max_concurrent_jobs}"
        )

    @property
    def docker_client(self):
        """Lazy-initialize Docker client."""
        if self._docker_client is None:
            try:
                import docker
                self._docker_client = docker.from_env()
                self._docker_client.ping()
            except Exception as e:
                raise BackendUnavailableError(f"Docker is not available: {e}")
        return self._docker_client

    @property
    def backend_type(self) -> str:
        return "local"

    def submit_job(self, spec: JobSpec, job_id: Optional[str] = None) -> str:
        """Submit a job for execution via Celery or in-thread fallback.

        Args:
            spec: Job specification
            job_id: Optional pre-generated job ID

        Returns:
            Job ID string
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        # Create output directory
        output_dir = self.data_dir / "outputs" / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build spec dict for serialization
        spec_dict = {
            "pipeline_name": spec.pipeline_name,
            "container_image": spec.container_image,
            "input_files": spec.input_files,
            "output_dir": str(output_dir),
            "parameters": spec.parameters,
            "resources": {
                "memory_gb": spec.resources.memory_gb,
                "cpus": spec.resources.cpus,
                "time_hours": spec.resources.time_hours,
                "gpu": spec.resources.gpu,
            },
            "pipeline_version": spec.pipeline_version,
            "plugin_id": spec.plugin_id,
            "workflow_id": spec.workflow_id,
            "execution_mode": spec.execution_mode,
            "data_dir": str(self.data_dir),
        }

        # Get command template from plugin (extracted from execution.stages[0].command_template)
        try:
            from backend.core.plugin_registry import get_plugin_workflow_registry
            registry = get_plugin_workflow_registry()
            plugin = registry.get_plugin(spec.plugin_id) if spec.plugin_id else None
            if plugin:
                # Prefer command_template (from YAML execution.stages), fall back to command
                template = plugin.command_template or plugin.command
                if template:
                    spec_dict["command_template"] = template
        except Exception:
            pass

        # Track job locally
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": JobStatus.PENDING,
                "spec": spec_dict,
                "output_dir": str(output_dir),
                "submitted_at": datetime.utcnow(),
                "started_at": None,
                "completed_at": None,
                "container_id": None,
                "celery_task_id": None,
                "exit_code": None,
                "error_message": None,
                "progress": 0,
                "current_phase": "Queued",
            }

        # Create DB record
        try:
            from backend.core.database import get_db_context
            from backend.models.job import Job

            job_model = Job.from_spec(job_id, "local_docker", spec)
            with get_db_context() as db:
                db.add(job_model)
                db.commit()
                logger.info(f"Created DB record for job {job_id[:8]}")
        except Exception as e:
            logger.error(f"Failed to create DB record for job {job_id[:8]}: {e}")

        # Dispatch to Celery -- pick the right task for single-plugin vs workflow
        try:
            is_workflow = spec_dict.get("execution_mode") == "workflow"
            if is_workflow:
                from backend.execution.celery_tasks import run_workflow_job
                result = run_workflow_job.delay(job_id, spec_dict)
            else:
                from backend.execution.celery_tasks import run_docker_job
                result = run_docker_job.delay(job_id, spec_dict)
            with self._lock:
                self._jobs[job_id]["celery_task_id"] = result.id
            task_name = "run_workflow_job" if is_workflow else "run_docker_job"
            logger.info(f"Dispatched job {job_id[:8]} to Celery ({task_name}, task_id={result.id})")
        except Exception as e:
            logger.warning(f"Celery dispatch failed for job {job_id[:8]}: {e}. Running in-thread.")
            self._run_in_thread(job_id, spec_dict)

        return job_id

    def _run_in_thread(self, job_id: str, spec_dict: dict) -> None:
        """Fallback: run job in a background thread when Celery is unavailable."""

        def _execute():
            try:
                from backend.execution.celery_tasks import (
                    _sync_job_to_db,
                    _resolve_parameters,
                    _prepare_volumes,
                    _upload_outputs_to_minio,
                    _extract_bundle,
                )
                import docker as _docker
                from docker.errors import ImageNotFound

                client = _docker.from_env()
                output_dir = Path(spec_dict["output_dir"])

                for sub in ("native", "bundle/volumes", "bundle/metrics", "bundle/qc", "logs", "_inputs"):
                    (output_dir / sub).mkdir(parents=True, exist_ok=True)

                now = datetime.utcnow()
                with self._lock:
                    self._jobs[job_id]["status"] = JobStatus.RUNNING
                    self._jobs[job_id]["started_at"] = now

                _sync_job_to_db(job_id, "running", started_at=now, progress=1)

                image = spec_dict.get("container_image", "")

                # Pull if needed
                try:
                    client.images.get(image)
                except ImageNotFound:
                    _sync_job_to_db(job_id, "running", progress=2, current_phase="Pulling image")
                    client.images.pull(image)

                # Resolve and prepare
                resolved_params = _resolve_parameters(spec_dict)
                volumes = _prepare_volumes(spec_dict, output_dir)

                command_template = spec_dict.get("command_template", "")
                if command_template:
                    command = command_template
                    for key, value in resolved_params.items():
                        command = command.replace(f"{{{key}}}", str(value))
                        command = command.replace(f"${{{key}}}", str(value))
                else:
                    command = None

                resources_spec = spec_dict.get("resources", {})
                mem_limit = f"{resources_spec.get('memory_gb', 8)}g"
                cpu_count = resources_spec.get("cpus", 4)

                container_env = {
                    "OMP_NUM_THREADS": str(cpu_count),
                    "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": str(cpu_count),
                }

                container = client.containers.run(
                    image=image,
                    command=command,
                    volumes=volumes,
                    environment=container_env,
                    mem_limit=mem_limit,
                    nano_cpus=int(cpu_count * 1e9),
                    detach=True,
                    remove=False,
                )

                with self._lock:
                    self._jobs[job_id]["container_id"] = container.id[:12]

                _sync_job_to_db(job_id, "running", backend_job_id=container.id[:12])

                # Wait for completion
                result = container.wait()
                exit_code = result.get("StatusCode", -1)

                # Save logs
                try:
                    logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                    (output_dir / "logs" / "stdout.log").write_text(logs)
                except Exception:
                    pass

                completed_at = datetime.utcnow()
                with self._lock:
                    self._jobs[job_id]["completed_at"] = completed_at
                    self._jobs[job_id]["exit_code"] = exit_code

                if exit_code == 0:
                    with self._lock:
                        self._jobs[job_id]["status"] = JobStatus.COMPLETED
                    _sync_job_to_db(
                        job_id, "completed",
                        completed_at=completed_at,
                        exit_code=0,
                        progress=100,
                        current_phase="Completed",
                    )
                    try:
                        _upload_outputs_to_minio(job_id, output_dir)
                    except Exception:
                        pass
                    try:
                        _extract_bundle(job_id, spec_dict, output_dir, client)
                    except Exception:
                        pass
                else:
                    with self._lock:
                        self._jobs[job_id]["status"] = JobStatus.FAILED
                        self._jobs[job_id]["error_message"] = f"Exit code {exit_code}"
                    _sync_job_to_db(
                        job_id, "failed",
                        completed_at=completed_at,
                        exit_code=exit_code,
                        error_message=f"Container exited with code {exit_code}",
                    )

                # Remove container
                try:
                    container.remove(force=True)
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"In-thread execution failed for job {job_id[:8]}: {e}")
                with self._lock:
                    self._jobs[job_id]["status"] = JobStatus.FAILED
                    self._jobs[job_id]["error_message"] = str(e)
                try:
                    from backend.execution.celery_tasks import _sync_job_to_db
                    _sync_job_to_db(
                        job_id, "failed",
                        completed_at=datetime.utcnow(),
                        exit_code=-1,
                        error_message=str(e),
                    )
                except Exception:
                    pass

        thread = threading.Thread(target=_execute, name=f"job-{job_id[:8]}", daemon=True)
        thread.start()

    def get_job_status(self, job_id: str) -> JobStatus:
        """Query current job status."""
        # Check local cache first
        with self._lock:
            if job_id in self._jobs:
                return self._jobs[job_id]["status"]

        # Fall back to database
        try:
            from backend.core.database import get_db_context
            from backend.models.job import Job

            with get_db_context() as db:
                job = db.query(Job).filter_by(id=job_id).first()
                if job:
                    status_map = {
                        "pending": JobStatus.PENDING,
                        "running": JobStatus.RUNNING,
                        "completed": JobStatus.COMPLETED,
                        "failed": JobStatus.FAILED,
                        "cancelled": JobStatus.CANCELLED,
                    }
                    return status_map.get(job.status, JobStatus.UNKNOWN)
        except Exception:
            pass

        raise JobNotFoundError(f"Job {job_id} not found")

    def get_job_info(self, job_id: str) -> JobInfo:
        """Get detailed job information."""
        # Try database first for most current info
        try:
            from backend.core.database import get_db_context
            from backend.models.job import Job

            with get_db_context() as db:
                job = db.query(Job).filter_by(id=job_id).first()
                if job:
                    status_map = {
                        "pending": JobStatus.PENDING,
                        "running": JobStatus.RUNNING,
                        "completed": JobStatus.COMPLETED,
                        "failed": JobStatus.FAILED,
                        "cancelled": JobStatus.CANCELLED,
                    }
                    return JobInfo(
                        job_id=job.id,
                        status=status_map.get(job.status, JobStatus.UNKNOWN),
                        pipeline_name=job.pipeline_name or "",
                        container_image=job.container_image or "",
                        backend_job_id=job.backend_job_id,
                        progress=job.progress or 0,
                        current_phase=job.current_phase,
                        submitted_at=job.submitted_at,
                        started_at=job.started_at,
                        completed_at=job.completed_at,
                        exit_code=job.exit_code,
                        error_message=job.error_message,
                        output_dir=job.output_dir,
                    )
        except Exception:
            pass

        # Fall back to local cache
        with self._lock:
            if job_id in self._jobs:
                info = self._jobs[job_id]
                return JobInfo(
                    job_id=job_id,
                    status=info["status"],
                    pipeline_name=info.get("spec", {}).get("pipeline_name", ""),
                    container_image=info.get("spec", {}).get("container_image", ""),
                    backend_job_id=info.get("container_id"),
                    progress=info.get("progress", 0),
                    current_phase=info.get("current_phase"),
                    submitted_at=info.get("submitted_at"),
                    started_at=info.get("started_at"),
                    completed_at=info.get("completed_at"),
                    exit_code=info.get("exit_code"),
                    error_message=info.get("error_message"),
                    output_dir=info.get("output_dir"),
                )

        raise JobNotFoundError(f"Job {job_id} not found")

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or pending job by stopping its Docker container."""
        with self._lock:
            job_info = self._jobs.get(job_id)

        if not job_info:
            # Check DB
            try:
                from backend.core.database import get_db_context
                from backend.models.job import Job

                with get_db_context() as db:
                    job = db.query(Job).filter_by(id=job_id).first()
                    if not job:
                        raise JobNotFoundError(f"Job {job_id} not found")
                    if job.status in ("completed", "failed", "cancelled"):
                        return False
                    job.mark_cancelled()
                    db.commit()
                    return True
            except JobNotFoundError:
                raise
            except Exception as e:
                logger.error(f"Failed to cancel job {job_id[:8]}: {e}")
                return False

        # Try to stop Docker container
        container_id = job_info.get("container_id")
        if container_id:
            try:
                import docker
                client = docker.from_env()
                container = client.containers.get(container_id)
                container.stop(timeout=10)
                logger.info(f"Stopped container {container_id} for job {job_id[:8]}")
            except Exception as e:
                logger.warning(f"Failed to stop container for job {job_id[:8]}: {e}")

        # Try to revoke Celery task
        celery_task_id = job_info.get("celery_task_id")
        if celery_task_id:
            try:
                from backend.core.celery_app import celery_app
                celery_app.control.revoke(celery_task_id, terminate=True)
                logger.info(f"Revoked Celery task {celery_task_id} for job {job_id[:8]}")
            except Exception as e:
                logger.warning(f"Failed to revoke Celery task: {e}")

        # Update status
        with self._lock:
            self._jobs[job_id]["status"] = JobStatus.CANCELLED
            self._jobs[job_id]["completed_at"] = datetime.utcnow()

        try:
            from backend.execution.celery_tasks import _sync_job_to_db
            _sync_job_to_db(
                job_id, "cancelled",
                completed_at=datetime.utcnow(),
            )
        except Exception:
            pass

        return True

    def get_job_logs(self, job_id: str) -> JobLogs:
        """Retrieve job logs from Docker container or log files."""
        # Try log files first
        output_dir = self.data_dir / "outputs" / job_id / "logs"
        stdout = ""
        stderr = ""

        stdout_file = output_dir / "stdout.log"
        stderr_file = output_dir / "stderr.log"
        container_log = output_dir / "container.log"

        if stdout_file.exists():
            stdout = stdout_file.read_text()
        elif container_log.exists():
            stdout = container_log.read_text()

        if stderr_file.exists():
            stderr = stderr_file.read_text()

        # If no log files yet, try Docker container directly
        if not stdout:
            with self._lock:
                job_info = self._jobs.get(job_id)
            container_id = job_info.get("container_id") if job_info else None
            if container_id:
                try:
                    import docker
                    client = docker.from_env()
                    container = client.containers.get(container_id)
                    stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
                    stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
                except Exception:
                    pass

        if not stdout and not stderr:
            # Check if job exists at all
            with self._lock:
                if job_id not in self._jobs:
                    try:
                        from backend.core.database import get_db_context
                        from backend.models.job import Job
                        with get_db_context() as db:
                            if not db.query(Job).filter_by(id=job_id).first():
                                raise JobNotFoundError(f"Job {job_id} not found")
                    except JobNotFoundError:
                        raise

        return JobLogs(job_id=job_id, stdout=stdout, stderr=stderr)

    def list_jobs(self, status_filter: Optional[List[str]] = None, limit: int = 100) -> List[JobInfo]:
        """List jobs from database with optional filtering."""
        try:
            from backend.core.database import get_db_context
            from backend.models.job import Job

            with get_db_context() as db:
                query = db.query(Job).filter(Job.deleted == False)
                if status_filter:
                    query = query.filter(Job.status.in_(status_filter))
                query = query.order_by(Job.submitted_at.desc()).limit(limit)

                jobs = []
                status_map = {
                    "pending": JobStatus.PENDING,
                    "running": JobStatus.RUNNING,
                    "completed": JobStatus.COMPLETED,
                    "failed": JobStatus.FAILED,
                    "cancelled": JobStatus.CANCELLED,
                }
                for job in query.all():
                    jobs.append(JobInfo(
                        job_id=job.id,
                        status=status_map.get(job.status, JobStatus.UNKNOWN),
                        pipeline_name=job.pipeline_name or "",
                        container_image=job.container_image or "",
                        backend_job_id=job.backend_job_id,
                        progress=job.progress or 0,
                        current_phase=job.current_phase,
                        submitted_at=job.submitted_at,
                        started_at=job.started_at,
                        completed_at=job.completed_at,
                        exit_code=job.exit_code,
                        error_message=job.error_message,
                        output_dir=job.output_dir,
                    ))
                return jobs
        except Exception as e:
            logger.error(f"Failed to list jobs from DB: {e}")
            # Fall back to local cache
            with self._lock:
                results = []
                for job_id, info in list(self._jobs.items())[:limit]:
                    if status_filter and info["status"].value not in status_filter:
                        continue
                    results.append(JobInfo(
                        job_id=job_id,
                        status=info["status"],
                        pipeline_name=info.get("spec", {}).get("pipeline_name", ""),
                    ))
                return results

    def cleanup_job(self, job_id: str) -> bool:
        """Clean up job resources (container, temp files)."""
        cleaned = False

        # Remove from local tracking
        with self._lock:
            job_info = self._jobs.pop(job_id, None)

        # Stop and remove container if still running
        if job_info:
            container_id = job_info.get("container_id")
            if container_id:
                try:
                    import docker
                    client = docker.from_env()
                    container = client.containers.get(container_id)
                    container.stop(timeout=5)
                    container.remove(force=True)
                    cleaned = True
                except Exception:
                    pass

        # Remove output directory
        output_dir = self.data_dir / "outputs" / job_id
        if output_dir.exists():
            try:
                shutil.rmtree(str(output_dir))
                cleaned = True
                logger.info(f"Cleaned up output directory for job {job_id[:8]}")
            except Exception as e:
                logger.warning(f"Failed to clean up {output_dir}: {e}")

        # Soft-delete DB record
        try:
            from backend.core.database import get_db_context
            from backend.models.job import Job

            with get_db_context() as db:
                job = db.query(Job).filter_by(id=job_id).first()
                if job:
                    job.soft_delete()
                    db.commit()
                    cleaned = True
        except Exception:
            pass

        return cleaned

    def health_check(self) -> dict:
        """Check backend health and Docker availability."""
        try:
            import docker
            client = docker.from_env()
            info = client.info()

            # Count active containers
            active_containers = len(client.containers.list(
                filters={"label": "neuroinsight"}
            ))

            return {
                "healthy": True,
                "message": "Docker is available",
                "details": {
                    "backend_type": "local",
                    "docker_version": info.get("ServerVersion", "unknown"),
                    "containers_running": info.get("ContainersRunning", 0),
                    "active_job_containers": active_containers,
                    "max_concurrent_jobs": self.max_concurrent_jobs,
                    "data_dir": str(self.data_dir),
                    "images_cached": len(client.images.list()),
                },
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Docker is not available: {e}",
                "details": {
                    "backend_type": "local",
                    "error": str(e),
                },
            }
