/**
 * DirectorySelector Component
 * 
 * Allows users to browse and select input/output directories
 * for batch processing of neuroimaging data.
 * 
 * Works in both local and HPC modes.
 */

import React, { useState } from 'react';
import { FolderOpen, File, AlertCircle, CheckCircle2 } from 'lucide-react';
import { apiService } from '../services/api';
import type { DirectoryInfo } from '../types';

interface DirectorySelectorProps {
  mode: 'local' | 'hpc';
  onSubmit: (inputDir: string, outputDir: string, files: string[]) => void;
  onCancel?: () => void;
}

export const DirectorySelector: React.FC<DirectorySelectorProps> = ({ 
  mode, 
  onSubmit, 
  onCancel 
}) => {
  const [inputDir, setInputDir] = useState('');
  const [outputDir, setOutputDir] = useState('');
  const [directoryInfo, setDirectoryInfo] = useState<DirectoryInfo | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleBrowseInput = async () => {
    if (!inputDir.trim()) {
      setError('Please enter a directory path');
      return;
    }

    setScanning(true);
    setError(null);

    try {
      const info = await apiService.browseDirectory(inputDir, mode);
      setDirectoryInfo(info);
      
      if (info.nifti_files.length === 0) {
        setError('No NIfTI files (.nii or .nii.gz) found in this directory');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to browse directory');
      setDirectoryInfo(null);
    } finally {
      setScanning(false);
    }
  };

  const handleSubmit = () => {
    if (!inputDir || !outputDir) {
      setError('Please specify both input and output directories');
      return;
    }

    if (!directoryInfo || directoryInfo.nifti_files.length === 0) {
      setError('No files to process. Please browse input directory first.');
      return;
    }

    onSubmit(inputDir, outputDir, directoryInfo.nifti_files);
  };

  return (
    <div className="space-y-6">
      <div className="bg-white shadow sm:rounded-lg p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="text-lg font-medium text-gray-900">
              {mode === 'local' ? 'Local' : 'HPC'} Directory Selection
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Select directories for batch processing. Data stays in place.
            </p>
          </div>
          {onCancel && (
            <button
              onClick={onCancel}
              className="text-sm text-gray-600 hover:text-gray-800"
            >
              Cancel
            </button>
          )}
        </div>

        {/* Input Directory */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">
            Input Directory <span className="text-red-500">*</span>
          </label>
          <p className="text-xs text-gray-500">
            Directory containing your NIfTI files (.nii or .nii.gz)
          </p>
          <div className="flex space-x-2">
            <input
              type="text"
              value={inputDir}
              onChange={(e) => {
                setInputDir(e.target.value);
                setDirectoryInfo(null); // Clear previous scan
              }}
              placeholder={
                mode === 'local'
                  ? '/home/user/scans or C:\\Users\\user\\scans'
                  : '/scratch/username/scans'
              }
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
              onKeyPress={(e) => e.key === 'Enter' && handleBrowseInput()}
            />
            <button
              onClick={handleBrowseInput}
              disabled={scanning || !inputDir.trim()}
              className="px-4 py-2 bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              <FolderOpen className="h-4 w-4 mr-2" />
              {scanning ? 'Scanning...' : 'Browse'}
            </button>
          </div>
        </div>

        {/* Output Directory */}
        <div className="space-y-2 mt-4">
          <label className="block text-sm font-medium text-gray-700">
            Output Directory <span className="text-red-500">*</span>
          </label>
          <p className="text-xs text-gray-500">
            Directory where results will be saved (will be created if it doesn't exist)
          </p>
          <div className="flex space-x-2">
            <input
              type="text"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
              placeholder={
                mode === 'local'
                  ? '/home/user/results or C:\\Users\\user\\results'
                  : '/scratch/username/results'
              }
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-navy-500 focus:border-navy-500"
            />
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-md flex items-start">
            <AlertCircle className="h-5 w-5 text-red-600 mr-3 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-red-800">Error</h4>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Files Found */}
        {directoryInfo && directoryInfo.nifti_files.length > 0 && (
          <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-md">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center">
                <CheckCircle2 className="h-5 w-5 text-green-600 mr-2" />
                <h4 className="text-sm font-medium text-green-800">
                  Found {directoryInfo.nifti_files.length} NIfTI file{directoryInfo.nifti_files.length !== 1 ? 's' : ''}
                </h4>
              </div>
            </div>

            {/* File List (show first 10) */}
            <div className="max-h-48 overflow-y-auto space-y-1 bg-white rounded p-3">
              {directoryInfo.nifti_files.slice(0, 10).map((file, idx) => (
                <div key={idx} className="text-sm text-gray-700 flex items-center py-1">
                  <File className="h-3 w-3 mr-2 text-gray-400 flex-shrink-0" />
                  <span className="truncate">{file}</span>
                </div>
              ))}
              {directoryInfo.nifti_files.length > 10 && (
                <div className="text-sm text-gray-500 italic pt-2 border-t">
                  ... and {directoryInfo.nifti_files.length - 10} more file{directoryInfo.nifti_files.length - 10 !== 1 ? 's' : ''}
                </div>
              )}
            </div>

            {/* Summary */}
            <div className="mt-3 text-xs text-gray-600 space-y-1">
              <p><strong>Input:</strong> {inputDir}</p>
              <p><strong>Output:</strong> {outputDir || '(not set)'}</p>
              <p><strong>Total files:</strong> {directoryInfo.files.length} (NIfTI: {directoryInfo.nifti_files.length})</p>
            </div>
          </div>
        )}

        {/* Submit Button */}
        <button
          onClick={handleSubmit}
          disabled={
            !inputDir || 
            !outputDir || 
            !directoryInfo || 
            directoryInfo.nifti_files.length === 0
          }
          className="mt-6 w-full py-3 px-4 bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center justify-center"
        >
          <CheckCircle2 className="h-5 w-5 mr-2" />
          Process {directoryInfo?.nifti_files.length || 0} File{directoryInfo?.nifti_files.length !== 1 ? 's' : ''}
        </button>

        {/* Help Text */}
        <div className="mt-4 p-3 bg-navy-50 border border-navy-100 rounded-md">
          <p className="text-xs text-gray-700">
            <strong>Note:</strong> Files will be processed in place. No data will be uploaded or moved. 
            Each file will get its own job and output subdirectory.
          </p>
        </div>
      </div>
    </div>
  );
};
