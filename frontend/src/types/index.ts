/**
 * NeuroInsight Research - Type Definitions
 *
 * Comprehensive TypeScript interfaces for type-safe frontend development.
 * All types match backend API contracts (FastAPI Pydantic models).
 */

/**
 * Pipeline Definition
 *
 * Represents a neuroimaging processing pipeline (e.g., FreeSurfer, FastSurfer).
 * Loaded from YAML files in backend/pipelines/ directory.
 */
export interface Pipeline {
  /** Unique pipeline identifier (e.g., "freesurfer_hippocampus") */
  name: string;

  /** Plugin ID (for new architecture) */
  id?: string;

  /** Semantic version (e.g., "1.0.0") */
  version: string;

  /** Human-readable description of pipeline functionality */
  description: string;

  /** Docker/Singularity container image (e.g., "freesurfer/freesurfer:7.3.2") */
  container_image: string;

  /** Required and optional input files */
  inputs: InputSpec[];

  /** Configurable pipeline parameters */
  parameters: ParameterSpec[];

  /** Default resource requirements */
  resources: ResourceSpec;

  /** All named resource profiles (default, cpu_only, high_memory, etc.) */
  resource_profiles?: Record<string, ResourceProfile>;

  /** Parallelization capabilities detected from plugin definition */
  parallelization?: ParallelizationInfo;

  /** Optional: Pipeline authors/maintainers */
  authors?: string[];

  /** Optional: Scientific references (DOIs, URLs) */
  references?: string[];
}

/**
 * Input File Specification
 *
 * Defines expected input files for a pipeline.
 */
export interface InputSpec {
  /** Input name (e.g., "t1w", "flair", "dwi") */
  name: string;

  /** File type: nifti (.nii.gz), dicom, text, json */
  type: 'nifti' | 'dicom' | 'text' | 'json';

  /** Whether this input is mandatory */
  required: boolean;

  /** Description of what this input represents */
  description: string;

  /** Optional: Glob pattern for file selection (e.g., "*_T1w.nii.gz") */
  pattern?: string;
}

/**
 * Pipeline Parameter Specification
 *
 * Defines configurable parameters for pipeline execution.
 */
export interface ParameterSpec {
  /** Parameter name (e.g., "threads", "use_gpu") */
  name: string;

  /** Data type */
  type: 'int' | 'float' | 'string' | 'bool' | 'choice';

  /** Default value used if not specified */
  default: any;

  /** Human-readable description */
  description: string;

  /** For 'choice' type: available options */
  choices?: any[];

  /** For numeric types: minimum valid value */
  min_value?: number;

  /** For numeric types: maximum valid value */
  max_value?: number;
}

/**
 * Resource Requirements
 *
 * Computational resources needed for job execution.
 * Used for both pipeline defaults and user customization.
 */
export interface ResourceSpec {
  /** RAM in gigabytes (e.g., 16, 32, 64) */
  memory_gb: number;

  /** Number of CPU cores */
  cpus: number;

  /** Maximum runtime in hours (for HPC walltime) */
  time_hours: number;

  /** Whether GPU is required */
  gpu: boolean;

  /** Thread count for parallel processing (defaults to cpus) */
  threads?: number;

  /** OpenMP thread count (defaults to min(4, cpus)) */
  omp_nthreads?: number;

  /** Enable parallelization where supported */
  parallel?: boolean;
}

/** Resource profile from plugin YAML (e.g. default, cpu_only, high_memory) */
export interface ResourceProfile {
  cpus: number;
  mem_gb: number;
  time_hours: number;
  gpus: number;
}

/** Plugin parallelization capabilities */
export interface ParallelizationInfo {
  supports_threading: boolean;
  supports_openmp: boolean;
  supports_gpu: boolean;
  gpu_optional: boolean;
  thread_param: string | null;
  max_useful_cpus: number | null;
}

/** Host system resource limits (from /api/system/resources) */
export interface SystemResources {
  cpu: {
    total_logical: number;
    total_physical: number;
    recommended_max: number;
  };
  memory: {
    total_gb: number;
    recommended_max_gb: number;
  };
  gpu: {
    available: boolean;
    count: number;
    devices: Array<{ name: string; memory_mb: number; driver_version: string }>;
    docker_nvidia_runtime: boolean;
  };
  limits: {
    max_cpus: number;
    max_memory_gb: number;
    gpu_available: boolean;
    gpu_count: number;
  };
}

/**
 * Job Entity
 *
 * Represents a submitted processing job with full lifecycle tracking.
 * Stored in database and returned by API endpoints.
 *
 * Status Lifecycle:
 *   pending -> running -> completed/failed/cancelled
 */
export interface Job {
  /** Unique job identifier (UUID) */
  id: string;

  /** Execution backend: "local_docker" or "slurm" */
  backend_type: string;

  /** Scheduler-specific job ID (e.g., SLURM job ID) */
  backend_job_id?: string;

  /** Pipeline name that was executed (legacy - use workflow_id or plugin_id) */
  pipeline_name: string;

  /** Pipeline version at time of execution */
  pipeline_version?: string;

  /** Workflow ID (if using workflow mode) */
  workflow_id?: string;

  /** Plugin ID (if using single plugin mode) */
  plugin_id?: string;

  /** Execution mode: "workflow" or "plugin" */
  execution_mode?: 'workflow' | 'plugin';

  /** Container image used for execution */
  container_image: string;

  /** Input file paths (local or HPC) */
  input_files: string[];

  /** Pipeline parameters (merged with defaults) */
  parameters: Record<string, any>;

  /** Allocated resources */
  resources: ResourceSpec;

  /** Current job status */
  status: JobStatus;

  /** Estimated progress percentage (0-100), weighted by pipeline phase */
  progress?: number;

  /** Human-readable label for the current pipeline phase */
  current_phase?: string | null;

  /** ISO 8601 timestamp when job was submitted */
  submitted_at: string;

  /** ISO 8601 timestamp when execution started */
  started_at?: string;

  /** ISO 8601 timestamp when execution finished */
  completed_at?: string;

  /** Path to output directory (local or HPC) */
  output_dir: string;

  /** Process exit code (0 = success) */
  exit_code?: number;

  /** Error message if status is 'failed' */
  error_message?: string;

  /** Calculated runtime in seconds */
  runtime_seconds?: number;

  /** Optional: User ID for multi-user systems (Phase 2+) */
  user_id?: string;

  /** Optional: User-defined tags for organization */
  tags?: string[];
}

/**
 * Job Status Enum
 *
 * Universal status across all execution backends.
 *
 * - pending:   Waiting in queue
 * - running:   Currently executing
 * - completed: Finished successfully (exit code 0)
 * - failed:    Execution error (exit code != 0)
 * - cancelled: User-cancelled before completion
 */
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

/**
 * Directory Browser Response
 *
 * Returned by /api/browse endpoint for directory-based batch processing.
 */
export interface DirectoryInfo {
  /** Directory path */
  path: string;

  /** All files in directory */
  files: string[];

  /** Filtered NIfTI files (.nii, .nii.gz) */
  nifti_files: string[];

  /** Total size in bytes */
  total_size?: number;
}

/**
 * Custom Resource Overrides
 *
 * User-specified resource requirements that override pipeline defaults.
 * Includes HPC-specific options for SLURM/PBS schedulers.
 */
export interface CustomResources {
  /** RAM in GB (overrides pipeline default) */
  memory_gb: number;

  /** CPU cores (overrides pipeline default) */
  cpus: number;

  /** Max runtime in hours (overrides pipeline default) */
  time_hours: number;

  /** GPU requirement (overrides pipeline default) */
  gpu: boolean;

  /** Thread count for parallel processing */
  threads?: number;

  /** OpenMP thread count */
  omp_nthreads?: number;

  /** Enable parallelization */
  parallel?: boolean;

  // HPC-Specific Options (Phase 2)

  /** SLURM partition name (e.g., "gpu", "highmem") */
  partition?: string;

  /** Quality of Service level (e.g., "high", "low") */
  qos?: string;

  /** Allocation/project account code */
  account?: string;

  /** Number of nodes for multi-node jobs */
  nodes?: number;
}

/**
 * Batch Job Submission Request
 *
 * Payload for /api/jobs/submit-batch endpoint.
 * Processes all matching files in a directory.
 */
export interface BatchSubmitRequest {
  /** Pipeline to execute */
  pipeline_name: string;

  /** Directory containing input files */
  input_dir: string;

  /** Directory for outputs (subdirs created per file) */
  output_dir: string;

  /** Pipeline parameter overrides */
  parameters?: Record<string, any>;

  /** Glob pattern for file selection (default: "*.nii.gz") */
  file_pattern?: string;

  /** Resource requirement overrides */
  custom_resources?: CustomResources;
}

/**
 * Batch Job Submission Response
 *
 * Returned after successful batch submission.
 */
export interface BatchSubmitResponse {
  /** Success message */
  message: string;

  /** Array of created job IDs (one per file) */
  job_ids: string[];

  /** Number of files that will be processed */
  files_processed: number;
}
