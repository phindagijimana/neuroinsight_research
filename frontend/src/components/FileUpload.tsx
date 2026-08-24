/**
 * FileUpload Component
 *
 * Jobs page: compute-only submission.
 * Connect one compute backend, browse paths on that backend, pick pipeline, submit.
 * Data from Pennsieve/XNAT or other hosts must be staged via Transfer first.
 */

import React, { useState, useEffect } from 'react';
import { Upload, FolderOpen, ArrowRight, AlertTriangle } from 'lucide-react';
import { DirectorySelector } from './DirectorySelector';
import { SingleFileUpload } from './SingleFileUpload';
import { PipelineSelector } from './PipelineSelector';
import { ResourceSelector, ResourceConfig } from './ResourceSelector';
import { BackendSelector, BackendType } from './BackendSelector';
import { apiService } from '../services/api';
import type { Pipeline } from '../types';
import { useToast } from '../contexts/NotificationContext';
import {
  type ExecutionInputProfile,
  isBidsInput,
  parseBidsSubjectPath,
} from '../lib/inputFormat';
import { consumeJobsOpenAt } from '../lib/openJobPath';
import { checkPathComputeMismatch } from '../lib/pathMismatch';

type UploadMode = 'directory' | 'single';

interface FileUploadProps {
  onJobsSubmitted: (jobIds: string[]) => void;
  onBack?: () => void;
  onNavigateToTransfer?: () => void;
}

interface SelectedExecution extends ExecutionInputProfile {
  type: 'plugin' | 'workflow';
  id: string;
  name: string;
}

function resourceParams(customResources: ResourceConfig | null): Record<string, unknown> {
  if (!customResources?.threads) return {};
  return { threads: customResources.threads };
}

function computeBrowseMode(backend: BackendType): 'local' | 'remote' | 'hpc' {
  if (backend === 'remote_hpc') return 'hpc';
  if (backend === 'remote') return 'remote';
  return 'local';
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onJobsSubmitted,
  onBack,
  onNavigateToTransfer,
}) => {
  const toast = useToast();

  const [selectedBackend, setSelectedBackend] = useState<BackendType>('local');
  const [sshConfig, setSSHConfig] = useState({ host: '', username: '', port: 22 });
  const [sshConnected, setSSHConnected] = useState(false);

  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<SelectedExecution | null>(null);
  const [customResources, setCustomResources] = useState<ResourceConfig | null>(null);

  const [mode, setMode] = useState<UploadMode>('single');
  const [uploadedFilePath, setUploadedFilePath] = useState<string | null>(null);
  const [batchInputDir, setBatchInputDir] = useState('');
  const [prefillInputDir, setPrefillInputDir] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const browseMode = computeBrowseMode(selectedBackend);
  const bidsWorkflow = isBidsInput(selectedExecution);
  const activeInputPath = mode === 'single' ? uploadedFilePath : batchInputDir || null;
  const pathMismatch = checkPathComputeMismatch(activeInputPath, selectedBackend);
  const submitBlocked = Boolean(pathMismatch?.blockSubmit);

  useEffect(() => {
    const openAt = consumeJobsOpenAt();
    if (!openAt) return;
    setSelectedBackend(openAt.backend);
    setUploadedFilePath(openAt.path);
    setPrefillInputDir(openAt.path);
    setMode('single');
  }, []);

  const handleBatchSubmit = async (inputDir: string, _outputDir: string, files: string[]) => {
    if (!selectedPipeline) {
      setError('Please select a plugin or workflow first');
      return;
    }
    const mismatch = checkPathComputeMismatch(inputDir, selectedBackend);
    if (mismatch?.blockSubmit) {
      setError(mismatch.message);
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const jobIds: string[] = [];
      const wfP: Record<string, string> = {};
      for (const file of files) {
        const filePath = `${inputDir}/${file}`;
        if (selectedExecution?.type === 'plugin' && selectedExecution.id) {
          const result = await apiService.submitPluginJob(
            selectedExecution.id,
            [filePath],
            resourceParams(customResources),
            customResources || undefined,
          );
          jobIds.push(result.job_id);
        } else if (selectedExecution?.type === 'workflow' && selectedExecution.id) {
          const result = await apiService.submitWorkflowJob(
            selectedExecution.id,
            [filePath],
            wfP,
            customResources || undefined,
          );
          jobIds.push(result.job_id);
        } else {
          const result = await apiService.submitBatchJob({
            pipeline_name: selectedPipeline.name,
            input_dir: inputDir,
            output_dir: '',
            parameters: {},
            file_pattern: '*.nii.gz',
            custom_resources: customResources || undefined,
          });
          jobIds.push(...result.job_ids);
          break;
        }
      }
      onJobsSubmitted(jobIds);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to submit batch job.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleBidsBatchSubmit = async (bidsDir: string, subjectIds: string[]) => {
    if (!selectedExecution) {
      setError('Please select a plugin or workflow first');
      return;
    }
    if (selectedExecution.type !== 'workflow') {
      setError('BIDS batch mode is only available for workflows. Select a workflow pipeline.');
      return;
    }
    const mismatch = checkPathComputeMismatch(bidsDir, selectedBackend);
    if (mismatch?.blockSubmit) {
      setError(mismatch.message);
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const wfP: Record<string, string> = {};
      const result = await apiService.submitWorkflowBatch(
        selectedExecution.id,
        bidsDir,
        subjectIds,
        wfP,
        customResources || undefined,
      );
      const jobIds = result.jobs.map((j) => j.job_id);

      if (result.errors.length > 0) {
        const errMsg = result.errors.map((e) => `${e.subject_id}: ${e.error}`).join('; ');
        setError(`Submitted ${result.submitted}/${result.total_subjects} jobs. Failures: ${errMsg}`);
      }

      if (jobIds.length > 0) onJobsSubmitted(jobIds);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to submit BIDS batch.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSingleFileSubmit = async () => {
    if (!selectedPipeline) {
      setError('Please select a plugin or workflow first');
      return;
    }
    if (!uploadedFilePath) {
      setError('Please select a file or folder first');
      return;
    }
    if (pathMismatch?.blockSubmit) {
      setError(pathMismatch.message);
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const wfP: Record<string, string> = {};

      if (bidsWorkflow && selectedExecution?.type === 'workflow' && selectedExecution.id) {
        const parsed = parseBidsSubjectPath(uploadedFilePath);
        let bidsDir = uploadedFilePath;
        let subjectId: string | undefined;

        if (parsed) {
          bidsDir = parsed.bidsDir;
          subjectId = parsed.subjectId;
        } else {
          const info = await apiService.browseDirectory(uploadedFilePath, browseMode);
          const subjects = (info.directories || [])
            .map((d: { name: string }) => d.name)
            .filter((n: string) => n.startsWith('sub-'))
            .map((n: string) => n.replace(/^sub-/, ''));
          if (subjects.length === 1) {
            subjectId = subjects[0];
          } else if (subjects.length > 1) {
            setError(
              'Multiple subjects in this dataset — select a sub-XXX folder for one subject, or use BIDS batch mode.',
            );
            return;
          } else {
            setError('No sub-* folders found. Choose a BIDS dataset root or a sub-XXX folder.');
            return;
          }
        }

        const params = { ...resourceParams(customResources), subject_id: subjectId, ...wfP };
        const result = await apiService.submitWorkflowJob(
          selectedExecution.id,
          [bidsDir],
          params,
          customResources || undefined,
        );
        onJobsSubmitted([result.job_id]);
        return;
      }

      if (selectedExecution?.type === 'plugin' && selectedExecution.id) {
        const result = await apiService.submitPluginJob(
          selectedExecution.id,
          [uploadedFilePath],
          resourceParams(customResources),
          customResources || undefined,
        );
        onJobsSubmitted([result.job_id]);
      } else if (selectedExecution?.type === 'workflow' && selectedExecution.id) {
        const result = await apiService.submitWorkflowJob(
          selectedExecution.id,
          [uploadedFilePath],
          wfP,
          customResources || undefined,
        );
        onJobsSubmitted([result.job_id]);
      } else {
        const result = await apiService.submitJob(
          selectedPipeline.name,
          [uploadedFilePath],
          {},
          customResources || undefined,
        );
        onJobsSubmitted([result.job_id]);
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to submit job.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Process MRI Data</h2>
          <p className="mt-0.5 text-sm text-gray-500">
            Connect compute, browse input on that backend, and submit. Copy data from
            Pennsieve, XNAT, or another host with Transfer first.
          </p>
        </div>
        {onBack && (
          <button
            onClick={onBack}
            className="shrink-0 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            &larr; Back
          </button>
        )}
      </div>

      {onNavigateToTransfer && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200/80 bg-amber-50/60 px-3 py-2 text-xs text-amber-900">
          <span>
            Need data from Pennsieve, XNAT, or another machine? Stage it with Transfer — Jobs runs
            on the compute backend only.
          </span>
          <button
            type="button"
            onClick={onNavigateToTransfer}
            className="inline-flex items-center gap-1 font-medium text-navy-700 hover:text-navy-900"
          >
            Open Transfer
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-5 lg:items-start">
        <div className="space-y-4 min-w-0">
          <BackendSelector
            selectedBackend={selectedBackend}
            onBackendChange={setSelectedBackend}
            sshConfig={sshConfig}
            onSSHConfigChange={setSSHConfig}
            onSSHConnectionChange={setSSHConnected}
            jobsMode
          />

          {selectedPipeline && (
            <div className="rounded-xl border border-gray-100 bg-slate-50/40 p-4 space-y-4">
              <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5">
                <button
                  type="button"
                  onClick={() => setMode('single')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition ${
                    mode === 'single' ? 'bg-navy-600 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <Upload className="h-3.5 w-3.5" />
                  Single
                </button>
                <button
                  type="button"
                  onClick={() => setMode('directory')}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition ${
                    mode === 'directory' ? 'bg-navy-600 text-white shadow-sm' : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <FolderOpen className="h-3.5 w-3.5" />
                  Batch
                </button>
              </div>

              {pathMismatch && (
                <div className="flex gap-2 p-2.5 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900">
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                  <p>{pathMismatch.message}</p>
                </div>
              )}

              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded">
                  <p className="text-xs text-red-700">{error}</p>
                </div>
              )}
              {submitting && (
                <div className="p-3 bg-navy-50 border border-navy-200 rounded">
                  <p className="text-xs text-navy-700">Submitting jobs...</p>
                </div>
              )}

              <div style={submitting ? { opacity: 0.5, pointerEvents: 'none' } : undefined}>
                {mode === 'directory' ? (
                  <DirectorySelector
                    mode={browseMode}
                    sshConnected={selectedBackend === 'local' ? true : sshConnected}
                    onSubmit={handleBatchSubmit}
                    onBidsSubmit={handleBidsBatchSubmit}
                    bidsAppMode={bidsWorkflow}
                    initialPath={prefillInputDir}
                    onInputDirChange={setBatchInputDir}
                  />
                ) : (
                  <>
                    <SingleFileUpload
                      browseMode={browseMode}
                      sshConnected={selectedBackend === 'local' ? true : sshConnected}
                      onFileUploaded={(path) => {
                        setUploadedFilePath(path);
                        setError(null);
                      }}
                      executionContext={
                        selectedExecution
                          ? { type: selectedExecution.type, id: selectedExecution.id }
                          : null
                      }
                      inputFormatName={selectedExecution?.inputFormatName}
                      bidsAppMode={bidsWorkflow}
                      initialPath={prefillInputDir}
                    />
                    <div className="mt-3">
                      <button
                        onClick={handleSingleFileSubmit}
                        disabled={!uploadedFilePath || submitting || submitBlocked}
                        className="w-full py-2 px-4 bg-navy-600 text-white rounded-md hover:bg-navy-800 font-medium text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {submitting ? 'Submitting…' : 'Submit Job'}
                      </button>
                      {!uploadedFilePath && (
                        <p className="mt-1.5 text-[11px] text-gray-500 text-center">
                          Choose a subject path above to enable submit.
                        </p>
                      )}
                      {uploadedFilePath && submitBlocked && (
                        <p className="mt-1.5 text-[11px] text-amber-700 text-center">
                          Fix the path warning above before submitting.
                        </p>
                      )}
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4 min-w-0">
          <PipelineSelector
            onPipelineSelect={setSelectedPipeline}
            selectedPipeline={selectedPipeline}
            onExecutionSelect={setSelectedExecution}
          />

          {selectedPipeline && (
            <ResourceSelector
              plugin={selectedPipeline}
              backendType={
                selectedBackend === 'local'
                  ? 'local'
                  : selectedBackend === 'remote_hpc'
                    ? 'hpc'
                    : 'remote'
              }
              onResourcesChange={setCustomResources}
            />
          )}
        </div>
      </div>
    </div>
  );
};
