
'''
NeuroInsight Research - Main API Application

FastAPI application for HPC-native neuroimaging pipeline platform.
'''
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
importshutil
from backend.core.config import get_settings
from backend.core.database import init_db, get_db
from backend.core.pipelines import get_pipeline_registry
from backend.core.plugin_registry import get_plugin_workflow_registry
from backend.execution import get_backend
from backend.models.job import Job, JobStatusEnum
from backend.routes import results
logging.basicConfig(logging.INFO, '%(asctime)s - %(name)s - %(levelname)s - %(message)s', **('level', 'format'))
logger = logging.getLogger(__name__)
settings = get_settings()

def _dispatch_job(job_id = None, spec = None, backend = None):
    """
    Dispatch a job to Celery (preferred) or fall back to local threading.
    
    Serialises the JobSpec into a plain dict so Celery's JSON serialiser
    can transmit it to the worker process.
    """
    spec_dict = {
        'pipeline_name': spec.pipeline_name,
        'container_image': spec.container_image,
        'input_files': spec.input_files,
        'output_dir': spec.output_dir,
        'parameters': spec.parameters,
        'resources': {
            'memory_gb': spec.resources.memory_gb,
            'cpus': spec.resources.cpus,
            'time_hours': spec.resources.time_hours,
            'gpu': spec.resources.gpu,
            'threads': spec.resources.threads,
            'omp_nthreads': spec.resources.omp_nthreads,
            'parallel': spec.resources.parallel },
        'environment': spec.environment,
        'command_template': spec.command_template,
        'plugin_id': spec.plugin_id,
        'workflow_id': spec.workflow_id,
        'execution_mode': spec.execution_mode,
        'data_dir': str(settings.data_dir) }
# WARNING: Decompyle incomplete


def lifespan(app = None):
    '''Application lifespan manager'''
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Backend: {settings.backend_type}")
    init_db()
    pipelines_dir = Path(settings.pipelines_dir)
    if not pipelines_dir.exists():
        pipelines_dir = Path(__file__).parent.parent / 'pipelines'
    registry = get_pipeline_registry(pipelines_dir)
    logger.info(f"Loaded {len(registry.list_pipelines())} legacy pipelines")
    plugins_dir = Path(__file__).parent.parent / 'plugins'
    workflows_dir = Path(__file__).parent.parent / 'workflows'
    pw_registry = get_plugin_workflow_registry(plugins_dir, workflows_dir)
    logger.info(f"Loaded {len(pw_registry.list_plugins())} plugins, {len(pw_registry.list_workflows())} workflows")
# WARNING: Decompyle incomplete

lifespan = None(lifespan)
app = FastAPI(settings.app_name, settings.app_version, 'HPC-native neuroimaging pipeline execution platform', lifespan, **('title', 'version', 'description', 'lifespan'))
app.add_middleware(CORSMiddleware, settings.cors_origins_list, True, [
    '*'], [
    '*'], **('allow_origins', 'allow_credentials', 'allow_methods', 'allow_headers'))
app.include_router(results.router)

def root():
    '''Root endpoint'''
    return {
        'app': settings.app_name,
        'version': settings.app_version,
        'environment': settings.environment,
        'backend': settings.backend_type }

root = app.get('/')(root)

def health_check():
    '''Health check endpoint — reports status of all infrastructure.'''
    services = { }
# WARNING: Decompyle incomplete

health_check = app.get('/health')(health_check)

def get_system_resources():
    '''
    Detect host machine CPU, RAM, and GPU capabilities.
    
    Used by the frontend to show realistic resource limits and
    warn when users request more than the host can provide.
    '''
    detect_all = detect_all
    import backend.core.system_resources
    return detect_all()

get_system_resources = app.get('/api/system/resources')(get_system_resources)

def list_pipelines():
    '''List available pipelines'''
    registry = get_pipeline_registry()
    pipelines = registry.list_pipelines()
    return {
        'pipelines': [ {
'name': p.name,
'version': p.version,
'description': p.description,
'container_image': p.container_image,
'inputs': [{
                    'name': inp.name,
                    'type': inp.type.value,
                    'required': inp.required,
                    'description': inp.description} for inp in p.inputs],
                'parameters': [{
                    'name': param.name,
                    'type': param.type.value,
                    'default': param.default,
                    'description': param.description} for param in p.parameters],
                'resources': {
                    'memory_gb': p.resources.memory_gb,
                    'cpus': p.resources.cpus,
                    'time_hours': p.resources.time_hours,
                    'gpu': p.resources.gpu}} for p in pipelines]}

list_pipelines = app.get('/api/pipelines')(list_pipelines)

def get_pipeline_details(pipeline_name = None):
    '''Get detailed pipeline information'''
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline(pipeline_name)
    if not pipeline:
        raise HTTPException(404, 'Pipeline not found', **('status_code', 'detail'))
    return {
        'name': pipeline.name,
        'version': pipeline.version,
        'description': pipeline.description,
        'container_image': pipeline.container_image,
        'inputs': [ vars(inp) for inp in pipeline.inputs ],
        'parameters': [ vars(param) for param in pipeline.parameters ],
        'resources': vars(pipeline.resources),
        'outputs': [ vars(out) for out in pipeline.outputs ],
        'authors': pipeline.authors,
        'references': pipeline.references }

get_pipeline_details = None(get_pipeline_details)
_FS_LICENSE_PLUGIN_IDS = {
    'fmriprep',
    'fastsurfer',
    'segmentha_t1',
    'segmentha_t2',
    'freesurfer_recon',
    'freesurfer_longitudinal',
    'freesurfer_longitudinal_stats'}

def _plugin_needs_fs_license(plugin = None):
    """Check if a plugin requires a FreeSurfer license.
    
    Detects by: explicit plugin ID list, or YAML inputs containing 'fs_license',
    or environment referencing FS_LICENSE.
    """
    if plugin.id in _FS_LICENSE_PLUGIN_IDS:
        return True
    for inp in None.inputs_required + plugin.inputs_optional:
        if inp.get('key') == 'fs_license':
            return True
        return False


def license_status():
    '''Check FreeSurfer license status.'''
    path = settings.fs_license_resolved
    return {
        'found': path is not None,
        'path': path,
        'search_locations': [
            './license.txt (app directory)',
            './data/license.txt',
            '$FREESURFER_HOME/license.txt',
            '~/.freesurfer/license.txt'],
        'hint': 'Place your FreeSurfer license.txt in the app directory (next to start_dev.sh)' }

license_status = app.get('/api/license/status')(license_status)

def list_plugins(user_selectable_only = None):
    '''List available plugins.
    
    Args:
        user_selectable_only: If true (default), hide utility plugins.
    '''
    pw_registry = get_plugin_workflow_registry()
    plugins = pw_registry.list_plugins(user_selectable_only, **('user_selectable_only',))
    return {
        'plugins': [ p.to_api_dict() for p in plugins ],
        'total': len(plugins) }

list_plugins = None(list_plugins)

def get_plugin(plugin_id = None):
    '''Get detailed plugin information.'''
    pw_registry = get_plugin_workflow_registry()
    plugin = pw_registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(404, f'''Plugin \'{plugin_id}\' not found''', **('status_code', 'detail'))
    return plugin.to_api_dict()

get_plugin = None(get_plugin)

def get_plugin_yaml(plugin_id = None):
    '''Get the raw YAML def inition for a plugin (for docs/review).'''
    pw_registry = get_plugin_workflow_registry()
    plugin = pw_registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(404, f'''Plugin \'{plugin_id}\' not found''', **('status_code', 'detail'))
    import yaml
    return {
        'id': plugin.id,
        'name': plugin.name,
        'yaml': yaml.dump(plugin.raw_yaml, False, False, **('default_flow_style', 'sort_keys')) }

get_plugin_yaml = None(get_plugin_yaml)

def list_workflows():
    '''List available workflows with enriched step info.'''
    pw_registry = get_plugin_workflow_registry()
    workflows = pw_registry.list_workflows()
    return {
        'workflows': [w.to_api_dict(plugin_registry=pw_registry.plugins) for w in workflows],
        'total': len(workflows) }

list_workflows = app.get('/api/workflows')(list_workflows)

def get_workflow(workflow_id = None):
    '''Get detailed workflow information with plugin metadata.'''
    pw_registry = get_plugin_workflow_registry()
    workflow = pw_registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(404, f'''Workflow \'{workflow_id}\' not found''', **('status_code', 'detail'))
    return workflow.to_api_dict(pw_registry.plugins, **('plugin_registry',))

get_workflow = None(get_workflow)

def get_workflow_yaml(workflow_id = None):
    '''Get the raw YAML def inition for a workflow (for docs/review).'''
    pw_registry = get_plugin_workflow_registry()
    workflow = pw_registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(404, f'''Workflow \'{workflow_id}\' not found''', **('status_code', 'detail'))
    import yaml
    return {
        'id': workflow.id,
        'name': workflow.name,
        'yaml': yaml.dump(workflow.raw_yaml, False, False, **('default_flow_style', 'sort_keys')) }

get_workflow_yaml = None(get_workflow_yaml)

def get_docs_all():
    '''Get all plugins and workflows with full details for the docs page.'''
    pw_registry = get_plugin_workflow_registry()
    plugins = pw_registry.list_plugins(False, **('user_selectable_only',))
    workflows = pw_registry.list_workflows()
    import yaml
    return {
        'plugins': None,
        'workflows': [w.to_api_dict(plugin_registry=pw_registry.plugins) for w in workflows],
        'total_plugins': len(plugins),
        'total_workflows': len(workflows) }

get_docs_all = app.get('/api/docs/all')(get_docs_all)

class PluginJobSubmitRequest(BaseModel):
    input_files: list[str] = 'Submit a single-plugin job.'
    parameters: dict = { }
    custom_resources: Optional[dict] = None


def submit_plugin_job(plugin_id = None, request = None, db = app.post('/api/plugins/{plugin_id}/submit')):
    '''Submit a job that runs a single plugin.'''
    pw_registry = get_plugin_workflow_registry()
    plugin = pw_registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(404, f'''Plugin \'{plugin_id}\' not found''', **('status_code', 'detail'))
# WARNING: Decompyle incomplete

submit_plugin_job = None(submit_plugin_job)

class WorkflowJobSubmitRequest(BaseModel):
    input_files: list[str] = 'Submit a workflow job (multi-step).'
    parameters: dict = { }
    custom_resources: Optional[dict] = None


def submit_workflow_job(workflow_id = None, request = None, db = app.post('/api/workflows/{workflow_id}/submit')):
    '''
    Submit a workflow job that chains multiple plugins.
    
    Each step runs sequentially, passing outputs to the next step.
    '''
    pw_registry = get_plugin_workflow_registry()
    workflow = pw_registry.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(404, f'''Workflow \'{workflow_id}\' not found''', **('status_code', 'detail'))
    for step in workflow.steps:
        if not pw_registry.get_plugin(step.uses):
            raise HTTPException(500, f"Workflow references unknown plugin: {step.uses}", **('status_code', 'detail'))
# WARNING: Decompyle incomplete

submit_workflow_job = None(submit_workflow_job)

class JobSubmitRequest(BaseModel):
    input_files: list[str] = 'Job submission request model'
    parameters: dict = { }
    custom_resources: Optional[dict] = None


def submit_job(request = None, db = None):
    '''
    Submit a job for execution.
    
    Args:
        request: Job submission parameters (JSON body)
        
    Returns:
        Job information including job_id
    '''
    pipeline_name = request.pipeline_name
    input_files = request.input_files
    parameters = request.parameters
    custom_resources = request.custom_resources
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline(pipeline_name)
    if not pipeline:
        raise HTTPException(404, f'''Pipeline \'{pipeline_name}\' not found''', **('status_code', 'detail'))
    merged_params = pipeline.get_parameter_defaults()
    merged_params.update(parameters)
    validation_errors = pipeline.validate_parameters(merged_params)
    if validation_errors:
        raise HTTPException(400, {
            'errors': validation_errors }, **('status_code', 'detail'))
# WARNING: Decompyle incomplete

submit_job = None(submit_job)

def list_jobs(status = None, limit = None, db = app.get('/api/jobs')):
    '''List jobs with optional status filter'''
    query = db.query(Job).filter(Job.deleted == False)
    if status:
        query = query.filter(Job.status == status)
    query = query.order_by(Job.submitted_at.desc()).limit(limit)
    jobs = query.all()
    return {
        'jobs': [ job.to_dict() for job in jobs ] }

list_jobs = None(list_jobs)

def get_jobs_progress(db = None):
    '''Lightweight endpoint return ing progress for all active (non-terminal) jobs.
    
    Returns a list of {id, status, progress, current_phase} for every
    pending or running job.  Frontend polls this at ~2-3s intervals to
    animate the progress bars without fetching full job payloads.
    '''
    active_jobs = db.query(Job).filter(Job.deleted == False, Job.status.in_([
        'pending',
        'running'])).all()
    return {
        'jobs': [ {
'id': j.id,
'status': j.status,
'progress': 0,
'current_phase': j.current_phase } for j in active_jobs if j.progress ] }

get_jobs_progress = None(get_jobs_progress)

def get_job(job_id = None, db = None):
    '''Get job details'''
    job = db.query(Job).filter(Job.id == job_id, Job.deleted == False).first()
    if not job:
        raise HTTPException(404, 'Job not found', **('status_code', 'detail'))
# WARNING: Decompyle incomplete

get_job = None(get_job)

def cancel_job(job_id = None, db = None):
    '''Cancel a running job'''
    job = db.query(Job).filter(Job.id == job_id, Job.deleted == False).first()
    if not job:
        raise HTTPException(404, 'Job not found', **('status_code', 'detail'))
    if job.is_terminal:
        raise HTTPException(400, 'Job already in terminal state', **('status_code', 'detail'))
# WARNING: Decompyle incomplete

cancel_job = None(cancel_job)

def get_job_logs(job_id = None):
    '''Get job logs'''
    pass
# WARNING: Decompyle incomplete

get_job_logs = None(get_job_logs)

def delete_job(job_id = None, db = None):
    '''
    Delete a job and its database record.
    
    Note: This only deletes the database record. 
    Actual job cancellation must be done via the cancel endpoint first.
    '''
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, f'''Job \'{job_id}\' not found''', **('status_code', 'detail'))
# WARNING: Decompyle incomplete

delete_job = None(delete_job)

async def upload_file(file = None):
    '''
    Upload a single file to the server.
    
    Args:
        file: File uploaded via multipart/form-data
        
    Returns:
        File path on server
    '''
    pass
# WARNING: Decompyle incomplete

upload_file = None(upload_file)

def browse_directory(path = None, backend_type = None):
    """
    Browse directory to list files.
    
    Args:
        path: Directory path to browse
        backend_type: 'local' or 'hpc'
    
    Returns:
        Directory contents with NIfTI files highlighted
    """
    import os
    import glob
# WARNING: Decompyle incomplete

browse_directory = None(browse_directory)

def submit_batch_job(pipeline_name, input_dir = None, output_dir = None, parameters = app.post('/api/jobs/submit-batch'), file_pattern = ({ }, '*.nii.gz', Depends(get_db)), db = ('pipeline_name', str, 'input_dir', str, 'output_dir', str, 'parameters', dict, 'file_pattern', str, 'db', Session)):
    '''
    Submit batch job to process all files in a directory.
    
    Args:
        pipeline_name: Name of pipeline to run
        input_dir: Directory containing input files
        output_dir: Directory for output (subdirectories created per file)
        parameters: Pipeline parameters
        file_pattern: Glob pattern for file selection
    
    Returns:
        Batch job submission result with job IDs
    '''
    Path = Path
    import pathlib
    import glob as glob_module
    registry = get_pipeline_registry()
    pipeline = registry.get_pipeline(pipeline_name)
    if not pipeline:
        raise HTTPException(404, f'''Pipeline \'{pipeline_name}\' not found''', **('status_code', 'detail'))
    input_path = Path(input_dir)
    if not input_path.exists() or input_path.is_dir():
        raise HTTPException(400, f"Input directory not found: {input_dir}", **('status_code', 'detail'))
    pattern = str(input_path / file_pattern)
    input_files = glob_module.glob(pattern)
    if not input_files:
        raise HTTPException(400, f'''No files matching \'{file_pattern}\' found in {input_dir}''', **('status_code', 'detail'))
# WARNING: Decompyle incomplete

submit_batch_job = None(submit_batch_job)
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('backend.main:app', settings.api_host, settings.api_port, settings.environment == 'development', **('host', 'port', 'reload'))
    return None
