"""
Results endpoints for serving real job output files.

All endpoints read from the actual output directory -- no mock/placeholder data.
If a job has no results yet, endpoints return 404.
"""
import hashlib
import json
import logging
import tarfile
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/results", tags=["results"])
logger = logging.getLogger(__name__)


def _get_output_dir(job_id: str) -> Path:
    """Resolve the output directory for a given job.

    Checks both settings.output_dir and settings.data_dir/outputs for
    backwards compatibility.
    """
    from backend.core.config import get_settings

    settings = get_settings()

    # Primary: data_dir/outputs/job_id (used by celery_tasks)
    d = Path(settings.data_dir) / "outputs" / job_id
    if d.exists():
        return d

    # Fallback: output_dir/job_id
    d2 = Path(settings.output_dir) / job_id
    if d2.exists():
        return d2

    return d  # Return primary even if it doesn't exist -- caller checks


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


# --------------------------------------------------------------------------- #
#  File listing                                                                #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/files")
async def list_job_files(job_id: str):
    """List all output files for a completed job.

    Returns a flat list of every file in the job's output directory with
    type classification, size, and a download URL.
    """
    output_dir = _get_output_dir(job_id)

    if not output_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No output directory for job {job_id}. Job may still be running or has no results.",
        )

    files = []
    for file_path in sorted(output_dir.rglob("*")):
        if file_path.is_file():
            rel = file_path.relative_to(output_dir)
            # Skip internal staging directory
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

def _find_files(output_dir: Path, patterns: list[str]) -> list[dict]:
    """Find files matching name patterns in the output dir."""
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
                    "path": f"/api/results/{output_dir.name}/download?file_path={rel}",
                    "size": _format_size(f.stat().st_size),
                })
                break
    return results


@router.get("/{job_id}/volume")
async def get_volume(job_id: str):
    """Find the main anatomical volume(s) in job output.

    Searches for common volume filenames: norm, T1w, brain, anatomy, orig.
    """
    output_dir = _get_output_dir(job_id)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="No results yet")

    volumes = _find_files(output_dir, ["norm.nii", "t1w.nii", "brain.nii", "anatomy.nii", "orig.nii"])
    if not volumes:
        # Fallback: any NIfTI file
        volumes = _find_files(output_dir, [".nii.gz", ".nii"])
    return {"job_id": job_id, "volumes": volumes}


@router.get("/{job_id}/segmentation")
async def get_segmentation(job_id: str):
    """Find segmentation overlays in job output.

    Searches for aseg, aparc, segmentation, labels.
    """
    output_dir = _get_output_dir(job_id)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="No results yet")

    segs = _find_files(output_dir, ["aseg.nii", "aparc", "segmentation.nii", "labels.nii", "dseg.nii"])
    return {"job_id": job_id, "segmentations": segs}


# --------------------------------------------------------------------------- #
#  Labels / Metrics -- read from real files                                    #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/labels")
async def get_labels(job_id: str):
    """Read label definitions from job output.

    Searches for labels.json or any *labels*.json file in the output tree.
    Returns its content as-is. Falls back to parsed .stats files.
    """
    output_dir = _get_output_dir(job_id)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="No results yet")

    # Look for labels JSON
    for f in output_dir.rglob("*labels*.json"):
        try:
            return {"job_id": job_id, "labels": json.loads(f.read_text()), "source": str(f.name)}
        except Exception:
            continue

    # Look for FreeSurfer colorLUT-style file
    for f in output_dir.rglob("*ColorLUT*"):
        try:
            labels = _parse_color_lut(f)
            return {"job_id": job_id, "labels": labels, "source": str(f.name)}
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="No label definitions found in job output")


@router.get("/{job_id}/metrics")
async def get_metrics(job_id: str):
    """Read quantitative metrics from job output.

    Searches for:
    1. metrics.json, stats.json, summary.json
    2. FreeSurfer .stats files (aseg.stats, etc.)
    3. Any CSV/TSV files
    """
    output_dir = _get_output_dir(job_id)
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="No results yet")

    metrics: dict[str, Any] = {}
    sources: list[str] = []

    # JSON metrics files
    for pattern in ["**/metrics*.json", "**/stats*.json", "**/summary*.json", "**/*_stats.json"]:
        for f in output_dir.glob(pattern):
            try:
                data = json.loads(f.read_text())
                metrics[f.stem] = data
                sources.append(str(f.relative_to(output_dir)))
            except Exception:
                continue

    # FreeSurfer .stats files
    for f in output_dir.rglob("*.stats"):
        try:
            parsed = _parse_stats_file(f)
            if parsed:
                metrics[f.stem] = parsed
                sources.append(str(f.relative_to(output_dir)))
        except Exception:
            continue

    # CSV/TSV files (provide paths for frontend to fetch and display)
    csv_files = []
    for f in output_dir.rglob("*.csv"):
        csv_files.append(str(f.relative_to(output_dir)))
    for f in output_dir.rglob("*.tsv"):
        csv_files.append(str(f.relative_to(output_dir)))

    if not metrics and not csv_files:
        raise HTTPException(status_code=404, detail="No metrics found in job output")

    return {
        "job_id": job_id,
        "metrics": metrics,
        "csv_files": csv_files,
        "sources": sources,
    }


# --------------------------------------------------------------------------- #
#  File download                                                               #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/download")
async def download_file(job_id: str, file_path: str = Query(...)):
    """Download a specific file from job results.

    The file_path is relative to the job output directory.
    Path traversal is blocked.
    """
    output_dir = _get_output_dir(job_id)
    target = (output_dir / file_path).resolve()

    # Security: path must stay inside output_dir
    try:
        target.relative_to(output_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path (path traversal detected)")

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    if not target.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {file_path}")

    # Determine media type for in-browser viewing
    media_type = "application/octet-stream"
    lower = target.name.lower()
    if lower.endswith(".json"):
        media_type = "application/json"
    elif lower.endswith(".csv"):
        media_type = "text/csv"
    elif lower.endswith(".tsv"):
        media_type = "text/tab-separated-values"
    elif lower.endswith(".html"):
        media_type = "text/html"
    elif lower.endswith(".png"):
        media_type = "image/png"
    elif lower.endswith((".jpg", ".jpeg")):
        media_type = "image/jpeg"
    elif lower.endswith(".svg"):
        media_type = "image/svg+xml"
    elif lower.endswith(".txt") or lower.endswith(".log"):
        media_type = "text/plain"

    return FileResponse(path=str(target), filename=target.name, media_type=media_type)


# --------------------------------------------------------------------------- #
#  Export                                                                       #
# --------------------------------------------------------------------------- #

@router.get("/{job_id}/export")
async def export_results(job_id: str):
    """Package all job results as a .tar.gz archive for download."""
    output_dir = _get_output_dir(job_id)

    if not output_dir.exists():
        raise HTTPException(status_code=404, detail=f"No output directory for job {job_id}")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{job_id[:8]}_results.tar.gz")
    with tarfile.open(tmp.name, "w:gz") as tar:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file() and not str(file_path.relative_to(output_dir)).startswith("_inputs"):
                arcname = str(file_path.relative_to(output_dir))
                tar.add(str(file_path), arcname=arcname)

    try:
        from backend.core.audit import audit_log
        audit_log.record("results_exported", job_id=job_id)
    except Exception:
        pass

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
    """Get provenance/reproducibility information for a job.

    Reads job_spec.json from the output directory and cross-references
    the database for timing and status information.
    """
    output_dir = _get_output_dir(job_id)

    # Load job spec from disk
    spec_file = output_dir / "job_spec.json"
    spec_data: dict = {}
    if spec_file.exists():
        try:
            spec_data = json.loads(spec_file.read_text())
        except Exception:
            pass

    # Compute input file hashes
    input_hashes = {}
    for input_file in spec_data.get("input_files", []):
        p = Path(input_file)
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            input_hashes[p.name] = f"sha256:{h}"

    # Get timing from DB
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
    except Exception:
        pass

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
    }


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _build_repro_command(spec: dict) -> str:
    """Build a CLI command to reproduce this job."""
    image = spec.get("container_image", "")
    if not image:
        return ""
    parts = [f"docker run --rm"]
    parts.append("-v $(pwd)/inputs:/data/inputs:ro")
    parts.append("-v $(pwd)/outputs:/data/outputs:rw")
    cmd = spec.get("command_template", "")
    if cmd:
        parts.append(f'{image} /bin/bash -c "{cmd.strip()[:200]}..."')
    else:
        parts.append(image)
    return " \\\n  ".join(parts)


def _parse_stats_file(path: Path) -> dict | None:
    """Parse a FreeSurfer .stats file into a dict of measures."""
    result: dict[str, Any] = {}
    table_data: list[dict] = []
    headers: list[str] = []

    for line in path.read_text(errors="replace").splitlines():
        # Header measures: # Measure BrainSeg, BrainSegVol, Brain Segmentation Volume, 1234.0, mm^3
        if line.startswith("# Measure"):
            parts = [p.strip() for p in line[len("# Measure"):].split(",")]
            if len(parts) >= 4:
                try:
                    result[parts[1]] = float(parts[3])
                except (ValueError, IndexError):
                    result[parts[1]] = parts[3]

        # Table header: # ColHeaders StructName NumVert SurfArea ...
        elif line.startswith("# ColHeaders"):
            headers = line.split()[2:]

        # Table rows (non-comment lines)
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
    """Parse a FreeSurfer-style color LUT file."""
    labels = {}
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 5:
            idx, name = parts[0], parts[1]
            r, g, b = int(parts[2]), int(parts[3]), int(parts[4])
            labels[idx] = {"name": name, "color": f"#{r:02x}{g:02x}{b:02x}"}
    return labels
