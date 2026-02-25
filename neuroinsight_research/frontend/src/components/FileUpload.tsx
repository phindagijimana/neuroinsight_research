/**
 * FileUpload Component
 *
 * Main orchestrator for job submission. Supports two flows:
 *
 * A) Filesystem flow (Local / Remote / HPC):
 *    BackendSelector -> DirectorySelector -> PipelineSelector -> Submit
 *    Data source and compute are independent -- data source controls
 *    filesystem browsing, compute controls where jobs run.
 *
 * B) Platform flow (Pennsieve / XNAT):
 *    BackendSelector (connect) -> PlatformBrowser -> BackendSelector (processing target)
 *    -> TransferProgress -> PipelineSelector -> Submit
 */

import React, { useState } from 'react';
import { Upload, FolderOpen, ArrowLeft, ArrowRight } from 'lucide-react';
import { DirectorySelector } from './DirectorySelector';
import { SingleFileUpload } from './SingleFileUpload';
import { PipelineSelector } from './PipelineSelector';
import { ResourceSelector, ResourceConfig } from './ResourceSelector';
import { BackendSelector, BackendType, SSHConfig } from './BackendSelector';
import { PlatformBrowser } from './PlatformBrowser';
import { TransferProgress } from './TransferProgress';
import { apiService } from '../services/api';
import type { Pipeline, DataSourceType, PlatformConnection, PlatformFile } from '../types';

type UploadMode = 'directory' | 'single';
type Step = 'source' | 'browse' | 'backend' | 'transfer' | 'pipeline';

interface FileUploadProps {
  onJobsSubmitted: (jobIds: string[]) => void;
  onBack?: () => void;
}

interface SelectedExecution {
  type: 'plugin' | 'workflow';
  id: string;
  name: string;
}

export const FileUpload: React.FC<FileUploadProps> = ({ onJobsSubmitted, onBack }) => {
  // Data source (where data lives)
  const [dataSource, setDataSource] = useState<DataSourceType>('local');
  const [platformConnection, setPlatformConnection] = useState<PlatformConnection | null>(null);
  const [platformFiles, setPlatformFiles] = useState<PlatformFile[]>([]);

  // Processing target (where to run the job)
  const [selectedBackend, setSelectedBackend] = useState<BackendType>('local');
  const [sshConfig, setSSHConfig] = useState<SSHConfig>({ host: '', username: '', port: 22 });

  // Transfer state
  const [transferId, setTransferId] = useState<string | null>(null);
  const [transferredPath, setTransferredPath] = useState<string | null>(null);
  const [transferredFilePaths, setTransferredFilePaths] = useState<string[]>([]);
  const [platformDatasetId, setPlatformDatasetId] = useState<string | null>(null);

  // Pipeline / execution
  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<SelectedExecution | null>(null);
  const [customResources, setCustomResources] = useState<ResourceConfig | null>(null);

  // Input mode (single subject vs batch)
  const [mode, setMode] = useState<UploadMode>('single');
  const [uploadedFilePath, setUploadedFilePath] = useState<string | null>(null);

  // UI state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPlatformSource = dataSource === 'pennsieve' || dataSource === 'xnat';
  const isPlatformConnected = platformConnection?.connected && platformConnection.platform === dataSource;

  const getCurrentStep = (): Step => {
    if (!isPlatformSource) return 'source';
    if (!isPlatformConnected) return 'source';
    if (platformFiles.length === 0) return 'browse';
    if (!transferId && !transferredPath) return 'backend';
    if (transferId && !transferredPath) return 'transfer';
    return 'pipeline';
  };

  const currentStep = getCurrentStep();

  // ---- Platform flow handlers ----

  const handlePlatformFilesSelected = (files: PlatformFile[], datasetId: string) => {
    setPlatformFiles(files);
    setPlatformDatasetId(datasetId);
  };

  const expandDirectories = async (files: PlatformFile[], datasetId: string): Promise<PlatformFile[]> => {
    const result: PlatformFile[] = [];
    for (const item of files) {
      if (item.type === 'file') {
        result.push(item);
      } else if (item.type === 'directory' && datasetId) {
        try {
          const contents = await apiService.platformBrowse(dataSource, datasetId, item.path);
          const expanded = await expandDirectories(contents.items as PlatformFile[], datasetId);
          result.push(...expanded);
        } catch {
          result.push(item);
        }
      }
    }
    return result;
  };

  const handleStartTransfer = async () => {
    if (platformFiles.length === 0) return;
    setError(null);
    const targetPath = `/tmp/neuroinsight/transfers/${Date.now()}`;
    try {
      // Expand any selected directories into individual files
      const expandedFiles = await expandDirectories(platformFiles, platformDatasetId || '');
      const fileIds = expandedFiles.filter(f => f.type === 'file').map(f => f.id);
      if (fileIds.length === 0) {
        setError('No downloadable files found in the selected items');
        return;
      }
      const backendType = selectedBackend === 'remote_hpc' ? 'hpc' : selectedBackend;
      const result = await apiService.startTransferDownload(
        dataSource, fileIds, backendType, targetPath,
      );
      setTransferId(result.transfer_id);
      setTransferredPath((result as any).target_path || targetPath);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start transfer');
    }
  };

  const handleTransferComplete = (info: { localPaths: string[]; targetPath: string }) => {
    if (info.localPaths.length > 0) {
      setTransferredFilePaths(info.localPaths);
    }
    if (info.targetPath) {
      setTransferredPath(info.targetPath);
    }
  };

  // ---- Job submission handlers ----

  const handleBatchSubmit = async (inputDir: string, _outputDir: string, files: string[]) => {
    if (!selectedPipeline) { setError('Please select a plugin or workflow first'); return; }
    setSubmitting(true);
    setError(null);

    try {
      const jobIds: string[] = [];
      for (const file of files) {
        const filePath = `${inputDir}/${file}`;
        if (selectedExecution?.type === 'plugin' && selectedExecution.id) {
          const result = await apiService.submitPluginJob(selectedExecution.id, [filePath], {}, customResources || undefined);
          jobIds.push(result.job_id);
        } else if (selectedExecution?.type === 'workflow' && selectedExecution.id) {
          const result = await apiService.submitWorkflowJob(selectedExecution.id, [filePath], {}, customResources || undefined);
          jobIds.push(result.job_id);
        } else {
          const result = await apiService.submitBatchJob({
            pipeline_name: selectedPipeline.name, input_dir: inputDir, output_dir: '',
            parameters: {}, file_pattern: '*.nii.gz', custom_resources: customResources || undefined,
          });
          jobIds.push(...result.job_ids);
          break;
        }
      }
      onJobsSubmitted(jobIds);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit batch job');
    } finally {
      setSubmitting(false);
    }
  };

  const handleBidsBatchSubmit = async (bidsDir: string, subjectIds: string[]) => {
    if (!selectedExecution) { setError('Please select a plugin or workflow first'); return; }
    if (selectedExecution.type !== 'workflow') {
      setError('BIDS batch mode is only available for workflows. Select a workflow pipeline.');
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const result = await apiService.submitWorkflowBatch(
        selectedExecution.id,
        bidsDir,
        subjectIds,
        {},
        customResources || undefined,
      );
      const jobIds = result.jobs.map(j => j.job_id);

      if (result.errors.length > 0) {
        const errMsg = result.errors.map(e => `${e.subject_id}: ${e.error}`).join('; ');
        setError(`Submitted ${result.submitted}/${result.total_subjects} jobs. Failures: ${errMsg}`);
      }

      if (jobIds.length > 0) onJobsSubmitted(jobIds);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit BIDS batch');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSingleFileSubmit = async () => {
    if (!selectedPipeline) { setError('Please select a plugin or workflow first'); return; }
    if (!uploadedFilePath) { setError('Please select a file or folder first'); return; }
    setSubmitting(true);
    setError(null);

    try {
      if (selectedExecution?.type === 'plugin' && selectedExecution.id) {
        const result = await apiService.submitPluginJob(selectedExecution.id, [uploadedFilePath], {}, customResources || undefined);
        onJobsSubmitted([result.job_id]);
      } else if (selectedExecution?.type === 'workflow' && selectedExecution.id) {
        const result = await apiService.submitWorkflowJob(selectedExecution.id, [uploadedFilePath], {}, customResources || undefined);
        onJobsSubmitted([result.job_id]);
      } else {
        const result = await apiService.submitJob(selectedPipeline.name, [uploadedFilePath], {}, customResources || undefined);
        onJobsSubmitted([result.job_id]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit job');
    } finally {
      setSubmitting(false);
    }
  };

  const handlePlatformJobSubmit = async () => {
    if (!selectedPipeline || !transferredPath) { setError('Missing data'); return; }
    setSubmitting(true);
    setError(null);
    try {
      // Use actual file paths from transfer, or fall back to directory
      const inputFiles = transferredFilePaths.length > 0
        ? transferredFilePaths
        : [transferredPath];
      const srcPlatform = isPlatformSource ? dataSource : undefined;
      const srcDatasetId = isPlatformSource ? (platformDatasetId || undefined) : undefined;
      if (selectedExecution?.type === 'plugin' && selectedExecution.id) {
        const result = await apiService.submitPluginJob(selectedExecution.id, inputFiles, {}, customResources || undefined, srcPlatform, srcDatasetId);
        onJobsSubmitted([result.job_id]);
      } else if (selectedExecution?.type === 'workflow' && selectedExecution.id) {
        const result = await apiService.submitWorkflowJob(selectedExecution.id, inputFiles, {}, customResources || undefined, srcPlatform, srcDatasetId);
        onJobsSubmitted([result.job_id]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit job');
    } finally {
      setSubmitting(false);
    }
  };

  const resetPlatformFlow = () => {
    setPlatformFiles([]);
    setPlatformDatasetId(null);
    setTransferId(null);
    setTransferredPath(null);
    setTransferredFilePaths([]);
  };

  // Shared BackendSelector props
  const backendProps = {
    selectedBackend,
    onBackendChange: setSelectedBackend,
    sshConfig,
    onSSHConfigChange: setSSHConfig,
    dataSource,
    onDataSourceChange: (s: DataSourceType) => { setDataSource(s); resetPlatformFlow(); },
    platformConnection,
    onPlatformConnect: setPlatformConnection,
    onPlatformDisconnect: () => { setPlatformConnection(null); resetPlatformFlow(); },
    showPlatformTabs: true,
  };

  // ===========================================================================
  // PLATFORM FLOW (step-by-step after connection)
  // ===========================================================================
  if (isPlatformSource && isPlatformConnected) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Process MRI Data</h2>
            <p className="mt-1 text-sm text-gray-600">
              Browse data on {dataSource === 'pennsieve' ? 'Pennsieve' : 'XNAT'}, download, and process
            </p>
          </div>
          {onBack && (
            <button onClick={onBack} className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">
              &larr; Back
            </button>
          )}
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-2 text-xs text-gray-500">
          {['Connected', 'Browse', 'Backend', 'Transfer', 'Pipeline'].map((label, i) => {
            const steps: Step[] = ['source', 'browse', 'backend', 'transfer', 'pipeline'];
            const isActive = steps[i] === currentStep;
            const isDone = steps.indexOf(currentStep) > i;
            return (
              <React.Fragment key={label}>
                {i > 0 && <ArrowRight className="h-3 w-3 text-gray-300" />}
                <span className={`px-2 py-1 rounded ${isActive ? 'bg-[#003d7a] text-white font-medium' : isDone ? 'text-green-700 font-medium' : ''}`}>
                  {label}
                </span>
              </React.Fragment>
            );
          })}
        </div>

        {/* Unified backend selector (stays visible so user can disconnect) */}
        <BackendSelector {...backendProps} />

        {/* Step: Browse */}
        {currentStep === 'browse' && (
          <PlatformBrowser platform={dataSource} onFilesSelected={handlePlatformFilesSelected} />
        )}

        {/* Step: Backend selection for processing */}
        {currentStep === 'backend' && (
          <div className="space-y-3">
            <div className="bg-navy-50 border border-navy-200 rounded-lg p-3">
              <p className="text-xs text-navy-700">
                <strong>{platformFiles.length} file{platformFiles.length !== 1 ? 's' : ''}</strong> selected.
                Choose where to process, then download:
              </p>
            </div>
            <BackendSelector
              selectedBackend={selectedBackend}
              onBackendChange={setSelectedBackend}
              sshConfig={sshConfig}
              onSSHConfigChange={setSSHConfig}
              showPlatformTabs={false}
            />
            <div className="flex gap-2">
              <button onClick={resetPlatformFlow} className="px-4 py-2 text-sm text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50">
                <ArrowLeft className="h-3.5 w-3.5 inline mr-1" />Back
              </button>
              <button onClick={handleStartTransfer} className="flex-1 px-4 py-2 text-sm bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] font-medium">
                Download & Continue
              </button>
            </div>
            {error && <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">{error}</div>}
          </div>
        )}

        {/* Step: Transfer */}
        {currentStep === 'transfer' && transferId && (
          <TransferProgress transferId={transferId} direction="download" onComplete={handleTransferComplete} onCancel={resetPlatformFlow} />
        )}

        {/* Step: Pipeline + submit */}
        {currentStep === 'pipeline' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-4">
              <PipelineSelector onPipelineSelect={setSelectedPipeline} selectedPipeline={selectedPipeline} onExecutionSelect={setSelectedExecution} />
              {selectedPipeline && (
                <ResourceSelector plugin={selectedPipeline} backendType={selectedBackend === 'local' ? 'local' : selectedBackend === 'remote_hpc' ? 'hpc' : 'remote'} onResourcesChange={setCustomResources} />
              )}
            </div>
            <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4">
              <h3 className="text-sm font-semibold text-gray-700">Ready to Process</h3>
              <div className="text-xs text-gray-600 space-y-1">
                <p><strong>Source:</strong> {dataSource === 'pennsieve' ? 'Pennsieve' : 'XNAT'}</p>
                <p><strong>Files:</strong> {platformFiles.length}</p>
                <p><strong>Backend:</strong> {selectedBackend === 'local' ? 'Local Docker' : selectedBackend === 'remote' ? 'Remote Server' : 'HPC (SLURM)'}</p>
                <p><strong>Data:</strong> Downloaded to {transferredPath}</p>
              </div>
              {error && <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">{error}</div>}
              <button onClick={handlePlatformJobSubmit} disabled={!selectedPipeline || submitting}
                className="w-full py-2.5 px-4 bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed">
                {submitting ? 'Submitting...' : 'Submit Job'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ===========================================================================
  // FILESYSTEM FLOW (Local / Remote / HPC) -- original layout
  // ===========================================================================
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Process MRI Data</h2>
          <p className="mt-1 text-sm text-gray-600">Select execution backend, pipeline, and input data</p>
        </div>
        {onBack && (
          <button onClick={onBack} className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50">
            &larr; Back
          </button>
        )}
      </div>

      <div className="space-y-4">
        {/* Row 1: Unified Backend (with platform tabs) + Resource Configuration */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <BackendSelector {...backendProps} />

          {selectedPipeline && (
            <ResourceSelector
              plugin={selectedPipeline}
              backendType={selectedBackend === 'local' ? 'local' : selectedBackend === 'remote_hpc' ? 'hpc' : 'remote'}
              onResourcesChange={setCustomResources}
            />
          )}
        </div>

        {/* Row 2: Input Mode + Pipeline Selector */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {selectedPipeline && (
            <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4 flex flex-col h-full">
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Input Mode</h3>
                <div className="grid grid-cols-2 gap-3">
                  <button onClick={() => setMode('single')}
                    className={`p-3 rounded-md border transition-all ${mode === 'single' ? 'border-navy-600 bg-navy-50' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                    <div className="flex items-center mb-1">
                      <Upload className={`h-4 w-4 mr-1.5 ${mode === 'single' ? 'text-navy-600' : 'text-gray-400'}`} />
                      <span className="text-sm font-medium text-gray-900">Single</span>
                    </div>
                    <p className="text-xs text-gray-600 text-left">One subject folder or file</p>
                  </button>
                  <button onClick={() => setMode('directory')}
                    className={`p-3 rounded-md border transition-all ${mode === 'directory' ? 'border-navy-600 bg-navy-50' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                    <div className="flex items-center mb-1">
                      <FolderOpen className={`h-4 w-4 mr-1.5 ${mode === 'directory' ? 'text-navy-600' : 'text-gray-400'}`} />
                      <span className="text-sm font-medium text-gray-900">Batch</span>
                    </div>
                    <p className="text-xs text-gray-600 text-left">Folder with multiple subjects</p>
                  </button>
                </div>
              </div>

              {error && <div className="p-3 bg-red-50 border border-red-200 rounded"><p className="text-xs text-red-700">{error}</p></div>}
              {submitting && <div className="p-3 bg-navy-50 border border-navy-200 rounded"><p className="text-xs text-navy-700">Submitting jobs...</p></div>}

              <div className="flex-1" style={submitting ? { opacity: 0.5, pointerEvents: 'none' } : undefined}>
                {mode === 'directory' ? (
                  <DirectorySelector
                    mode={dataSource === 'hpc' ? 'hpc' : dataSource === 'remote' ? 'remote' : 'local'}
                    onSubmit={handleBatchSubmit}
                    onBidsSubmit={handleBidsBatchSubmit}
                  />
                ) : (
                  <>
                    <SingleFileUpload
                      browseMode={dataSource === 'hpc' ? 'hpc' : dataSource === 'remote' ? 'remote' : 'local'}
                      onFileUploaded={(path) => { setUploadedFilePath(path); setError(null); }}
                      executionContext={selectedExecution ? { type: selectedExecution.type, id: selectedExecution.id } : null}
                    />
                    {uploadedFilePath && (
                      <div className="mt-3">
                        <button onClick={handleSingleFileSubmit} className="w-full py-2 px-4 bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] font-medium text-sm">
                          Submit Job
                        </button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          <PipelineSelector onPipelineSelect={setSelectedPipeline} selectedPipeline={selectedPipeline} onExecutionSelect={setSelectedExecution} />
        </div>
      </div>
    </div>
  );
};
