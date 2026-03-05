"""
Results endpoints for serving real job output files.

All endpoints read from the actual output directory -- no mock/placeholder data.
If a job has no results yet, endpoints return 404.

Supports both local output directories and remote HPC paths accessed via SSH.
"""
import hashlib
import json
import logging
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/results", tags=["results"])
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
#  Output directory resolution (local vs remote/HPC)                           #
# --------------------------------------------------------------------------- #

@dataclass
class _OutputLocation:
    """Encapsulates where a job's output lives: local path or remote via SSH."""
    local_path: Optional[Path] = None
    remote_path: Optional[str] = None

    @property
    def is_remote(self) -> bool:
        return self.remote_path is not None and self.local_path is None

    @property
    def exists(self) -> bool:
        return self.local_path is not None or self.remote_path is not None


def _get_ssh():
    """Get a connected SSH manager, auto-reconnecting if possible.

    Tries in order:
    1. Existing SLURM backend (calls _ensure_ssh which reconnects if configured)
    2. Global SSH manager if already connected
    3. Auto-reconnect from persisted HPC config
    """
    # 1. Try via SLURM backend
    try:
        from backend.execution import get_backend
        backend = get_backend()
        if backend.backend_type == "slurm":
            backend._ensure_ssh()
            return backend._ssh
    except Exception as e:
        logger.debug("Could not get SSH via SLURM backend: %s", e)

    # 2. Try global SSH manager
    try:
        from backend.core.ssh_manager import get_ssh_manager
        ssh = get_ssh_manager()
        if ssh.is_connected:
            return ssh
    except Exception:
        pass

    # 3. Auto-reconnect from persisted config
    try:
        from backend.core.hpc_config_store import load_hpc_config
        cfg = load_hpc_config()
        if cfg:
            from backend.core.ssh_manager import get_ssh_manager, SSHConnectionError
            ssh = get_ssh_manager()
            if not ssh.is_connected:
                ssh.configure(
                    host=cfg["ssh_host"],
                    username=cfg["ssh_user"],
                    port=cfg.get("ssh_port", 22),
                )
                ssh.connect()
                logger.info(
                    "Auto-reconnected SSH to %s@%s:%s from persisted config",
                    cfg["ssh_user"], cfg["ssh_host"], cfg.get("ssh_port", 22),
                )

                # Also restore the SLURM backend if needed
                if cfg.get("backend_type") == "slurm":
                    _restore_slurm_backend(cfg)

                return ssh
    except Exception as e:
        logger.debug("Auto-reconnect from persisted config failed: %s", e)

    return None


def _restore_slurm_backend(cfg: dict) -> None:
    """Restore the SLURM backend from persisted config."""
    try:
        import os
        import backend.execution as exec_module
        from backend.execution.slurm_backend import SLURMBackend

        current = getattr(exec_module, "_backend_instance", None)
        if current and getattr(current, "backend_type", None) == "slurm":
            return

        modules_str = cfg.get("modules", "")
        modules = [m.strip() for m in modules_str.split(",") if m.strip()] if modules_str else []

        os.environ["BACKEND_TYPE"] = "slurm"
        os.environ["HPC_HOST"] = cfg["ssh_host"]
        os.environ["HPC_USER"] = cfg["ssh_user"]
        os.environ["HPC_WORK_DIR"] = cfg.get("work_dir", "~")
        os.environ["HPC_PARTITION"] = cfg.get("partition", "general")

        backend = SLURMBackend(
            ssh_host=cfg["ssh_host"],
            ssh_user=cfg["ssh_user"],
            ssh_port=cfg.get("ssh_port", 22),
            work_dir=cfg.get("work_dir", "~"),
            partition=cfg.get("partition", "general"),
            account=cfg.get("account"),
            qos=cfg.get("qos"),
            modules=modules,
        )
        exec_module._backend_instance = backend
        logger.info("SLURM backend restored from persisted config")
    except Exception as e:
        logger.warning("Could not restore SLURM backend: %s", e)


def _resolve_output(job_id: str) -> _OutputLocation:
    """Resolve a job's output directory, checking local paths and the DB."""
    from backend.core.config import get_settings

    # Check DB for the job's actual output_dir (SLURM jobs store the HPC path)
    db_output_dir: Optional[str] = None
    backend_type: Optional[str] = None
    try:
        from backend.core.database import get_db_context
        from backend.models.job import Job

        with get_db_context() as db:
            job = db.query(Job).filter_by(id=job_id).first()
            if job and job.output_dir:
                db_output_dir = job.output_dir
                backend_type = job.backend_type
    except Exception as e:
        logger.debug("Could not query job %s from DB: %s", job_id[:8], e)

    # If we got a DB path, check local first, then try remote
    if db_output_dir:
        local = Path(db_output_dir)
        if local.exists():
            return _OutputLocation(local_path=local)

        # For SLURM jobs, the path is on HPC -- verify via SSH
        if backend_type == "slurm":
            ssh = _get_ssh()
            if ssh:
                try:
                    exit_code, _, _ = ssh.execute(
                        f"test -d {db_output_dir!r}", timeout=10,
                    )
                    if exit_code == 0:
                        return _OutputLocation(remote_path=db_output_dir)
                except Exception as e:
                    logger.debug("SSH check for %s failed: %s", db_output_dir, e)

    # Fallback: local settings-based paths
    settings = get_settings()
    for candidate in (
        Path(settings.data_dir) / "outputs" / job_id,
        Path(settings.output_dir) / job_id,
    ):
        if candidate.exists():
            return _OutputLocation(local_path=candidate)

    return _OutputLocation()


# --------------------------------------------------------------------------- #
#  Remote file helpers (SSH/SFTP)                                              #
# --------------------------------------------------------------------------- #

def _remote_list_files(ssh, remote_dir: str) -> list[dict]:
    """List all files recursively in a remote directory via SSH."""
    cmd = (
        f"find {remote_dir!r} -type f -not -path '*/_inputs/*' "
        f"-printf '%P\\t%s\\n' 2>/dev/null"
    )
    exit_code, stdout, _ = ssh.execute(cmd, timeout=30)
    if exit_code != 0:
        return []

    files = []
    for line in stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        rel_path, size_str = parts
        try:
            size = int(size_str)
        except ValueError:
            size = 0
        files.append({"rel_path": rel_path, "size": size})
    return files


def _remote_find_files(ssh, remote_dir: str, patterns: list[str]) -> list[dict]:
    """Find files matching name patterns in a remote directory."""
    all_files = _remote_list_files(ssh, remote_dir)
    results = []
    for f in all_files:
        lower = f["rel_path"].lower()
        name = PurePosixPath(f["rel_path"]).name.lower()
        for pat in patterns:
            if pat in name:
                results.append(f)
                break
    return results


def _remote_download_to_temp(ssh, remote_path: str, suffix: str = "") -> str:
    """Download a remote file to a local temp file, return local path."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.close()
    ssh.get_file(remote_path, tmp.name)
    return tmp.name


def _remote_read_text(ssh, remote_path: str) -> str:
    """Read the text content of a remote file via SSH."""
    exit_code, stdout, _ = ssh.execute(f"cat {remote_path!r}", timeout=15)
    if exit_code != 0:
        raise FileNotFoundError(f"Cannot read remote file: {remote_path}")
    return stdout


# --------------------------------------------------------------------------- #
#  Shared helpers                                                              #
# --------------------------------------------------------------------------- #

def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def _classify_file(name: str) -> str:
    """Classify a file by its extension."""
    lower = name.lower()
    if lower.endswith((".nii", ".nii.gz", ".mgz", ".mgh")):
        return "volume"
    elif lower.endswith((".json",)):
        return "metadata"
    elif lower.endswith((".csv", ".tsv", ".stats")):
        return "metrics"
    elif lower.endswith((".png", ".jpg", ".jpeg", ".svg")):
        return "image"
    elif lower.endswith((".html",)):
        return "report"
    elif lower.endswith((".log", ".txt")):
        return "log"
    return "file"


def _media_type_for(filename: str) -> str:
    """Determine media type for a filename."""
    lower = filename.lower()
    if lower.endswith(".json"):
        return "application/json"
    elif lower.endswith(".csv"):
        return "text/csv"
    elif lower.endswith(".tsv"):
        return "text/tab-separated-values"
    elif lower.endswith(".html"):
        return "text/html"
    elif lower.endswith(".png"):
        return "image/png"
    elif lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    elif lower.endswith(".svg"):
        return "image/svg+xml"
    elif lower.endswith((".txt", ".log")):
        return "text/plain"
    elif lower.endswith(".nii.gz"):
        return "application/gzip"
    return "application/octet-stream"


def _ensure_output(job_id: str) -> _OutputLocation:
    """Resolve output and raise 404 if not found."""
    loc = _resolve_output(job_id)
    if not loc.exists:
        raise HTTPException(
            status_code=404,
            detail=f"No output directory for job {job_id}. "
                   f"Job may still be running or has no results.",
        )
    return loc


# --------------------------------------------------------------------------- #
#  File listing                                                                #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/files")
async def list_job_files(job_id: str):
    """List all output files for a completed job."""
    loc = _ensure_output(job_id)

    if loc.is_remote:
        ssh = _get_ssh()
        if not ssh:
            raise HTTPException(status_code=503, detail="SSH not connected")
        raw = _remote_list_files(ssh, loc.remote_path)
        files = []
        for f in sorted(raw, key=lambda x: x["rel_path"]):
            name = PurePosixPath(f["rel_path"]).name
            files.append({
                "name": f["rel_path"],
                "type": _classify_file(name),
                "path": f"/api/results/{job_id}/download?file_path={f['rel_path']}",
                "size": _format_size(f["size"]),
                "size_bytes": f["size"],
            })
        return {"job_id": job_id, "files": files, "total": len(files)}

    # Local path
    output_dir = loc.local_path
    files = []
    for file_path in sorted(output_dir.rglob("*")):
        if file_path.is_file():
            rel = file_path.relative_to(output_dir)
            if str(rel).startswith("_inputs"):
                continue
            size = file_path.stat().st_size
            files.append({
                "name": str(rel),
                "type": _classify_file(file_path.name),
                "path": f"/api/results/{job_id}/download?file_path={rel}",
                "size": _format_size(size),
                "size_bytes": size,
            })

    return {"job_id": job_id, "files": files, "total": len(files)}


# --------------------------------------------------------------------------- #
#  Volume / Segmentation discovery                                             #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/volume")
async def get_volume(job_id: str):
    """Find the main anatomical volume(s) in job output."""
    loc = _ensure_output(job_id)

    volume_patterns = [
        "norm.nii", "norm.mgz", "t1w.nii", "t1.nii", "brain.nii", "brain.mgz",
        "anatomy.nii", "orig.nii", "orig.mgz", "nu.mgz",
    ]
    fallback_patterns = [".nii.gz", ".nii", ".mgz"]

    if loc.is_remote:
        ssh = _get_ssh()
        if not ssh:
            raise HTTPException(status_code=503, detail="SSH not connected")
        raw = _remote_find_files(ssh, loc.remote_path, volume_patterns)
        if not raw:
            raw = _remote_find_files(ssh, loc.remote_path, fallback_patterns)
        volumes = [{
            "name": f["rel_path"],
            "path": f"/api/results/{job_id}/download?file_path={f['rel_path']}",
            "size": _format_size(f["size"]),
        } for f in raw]
        return {"job_id": job_id, "volumes": volumes}

    # Local
    output_dir = loc.local_path
    volumes = _find_files_local(output_dir, job_id, volume_patterns)
    if not volumes:
        volumes = _find_files_local(output_dir, job_id, fallback_patterns)
    return {"job_id": job_id, "volumes": volumes}


@router.get("/{job_id}/segmentation")
async def get_segmentation(job_id: str):
    """Find segmentation overlays in job output."""
    loc = _ensure_output(job_id)

    seg_patterns = [
        "hippo_labels", "hippo",
        "aseg.nii", "aseg.mgz", "aparc", "segmentation.nii",
        "labels.nii", "dseg.nii", "wmparc.mgz",
    ]

    if loc.is_remote:
        ssh = _get_ssh()
        if not ssh:
            raise HTTPException(status_code=503, detail="SSH not connected")
        raw = _remote_find_files(ssh, loc.remote_path, seg_patterns)
        segs = [{
            "name": f["rel_path"],
            "path": f"/api/results/{job_id}/download?file_path={f['rel_path']}",
            "size": _format_size(f["size"]),
        } for f in raw]
        return {"job_id": job_id, "segmentations": segs}

    output_dir = loc.local_path
    segs = _find_files_local(output_dir, job_id, seg_patterns)
    return {"job_id": job_id, "segmentations": segs}


def _find_files_local(output_dir: Path, job_id: str, patterns: list[str]) -> list[dict]:
    """Find files matching name patterns in a local output dir."""
    results = []
    for f in output_dir.rglob("*"):
        if not f.is_file():
            continue
        lower = f.name.lower()
        rel = f.relative_to(output_dir)
        for pat in patterns:
            if pat in lower:
                results.append({
                    "name": str(rel),
                    "path": f"/api/results/{job_id}/download?file_path={rel}",
                    "size": _format_size(f.stat().st_size),
                })
                break
    return results


# --------------------------------------------------------------------------- #
#  Labels / Metrics                                                            #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/labels")
async def get_labels(job_id: str):
    """Read label definitions from job output."""
    loc = _ensure_output(job_id)

    if loc.is_remote:
        ssh = _get_ssh()
        if not ssh:
            raise HTTPException(status_code=503, detail="SSH not connected")
        # Search for labels JSON
        label_files = _remote_find_files(ssh, loc.remote_path, ["labels.json"])
        for lf in label_files:
            try:
                content = _remote_read_text(
                    ssh, f"{loc.remote_path}/{lf['rel_path']}"
                )
                return {
                    "job_id": job_id,
                    "labels": json.loads(content),
                    "source": PurePosixPath(lf["rel_path"]).name,
                }
            except Exception as e:
                logger.debug("Could not parse remote label file %s: %s",
                             lf["rel_path"], e)
        # Try ColorLUT
        lut_files = _remote_find_files(ssh, loc.remote_path, ["colorlut"])
        for lf in lut_files:
            try:
                content = _remote_read_text(
                    ssh, f"{loc.remote_path}/{lf['rel_path']}"
                )
                labels = _parse_color_lut_text(content)
                return {
                    "job_id": job_id,
                    "labels": labels,
                    "source": PurePosixPath(lf["rel_path"]).name,
                }
            except Exception as e:
                logger.debug("Could not parse remote ColorLUT %s: %s",
                             lf["rel_path"], e)
        raise HTTPException(status_code=404,
                            detail="No label definitions found in job output")

    # Local
    output_dir = loc.local_path
    for f in output_dir.rglob("*labels*.json"):
        try:
            return {
                "job_id": job_id,
                "labels": json.loads(f.read_text()),
                "source": str(f.name),
            }
        except Exception as e:
            logger.debug("Could not parse label file %s: %s", f.name, e)
    for f in output_dir.rglob("*ColorLUT*"):
        try:
            labels = _parse_color_lut(f)
            return {"job_id": job_id, "labels": labels, "source": str(f.name)}
        except Exception as e:
            logger.debug("Could not parse ColorLUT file %s: %s", f.name, e)
    raise HTTPException(status_code=404,
                        detail="No label definitions found in job output")


@router.get("/{job_id}/metrics")
async def get_metrics(job_id: str):
    """Read quantitative metrics from job output."""
    loc = _ensure_output(job_id)

    if loc.is_remote:
        return await _get_metrics_remote(job_id, loc.remote_path)

    return _get_metrics_local(job_id, loc.local_path)


async def _get_metrics_remote(job_id: str, remote_dir: str) -> dict:
    ssh = _get_ssh()
    if not ssh:
        raise HTTPException(status_code=503, detail="SSH not connected")

    metrics: dict[str, Any] = {}
    sources: list[str] = []

    all_files = _remote_list_files(ssh, remote_dir)

    # JSON metrics files
    json_metrics = [
        f for f in all_files
        if f["rel_path"].lower().endswith(".json")
        and any(kw in PurePosixPath(f["rel_path"]).name.lower()
                for kw in ("metrics", "stats", "summary"))
    ]
    for f in json_metrics:
        try:
            content = _remote_read_text(
                ssh, f"{remote_dir}/{f['rel_path']}"
            )
            stem = PurePosixPath(f["rel_path"]).stem
            metrics[stem] = json.loads(content)
            sources.append(f["rel_path"])
        except Exception as e:
            logger.debug("Could not parse remote JSON metrics %s: %s",
                         f["rel_path"], e)

    # FreeSurfer .stats files -- batch-read in a single SSH call
    stats_files = [
        f["rel_path"] for f in all_files
        if f["rel_path"].lower().endswith(".stats")
    ]
    if stats_files:
        _DELIM = "===NEUROINSIGHT_FILE_BOUNDARY==="
        paths_str = " ".join(
            f"{remote_dir}/{p}" for p in stats_files
        )
        cmd = (
            f"for f in {paths_str}; do "
            f"echo '{_DELIM}'\"$f\"; cat \"$f\" 2>/dev/null; "
            f"done"
        )
        exit_code, stdout, _ = ssh.execute(cmd, timeout=60)
        if exit_code == 0 and stdout.strip():
            chunks = stdout.split(_DELIM)
            for chunk in chunks:
                if not chunk.strip():
                    continue
                lines = chunk.strip().split("\n", 1)
                file_path = lines[0].strip()
                content = lines[1] if len(lines) > 1 else ""
                try:
                    parsed = _parse_stats_text(content)
                    if parsed:
                        rel = file_path.replace(remote_dir + "/", "", 1)
                        stem = PurePosixPath(rel).stem
                        metrics[stem] = parsed
                        sources.append(rel)
                except Exception as e:
                    logger.debug("Could not parse stats chunk %s: %s",
                                 file_path, e)

    # CSV/TSV files
    csv_files = [
        f["rel_path"] for f in all_files
        if f["rel_path"].lower().endswith((".csv", ".tsv"))
    ]

    if not metrics and not csv_files:
        raise HTTPException(status_code=404,
                            detail="No metrics found in job output")

    return {
        "job_id": job_id,
        "metrics": metrics,
        "csv_files": csv_files,
        "sources": sources,
    }


def _get_metrics_local(job_id: str, output_dir: Path) -> dict:
    metrics: dict[str, Any] = {}
    sources: list[str] = []

    for pattern in [
        "**/metrics*.json", "**/stats*.json",
        "**/summary*.json", "**/*_stats.json",
    ]:
        for f in output_dir.glob(pattern):
            try:
                data = json.loads(f.read_text())
                metrics[f.stem] = data
                sources.append(str(f.relative_to(output_dir)))
            except Exception as e:
                logger.debug("Could not parse JSON metrics %s: %s", f.name, e)

    for f in output_dir.rglob("*.stats"):
        try:
            parsed = _parse_stats_file(f)
            if parsed:
                metrics[f.stem] = parsed
                sources.append(str(f.relative_to(output_dir)))
        except Exception as e:
            logger.debug("Could not parse stats file %s: %s", f.name, e)

    csv_files = [
        str(f.relative_to(output_dir))
        for f in output_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in (".csv", ".tsv")
    ]

    if not metrics and not csv_files:
        raise HTTPException(status_code=404,
                            detail="No metrics found in job output")

    return {
        "job_id": job_id,
        "metrics": metrics,
        "csv_files": csv_files,
        "sources": sources,
    }


# --------------------------------------------------------------------------- #
#  Stats-to-CSV (plugin-aware structured CSVs)                                 #
# --------------------------------------------------------------------------- #

def _build_file_provider(loc: "_OutputLocation"):
    """Create a FileProvider for the stats converter from an _OutputLocation."""
    from backend.services.stats_converter import FileProvider

    if loc.is_remote:
        ssh = _get_ssh()
        if not ssh:
            raise HTTPException(status_code=503, detail="SSH not connected")
        return FileProvider(remote_dir=loc.remote_path, ssh=ssh)
    return FileProvider(local_dir=str(loc.local_path))


def _get_pipeline_name(job_id: str) -> str:
    """Resolve a job's pipeline_name from the database."""
    try:
        from backend.core.database import get_db_context
        from backend.models.job import Job

        with get_db_context() as db:
            job = db.query(Job).filter_by(id=job_id).first()
            if job:
                return job.pipeline_name
    except Exception as e:
        logger.debug("Could not get pipeline_name for %s: %s", job_id[:8], e)
    return ""


def _load_pregenerated_csvs(loc: "_OutputLocation") -> list:
    """Check for pre-generated CSVs in bundle/csv/ (from post-job processing)."""
    import csv as csv_mod
    from backend.services.stats_converter import CSVSheet

    sheets: list[CSVSheet] = []
    csv_dir_candidates = ["bundle/csv", "csv"]

    if loc.is_remote:
        ssh = _get_ssh()
        if not ssh:
            return []
        for cand in csv_dir_candidates:
            full = f"{loc.remote_path}/{cand}"
            exit_code, stdout, _ = ssh.execute(
                f"ls {full!r}/*.csv 2>/dev/null", timeout=10,
            )
            if exit_code != 0 or not stdout.strip():
                continue
            for line in stdout.strip().split("\n"):
                fname = PurePosixPath(line.strip()).name
                try:
                    ec2, content, _ = ssh.execute(
                        f"cat {line.strip()!r}", timeout=15,
                    )
                    if ec2 == 0 and content.strip():
                        reader = csv_mod.reader(content.strip().splitlines())
                        rows_list = list(reader)
                        if len(rows_list) > 1:
                            sheets.append(CSVSheet(
                                name=fname.replace(".csv", "").replace("_", " ").title(),
                                filename=fname,
                                description="Pre-generated statistics",
                                headers=rows_list[0],
                                rows=[[_try_float(v) for v in r] for r in rows_list[1:]],
                                category="general",
                            ))
                except Exception:
                    continue
            if sheets:
                return sheets
    else:
        for cand in csv_dir_candidates:
            csv_dir = loc.local_path / cand
            if not csv_dir.is_dir():
                continue
            for csv_file in sorted(csv_dir.glob("*.csv")):
                try:
                    with open(csv_file, newline="", encoding="utf-8") as f:
                        reader = csv_mod.reader(f)
                        rows_list = list(reader)
                    if len(rows_list) > 1:
                        sheets.append(CSVSheet(
                            name=csv_file.stem.replace("_", " ").title(),
                            filename=csv_file.name,
                            description="Pre-generated statistics",
                            headers=rows_list[0],
                            rows=[[_try_float(v) for v in r] for r in rows_list[1:]],
                            category="general",
                        ))
                except Exception:
                    continue
            if sheets:
                return sheets
    return sheets


def _try_float(v: str):
    try:
        return float(v)
    except (ValueError, TypeError):
        return v


@router.get("/{job_id}/stats/csv")
async def get_stats_csvs(job_id: str):
    """Generate structured CSV previews from job output, plugin-aware.

    First checks for pre-generated CSVs in bundle/csv/ (fast path),
    then falls back to on-the-fly parsing from raw stats files.
    """
    from backend.services.stats_converter import generate_stats_csvs

    loc = _ensure_output(job_id)
    pipeline_name = _get_pipeline_name(job_id)

    # Fast path: pre-generated CSVs from post-job processing
    sheets = _load_pregenerated_csvs(loc)

    # Fallback: on-the-fly parsing
    if not sheets:
        fp = _build_file_provider(loc)
        sheets = generate_stats_csvs(pipeline_name, fp)

    if not sheets:
        raise HTTPException(
            status_code=404,
            detail="No structured statistics found for this job",
        )

    return {
        "job_id": job_id,
        "pipeline_name": pipeline_name,
        "csv_count": len(sheets),
        "csvs": [s.preview() for s in sheets],
    }


@router.get("/{job_id}/stats/csv/{csv_filename}")
async def download_stats_csv(job_id: str, csv_filename: str):
    """Download a specific generated CSV file.

    Checks pre-generated CSVs first, falls back to on-the-fly generation.
    """
    from backend.services.stats_converter import generate_stats_csvs

    loc = _ensure_output(job_id)
    pipeline_name = _get_pipeline_name(job_id)

    # Try pre-generated first
    sheets = _load_pregenerated_csvs(loc)
    if not sheets:
        fp = _build_file_provider(loc)
        sheets = generate_stats_csvs(pipeline_name, fp)

    target = next((s for s in sheets if s.filename == csv_filename), None)
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"CSV '{csv_filename}' not available for this job",
        )

    csv_content = target.to_csv_string()

    tmp = tempfile.NamedTemporaryFile(
        suffix=".csv", delete=False, mode="w", encoding="utf-8",
    )
    tmp.write(csv_content)
    tmp.close()

    return FileResponse(
        path=tmp.name,
        media_type="text/csv",
        filename=f"{job_id[:8]}_{csv_filename}",
        headers={"Content-Disposition": f'attachment; filename="{job_id[:8]}_{csv_filename}"'},
    )


# --------------------------------------------------------------------------- #
#  File download                                                               #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/download")
async def download_file(job_id: str, file_path: str = Query(...)):
    """Download a specific file from job results.

    Works for both local and remote (HPC) output directories.
    """
    # Block path traversal
    normalized = PurePosixPath(file_path)
    if ".." in normalized.parts:
        raise HTTPException(status_code=400,
                            detail="Invalid file path (path traversal detected)")

    loc = _ensure_output(job_id)
    filename = normalized.name
    media_type = _media_type_for(filename)

    if loc.is_remote:
        ssh = _get_ssh()
        if not ssh:
            raise HTTPException(status_code=503, detail="SSH not connected")

        remote_file = f"{loc.remote_path}/{file_path}"
        try:
            local_tmp = _remote_download_to_temp(
                ssh, remote_file, suffix=f"_{filename}"
            )
        except FileNotFoundError:
            raise HTTPException(status_code=404,
                                detail=f"File not found: {file_path}")
        except Exception as e:
            raise HTTPException(status_code=500,
                                detail=f"Download failed: {e}")

        return FileResponse(
            path=local_tmp, filename=filename, media_type=media_type,
        )

    # Local
    output_dir = loc.local_path
    target = (output_dir / file_path).resolve()

    try:
        target.relative_to(output_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400,
                            detail="Invalid file path (path traversal detected)")

    if not target.exists():
        raise HTTPException(status_code=404,
                            detail=f"File not found: {file_path}")
    if not target.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {file_path}")

    return FileResponse(path=str(target), filename=target.name,
                        media_type=media_type)


# --------------------------------------------------------------------------- #
#  Export                                                                       #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/export")
async def export_results(job_id: str):
    """Package all job results as a .tar.gz archive for download."""
    loc = _ensure_output(job_id)

    if loc.is_remote:
        ssh = _get_ssh()
        if not ssh:
            raise HTTPException(status_code=503, detail="SSH not connected")

        # Create archive remotely, then download it
        remote_tar = f"/tmp/neuroinsight_{job_id[:8]}_results.tar.gz"
        cmd = f"tar -czf {remote_tar} -C {loc.remote_path!r} --exclude='_inputs' ."
        exit_code, _, stderr = ssh.execute(cmd, timeout=120)
        if exit_code != 0:
            raise HTTPException(status_code=500,
                                detail=f"Remote tar failed: {stderr.strip()}")
        try:
            local_tmp = _remote_download_to_temp(ssh, remote_tar, suffix=".tar.gz")
        finally:
            ssh.execute(f"rm -f {remote_tar}", timeout=10)

        return FileResponse(
            path=local_tmp,
            filename=f"neuroinsight_{job_id[:8]}_results.tar.gz",
            media_type="application/gzip",
        )

    # Local
    output_dir = loc.local_path
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=f"_{job_id[:8]}_results.tar.gz"
    )
    with tarfile.open(tmp.name, "w:gz") as tar:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                rel = str(file_path.relative_to(output_dir))
                if not rel.startswith("_inputs"):
                    tar.add(str(file_path), arcname=rel)

    try:
        from backend.core.audit import audit_log
        audit_log.record("results_exported", job_id=job_id)
    except Exception as e:
        logger.debug("Audit log unavailable for export: %s", e)

    return FileResponse(
        path=tmp.name,
        filename=f"neuroinsight_{job_id[:8]}_results.tar.gz",
        media_type="application/gzip",
    )


# --------------------------------------------------------------------------- #
#  Provenance                                                                  #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/provenance")
async def get_provenance(job_id: str):
    """Get provenance/reproducibility information for a job."""
    loc = _resolve_output(job_id)

    spec_data: dict = {}
    if loc.is_remote:
        ssh = _get_ssh()
        if ssh:
            candidates = [
                f"{loc.remote_path}/job_spec.json",
                f"{loc.remote_path}/../scripts/job_spec.json",
            ]
            for candidate in candidates:
                try:
                    content = _remote_read_text(ssh, candidate)
                    spec_data = json.loads(content)
                    break
                except Exception:
                    continue
            if not spec_data:
                logger.debug("Could not read remote job_spec.json for %s", job_id[:8])
    elif loc.local_path:
        candidates = [
            loc.local_path / "job_spec.json",
            loc.local_path.parent / "scripts" / "job_spec.json",
        ]
        for spec_file in candidates:
            if spec_file.exists():
                try:
                    spec_data = json.loads(spec_file.read_text())
                    break
                except Exception as e:
                    logger.debug("Could not parse %s for %s: %s",
                                 spec_file.name, job_id[:8], e)

    # Input file hashes (only for local files)
    input_hashes = {}
    for input_file in spec_data.get("input_files", []):
        p = Path(input_file)
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            input_hashes[p.name] = f"sha256:{h}"

    # Timing from DB
    job_info: dict = {}
    try:
        from backend.core.database import get_db_context
        from backend.models.job import Job
        with get_db_context() as db:
            job = db.query(Job).filter_by(id=job_id).first()
            if job:
                job_info = {
                    "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "exit_code": job.exit_code,
                    "backend_type": job.backend_type,
                    "backend_job_id": job.backend_job_id,
                }
    except Exception as e:
        logger.debug("Could not load provenance from DB for %s: %s",
                     job_id[:8], e)

    metadata_audit = ""
    metadata_audit_path = ""
    audit_candidates = [
        "bundle/provenance/metadata_audit.txt",
        "bundle/metadata_audit.txt",
    ]
    if loc.is_remote:
        ssh = _get_ssh()
        if ssh and loc.remote_path:
            for rel in audit_candidates:
                candidate = f"{loc.remote_path}/{rel}"
                try:
                    metadata_audit = _remote_read_text(ssh, candidate)
                    metadata_audit_path = rel
                    break
                except Exception:
                    continue
    elif loc.local_path:
        for rel in audit_candidates:
            p = loc.local_path / rel
            if p.exists():
                try:
                    metadata_audit = p.read_text(errors="replace")
                    metadata_audit_path = rel
                    break
                except Exception:
                    continue

    return {
        "job_id": job_id,
        "container_image": spec_data.get("container_image"),
        "plugin_id": spec_data.get("plugin_id"),
        "workflow_id": spec_data.get("workflow_id"),
        "parameters": spec_data.get("parameters", {}),
        "resources": spec_data.get("resources", {}),
        "input_files": spec_data.get("input_files", []),
        "input_hashes": input_hashes,
        "execution": job_info,
        "reproducibility_command": _build_repro_command(spec_data),
        "metadata_audit": metadata_audit,
        "metadata_audit_path": metadata_audit_path,
    }


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _build_repro_command(spec: dict) -> str:
    """Build a CLI command to reproduce this job."""
    image = spec.get("container_image", "")
    if not image:
        return ""
    parts = ["docker run --rm"]
    parts.append("-v $(pwd)/inputs:/data/inputs:ro")
    parts.append("-v $(pwd)/outputs:/data/outputs:rw")
    cmd = spec.get("command_template", "")
    if cmd:
        parts.append(f'{image} /bin/bash -c "{cmd.strip()[:200]}..."')
    else:
        parts.append(image)
    return " \\\n  ".join(parts)


def _parse_stats_file(path: Path) -> dict | None:
    """Parse a FreeSurfer .stats file from a local Path."""
    return _parse_stats_text(path.read_text(errors="replace"))


def _parse_stats_text(text: str) -> dict | None:
    """Parse a FreeSurfer .stats file from raw text."""
    result: dict[str, Any] = {}
    table_data: list[dict] = []
    headers: list[str] = []

    for line in text.splitlines():
        if line.startswith("# Measure"):
            parts = [p.strip() for p in line[len("# Measure"):].split(",")]
            if len(parts) >= 4:
                try:
                    result[parts[1]] = float(parts[3])
                except (ValueError, IndexError):
                    result[parts[1]] = parts[3]
        elif line.startswith("# ColHeaders"):
            headers = line.split()[2:]
        elif not line.startswith("#") and line.strip() and headers:
            cols = line.split()
            if len(cols) == len(headers):
                row: dict[str, Any] = {}
                for h, v in zip(headers, cols):
                    try:
                        row[h] = float(v)
                    except ValueError:
                        row[h] = v
                table_data.append(row)

    if not result and not table_data:
        return None

    if table_data:
        result["table"] = table_data
    return result


def _parse_color_lut(path: Path) -> dict:
    """Parse a FreeSurfer-style color LUT file from a local Path."""
    return _parse_color_lut_text(path.read_text(errors="replace"))


def _parse_color_lut_text(text: str) -> dict:
    """Parse a FreeSurfer-style color LUT from raw text."""
    labels = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 5:
            idx, name = parts[0], parts[1]
            r, g, b = int(parts[2]), int(parts[3]), int(parts[4])
            labels[idx] = {"name": name, "color": f"#{r:02x}{g:02x}{b:02x}"}
    return labels
