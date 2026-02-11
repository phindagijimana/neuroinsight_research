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
from pathlib import PurePosixPath
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
        work_dir: str = "/scratch",
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
            work_dir: Working directory on HPC (e.g. /scratch/username)
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

        # Create remote working directory
        job_dir = str(PurePosixPath(self.work_dir) / "neuroinsight" / "jobs" / job_id)
        for sub in ("scripts", "logs", "inputs", "outputs/native", "outputs/bundle", "outputs/logs"):
            self._ssh_exec(f"mkdir -p {job_dir}/{sub}")

        # Get command template from plugin
        command_template = ""
        try:
            from backend.core.plugin_registry import get_plugin_workflow_registry
            registry = get_plugin_workflow_registry()
            plugin = registry.get_plugin(spec.plugin_id) if spec.plugin_id else None
            if plugin:
                command_template = plugin.command_template or plugin.command
        except Exception:
            pass

        # Generate and upload sbatch script
        sbatch_script = self._generate_sbatch_script(spec, job_id, job_dir, command_template)
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
        except Exception:
            pass

        # Fall back to sacct (for completed/failed jobs)
        try:
            stdout = self._ssh_exec(
                f"sacct -j {slurm_id} --noheader --format=State -P 2>/dev/null | head -1",
                check=False,
            )
            status_str = stdout.strip().split("+")[0]  # Handle "CANCELLED+" etc.
            if status_str:
                return self._parse_slurm_status(status_str)
        except Exception:
            pass

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
            except Exception:
                pass

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
            except Exception:
                pass

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
            except Exception:
                pass

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
            except Exception:
                pass

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
            except Exception:
                pass

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
        except Exception:
            pass

        # Check container runtime
        try:
            runtime_out = self._ssh_exec(
                f"which {self.container_runtime} 2>/dev/null || echo 'not found'",
                check=False,
            )
            runtime_available = "not found" not in runtime_out
            result["details"]["container_runtime"] = self.container_runtime
            result["details"]["container_runtime_available"] = runtime_available
            if not runtime_available:
                # Try alternative
                alt = "apptainer" if self.container_runtime == "singularity" else "singularity"
                alt_out = self._ssh_exec(f"which {alt} 2>/dev/null || echo 'not found'", check=False)
                if "not found" not in alt_out:
                    result["details"]["container_runtime_alt"] = alt
        except Exception:
            pass

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
        except Exception:
            pass
        return info

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_sbatch_script(
        self,
        spec: JobSpec,
        job_id: str,
        job_dir: str,
        command_template: str = "",
    ) -> str:
        """Generate SLURM batch script.

        Produces a script that:
        1. Requests resources via #SBATCH directives
        2. Loads required environment modules
        3. Runs the pipeline inside Singularity/Apptainer
        4. Captures output and logs
        """
        res = spec.resources
        lines = [
            "#!/bin/bash",
            f"#SBATCH --job-name=ni-{spec.pipeline_name[:20]}-{job_id[:8]}",
            f"#SBATCH --partition={self.partition}",
            f"#SBATCH --mem={res.memory_gb}G",
            f"#SBATCH --cpus-per-task={res.cpus}",
            f"#SBATCH --time={res.time_hours}:00:00",
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

        # Always try to load container runtime module
        lines.append(f"# Ensure container runtime is available")
        lines.append(f"module load {self.container_runtime} 2>/dev/null || true")
        lines.append("")

        # Set environment variables
        lines.append("# Job environment")
        lines.append(f'export NEUROINSIGHT_JOB_ID="{job_id}"')
        lines.append(f'export OMP_NUM_THREADS={res.cpus}')
        lines.append(f'export ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS={res.cpus}')
        lines.append("")

        # Prepare bind mounts for Singularity
        lines.append("# Prepare directories")
        lines.append(f"mkdir -p {job_dir}/outputs/native {job_dir}/outputs/bundle {job_dir}/outputs/logs")
        lines.append("")

        # Build container command
        image = spec.container_image
        runtime = self.container_runtime

        bind_mounts = [
            f"{job_dir}/inputs:/data/inputs:ro",
            f"{job_dir}/outputs:/data/outputs:rw",
        ]

        # Add FreeSurfer license if needed
        try:
            from backend.core.config import get_settings
            settings = get_settings()
            if settings.fs_license_resolved:
                bind_mounts.append(f"{settings.fs_license_resolved}:/license/license.txt:ro")
        except Exception:
            pass

        binds_str = " ".join(f"--bind {b}" for b in bind_mounts)

        if command_template:
            # Write command template as script inside container
            # Substitute parameters into template
            cmd_script = command_template
            # Sanitize parameters to prevent shell injection
            dangerous_chars = set(";|&`$(){}!><\n\r")
            for key, value in spec.parameters.items():
                if not str(key).startswith("_"):
                    safe_val = "".join(c for c in str(value) if c not in dangerous_chars)
                    cmd_script = cmd_script.replace(f"{{{key}}}", safe_val)
                    cmd_script = cmd_script.replace(f"${{{key}}}", safe_val)

            lines.append("# Write pipeline command script")
            lines.append(f"cat > {job_dir}/scripts/pipeline_cmd.sh << 'NEUROINSIGHT_CMD_EOF'")
            lines.append(cmd_script)
            lines.append("NEUROINSIGHT_CMD_EOF")
            lines.append(f"chmod +x {job_dir}/scripts/pipeline_cmd.sh")
            lines.append("")
            lines.append(f"# Run pipeline in container")
            lines.append(
                f"{runtime} exec {binds_str} "
                f"--bind {job_dir}/scripts/pipeline_cmd.sh:/run_pipeline.sh:ro "
                f"docker://{image} "
                f"bash /run_pipeline.sh 2>&1 | tee {job_dir}/outputs/logs/container.log"
            )
        else:
            # No command template -- run container's default CMD
            lines.append(f"# Run container (default command)")
            lines.append(
                f"{runtime} run {binds_str} "
                f"docker://{image} 2>&1 | tee {job_dir}/outputs/logs/container.log"
            )

        lines.append("")
        lines.append('echo "NeuroInsight job completed with exit code $?"')
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
        except Exception:
            pass

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
                    except ValueError:
                        pass
                if len(parts) > 4 and parts[4] != "Unknown":
                    try:
                        info["end_time"] = datetime.strptime(parts[4], "%Y-%m-%dT%H:%M:%S")
                    except ValueError:
                        pass
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

        except Exception:
            return (0, "Running")
