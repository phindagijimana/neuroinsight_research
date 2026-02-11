"""
Celery Tasks for Docker Job Execution

Each task runs inside a Celery worker process. This replaces the in-process
threading approach with a proper distributed task queue, enabling:
  - Multiple concurrent jobs across worker processes
  - Automatic retry on worker crash
  - Persistent status tracking via Redis + PostgreSQL
  - Job output upload to MinIO after completion
"""
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from celery import shared_task

logger = logging.getLogger(__name__)


def _sync_job_to_db(job_id: str, status: str, **kwargs) -> None:
    """Update job row in PostgreSQL.

    kwargs may include: started_at, completed_at, exit_code, error_message,
    backend_job_id, progress (int), current_phase (str).
    """
    try:
        from backend.core.database import get_db_context
        from backend.models.job import Job, JobStatusEnum

        with get_db_context() as db:
            job = db.query(Job).filter_by(id=job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found in database")
                return

            job.status = status

            if "started_at" in kwargs:
                job.started_at = kwargs["started_at"]
            if "completed_at" in kwargs:
                job.completed_at = kwargs["completed_at"]
            if "exit_code" in kwargs:
                job.exit_code = kwargs["exit_code"]
            if "error_message" in kwargs:
                job.error_message = kwargs["error_message"]
            if "backend_job_id" in kwargs:
                job.backend_job_id = kwargs["backend_job_id"]
            if "progress" in kwargs:
                job.progress = kwargs["progress"]
            if "current_phase" in kwargs:
                job.current_phase = kwargs["current_phase"]

            db.commit()
            logger.debug(f"Synced job {job_id[:8]} status={status}")
    except Exception as e:
        logger.error(f"Failed to sync job {job_id[:8]} to DB: {e}")


def _update_progress(job_id: str, progress: int, phase_label: str = "") -> None:
    """Lightweight DB update for progress tracking only (no status change)."""
    try:
        from backend.core.database import get_db_context
        from backend.models.job import Job

        with get_db_context() as db:
            job = db.query(Job).filter_by(id=job_id).first()
            if job:
                job.progress = progress
                if phase_label:
                    job.current_phase = phase_label
                db.commit()
    except Exception as e:
        logger.error(f"Failed to update progress for job {job_id[:8]}: {e}")


def _resolve_parameters(spec_dict: dict) -> dict:
    """Merge user-provided parameters with plugin YAML defaults."""
    resolved = dict(spec_dict.get("parameters", {}))
    plugin_id = spec_dict.get("plugin_id")
    input_files = spec_dict.get("input_files", [])

    # Try to get default parameters from plugin registry
    try:
        from backend.core.plugin_registry import get_plugin_workflow_registry
        registry = get_plugin_workflow_registry()
        plugin = registry.get_plugin(plugin_id) if plugin_id else None
        if plugin:
            for param_def in plugin.parameters:
                param_name = param_def.get("name", "") if isinstance(param_def, dict) else getattr(param_def, "name", "")
                param_default = param_def.get("default") if isinstance(param_def, dict) else getattr(param_def, "default", None)
                if param_name and param_name not in resolved and param_default is not None:
                    resolved[param_name] = param_default
    except Exception as e:
        logger.debug(f"Could not load plugin defaults for {plugin_id}: {e}")

    # Auto-set input file path if not already provided
    if input_files and "input_file" not in resolved:
        resolved["input_file"] = input_files[0]

    return resolved


def _prepare_volumes(spec_dict: dict, output_dir: Path) -> dict:
    """Prepare Docker volume mappings with smart input-file renaming.

    Maps input files into /data/inputs/ inside the container and the full
    output directory to /data/outputs/. This matches the paths expected by
    plugin command templates (e.g. /data/inputs/T1w.nii.gz,
    /data/outputs/native/fastsurfer/). Also maps FreeSurfer license if available.
    """
    volumes = {}
    input_files = spec_dict.get("input_files", [])
    environment = spec_dict.get("environment", {})
    plugin_id = spec_dict.get("plugin_id")

    # Map each input file to /input/ in container
    input_staging = output_dir / "_inputs"
    input_staging.mkdir(parents=True, exist_ok=True)

    # Try to get expected input names from plugin
    expected_input_names = []
    try:
        from backend.core.plugin_registry import get_plugin_workflow_registry
        registry = get_plugin_workflow_registry()
        plugin = registry.get_plugin(plugin_id) if plugin_id else None
        if plugin:
            for inp in plugin.inputs_required:
                key = inp.get("key", "") if isinstance(inp, dict) else getattr(inp, "key", "")
                if key:
                    expected_input_names.append(key)
    except Exception:
        pass

    # Copy/symlink input files into staging area with expected names
    for i, input_file in enumerate(input_files):
        input_path = Path(input_file)
        if input_path.exists():
            # Use expected name if available, otherwise keep original
            if i < len(expected_input_names):
                # Keep file extension from original
                ext = "".join(input_path.suffixes)
                staged_name = f"{expected_input_names[i]}{ext}"
            else:
                staged_name = input_path.name
            staged_path = input_staging / staged_name
            if not staged_path.exists():
                import shutil
                shutil.copy2(str(input_path), str(staged_path))

    # Volume mounts - match paths expected by plugin command templates
    # Command templates use /data/inputs/ and /data/outputs/
    volumes[str(input_staging)] = {"bind": "/data/inputs", "mode": "ro"}
    volumes[str(output_dir)] = {"bind": "/data/outputs", "mode": "rw"}

    # FreeSurfer license
    try:
        from backend.core.config import get_settings
        settings = get_settings()
        license_path = settings.fs_license_resolved
        if license_path:
            volumes[license_path] = {"bind": "/license/license.txt", "mode": "ro"}
    except Exception:
        pass

    return volumes


@shared_task(
    bind=True,
    name="backend.execution.celery_tasks.pull_docker_image",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=30,
    retry_backoff_max=300,
    retry_jitter=True,
)
def pull_docker_image(self, image: str) -> dict:
    """Pre-pull a Docker image (can be triggered independently).

    Retries up to 3 times with exponential backoff for network failures.
    """
    import docker as _docker
    client = _docker.from_env()
    try:
        logger.info(f"Pulling Docker image: {image} (attempt {self.request.retries + 1})")
        client.images.pull(image)
        return {"status": "pulled", "image": image}
    except Exception as e:
        logger.error(f"Failed to pull image {image}: {e}")
        return {"status": "error", "image": image, "error": str(e)}


@shared_task(
    bind=True,
    name="backend.execution.celery_tasks.run_docker_job",
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 2},
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
)
def run_docker_job(self, job_id: str, spec_dict: dict) -> dict:
    """Execute a neuroimaging job inside a Docker container.

    This is the core Celery task. It:
      1. Resolves parameters (fills defaults from plugin YAML)
      2. Prepares smart volume mounts (renamed input files)
      3. Pulls the Docker image if missing
      4. Runs the container with the command_template
      5. Streams logs and updates progress via phase milestones
      6. Updates the DB with final status
      7. Uploads outputs to MinIO
      8. Runs bundle extraction (mgz -> nii.gz)

    Retry policy:
      - Up to 2 automatic retries for transient failures (Docker daemon
        unavailable, image pull timeout, OOM kill)
      - Exponential backoff: 60s -> ~120s -> ~240s (with jitter)
      - Non-retryable failures (bad parameters, missing input files) raise
        Reject to skip retries

    Args:
        job_id: Pre-generated UUID (DB row must already exist)
        spec_dict: Serialised JobSpec (JSON-safe dict)

    Returns:
        dict with status, exit_code, output_dir
    """
    import docker as _docker
    from docker.errors import ImageNotFound

    data_dir = Path(spec_dict.get("data_dir", "./data"))
    output_dir = data_dir / "outputs" / job_id

    # Create output directory structure
    for sub in ("native", "bundle/volumes", "bundle/metrics", "bundle/qc", "logs", "_inputs"):
        (output_dir / sub).mkdir(parents=True, exist_ok=True)

    # Save job spec for audit trail
    spec_file = output_dir / "job_spec.json"
    safe_params = {
        k: v for k, v in spec_dict.get("parameters", {}).items()
        if not str(k).startswith("_")
    }
    spec_file.write_text(json.dumps({
        "pipeline_name": spec_dict.get("pipeline_name"),
        "container_image": spec_dict.get("container_image"),
        "input_files": spec_dict.get("input_files"),
        "parameters": safe_params,
        "resources": spec_dict.get("resources"),
        "plugin_id": spec_dict.get("plugin_id"),
        "workflow_id": spec_dict.get("workflow_id"),
        "execution_mode": spec_dict.get("execution_mode"),
        "has_command_template": spec_dict.get("command_template") is not None,
    }, indent=2))

    now = datetime.utcnow()

    # Load phase milestones for progress tracking
    from backend.core.phase_milestones import get_milestones
    plugin_id = spec_dict.get("plugin_id", "")
    if not plugin_id:
        steps = spec_dict.get("parameters", {}).get("_workflow_steps", [])
        plugin_id = steps[0] if steps else ""
    milestones = get_milestones(plugin_id)

    # Mark job as running
    _sync_job_to_db(job_id, "running", started_at=now, progress=1, current_phase="Queued")
    self.update_state(state="RUNNING", meta={"started_at": now.isoformat(), "progress": 1})

    # ---- Non-retryable validation (raise Reject to skip retries) ----
    from celery.exceptions import Reject

    image = spec_dict.get("container_image", "")
    if not image:
        _sync_job_to_db(job_id, "failed", error_message="No container image specified")
        raise Reject("No container image specified -- cannot retry", requeue=False)

    input_files = spec_dict.get("input_files", [])
    for inp in input_files:
        if isinstance(inp, str) and not Path(inp).exists():
            msg = f"Input file not found: {inp}"
            _sync_job_to_db(job_id, "failed", error_message=msg)
            raise Reject(msg, requeue=False)

    container = None
    container_id = None
    exit_code = -1
    error_message = ""

    try:
        client = _docker.from_env()

        # Pull image if not present
        try:
            client.images.get(image)
            logger.info(f"Image already present: {image}")
        except ImageNotFound:
            logger.info(f"Pulling image: {image}")
            _sync_job_to_db(job_id, "running", progress=2, current_phase="Pulling Docker image")
            client.images.pull(image)

        # Resolve parameters and prepare volumes
        resolved_params = _resolve_parameters(spec_dict)
        volumes = _prepare_volumes(spec_dict, output_dir)

        # Build command
        command_template = spec_dict.get("command_template", "")
        if command_template:
            # Substitute parameters into command template
            command = command_template
            for key, value in resolved_params.items():
                command = command.replace(f"{{{key}}}", str(value))
                command = command.replace(f"${{{key}}}", str(value))
        else:
            command = None  # Use container's default CMD

        # Resource limits
        resources_spec = spec_dict.get("resources", {})
        mem_limit = f"{resources_spec.get('memory_gb', 8)}g"
        cpu_count = resources_spec.get("cpus", 4)
        gpu_requested = resources_spec.get("gpu", False)

        # Environment variables for container
        container_env = {
            "OMP_NUM_THREADS": str(cpu_count),
            "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": str(cpu_count),
        }

        # Device requests for GPU
        device_requests = []
        if gpu_requested:
            device_requests = [_docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])]

        # Run the container
        logger.info(f"Starting container for job {job_id[:8]}: image={image}")
        _sync_job_to_db(job_id, "running", progress=3, current_phase="Starting container")

        container = client.containers.run(
            image=image,
            command=command,
            volumes=volumes,
            environment=container_env,
            mem_limit=mem_limit,
            nano_cpus=int(cpu_count * 1e9),
            device_requests=device_requests if device_requests else None,
            detach=True,
            remove=False,
        )
        container_id = container.id
        _sync_job_to_db(job_id, "running", backend_job_id=container_id[:12])

        # Stream logs and update progress
        current_progress = 3
        log_buffer = ""
        log_file = output_dir / "logs" / "container.log"

        for log_chunk in container.logs(stream=True, follow=True):
            try:
                text = log_chunk.decode("utf-8", errors="replace")
            except AttributeError:
                text = str(log_chunk)

            log_buffer += text

            # Write to log file
            with open(log_file, "a") as f:
                f.write(text)

            # Check milestones
            for marker, pct, label in milestones:
                if pct > current_progress:
                    try:
                        if re.search(marker, log_buffer):
                            current_progress = pct
                            _update_progress(job_id, pct, label)
                            self.update_state(
                                state="RUNNING",
                                meta={"progress": pct, "current_phase": label},
                            )
                            break  # Only advance one milestone at a time
                    except re.error:
                        # Treat as substring match if regex fails
                        if marker in log_buffer:
                            current_progress = pct
                            _update_progress(job_id, pct, label)
                            self.update_state(
                                state="RUNNING",
                                meta={"progress": pct, "current_phase": label},
                            )
                            break

        # Wait for container to finish
        result = container.wait()
        exit_code = result.get("StatusCode", -1)

        # Capture final logs
        try:
            final_logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            stdout_file = output_dir / "logs" / "stdout.log"
            stderr_file = output_dir / "logs" / "stderr.log"
            stdout_file.write_text(final_logs)
            # Try to get stderr separately
            try:
                stderr_logs = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
                stderr_file.write_text(stderr_logs)
            except Exception:
                stderr_file.write_text("")
        except Exception as e:
            logger.warning(f"Failed to capture final logs: {e}")

        if exit_code == 0:
            logger.info(f"Job {job_id[:8]} completed successfully")
            _sync_job_to_db(
                job_id, "completed",
                completed_at=datetime.utcnow(),
                exit_code=0,
                progress=100,
                current_phase="Completed",
            )

            # Upload outputs to MinIO
            try:
                _upload_outputs_to_minio(job_id, output_dir)
            except Exception as e:
                logger.warning(f"MinIO upload failed for {job_id[:8]}: {e}")

            # Extract bundle (mgz -> nii.gz)
            try:
                _extract_bundle(job_id, spec_dict, output_dir, client)
            except Exception as e:
                logger.warning(f"Bundle extraction failed for {job_id[:8]}: {e}")

            return {"status": "completed", "exit_code": 0, "output_dir": str(output_dir)}
        else:
            error_message = f"Container exited with code {exit_code}"
            logger.error(f"Job {job_id[:8]} failed: {error_message}")
            _sync_job_to_db(
                job_id, "failed",
                completed_at=datetime.utcnow(),
                exit_code=exit_code,
                error_message=error_message,
            )
            return {"status": "failed", "exit_code": exit_code, "output_dir": str(output_dir)}

    except Exception as e:
        error_message = str(e)
        retry_num = self.request.retries
        max_retries = self.max_retries or 2
        logger.error(
            f"Job {job_id[:8]} exception (attempt {retry_num + 1}/{max_retries + 1}): {error_message}"
        )
        if retry_num >= max_retries:
            # Final attempt failed -- mark as permanently failed
            _sync_job_to_db(
                job_id, "failed",
                completed_at=datetime.utcnow(),
                exit_code=-1,
                error_message=f"Failed after {retry_num + 1} attempts: {error_message}",
            )
        else:
            # Will be retried -- mark as retrying
            _sync_job_to_db(
                job_id, "running",
                current_phase=f"Retrying (attempt {retry_num + 2}/{max_retries + 1})",
                error_message=f"Retry {retry_num + 1}: {error_message}",
            )
        # Let autoretry_for handle the re-raise
        return {"status": "failed", "exit_code": -1, "error": error_message}

    finally:
        # Clean up container
        if container:
            try:
                container.remove(force=True)
            except Exception:
                pass


def _upload_outputs_to_minio(job_id: str, output_dir: Path) -> None:
    """Upload all job output files to MinIO."""
    try:
        from backend.core.storage import storage
        count = storage.upload_output_dir(job_id, str(output_dir / "native"), prefix="native")
        bundle_dir = output_dir / "bundle"
        if bundle_dir.exists():
            count += storage.upload_output_dir(job_id, str(bundle_dir), prefix="bundle")
        logger.info(f"Uploaded {count} output files to MinIO for job {job_id[:8]}")
    except Exception as e:
        logger.warning(f"Failed to upload outputs to MinIO for job {job_id[:8]}: {e}")


def _extract_bundle(job_id: str, spec_dict: dict, output_dir: Path, docker_client=None) -> None:
    """Run bundle extraction (mgz -> nii.gz conversions) in the same container image.

    Converts FreeSurfer .mgz files to NIfTI .nii.gz for the viewer.
    """
    native_dir = output_dir / "native"
    bundle_dir = output_dir / "bundle" / "volumes"

    # Find .mgz files in native output
    mgz_files = list(native_dir.rglob("*.mgz"))
    if not mgz_files:
        logger.debug(f"No .mgz files found for job {job_id[:8]}, skipping bundle extraction")
        return

    if docker_client is None:
        import docker as _docker
        docker_client = _docker.from_env()

    image = spec_dict.get("container_image", "")
    bundle_dir.mkdir(parents=True, exist_ok=True)

    for mgz_file in mgz_files:
        nii_name = mgz_file.stem + ".nii.gz"
        nii_path = bundle_dir / nii_name
        if nii_path.exists():
            continue

        try:
            # Use mri_convert from the same container
            rel_path = mgz_file.relative_to(native_dir)
            docker_client.containers.run(
                image=image,
                command=f"mri_convert /input/{rel_path} /output/{nii_name}",
                volumes={
                    str(native_dir): {"bind": "/input", "mode": "ro"},
                    str(bundle_dir): {"bind": "/output", "mode": "rw"},
                },
                remove=True,
            )
            logger.debug(f"Converted {mgz_file.name} -> {nii_name}")
        except Exception as e:
            logger.warning(f"Failed to convert {mgz_file.name}: {e}")
