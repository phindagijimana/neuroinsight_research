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
from backend.routes import platform as platform_routes
from backend.routes import transfer as transfer_routes

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

    # Reap any jobs orphaned by previous worker crashes
    try:
        from backend.core.stale_job_reaper import reap_stale_jobs
        reaped = reap_stale_jobs()
        if reaped:
            logger.info(f"Startup reaper finalised {len(reaped)} orphaned jobs")
    except Exception as e:
        logger.warning(f"Startup stale-job reap failed: {e}")

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
app.include_router(platform_routes.router)
app.include_router(transfer_routes.router)


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


@app.post("/api/jobs/reap-stale")
def reap_stale_jobs_endpoint():
    """Manually trigger stale-job reaper to finalise orphaned jobs."""
    from backend.core.stale_job_reaper import reap_stale_jobs
    reaped = reap_stale_jobs()
    return {"reaped": len(reaped), "jobs": reaped}


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
        "workflows": [
            {
                **w.to_api_dict(plugin_registry=pw_registry.plugins),
                "yaml": yaml.dump(w.raw_yaml, default_flow_style=False, sort_keys=False),
            }
            for w in workflows
        ],
        "total_plugins": len(plugins),
        "total_workflows": len(workflows),
    }


# ---------------------------------------------------------------------------
# License Status
# ---------------------------------------------------------------------------

@app.get("/api/license/status")
def license_status():
    """Check FreeSurfer and MELD Graph license status."""
    fs_path = settings.fs_license_resolved
    meld_path = settings.meld_license_resolved
    return {
        "freesurfer": {
            "found": fs_path is not None,
            "path": fs_path,
            "required_by": ["FreeSurfer", "FastSurfer", "fMRIPrep", "MELD Graph"],
            "registration_url": "https://surfer.nmr.mgh.harvard.edu/registration.html",
            "search_locations": [
                "./license.txt",
                "./data/license.txt",
                "$FREESURFER_HOME/license.txt",
                "~/.freesurfer/license.txt",
            ],
        },
        "meld_graph": {
            "found": meld_path is not None,
            "path": meld_path,
            "required_by": ["MELD Graph (v2.2.4+)"],
            "registration_url": "https://docs.google.com/forms/d/e/1FAIpQLSdocMWtxbmh9T7Sv8NT4f0Kpev-tmRI-kngDhUeBF9VcZXcfg/viewform",
            "search_locations": [
                "./meld_license.txt",
                "./data/meld_license.txt",
                "~/.meld/meld_license.txt",
            ],
        },
        "hint": "Place license files in the project root directory (same folder as ./research).",
    }


# ---------------------------------------------------------------------------
# Job Submission -- Plugins
# ---------------------------------------------------------------------------

class PluginJobSubmitRequest(BaseModel):
    """Submit a single-plugin job."""
    input_files: List[str]
    parameters: dict = {}
    custom_resources: Optional[dict] = None
    data_source_platform: Optional[str] = None
    data_source_dataset_id: Optional[str] = None


# Plugins that require the MELD Graph license (meld_license.txt)
MELD_LICENSE_PLUGINS = {"meld_graph"}

# Plugins that require the FreeSurfer license (license.txt)
FS_LICENSE_PLUGINS = {
    "freesurfer_recon", "freesurfer_autorecon_volonly", "fastsurfer",
    "fmriprep", "meld_graph", "segmentha_t1", "segmentha_t2",
    "freesurfer_longitudinal", "freesurfer_longitudinal_stats",
}


def _check_licenses(plugin_ids: List[str]):
    """Check that required license files are present before job submission.

    Raises HTTPException with a clear message if a license is missing.
    """
    needs_fs = any(pid in FS_LICENSE_PLUGINS for pid in plugin_ids)
    needs_meld = any(pid in MELD_LICENSE_PLUGINS for pid in plugin_ids)

    if needs_fs and not settings.fs_license_resolved:
        raise HTTPException(
            status_code=400,
            detail=(
                "FreeSurfer license.txt not found. "
                "Register for free at https://surfer.nmr.mgh.harvard.edu/registration.html "
                "and place the license.txt file in the project root directory."
            ),
        )

    if needs_meld and not settings.meld_license_resolved:
        raise HTTPException(
            status_code=400,
            detail=(
                "MELD Graph meld_license.txt not found. "
                "Register at https://docs.google.com/forms/d/e/1FAIpQLSdocMWtxbmh9T7Sv8NT4f0Kpev-tmRI-kngDhUeBF9VcZXcfg/viewform "
                "and place the meld_license.txt file in the project root directory "
                "(same location as your FreeSurfer license.txt)."
            ),
        )


@app.post("/api/plugins/{plugin_id}/submit")
def submit_plugin_job(plugin_id: str, request: PluginJobSubmitRequest, db: Session = Depends(get_db)):
    """Submit a job that runs a single plugin."""
    pw_registry = get_plugin_workflow_registry()
    plugin = pw_registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")

    # Check required licenses before submitting
    _check_licenses([plugin_id])

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

    params = dict(request.parameters)
    params["_plugin_id"] = plugin_id

    spec = JobSpec(
        pipeline_name=plugin.name,
        container_image=plugin.container_image,
        input_files=request.input_files,
        output_dir=output_dir,
        parameters=params,
        resources=resources,
        plugin_id=plugin_id,
        execution_mode="plugin",
    )

    # Submit via backend
    backend = get_backend()
    backend.submit_job(spec, job_id=job_id)

    # Persist data-source provenance if the job originated from a platform
    if request.data_source_platform:
        try:
            from backend.models.job import Job
            job_row = db.query(Job).filter(Job.id == job_id).first()
            if job_row:
                job_row.data_source_platform = request.data_source_platform
                job_row.data_source_dataset_id = request.data_source_dataset_id
                db.commit()
        except Exception:
            db.rollback()

    try:
        from backend.core.audit import audit_log
        audit_log.record("job_submitted", job_id=job_id, plugin_id=plugin_id, mode="plugin")
    except Exception as e:
        logger.debug("Audit log unavailable: %s", e)

    return {"job_id": job_id, "status": "pending", "plugin": plugin_id}


# ---------------------------------------------------------------------------
# Job Submission -- Workflows
# ---------------------------------------------------------------------------

class WorkflowJobSubmitRequest(BaseModel):
    """Submit a workflow job (multi-step)."""
    input_files: List[str]
    parameters: dict = {}
    custom_resources: Optional[dict] = None
    data_source_platform: Optional[str] = None
    data_source_dataset_id: Optional[str] = None


@app.post("/api/workflows/{workflow_id}/submit")
def submit_workflow_job(workflow_id: str, request: WorkflowJobSubmitRequest, db: Session = Depends(get_db)):
    """Submit a workflow job that chains multiple plugins."""
    pw_registry = get_plugin_workflow_registry()
    workflow = pw_registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    # Validate all steps reference valid plugins
    step_plugin_ids = []
    for step in workflow.steps:
        if not pw_registry.get_plugin(step.uses):
            raise HTTPException(
                status_code=500,
                detail=f"Workflow references unknown plugin: {step.uses}",
            )
        step_plugin_ids.append(step.uses)

    # Check required licenses for all plugins in the workflow
    _check_licenses(step_plugin_ids)

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

    # Persist data-source provenance if the job originated from a platform
    if request.data_source_platform:
        try:
            from backend.models.job import Job
            job_row = db.query(Job).filter(Job.id == job_id).first()
            if job_row:
                job_row.data_source_platform = request.data_source_platform
                job_row.data_source_dataset_id = request.data_source_dataset_id
                db.commit()
        except Exception:
            db.rollback()

    try:
        from backend.core.audit import audit_log
        audit_log.record("job_submitted", job_id=job_id, workflow_id=workflow_id, mode="workflow")
    except Exception as e:
        logger.debug("Audit log unavailable: %s", e)

    return {"job_id": job_id, "status": "pending", "workflow": workflow_id}


# ---------------------------------------------------------------------------
# Workflow Batch Submission (all subjects in a BIDS directory)
# ---------------------------------------------------------------------------

class WorkflowBatchSubmitRequest(BaseModel):
    """Submit a workflow for every subject in a BIDS directory."""
    bids_dir: str
    parameters: dict = {}
    custom_resources: Optional[dict] = None
    subject_ids: Optional[List[str]] = None
    data_source_platform: Optional[str] = None
    data_source_dataset_id: Optional[str] = None


@app.post("/api/workflows/{workflow_id}/submit-batch")
def submit_workflow_batch(workflow_id: str, request: WorkflowBatchSubmitRequest, db: Session = Depends(get_db)):
    """Submit a workflow job for every subject in a BIDS directory.

    Auto-discovers sub-* directories. Each subject gets its own SLURM job
    so they run in parallel.  Optionally pass subject_ids to limit which
    subjects are processed.
    """
    pw_registry = get_plugin_workflow_registry()
    workflow = pw_registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    step_plugin_ids = [step.uses for step in workflow.steps]
    _check_licenses(step_plugin_ids)

    # Discover subjects -- via SSH for SLURM, local filesystem otherwise
    bids_dir = request.bids_dir
    subject_ids = request.subject_ids

    if not subject_ids:
        backend = get_backend()
        backend_type = getattr(backend, "backend_type", "local")

        if backend_type == "slurm":
            from backend.core.ssh_manager import get_ssh_manager
            ssh = get_ssh_manager()
            if not ssh.is_connected:
                raise HTTPException(status_code=503, detail="SSH not connected to HPC")
            exit_code, stdout, _ = ssh.execute(
                f'ls -d "{bids_dir}"/sub-* 2>/dev/null | xargs -I{{}} basename {{}}',
                timeout=15,
            )
            subject_ids = [
                d.replace("sub-", "")
                for d in stdout.strip().split("\n")
                if d.strip().startswith("sub-")
            ]
        else:
            from pathlib import Path as _P
            bids_path = _P(bids_dir)
            if not bids_path.is_dir():
                raise HTTPException(status_code=400, detail=f"BIDS directory not found: {bids_dir}")
            subject_ids = sorted(
                d.name.replace("sub-", "")
                for d in bids_path.iterdir()
                if d.is_dir() and d.name.startswith("sub-")
            )

    if not subject_ids:
        raise HTTPException(
            status_code=400,
            detail=f"No sub-* directories found in {bids_dir}",
        )

    # Resolve resources from first step plugin
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

    # Submit one job per subject
    submitted = []
    errors = []
    backend = get_backend()

    for sid in subject_ids:
        try:
            job_id = str(uuid.uuid4())
            output_dir = str(Path(settings.data_dir) / "outputs" / job_id)

            params = dict(request.parameters)
            params["subject_id"] = sid
            params["_plugin_id"] = step_plugin_ids[0] if len(step_plugin_ids) == 1 else ""
            params["_workflow_steps"] = step_plugin_ids
            params["_workflow_id"] = workflow_id

            spec = JobSpec(
                pipeline_name=workflow.name,
                container_image=first_plugin.container_image,
                input_files=[bids_dir],
                output_dir=output_dir,
                parameters=params,
                resources=resources,
                workflow_id=workflow_id,
                execution_mode="workflow",
            )

            backend.submit_job(spec, job_id=job_id)

            if request.data_source_platform:
                try:
                    job_row = db.query(Job).filter(Job.id == job_id).first()
                    if job_row:
                        job_row.data_source_platform = request.data_source_platform
                        job_row.data_source_dataset_id = request.data_source_dataset_id
                        db.commit()
                except Exception:
                    db.rollback()

            submitted.append({"job_id": job_id, "subject_id": sid})
        except Exception as e:
            errors.append({"subject_id": sid, "error": str(e)})
            logger.error("Batch submit failed for subject %s: %s", sid, e)

    return {
        "workflow": workflow_id,
        "bids_dir": bids_dir,
        "total_subjects": len(subject_ids),
        "submitted": len(submitted),
        "jobs": submitted,
        "errors": errors,
    }


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
# Reusable Outputs -- pick completed job results as inputs for new jobs
# ---------------------------------------------------------------------------

# Which plugin outputs satisfy which input keys, and where on disk
_OUTPUT_TYPE_MAP = {
    "freesurfer_recon":             {"provides": "subjects_dir",               "subpath": "native/freesurfer/SUBJECTS_DIR"},
    "freesurfer_autorecon_volonly":  {"provides": "subjects_dir",               "subpath": "native/freesurfer/SUBJECTS_DIR"},
    "fastsurfer":                   {"provides": "subjects_dir",               "subpath": "native/fastsurfer"},
    "freesurfer_longitudinal":      {"provides": "subjects_dir",               "subpath": "native/freesurfer/SUBJECTS_DIR"},
    "qsiprep":                      {"provides": "qsiprep_derivatives",        "subpath": "native/qsiprep"},
    "qsirecon":                     {"provides": "qsirecon_derivatives",       "subpath": "native/qsirecon"},
    "fmriprep":                     {"provides": "fmriprep_derivatives",       "subpath": "native/fmriprep"},
    "xcpd":                         {"provides": "xcpd_derivatives",           "subpath": "native/xcpd"},
}

# Which input keys each plugin/workflow step accepts for chaining
_INPUT_ACCEPTS = {
    "subjects_dir":             ["meld_graph", "hs_postprocess", "segmentha_t1", "segmentha_t2",
                                  "freesurfer_longitudinal", "freesurfer_longitudinal_stats"],
    "freesurfer_subjects_dir":  ["meld_graph"],
    "qsiprep_derivatives":      ["qsirecon"],
    "fmriprep_derivatives":     ["xcpd"],
}


@app.get("/api/jobs/reusable-outputs")
def list_reusable_outputs(
    input_type: Optional[str] = Query(None, description="Filter by input type needed (e.g. subjects_dir, qsiprep_derivatives)"),
    plugin_id: Optional[str] = Query(None, description="Filter to outputs usable by this plugin"),
    workflow_id: Optional[str] = Query(None, description="Filter to outputs usable by this workflow's steps"),
    db: Session = Depends(get_db),
):
    """List completed jobs whose outputs can be reused as inputs for new jobs.

    Returns output paths that can be plugged into a new job's input_files or
    parameters, avoiding redundant re-computation.
    """
    # Determine which output types are relevant
    wanted_types: set[str] = set()
    if input_type:
        wanted_types.add(input_type)
    if plugin_id:
        for itype, consumers in _INPUT_ACCEPTS.items():
            if plugin_id in consumers:
                wanted_types.add(itype)
    if workflow_id:
        pw_registry = get_plugin_workflow_registry()
        wf = pw_registry.get_workflow(workflow_id)
        if wf:
            for step in wf.steps:
                for itype, consumers in _INPUT_ACCEPTS.items():
                    if step.uses in consumers:
                        wanted_types.add(itype)

    # Find completed jobs that produce matching outputs
    completed = (
        db.query(Job)
        .filter(Job.deleted == False, Job.status == "completed")
        .order_by(Job.completed_at.desc())
        .limit(200)
        .all()
    )

    results_list = []
    for job in completed:
        params = job.parameters or {}
        job_plugin_id = params.get("_plugin_id", "")

        # For workflow jobs, scan all step plugin_ids
        plugin_ids_in_job = []
        if job_plugin_id:
            plugin_ids_in_job.append(job_plugin_id)
        pipeline = job.pipeline_name or ""
        if pipeline.startswith("workflow:"):
            wf_id = pipeline.replace("workflow:", "")
            pw_registry = get_plugin_workflow_registry()
            wf = pw_registry.get_workflow(wf_id)
            if wf:
                plugin_ids_in_job.extend(s.uses for s in wf.steps)

        for pid in plugin_ids_in_job:
            mapping = _OUTPUT_TYPE_MAP.get(pid)
            if not mapping:
                continue
            provides = mapping["provides"]
            if wanted_types and provides not in wanted_types:
                continue

            output_base = job.output_dir or ""
            output_path = f"{output_base}/{mapping['subpath']}" if output_base else ""

            subject_id = params.get("subject_id", "")

            results_list.append({
                "job_id": job.id,
                "job_pipeline": job.pipeline_name,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "subject_id": subject_id,
                "provides": provides,
                "plugin_id": pid,
                "output_path": output_path,
            })

    return {"outputs": results_list}


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
    For SLURM jobs, queries live status from the HPC scheduler via SSH.
    Uses a single batched squeue call instead of one per job.
    """
    active_jobs = (
        db.query(Job)
        .filter(Job.deleted == False, Job.status.in_(["pending", "running"]))
        .all()
    )

    # Batch-query SLURM statuses in a single SSH call
    slurm_jobs = {
        j.backend_job_id: j
        for j in active_jobs
        if j.backend_type == "slurm" and j.backend_job_id
    }
    slurm_statuses: dict[str, str] = {}
    if slurm_jobs:
        slurm_statuses = _poll_slurm_status_batch(list(slurm_jobs.keys()))

    import time as _t
    _progress_deadline = _t.time() + 12  # max 12s on log polling

    results = []
    for j in active_jobs:
        status = j.status
        progress = j.progress or 0
        phase = j.current_phase

        if j.backend_type == "slurm" and j.backend_job_id:
            new_status = slurm_statuses.get(j.backend_job_id)
            if new_status and new_status != status:
                status = new_status
                j.status = status
                if status == "running" and not j.started_at:
                    from datetime import datetime
                    j.started_at = datetime.utcnow()
                    phase = "Running on HPC"
                    j.current_phase = phase
                if status in ("completed", "failed", "cancelled"):
                    from datetime import datetime
                    j.completed_at = datetime.utcnow()
                    if status == "completed":
                        progress = 100
                        phase = "Completed"
                        j.progress = 100
                        j.current_phase = "Completed"
                    _slurm_progress_cache.pop(j.id, None)
                try:
                    db.commit()
                except Exception:
                    db.rollback()

            if status == "running" and _t.time() < _progress_deadline:
                prog_result = _poll_slurm_progress(j)
                if prog_result:
                    new_progress, new_phase = prog_result
                    if new_progress > progress:
                        progress = new_progress
                        phase = new_phase
                        j.progress = progress
                        j.current_phase = phase
                        try:
                            db.commit()
                        except Exception:
                            db.rollback()

        results.append({
            "id": j.id,
            "status": status,
            "progress": progress,
            "current_phase": phase,
        })

    return {"jobs": results}


_SLURM_STATUS_MAP = {
    "PENDING": "pending", "RUNNING": "running",
    "COMPLETING": "running", "COMPLETED": "completed",
    "FAILED": "failed", "CANCELLED": "cancelled",
    "TIMEOUT": "failed", "NODE_FAIL": "failed",
    "OUT_OF_MEMORY": "failed", "PREEMPTED": "failed",
}


def _poll_slurm_status_batch(slurm_job_ids: list[str]) -> dict[str, str]:
    """Query SLURM statuses for multiple jobs in a single SSH call.

    Returns {slurm_job_id: mapped_status} for jobs with a known state.
    """
    if not slurm_job_ids:
        return {}

    try:
        from backend.core.ssh_manager import get_ssh_manager
        ssh = get_ssh_manager()
        if not ssh.is_connected:
            if ssh.host and ssh.username:
                try:
                    ssh.connect()
                    logger.info("Auto-reconnected SSH for SLURM status polling")
                except Exception:
                    pass
            if not ssh.is_connected:
                return {}

        id_list = ",".join(slurm_job_ids)
        exit_code, stdout, _ = ssh.execute(
            f"squeue -j {id_list} --noheader -o '%i %T' 2>/dev/null; "
            f"sacct -j {id_list} --noheader --format=JobID,State -P 2>/dev/null",
            timeout=15,
        )

        results: dict[str, str] = {}
        for line in stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 2:
                jid = parts[0].split("|")[0].split(".")[0].strip()
                state = parts[-1].split("+")[0].strip().upper()
                if jid in slurm_job_ids or jid in {s.split("_")[0] for s in slurm_job_ids}:
                    mapped = _SLURM_STATUS_MAP.get(state)
                    if mapped and jid not in results:
                        results[jid] = mapped
        return results
    except Exception as e:
        logger.debug("Batched SLURM status poll failed: %s", e)
        return {}


def _poll_slurm_status(slurm_job_id: str) -> str | None:
    """Query SLURM for a single job's status (fallback, prefer batch)."""
    result = _poll_slurm_status_batch([slurm_job_id])
    return result.get(slurm_job_id)


# ---------------------------------------------------------------------------
# SLURM Log-Based Progress Tracking
# ---------------------------------------------------------------------------
import time as _time
import re as _re

_slurm_progress_cache: dict[str, tuple[float, int, str]] = {}
_SLURM_PROGRESS_POLL_INTERVAL = 30  # seconds between log reads per job


def _poll_slurm_progress(job: "Job") -> tuple[int, str] | None:
    """Parse progress from a SLURM job's container log via SSH.

    Reads the tail of the log file, matches against phase milestones,
    and returns (progress_pct, phase_label).  Rate-limited to avoid
    excessive SSH traffic.
    """
    now = _time.time()
    cached = _slurm_progress_cache.get(job.id)
    if cached:
        last_read, cached_progress, cached_phase = cached
        if now - last_read < _SLURM_PROGRESS_POLL_INTERVAL:
            return (cached_progress, cached_phase)

    try:
        from backend.core.ssh_manager import get_ssh_manager
        ssh = get_ssh_manager()
        if not ssh.is_connected:
            return cached[1:] if cached else None

        params = job.parameters or {}
        plugin_id = params.get("_plugin_id", "")
        workflow_steps = params.get("_workflow_steps", [])
        output_dir = job.output_dir  # e.g. ~/neuroinsight/jobs/{id}/outputs

        log_content = ""
        active_plugin_id = plugin_id
        step_offset_pct = 0  # base percentage offset for workflow steps

        # Read last 200KB of log — large enough to capture recent phase markers
        # even for verbose pipelines like FreeSurfer
        _TAIL_BYTES = 204800

        if workflow_steps:
            # Workflow job: find the latest active step log (check newest first)
            total_steps = len(workflow_steps)
            workflow_id = params.get("_workflow_id", "")
            from backend.core.phase_milestones import get_workflow_step_weights
            weights = get_workflow_step_weights(workflow_id, total_steps)

            for step_idx in range(total_steps - 1, -1, -1):
                step_num = step_idx + 1
                step_pid = workflow_steps[step_idx]
                log_path = f"{output_dir}/logs/step_{step_num}_{step_pid}.log"
                exit_code, stdout, _ = ssh.execute(
                    f"tail -c {_TAIL_BYTES} {log_path} 2>/dev/null", timeout=15,
                )
                if stdout.strip():
                    log_content = stdout
                    active_plugin_id = step_pid
                    step_offset_pct = sum(weights[:step_idx]) * 100
                    break
        else:
            log_path = f"{output_dir}/logs/container.log"
            exit_code, stdout, _ = ssh.execute(
                f"tail -c {_TAIL_BYTES} {log_path} 2>/dev/null", timeout=15,
            )
            log_content = stdout

        if not log_content.strip():
            # No container log yet — check SLURM stdout for setup messages
            slurm_id = job.backend_job_id
            if slurm_id:
                job_dir = output_dir.rstrip("/").rsplit("/outputs", 1)[0]
                slurm_log = f"{job_dir}/logs/slurm-{slurm_id}.out"
                exit_code, stdout, _ = ssh.execute(
                    f"tail -c {_TAIL_BYTES} {slurm_log} 2>/dev/null", timeout=15,
                )
                if stdout.strip():
                    log_content = stdout
                    if not active_plugin_id:
                        active_plugin_id = ""

        if not log_content.strip():
            result = (0, "Running on HPC")
            _slurm_progress_cache[job.id] = (now, *result)
            return result

        from backend.core.phase_milestones import get_milestones
        milestones = get_milestones(active_plugin_id)

        best_progress = 0
        best_label = ""
        for marker, pct, label in milestones:
            if pct > best_progress:
                try:
                    if _re.search(marker, log_content):
                        best_progress = pct
                        best_label = label
                except _re.error:
                    if marker in log_content:
                        best_progress = pct
                        best_label = label

        # For workflow jobs, scale step progress into overall progress
        if workflow_steps:
            total_steps = len(workflow_steps)
            workflow_id = params.get("_workflow_id", "")
            from backend.core.phase_milestones import get_workflow_step_weights
            weights = get_workflow_step_weights(workflow_id, total_steps)
            active_step_idx = 0
            for i, pid in enumerate(workflow_steps):
                if pid == active_plugin_id:
                    active_step_idx = i
                    break
            step_pct_range = weights[active_step_idx] * 100
            best_progress = int(step_offset_pct + (best_progress * step_pct_range / 100))
            best_progress = min(best_progress, 99)

        # Preserve the previously known phase label if no milestone matched
        if not best_label:
            if cached:
                best_label = cached[2]
            elif job.current_phase:
                best_label = job.current_phase
            else:
                best_label = "Running on HPC"

        _slurm_progress_cache[job.id] = (now, best_progress, best_label)
        return (best_progress, best_label)

    except Exception as e:
        logger.debug("SLURM progress parse failed for %s: %s", job.id[:8], e)
        return cached[1:] if cached else None


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
        except Exception as e:
            logger.debug("Could not refresh live progress for job %s: %s", job_id[:8], e)

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
    """Delete a job -- stops the container first if still running."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    container_stopped = False
    if job.status in ("pending", "running"):
        try:
            backend = get_backend()
            backend.cancel_job(job_id)
            container_stopped = True
            logger.info(f"Stopped running job {job_id[:8]} before deletion")
        except Exception as e:
            logger.warning(f"Could not stop job {job_id[:8]} before deletion: {e}")

    job.soft_delete()
    db.commit()

    msg = f"Job {job_id} deleted"
    if container_stopped:
        msg += " (container stopped)"
    return {"message": msg}


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
    except Exception as e:
        logger.debug("Audit log unavailable: %s", e)

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
