"""
NeuroInsight Research - Main API Application

FastAPI application for HPC-native neuroimaging pipeline platform.
"""
import logging
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from backend.core.config import get_settings
from backend.core.database import init_db, get_db
from backend.core.pipelines import get_pipeline_registry
from backend.core.plugin_registry import get_plugin_workflow_registry
from backend.core.execution import JobSpec, ResourceSpec
from backend.execution import get_backend
from backend.models.job import Job, JobStatusEnum
from backend.routes import results
from backend.routes import hpc
from backend.routes import audit

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_FS_LICENSE_PLUGIN_IDS = {
    "fmriprep",
    "fastsurfer",
    "segmentha_t1",
    "segmentha_t2",
    "freesurfer_recon",
    "freesurfer_longitudinal",
    "freesurfer_longitudinal_stats",
}


def _plugin_needs_fs_license(plugin) -> bool:
    """Check if a plugin requires a FreeSurfer license."""
    if plugin.id in _FS_LICENSE_PLUGIN_IDS:
        return True
    for inp in plugin.inputs_required + plugin.inputs_optional:
        if isinstance(inp, dict) and inp.get("key") == "fs_license":
            return True
    return False


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app):
    """Application lifespan manager."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Backend: {settings.backend_type}")

    # Initialize database
    init_db()

    # Load legacy pipeline registry
    pipelines_dir = Path(settings.pipelines_dir)
    if not pipelines_dir.exists():
        pipelines_dir = Path(__file__).parent.parent / "pipelines"
    registry = get_pipeline_registry(pipelines_dir)
    logger.info(f"Loaded {len(registry.list_pipelines())} legacy pipelines")

    # Load plugin/workflow registry
    plugins_dir = Path(__file__).parent.parent / "plugins"
    workflows_dir = Path(__file__).parent.parent / "workflows"
    pw_registry = get_plugin_workflow_registry(plugins_dir, workflows_dir)
    logger.info(
        f"Loaded {len(pw_registry.list_plugins())} plugins, "
        f"{len(pw_registry.list_workflows())} workflows"
    )

    # Ensure data directories
    settings.ensure_directories()

    yield

    logger.info("Shutting down...")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="HPC-native neuroimaging pipeline execution platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(results.router)
app.include_router(hpc.router)
app.include_router(audit.router)


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "backend": settings.backend_type,
    }


@app.get("/health")
def health_check():
    """Health check -- reports status of all infrastructure."""
    services = {}

    # Database health
    try:
        from backend.core.database import health_check as db_health
        services["database"] = db_health()
    except Exception as e:
        services["database"] = {"healthy": False, "message": str(e)}

    # Redis health
    try:
        import redis
        r = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            socket_timeout=3,
        )
        r.ping()
        services["redis"] = {"healthy": True, "message": "Redis connection OK"}
    except Exception as e:
        services["redis"] = {"healthy": False, "message": str(e)}

    # MinIO health
    try:
        from backend.core.storage import storage
        services["minio"] = storage.health_check()
    except Exception as e:
        services["minio"] = {"healthy": False, "message": str(e)}

    # Execution backend health
    try:
        backend = get_backend()
        services["execution"] = backend.health_check()
    except Exception as e:
        services["execution"] = {"healthy": False, "message": str(e)}

    all_healthy = all(s.get("healthy", False) for s in services.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "services": services,
    }


@app.get("/api/system/resources")
def get_system_resources():
    """Detect host machine CPU, RAM, and GPU capabilities."""
    from backend.core.system_resources import detect_all
    return detect_all()


# ---------------------------------------------------------------------------
# Legacy Pipelines
# ---------------------------------------------------------------------------

@app.get("/api/pipelines")
def list_pipelines():
    """List available pipelines."""
    registry = get_pipeline_registry()
    pipelines = registry.list_pipelines()
    return {
        "pipelines": [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "container_image": p.container_image,
                "inputs": [
                    {
                        "name": inp.name,
                        "type": inp.type,
                        "required": inp.required,
                        "description": inp.description,
                    }
                    for inp in p.inputs
                ],
                "parameters": [
                    {
                        "name": param.name,
                        "type": param.type,
                        "default": param.default,
                        "description": param.description,
                    }
                    for param in p.parameters
                ],
                "resources": {
                    "memory_gb": p.resources.memory_gb,
                    "cpus": p.resources.cpus,
                    "time_hours": p.resources.time_hours,
                    "gpu": p.resources.gpu,
                },
            }
            for p in pipelines
        ]
    }


@app.get("/api/pipelines/{pipeline_name}")
def get_pipeline_details(pipeline_name: str):
    """Get detailed pipeline information."""
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline(pipeline_name)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {
        "name": pipeline.name,
        "version": pipeline.version,
        "description": pipeline.description,
        "container_image": pipeline.container_image,
        "inputs": [vars(inp) for inp in pipeline.inputs],
        "parameters": [vars(param) for param in pipeline.parameters],
        "resources": vars(pipeline.resources),
        "outputs": [vars(out) for out in pipeline.outputs],
        "authors": pipeline.authors,
        "references": pipeline.references,
    }


# ---------------------------------------------------------------------------
# Plugins & Workflows
# ---------------------------------------------------------------------------

@app.get("/api/plugins")
def list_plugins(user_selectable_only: bool = True):
    """List available plugins."""
    pw_registry = get_plugin_workflow_registry()
    plugins = pw_registry.list_plugins(user_selectable_only=user_selectable_only)
    return {
        "plugins": [p.to_api_dict() for p in plugins],
        "total": len(plugins),
    }


@app.get("/api/plugins/{plugin_id}")
def get_plugin(plugin_id: str):
    """Get detailed plugin information."""
    pw_registry = get_plugin_workflow_registry()
    plugin = pw_registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return plugin.to_api_dict()


@app.get("/api/plugins/{plugin_id}/yaml")
def get_plugin_yaml(plugin_id: str):
    """Get the raw YAML definition for a plugin (for docs/review)."""
    pw_registry = get_plugin_workflow_registry()
    plugin = pw_registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    import yaml
    return {
        "id": plugin.id,
        "name": plugin.name,
        "yaml": yaml.dump(plugin.raw_yaml, default_flow_style=False, sort_keys=False),
    }


@app.get("/api/workflows")
def list_workflows():
    """List available workflows with enriched step info."""
    pw_registry = get_plugin_workflow_registry()
    workflows = pw_registry.list_workflows()
    return {
        "workflows": [w.to_api_dict(plugin_registry=pw_registry.plugins) for w in workflows],
        "total": len(workflows),
    }


@app.get("/api/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    """Get detailed workflow information with plugin metadata."""
    pw_registry = get_plugin_workflow_registry()
    workflow = pw_registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return workflow.to_api_dict(plugin_registry=pw_registry.plugins)


@app.get("/api/workflows/{workflow_id}/yaml")
def get_workflow_yaml(workflow_id: str):
    """Get the raw YAML definition for a workflow (for docs/review)."""
    pw_registry = get_plugin_workflow_registry()
    workflow = pw_registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    import yaml
    return {
        "id": workflow.id,
        "name": workflow.name,
        "yaml": yaml.dump(workflow.raw_yaml, default_flow_style=False, sort_keys=False),
    }


# ---------------------------------------------------------------------------
# Version Management
# ---------------------------------------------------------------------------

@app.get("/api/registry/versions")
def get_registry_versions():
    """Get current plugin/workflow version summary."""
    pw_registry = get_plugin_workflow_registry()
    return {
        "plugins": pw_registry.get_plugin_versions(),
        "workflows": pw_registry.get_workflow_versions(),
    }


@app.get("/api/registry/lockfile")
def get_registry_lockfile():
    """Generate a lockfile capturing all current plugin/workflow versions and content hashes.

    Save this lockfile with your data to ensure reproducibility.
    """
    pw_registry = get_plugin_workflow_registry()
    return pw_registry.generate_lockfile()


@app.post("/api/registry/verify")
def verify_registry_lockfile(lockfile: dict):
    """Verify the current registry against a previously saved lockfile.

    Returns a report of any version or content mismatches.
    """
    pw_registry = get_plugin_workflow_registry()
    return pw_registry.verify_lockfile(lockfile)


@app.post("/api/registry/reload")
def reload_registry():
    """Reload all plugins and workflows from disk.

    Use after adding or updating YAML definitions.
    """
    pw_registry = get_plugin_workflow_registry()
    pw_registry.reload()
    return {
        "plugins": len(pw_registry.plugins),
        "workflows": len(pw_registry.workflows),
        "message": "Registry reloaded successfully",
    }


# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------

@app.get("/api/docs/all")
def get_docs_all():
    """Get all plugins and workflows with full details for the docs page."""
    pw_registry = get_plugin_workflow_registry()
    plugins = pw_registry.list_plugins(user_selectable_only=False)
    workflows = pw_registry.list_workflows()
    import yaml
    return {
        "plugins": [
            {
                **p.to_api_dict(),
                "yaml": yaml.dump(p.raw_yaml, default_flow_style=False, sort_keys=False),
            }
            for p in plugins
        ],
        "workflows": [w.to_api_dict(plugin_registry=pw_registry.plugins) for w in workflows],
        "total_plugins": len(plugins),
        "total_workflows": len(workflows),
    }


# ---------------------------------------------------------------------------
# License Status
# ---------------------------------------------------------------------------

@app.get("/api/license/status")
def license_status():
    """Check FreeSurfer license status."""
    path = settings.fs_license_resolved
    return {
        "found": path is not None,
        "path": path,
        "search_locations": [
            "./license.txt (app directory)",
            "./data/license.txt",
            "$FREESURFER_HOME/license.txt",
            "~/.freesurfer/license.txt",
        ],
        "hint": "Place your FreeSurfer license.txt in the app directory (next to start_dev.sh)",
    }


# ---------------------------------------------------------------------------
# Job Submission -- Plugins
# ---------------------------------------------------------------------------

class PluginJobSubmitRequest(BaseModel):
    """Submit a single-plugin job."""
    input_files: List[str]
    parameters: dict = {}
    custom_resources: Optional[dict] = None


@app.post("/api/plugins/{plugin_id}/submit")
def submit_plugin_job(plugin_id: str, request: PluginJobSubmitRequest, db: Session = Depends(get_db)):
    """Submit a job that runs a single plugin."""
    pw_registry = get_plugin_workflow_registry()
    plugin = pw_registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")

    # Resolve resources
    res = plugin.resources if isinstance(plugin.resources, dict) else {}
    if request.custom_resources:
        res = {**res, **request.custom_resources}

    resources = ResourceSpec(
        memory_gb=res.get("memory_gb", 8),
        cpus=res.get("cpus", 4),
        time_hours=res.get("time_hours", 6),
        gpu=res.get("gpu", False),
    )

    job_id = str(uuid.uuid4())
    output_dir = str(Path(settings.data_dir) / "outputs" / job_id)

    spec = JobSpec(
        pipeline_name=plugin.name,
        container_image=plugin.container_image,
        input_files=request.input_files,
        output_dir=output_dir,
        parameters=request.parameters,
        resources=resources,
        plugin_id=plugin_id,
        execution_mode="plugin",
    )

    # Submit via backend
    backend = get_backend()
    backend.submit_job(spec, job_id=job_id)

    try:
        from backend.core.audit import audit_log
        audit_log.record("job_submitted", job_id=job_id, plugin_id=plugin_id, mode="plugin")
    except Exception:
        pass

    return {"job_id": job_id, "status": "pending", "plugin": plugin_id}


# ---------------------------------------------------------------------------
# Job Submission -- Workflows
# ---------------------------------------------------------------------------

class WorkflowJobSubmitRequest(BaseModel):
    """Submit a workflow job (multi-step)."""
    input_files: List[str]
    parameters: dict = {}
    custom_resources: Optional[dict] = None


@app.post("/api/workflows/{workflow_id}/submit")
def submit_workflow_job(workflow_id: str, request: WorkflowJobSubmitRequest, db: Session = Depends(get_db)):
    """Submit a workflow job that chains multiple plugins."""
    pw_registry = get_plugin_workflow_registry()
    workflow = pw_registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    # Validate all steps reference valid plugins
    for step in workflow.steps:
        if not pw_registry.get_plugin(step.uses):
            raise HTTPException(
                status_code=500,
                detail=f"Workflow references unknown plugin: {step.uses}",
            )

    # Use first step's plugin for container image and resources
    first_plugin = pw_registry.get_plugin(workflow.steps[0].uses)
    res = first_plugin.resources if isinstance(first_plugin.resources, dict) else {}
    if request.custom_resources:
        res = {**res, **request.custom_resources}

    resources = ResourceSpec(
        memory_gb=res.get("memory_gb", 8),
        cpus=res.get("cpus", 4),
        time_hours=res.get("time_hours", 6),
        gpu=res.get("gpu", False),
    )

    job_id = str(uuid.uuid4())
    output_dir = str(Path(settings.data_dir) / "outputs" / job_id)

    # Store workflow steps in parameters for the Celery task
    params = dict(request.parameters)
    params["_workflow_steps"] = [step.uses for step in workflow.steps]
    params["_workflow_id"] = workflow_id

    spec = JobSpec(
        pipeline_name=workflow.name,
        container_image=first_plugin.container_image,
        input_files=request.input_files,
        output_dir=output_dir,
        parameters=params,
        resources=resources,
        workflow_id=workflow_id,
        execution_mode="workflow",
    )

    backend = get_backend()
    backend.submit_job(spec, job_id=job_id)

    try:
        from backend.core.audit import audit_log
        audit_log.record("job_submitted", job_id=job_id, workflow_id=workflow_id, mode="workflow")
    except Exception:
        pass

    return {"job_id": job_id, "status": "pending", "workflow": workflow_id}


# ---------------------------------------------------------------------------
# Job Submission -- Legacy
# ---------------------------------------------------------------------------

class JobSubmitRequest(BaseModel):
    """Job submission request model."""
    pipeline_name: str
    input_files: List[str]
    parameters: dict = {}
    custom_resources: Optional[dict] = None


@app.post("/api/jobs/submit")
def submit_job(request: JobSubmitRequest, db: Session = Depends(get_db)):
    """Submit a job for execution (legacy pipeline mode)."""
    pipeline_name = request.pipeline_name
    input_files = request.input_files
    parameters = request.parameters
    custom_resources = request.custom_resources

    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline(pipeline_name)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_name}' not found")

    # Merge parameters with pipeline defaults
    merged_params = {}
    for param in pipeline.parameters:
        if param.default is not None:
            merged_params[param.name] = param.default
    merged_params.update(parameters)

    # Build resource spec
    res = vars(pipeline.resources)
    if custom_resources:
        res.update(custom_resources)

    resources = ResourceSpec(
        memory_gb=res.get("memory_gb", 8),
        cpus=res.get("cpus", 4),
        time_hours=res.get("time_hours", 6),
        gpu=res.get("gpu", False),
    )

    job_id = str(uuid.uuid4())
    output_dir = str(Path(settings.data_dir) / "outputs" / job_id)

    spec = JobSpec(
        pipeline_name=pipeline_name,
        container_image=pipeline.container_image,
        input_files=input_files,
        output_dir=output_dir,
        parameters=merged_params,
        resources=resources,
        pipeline_version=pipeline.version,
    )

    backend = get_backend()
    backend.submit_job(spec, job_id=job_id)

    return {"job_id": job_id, "status": "pending"}


# ---------------------------------------------------------------------------
# Batch Job Submission
# ---------------------------------------------------------------------------

class BatchSubmitRequest(BaseModel):
    """Batch job submission request."""
    pipeline_name: str
    input_dir: str
    output_dir: str = ""
    parameters: dict = {}
    file_pattern: str = "*.nii.gz"


@app.post("/api/jobs/submit-batch")
def submit_batch_job(request: BatchSubmitRequest, db: Session = Depends(get_db)):
    """Submit batch job to process all files in a directory."""
    import glob as glob_module

    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline(request.pipeline_name)
    if not pipeline:
        raise HTTPException(status_code=404, detail=f"Pipeline '{request.pipeline_name}' not found")

    input_path = Path(request.input_dir)
    if not input_path.exists() or not input_path.is_dir():
        raise HTTPException(status_code=400, detail=f"Input directory not found: {request.input_dir}")

    pattern = str(input_path / request.file_pattern)
    input_files = sorted(glob_module.glob(pattern))
    if not input_files:
        raise HTTPException(
            status_code=400,
            detail=f"No files matching '{request.file_pattern}' found in {request.input_dir}",
        )

    job_ids = []
    backend = get_backend()

    for input_file in input_files:
        job_id = str(uuid.uuid4())
        output_dir = str(Path(settings.data_dir) / "outputs" / job_id)

        resources = ResourceSpec(
            memory_gb=pipeline.resources.memory_gb,
            cpus=pipeline.resources.cpus,
            time_hours=pipeline.resources.time_hours,
            gpu=pipeline.resources.gpu,
        )

        spec = JobSpec(
            pipeline_name=request.pipeline_name,
            container_image=pipeline.container_image,
            input_files=[input_file],
            output_dir=output_dir,
            parameters=request.parameters,
            resources=resources,
            pipeline_version=pipeline.version,
        )

        backend.submit_job(spec, job_id=job_id)
        job_ids.append(job_id)

    return {
        "job_ids": job_ids,
        "total_jobs": len(job_ids),
        "pipeline_name": request.pipeline_name,
        "file_pattern": request.file_pattern,
    }


# ---------------------------------------------------------------------------
# Job Monitoring
# ---------------------------------------------------------------------------

@app.get("/api/jobs")
def list_jobs(status: Optional[str] = None, limit: int = 100, db: Session = Depends(get_db)):
    """List jobs with optional status filter."""
    query = db.query(Job).filter(Job.deleted == False)
    if status:
        query = query.filter(Job.status == status)
    query = query.order_by(Job.submitted_at.desc()).limit(limit)
    jobs = query.all()
    return {"jobs": [job.to_dict() for job in jobs]}


@app.get("/api/jobs/progress")
def get_jobs_progress(db: Session = Depends(get_db)):
    """Lightweight endpoint returning progress for all active jobs.

    Frontend polls this at ~2-3s intervals to animate progress bars.
    """
    active_jobs = (
        db.query(Job)
        .filter(Job.deleted == False, Job.status.in_(["pending", "running"]))
        .all()
    )
    return {
        "jobs": [
            {
                "id": j.id,
                "status": j.status,
                "progress": j.progress or 0,
                "current_phase": j.current_phase,
            }
            for j in active_jobs
        ]
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get job details."""
    job = db.query(Job).filter(Job.id == job_id, Job.deleted == False).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # If job is running, refresh status from backend
    if job.status in ("pending", "running"):
        try:
            backend = get_backend()
            info = backend.get_job_info(job_id)
            if info.progress and info.progress > (job.progress or 0):
                job.progress = info.progress
            if info.current_phase:
                job.current_phase = info.current_phase
            db.commit()
        except Exception:
            pass

    return job.to_dict()


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    """Cancel a running job."""
    job = db.query(Job).filter(Job.id == job_id, Job.deleted == False).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.is_terminal:
        raise HTTPException(status_code=400, detail="Job already in terminal state")

    try:
        backend = get_backend()
        backend.cancel_job(job_id)
    except Exception as e:
        logger.warning(f"Backend cancel failed for {job_id}: {e}")

    job.mark_cancelled()
    db.commit()

    return {"message": f"Job {job_id} cancelled", "status": "cancelled"}


@app.get("/api/jobs/{job_id}/logs")
def get_job_logs(job_id: str):
    """Get job logs."""
    try:
        backend = get_backend()
        logs = backend.get_job_logs(job_id)
        return {
            "job_id": job_id,
            "stdout": logs.stdout,
            "stderr": logs.stderr,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Logs not found: {e}")


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete a job and its database record."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    job.soft_delete()
    db.commit()

    return {"message": f"Job {job_id} deleted"}


# ---------------------------------------------------------------------------
# File Operations
# ---------------------------------------------------------------------------

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a single file to the server."""
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_name = file.filename.replace("..", "").replace("/", "_").replace("\\", "_")
    dest_path = upload_dir / safe_name

    # Handle duplicate filenames
    if dest_path.exists():
        stem = dest_path.stem
        suffix = dest_path.suffix
        counter = 1
        while dest_path.exists():
            dest_path = upload_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    # Write file
    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)

    return {"path": str(dest_path), "filename": safe_name, "size": len(content)}


@app.get("/api/browse")
def browse_directory(path: str = ".", backend_type: str = "local"):
    """Browse directory to list files."""
    target = Path(path).resolve()

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    files = []
    directories = []
    nifti_files = []

    try:
        for entry in sorted(target.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                directories.append({
                    "name": entry.name,
                    "path": str(entry),
                    "type": "directory",
                })
            elif entry.is_file():
                file_info = {
                    "name": entry.name,
                    "path": str(entry),
                    "type": "file",
                    "size": entry.stat().st_size,
                }
                files.append(file_info)

                # Highlight NIfTI files
                if entry.name.endswith((".nii", ".nii.gz")):
                    nifti_files.append(file_info)
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {path}")

    return {
        "path": str(target),
        "parent": str(target.parent),
        "directories": directories,
        "files": files,
        "nifti_files": nifti_files,
        "total_files": len(files),
        "total_directories": len(directories),
    }


# ---------------------------------------------------------------------------
# DICOM De-identification
# ---------------------------------------------------------------------------

class DeidentifyRequest(BaseModel):
    """DICOM de-identification request."""
    input_dir: str
    output_dir: str = ""
    subject_id: str = "ANON"
    date_offset_days: Optional[int] = None


@app.post("/api/dicom/deidentify")
def deidentify_dicom(request: DeidentifyRequest):
    """De-identify DICOM files by removing PHI tags.

    Strips patient name, DOB, IDs, institution info, and other
    protected health information from DICOM headers.
    """
    from backend.core.dicom_deid import deidentify_dicom_dir

    input_dir = Path(request.input_dir)
    if not input_dir.exists():
        raise HTTPException(status_code=404, detail=f"Input directory not found: {request.input_dir}")

    output_dir = request.output_dir or str(input_dir.parent / f"{input_dir.name}_deid")

    stats = deidentify_dicom_dir(
        str(input_dir),
        output_dir,
        subject_id=request.subject_id,
        date_offset_days=request.date_offset_days,
    )

    try:
        from backend.core.audit import audit_log
        audit_log.record("dicom_deidentified",
                         input_dir=request.input_dir,
                         files_processed=stats.get("files_processed", 0))
    except Exception:
        pass

    return {"output_dir": output_dir, **stats}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=(settings.environment == "development"),
    )
