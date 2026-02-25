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

from backend.core.celery_app import celery_app  # noqa: F401 — ensure app is loaded before shared_task binds

# ---------------------------------------------------------------------------
# Periodic: stale-job reaper
# ---------------------------------------------------------------------------
celery_app.conf.beat_schedule = {
    "reap-stale-jobs": {
        "task": "backend.execution.celery_tasks.reap_stale_jobs_task",
        "schedule": 120.0,  # every 2 minutes
    },
}

logger = logging.getLogger(__name__)

# Allowed Docker image prefixes for neuroimaging plugins
ALLOWED_IMAGE_PREFIXES = (
    "freesurfer/freesurfer",
    "deepmi/fastsurfer",
    "nipreps/fmriprep",
    "pennlinc/xcp_d",
    "pennbbl/qsiprep",
    "pennbbl/qsirecon",
    "pennlinc/qsirecon",
    "nipy/heudiconv",
    "meldproject/meld_graph",
    "nipreps/mriqc",
    "neuroinsight/",
    "bids/",
)


def _sanitize_param(value: str) -> str:
    """Sanitize a parameter value for safe inclusion in shell commands.

    Removes shell metacharacters that could enable command injection.
    Only allows alphanumeric, path-safe, and common flag characters.
    """
    # Block the most dangerous shell metacharacters
    dangerous = set(";|&`$(){}!><\n\r")
    sanitized = "".join(c for c in value if c not in dangerous)
    return sanitized


def _validate_image(image: str) -> bool:
    """Check if a Docker image is in the allow list.

    Returns True if the image is allowed, False otherwise.
    """
    # Strip tag/digest for prefix matching
    image_base = image.split(":")[0].split("@")[0]
    return any(image_base.startswith(prefix) for prefix in ALLOWED_IMAGE_PREFIXES)


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
            # Also pull defaults from optional inputs (used by utility plugins)
            for inp_def in plugin.inputs_optional:
                inp_key = inp_def.get("key", "") if isinstance(inp_def, dict) else getattr(inp_def, "key", "")
                inp_default = inp_def.get("default") if isinstance(inp_def, dict) else getattr(inp_def, "default", None)
                if inp_key and inp_key not in resolved and inp_default is not None:
                    resolved[inp_key] = inp_default
    except Exception as e:
        logger.debug(f"Could not load plugin defaults for {plugin_id}: {e}")

    # Auto-set input file path if not already provided
    if input_files and "input_file" not in resolved:
        resolved["input_file"] = input_files[0]

    # Inject resource variables so command templates can use {threads}, {mem_gb}, etc.
    resources = spec_dict.get("resources", {})
    cpus = resources.get("cpus", 4)
    mem_gb = resources.get("memory_gb", 8)
    resource_vars = {
        "threads": str(cpus),
        "nthreads": str(cpus),
        "omp_nthreads": str(max(1, cpus - 1)),  # reserve 1 core for orchestration
        "mem_gb": str(mem_gb),
        "mem_mb": str(mem_gb * 1024),
        "cpus": str(cpus),
    }
    for key, value in resource_vars.items():
        if key not in resolved:
            resolved[key] = value

    return resolved


def _prepare_volumes(spec_dict: dict, output_dir: Path) -> dict:
    """Prepare Docker volume mappings with smart input-file renaming.

    Maps input files into /data/inputs/ inside the container and the full
    output directory to /data/outputs/. This matches the paths expected by
    plugin command templates (e.g. /data/inputs/T1w.nii.gz,
    /data/outputs/native/fastsurfer/). Also maps FreeSurfer license if available.

    Handles both files (copied into a staging dir) and directories (mounted
    directly as separate volumes) so that multi-step workflows can pass
    SUBJECTS_DIR or similar directory outputs between steps.
    """
    import shutil

    volumes = {}
    input_files = spec_dict.get("input_files", [])
    environment = spec_dict.get("environment", {})
    plugin_id = spec_dict.get("plugin_id")

    input_staging = output_dir / "_inputs"
    input_staging.mkdir(parents=True, exist_ok=True)

    # Collect expected input names (file/path types only, skip string params)
    expected_input_names: list[str] = []
    try:
        from backend.core.plugin_registry import get_plugin_workflow_registry
        registry = get_plugin_workflow_registry()
        plugin = registry.get_plugin(plugin_id) if plugin_id else None
        if plugin:
            for inp in plugin.inputs_required:
                if isinstance(inp, dict):
                    key, inp_type = inp.get("key", ""), inp.get("type", "")
                else:
                    key, inp_type = getattr(inp, "key", ""), getattr(inp, "type", "")
                if key and inp_type not in ("string", "int", "float", "bool"):
                    expected_input_names.append(key)
    except Exception as e:
        logger.debug("Could not resolve expected input names for %s: %s", plugin_id, e)

    # --- Name-based matching (preferred over fragile positional mapping) ---
    matched: dict[int, str] = {}
    unmatched_indices = list(range(len(input_files)))

    def _stem_lower(p: Path) -> str:
        name = p.name.lower()
        return name[:-7] if name.endswith(".nii.gz") else p.stem.lower()

    for expected_name in expected_input_names:
        en_lower = expected_name.lower()
        for idx in list(unmatched_indices):
            stem = _stem_lower(Path(input_files[idx]))
            if en_lower in stem:
                matched[idx] = expected_name
                unmatched_indices.remove(idx)
                break

    # Positional fallback for any remaining expected names
    remaining_names = [n for n in expected_input_names if n not in matched.values()]
    for idx in list(unmatched_indices):
        if remaining_names:
            matched[idx] = remaining_names.pop(0)
            unmatched_indices.remove(idx)

    # --- Stage files / mount directories ---
    has_dir_mounts = False
    for i, input_file in enumerate(input_files):
        input_path = Path(input_file)
        if not input_path.exists():
            continue

        container_name = matched.get(i, input_path.name)

        if input_path.is_dir():
            # Directories are mounted directly (avoids expensive copies of
            # large trees like SUBJECTS_DIR and works with rw access).
            # Docker requires absolute paths for bind mounts.
            has_dir_mounts = True
            volumes[str(input_path.resolve())] = {
                "bind": f"/data/inputs/{container_name}", "mode": "rw",
            }
        else:
            ext = "".join(input_path.suffixes)
            staged_name = f"{container_name}{ext}"
            staged_path = input_staging / staged_name
            if not staged_path.exists():
                shutil.copy2(str(input_path), str(staged_path))

    # When directory mounts overlay /data/inputs/, Docker needs the base
    # mount to be rw so it can create the sub-mountpoints on the overlay FS.
    staging_mode = "rw" if has_dir_mounts else "ro"
    volumes[str(input_staging)] = {"bind": "/data/inputs", "mode": staging_mode}
    volumes[str(output_dir)] = {"bind": "/data/outputs", "mode": "rw"}

    # FreeSurfer license -- mount at every path that tools may expect
    try:
        from backend.core.config import get_settings
        settings = get_settings()
        license_path = settings.fs_license_resolved
        if license_path:
            volumes[license_path] = {"bind": "/opt/freesurfer/license.txt", "mode": "ro"}
        # MELD Graph license
        meld_license_path = settings.meld_license_resolved
        if meld_license_path:
            volumes[meld_license_path] = {"bind": "/run/secrets/meld_license.txt", "mode": "ro"}
    except Exception as e:
        logger.warning("Could not resolve license paths: %s", e)

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

    data_dir = Path(spec_dict.get("data_dir", "./data")).resolve()
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

    if not _validate_image(image):
        msg = f"Image '{image}' is not in the allowed list. Contact admin to add it."
        _sync_job_to_db(job_id, "failed", error_message=msg)
        raise Reject(msg, requeue=False)

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
        if not command_template:
            # Try to look up from plugin registry as fallback
            plugin_id = spec_dict.get("plugin_id")
            if plugin_id:
                try:
                    from backend.core.plugin_registry import get_plugin_workflow_registry
                    reg = get_plugin_workflow_registry()
                    plugin = reg.get_plugin(plugin_id)
                    if plugin:
                        command_template = plugin.command_template or plugin.command or ""
                except Exception as e:
                    logger.warning(f"Could not look up command_template for {plugin_id}: {e}")

        if command_template:
            # Substitute parameters into command template with shell-safe escaping
            command = command_template
            for key, value in resolved_params.items():
                safe_value = _sanitize_param(str(value))
                command = command.replace(f"{{{key}}}", safe_value)
                command = command.replace(f"${{{key}}}", safe_value)
        elif spec_dict.get("execution_mode") == "plugin":
            # Plugin jobs require a command template -- fail fast
            plugin_id = spec_dict.get("plugin_id", "unknown")
            msg = f"Plugin '{plugin_id}' has no command_template -- cannot execute"
            _sync_job_to_db(job_id, "failed", error_message=msg)
            raise Reject(msg, requeue=False)
        else:
            command = None  # Use container's default CMD (legacy jobs only)

        # Resource limits
        resources_spec = spec_dict.get("resources", {})
        mem_limit = f"{resources_spec.get('memory_gb', 8)}g"
        cpu_count = resources_spec.get("cpus", 4)
        gpu_requested = resources_spec.get("gpu", False)

        # Environment variables for container
        container_env = {
            "OMP_NUM_THREADS": str(cpu_count),
            "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": str(cpu_count),
            "PYTHONNOUSERSITE": "1",
        }

        if any(v.get("bind") == "/opt/freesurfer/license.txt" for v in volumes.values()):
            container_env["FS_LICENSE"] = "/opt/freesurfer/license.txt"
        if any(v.get("bind") == "/run/secrets/meld_license.txt" for v in volumes.values()):
            container_env["MELD_LICENSE"] = "/run/secrets/meld_license.txt"

        # MELD Graph needs a persistent data volume for params/models
        # (~450 MB, downloaded on first run).
        is_meld = "meld_graph" in image or "meld_graph" in (parameters.get("_plugin_id", ""))
        meld_data_dir = Path(settings.data_dir) / "meld_data"
        if is_meld and meld_data_dir.exists():
            volumes[str(meld_data_dir / "meld_params")] = {
                "bind": "/data/meld_params", "mode": "ro",
            }
            volumes[str(meld_data_dir / "models")] = {
                "bind": "/data/models", "mode": "ro",
            }
            logger.info("Mounted cached MELD data from %s", meld_data_dir)

        # Device requests for GPU
        device_requests = []
        if gpu_requested:
            device_requests = [_docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])]

        # Wrap multi-line / shebang commands so Docker uses bash.
        # Override the image's ENTRYPOINT so our bash wrapper isn't passed
        # to it as positional arguments (e.g. QSIPrep/QSIRecon entrypoints).
        docker_command = command
        override_entrypoint = None
        if command and ("\n" in command or command.strip().startswith("#!")):
            docker_command = ["/bin/bash", "-c", command]
            override_entrypoint = ""

        # Run the container
        logger.info(f"Starting container for job {job_id[:8]}: image={image}")
        _sync_job_to_db(job_id, "running", progress=3, current_phase="Starting container")

        run_kwargs = dict(
            image=image,
            command=docker_command,
            volumes=volumes,
            environment=container_env,
            mem_limit=mem_limit,
            nano_cpus=int(cpu_count * 1e9),
            device_requests=device_requests if device_requests else None,
            detach=True,
            remove=False,
            user="root",
            security_opt=["no-new-privileges"],
            network_mode="none",
            labels={"neuroinsight.job_id": job_id, "managed-by": "neuroinsight"},
        )
        if is_meld:
            run_kwargs["working_dir"] = "/app"
        if override_entrypoint is not None:
            run_kwargs["entrypoint"] = override_entrypoint

        container = client.containers.run(**run_kwargs)
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
            except Exception as e2:
                logger.debug("Could not capture stderr for %s: %s", job_id[:8], e2)
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

            # Generate stats CSVs
            try:
                _generate_stats_csvs(job_id, spec_dict.get("pipeline_name", ""), output_dir)
            except Exception as e:
                logger.warning(f"Stats CSV generation failed for {job_id[:8]}: {e}")

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
            except Exception as e:
                logger.debug("Could not remove container for %s: %s", job_id[:8], e)


def _run_single_container(
    job_id: str,
    image: str,
    command: Optional[str],
    volumes: dict,
    resources_spec: dict,
    output_dir: Path,
    step_label: str = "",
    milestones: list = None,
    progress_base: int = 0,
    progress_range: int = 90,
    update_fn=None,
) -> int:
    """Run a single Docker container and stream its logs.

    Returns the container exit code. Shared between single-plugin and
    multi-step workflow execution.
    """
    import docker as _docker

    from backend.core.config import get_settings
    settings = get_settings()

    client = _docker.from_env()
    from docker.errors import ImageNotFound

    # Pull image if missing
    try:
        client.images.get(image)
    except ImageNotFound:
        logger.info(f"Pulling image: {image}")
        if update_fn:
            update_fn(progress_base + 1, f"Pulling {step_label or image}")
        client.images.pull(image)

    mem_limit = f"{resources_spec.get('memory_gb', 8)}g"
    cpu_count = resources_spec.get("cpus", 4)
    gpu_requested = resources_spec.get("gpu", False)

    container_env = {
        "OMP_NUM_THREADS": str(cpu_count),
        "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": str(cpu_count),
        "PYTHONNOUSERSITE": "1",
    }

    if any(v.get("bind") == "/opt/freesurfer/license.txt" for v in volumes.values()):
        container_env["FS_LICENSE"] = "/opt/freesurfer/license.txt"
    if any(v.get("bind") == "/run/secrets/meld_license.txt" for v in volumes.values()):
        container_env["MELD_LICENSE"] = "/run/secrets/meld_license.txt"

    is_meld = "meld_graph" in image
    meld_data_dir = Path(settings.data_dir) / "meld_data"
    if is_meld and meld_data_dir.exists():
        if (meld_data_dir / "meld_params").is_dir():
            volumes[str(meld_data_dir / "meld_params")] = {
                "bind": "/data/meld_params", "mode": "ro",
            }
        if (meld_data_dir / "models").is_dir():
            volumes[str(meld_data_dir / "models")] = {
                "bind": "/data/models", "mode": "ro",
            }
        logger.info("Mounted cached MELD data from %s", meld_data_dir)

    device_requests = []
    if gpu_requested:
        device_requests = [_docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])]

    label = step_label or image.split("/")[-1].split(":")[0]
    logger.info(f"Starting container [{label}] for job {job_id[:8]}: image={image}")
    if update_fn:
        update_fn(progress_base + 2, f"Running {label}")

    # Wrap multi-line bash scripts so Docker exec-form doesn't shlex-split them.
    # Override the image's ENTRYPOINT so our bash wrapper isn't passed to it
    # as positional arguments (e.g. QSIPrep has ENTRYPOINT ["/usr/.../qsiprep"]).
    docker_command = command
    override_entrypoint = None
    if command and ("\n" in command or command.strip().startswith("#!")):
        docker_command = ["/bin/bash", "-c", command]
        override_entrypoint = ""

    run_kwargs = dict(
        image=image,
        command=docker_command,
        volumes=volumes,
        environment=container_env,
        mem_limit=mem_limit,
        nano_cpus=int(cpu_count * 1e9),
        device_requests=device_requests if device_requests else None,
        detach=True,
        remove=False,
        user="root",
        security_opt=["no-new-privileges"],
        network_mode="none",
        labels={"neuroinsight.job_id": job_id, "managed-by": "neuroinsight"},
    )
    if is_meld:
        run_kwargs["working_dir"] = "/app"
    if override_entrypoint is not None:
        run_kwargs["entrypoint"] = override_entrypoint

    container = client.containers.run(**run_kwargs)

    try:
        current_progress = progress_base + 2
        log_buffer = ""
        log_file = output_dir / "logs" / f"{label}.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)

        for log_chunk in container.logs(stream=True, follow=True):
            try:
                text = log_chunk.decode("utf-8", errors="replace")
            except AttributeError:
                text = str(log_chunk)
            log_buffer += text
            with open(log_file, "a") as f:
                f.write(text)

            # Check milestones for progress
            if milestones:
                for marker, pct_raw, mlabel in milestones:
                    pct = progress_base + int(pct_raw * progress_range / 100)
                    if pct > current_progress:
                        try:
                            if re.search(marker, log_buffer):
                                current_progress = pct
                                if update_fn:
                                    update_fn(pct, f"{label}: {mlabel}")
                                break
                        except re.error:
                            if marker in log_buffer:
                                current_progress = pct
                                if update_fn:
                                    update_fn(pct, f"{label}: {mlabel}")
                                break

        result = container.wait()
        exit_code = result.get("StatusCode", -1)

        # Capture final logs
        try:
            final_logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
            (output_dir / "logs" / f"{label}_stdout.log").write_text(final_logs)
        except Exception as e:
            logger.debug("Could not capture logs for container %s: %s", label, e)

        return exit_code
    finally:
        try:
            container.remove(force=True)
        except Exception as e:
            logger.debug("Could not remove container %s: %s", label, e)


@shared_task(
    bind=True,
    name="backend.execution.celery_tasks.run_workflow_job",
    acks_late=True,
    reject_on_worker_lost=True,
    max_retries=0,
)
def run_workflow_job(self, job_id: str, spec_dict: dict) -> dict:
    """Execute a multi-step workflow by chaining plugin containers.

    Each step in the workflow runs its own Docker container. The output
    directory of step N becomes available as input to step N+1.

    Args:
        job_id: Pre-generated UUID
        spec_dict: Serialised JobSpec with _workflow_steps in parameters

    Returns:
        dict with status, exit_code, output_dir
    """
    from celery.exceptions import Reject

    data_dir = Path(spec_dict.get("data_dir", "./data")).resolve()
    output_dir = data_dir / "outputs" / job_id

    for sub in ("native", "bundle/volumes", "bundle/metrics", "bundle/qc", "logs", "_inputs"):
        (output_dir / sub).mkdir(parents=True, exist_ok=True)

    # Save job spec
    spec_file = output_dir / "job_spec.json"
    safe_params = {k: v for k, v in spec_dict.get("parameters", {}).items() if not str(k).startswith("_")}
    spec_file.write_text(json.dumps({
        "pipeline_name": spec_dict.get("pipeline_name"),
        "container_image": spec_dict.get("container_image"),
        "input_files": spec_dict.get("input_files"),
        "parameters": safe_params,
        "resources": spec_dict.get("resources"),
        "workflow_id": spec_dict.get("workflow_id"),
        "execution_mode": "workflow",
    }, indent=2))

    now = datetime.utcnow()
    _sync_job_to_db(job_id, "running", started_at=now, progress=1, current_phase="Preparing workflow")
    self.update_state(state="RUNNING", meta={"started_at": now.isoformat(), "progress": 1})

    # Get workflow steps (plugin IDs)
    workflow_steps = spec_dict.get("parameters", {}).get("_workflow_steps", [])
    if not workflow_steps:
        _sync_job_to_db(job_id, "failed", error_message="No workflow steps defined")
        raise Reject("No workflow steps defined", requeue=False)

    # Load plugin registry
    try:
        from backend.core.plugin_registry import get_plugin_workflow_registry
        registry = get_plugin_workflow_registry()
    except Exception as e:
        _sync_job_to_db(job_id, "failed", error_message=f"Failed to load plugin registry: {e}")
        raise Reject(str(e), requeue=False)

    # Validate all steps
    for step_id in workflow_steps:
        plugin = registry.get_plugin(step_id)
        if not plugin:
            msg = f"Workflow step references unknown plugin: {step_id}"
            _sync_job_to_db(job_id, "failed", error_message=msg)
            raise Reject(msg, requeue=False)
        if not _validate_image(plugin.container_image):
            msg = f"Image '{plugin.container_image}' not in allow list"
            _sync_job_to_db(job_id, "failed", error_message=msg)
            raise Reject(msg, requeue=False)

    # Validate initial inputs
    input_files = spec_dict.get("input_files", [])
    for inp in input_files:
        if isinstance(inp, str) and not Path(inp).exists():
            msg = f"Input file not found: {inp}"
            _sync_job_to_db(job_id, "failed", error_message=msg)
            raise Reject(msg, requeue=False)

    total_steps = len(workflow_steps)
    resources_spec = spec_dict.get("resources", {})

    def update_fn(progress: int, phase: str):
        _update_progress(job_id, progress, phase)
        self.update_state(state="RUNNING", meta={"progress": progress, "current_phase": phase})

    # Keep original user-supplied inputs so later steps can access files
    # that aren't produced by earlier steps (e.g. T2w scan for step 2).
    original_input_files = list(input_files)
    current_input_files = list(input_files)
    all_exit_codes = []

    for step_idx, step_plugin_id in enumerate(workflow_steps):
        plugin = registry.get_plugin(step_plugin_id)
        step_label = plugin.name or step_plugin_id

        # Progress range for this step
        progress_base = int((step_idx / total_steps) * 90)
        progress_range = int(90 / total_steps)

        update_fn(progress_base + 1, f"Step {step_idx + 1}/{total_steps}: {step_label}")
        logger.info(f"Workflow {job_id[:8]} step {step_idx + 1}/{total_steps}: {step_plugin_id}")

        # Build step spec by merging plugin defaults with workflow params
        step_spec = dict(spec_dict)
        step_spec["plugin_id"] = step_plugin_id
        step_spec["container_image"] = plugin.container_image
        step_spec["input_files"] = current_input_files

        # Get command template from plugin
        cmd_template = plugin.raw_yaml.get("execution", {}).get("command_template", "")
        if not cmd_template:
            cmd_template = plugin.command_template if hasattr(plugin, "command_template") else ""
        step_spec["command_template"] = cmd_template

        # Resolve parameters for this step
        resolved_params = _resolve_parameters(step_spec)

        # Prepare volumes
        volumes = _prepare_volumes(step_spec, output_dir)

        # Build command
        command = None
        if cmd_template:
            command = cmd_template
            for key, value in resolved_params.items():
                safe_value = _sanitize_param(str(value))
                command = command.replace(f"{{{key}}}", safe_value)
                command = command.replace(f"${{{key}}}", safe_value)

        # Load milestones for this plugin
        try:
            from backend.core.phase_milestones import get_milestones
            milestones = get_milestones(step_plugin_id)
        except Exception as e:
            logger.debug("Could not load milestones for %s: %s", step_plugin_id, e)
            milestones = []

        # Run the container
        try:
            exit_code = _run_single_container(
                job_id=job_id,
                image=plugin.container_image,
                command=command,
                volumes=volumes,
                resources_spec=resources_spec,
                output_dir=output_dir,
                step_label=step_plugin_id,
                milestones=milestones,
                progress_base=progress_base,
                progress_range=progress_range,
                update_fn=update_fn,
            )
        except Exception as e:
            msg = f"Step {step_idx + 1} ({step_plugin_id}) failed: {e}"
            logger.error(f"Workflow {job_id[:8]}: {msg}")
            _sync_job_to_db(job_id, "failed", completed_at=datetime.utcnow(), error_message=msg, exit_code=-1)
            return {"status": "failed", "exit_code": -1, "error": msg, "output_dir": str(output_dir)}

        all_exit_codes.append(exit_code)

        if exit_code != 0:
            msg = f"Step {step_idx + 1} ({step_plugin_id}) exited with code {exit_code}"
            logger.error(f"Workflow {job_id[:8]}: {msg}")
            _sync_job_to_db(
                job_id, "failed",
                completed_at=datetime.utcnow(),
                exit_code=exit_code,
                error_message=msg,
            )
            return {"status": "failed", "exit_code": exit_code, "error": msg, "output_dir": str(output_dir)}

        # Build inputs for the next step: step outputs first (highest
        # priority for name-matching), then original user files so that
        # scans like T2w remain accessible to later steps.
        native_dir = output_dir / "native"
        step_output_dirs = [str(d) for d in native_dir.iterdir() if d.is_dir()] if native_dir.exists() else []
        if step_output_dirs:
            current_input_files = step_output_dirs + original_input_files
        logger.info(f"Workflow {job_id[:8]} step {step_idx + 1} completed. Next inputs: {current_input_files}")

    # All steps completed successfully
    logger.info(f"Workflow {job_id[:8]} completed all {total_steps} steps successfully")
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
        logger.warning(f"MinIO upload failed for workflow {job_id[:8]}: {e}")

    # Extract bundle (mgz -> nii.gz)
    try:
        import docker as _docker
        docker_client = _docker.from_env()
        last_plugin = registry.get_plugin(workflow_steps[-1])
        _extract_bundle(job_id, {"container_image": last_plugin.container_image}, output_dir, docker_client)
    except Exception as e:
        logger.warning(f"Bundle extraction failed for workflow {job_id[:8]}: {e}")

    # Generate stats CSVs
    try:
        _generate_stats_csvs(job_id, spec_dict.get("pipeline_name", ""), output_dir)
    except Exception as e:
        logger.warning(f"Stats CSV generation failed for workflow {job_id[:8]}: {e}")

    return {"status": "completed", "exit_code": 0, "output_dir": str(output_dir)}


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


def _generate_stats_csvs(job_id: str, pipeline_name: str, output_dir: Path) -> None:
    """Generate structured CSV files from job statistics (post-processing step).

    Writes CSVs into output_dir/bundle/csv/ so they are available as
    permanent artifacts alongside the raw output.
    """
    from backend.services.stats_converter import FileProvider, generate_stats_csvs

    if not pipeline_name:
        logger.debug(f"No pipeline_name for job {job_id[:8]}, skipping CSV generation")
        return

    fp = FileProvider(local_dir=str(output_dir))
    sheets = generate_stats_csvs(pipeline_name, fp)

    if not sheets:
        logger.debug(f"No stats CSVs generated for job {job_id[:8]} ({pipeline_name})")
        return

    csv_dir = output_dir / "bundle" / "csv"
    csv_dir.mkdir(parents=True, exist_ok=True)

    for sheet in sheets:
        csv_path = csv_dir / sheet.filename
        csv_path.write_text(sheet.to_csv_string(), encoding="utf-8")
        logger.debug(f"Generated {sheet.filename} ({sheet.total_rows} rows) for job {job_id[:8]}")

    logger.info(f"Generated {len(sheets)} stats CSVs for job {job_id[:8]}")


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


# ---------------------------------------------------------------------------
# Periodic task: stale-job reaper
# ---------------------------------------------------------------------------

@shared_task(name="backend.execution.celery_tasks.reap_stale_jobs_task")
def reap_stale_jobs_task():
    """Periodic sweep for orphaned jobs whose containers exited unnoticed."""
    from backend.core.stale_job_reaper import reap_stale_jobs
    reaped = reap_stale_jobs()
    return {"reaped": len(reaped), "jobs": [r["job_id"][:8] for r in reaped]}
