"""
SLURM HPC Backend

Executes neuroimaging pipeline jobs on HPC clusters using SLURM scheduler
via SSH. Data and processing stay on the HPC -- only metadata travels.

Architecture:
    - SSH connection managed by SSHManager (paramiko)
    - sbatch scripts generated from plugin command templates
    - Job status polled via squeue / sacct
    - Logs retrieved via SFTP from SLURM output files
    - Singularity/Apptainer used for container execution on HPC
    - Progress tracked by parsing log files for phase milestones
"""
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path, PurePosixPath
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
from backend.core.ssh_manager import (
    SSHManager,
    SSHConnectionError,
    SSHCommandError,
    get_ssh_manager,
)

logger = logging.getLogger(__name__)


class SLURMBackend(ExecutionBackend):
    """SLURM HPC execution backend.
    
    Submits jobs to SLURM scheduler via SSH connection.
    Data and processing stay on HPC -- no local data transfer.
    """

    def __init__(
        self,
        ssh_host: str,
        ssh_user: str,
        work_dir: str = "~",
        partition: str = "general",
        account: Optional[str] = None,
        qos: Optional[str] = None,
        modules: Optional[List[str]] = None,
        container_runtime: str = "singularity",
        ssh_manager: Optional[SSHManager] = None,
    ):
        """Initialize SLURM backend.
        
        Args:
            ssh_host: HPC hostname
            ssh_user: SSH username
            work_dir: Working directory on HPC (defaults to ~ which resolves to $HOME)
            partition: Default SLURM partition
            account: SLURM account/allocation (optional)
            qos: SLURM QoS level (optional)
            modules: Environment modules to load before running jobs
            container_runtime: Container runtime on HPC ('singularity' or 'apptainer')
            ssh_manager: Existing SSH manager (None = use global singleton)
        """
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.work_dir = work_dir
        self._work_dir_resolved = False
        self.partition = partition
        self.account = account
        self.qos = qos
        self.modules = modules or []
        self.container_runtime = container_runtime

        # SSH connection
        self._ssh = ssh_manager or get_ssh_manager()

        # Local job tracking (supplementary to DB)
        self._jobs: Dict[str, dict] = {}

        logger.info(
            f"SLURMBackend initialized: {ssh_user}@{ssh_host}, "
            f"partition={partition}, work_dir={work_dir}"
        )

    def _resolve_work_dir(self) -> None:
        """Resolve ~, $HOME, or relative paths to an absolute path on the HPC.

        Runs once, caches the result. Falls back to the original value if
        resolution fails.
        """
        if self._work_dir_resolved:
            return
        self._work_dir_resolved = True

        raw = self.work_dir
        needs_resolve = (
            raw.startswith("~")
            or raw.startswith("$")
            or not raw.startswith("/")
        )
        if not needs_resolve:
            return

        try:
            self._ensure_ssh()
            exit_code, stdout, _ = self._ssh.execute(
                f'eval echo "{raw}"', timeout=10
            )
            resolved = stdout.strip()
            if exit_code == 0 and resolved and resolved.startswith("/"):
                logger.info("Resolved work_dir: %s -> %s", raw, resolved)
                self.work_dir = resolved
            else:
                # Try $HOME as fallback
                exit_code, stdout, _ = self._ssh.execute("echo $HOME", timeout=10)
                home = stdout.strip()
                if exit_code == 0 and home.startswith("/"):
                    self.work_dir = home
                    logger.info("Resolved work_dir to $HOME: %s", home)
        except Exception as e:
            logger.warning("Could not resolve work_dir '%s': %s", raw, e)

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _ensure_ssh(self) -> None:
        """Ensure SSH is configured and connected."""
        if not self._ssh.is_connected:
            self._ssh.configure(host=self.ssh_host, username=self.ssh_user)
            try:
                self._ssh.connect()
            except SSHConnectionError as e:
                raise BackendUnavailableError(f"Cannot connect to HPC: {e}")

    def _ssh_exec(self, command: str, check: bool = True, timeout: int = 60) -> str:
        """Execute command via SSH with auto-connect.

        Returns stdout on success. Raises on failure if check=True.
        """
        self._ensure_ssh()
        try:
            exit_code, stdout, stderr = self._ssh.execute(command, timeout=timeout)
            if check and exit_code != 0:
                raise ExecutionError(
                    f"Remote command failed (exit {exit_code}): {command}\n"
                    f"stderr: {stderr[:500]}"
                )
            return stdout
        except SSHConnectionError as e:
            raise BackendUnavailableError(f"SSH command failed: {e}")

    # ------------------------------------------------------------------
    # ExecutionBackend interface
    # ------------------------------------------------------------------

    @property
    def backend_type(self) -> str:
        return "slurm"

    def submit_job(self, spec: JobSpec, job_id: Optional[str] = None) -> str:
        """Submit a job to SLURM scheduler.

        Steps:
        1. Generate sbatch script from plugin command template
        2. Create working directory on HPC
        3. Upload sbatch script via SFTP
        4. Execute sbatch and parse SLURM job ID
        5. Track job in local state + database
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        self._ensure_ssh()
        self._resolve_work_dir()

        # Create remote working directory
        job_dir = str(PurePosixPath(self.work_dir) / "neuroinsight" / "jobs" / job_id)
        for sub in ("scripts", "logs", "inputs", "outputs/native", "outputs/bundle", "outputs/logs"):
            self._ssh_exec(f"mkdir -p {job_dir}/{sub}")

        # Symlink input files into the job inputs directory, renaming to match
        # the names expected by the command template (e.g. T1w.nii.gz).
        self._stage_inputs(spec, job_dir)

        # Get command template from plugin, or collect per-step info for workflows
        command_template = ""
        workflow_step_info: List[dict] = []
        try:
            from backend.core.plugin_registry import get_plugin_workflow_registry
            registry = get_plugin_workflow_registry()

            workflow_steps = spec.parameters.get("_workflow_steps", [])
            if workflow_steps:
                for step_plugin_id in workflow_steps:
                    step_plugin = registry.get_plugin(step_plugin_id)
                    if step_plugin:
                        tmpl = step_plugin.command_template or step_plugin.command or ""
                        if tmpl:
                            workflow_step_info.append({
                                "plugin_id": step_plugin_id,
                                "name": step_plugin.name or step_plugin_id,
                                "image": step_plugin.container_image,
                                "command_template": tmpl,
                            })
                if workflow_step_info:
                    logger.info(
                        "Workflow %s: %d steps with separate containers",
                        spec.pipeline_name, len(workflow_step_info),
                    )
            else:
                plugin = registry.get_plugin(spec.plugin_id) if spec.plugin_id else None
                if plugin:
                    command_template = plugin.command_template or plugin.command
        except Exception as e:
            logger.debug(f"Could not load plugin registry for command template: {e}")

        # Generate and upload sbatch script
        sbatch_script = self._generate_sbatch_script(
            spec, job_id, job_dir, command_template, workflow_step_info,
        )
        script_path = f"{job_dir}/scripts/run.sh"
        self._ssh.write_file(script_path, sbatch_script, mode=0o755)

        # Save job spec for audit trail
        spec_json = json.dumps({
            "job_id": job_id,
            "pipeline_name": spec.pipeline_name,
            "container_image": spec.container_image,
            "input_files": spec.input_files,
            "parameters": {k: v for k, v in spec.parameters.items() if not str(k).startswith("_")},
            "resources": {
                "memory_gb": spec.resources.memory_gb,
                "cpus": spec.resources.cpus,
                "time_hours": spec.resources.time_hours,
                "gpu": spec.resources.gpu,
            },
            "plugin_id": spec.plugin_id,
            "workflow_id": spec.workflow_id,
        }, indent=2)
        self._ssh.write_file(f"{job_dir}/scripts/job_spec.json", spec_json)

        # Upload stats_converter.py for post-container CSV generation
        try:
            converter_path = Path(__file__).parent.parent / "services" / "stats_converter.py"
            if converter_path.exists():
                self._ssh.write_file(
                    f"{job_dir}/scripts/stats_converter.py",
                    converter_path.read_text(encoding="utf-8"),
                )
                logger.debug("Uploaded stats_converter.py to HPC for job %s", job_id[:8])
        except Exception as e:
            logger.debug("Could not upload stats_converter.py: %s", e)

        # Submit via sbatch
        try:
            stdout = self._ssh_exec(f"sbatch {script_path}")
            slurm_job_id = self._parse_slurm_job_id(stdout)
            logger.info(f"Submitted job {job_id[:8]} -> SLURM {slurm_job_id}")
        except Exception as e:
            raise ExecutionError(f"sbatch submission failed: {e}")

        # Track locally (include spec metadata for get_job_info/progress lookup)
        now = datetime.utcnow()
        self._jobs[job_id] = {
            "job_id": job_id,
            "slurm_id": slurm_job_id,
            "status": JobStatus.PENDING,
            "job_dir": job_dir,
            "script_path": script_path,
            "submitted_at": now,
            "started_at": None,
            "completed_at": None,
            "exit_code": None,
            "error_message": None,
            "progress": 0,
            "current_phase": "Queued in SLURM",
            "spec": {
                "pipeline_name": spec.pipeline_name,
                "container_image": spec.container_image,
                "plugin_id": spec.plugin_id,
            },
        }

        # Create DB record
        try:
            from backend.core.database import get_db_context
            from backend.models.job import Job

            job_model = Job.from_spec(job_id, "slurm", spec)
            job_model.backend_job_id = slurm_job_id
            job_model.output_dir = f"{job_dir}/outputs"
            with get_db_context() as db:
                db.add(job_model)
                db.commit()
        except Exception as e:
            logger.error(f"Failed to create DB record for job {job_id[:8]}: {e}")

        return job_id

    def get_job_status(self, job_id: str) -> JobStatus:
        """Query SLURM job status via squeue/sacct."""
        slurm_id = self._get_slurm_id(job_id)
        if not slurm_id:
            raise JobNotFoundError(f"Job {job_id} not found")

        # Try squeue first (for running/pending jobs)
        try:
            stdout = self._ssh_exec(
                f"squeue -j {slurm_id} --noheader -o '%T' 2>/dev/null || true",
                check=False,
            )
            status_str = stdout.strip()
            if status_str:
                return self._parse_slurm_status(status_str)
        except Exception as e:
            logger.debug("squeue status query failed for %s: %s", slurm_id, e)

        # Fall back to sacct (for completed/failed jobs)
        try:
            stdout = self._ssh_exec(
                f"sacct -j {slurm_id} --noheader --format=State -P 2>/dev/null | head -1",
                check=False,
            )
            status_str = stdout.strip().split("+")[0]  # Handle "CANCELLED+" etc.
            if " " in status_str:
                status_str = status_str.split()[0]  # Handle "CANCELLED by UID"
            if status_str:
                return self._parse_slurm_status(status_str)
        except Exception as e:
            logger.debug(f"sacct status query failed for {slurm_id}: {e}")

        # Check local cache
        if job_id in self._jobs:
            return self._jobs[job_id]["status"]

        raise JobNotFoundError(f"Cannot determine status for job {job_id}")

    def get_job_info(self, job_id: str) -> JobInfo:
        """Get detailed SLURM job information from sacct."""
        slurm_id = self._get_slurm_id(job_id)
        if not slurm_id:
            raise JobNotFoundError(f"Job {job_id} not found")

        # Query sacct for detailed info
        info = self._query_sacct(slurm_id)
        local = self._jobs.get(job_id, {})

        status = info.get("status", local.get("status", JobStatus.UNKNOWN))

        # Parse progress from log file
        progress = local.get("progress", 0)
        current_phase = local.get("current_phase", "")
        if status == JobStatus.RUNNING:
            try:
                progress, current_phase = self._parse_progress(job_id)
            except Exception as e:
                logger.debug("Could not parse progress for job %s: %s", job_id[:8], e)

        return JobInfo(
            job_id=job_id,
            status=status,
            pipeline_name=local.get("spec", {}).get("pipeline_name", ""),
            container_image=local.get("spec", {}).get("container_image", ""),
            backend_job_id=slurm_id,
            progress=progress,
            current_phase=current_phase,
            submitted_at=local.get("submitted_at"),
            started_at=info.get("start_time") or local.get("started_at"),
            completed_at=info.get("end_time") or local.get("completed_at"),
            exit_code=info.get("exit_code") or local.get("exit_code"),
            error_message=local.get("error_message"),
            output_dir=local.get("job_dir", ""),
        )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a SLURM job via scancel."""
        slurm_id = self._get_slurm_id(job_id)
        if not slurm_id:
            raise JobNotFoundError(f"Job {job_id} not found")

        try:
            self._ssh_exec(f"scancel {slurm_id}")
            logger.info(f"Cancelled SLURM job {slurm_id} (job {job_id[:8]})")

            if job_id in self._jobs:
                self._jobs[job_id]["status"] = JobStatus.CANCELLED
                self._jobs[job_id]["completed_at"] = datetime.utcnow()

            # Update DB
            try:
                from backend.core.database import get_db_context
                from backend.models.job import Job

                with get_db_context() as db:
                    job = db.query(Job).filter_by(id=job_id).first()
                    if job:
                        job.mark_cancelled()
                        db.commit()
            except Exception as e:
                logger.warning(f"Failed to update DB after cancelling job {job_id[:8]}: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to cancel SLURM job {slurm_id}: {e}")
            return False

    def get_job_logs(self, job_id: str) -> JobLogs:
        """Retrieve job logs from HPC via SFTP."""
        local = self._jobs.get(job_id, {})
        job_dir = local.get("job_dir", "")
        slurm_id = local.get("slurm_id", "")
        stdout = ""
        stderr = ""

        if not job_dir:
            # Try to reconstruct from DB
            try:
                from backend.core.database import get_db_context
                from backend.models.job import Job
                with get_db_context() as db:
                    job = db.query(Job).filter_by(id=job_id).first()
                    if job and job.output_dir:
                        job_dir = str(PurePosixPath(job.output_dir).parent)
                        slurm_id = job.backend_job_id or ""
            except Exception as e:
                logger.debug(f"Could not reconstruct job_dir from DB for {job_id[:8]}: {e}")

        if not job_dir:
            raise JobNotFoundError(f"Job {job_id} not found or no job directory")

        self._ensure_ssh()

        # Read SLURM output file
        stdout_path = f"{job_dir}/logs/slurm-{slurm_id}.out"
        stderr_path = f"{job_dir}/logs/slurm-{slurm_id}.err"

        try:
            if self._ssh.file_exists(stdout_path):
                stdout = self._ssh.read_file(stdout_path)
        except Exception as e:
            logger.debug(f"Could not read stdout log: {e}")

        try:
            if self._ssh.file_exists(stderr_path):
                stderr = self._ssh.read_file(stderr_path)
        except Exception as e:
            logger.debug(f"Could not read stderr log: {e}")

        # Also try container log
        if not stdout:
            container_log = f"{job_dir}/outputs/logs/container.log"
            try:
                if self._ssh.file_exists(container_log):
                    stdout = self._ssh.read_file(container_log)
            except Exception as e:
                logger.debug(f"Could not read container log for job {job_id[:8]}: {e}")

        return JobLogs(job_id=job_id, stdout=stdout, stderr=stderr)

    def list_jobs(self, status_filter: Optional[List[str]] = None, limit: int = 100) -> List[JobInfo]:
        """List jobs from database with optional SLURM status refresh."""
        try:
            from backend.core.database import get_db_context
            from backend.models.job import Job

            with get_db_context() as db:
                query = db.query(Job).filter(
                    Job.deleted == False,
                    Job.backend_job_id.isnot(None),
                )
                if status_filter:
                    query = query.filter(Job.status.in_(status_filter))
                query = query.order_by(Job.submitted_at.desc()).limit(limit)

                jobs = []
                for job in query.all():
                    status = self._parse_slurm_status(job.status.upper()) if job.status else JobStatus.UNKNOWN
                    jobs.append(JobInfo(
                        job_id=job.id,
                        status=status,
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
            logger.error(f"Failed to list jobs: {e}")
            return []

    def cleanup_job(self, job_id: str) -> bool:
        """Clean up job files on HPC."""
        local = self._jobs.get(job_id, {})
        job_dir = local.get("job_dir", "")

        if not job_dir:
            return False

        try:
            self._ssh_exec(f"rm -rf {job_dir}")
            self._jobs.pop(job_id, None)

            # Soft-delete DB record
            try:
                from backend.core.database import get_db_context
                from backend.models.job import Job
                with get_db_context() as db:
                    job = db.query(Job).filter_by(id=job_id).first()
                    if job:
                        job.soft_delete()
                        db.commit()
            except Exception as e:
                logger.warning("Failed to soft-delete DB record for job %s: %s", job_id[:8], e)

            logger.info(f"Cleaned up HPC job directory: {job_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to clean up job {job_id[:8]}: {e}")
            return False

    def health_check(self) -> dict:
        """Check SSH connectivity and SLURM scheduler availability."""
        result = {
            "healthy": False,
            "message": "Unknown",
            "details": {
                "backend_type": "slurm",
                "host": self.ssh_host,
                "username": self.ssh_user,
                "partition": self.partition,
            },
        }

        # Check SSH
        try:
            self._ensure_ssh()
        except Exception as e:
            result["message"] = f"SSH connection failed: {e}"
            result["details"]["ssh_connected"] = False
            return result

        result["details"]["ssh_connected"] = True

        # Check SLURM availability
        try:
            version_out = self._ssh_exec("sinfo --version 2>/dev/null || echo 'not found'", check=False)
            if "not found" in version_out:
                result["message"] = "SLURM not available on remote host"
                result["details"]["slurm_available"] = False
                return result

            result["details"]["slurm_version"] = version_out.strip()
            result["details"]["slurm_available"] = True
        except Exception as e:
            result["message"] = f"Cannot check SLURM: {e}"
            return result

        # Check partition exists
        try:
            partitions_out = self._ssh_exec(
                "sinfo --noheader -o '%P %a %l %D' 2>/dev/null", check=False
            )
            partitions = []
            for line in partitions_out.strip().split("\n"):
                parts = line.split()
                if parts:
                    name = parts[0].rstrip("*")
                    partitions.append({
                        "name": name,
                        "available": parts[1] if len(parts) > 1 else "unknown",
                        "timelimit": parts[2] if len(parts) > 2 else "unknown",
                        "nodes": parts[3] if len(parts) > 3 else "unknown",
                    })
            result["details"]["partitions"] = partitions

            partition_names = [p["name"] for p in partitions]
            if self.partition not in partition_names:
                result["message"] = f"Partition '{self.partition}' not found. Available: {', '.join(partition_names)}"
                result["details"]["partition_valid"] = False
                return result

            result["details"]["partition_valid"] = True
        except Exception as e:
            logger.debug(f"Could not fetch partition info for health check: {e}")

        # Check container runtime (with auto-fallback)
        try:
            runtime_out = self._ssh_exec(
                f"which {self.container_runtime} 2>/dev/null || echo 'not found'",
                check=False,
            )
            runtime_available = "not found" not in runtime_out
            result["details"]["container_runtime"] = self.container_runtime
            result["details"]["container_runtime_available"] = runtime_available
            if not runtime_available:
                alt = "apptainer" if self.container_runtime == "singularity" else "singularity"
                alt_out = self._ssh_exec(f"which {alt} 2>/dev/null || echo 'not found'", check=False)
                if "not found" not in alt_out:
                    logger.info(
                        f"Container runtime '{self.container_runtime}' not found on HPC, "
                        f"auto-switching to '{alt}'"
                    )
                    self.container_runtime = alt
                    result["details"]["container_runtime"] = alt
                    result["details"]["container_runtime_available"] = True
                    result["details"]["container_runtime_switched"] = True
        except Exception as e:
            logger.debug("Could not check container runtime: %s", e)

        # Check work directory
        try:
            self._ssh_exec(f"test -d {self.work_dir} && echo 'exists'", check=False)
            result["details"]["work_dir_accessible"] = True
        except Exception:
            result["details"]["work_dir_accessible"] = False

        result["healthy"] = True
        result["message"] = f"Connected to {self.ssh_host} (SLURM {result['details'].get('slurm_version', 'OK')})"

        return result

    # ------------------------------------------------------------------
    # SLURM-specific operations
    # ------------------------------------------------------------------

    def get_partitions(self) -> List[dict]:
        """List available SLURM partitions with details."""
        self._ensure_ssh()
        try:
            stdout = self._ssh_exec(
                "sinfo --noheader -o '%P|%a|%l|%D|%C|%m|%G' 2>/dev/null",
                check=False,
            )
            partitions = []
            for line in stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|")
                name = parts[0].rstrip("*") if parts else ""
                is_default = parts[0].endswith("*") if parts else False
                partitions.append({
                    "name": name,
                    "is_default": is_default,
                    "available": parts[1] if len(parts) > 1 else "unknown",
                    "timelimit": parts[2] if len(parts) > 2 else "unknown",
                    "nodes": parts[3] if len(parts) > 3 else "0",
                    "cpus": parts[4] if len(parts) > 4 else "0/0/0/0",
                    "memory_mb": parts[5] if len(parts) > 5 else "0",
                    "gpus": parts[6] if len(parts) > 6 else "(null)",
                })
            return partitions
        except Exception as e:
            logger.error(f"Failed to list partitions: {e}")
            return []

    def get_queue_info(self, user_only: bool = True) -> List[dict]:
        """Get SLURM queue information."""
        self._ensure_ssh()
        user_flag = f"-u {self.ssh_user}" if user_only else ""
        try:
            stdout = self._ssh_exec(
                f"squeue {user_flag} --noheader -o '%i|%j|%T|%M|%P|%l|%D|%R' 2>/dev/null",
                check=False,
            )
            jobs = []
            for line in stdout.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split("|")
                jobs.append({
                    "slurm_id": parts[0] if parts else "",
                    "name": parts[1] if len(parts) > 1 else "",
                    "state": parts[2] if len(parts) > 2 else "",
                    "time": parts[3] if len(parts) > 3 else "",
                    "partition": parts[4] if len(parts) > 4 else "",
                    "timelimit": parts[5] if len(parts) > 5 else "",
                    "nodes": parts[6] if len(parts) > 6 else "",
                    "reason": parts[7] if len(parts) > 7 else "",
                })
            return jobs
        except Exception as e:
            logger.error(f"Failed to get queue info: {e}")
            return []

    def get_account_info(self) -> dict:
        """Get user's SLURM account/allocation info."""
        self._ensure_ssh()
        info = {"accounts": [], "qos": [], "default_account": None}
        try:
            stdout = self._ssh_exec(
                f"sacctmgr show assoc where user={self.ssh_user} format=Account,QOS,DefaultQOS --noheader -P 2>/dev/null",
                check=False,
            )
            for line in stdout.strip().split("\n"):
                parts = line.split("|")
                if parts and parts[0].strip():
                    info["accounts"].append(parts[0].strip())
                    if len(parts) > 1:
                        info["qos"].extend([q.strip() for q in parts[1].split(",") if q.strip()])
            info["accounts"] = list(set(info["accounts"]))
            info["qos"] = list(set(info["qos"]))
        except Exception as e:
            logger.debug(f"Could not fetch SLURM account info for user {self.ssh_user}: {e}")
        return info

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _stage_inputs(self, spec: JobSpec, job_dir: str) -> None:
        """Symlink input files into {job_dir}/inputs/ with plugin-expected names.

        Mirrors the smart name-matching logic used by the local Docker backend:
        match each input file against the plugin's expected input keys, then
        create a symlink named {key}{ext} (e.g. T1w.nii.gz).

        When a directory is submitted but the plugin expects file-type inputs
        (e.g. T1w of type nifti), the directory is also searched for matching
        files (flat + BIDS ses-*/anat/ layout) and those are symlinked too.
        This means *every* plugin that expects T1w.nii.gz automatically works
        with folder input, without needing custom bash detection in the
        command template.
        """
        input_files = spec.input_files or []
        if not input_files:
            return

        # expected_inputs: list of (key, type) tuples for non-scalar inputs
        expected_inputs: list[tuple[str, str]] = []
        expected_names: list[str] = []
        try:
            from backend.core.plugin_registry import get_plugin_workflow_registry
            registry = get_plugin_workflow_registry()

            plugin_ids_to_check: list[str] = []
            if spec.plugin_id:
                plugin_ids_to_check.append(spec.plugin_id)
            else:
                workflow_steps = spec.parameters.get("_workflow_steps", [])
                if workflow_steps:
                    plugin_ids_to_check.extend(workflow_steps)

            workflow_id = spec.parameters.get("_workflow_id", "")
            if workflow_id:
                wf = registry.get_workflow(workflow_id)
                if wf and hasattr(wf, "inputs_required"):
                    for inp in wf.inputs_required:
                        if isinstance(inp, dict):
                            key, inp_type = inp.get("key", ""), inp.get("type", "")
                        else:
                            key, inp_type = getattr(inp, "key", ""), getattr(inp, "type", "")
                        if key and inp_type not in ("string", "int", "float", "bool"):
                            if key not in expected_names:
                                expected_names.append(key)
                                expected_inputs.append((key, inp_type))

            for pid in plugin_ids_to_check:
                plugin = registry.get_plugin(pid)
                if not plugin:
                    continue
                all_inputs = list(plugin.inputs_required or [])
                if hasattr(plugin, "inputs_optional") and plugin.inputs_optional:
                    all_inputs.extend(plugin.inputs_optional)
                for inp in all_inputs:
                    if isinstance(inp, dict):
                        key, inp_type = inp.get("key", ""), inp.get("type", "")
                    else:
                        key, inp_type = getattr(inp, "key", ""), getattr(inp, "type", "")
                    if key and inp_type not in ("string", "int", "float", "bool"):
                        if key not in expected_names:
                            expected_names.append(key)
                            expected_inputs.append((key, inp_type))
        except Exception as e:
            logger.debug("Could not resolve expected input names: %s", e)

        def _stem_lower(name: str) -> str:
            n = name.lower()
            return n[:-7] if n.endswith(".nii.gz") else PurePosixPath(n).stem

        # Check which inputs are directories (remote first, then local fallback)
        input_is_dir: dict[int, bool] = {}
        input_is_local: dict[int, bool] = {}
        for idx, input_file in enumerate(input_files):
            try:
                exit_code, stdout, _ = self._ssh.execute(
                    f'test -e "{input_file}" && (test -d "{input_file}" && echo DIR || echo FILE) || echo MISSING',
                    timeout=5,
                )
                result = stdout.strip()
                if result == "MISSING":
                    local_path = Path(input_file)
                    if local_path.exists():
                        input_is_local[idx] = True
                        input_is_dir[idx] = local_path.is_dir()
                        logger.info(
                            "Input %s not found on remote; exists locally, will upload",
                            input_file,
                        )
                    else:
                        input_is_local[idx] = False
                        input_is_dir[idx] = False
                else:
                    input_is_local[idx] = False
                    input_is_dir[idx] = result == "DIR"
            except Exception:
                input_is_local[idx] = False
                input_is_dir[idx] = False

        # Name-based matching
        matched: dict[int, str] = {}
        unmatched = list(range(len(input_files)))

        for en in expected_names:
            en_lower = en.lower()
            for idx in list(unmatched):
                stem = _stem_lower(PurePosixPath(input_files[idx]).name)
                if en_lower in stem:
                    matched[idx] = en
                    unmatched.remove(idx)
                    break

        # For unmatched directory inputs, prefer directory-type keys
        remaining = [n for n in expected_names if n not in matched.values()]
        dir_keys = [n for n in remaining if "dir" in n.lower()]
        file_keys = [n for n in remaining if "dir" not in n.lower()]

        for idx in list(unmatched):
            if input_is_dir.get(idx) and dir_keys:
                matched[idx] = dir_keys.pop(0)
                unmatched.remove(idx)
            elif not input_is_dir.get(idx) and file_keys:
                matched[idx] = file_keys.pop(0)
                unmatched.remove(idx)
            elif remaining:
                matched[idx] = remaining.pop(0)
                unmatched.remove(idx)

        staged_keys: set[str] = set()
        dir_inputs_staged: list[str] = []

        for i, input_file in enumerate(input_files):
            p = PurePosixPath(input_file)
            container_name = matched.get(i)
            is_dir = input_is_dir.get(i, False)

            if is_dir:
                link_name = container_name or p.name
            else:
                ext = "".join(p.suffixes)
                link_name = f"{container_name or p.stem}{ext}"

            link_path = f"{job_dir}/inputs/{link_name}"

            if input_is_local.get(i, False):
                try:
                    local_path = Path(input_file)
                    if is_dir:
                        self._upload_directory(str(local_path), link_path)
                    else:
                        self._ssh.put_file(str(local_path), link_path)
                    logger.info("Uploaded local input: %s -> %s (%s)", p.name, link_name, "dir" if is_dir else "file")
                    if container_name:
                        staged_keys.add(container_name)
                    if is_dir:
                        dir_inputs_staged.append(link_path)
                except Exception as e:
                    logger.warning("Could not upload local input %s: %s", input_file, e)
            else:
                try:
                    self._ssh_exec(
                        f'ln -sf "{input_file}" "{link_path}"', check=False
                    )
                    logger.info("Staged input: %s -> %s (%s)", p.name, link_name, "dir" if is_dir else "file")
                    if container_name:
                        staged_keys.add(container_name)
                    if is_dir:
                        dir_inputs_staged.append(input_file)
                except Exception as e:
                    logger.warning("Could not symlink input %s: %s", input_file, e)

            if is_dir and container_name and "bids" in container_name.lower():
                bids_path = link_path if input_is_local.get(i, False) else input_file
                self._ensure_bids_description(bids_path)

        # Auto-resolve file-type inputs from staged directories.
        # If plugin expects e.g. T1w (nifti) but user submitted a directory,
        # search the directory for the matching file and symlink it directly.
        if dir_inputs_staged:
            nifti_keys = [
                (k, t) for k, t in expected_inputs
                if t in ("nifti", "nifti_gz") and k not in staged_keys
            ]
            if nifti_keys:
                for dir_path in dir_inputs_staged:
                    for key, _ in list(nifti_keys):
                        found = self._find_nifti_in_dir(dir_path, key)
                        if found:
                            ext = ".nii.gz" if found.endswith(".nii.gz") else ".nii"
                            link_path = f"{job_dir}/inputs/{key}{ext}"
                            try:
                                self._ssh_exec(
                                    f'ln -sf "{found}" "{link_path}"', check=False
                                )
                                logger.info(
                                    "Auto-resolved %s from directory: %s",
                                    key, PurePosixPath(found).name,
                                )
                                staged_keys.add(key)
                                nifti_keys = [(k, t) for k, t in nifti_keys if k != key]
                            except Exception as e:
                                logger.warning("Could not symlink auto-resolved %s: %s", key, e)

    # File patterns for BIDS-aware NIfTI detection by modality key.
    # Each key maps to (glob_patterns, exclusion_substrings).
    _NIFTI_SEARCH_PATTERNS: dict[str, tuple[list[str], list[str]]] = {
        "T1w":   (["*T1w*.nii.gz", "*T1w*.nii"], ["label-lesion", "_roi."]),
        "T2w":   (["*T2w*.nii.gz", "*T2w*.nii"], ["T2starw", "label-lesion", "_roi."]),
        "FLAIR": (["*FLAIR*.nii.gz", "*flair*.nii.gz", "*FLAIR*.nii", "*flair*.nii"], ["label-lesion", "_roi."]),
    }

    def _find_nifti_in_dir(self, dir_path: str, key: str) -> Optional[str]:
        """Search a directory for a NIfTI file matching a modality key.

        Uses a two-pass strategy:
          1. Flat: look directly in dir_path
          2. BIDS: look in dir_path/ses-*/anat/

        Returns the absolute path of the first match, or None.
        """
        patterns, exclusions = self._NIFTI_SEARCH_PATTERNS.get(
            key, ([f"*{key}*.nii.gz", f"*{key}*.nii", "*.nii.gz", "*.nii"], ["label-lesion", "_roi."])
        )
        excl_grep = "|".join(exclusions) if exclusions else "NOMATCH"

        # Build a find command that searches flat first, then BIDS ses-*/anat/
        search_dirs = [f'"{dir_path}"']
        # Also search immediate subdirectories named anat (e.g., dir_path/anat/)
        search_dirs.append(f'"{dir_path}/anat"')
        # BIDS session layout: ses-*/anat/
        search_dirs.append(f'"{dir_path}"/ses-*/anat')

        for search_dir in search_dirs:
            for pattern in patterns:
                cmd = (
                    f'shopt -s nullglob 2>/dev/null; '
                    f'for f in {search_dir}/{pattern}; do '
                    f'  basename "$f" | grep -qiE "{excl_grep}" || {{ echo "$f"; break; }}; '
                    f'done'
                )
                try:
                    exit_code, stdout, _ = self._ssh.execute(cmd, timeout=10)
                    result = stdout.strip()
                    if result and exit_code == 0:
                        first_line = result.split("\n")[0].strip()
                        if first_line:
                            logger.debug("_find_nifti_in_dir: %s matched %s in %s", key, first_line, search_dir)
                            return first_line
                except Exception:
                    continue
        return None

    def _upload_directory(self, local_dir: str, remote_dir: str) -> None:
        """Recursively upload a local directory to the remote host via SFTP."""
        local_path = Path(local_dir)
        self._ssh_exec(f'mkdir -p "{remote_dir}"', check=False)
        for item in local_path.rglob("*"):
            relative = item.relative_to(local_path)
            remote_target = f"{remote_dir}/{relative}"
            if item.is_dir():
                self._ssh_exec(f'mkdir -p "{remote_target}"', check=False)
            elif item.is_file():
                try:
                    self._ssh.put_file(str(item), remote_target)
                except Exception as e:
                    logger.warning("Failed to upload %s: %s", item, e)

    def _ensure_bids_description(self, bids_dir: str) -> None:
        """Create a minimal dataset_description.json if missing from a BIDS dir."""
        desc_path = f"{bids_dir}/dataset_description.json"
        try:
            exit_code, stdout, _ = self._ssh.execute(
                f'test -f "{desc_path}" && echo EXISTS || echo MISSING', timeout=5
            )
            if stdout.strip() == "MISSING":
                desc_json = json.dumps({
                    "Name": PurePosixPath(bids_dir).name,
                    "BIDSVersion": "1.6.0",
                    "DatasetType": "raw",
                    "GeneratedBy": [{"Name": "NeuroInsight Research"}],
                })
                self._ssh.write_file(desc_path, desc_json)
                logger.info("Created missing dataset_description.json in %s", bids_dir)
        except Exception as e:
            logger.warning("Could not ensure BIDS description in %s: %s", bids_dir, e)

    def _resolve_all_params(self, spec: JobSpec) -> dict:
        """Build complete parameter dict for command template substitution.

        Merges (in priority order):
        1. User-supplied parameters from spec.parameters
        2. Resource-derived variables (threads, mem_gb, cpus, etc.)
        3. Plugin default parameter values from YAML definitions

        For workflows, collects defaults from ALL step plugins.
        """
        resolved = {k: v for k, v in spec.parameters.items()
                    if not str(k).startswith("_")}

        # Resource-derived variables
        res = spec.resources
        resource_vars = {
            "threads": str(res.cpus),
            "nthreads": str(res.cpus),
            "omp_nthreads": str(max(1, res.cpus - 1)),
            "mem_gb": str(res.memory_gb),
            "mem_mb": str(res.memory_gb * 1024),
            "cpus": str(res.cpus),
            "time_hours": str(res.time_hours),
        }
        for k, v in resource_vars.items():
            resolved.setdefault(k, v)

        # Plugin default parameters
        try:
            from backend.core.plugin_registry import get_plugin_workflow_registry
            registry = get_plugin_workflow_registry()

            plugin_ids = spec.parameters.get("_workflow_steps", [])
            if not plugin_ids and spec.plugin_id:
                plugin_ids = [spec.plugin_id]

            for pid in plugin_ids:
                plugin = registry.get_plugin(pid)
                if not plugin:
                    continue
                for param_def in plugin.parameters:
                    name = param_def.get("name", "") if isinstance(param_def, dict) else getattr(param_def, "name", "")
                    default = param_def.get("default") if isinstance(param_def, dict) else getattr(param_def, "default", None)
                    if name and default is not None:
                        resolved.setdefault(name, str(default))
                for inp_def in plugin.inputs_optional:
                    key = inp_def.get("key", "") if isinstance(inp_def, dict) else getattr(inp_def, "key", "")
                    default = inp_def.get("default") if isinstance(inp_def, dict) else getattr(inp_def, "default", None)
                    if key and default is not None:
                        resolved.setdefault(key, str(default))
        except Exception as e:
            logger.debug("Could not load plugin defaults: %s", e)

        # Auto-set input_file if not provided
        if spec.input_files and "input_file" not in resolved:
            resolved["input_file"] = spec.input_files[0]

        # Auto-detect subject_id from BIDS paths (sub-XXXX pattern)
        if "subject_id" not in resolved and spec.input_files:
            for f in spec.input_files:
                match = re.search(r"sub-([A-Za-z0-9]+)", f)
                if match:
                    resolved["subject_id"] = match.group(1)
                    logger.info("Auto-detected subject_id from path: %s", match.group(1))
                    break

            # If still not found, scan BIDS directory contents for sub-* folders
            if "subject_id" not in resolved:
                for f in spec.input_files:
                    try:
                        exit_code, stdout, _ = self._ssh.execute(
                            f'ls -d "{f}"/sub-* 2>/dev/null | head -1', timeout=10
                        )
                        sub_dir = stdout.strip()
                        if sub_dir:
                            match = re.search(r"sub-([A-Za-z0-9]+)", sub_dir)
                            if match:
                                resolved["subject_id"] = match.group(1)
                                logger.info("Auto-detected subject_id from BIDS directory listing: %s", match.group(1))
                                break
                    except Exception:
                        pass

        return resolved

    def _generate_sbatch_script(
        self,
        spec: JobSpec,
        job_id: str,
        job_dir: str,
        command_template: str = "",
        workflow_steps: Optional[List[dict]] = None,
    ) -> str:
        """Generate SLURM batch script.

        Produces a script that:
        1. Requests resources via #SBATCH directives
        2. Loads required environment modules
        3. Runs the pipeline inside Singularity/Apptainer
        4. Captures output and logs

        For workflows, each step runs in its own container image.
        """
        res = spec.resources

        # For workflows, compute resource requirements from step plugins
        # to avoid under-allocating (e.g., 6h default vs 28h needed).
        effective_time = res.time_hours
        effective_mem = res.memory_gb
        effective_cpus = res.cpus
        if workflow_steps:
            try:
                from backend.core.plugin_registry import get_plugin_workflow_registry
                registry = get_plugin_workflow_registry()
                total_time = 0
                max_mem = res.memory_gb
                max_cpus = res.cpus
                for step in workflow_steps:
                    step_plugin = registry.get_plugin(step["plugin_id"])
                    if step_plugin and step_plugin.resource_profiles:
                        default_res = step_plugin.resource_profiles.get("default", {})
                        if isinstance(default_res, dict):
                            total_time += default_res.get("time_hours", 0)
                            max_mem = max(max_mem, default_res.get("mem_gb", 0))
                            max_cpus = max(max_cpus, default_res.get("cpus", 0))
                if total_time > effective_time:
                    logger.info(
                        "Workflow resource override: time %dh->%dh (sum of steps)",
                        effective_time, total_time,
                    )
                    effective_time = total_time
                if max_mem > effective_mem:
                    effective_mem = max_mem
                if max_cpus > effective_cpus:
                    effective_cpus = max_cpus
            except Exception as e:
                logger.debug("Could not compute workflow resources from steps: %s", e)

        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", spec.pipeline_name[:20])
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name=ni-{safe_name}-{job_id[:8]}",
            f"#SBATCH --partition={self.partition}",
            f"#SBATCH --mem={effective_mem}G",
            f"#SBATCH --cpus-per-task={effective_cpus}",
            f"#SBATCH --time={effective_time}:00:00",
            f"#SBATCH --output={job_dir}/logs/slurm-%j.out",
            f"#SBATCH --error={job_dir}/logs/slurm-%j.err",
        ]

        if self.account:
            lines.append(f"#SBATCH --account={self.account}")
        if self.qos:
            lines.append(f"#SBATCH --qos={self.qos}")
        if res.gpu:
            lines.append("#SBATCH --gpus-per-node=1")

        lines.append("")
        lines.append("set -euo pipefail")
        lines.append("")

        # Load environment modules
        if self.modules:
            lines.append("# Load environment modules")
            for mod in self.modules:
                lines.append(f"module load {mod}")
            lines.append("")

        # Detect container runtime (auto-fallback singularity <-> apptainer)
        lines.append("# Detect container runtime (prefer configured, fallback to alternative)")
        lines.append(f'CONTAINER_RT=""')
        lines.append(f'if command -v {self.container_runtime} &>/dev/null; then')
        lines.append(f'    CONTAINER_RT="{self.container_runtime}"')
        alt_runtime = "apptainer" if self.container_runtime == "singularity" else "singularity"
        lines.append(f'elif command -v {alt_runtime} &>/dev/null; then')
        lines.append(f'    CONTAINER_RT="{alt_runtime}"')
        lines.append(f'    echo "WARNING: {self.container_runtime} not found, falling back to {alt_runtime}"')
        lines.append(f'else')
        lines.append(f'    # Try loading via module system')
        lines.append(f'    module load {self.container_runtime} 2>/dev/null || module load {alt_runtime} 2>/dev/null || true')
        lines.append(f'    if command -v {self.container_runtime} &>/dev/null; then')
        lines.append(f'        CONTAINER_RT="{self.container_runtime}"')
        lines.append(f'    elif command -v {alt_runtime} &>/dev/null; then')
        lines.append(f'        CONTAINER_RT="{alt_runtime}"')
        lines.append(f'    else')
        lines.append(f'        echo "ERROR: Neither {self.container_runtime} nor {alt_runtime} found on this system"')
        lines.append(f'        exit 1')
        lines.append(f'    fi')
        lines.append(f'fi')
        lines.append(f'echo "Using container runtime: $CONTAINER_RT"')
        lines.append("")

        # Set environment variables
        lines.append("# Job environment")
        lines.append(f'export NEUROINSIGHT_JOB_ID="{job_id}"')
        lines.append(f'export OMP_NUM_THREADS={res.cpus}')
        lines.append(f'export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS={res.cpus}')
        lines.append("")

        # Prepare bind mounts for Singularity/Apptainer
        lines.append("# Prepare directories")
        lines.append(f"mkdir -p {job_dir}/outputs/native {job_dir}/outputs/bundle {job_dir}/outputs/logs")
        lines.append("")

        # Build per-item input bind mounts to avoid Singularity nested-mount issues.
        # Symlinks in inputs/ point to host paths invisible inside the container,
        # so we mount each item individually instead of the parent directory.
        lines.append("# Build per-item input bind mounts (resolves symlinks)")
        lines.append('INPUT_BINDS=""')
        lines.append(f'for item in {job_dir}/inputs/*; do')
        lines.append('  [ -e "$item" ] || [ -L "$item" ] || continue')
        lines.append('  name=$(basename "$item")')
        lines.append('  if [ -L "$item" ]; then')
        lines.append('    target=$(readlink -f "$item")')
        lines.append('    INPUT_BINDS="$INPUT_BINDS --bind $target:/data/inputs/$name:ro"')
        lines.append('    echo "Input (resolved symlink): $target -> /data/inputs/$name"')
        lines.append('  else')
        lines.append(f'    INPUT_BINDS="$INPUT_BINDS --bind $item:/data/inputs/$name:ro"')
        lines.append('    echo "Input (direct): $item -> /data/inputs/$name"')
        lines.append('  fi')
        lines.append('done')
        lines.append("")

        # Build container command
        image = spec.container_image

        bind_mounts = [
            f"{job_dir}/outputs:/data/outputs:rw",
        ]

        # Container env vars to pass via --env
        container_envs = {
            "OMP_NUM_THREADS": str(res.cpus),
            "ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS": str(res.cpus),
        }

        # Add FreeSurfer and MELD licenses.
        # For HPC jobs, use explicit HPC paths if configured; otherwise upload
        # the local license file to the job directory on the HPC.
        try:
            from backend.core.config import get_settings
            settings = get_settings()

            fs_hpc = settings.hpc_fs_license_path
            if not fs_hpc:
                local_fs = settings.fs_license_resolved
                if local_fs and Path(local_fs).exists():
                    fs_hpc = f"{job_dir}/scripts/license.txt"
                    try:
                        self._ssh.write_file(fs_hpc, Path(local_fs).read_text())
                        logger.info("Uploaded FreeSurfer license to HPC: %s", fs_hpc)
                    except Exception as e:
                        logger.warning("Could not upload FS license to HPC: %s", e)
                        fs_hpc = None
            if fs_hpc:
                bind_mounts.append(f"{fs_hpc}:/license/license.txt:ro")
                container_envs["FS_LICENSE"] = "/license/license.txt"

            meld_hpc = settings.hpc_meld_license_path
            if not meld_hpc:
                local_meld = settings.meld_license_resolved
                if local_meld and Path(local_meld).exists():
                    meld_hpc = f"{job_dir}/scripts/meld_license.txt"
                    try:
                        self._ssh.write_file(meld_hpc, Path(local_meld).read_text())
                        logger.info("Uploaded MELD license to HPC: %s", meld_hpc)
                    except Exception as e:
                        logger.warning("Could not upload MELD license to HPC: %s", e)
                        meld_hpc = None
            if meld_hpc:
                bind_mounts.append(f"{meld_hpc}:/run/secrets/meld_license.txt:ro")

            # Matlab Compiler Runtime -- optional host-side override for
            # segmentHA_T1/T2.  MCR is baked into the freesurfer-mcr container
            # image, so this bind-mount is purely an optimisation: if the HPC
            # already has MCR on a shared filesystem, mounting it avoids
            # pulling the larger container layer.
            plugin_id = spec.parameters.get("_plugin_id", "")
            needs_mcr = plugin_id in ("segmentha_t1", "segmentha_t2")
            if not needs_mcr and workflow_steps:
                needs_mcr = any(
                    s.get("plugin_id") in ("segmentha_t1", "segmentha_t2")
                    for s in workflow_steps
                )
            if needs_mcr:
                mcr_path = settings.hpc_mcr_path
                if not mcr_path:
                    for candidate in [
                        f"{self.work_dir}/freesurfer_mcr/MCRv97",
                    ]:
                        try:
                            exit_code, out = self._ssh_exec(f"test -d {candidate} && echo yes || echo no")
                            if exit_code == 0 and "yes" in out:
                                mcr_path = candidate
                                break
                        except Exception:
                            pass
                if mcr_path:
                    bind_mounts.append(f"{mcr_path}:/usr/local/freesurfer/MCRv97:ro")
                    logger.info("MCR bind mount (host override): %s", mcr_path)
                else:
                    logger.info(
                        "No host-side MCR found; using MCR from container image"
                    )
        except Exception as e:
            logger.debug(f"Could not add license bind mounts: {e}")

        binds_str = " ".join(f"--bind {b}" for b in bind_mounts)
        envs_str = " ".join(f"--env {k}={v}" for k, v in container_envs.items())

        all_params = self._resolve_all_params(spec)
        dangerous_chars = set(";|&`$(){}!><\n\r")

        def _substitute_params(template: str) -> str:
            result = template
            for key, value in all_params.items():
                if not str(key).startswith("_"):
                    safe_val = "".join(c for c in str(value) if c not in dangerous_chars)
                    result = result.replace(f"{{{key}}}", safe_val)
                    result = result.replace(f"${{{key}}}", safe_val)
            return result

        # Map of plugin_id -> container output path (populated during step iteration)
        _step_output_paths: dict[str, str] = {}

        # Known output paths for each plugin (host-side, relative to job_dir/outputs)
        _PLUGIN_OUTPUT_DIRS = {
            "qsiprep":       "native/qsiprep/qsiprep",
            "qsirecon":      "native/qsirecon",
            "fmriprep":      "native/fmriprep",
            "xcpd":          "native/xcpd",
            "freesurfer_recon":             "native/freesurfer/SUBJECTS_DIR",
            "freesurfer_autorecon_volonly":  "native/freesurfer/SUBJECTS_DIR",
            "freesurfer_longitudinal":      "native/freesurfer/SUBJECTS_DIR",
            "fastsurfer":    "native/fastsurfer",
        }

        if workflow_steps:
            # ---- Workflow: run each step in its own container ----
            total = len(workflow_steps)
            lines.append("PIPELINE_EXIT=0")
            lines.append("")

            for step_idx, step in enumerate(workflow_steps):
                step_num = step_idx + 1
                step_image = step["image"]
                step_name = step["name"]
                step_pid = step["plugin_id"]

                cmd_script = _substitute_params(step["command_template"])

                # Build extra bind mounts for inter-step output chaining.
                # Scan the command template for /data/inputs/{name} references and
                # bind the matching previous step's output directory there.
                step_extra_binds = ""
                step_override_names: list[str] = []
                if step_idx > 0:
                    for prev_step in workflow_steps[:step_idx]:
                        prev_pid = prev_step["plugin_id"]
                        host_out = _PLUGIN_OUTPUT_DIRS.get(prev_pid)
                        if not host_out:
                            continue
                        full_host_path = f"{job_dir}/outputs/{host_out}"
                        for m in re.finditer(r'/data/inputs/(\w+)', cmd_script):
                            input_name = m.group(1)
                            container_input = f"/data/inputs/{input_name}"
                            if (prev_pid in input_name
                                    or input_name.replace("_derivatives", "") == prev_pid
                                    or input_name == "subjects_dir"
                                    or input_name == "freesurfer_subjects_dir"):
                                step_extra_binds += f" --bind {full_host_path}:{container_input}:ro"
                                step_override_names.append(input_name)
                                logger.info(
                                    "Workflow step %d: bind previous output %s -> %s",
                                    step_num, full_host_path, container_input,
                                )
                                break

                # Record this step's output path for downstream steps
                if step_pid in _PLUGIN_OUTPUT_DIRS:
                    _step_output_paths[step_pid] = f"{job_dir}/outputs/{_PLUGIN_OUTPUT_DIRS[step_pid]}"

                # If this step overrides input names via inter-step binds,
                # build a filtered INPUT_BINDS that skips conflicting names.
                if step_override_names:
                    skip_var = f"STEP_{step_num}_SKIP"
                    input_var = f"STEP_{step_num}_INPUT_BINDS"
                    skip_list = " ".join(step_override_names)
                    lines.append(f'# Filter INPUT_BINDS for step {step_num} (skip names overridden by inter-step binds)')
                    lines.append(f'{skip_var}="{skip_list}"')
                    lines.append(f'{input_var}=""')
                    lines.append(f'for item in {job_dir}/inputs/*; do')
                    lines.append(f'  [ -e "$item" ] || [ -L "$item" ] || continue')
                    lines.append(f'  name=$(basename "$item")')
                    lines.append(f'  _skip=0; for _s in ${skip_var}; do [ "$name" = "$_s" ] && _skip=1 && break; done')
                    lines.append(f'  [ $_skip -eq 1 ] && continue')
                    lines.append(f'  if [ -L "$item" ]; then')
                    lines.append(f'    target=$(readlink -f "$item")')
                    lines.append(f'    {input_var}="${input_var} --bind $target:/data/inputs/$name:ro"')
                    lines.append(f'  else')
                    lines.append(f'    {input_var}="${input_var} --bind $item:/data/inputs/$name:ro"')
                    lines.append(f'  fi')
                    lines.append(f'done')
                    lines.append("")
                    input_binds_ref = f"${input_var}"
                else:
                    input_binds_ref = "$INPUT_BINDS"

                lines.append(f'# ---- Workflow step {step_num}/{total}: {step_name} ----')
                lines.append(f'if [ $PIPELINE_EXIT -eq 0 ]; then')
                lines.append(f'echo "=== WORKFLOW STEP {step_num}/{total}: {step_name} ==="')
                lines.append(f"cat > {job_dir}/scripts/step_{step_num}_cmd.sh << 'NI_STEP_{step_num}_EOF'")
                lines.append(cmd_script)
                lines.append(f"NI_STEP_{step_num}_EOF")
                lines.append(f"chmod +x {job_dir}/scripts/step_{step_num}_cmd.sh")
                lines.append("set +e")
                lines.append(
                    f"$CONTAINER_RT exec --writable-tmpfs {envs_str} {binds_str} {input_binds_ref}{step_extra_binds} "
                    f"--bind {job_dir}/scripts/step_{step_num}_cmd.sh:/run_pipeline.sh:ro "
                    f"docker://{step_image} "
                    f"bash /run_pipeline.sh 2>&1 | tee {job_dir}/outputs/logs/step_{step_num}_{step_pid}.log"
                )
                lines.append('PIPELINE_EXIT=${PIPESTATUS[0]}')
                lines.append("set -e")
                lines.append(f'echo "Step {step_num} ({step_name}) exited with code $PIPELINE_EXIT"')
                lines.append('fi')
                lines.append("")

        elif command_template:
            # ---- Single plugin: one container ----
            cmd_script = _substitute_params(command_template)

            lines.append("# Write pipeline command script")
            lines.append(f"cat > {job_dir}/scripts/pipeline_cmd.sh << 'NEUROINSIGHT_CMD_EOF'")
            lines.append(cmd_script)
            lines.append("NEUROINSIGHT_CMD_EOF")
            lines.append(f"chmod +x {job_dir}/scripts/pipeline_cmd.sh")
            lines.append("")
            lines.append(f"# Run pipeline in container")
            lines.append("set +e")
            lines.append(
                f"$CONTAINER_RT exec --writable-tmpfs {envs_str} {binds_str} $INPUT_BINDS "
                f"--bind {job_dir}/scripts/pipeline_cmd.sh:/run_pipeline.sh:ro "
                f"docker://{image} "
                f"bash /run_pipeline.sh 2>&1 | tee {job_dir}/outputs/logs/container.log"
            )
            lines.append('PIPELINE_EXIT=${PIPESTATUS[0]}')
            lines.append("set -e")
        else:
            lines.append(f"# Run container (default command)")
            lines.append("set +e")
            lines.append(
                f"$CONTAINER_RT run --writable-tmpfs {envs_str} {binds_str} "
                f"docker://{image} 2>&1 | tee {job_dir}/outputs/logs/container.log"
            )
            lines.append('PIPELINE_EXIT=${PIPESTATUS[0]}')
            lines.append("set -e")

        lines.append("")
        lines.append('echo "Pipeline exited with code $PIPELINE_EXIT"')
        lines.append("")

        # Post-container: generate stats CSVs if converter is available
        lines.append("# Post-processing: generate stats CSVs")
        lines.append(f'CONVERTER="{job_dir}/scripts/stats_converter.py"')
        lines.append(f'OUTPUT_DIR="{job_dir}/outputs"')
        pipeline_name_escaped = spec.pipeline_name.replace("'", "'\\''")
        lines.append('if [ -f "$CONVERTER" ] && command -v python3 &>/dev/null; then')
        lines.append('  echo "Generating stats CSVs..."')
        lines.append("  python3 << 'NI_STATS_EOF'")
        lines.append(f'import sys; sys.path.insert(0, "{job_dir}/scripts")')
        lines.append('from stats_converter import FileProvider, generate_stats_csvs')
        lines.append('from pathlib import Path')
        lines.append(f'fp = FileProvider(local_dir="{job_dir}/outputs")')
        lines.append(f'sheets = generate_stats_csvs("{pipeline_name_escaped}", fp)')
        lines.append('if sheets:')
        lines.append(f'    csv_dir = Path("{job_dir}/outputs/bundle/csv")')
        lines.append('    csv_dir.mkdir(parents=True, exist_ok=True)')
        lines.append('    for s in sheets:')
        lines.append('        (csv_dir / s.filename).write_text(s.to_csv_string())')
        lines.append('    print(f"Generated {len(sheets)} stats CSVs")')
        lines.append('else:')
        lines.append('    print("No stats to convert")')
        lines.append('NI_STATS_EOF')
        lines.append('fi')
        lines.append("")
        lines.append('echo "NeuroInsight job completed with exit code $PIPELINE_EXIT"')
        lines.append('exit $PIPELINE_EXIT')
        lines.append("")

        return "\n".join(lines)

    def _get_slurm_id(self, job_id: str) -> Optional[str]:
        """Look up SLURM job ID from local cache or database."""
        # Check local cache
        if job_id in self._jobs:
            return self._jobs[job_id].get("slurm_id")

        # Check database
        try:
            from backend.core.database import get_db_context
            from backend.models.job import Job
            with get_db_context() as db:
                job = db.query(Job).filter_by(id=job_id).first()
                if job and job.backend_job_id:
                    return job.backend_job_id
        except Exception as e:
            logger.debug(f"Could not look up slurm_id from DB for job {job_id[:8]}: {e}")

        return None

    def _parse_slurm_job_id(self, sbatch_output: str) -> str:
        """Parse SLURM job ID from sbatch output."""
        match = re.search(r"Submitted batch job (\d+)", sbatch_output)
        if match:
            return match.group(1)
        raise ExecutionError(f"Failed to parse SLURM job ID from: {sbatch_output}")
    
    def _parse_slurm_status(self, status_str: str) -> JobStatus:
        """Map SLURM state string to JobStatus enum."""
        status_map = {
            "PENDING": JobStatus.PENDING,
            "CONFIGURING": JobStatus.PENDING,
            "RUNNING": JobStatus.RUNNING,
            "COMPLETING": JobStatus.RUNNING,
            "COMPLETED": JobStatus.COMPLETED,
            "FAILED": JobStatus.FAILED,
            "CANCELLED": JobStatus.CANCELLED,
            "TIMEOUT": JobStatus.FAILED,
            "OUT_OF_MEMORY": JobStatus.FAILED,
            "NODE_FAIL": JobStatus.FAILED,
            "PREEMPTED": JobStatus.FAILED,
            "SUSPENDED": JobStatus.PENDING,
        }
        clean = status_str.strip().upper().split("+")[0]  # Handle "CANCELLED+"
        return status_map.get(clean, JobStatus.UNKNOWN)

    def _query_sacct(self, slurm_id: str) -> dict:
        """Query sacct for detailed job info."""
        info: dict = {}
        try:
            stdout = self._ssh_exec(
                f"sacct -j {slurm_id} --noheader -P "
                f"--format=JobID,State,ExitCode,Start,End,Elapsed,MaxRSS,NNodes,NCPUS 2>/dev/null | head -1",
                check=False,
            )
            parts = stdout.strip().split("|")
            if len(parts) >= 5:
                state = parts[1].split("+")[0] if len(parts) > 1 else ""
                info["status"] = self._parse_slurm_status(state)

                # Parse exit code (format: "0:0" -> exitcode:signal)
                if len(parts) > 2 and ":" in parts[2]:
                    info["exit_code"] = int(parts[2].split(":")[0])

                # Parse times
                if len(parts) > 3 and parts[3] != "Unknown":
                    try:
                        info["start_time"] = datetime.strptime(parts[3], "%Y-%m-%dT%H:%M:%S")
                    except ValueError as e:
                        logger.debug(f"Could not parse sacct start_time '{parts[3]}': {e}")
                if len(parts) > 4 and parts[4] != "Unknown":
                    try:
                        info["end_time"] = datetime.strptime(parts[4], "%Y-%m-%dT%H:%M:%S")
                    except ValueError as e:
                        logger.debug("Could not parse sacct end_time '%s': %s", parts[4], e)
        except Exception as e:
            logger.debug(f"sacct query failed for {slurm_id}: {e}")

        return info

    def _parse_progress(self, job_id: str) -> tuple:
        """Parse progress from job log file using phase milestones.

        Returns (progress_int, phase_label).
        """
        local = self._jobs.get(job_id, {})
        job_dir = local.get("job_dir", "")
        if not job_dir:
            return (0, "")

        try:
            log_path = f"{job_dir}/outputs/logs/container.log"
            if not self._ssh.file_exists(log_path):
                return (0, "Running")

            log_content = self._ssh.read_file(log_path)

            # Load milestones for this plugin
            plugin_id = local.get("spec", {}).get("plugin_id", "")
            from backend.core.phase_milestones import get_milestones
            milestones = get_milestones(plugin_id)

            best_progress = 0
            best_label = "Running"
            for marker, pct, label in milestones:
                if pct > best_progress:
                    try:
                        if re.search(marker, log_content):
                            best_progress = pct
                            best_label = label
                    except re.error:
                        if marker in log_content:
                            best_progress = pct
                            best_label = label

            return (best_progress, best_label)

        except Exception as e:
            logger.debug(f"Could not parse progress from log for job {job_id[:8]}: {e}")
            return (0, "Running")
