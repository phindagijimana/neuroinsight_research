"""
Remote Docker Backend

Executes neuroimaging jobs on any SSH-accessible Linux machine that has Docker
installed. This works with:
  - AWS EC2 instances
  - Google Cloud VMs
  - Azure VMs
  - DigitalOcean Droplets
  - Any Linux server with Docker + SSH

Architecture:
    - SSH connection managed by SSHManager (paramiko)
    - Docker commands executed via `docker run` over SSH
    - Job status tracked by polling container state
    - Logs retrieved via `docker logs` over SSH
    - Files transferred via SFTP when needed
    - No SLURM, no Singularity -- just plain Docker
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


# Map Docker container states to our JobStatus
_DOCKER_STATE_MAP = {
    "created": JobStatus.PENDING,
    "running": JobStatus.RUNNING,
    "paused": JobStatus.RUNNING,
    "restarting": JobStatus.RUNNING,
    "removing": JobStatus.RUNNING,
    "exited": JobStatus.COMPLETED,  # check exit code for FAILED
    "dead": JobStatus.FAILED,
}


class RemoteDockerBackend(ExecutionBackend):
    """Remote Docker execution backend.

    Runs Docker containers on a remote Linux machine over SSH.
    Works with any server that has Docker installed (EC2, cloud VMs, etc.)
    """

    def __init__(
        self,
        ssh_host: str,
        ssh_user: str,
        work_dir: str = "/tmp/neuroinsight",
        max_concurrent_jobs: int = 4,
        gpu_flag: str = "--gpus all",
    ):
        self._ssh_host = ssh_host
        self._ssh_user = ssh_user
        self._work_dir = work_dir
        self._max_concurrent_jobs = max_concurrent_jobs
        self._gpu_flag = gpu_flag

        # Track jobs: job_id -> {container_name, spec, submitted_at, ...}
        self._jobs: Dict[str, dict] = {}

        logger.info(
            f"RemoteDockerBackend initialized: {ssh_user}@{ssh_host}, "
            f"work_dir={work_dir}"
        )

    @property
    def backend_type(self) -> str:
        return "remote_docker"

    # ------------------------------------------------------------------
    # SSH helpers
    # ------------------------------------------------------------------

    def _ssh(self) -> SSHManager:
        """Get the shared SSH manager."""
        mgr = get_ssh_manager()
        if not mgr.is_connected:
            raise BackendUnavailableError(
                "SSH not connected. Connect to the remote server first."
            )
        return mgr

    def _run(self, cmd: str, timeout: int = 120, check: bool = False):
        """Execute a command on the remote host via SSH."""
        return self._ssh().execute(cmd, timeout=timeout, check=check)

    def _container_name(self, job_id: str) -> str:
        """Generate a unique Docker container name for a job."""
        short_id = job_id[:12].replace("-", "")
        return f"neuroinsight_{short_id}"

    # ------------------------------------------------------------------
    # Job submission
    # ------------------------------------------------------------------

    def submit_job(self, spec: JobSpec, job_id: Optional[str] = None) -> str:
        """Submit a job to run in Docker on the remote machine."""
        if job_id is None:
            job_id = str(uuid.uuid4())

        container_name = self._container_name(job_id)
        ssh = self._ssh()

        # Create working directories on remote
        job_dir = f"{self._work_dir}/jobs/{job_id}"
        self._run(f"mkdir -p {job_dir}/inputs {job_dir}/outputs {job_dir}/logs")

        # Upload input files if they are local paths
        for i, input_file in enumerate(spec.input_files):
            if input_file.startswith("/") or input_file.startswith("./"):
                try:
                    from pathlib import Path
                    local_path = Path(input_file)
                    if local_path.exists():
                        remote_input = f"{job_dir}/inputs/{local_path.name}"
                        ssh.put_file(str(local_path), remote_input)
                        logger.info(f"Uploaded {local_path.name} to remote")
                except Exception as e:
                    logger.warning(f"Could not upload input file {input_file}: {e}")

        # Build docker run command
        image = spec.container_image
        resources = spec.resources if isinstance(spec.resources, ResourceSpec) else ResourceSpec()

        docker_args = [
            "docker run -d",
            f"--name {container_name}",
            f"--cpus={resources.cpus}",
            f"--memory={resources.memory_gb}g",
            f"-v {job_dir}/inputs:/data/inputs:ro",
            f"-v {job_dir}/outputs:/data/outputs:rw",
        ]

        # GPU support
        if resources.gpu:
            docker_args.append(self._gpu_flag)

        # Environment variables
        docker_args.append(f"-e OMP_NUM_THREADS={resources.cpus}")
        docker_args.append(f"-e ITK_GLOBAL_DEFAULT_NUMBER_OF_THREADS={resources.cpus}")
        docker_args.append(f"-e NEUROINSIGHT_JOB_ID={job_id}")

        # Build command from template or use container default
        command_template = spec.parameters.get("_command_template", "")
        if not command_template:
            # Try to get from plugin registry
            try:
                from backend.core.plugin_registry import get_plugin_workflow_registry
                registry = get_plugin_workflow_registry()
                plugin = registry.get_plugin(spec.plugin_id) if spec.plugin_id else None
                if plugin:
                    command_template = plugin.command_template or plugin.command
            except Exception:
                pass

        if command_template:
            # Substitute parameters into template
            cmd = command_template
            for key, value in spec.parameters.items():
                if not key.startswith("_"):
                    cmd = cmd.replace(f"{{{key}}}", str(value))
                    cmd = cmd.replace(f"${{{key}}}", str(value))
            docker_args.append(image)
            docker_args.append(f'bash -c "{cmd}"')
        else:
            docker_args.append(image)

        full_cmd = " ".join(docker_args)
        logger.info(f"Submitting remote Docker job: {container_name}")

        # Pull image first if not present
        exit_code, stdout, stderr = self._run(
            f"docker image inspect {image} > /dev/null 2>&1 || docker pull {image}",
            timeout=600,
        )

        # Run the container
        exit_code, stdout, stderr = self._run(full_cmd, timeout=30)
        if exit_code != 0:
            raise ExecutionError(
                f"Failed to start container on remote: {stderr.strip()}"
            )

        container_id = stdout.strip()[:12]
        logger.info(f"Remote container started: {container_name} ({container_id})")

        # Track the job
        self._jobs[job_id] = {
            "container_name": container_name,
            "container_id": container_id,
            "job_dir": job_dir,
            "spec": spec,
            "submitted_at": datetime.utcnow(),
            "image": image,
        }

        # Save job metadata on remote for persistence
        meta = {
            "job_id": job_id,
            "container_name": container_name,
            "pipeline_name": spec.pipeline_name,
            "image": image,
            "submitted_at": datetime.utcnow().isoformat(),
        }
        ssh.write_file(
            f"{job_dir}/job_meta.json",
            json.dumps(meta, indent=2),
        )

        return job_id

    # ------------------------------------------------------------------
    # Status & info
    # ------------------------------------------------------------------

    def get_job_status(self, job_id: str) -> JobStatus:
        """Get job status by querying Docker container state on remote."""
        container_name = self._get_container_name(job_id)

        exit_code, stdout, stderr = self._run(
            f'docker inspect --format "{{{{.State.Status}}}} {{{{.State.ExitCode}}}}" {container_name} 2>/dev/null',
            timeout=10,
        )

        if exit_code != 0:
            return JobStatus.UNKNOWN

        parts = stdout.strip().split()
        if len(parts) < 2:
            return JobStatus.UNKNOWN

        state = parts[0].lower()
        container_exit_code = int(parts[1]) if parts[1].isdigit() else -1

        status = _DOCKER_STATE_MAP.get(state, JobStatus.UNKNOWN)

        # If container exited, check exit code to distinguish completed vs failed
        if state == "exited":
            status = JobStatus.COMPLETED if container_exit_code == 0 else JobStatus.FAILED

        return status

    def get_job_info(self, job_id: str) -> JobInfo:
        """Get detailed job information from remote container."""
        container_name = self._get_container_name(job_id)
        job_meta = self._jobs.get(job_id, {})

        # Get container inspection
        exit_code, stdout, stderr = self._run(
            f"docker inspect {container_name} 2>/dev/null",
            timeout=10,
        )

        status = self.get_job_status(job_id)

        info = JobInfo(
            job_id=job_id,
            status=status,
            pipeline_name=job_meta.get("spec", JobSpec(
                pipeline_name="Unknown", container_image="", input_files=[], output_dir="", parameters={}
            )).pipeline_name if "spec" in job_meta else "Unknown",
            container_image=job_meta.get("image", ""),
            backend_job_id=container_name,
            submitted_at=job_meta.get("submitted_at"),
        )

        if exit_code == 0 and stdout.strip():
            try:
                inspect_data = json.loads(stdout)[0]
                state = inspect_data.get("State", {})

                if state.get("StartedAt"):
                    started = state["StartedAt"].replace("Z", "+00:00")
                    try:
                        info.started_at = datetime.fromisoformat(started.split(".")[0])
                    except (ValueError, IndexError):
                        pass

                if state.get("FinishedAt") and not state["FinishedAt"].startswith("0001"):
                    finished = state["FinishedAt"].replace("Z", "+00:00")
                    try:
                        info.completed_at = datetime.fromisoformat(finished.split(".")[0])
                    except (ValueError, IndexError):
                        pass

                info.exit_code = state.get("ExitCode")
                if info.exit_code and info.exit_code != 0:
                    info.error_message = state.get("Error", f"Exit code {info.exit_code}")
            except (json.JSONDecodeError, IndexError, KeyError):
                pass

        return info

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job by stopping the Docker container."""
        container_name = self._get_container_name(job_id)
        exit_code, _, _ = self._run(
            f"docker stop {container_name} 2>/dev/null",
            timeout=30,
        )
        return exit_code == 0

    def get_job_logs(self, job_id: str) -> JobLogs:
        """Get container logs from remote."""
        container_name = self._get_container_name(job_id)

        exit_code, stdout, stderr = self._run(
            f"docker logs --tail 1000 {container_name} 2>&1",
            timeout=15,
        )

        return JobLogs(
            job_id=job_id,
            stdout=stdout if exit_code == 0 else "",
            stderr=stderr,
        )

    def list_jobs(self, status_filter: Optional[List[str]] = None, limit: int = 100) -> List[JobInfo]:
        """List jobs by querying Docker containers on remote."""
        # Get all neuroinsight containers
        exit_code, stdout, stderr = self._run(
            'docker ps -a --filter "name=neuroinsight_" '
            '--format "{{.Names}} {{.Status}} {{.CreatedAt}}"',
            timeout=10,
        )

        jobs = []
        if exit_code == 0 and stdout.strip():
            for line in stdout.strip().split("\n"):
                parts = line.split(None, 2)
                if len(parts) < 2:
                    continue
                container_name = parts[0]
                status_str = parts[1].lower()

                # Derive job_id from container name
                job_id = self._job_id_from_container(container_name)
                if not job_id:
                    continue

                # Map Docker status text
                if "up" in status_str:
                    status = JobStatus.RUNNING
                elif "exited" in status_str:
                    status = JobStatus.COMPLETED
                else:
                    status = JobStatus.UNKNOWN

                if status_filter and status.value not in status_filter:
                    continue

                jobs.append(JobInfo(
                    job_id=job_id,
                    status=status,
                    pipeline_name=self._jobs.get(job_id, {}).get("spec", None) and
                                  self._jobs[job_id]["spec"].pipeline_name or "Unknown",
                    backend_job_id=container_name,
                ))

                if len(jobs) >= limit:
                    break

        return jobs

    def cleanup_job(self, job_id: str) -> bool:
        """Remove container and optionally job directory from remote."""
        container_name = self._get_container_name(job_id)
        self._run(f"docker rm -f {container_name} 2>/dev/null", timeout=15)

        # Optionally clean job directory
        job_dir = f"{self._work_dir}/jobs/{job_id}"
        self._run(f"rm -rf {job_dir} 2>/dev/null", timeout=15)

        self._jobs.pop(job_id, None)
        return True

    def health_check(self) -> dict:
        """Check if remote Docker is accessible."""
        try:
            ssh = self._ssh()
            exit_code, stdout, stderr = self._run("docker info --format '{{.ServerVersion}}'", timeout=10)

            if exit_code != 0:
                return {
                    "healthy": False,
                    "message": "Docker not available on remote server",
                    "details": {"error": stderr.strip()},
                }

            docker_version = stdout.strip()

            # Get system resources
            _, cpu_out, _ = self._run("nproc", timeout=5)
            _, mem_out, _ = self._run(
                "free -g | awk '/^Mem:/{print $2}'", timeout=5
            )
            _, gpu_out, _ = self._run(
                "nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | wc -l",
                timeout=5,
            )

            return {
                "healthy": True,
                "message": f"Remote Docker {docker_version} on {self._ssh_host}",
                "details": {
                    "docker_version": docker_version,
                    "host": self._ssh_host,
                    "cpus": cpu_out.strip(),
                    "memory_gb": mem_out.strip(),
                    "gpus": gpu_out.strip(),
                    "work_dir": self._work_dir,
                },
            }
        except SSHConnectionError:
            return {
                "healthy": False,
                "message": "SSH not connected",
                "details": {},
            }
        except Exception as e:
            return {
                "healthy": False,
                "message": str(e),
                "details": {},
            }

    # ------------------------------------------------------------------
    # Remote system info (non-SLURM)
    # ------------------------------------------------------------------

    def get_system_info(self) -> dict:
        """Get system information from the remote machine.

        Returns CPU, memory, GPU, OS, Docker info -- useful for
        displaying remote server capabilities in the UI.
        """
        info: Dict = {"host": self._ssh_host, "user": self._ssh_user}

        try:
            # OS info
            _, os_out, _ = self._run("cat /etc/os-release 2>/dev/null | head -2", timeout=5)
            for line in os_out.strip().split("\n"):
                if line.startswith("PRETTY_NAME="):
                    info["os"] = line.split("=", 1)[1].strip('"')

            # CPU
            _, cpu_model, _ = self._run(
                "lscpu | grep 'Model name' | sed 's/Model name:\\s*//'", timeout=5
            )
            _, cpu_count, _ = self._run("nproc", timeout=5)
            info["cpu_model"] = cpu_model.strip()
            info["cpu_count"] = int(cpu_count.strip()) if cpu_count.strip().isdigit() else 0

            # Memory
            _, mem_out, _ = self._run("free -g | awk '/^Mem:/{print $2}'", timeout=5)
            info["memory_gb"] = int(mem_out.strip()) if mem_out.strip().isdigit() else 0

            # Disk
            _, disk_out, _ = self._run(
                f"df -BG {self._work_dir} 2>/dev/null | tail -1 | awk '{{print $4}}'",
                timeout=5,
            )
            disk_str = disk_out.strip().rstrip("G")
            info["disk_free_gb"] = int(disk_str) if disk_str.isdigit() else 0

            # GPU
            exit_code, gpu_out, _ = self._run(
                "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null",
                timeout=5,
            )
            if exit_code == 0 and gpu_out.strip():
                gpus = []
                for line in gpu_out.strip().split("\n"):
                    parts = line.split(",")
                    gpus.append({
                        "name": parts[0].strip(),
                        "memory": parts[1].strip() if len(parts) > 1 else "unknown",
                    })
                info["gpus"] = gpus
            else:
                info["gpus"] = []

            # Docker
            _, docker_ver, _ = self._run("docker --version 2>/dev/null", timeout=5)
            info["docker_version"] = docker_ver.strip()

            # Running containers count
            _, containers_out, _ = self._run(
                'docker ps --filter "name=neuroinsight_" -q | wc -l', timeout=5
            )
            info["running_jobs"] = int(containers_out.strip()) if containers_out.strip().isdigit() else 0

        except Exception as e:
            logger.warning(f"Failed to get remote system info: {e}")
            info["error"] = str(e)

        return info

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_container_name(self, job_id: str) -> str:
        """Get container name for a job, checking tracked jobs first."""
        if job_id in self._jobs:
            return self._jobs[job_id]["container_name"]
        return self._container_name(job_id)

    def _job_id_from_container(self, container_name: str) -> Optional[str]:
        """Reverse-lookup job_id from container name."""
        for jid, meta in self._jobs.items():
            if meta.get("container_name") == container_name:
                return jid
        # If not tracked, return None (orphaned container)
        return None
