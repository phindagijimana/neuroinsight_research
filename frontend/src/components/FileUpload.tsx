/**
 * FileUpload Component
 * 
 * Main component that allows users to choose between:
 * 1. Directory-based batch processing (recommended)
 * 2. Single file upload (for testing)
 */

import React, { useState } from 'react';
import { Upload, FolderOpen } from 'lucide-react';
import { DirectorySelector } from './DirectorySelector';
import { SingleFileUpload } from './SingleFileUpload';
import { PipelineSelector } from './PipelineSelector';
import { ResourceSelector, ResourceConfig } from './ResourceSelector';
import { BackendSelector, BackendType, SSHConfig } from './BackendSelector';
import { apiService } from '../services/api';
import type { Pipeline } from '../types';

type UploadMode = 'directory' | 'single';

interface FileUploadProps {
  onJobsSubmitted: (jobIds: string[]) => void;
  onBack?: () => void;
}

// Track which plugin/workflow was selected from PipelineSelector
interface SelectedExecution {
  type: 'plugin' | 'workflow';
  id: string;
  name: string;
}

export const FileUpload: React.FC<FileUploadProps> = ({ onJobsSubmitted, onBack }) => {
  const [mode, setMode] = useState<UploadMode>('directory'); // Default to directory mode
  const [selectedPipeline, setSelectedPipeline] = useState<Pipeline | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customResources, setCustomResources] = useState<ResourceConfig | null>(null);
  const [selectedExecution, setSelectedExecution] = useState<SelectedExecution | null>(null);

  // Backend selection
  const [selectedBackend, setSelectedBackend] = useState<BackendType>('local');
  const [sshConfig, setSSHConfig] = useState<SSHConfig>({ host: '', username: '', port: 22 });

  // For single file mode
  const [uploadedFilePath, setUploadedFilePath] = useState<string | null>(null);

  const handleBatchSubmit = async (inputDir: string, outputDir: string, files: string[]) => {
    if (!selectedPipeline) {
      setError('Please select a plugin or workflow first');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      // Submit one job per file in the directory
      const jobIds: string[] = [];
      
      for (const file of files) {
        const filePath = `${inputDir}/${file}`;
        
        if (selectedExecution?.type === 'plugin' && selectedExecution.id) {
          const result = await apiService.submitPluginJob(
            selectedExecution.id,
            [filePath],
            {},
            customResources || undefined,
          );
          jobIds.push(result.job_id);
        } else if (selectedExecution?.type === 'workflow' && selectedExecution.id) {
          const result = await apiService.submitWorkflowJob(
            selectedExecution.id,
            [filePath],
            {},
            customResources || undefined,
          );
          jobIds.push(result.job_id);
        } else {
          // Fallback to legacy batch submit
          const result = await apiService.submitBatchJob({
            pipeline_name: selectedPipeline.name,
            input_dir: inputDir,
            output_dir: outputDir,
            parameters: {},
            file_pattern: '*.nii.gz',
            custom_resources: customResources || undefined,
          });
          jobIds.push(...result.job_ids);
          break; // Legacy batch handles all files at once
        }
      }

      onJobsSubmitted(jobIds);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit batch job');
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
      setError('Please upload a file first');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      if (selectedExecution?.type === 'plugin' && selectedExecution.id) {
        const result = await apiService.submitPluginJob(
          selectedExecution.id,
          [uploadedFilePath],
          {},
          customResources || undefined,
        );
        onJobsSubmitted([result.job_id]);
      } else if (selectedExecution?.type === 'workflow' && selectedExecution.id) {
        const result = await apiService.submitWorkflowJob(
          selectedExecution.id,
          [uploadedFilePath],
          {},
          customResources || undefined,
        );
        onJobsSubmitted([result.job_id]);
      } else {
        // Fallback to legacy submit
        const result = await apiService.submitJob(
          selectedPipeline.name,
          [uploadedFilePath],
          {},
          customResources || undefined,
        );
        onJobsSubmitted([result.job_id]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit job');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Process MRI Data</h2>
          <p className="mt-1 text-sm text-gray-600">
            Select execution backend, pipeline, and input data
          </p>
        </div>
        {onBack && (
          <button
            onClick={onBack}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
          >
            &larr; Back
          </button>
        )}
      </div>

      {/* Grid Layout: 2 Rows x 2 Columns */}
      <div className="space-y-4">
        {/* Row 1: Backend + Resource Configuration */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <BackendSelector
            selectedBackend={selectedBackend}
            onBackendChange={setSelectedBackend}
            sshConfig={sshConfig}
            onSSHConfigChange={setSSHConfig}
          />

          {selectedPipeline && (
            <ResourceSelector
              plugin={selectedPipeline}
              backendType={selectedBackend === 'local' ? 'local' : selectedBackend === 'remote_hpc' ? 'hpc' : 'remote'}
              onResourcesChange={setCustomResources}
            />
          )}
        </div>

        {/* Row 2: Input Mode & Directory + Pipeline Selector */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {selectedPipeline && (
            <div className="bg-white rounded-lg border border-gray-200 p-4 space-y-4 flex flex-col h-full">
              {/* Mode Toggle */}
              <div>
                <h3 className="text-sm font-semibold text-gray-700 mb-3">Input Mode</h3>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setMode('directory')}
                    className={`p-3 rounded-md border transition-all ${
                      mode === 'directory'
                        ? 'border-navy-600 bg-navy-50'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center mb-1">
                      <FolderOpen className={`h-4 w-4 mr-1.5 ${
                        mode === 'directory' ? 'text-navy-600' : 'text-gray-400'
                      }`} />
                      <span className="text-sm font-medium text-gray-900">
                        Batch
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 text-left">
                      Multiple files
                    </p>
                  </button>

                  <button
                    onClick={() => setMode('single')}
                    className={`p-3 rounded-md border transition-all ${
                      mode === 'single'
                        ? 'border-navy-600 bg-navy-50'
                        : 'border-gray-200 bg-white hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center mb-1">
                      <Upload className={`h-4 w-4 mr-1.5 ${
                        mode === 'single' ? 'text-navy-600' : 'text-gray-400'
                      }`} />
                      <span className="text-sm font-medium text-gray-900">
                        Single
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 text-left">
                      One file
                    </p>
                  </button>
                </div>
              </div>

              {/* Error Message */}
              {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded">
                  <p className="text-xs text-red-700">{error}</p>
                </div>
              )}

              {/* Submitting State */}
              {submitting && (
                <div className="p-3 bg-navy-50 border border-navy-200 rounded">
                  <p className="text-xs text-navy-700">Submitting jobs...</p>
                </div>
              )}

              {/* Show selected mode component */}
              {!submitting && (
                <div className="flex-1">
                  {mode === 'directory' ? (
                    <DirectorySelector
                      mode={selectedBackend === 'local' ? 'local' : selectedBackend === 'remote_hpc' ? 'hpc' : 'remote'}
                      onSubmit={handleBatchSubmit}
                    />
                  ) : (
                    <>
                      <SingleFileUpload
                        onFileUploaded={(path) => {
                          setUploadedFilePath(path);
                          setError(null);
                        }}
                      />
                      
                      {uploadedFilePath && (
                        <div className="mt-3">
                          <button
                            onClick={handleSingleFileSubmit}
                            className="w-full py-2 px-4 bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] font-medium text-sm"
                          >
                            Submit Job
                          </button>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          )}

          <PipelineSelector
            onPipelineSelect={setSelectedPipeline}
            selectedPipeline={selectedPipeline}
            onExecutionSelect={setSelectedExecution}
          />
        </div>
      </div>
    </div>
  );
};
