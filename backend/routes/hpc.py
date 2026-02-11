"""
Remote & HPC API Routes

Endpoints for managing SSH connections to any remote server (EC2, cloud VMs,
HPC clusters), backend switching (local / remote_docker / slurm), SLURM
partitions, queue info, remote file browsing, and system info.
"""
import logging
from pathlib import PurePosixPath
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/hpc", tags=["hpc"])


def _audit(event: str, **details):
    """Helper to record audit events."""
    try:
        from backend.core.audit import audit_log
        audit_log.record(event, **details)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SSHConnectRequest(BaseModel):
    """SSH connection request."""
    host: str
    username: str
    port: int = 22
    key_path: Optional[str] = None


class SSHConnectResponse(BaseModel):
    """SSH connection response."""
    connected: bool
    message: str
    host: Optional[str] = None
    username: Optional[str] = None


class BackendSwitchRequest(BaseModel):
    """Backend switch request."""
    backend_type: str  # 'local', 'remote_docker', or 'slurm'
    # HPC-specific fields (required when backend_type == 'slurm')
    ssh_host: Optional[str] = None
    ssh_user: Optional[str] = None
    ssh_port: int = 22
    work_dir: str = "/scratch"
    partition: str = "general"
    account: Optional[str] = None
    qos: Optional[str] = None
    modules: Optional[str] = None  # comma-separated


# ---------------------------------------------------------------------------
# SSH Connection Management
# ---------------------------------------------------------------------------

@router.post("/connect", response_model=SSHConnectResponse)
def ssh_connect(request: SSHConnectRequest):
    """Test and establish SSH connection to HPC cluster.

    Uses SSH agent authentication by default. Specify key_path
    for explicit key file authentication.
    """
    from backend.core.ssh_manager import get_ssh_manager, SSHConnectionError

    ssh = get_ssh_manager()
    ssh.configure(
        host=request.host,
        username=request.username,
        port=request.port,
        key_path=request.key_path,
    )

    try:
        ssh.connect()

        # Verify with a quick command
        exit_code, stdout, _ = ssh.execute("hostname", timeout=10)
        remote_hostname = stdout.strip() if exit_code == 0 else request.host

        _audit("ssh_connected", host=request.host, username=request.username)
        return SSHConnectResponse(
            connected=True,
            message=f"Connected to {remote_hostname}",
            host=request.host,
            username=request.username,
        )
    except SSHConnectionError as e:
        return SSHConnectResponse(
            connected=False,
            message=str(e),
            host=request.host,
            username=request.username,
        )


@router.post("/disconnect")
def ssh_disconnect():
    """Disconnect SSH connection."""
    from backend.core.ssh_manager import get_ssh_manager

    ssh = get_ssh_manager()
    ssh.disconnect()
    _audit("ssh_disconnected")
    return {"message": "Disconnected", "connected": False}


@router.get("/status")
def ssh_status():
    """Get current SSH connection status and details."""
    from backend.core.ssh_manager import get_ssh_manager

    ssh = get_ssh_manager()
    info = ssh.connection_info
    return {
        "connected": info["connected"],
        "host": info["host"],
        "username": info["username"],
        "port": info["port"],
        "uptime_seconds": info["uptime_seconds"],
    }


@router.get("/health")
def hpc_health():
    """Full HPC health check: SSH + SLURM + container runtime."""
    from backend.core.ssh_manager import get_ssh_manager

    ssh = get_ssh_manager()
    if not ssh.is_connected:
        return {
            "healthy": False,
            "message": "SSH not connected",
            "details": {"ssh_connected": False},
        }

    # Try to check via SLURM backend health
    try:
        from backend.execution import get_backend
        backend = get_backend()
        if backend.backend_type == "slurm":
            return backend.health_check()
    except Exception:
        pass

    # Fallback: basic SSH health check
    return ssh.health_check()


# ---------------------------------------------------------------------------
# Backend Switcher
# ---------------------------------------------------------------------------

@router.post("/backend/switch")
def switch_backend(request: BackendSwitchRequest):
    """Switch between execution backends.

    Supported backends:
      - 'local': Docker on the local machine
      - 'remote_docker': Docker on any SSH-accessible server (EC2, cloud VMs)
      - 'slurm': SLURM scheduler on HPC clusters

    When switching to a remote backend, SSH connection is established first.
    """
    import os
    from backend.execution import get_backend, create_backend

    valid_types = ("local", "remote_docker", "slurm")
    if request.backend_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid backend_type: {request.backend_type}. Must be one of: {', '.join(valid_types)}",
        )

    # Remote backends require SSH credentials
    if request.backend_type in ("remote_docker", "slurm"):
        if not request.ssh_host or not request.ssh_user:
            raise HTTPException(
                status_code=400,
                detail="ssh_host and ssh_user are required for remote backends.",
            )

        # Establish SSH connection first
        from backend.core.ssh_manager import get_ssh_manager, SSHConnectionError
        ssh = get_ssh_manager()
        ssh.configure(host=request.ssh_host, username=request.ssh_user, port=request.ssh_port)
        try:
            ssh.connect()
        except SSHConnectionError as e:
            raise HTTPException(status_code=503, detail=f"SSH connection failed: {e}")

    # Update environment
    os.environ["BACKEND_TYPE"] = request.backend_type
    if request.backend_type in ("remote_docker", "slurm"):
        os.environ["HPC_HOST"] = request.ssh_host
        os.environ["HPC_USER"] = request.ssh_user
        os.environ["HPC_WORK_DIR"] = request.work_dir
        if request.backend_type == "slurm":
            os.environ["HPC_PARTITION"] = request.partition
            if request.account:
                os.environ["HPC_ACCOUNT"] = request.account
            if request.qos:
                os.environ["HPC_QOS"] = request.qos

    # Force backend re-creation
    import backend.execution as exec_module
    try:
        if request.backend_type == "slurm":
            modules = [m.strip() for m in request.modules.split(",") if m.strip()] if request.modules else []
            from backend.execution.slurm_backend import SLURMBackend
            new_backend = SLURMBackend(
                ssh_host=request.ssh_host,
                ssh_user=request.ssh_user,
                work_dir=request.work_dir,
                partition=request.partition,
                account=request.account,
                qos=request.qos,
                modules=modules,
            )
        elif request.backend_type == "remote_docker":
            from backend.execution.remote_docker_backend import RemoteDockerBackend
            new_backend = RemoteDockerBackend(
                ssh_host=request.ssh_host,
                ssh_user=request.ssh_user,
                work_dir=request.work_dir or "/tmp/neuroinsight",
            )
        else:
            from backend.execution.local_backend import LocalDockerBackend
            new_backend = LocalDockerBackend()

        exec_module._backend_instance = new_backend
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backend initialization failed: {e}")

    # Health check on new backend
    try:
        health = new_backend.health_check()
    except Exception as e:
        health = {"healthy": False, "message": str(e)}

    _audit("backend_switched", backend_type=request.backend_type,
           host=request.ssh_host, user=request.ssh_user)
    return {
        "backend_type": request.backend_type,
        "message": f"Switched to {request.backend_type} backend",
        "health": health,
    }


@router.get("/backend/current")
def get_current_backend():
    """Get current backend type and status."""
    try:
        from backend.execution import get_backend
        backend = get_backend()
        return {
            "backend_type": backend.backend_type,
            "healthy": True,
            "details": backend.health_check(),
        }
    except Exception as e:
        import os
        return {
            "backend_type": os.getenv("BACKEND_TYPE", "local"),
            "healthy": False,
            "error": str(e),
        }


@router.get("/system-info")
def get_remote_system_info():
    """Get system information from the connected remote server.

    Returns CPU, memory, GPU, OS, Docker info for the remote machine.
    Works with any SSH-connected server (EC2, cloud VMs, HPC).
    """
    from backend.execution import get_backend
    backend = get_backend()

    if backend.backend_type == "remote_docker":
        return backend.get_system_info()
    elif backend.backend_type == "slurm":
        # For SLURM, return basic info via SSH
        from backend.core.ssh_manager import get_ssh_manager
        ssh = get_ssh_manager()
        if not ssh.is_connected:
            raise HTTPException(status_code=503, detail="SSH not connected")
        info = {"host": ssh.host, "user": ssh.username, "type": "slurm"}
        try:
            _, os_out, _ = ssh.execute("cat /etc/os-release 2>/dev/null | head -2", timeout=5)
            for line in os_out.strip().split("\n"):
                if line.startswith("PRETTY_NAME="):
                    info["os"] = line.split("=", 1)[1].strip('"')
            _, cpu_out, _ = ssh.execute("nproc", timeout=5)
            info["cpu_count"] = int(cpu_out.strip()) if cpu_out.strip().isdigit() else 0
            _, mem_out, _ = ssh.execute("free -g | awk '/^Mem:/{print $2}'", timeout=5)
            info["memory_gb"] = int(mem_out.strip()) if mem_out.strip().isdigit() else 0
        except Exception:
            pass
        return info
    else:
        raise HTTPException(status_code=400, detail="System info only available for remote backends")


# ---------------------------------------------------------------------------
# SLURM Cluster Info
# ---------------------------------------------------------------------------

@router.get("/partitions")
def list_partitions():
    """List available SLURM partitions with resource details."""
    from backend.execution import get_backend
    backend = get_backend()

    if backend.backend_type != "slurm":
        raise HTTPException(status_code=400, detail="Not using SLURM backend")

    partitions = backend.get_partitions()
    return {"partitions": partitions, "total": len(partitions)}


@router.get("/queue")
def get_queue(user_only: bool = True):
    """Get SLURM queue information."""
    from backend.execution import get_backend
    backend = get_backend()

    if backend.backend_type != "slurm":
        raise HTTPException(status_code=400, detail="Not using SLURM backend")

    jobs = backend.get_queue_info(user_only=user_only)
    return {"queue": jobs, "total": len(jobs)}


@router.get("/resource-presets")
def get_resource_presets(partition: Optional[str] = None):
    """Get resource presets tailored to HPC partition capabilities.

    Returns recommended resource profiles per partition based on
    actual partition limits (memory, CPUs, GPUs, time).
    """
    from backend.execution import get_backend
    backend = get_backend()

    if backend.backend_type != "slurm":
        raise HTTPException(status_code=400, detail="Not using SLURM backend")

    partitions = backend.get_partitions()
    presets = []

    for p in partitions:
        if partition and p["name"] != partition:
            continue

        # Parse partition resources
        name = p["name"]
        timelimit = p.get("timelimit", "infinite")
        mem_str = p.get("memory_mb", "0")
        cpus_str = p.get("cpus", "0/0/0/0")
        gpus_str = p.get("gpus", "(null)")

        # Parse max memory from partition (MB -> GB)
        try:
            max_mem_gb = int(mem_str) // 1024 if mem_str.isdigit() else 128
        except (ValueError, TypeError):
            max_mem_gb = 128

        # Parse total CPUs from A/I/O/T format
        try:
            total_cpus = int(cpus_str.split("/")[-1]) if "/" in cpus_str else 64
        except (ValueError, IndexError):
            total_cpus = 64

        # Parse time limit to hours
        max_hours = 168  # default 7 days
        if timelimit and timelimit != "infinite":
            try:
                parts = timelimit.split("-")
                if len(parts) == 2:
                    max_hours = int(parts[0]) * 24 + int(parts[1].split(":")[0])
                else:
                    time_parts = timelimit.split(":")
                    max_hours = int(time_parts[0])
            except (ValueError, IndexError):
                pass

        has_gpu = gpus_str not in ("(null)", "", "0")

        # Build presets for this partition
        preset = {
            "partition": name,
            "max_memory_gb": max_mem_gb,
            "max_cpus": total_cpus,
            "max_time_hours": max_hours,
            "has_gpu": has_gpu,
            "profiles": {
                "small": {
                    "label": "Small (quick test)",
                    "cpus": min(4, total_cpus),
                    "memory_gb": min(8, max_mem_gb),
                    "time_hours": min(2, max_hours),
                    "gpu": False,
                },
                "medium": {
                    "label": "Medium (standard job)",
                    "cpus": min(8, total_cpus),
                    "memory_gb": min(32, max_mem_gb),
                    "time_hours": min(8, max_hours),
                    "gpu": has_gpu,
                },
                "large": {
                    "label": "Large (production run)",
                    "cpus": min(16, total_cpus),
                    "memory_gb": min(64, max_mem_gb),
                    "time_hours": min(24, max_hours),
                    "gpu": has_gpu,
                },
                "max": {
                    "label": "Maximum (full partition)",
                    "cpus": total_cpus,
                    "memory_gb": max_mem_gb,
                    "time_hours": max_hours,
                    "gpu": has_gpu,
                },
            },
        }
        presets.append(preset)

    return {"presets": presets, "total": len(presets)}


@router.get("/accounts")
def get_accounts():
    """Get user's SLURM account/allocation info."""
    from backend.execution import get_backend
    backend = get_backend()

    if backend.backend_type != "slurm":
        raise HTTPException(status_code=400, detail="Not using SLURM backend")

    return backend.get_account_info()


# ---------------------------------------------------------------------------
# Remote File Browsing
# ---------------------------------------------------------------------------

@router.get("/browse")
def browse_remote(path: str = "~"):
    """Browse remote HPC filesystem via SSH/SFTP.

    Args:
        path: Remote directory path (~ expands to home directory)
    """
    from backend.core.ssh_manager import get_ssh_manager

    ssh = get_ssh_manager()
    if not ssh.is_connected:
        raise HTTPException(status_code=503, detail="SSH not connected")

    # Expand ~ to home directory
    if path.startswith("~"):
        try:
            _, home_dir, _ = ssh.execute("echo $HOME", timeout=5)
            home = home_dir.strip()
            path = path.replace("~", home, 1)
        except Exception:
            pass

    try:
        entries = ssh.list_dir(path)

        # Separate into directories and files, identify NIfTI files
        directories = [e for e in entries if e["type"] == "directory"]
        files = [e for e in entries if e["type"] == "file"]
        nifti_files = [e for e in files if e["name"].endswith((".nii", ".nii.gz"))]

        parent = str(PurePosixPath(path).parent)

        return {
            "path": path,
            "parent": parent,
            "directories": directories,
            "files": files,
            "nifti_files": nifti_files,
            "total_files": len(files),
            "total_directories": len(directories),
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to browse: {e}")


@router.get("/file/download")
def download_remote_file(remote_path: str):
    """Download a file from the HPC to local temp and serve it."""
    import tempfile
    from fastapi.responses import FileResponse
    from backend.core.ssh_manager import get_ssh_manager

    ssh = get_ssh_manager()
    if not ssh.is_connected:
        raise HTTPException(status_code=503, detail="SSH not connected")

    filename = PurePosixPath(remote_path).name

    try:
        # Download to temp file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{filename}")
        ssh.get_file(remote_path, tmp.name)
        _audit("file_downloaded", remote_path=remote_path, filename=filename)
        return FileResponse(tmp.name, filename=filename, media_type="application/octet-stream")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {remote_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {e}")


@router.get("/file/stream-nifti")
def stream_nifti_from_hpc(remote_path: str):
    """Stream a NIfTI file from HPC for the Niivue viewer.

    Downloads the file via SFTP to a local temp cache, then serves it
    with the correct content type for Niivue to load directly.
    """
    import tempfile
    import hashlib
    from pathlib import Path as LocalPath
    from fastapi.responses import FileResponse
    from backend.core.ssh_manager import get_ssh_manager

    ssh = get_ssh_manager()
    if not ssh.is_connected:
        raise HTTPException(status_code=503, detail="SSH not connected")

    filename = PurePosixPath(remote_path).name
    if not filename.endswith((".nii", ".nii.gz", ".mgz", ".mgh")):
        raise HTTPException(status_code=400, detail="Not a viewable neuroimaging file")

    # Use a cache directory so repeated requests don't re-download
    cache_dir = LocalPath("./data/.nifti_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Cache key based on remote path
    path_hash = hashlib.md5(remote_path.encode()).hexdigest()[:12]
    cache_path = cache_dir / f"{path_hash}_{filename}"

    if not cache_path.exists():
        try:
            ssh.get_file(remote_path, str(cache_path))
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"File not found: {remote_path}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Download failed: {e}")

    # Determine content type
    content_type = "application/octet-stream"
    if filename.endswith(".nii.gz"):
        content_type = "application/gzip"
    elif filename.endswith(".nii"):
        content_type = "application/octet-stream"

    return FileResponse(
        str(cache_path),
        filename=filename,
        media_type=content_type,
        headers={"Access-Control-Allow-Origin": "*"},
    )
