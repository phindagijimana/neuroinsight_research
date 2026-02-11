/**
 * SingleFileUpload Component
 * 
 * For uploading a single NIfTI file (testing/demo purposes)
 * Alternative to batch directory processing
 */

import React, { useState } from 'react';
import { Upload, FileUp, AlertCircle } from 'lucide-react';
import { apiService } from '../services/api';

interface SingleFileUploadProps {
  onFileUploaded: (filePath: string) => void;
  onCancel?: () => void;
}

export const SingleFileUpload: React.FC<SingleFileUploadProps> = ({ 
  onFileUploaded, 
  onCancel 
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    
    if (!file) return;

    // Validate file type
    if (!file.name.endsWith('.nii') && !file.name.endsWith('.nii.gz')) {
      setError('Please select a NIfTI file (.nii or .nii.gz)');
      return;
    }

    // Validate file size (warn if > 500MB)
    const sizeMB = file.size / 1024 / 1024;
    if (sizeMB > 500) {
      if (!confirm(`This file is ${sizeMB.toFixed(0)}MB. Large uploads may take a while. Continue?`)) {
        return;
      }
    }

    setSelectedFile(file);
    setError(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      const result = await apiService.uploadFile(
        selectedFile,
        (progress) => setUploadProgress(progress)
      );

      onFileUploaded(result.path);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  return (
    <div className="bg-white shadow sm:rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-medium text-gray-900">Upload Single File</h3>
          <p className="mt-1 text-sm text-gray-500">
            Upload one NIfTI file for testing or demo purposes
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

      {/* File Input */}
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select NIfTI File
          </label>
          <div className="flex items-center justify-center w-full">
            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                <FileUp className="w-10 h-10 mb-3 text-gray-400" />
                <p className="mb-2 text-sm text-gray-500">
                  <span className="font-semibold">Click to upload</span> or drag and drop
                </p>
                <p className="text-xs text-gray-500">NIfTI files (.nii, .nii.gz)</p>
              </div>
              <input
                type="file"
                accept=".nii,.nii.gz"
                onChange={handleFileSelect}
                className="hidden"
                disabled={uploading}
              />
            </label>
          </div>
        </div>

        {/* Selected File Info */}
        {selectedFile && (
          <div className="bg-gray-50 p-4 rounded-md">
            <div className="flex items-start">
              <FileUp className="h-5 w-5 text-gray-400 mr-3 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {selectedFile.name}
                </p>
                <p className="text-sm text-gray-500">
                  Size: {formatFileSize(selectedFile.size)}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md flex items-start">
            <AlertCircle className="h-5 w-5 text-red-600 mr-3 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-medium text-red-800">Upload Failed</h4>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Upload Progress */}
        {uploading && (
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-gray-600">
              <span>Uploading...</span>
              <span>{uploadProgress}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-[#003d7a] h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}

        {/* Upload Button */}
        <button
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
          className="w-full flex items-center justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-[#003d7a] hover:bg-[#002b55] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#003d7a] disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Upload className="h-5 w-5 mr-2" />
          {uploading ? 'Uploading...' : 'Upload File'}
        </button>

        {/* Help Text */}
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md">
          <p className="text-xs text-yellow-800">
            <strong>Note:</strong> For processing multiple files, use the "Process Directory (Batch)" mode instead. 
            It's much faster and doesn't require uploading files.
          </p>
        </div>
      </div>
    </div>
  );
};
