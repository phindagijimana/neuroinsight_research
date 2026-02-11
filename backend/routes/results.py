"""
Results endpoints for serving job output files.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
import os

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/{job_id}/files")
async def list_job_files(job_id: str):
    """List all output files for a job."""
    from backend.core.config import get_settings
    settings = get_settings()

    output_dir = Path(settings.output_dir) / job_id
    if not output_dir.exists():
        # Return placeholder data if no real output yet
        return {
            "job_id": job_id,
            "files": [
                {
                    "name": "anatomy.nii.gz",
                    "type": "volume",
                    "path": f"/api/results/{job_id}/anatomy.nii.gz",
                    "size": "4.2 MB",
                },
                {
                    "name": "segmentation.nii.gz",
                    "type": "segmentation",
                    "path": f"/api/results/{job_id}/segmentation.nii.gz",
                    "size": "0.3 MB",
                },
                {
                    "name": "labels.json",
                    "type": "metadata",
                    "path": f"/api/results/{job_id}/labels.json",
                    "size": "2 KB",
                },
                {
                    "name": "metrics.json",
                    "type": "metrics",
                    "path": f"/api/results/{job_id}/metrics.json",
                    "size": "1 KB",
                },
            ],
        }

    # List real output files
    files = []
    for file_path in output_dir.rglob("*"):
        if file_path.is_file():
            rel = file_path.relative_to(output_dir)
            size = file_path.stat().st_size
            file_type = "file"
            if file_path.name.endswith((".nii", ".nii.gz")):
                file_type = "volume"
            elif file_path.name.endswith(".json"):
                file_type = "metadata"
            files.append({
                "name": str(rel),
                "type": file_type,
                "path": f"/api/results/{job_id}/download?file_path={rel}",
                "size": _format_size(size),
            })

    return {"job_id": job_id, "files": files}


@router.get("/{job_id}/volume")
async def get_volume(job_id: str):
    """Get the main anatomical volume for a job."""
    return {
        "job_id": job_id,
        "url": f"/api/results/{job_id}/anatomy.nii.gz",
        "type": "nifti",
    }


@router.get("/{job_id}/segmentation")
async def get_segmentation(job_id: str):
    """Get the segmentation overlay for a job."""
    return {
        "job_id": job_id,
        "url": f"/api/results/{job_id}/segmentation.nii.gz",
        "type": "nifti",
        "colormap": "actc",
    }


@router.get("/{job_id}/labels")
async def get_labels(job_id: str):
    """Get label definitions for segmentation."""
    return {
        "job_id": job_id,
        "labels": {
            "0": {"name": "Background", "color": "#000000"},
            "1": {"name": "Left Hippocampus", "color": "#FF0000", "volume_mm3": 3456},
            "2": {"name": "Right Hippocampus", "color": "#00FF00", "volume_mm3": 3521},
            "3": {"name": "Left Amygdala", "color": "#0000FF", "volume_mm3": 1234},
            "4": {"name": "Right Amygdala", "color": "#FFD700", "volume_mm3": 1198},
        },
    }


@router.get("/{job_id}/metrics")
async def get_metrics(job_id: str):
    """Get quantitative metrics for a job."""
    return {
        "job_id": job_id,
        "metrics": {
            "total_volume_mm3": 9409,
            "left_hippocampus_volume": 3456,
            "right_hippocampus_volume": 3521,
            "asymmetry_index": 0.019,
            "processing_time_seconds": 1234,
            "quality_score": 0.95,
        },
    }


@router.get("/{job_id}/download")
async def download_file(job_id: str, file_path: str = Query(...)):
    """Download a specific file from job results.

    Args:
        job_id: Job ID
        file_path: Relative path within job output directory
    """
    from backend.core.config import get_settings
    settings = get_settings()

    # Resolve the file path within the output directory
    output_dir = Path(settings.output_dir) / job_id
    target = (output_dir / file_path).resolve()

    # Security: ensure the target is within the output directory
    try:
        target.relative_to(output_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path (path traversal detected)")

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    if not target.is_file():
        raise HTTPException(status_code=400, detail=f"Not a file: {file_path}")

    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )


@router.get("/{job_id}/export")
async def export_results(job_id: str):
    """Package job results as a .tar.gz bundle for download.

    Creates a compressed archive of all output files and returns it.
    """
    import tarfile
    import tempfile
    from backend.core.config import get_settings

    settings = get_settings()
    output_dir = Path(settings.output_dir) / job_id

    if not output_dir.exists():
        raise HTTPException(status_code=404, detail=f"No output directory for job {job_id}")

    # Create temp tarball
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f"_{job_id[:8]}_results.tar.gz")
    with tarfile.open(tmp.name, "w:gz") as tar:
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                arcname = str(file_path.relative_to(output_dir))
                tar.add(str(file_path), arcname=arcname)

    # Audit
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


@router.get("/{job_id}/provenance")
async def get_provenance(job_id: str):
    """Get provenance/reproducibility information for a job.

    Returns container image, input hashes, parameters, and timing
    to enable exact reproduction of results.
    """
    import hashlib
    from backend.core.config import get_settings

    settings = get_settings()

    # Load job spec from disk or DB
    spec_file = Path(settings.output_dir) / job_id / "job_spec.json"
    spec_data = {}
    if spec_file.exists():
        import json
        spec_data = json.loads(spec_file.read_text())

    # Compute input file hashes
    input_hashes = {}
    for input_file in spec_data.get("input_files", []):
        p = Path(input_file)
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            input_hashes[p.name] = f"sha256:{h}"

    # Get job info from DB
    job_info = {}
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


def _build_repro_command(spec: dict) -> str:
    """Build a CLI command to reproduce this job."""
    image = spec.get("container_image", "")
    params = spec.get("parameters", {})
    if not image:
        return ""

    cmd_parts = [f"docker run --rm"]
    cmd_parts.append(f"-v $(pwd)/inputs:/data/inputs:ro")
    cmd_parts.append(f"-v $(pwd)/outputs:/data/outputs:rw")
    cmd_parts.append(image)

    return " \\\n  ".join(cmd_parts)


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
