
'''
Pipeline Plugin System

A flexible, YAML-based system for def ining and managing neuroimaging pipelines.

DESIGN PHILOSOPHY:
- Pipeline-Agnostic: Easy integration of new analysis tools
- Declarative: YAML def initions separate configuration from code
- Type-Safe: Pydantic-like validation with dataclasses
- Versioned: Each pipeline tracks its version for reproducibility

PIPELINE LIFECYCLE:
1. Definition: Create YAML file in pipelines/ directory
2. Loading: PipelineRegistry scans and validates YAML files
3. Registration: Valid pipelines added to registry
4. Discovery: Frontend queries /api/pipelines endpoint
5. Execution: Backend creates JobSpec from pipeline def inition
6. Validation: Inputs and parameters validated before submission

YAML STRUCTURE:
    name: pipeline_name              # Unique identifier
    version: 1.0.0                   # Semantic version
    description: "..."               # Human-readable description
    container_image: docker/image    # Container for execution
    inputs:                          # Required/optional input files
      - name: t1w
        type: nifti
        required: true
    parameters:                      # Configurable parameters
      - name: threads
        type: int
        default: 8
    resources:                       # Default resource requirements
      memory_gb: 32
      cpus: 8
      time_hours: 6
      gpu: false
    outputs:                         # Expected output files
      - name: segmentation
        path: segmentation.nii.gz
    command: "run_pipeline.sh"       # Execution command

NEUROIMAGING CONTEXT:
- Supports standard formats: NIfTI, DICOM, BIDS
- Compatible with: FreeSurfer, FSL, ANTS, AFNI, SPM
- Container-based: Docker (local) or Singularity (HPC)
- Follows BIDS conventions where applicable
'''
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
logger = logging.getLogger(__name__)

class InputType(Enum):
    '''
    Supported input file types for neuroimaging pipelines
    
    NIFTI: Neuroimaging Informatics Technology Initiative format (.nii, .nii.gz)
           Standard for structural and functional MRI, DTI, etc.
           
    DICOM: Digital Imaging and Communications in Medicine (.dcm)
           Raw scanner output, converted to NIfTI for processing
           
    TEXT: Plain text files (e.g., .bval, .bvec for diffusion imaging)
          B-values and gradient directions for DTI/DWI
          
    JSON: Metadata files (e.g., BIDS sidecar JSON)
          Acquisition parameters, scan metadata
    '''
    NIFTI = 'nifti'
    DICOM = 'dicom'
    TEXT = 'text'
    JSON = 'json'


class ParameterType(Enum):
    '''
    Supported parameter types for pipeline configuration
    
    INT: Integer values (e.g., threads=8, batch_size=16)
    FLOAT: Floating point (e.g., resolution=1.5, threshold=0.95)
    STRING: Text values (e.g., atlas="DKT", method="eddy")
    BOOL: Boolean flags (e.g., use_gpu=true, seg_only=false)
    CHOICE: Enumerated options (e.g., model=["eddy", "topup", "both"])
    '''
    INT = 'int'
    FLOAT = 'float'
    STRING = 'string'
    BOOL = 'bool'
    CHOICE = 'choice'

# NOTE: InputSpec dataclass def inition (decompiler artifact - see original)
# NOTE: ParameterSpec dataclass def inition (decompiler artifact - see original)
# NOTE: ResourceRequirements dataclass def inition (decompiler artifact - see original)
# NOTE: OutputSpec dataclass def inition (decompiler artifact - see original)
# NOTE: PipelineDefinition dataclass def inition (decompiler artifact - see original)

class PipelineRegistry:
    '''
    Registry for pipeline discovery and management
    
    Implements the Plugin Pattern for neuroimaging pipelines.
    Pipelines are defined in YAML files and loaded dynamically at startup.
    
    Features:
    - Automatic discovery: Scans directory for .yaml/.yml files
    - Lazy loading: Pipelines loaded once at startup
    - Validation: YAML validated against schema
    - Caching: Definitions cached in memory
    - Hot reload: Can reload without restarting application
    
    Thread Safety:
    - Read operations (get_pipeline, list_pipelines) are thread-safe
    - Write operations (reload) should be called during startup only
    
    Usage:
        registry = PipelineRegistry(Path("./pipelines"))
        pipeline = registry.get_pipeline("freesurfer_hippocampus")
        all_pipelines = registry.list_pipelines()
    '''
    
    def __init__(self = None, pipelines_dir = None):
        """
        Initialize pipeline registry
        
        Args:
            pipelines_dir: Directory containing pipeline YAML files
            
        Raises:
            Warning: If directory doesn't exist (not fatal, allows testing)
        """
        self.pipelines_dir = Path(pipelines_dir)
        self.pipelines = { }
        if self.pipelines_dir.exists():
            self._load_pipelines()
            logger.info(f"Pipeline registry initialized with {len(self.pipelines)} pipelines")
            return None
        None.warning(f"Pipelines directory not found: {pipelines_dir}. No pipelines will be available. Create directory and add YAML files.")

    
    def _load_pipelines(self = None):
        '''
        Scan directory and load all pipeline YAML files
        
        Internal method called during initialization and reload.
        Supports both .yaml and .yml extensions.
        Logs errors but continues loading other pipelines if one fails.
        '''
        yaml_files = list(self.pipelines_dir.glob('*.yaml')) + list(self.pipelines_dir.glob('*.yml'))
        if not yaml_files:
            logger.warning(f"No pipeline YAML files found in {self.pipelines_dir}")
            return None
        None.info(f"Found {len(yaml_files)} pipeline def inition files")
        loaded_count = 0
        failed_count = 0
    # WARNING: Decompyle incomplete

    
    def get_pipeline(self = None, name = None):
        '''
        Get pipeline def inition by name
        
        Args:
            name: Pipeline identifier
            
        Returns:
            PipelineDefinition if found, None otherwise
            
        Example:
            pipeline = registry.get_pipeline("freesurfer_hippocampus")
            if pipeline:
                print(f"Found: {pipeline.description}")
            else:
                print("Pipeline not found")
        '''
        return self.pipelines.get(name)

    
    def list_pipelines(self = None):
        '''
        List all available pipelines
        
        Returns:
            List of pipeline def initions
            
        Example:
            for pipeline in registry.list_pipelines():
                print(f"- {pipeline.name}: {pipeline.description}")
        '''
        return list(self.pipelines.values())

    
    def has_pipeline(self = None, name = None):
        '''
        Check if pipeline exists in registry
        
        Args:
            name: Pipeline identifier
            
        Returns:
            True if pipeline exists, False otherwise
            
        Example:
            if registry.has_pipeline("freesurfer_hippocampus"):
                # Submit job
            else:
                print("Pipeline not available")
        '''
        return name in self.pipelines

    
    def get_pipeline_names(self = None):
        '''
        Get list of all pipeline names
        
        Returns:
            Sorted list of pipeline names
            
        Example:
            names = registry.get_pipeline_names()
            # ["fastsurfer", "freesurfer_hippocampus", "qsiprep"]
        '''
        return sorted(self.pipelines.keys())

    
    def search_pipelines(self = None, query = None):
        '''
        Search pipelines by name or description
        
        Args:
            query: Search string (case-insensitive)
            
        Returns:
            List of matching pipelines
            
        Example:
            # Find all FreeSurfer-related pipelines
            freesurfer_pipelines = registry.search_pipelines("freesurfer")
        '''
        query_lower = query.lower()
        matches = []
        for pipeline in self.pipelines.values():
            if query_lower in pipeline.name.lower() or query_lower in pipeline.description.lower():
                matches.append(pipeline)
        return matches

    
    def reload(self = None):
        '''
        Reload all pipeline def initions from disk
        
        Use this to pick up changes to YAML files without restarting application.
        Clears existing pipelines and rescans directory.
        
        Warning:
            This clears the pipeline cache. Any in-flight job submissions
            may reference stale pipeline def initions.
        
        Example:
            # After editing pipeline YAML
            registry.reload()
            print(f"Reloaded {len(registry.list_pipelines())} pipelines")
        '''
        logger.info('Reloading pipeline registry...')
        self.pipelines.clear()
        self._load_pipelines()

    
    def validate_all(self = None):
        '''
        Validate all loaded pipelines
        
        Returns:
            Dictionary mapping pipeline names to validation errors
            Empty dict if all valid
            
        Example:
            errors = registry.validate_all()
            if errors:
                for name, err_list in errors.items():
                    print(f"Pipeline {name} has errors: {err_list}")
        '''
        validation_errors = { }
        for name, pipeline in self.pipelines.items():
            errors = []
            if not pipeline.container_image:
                errors.append('Missing container_image')
            if not pipeline.inputs:
                errors.append('No inputs defined')
            if validation_errors:
                validation_errors[name] = errors
        return validation_errors

    
    def __len__(self = None):
        '''Return number of loaded pipelines'''
        return len(self.pipelines)

    
    def __repr__(self = None):
        '''String representation'''
        return f"PipelineRegistry({len(self.pipelines)} pipelines)"


_registry: Optional[PipelineRegistry] = None

def get_pipeline_registry(pipelines_dir = None):
    '''
    Get global pipeline registry instance.
    
    Args:
        pipelines_dir: Directory containing pipelines (only used on first call)
        
    Returns:
        PipelineRegistry instance
    '''
    global _registry
    if _registry is None:
        if pipelines_dir is None:
            pipelines_dir = Path(__file__).parent.parent.parent / 'pipelines'
        _registry = PipelineRegistry(pipelines_dir)
    return _registry

