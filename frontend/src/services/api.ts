/**
 * API Service Layer
 * 
 * Centralized HTTP client for all backend communication.
 * Provides type-safe methods wrapping FastAPI endpoints.
 * 
 * ARCHITECTURE
 * ------------
 * 
 * - Single axios instance with base configuration
 * - Automatic JSON serialization/deserialization
 * - Type-safe request/response via TypeScript interfaces
 * - Error handling with axios interceptors
 * - Environment-based URL configuration
 * 
 * ERROR HANDLING
 * --------------
 * 
 * Network Errors:
 *  - Connection refused: Backend not running
 *  - Timeout: Slow network or backend overload
 *  - CORS: Misconfigured proxy or backend
 * 
 * HTTP Errors:
 *  - 400: Validation error (bad request data)
 *  - 404: Resource not found (job/pipeline doesn't exist)
 *  - 500: Server error (backend bug or system failure)
 * 
 * Best Practice:
 *  Always wrap API calls in try/catch blocks at component level.
 * 
 * @example
 * try {
 *   const jobs = await apiService.getJobs();
 *   setJobs(jobs);
 * } catch (error) {
 *   console.error('Failed to fetch jobs:', error);
 *   // Show user-friendly error message
 * }
 */

import axios, { AxiosError } from 'axios';
import type { 
  Pipeline, 
  Job, 
  DirectoryInfo, 
  BatchSubmitRequest, 
  BatchSubmitResponse,
  SystemResources,
} from '../types';

// Backend API URL (configured via environment variable or default)
// Vite proxy redirects /api/* and /health to backend in development
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

// Axios instance with default configuration
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 second timeout
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Log errors for debugging
    if (error.response) {
      // Server responded with error status
      console.error('API Error:', error.response.status, error.response.data);
    } else if (error.request) {
      // Request made but no response received
      console.error('Network Error: No response from server');
    } else {
      // Error in request configuration
      console.error('Request Error:', error.message);
    }
    return Promise.reject(error);
  }
);

/**
 * API Service
 * 
 * Collection of type-safe methods for backend communication.
 * All methods return Promises that resolve to typed data.
 */
export const apiService = {
  /**
   * Get the base URL for direct fetch calls (used by HPC components).
   */
  getBaseUrl(): string {
    return API_BASE_URL;
  },

  // ================================================================================
  // HEALTH & STATUS
  // ================================================================================
  
  /**
   * Check backend health and availability
   * 
   * @returns Health status object with backend details
   * @throws {AxiosError} If backend is unreachable
   * 
   * @example
   * const health = await apiService.healthCheck();
   * console.log('Backend status:', health.status); // "healthy" or "unhealthy"
   */
  async healthCheck() {
    const response = await api.get('/health');
    return response.data;
  },

  /**
   * Get host system resource capabilities (CPU, RAM, GPU).
   * Used to show realistic limits in the resource selector.
   */
  async getSystemResources(): Promise<SystemResources> {
    const response = await api.get('/api/system/resources');
    return response.data;
  },

  // ================================================================================
  // PIPELINES
  // ================================================================================
  
  /**
   * List all available pipelines
   * 
   * @returns Array of pipeline definitions
   * @throws {AxiosError} If backend is unreachable or error occurs
   * 
   * @example
   * const { pipelines } = await apiService.getPipelines();
   * pipelines.forEach(p => console.log(p.name, p.description));
   */
  async getPipelines(): Promise<{ pipelines: Pipeline[] }> {
    const response = await api.get('/api/pipelines');
    return response.data;
  },

  /**
   * Get detailed information about a specific pipeline
   * 
   * @param name - Pipeline identifier (e.g., "freesurfer_hippocampus")
   * @returns Complete pipeline specification
   * @throws {AxiosError} 404 if pipeline not found
   * 
   * @example
   * const pipeline = await apiService.getPipeline("freesurfer_hippocampus");
   * console.log('Inputs:', pipeline.inputs);
   * console.log('Default memory:', pipeline.resources.memory_gb, 'GB');
   */
  async getPipeline(name: string): Promise<Pipeline> {
    const response = await api.get(`/api/pipelines/${name}`);
    return response.data;
  },

  // ================================================================================
  // PLUGINS & WORKFLOWS (New Architecture)
  // ================================================================================

  /**
   * List all available plugins
   * @param userSelectableOnly - If true, hide utility plugins (default: true)
   */
  async getPlugins(userSelectableOnly: boolean = true): Promise<{ plugins: any[]; total: number }> {
    const response = await api.get('/api/plugins', {
      params: { user_selectable_only: userSelectableOnly }
    });
    return response.data;
  },

  /**
   * Get detailed plugin information
   */
  async getPlugin(pluginId: string): Promise<any> {
    const response = await api.get(`/api/plugins/${pluginId}`);
    return response.data;
  },

  /**
   * List all available workflows (with enriched step info)
   */
  async getWorkflows(): Promise<{ workflows: any[]; total: number }> {
    const response = await api.get('/api/workflows');
    return response.data;
  },

  /**
   * Get detailed workflow information
   */
  async getWorkflow(workflowId: string): Promise<any> {
    const response = await api.get(`/api/workflows/${workflowId}`);
    return response.data;
  },

  /**
   * Submit a plugin job
   */
  async submitPluginJob(pluginId: string, inputFiles: string[], parameters: Record<string, any> = {}, customResources?: Record<string, any>): Promise<any> {
    const response = await api.post(`/api/plugins/${pluginId}/submit`, {
      input_files: inputFiles,
      parameters,
      custom_resources: customResources,
    });
    return response.data;
  },

  /**
   * Submit a workflow job
   */
  async submitWorkflowJob(workflowId: string, inputFiles: string[], parameters: Record<string, any> = {}, customResources?: Record<string, any>): Promise<any> {
    const response = await api.post(`/api/workflows/${workflowId}/submit`, {
      input_files: inputFiles,
      parameters,
      custom_resources: customResources,
    });
    return response.data;
  },

  // ================================================================================
  // LICENSE STATUS
  // ================================================================================

  /**
   * Check FreeSurfer license status
   */
  async getLicenseStatus(): Promise<{ found: boolean; path: string | null; hint: string }> {
    const response = await api.get('/api/license/status');
    return response.data;
  },

  // ================================================================================
  // DOCUMENTATION
  // ================================================================================

  /**
   * Get all plugins and workflows with full YAML for the docs page
   */
  async getDocsAll(): Promise<{ plugins: any[]; workflows: any[]; total_plugins: number; total_workflows: number }> {
    const response = await api.get('/api/docs/all');
    return response.data;
  },

  // ================================================================================
  // JOB SUBMISSION (Legacy)
  // ================================================================================
  
  /**
   * Submit a single job for execution
   * 
   * @param pipelineName - Pipeline to execute
   * @param inputFiles - Array of input file paths (local or HPC)
   * @param parameters - Optional parameter overrides
   * @param customResources - Optional resource overrides
   * @returns Job ID and initial status
   * @throws {AxiosError} 400 if validation fails, 404 if pipeline not found
   * 
   * @example
   * const { job_id } = await apiService.submitJob(
   *   "freesurfer_hippocampus",
   *   ["/data/subject001_T1w.nii.gz"],
   *   { threads: 8 },
   *   { memory_gb: 64, cpus: 16 }
   * );
   * console.log('Job submitted:', job_id);
   */
  async submitJob(
    pipelineName: string,
    inputFiles: string[],
    parameters: Record<string, any> = {},
    customResources?: any
  ): Promise<{ job_id: string; status: string }> {
    const response = await api.post('/api/jobs/submit', {
      pipeline_name: pipelineName,
      input_files: inputFiles,
      parameters,
      custom_resources: customResources,
    });
    return response.data;
  },

  /**
   * Submit batch job to process multiple files in a directory
   * 
   * Creates one job per matching file in input_dir.
   * Ideal for processing entire datasets.
   * 
   * @param request - Batch submission configuration
   * @returns Array of job IDs and file count
   * @throws {AxiosError} 400 if directory invalid or no files match
   * 
   * @example
   * const result = await apiService.submitBatchJob({
   *   pipeline_name: "fastsurfer",
   *   input_dir: "/data/study/subjects",
   *   output_dir: "/results/fastsurfer",
   *   file_pattern: "*_T1w.nii.gz",
   *   parameters: { seg_only: false }
   * });
   * console.log(`Submitted ${result.job_ids.length} jobs`);
   */
  async submitBatchJob(request: BatchSubmitRequest): Promise<BatchSubmitResponse> {
    const response = await api.post('/api/jobs/submit-batch', request);
    return response.data;
  },

  // ================================================================================
  // JOB MONITORING
  // ================================================================================
  
  /**
   * List jobs with optional filtering
   * 
   * @param status - Optional status filter ('pending' | 'running' | 'completed' | 'failed')
   * @param limit - Maximum number of jobs to return (default: 100)
   * @returns Array of job objects
   * 
   * @example
   * // Get all running jobs
   * const runningJobs = await apiService.getJobs('running');
   * 
   * // Get all jobs (up to 100)
   * const allJobs = await apiService.getJobs();
   * 
   * // Get last 50 jobs
   * const recentJobs = await apiService.getJobs(undefined, 50);
   */
  async getJobs(status?: string, limit: number = 100): Promise<Job[]> {
    const params = new URLSearchParams();
    if (status) params.append('status', status);
    params.append('limit', limit.toString());

    const response = await api.get(`/api/jobs?${params.toString()}`);
    return response.data.jobs;
  },

  /**
   * Get detailed information about a specific job
   * 
   * Includes current status, timing, resources, and error messages.
   * Status is refreshed from backend execution system.
   * 
   * @param jobId - Job identifier (UUID)
   * @returns Complete job information
   * @throws {AxiosError} 404 if job not found
   * 
   * @example
   * const job = await apiService.getJob("550e8400-e29b-41d4-a716-446655440000");
   * console.log('Status:', job.status);
   * if (job.runtime_seconds) {
   *   console.log('Runtime:', Math.floor(job.runtime_seconds / 60), 'minutes');
   * }
   */
  async getJob(jobId: string): Promise<Job> {
    const response = await api.get(`/api/jobs/${jobId}`);
    return response.data;
  },

  /**
   * Get progress for all active (pending/running) jobs.
   * Lightweight endpoint optimised for frequent polling.
   */
  async getJobsProgress(): Promise<{ id: string; status: string; progress: number; current_phase: string | null }[]> {
    const response = await api.get('/api/jobs/progress');
    return response.data.jobs;
  },

  /**
   * Cancel a running or pending job
   * 
   * Sends cancellation signal to execution backend (Docker stop or scancel).
   * Job status will update to 'cancelled'.
   * 
   * @param jobId - Job identifier
   * @returns Success message
   * @throws {AxiosError} 404 if job not found, 400 if already in terminal state
   * 
   * @example
   * try {
   *   await apiService.cancelJob(jobId);
   *   console.log('Job cancelled successfully');
   * } catch (error) {
   *   console.error('Cancellation failed:', error.response?.data?.detail);
   * }
   */
  async cancelJob(jobId: string): Promise<{ message: string }> {
    const response = await api.post(`/api/jobs/${jobId}/cancel`);
    return response.data;
  },

  /**
   * Retrieve job execution logs
   * 
   * Returns stdout and stderr from job execution.
   * Useful for debugging failures or monitoring progress.
   * 
   * @param jobId - Job identifier
   * @returns Log contents
   * @throws {AxiosError} 404 if job not found, 500 if logs unavailable
   * 
   * @example
   * const logs = await apiService.getJobLogs(jobId);
   * console.log('=== STDOUT ===');
   * console.log(logs.stdout);
   * if (logs.stderr) {
   *   console.error('=== STDERR ===');
   *   console.error(logs.stderr);
   * }
   */
  async getJobLogs(jobId: string): Promise<{ job_id: string; stdout: string; stderr: string }> {
    const response = await api.get(`/api/jobs/${jobId}/logs`);
    return response.data;
  },

  /**
   * Delete job from database
   * 
   * Note: This only removes the database record.
   * Cancel the job first if it's still running.
   * Output files are not deleted (manual cleanup required).
   * 
   * @param jobId - Job identifier
   * @returns void (204 No Content)
   * @throws {AxiosError} 404 if job not found
   * 
   * @example
   * // Proper cleanup sequence
   * await apiService.cancelJob(jobId);  // Stop execution
   * await apiService.deleteJob(jobId);  // Remove from database
   */
  async deleteJob(jobId: string): Promise<void> {
    await api.delete(`/api/jobs/${jobId}`);
  },

  // ================================================================================
  // FILE OPERATIONS
  // ================================================================================
  
  /**
   * Browse directory contents
   * 
   * Lists files in a directory on local machine or HPC.
   * Filters and highlights NIfTI files (.nii, .nii.gz).
   * 
   * @param path - Directory path to browse
   * @param backendType - 'local' or 'hpc' (default: 'local')
   * @returns Directory contents with NIfTI files highlighted
   * @throws {AxiosError} 404 if directory not found, 400 if not a directory
   * 
   * @example
   * // Browse local directory
   * const dir = await apiService.browseDirectory("/data/subjects");
   * console.log('NIfTI files:', dir.nifti_files);
   * 
   * // Browse HPC directory (Phase 2)
   * const hpcDir = await apiService.browseDirectory("/scratch/user/data", "hpc");
   */
  async browseDirectory(path: string, backendType: 'local' | 'remote' | 'hpc' = 'local'): Promise<DirectoryInfo> {
    if (backendType === 'hpc' || backendType === 'remote') {
      // Route to HPC browse endpoint (remote filesystem via SSH/SFTP)
      const response = await api.get('/api/hpc/browse', {
        params: { path },
      });
      return response.data;
    }
    const response = await api.get('/api/browse', {
      params: { path, backend_type: backendType },
    });
    return response.data;
  },

  /**
   * Upload file to server
   * 
   * Multipart form upload with progress tracking.
   * Used for single-file upload mode.
   * 
   * @param file - File object from input element
   * @param onProgress - Optional callback for upload progress (0-100)
   * @returns Server file path
   * @throws {AxiosError} 413 if file too large, 400 if invalid file type
   * 
   * @example
   * const fileInput = document.getElementById('file') as HTMLInputElement;
   * const file = fileInput.files[0];
   * 
   * const { path } = await apiService.uploadFile(file, (progress) => {
   *   console.log(`Upload progress: ${progress}%`);
   *   setUploadProgress(progress);
   * });
   * 
   * console.log('File uploaded to:', path);
   */
  async uploadFile(file: File, onProgress?: (progress: number) => void): Promise<{ path: string }> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/api/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentCompleted);
        }
      },
    });

    return response.data;
  },

  // ================================================================================
  // HPC / REMOTE BACKEND
  // ================================================================================

  /**
   * Test SSH connection to HPC cluster.
   */
  async hpcConnect(host: string, username: string, port: number = 22): Promise<{ connected: boolean; message: string }> {
    const response = await api.post('/api/hpc/connect', { host, username, port });
    return response.data;
  },

  /**
   * Disconnect SSH connection.
   */
  async hpcDisconnect(): Promise<void> {
    await api.post('/api/hpc/disconnect');
  },

  /**
   * Get SSH connection status.
   */
  async hpcStatus(): Promise<{ connected: boolean; host: string | null; username: string | null }> {
    const response = await api.get('/api/hpc/status');
    return response.data;
  },

  /**
   * Switch execution backend (local or slurm).
   */
  async switchBackend(config: {
    backend_type: string;
    ssh_host?: string;
    ssh_user?: string;
    ssh_port?: number;
    work_dir?: string;
    partition?: string;
    account?: string;
    qos?: string;
    modules?: string;
  }): Promise<{ backend_type: string; message: string; health: any }> {
    const response = await api.post('/api/hpc/backend/switch', config);
    return response.data;
  },

  /**
   * Get current backend type and status.
   */
  async getCurrentBackend(): Promise<{ backend_type: string; healthy: boolean }> {
    const response = await api.get('/api/hpc/backend/current');
    return response.data;
  },

  /**
   * List available SLURM partitions.
   */
  async hpcPartitions(): Promise<{ partitions: any[] }> {
    const response = await api.get('/api/hpc/partitions');
    return response.data;
  },

  /**
   * Get SLURM queue information.
   */
  async hpcQueue(userOnly: boolean = true): Promise<{ queue: any[] }> {
    const response = await api.get('/api/hpc/queue', { params: { user_only: userOnly } });
    return response.data;
  },

  /**
   * Browse remote HPC filesystem.
   */
  async browseRemote(path: string = '~'): Promise<DirectoryInfo> {
    const response = await api.get('/api/hpc/browse', { params: { path } });
    return response.data;
  },

  // ================================================================================
  // FILE DOWNLOAD
  // ================================================================================

  /**
   * Download a file from job results
   * 
   * @param jobId - Job ID
   * @param filePath - Relative path within job output directory (e.g., '/bundle/volumes/aseg.nii.gz')
   * @returns Download URL (triggers browser download)
   * 
   * @example
   * // Download a specific file
   * apiService.downloadFile('job_12345', '/bundle/volumes/aseg.nii.gz');
   */
  async downloadFile(jobId: string, filePath: string): Promise<void> {
    // Create download URL with query parameters
    const url = `${API_BASE_URL}/api/results/${jobId}/download?file_path=${encodeURIComponent(filePath)}`;
    
    // Trigger download by opening URL in new window
    // Browser will handle the file download based on FileResponse headers
    window.open(url, '_blank');
  },
};

export default apiService;
