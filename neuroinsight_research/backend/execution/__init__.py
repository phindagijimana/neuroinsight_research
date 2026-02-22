"""
Execution Backend Module

Factory for creating execution backends based on configuration.

Supported backends:
  - local / local_docker: Run Docker containers on the local machine
  - remote_docker: Run Docker containers on any SSH-accessible server (EC2, VMs, etc.)
  - slurm: Submit jobs to SLURM scheduler on HPC clusters
"""
import os
from typing import Optional

from backend.core.execution import ExecutionBackend, BackendUnavailableError
from backend.execution.local_backend import LocalDockerBackend
from backend.execution.slurm_backend import SLURMBackend
from backend.execution.remote_docker_backend import RemoteDockerBackend


def create_backend(backend_type: Optional[str] = None, **kwargs) -> ExecutionBackend:
    """Factory function to create appropriate execution backend.

    Args:
        backend_type: Backend type ('local', 'remote_docker', 'slurm').
                     If None, reads from BACKEND_TYPE env var.
        **kwargs: Backend-specific configuration

    Returns:
        ExecutionBackend instance

    Raises:
        ValueError: If backend_type is unknown
        BackendUnavailableError: If backend cannot be initialized
    """
    if backend_type is None:
        backend_type = os.getenv("BACKEND_TYPE", "local")
    backend_type = backend_type.lower().strip()

    if backend_type in ("local", "local_docker"):
        data_dir = kwargs.get("data_dir", os.getenv("DATA_DIR", "./data"))
        max_concurrent_jobs = int(
            kwargs.get("max_concurrent_jobs", os.getenv("MAX_CONCURRENT_JOBS", 2))
        )
        return LocalDockerBackend(
            data_dir=data_dir,
            max_concurrent_jobs=max_concurrent_jobs,
        )

    if backend_type == "remote_docker":
        ssh_host = kwargs.get("ssh_host", os.getenv("REMOTE_HOST", os.getenv("HPC_HOST")))
        ssh_user = kwargs.get("ssh_user", os.getenv("REMOTE_USER", os.getenv("HPC_USER")))
        work_dir = kwargs.get("work_dir", os.getenv("REMOTE_WORK_DIR", "/tmp/neuroinsight"))
        if not ssh_host or not ssh_user:
            raise ValueError(
                "Remote Docker backend requires ssh_host and ssh_user. "
                "Set REMOTE_HOST and REMOTE_USER (or HPC_HOST and HPC_USER) environment variables."
            )
        return RemoteDockerBackend(
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            work_dir=work_dir,
        )

    if backend_type == "slurm":
        ssh_host = kwargs.get("ssh_host", os.getenv("HPC_HOST"))
        ssh_user = kwargs.get("ssh_user", os.getenv("HPC_USER"))
        work_dir = kwargs.get("work_dir", os.getenv("HPC_WORK_DIR", "/scratch"))
        partition = kwargs.get("partition", os.getenv("HPC_PARTITION", "general"))
        account = kwargs.get("account", os.getenv("HPC_ACCOUNT"))
        qos = kwargs.get("qos", os.getenv("HPC_QOS"))
        modules_str = kwargs.get("modules", os.getenv("HPC_MODULES", ""))
        modules = [m.strip() for m in modules_str.split(",") if m.strip()] if modules_str else []
        container_runtime = kwargs.get("container_runtime", os.getenv("HPC_CONTAINER_RUNTIME", "singularity"))
        if not ssh_host or not ssh_user:
            raise ValueError(
                "SLURM backend requires ssh_host and ssh_user. "
                "Set HPC_HOST and HPC_USER environment variables."
            )
        return SLURMBackend(
            ssh_host=ssh_host,
            ssh_user=ssh_user,
            work_dir=work_dir,
            partition=partition,
            account=account,
            qos=qos,
            modules=modules,
            container_runtime=container_runtime,
        )

    raise ValueError(
        f"Unknown backend type: {backend_type}. "
        f"Supported: 'local', 'remote_docker', 'slurm'"
    )


_backend_instance: Optional[ExecutionBackend] = None


def get_backend(reinit: bool = False) -> ExecutionBackend:
    """Get singleton execution backend instance.

    Args:
        reinit: Force reinitialization of backend
    """
    global _backend_instance
    if _backend_instance is None or reinit:
        _backend_instance = create_backend()
    return _backend_instance


__all__ = [
    "ExecutionBackend",
    "LocalDockerBackend",
    "RemoteDockerBackend",
    "SLURMBackend",
    "create_backend",
    "get_backend",
]
