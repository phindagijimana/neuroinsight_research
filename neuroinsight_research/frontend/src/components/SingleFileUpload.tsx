/**
 * SingleFileUpload Component (Single Subject Mode)
 *
 * Browse to select one subject's folder or file for processing.
 * Supports visual browsing, direct path entry, and reusing outputs
 * from previously completed jobs.
 */

import React, { useState, useEffect } from 'react';
import {
  AlertCircle, FolderOpen, File, FileText,
  ChevronRight, ArrowUp, Loader2, CheckCircle2,
  History,
} from 'lucide-react';
import { apiService } from '../services/api';

type BrowseMode = 'local' | 'remote' | 'hpc';

interface BrowseEntry {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
}

interface ReusableOutput {
  job_id: string;
  job_pipeline: string;
  completed_at: string | null;
  subject_id: string;
  provides: string;
  plugin_id: string;
  output_path: string;
}

interface SingleFileUploadProps {
  onFileUploaded: (filePath: string) => void;
  onCancel?: () => void;
  browseMode?: BrowseMode;
  /** Current execution context — enables "Previous Results" filtering */
  executionContext?: { type: 'plugin' | 'workflow'; id: string } | null;
}

const isNifti = (name: string) => /\.(nii|nii\.gz)$/i.test(name);

function formatSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffH = Math.floor(diffMs / 3600000);
  if (diffH < 1) return 'just now';
  if (diffH < 24) return `${diffH}h ago`;
  const diffD = Math.floor(diffH / 24);
  if (diffD < 7) return `${diffD}d ago`;
  return d.toLocaleDateString();
}

function friendlyPipeline(name: string): string {
  if (name.startsWith('workflow:')) return name.replace('workflow:', '').replace(/_/g, ' ');
  return name.replace(/_/g, ' ');
}

export const SingleFileUpload: React.FC<SingleFileUploadProps> = ({
  onFileUploaded,
  browseMode = 'local',
  executionContext,
}) => {
  const defaultPath = browseMode === 'local' ? './data' : '~';

  const [browserOpen, setBrowserOpen] = useState(false);
  const [browserPath, setBrowserPath] = useState(defaultPath);
  const [browserParent, setBrowserParent] = useState<string | null>(null);
  const [entries, setEntries] = useState<BrowseEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [browserError, setBrowserError] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [manualPath, setManualPath] = useState('');

  // Previous results state
  const [prevResultsOpen, setPrevResultsOpen] = useState(false);
  const [prevResults, setPrevResults] = useState<ReusableOutput[]>([]);
  const [prevLoading, setPrevLoading] = useState(false);
  const [prevError, setPrevError] = useState<string | null>(null);
  const [selectedPrevResult, setSelectedPrevResult] = useState<ReusableOutput | null>(null);

  useEffect(() => {
    const p = browseMode === 'local' ? './data' : '~';
    setBrowserPath(p);
    setSelectedPath(null);
    setManualPath('');
    setSelectedPrevResult(null);
  }, [browseMode]);

  useEffect(() => {
    if (browserOpen) loadDir(browserPath);
  }, [browserOpen]);

  // Load previous results when panel opens
  useEffect(() => {
    if (prevResultsOpen) loadPreviousResults();
  }, [prevResultsOpen, executionContext?.id]);

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

  const loadPreviousResults = async () => {
    setPrevLoading(true);
    setPrevError(null);
    try {
      const params: { plugin_id?: string; workflow_id?: string } = {};
      if (executionContext?.type === 'plugin') {
        params.plugin_id = executionContext.id;
      } else if (executionContext?.type === 'workflow') {
        params.workflow_id = executionContext.id;
      }
      const data = await apiService.getReusableOutputs(params);
      setPrevResults(data.outputs);
    } catch (err: any) {
      setPrevError(err.response?.data?.detail || 'Failed to load previous results');
      setPrevResults([]);
    } finally {
      setPrevLoading(false);
    }
  };

  const selectFile = (entry: BrowseEntry) => {
    setSelectedPath(entry.path);
    setManualPath(entry.path);
    setSelectedPrevResult(null);
    onFileUploaded(entry.path);
  };

  const selectFolder = (path: string) => {
    setSelectedPath(path);
    setManualPath(path);
    setSelectedPrevResult(null);
    onFileUploaded(path);
    setBrowserOpen(false);
  };

  const selectPreviousResult = (result: ReusableOutput) => {
    setSelectedPrevResult(result);
    setSelectedPath(result.output_path);
    setManualPath(result.output_path);
    onFileUploaded(result.output_path);
    setPrevResultsOpen(false);
  };

  const handleManualSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (manualPath.trim()) {
      setSelectedPath(manualPath.trim());
      setSelectedPrevResult(null);
      onFileUploaded(manualPath.trim());
    }
  };

  const modeLabel = browseMode === 'local' ? 'Server' : browseMode === 'hpc' ? 'HPC' : 'Remote';
  const niftiInBrowser = entries.filter(e => e.type === 'file' && isNifti(e.name)).length;
  const dirsInBrowser = entries.filter(e => e.type === 'directory').length;

  return (
    <div className="space-y-3">
      {/* Path input */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-gray-700">
          Subject Path <span className="text-red-500">*</span>
        </label>
        <p className="text-[11px] text-gray-500">
          Browse to a subject folder, NIfTI file, or pick from previous results
        </p>
        <form onSubmit={handleManualSubmit} className="flex gap-2">
          <input
            type="text"
            value={manualPath}
            onChange={e => { setManualPath(e.target.value); setSelectedPath(null); setSelectedPrevResult(null); }}
            placeholder={browseMode === 'local' ? './data/sub-001/T1w.nii.gz' : '/scratch/username/sub-001'}
            className="flex-1 px-2.5 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#003d7a] focus:border-[#003d7a]"
          />
          <button
            onClick={() => { setBrowserOpen(!browserOpen); setPrevResultsOpen(false); }}
            type="button"
            className="px-3 py-1.5 text-xs font-medium border border-gray-300 rounded-md hover:bg-gray-50 text-gray-700 flex items-center gap-1"
          >
            <FolderOpen className="h-3.5 w-3.5" />
            Browse
          </button>
          <button
            onClick={() => { setPrevResultsOpen(!prevResultsOpen); setBrowserOpen(false); }}
            type="button"
            className={`px-3 py-1.5 text-xs font-medium border rounded-md flex items-center gap-1 transition ${
              prevResultsOpen
                ? 'border-[#003d7a] bg-[#003d7a]/5 text-[#003d7a]'
                : 'border-gray-300 hover:bg-gray-50 text-gray-700'
            }`}
            title="Use outputs from a completed job"
          >
            <History className="h-3.5 w-3.5" />
            Previous
          </button>
          <button
            type="submit"
            disabled={!manualPath.trim()}
            className="px-3 py-1.5 text-xs font-medium bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Use Path
          </button>
        </form>
      </div>

      {/* Previous Results Panel */}
      {prevResultsOpen && (
        <div className="border border-[#003d7a]/30 rounded-lg overflow-hidden bg-white shadow-sm">
          <div className="flex items-center gap-2 px-3 py-2 bg-[#003d7a]/5 border-b border-[#003d7a]/10">
            <History className="h-3.5 w-3.5 text-[#003d7a]" />
            <span className="text-xs font-semibold text-[#003d7a]">
              Previous Job Results
            </span>
            <span className="text-[10px] text-gray-400 ml-auto">
              {executionContext
                ? 'Showing compatible outputs for selected pipeline'
                : 'Select a pipeline first for filtered results'}
            </span>
          </div>

          <div className="max-h-52 overflow-y-auto">
            {prevLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-4 w-4 text-[#003d7a] animate-spin mr-2" />
                <span className="text-xs text-gray-500">Loading completed jobs...</span>
              </div>
            )}

            {prevError && (
              <div className="flex items-center gap-2 mx-3 my-2 text-xs text-red-600 bg-red-50 px-3 py-2 rounded">
                <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                {prevError}
              </div>
            )}

            {!prevLoading && prevResults.length === 0 && !prevError && (
              <p className="text-xs text-gray-400 py-6 text-center">
                {executionContext
                  ? 'No compatible completed jobs found'
                  : 'No completed jobs with reusable outputs'}
              </p>
            )}

            {!prevLoading && prevResults.map((result) => (
              <div
                key={`${result.job_id}-${result.plugin_id}`}
                className="flex items-center px-3 py-2 text-xs hover:bg-[#003d7a]/5 cursor-pointer border-b border-gray-50 group transition"
                onClick={() => selectPreviousResult(result)}
              >
                <CheckCircle2 className="h-3.5 w-3.5 text-green-500 mr-2 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium text-gray-800 truncate">
                      {friendlyPipeline(result.job_pipeline)}
                    </span>
                    {result.subject_id && (
                      <span className="text-[9px] bg-[#003d7a]/10 text-[#003d7a] px-1.5 py-0.5 rounded font-medium flex-shrink-0">
                        {result.subject_id}
                      </span>
                    )}
                    <span className="text-[9px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded flex-shrink-0">
                      {result.provides.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-400 truncate mt-0.5 font-mono">
                    {result.output_path}
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 ml-2">
                  <span className="text-[10px] text-gray-400">{formatDate(result.completed_at)}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); selectPreviousResult(result); }}
                    className="text-[10px] text-white bg-[#003d7a] px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition"
                  >
                    Use
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between px-3 py-1.5 border-t border-gray-200 bg-gray-50">
            <span className="text-[10px] text-gray-500">
              {prevResults.length} result{prevResults.length !== 1 ? 's' : ''}
            </span>
            <button
              onClick={() => setPrevResultsOpen(false)}
              className="text-[10px] text-gray-500 hover:text-gray-700"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Collapsible File Browser */}
      {browserOpen && (
        <div className="border border-[#003d7a]/30 rounded-lg overflow-hidden bg-white shadow-sm">
          {/* Header */}
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200">
            <FolderOpen className="h-3.5 w-3.5 text-[#003d7a]" />
            <span className="text-xs font-semibold text-gray-700">{modeLabel} File Browser</span>
            <span className="text-[10px] text-gray-400 ml-auto">Click a file to select it, or use a folder</span>
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-gray-100">
            <button
              onClick={() => browserParent && loadDir(browserParent)}
              disabled={!browserParent}
              className="p-1 rounded hover:bg-gray-100 text-gray-500 disabled:opacity-30"
              title="Go up"
            >
              <ArrowUp className="h-3.5 w-3.5" />
            </button>
            <div className="flex-1 px-2 py-1 text-xs text-gray-600 bg-gray-50 rounded font-mono truncate">
              {browserPath}
            </div>
            <button
              onClick={() => selectFolder(browserPath)}
              className="px-2.5 py-1 text-[10px] font-semibold text-white bg-navy-600 rounded hover:bg-navy-700 whitespace-nowrap"
              title="Use the current directory as input"
            >
              Use This Folder
            </button>
          </div>

          {/* Entries */}
          <div className="max-h-52 overflow-y-auto">
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
                    isSelected ? 'bg-navy-50 border-navy-100' : 'hover:bg-gray-50'
                  }`}
                  onClick={() => isFile ? selectFile(entry) : loadDir(entry.path)}
                >
                  {isFile ? (
                    nifti ? <FileText className="h-3.5 w-3.5 text-green-600 mr-2 flex-shrink-0" />
                      : <File className="h-3.5 w-3.5 text-gray-400 mr-2 flex-shrink-0" />
                  ) : (
                    <FolderOpen className="h-3.5 w-3.5 text-navy-500 mr-2 flex-shrink-0" />
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
                  {!isFile && (
                    <>
                      <button
                        onClick={(e) => { e.stopPropagation(); selectFolder(entry.path); }}
                        className="text-[10px] text-white bg-[#003d7a] px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition mr-2"
                      >
                        Select
                      </button>
                      <ChevronRight className="h-3 w-3 text-gray-300" />
                    </>
                  )}
                </div>
              );
            })}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-3 py-1.5 border-t border-gray-200 bg-gray-50">
            <span className="text-[10px] text-gray-500">
              {dirsInBrowser} folder{dirsInBrowser !== 1 ? 's' : ''}, {niftiInBrowser} NIfTI file{niftiInBrowser !== 1 ? 's' : ''}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => selectFolder(browserPath)}
                className="text-[10px] font-medium text-[#003d7a] hover:underline"
              >
                Use current folder
              </button>
              <button
                onClick={() => setBrowserOpen(false)}
                className="text-[10px] text-gray-500 hover:text-gray-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Selected path confirmation */}
      {selectedPath && (
        <div className="flex items-center gap-2 p-2.5 bg-green-50 border border-green-200 rounded-md">
          <CheckCircle2 className="h-4 w-4 text-green-600 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-green-800 truncate">{selectedPath}</p>
            {selectedPrevResult && (
              <p className="text-[10px] text-green-600 mt-0.5">
                From: {friendlyPipeline(selectedPrevResult.job_pipeline)}
                {selectedPrevResult.subject_id ? ` (${selectedPrevResult.subject_id})` : ''}
                {' '}&middot; {selectedPrevResult.provides.replace(/_/g, ' ')}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
