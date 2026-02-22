/**
 * SingleFileUpload Component
 *
 * Two ways to select a single file for processing:
 *   1. Browse the server/HPC filesystem and click a file
 *   2. Upload a file from the user's local machine
 */

import React, { useState, useEffect } from 'react';
import {
  Upload, FileUp, AlertCircle, FolderOpen, File, FileText,
  ChevronRight, ArrowUp, Loader2, CheckCircle2,
} from 'lucide-react';
import { apiService } from '../services/api';

type BrowseMode = 'local' | 'remote' | 'hpc';

interface BrowseEntry {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
}

interface SingleFileUploadProps {
  onFileUploaded: (filePath: string) => void;
  onCancel?: () => void;
  browseMode?: BrowseMode;
}

const isNifti = (name: string) => /\.(nii|nii\.gz)$/i.test(name);

function formatSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export const SingleFileUpload: React.FC<SingleFileUploadProps> = ({
  onFileUploaded,
  onCancel,
  browseMode = 'local',
}) => {
  const [tab, setTab] = useState<'browse' | 'upload'>('browse');

  // --- Browse state ---
  const defaultPath = browseMode === 'local' ? './data' : '~';
  const [browserPath, setBrowserPath] = useState(defaultPath);
  const [browserParent, setBrowserParent] = useState<string | null>(null);
  const [entries, setEntries] = useState<BrowseEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [browserError, setBrowserError] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [manualPath, setManualPath] = useState('');

  // --- Upload state ---
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Reset browser on mode change
  useEffect(() => {
    const p = browseMode === 'local' ? './data' : '~';
    setBrowserPath(p);
    setSelectedPath(null);
    setManualPath('');
  }, [browseMode]);

  // Auto-load on mount
  useEffect(() => {
    if (tab === 'browse') loadDir(browserPath);
  }, [tab]);

  const loadDir = async (path: string) => {
    setLoading(true);
    setBrowserError(null);
    try {
      const data = await apiService.browseDirectory(path, browseMode);
      const dirs: BrowseEntry[] = (data.directories || []).map((d: any) => ({
        name: d.name, path: d.path, type: 'directory' as const,
      }));
      const files: BrowseEntry[] = (data.files || []).map((f: any) => ({
        name: f.name, path: f.path, type: 'file' as const, size: f.size,
      }));
      setEntries([...dirs, ...files]);
      setBrowserPath(data.path || path);
      setBrowserParent(data.parent || null);
    } catch (err: any) {
      setBrowserError(err.response?.data?.detail || 'Failed to browse');
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  const selectFile = (entry: BrowseEntry) => {
    setSelectedPath(entry.path);
    setManualPath(entry.path);
    onFileUploaded(entry.path);
  };

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (manualPath.trim()) {
      setSelectedPath(manualPath.trim());
      onFileUploaded(manualPath.trim());
    }
  };

  // --- Upload handlers ---
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
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
        (progress) => setUploadProgress(progress),
      );
      onFileUploaded(result.path);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed.');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const modeLabel = browseMode === 'local' ? 'Server' : browseMode === 'hpc' ? 'HPC' : 'Remote';

  return (
    <div className="space-y-3">
      {/* Tab switcher */}
      <div className="flex border-b border-gray-200">
        <button
          onClick={() => setTab('browse')}
          className={`px-3 py-1.5 text-xs font-medium border-b-2 transition ${
            tab === 'browse'
              ? 'border-[#003d7a] text-[#003d7a]'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <FolderOpen className="h-3.5 w-3.5 inline mr-1" />
          Browse {modeLabel}
        </button>
        <button
          onClick={() => setTab('upload')}
          className={`px-3 py-1.5 text-xs font-medium border-b-2 transition ${
            tab === 'upload'
              ? 'border-[#003d7a] text-[#003d7a]'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Upload className="h-3.5 w-3.5 inline mr-1" />
          Upload
        </button>
      </div>

      {/* ===== Browse tab ===== */}
      {tab === 'browse' && (
        <div className="space-y-2">
          {/* Manual path input */}
          <form onSubmit={handleManualSubmit} className="flex gap-2">
            <input
              type="text"
              value={manualPath}
              onChange={e => setManualPath(e.target.value)}
              placeholder="Type a file path or browse below"
              className="flex-1 px-2.5 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#003d7a]"
            />
            <button
              type="submit"
              disabled={!manualPath.trim()}
              className="px-3 py-1.5 text-xs font-medium bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] disabled:opacity-50"
            >
              Use Path
            </button>
          </form>

          {/* File browser */}
          <div className="border border-gray-200 rounded-lg overflow-hidden">
            {/* Toolbar */}
            <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-gray-100 bg-gray-50">
              <button
                onClick={() => browserParent && loadDir(browserParent)}
                disabled={!browserParent}
                className="p-1 rounded hover:bg-gray-200 text-gray-500 disabled:opacity-30"
              >
                <ArrowUp className="h-3.5 w-3.5" />
              </button>
              <div className="flex-1 px-2 py-1 text-xs text-gray-600 bg-white rounded font-mono truncate border border-gray-100">
                {browserPath}
              </div>
              <button onClick={() => loadDir(browserPath)} className="p-1 rounded hover:bg-gray-200 text-gray-500">
                <Loader2 className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>

            {/* Entries */}
            <div className="max-h-48 overflow-y-auto">
              {loading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-4 w-4 text-[#003d7a] animate-spin mr-2" />
                  <span className="text-xs text-gray-500">Loading...</span>
                </div>
              )}

              {browserError && (
                <div className="flex items-center gap-2 mx-3 my-2 text-xs text-red-600 bg-red-50 px-3 py-2 rounded">
                  <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                  {browserError}
                </div>
              )}

              {!loading && entries.length === 0 && !browserError && (
                <p className="text-xs text-gray-400 py-6 text-center">Empty directory</p>
              )}

              {!loading && entries.map(entry => {
                const isFile = entry.type === 'file';
                const nifti = isFile && isNifti(entry.name);
                const isSelected = selectedPath === entry.path;

                return (
                  <div
                    key={entry.path}
                    className={`flex items-center px-3 py-1.5 text-xs cursor-pointer border-b border-gray-50 group transition ${
                      isSelected ? 'bg-blue-50 border-blue-100' : 'hover:bg-gray-50'
                    }`}
                    onClick={() => isFile ? selectFile(entry) : loadDir(entry.path)}
                  >
                    {isFile ? (
                      nifti ? <FileText className="h-3.5 w-3.5 text-green-600 mr-2 flex-shrink-0" />
                        : <File className="h-3.5 w-3.5 text-gray-400 mr-2 flex-shrink-0" />
                    ) : (
                      <FolderOpen className="h-3.5 w-3.5 text-yellow-500 mr-2 flex-shrink-0" />
                    )}
                    <span className={`flex-1 truncate ${
                      isSelected ? 'font-semibold text-[#003d7a]' :
                      !isFile ? 'font-medium text-gray-800' :
                      nifti ? 'text-green-700' : 'text-gray-600'
                    }`}>
                      {entry.name}
                    </span>
                    {nifti && <span className="text-[9px] bg-green-100 text-green-700 px-1 py-0.5 rounded font-medium mr-1">NIfTI</span>}
                    {isFile && <span className="text-[10px] text-gray-400 mr-1">{formatSize(entry.size)}</span>}
                    {isFile && (
                      <button
                        onClick={e => { e.stopPropagation(); selectFile(entry); }}
                        className="text-[10px] text-white bg-[#003d7a] px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition"
                      >
                        Select
                      </button>
                    )}
                    {!isFile && <ChevronRight className="h-3 w-3 text-gray-300" />}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Selected file info */}
          {selectedPath && (
            <div className="flex items-center gap-2 p-2.5 bg-green-50 border border-green-200 rounded-md">
              <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-green-800 truncate">{selectedPath}</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ===== Upload tab ===== */}
      {tab === 'upload' && (
        <div className="space-y-3">
          <div className="flex items-center justify-center w-full">
            <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-gray-300 border-dashed rounded-lg cursor-pointer bg-gray-50 hover:bg-gray-100">
              <div className="flex flex-col items-center justify-center py-4">
                <FileUp className="w-8 h-8 mb-2 text-gray-400" />
                <p className="text-xs text-gray-500">
                  <span className="font-semibold">Click to upload</span> or drag and drop
                </p>
                <p className="text-[10px] text-gray-400">Any file type</p>
              </div>
              <input type="file" onChange={handleFileSelect} className="hidden" disabled={uploading} />
            </label>
          </div>

          {selectedFile && (
            <div className="flex items-center gap-2 p-2.5 bg-gray-50 rounded-md">
              <FileUp className="h-4 w-4 text-gray-400 flex-shrink-0" />
              <span className="text-xs font-medium text-gray-900 truncate flex-1">{selectedFile.name}</span>
              <span className="text-xs text-gray-500">{formatSize(selectedFile.size)}</span>
            </div>
          )}

          {error && (
            <div className="p-2 bg-red-50 border border-red-200 rounded flex items-center gap-2">
              <AlertCircle className="h-3.5 w-3.5 text-red-600 flex-shrink-0" />
              <p className="text-xs text-red-700">{error}</p>
            </div>
          )}

          {uploading && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-gray-600">
                <span>Uploading...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div className="bg-[#003d7a] h-1.5 rounded-full transition-all" style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className="w-full flex items-center justify-center py-2 px-4 bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] font-medium text-xs disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Upload className="h-4 w-4 mr-1.5" />
            {uploading ? 'Uploading...' : 'Upload File'}
          </button>
        </div>
      )}
    </div>
  );
};
