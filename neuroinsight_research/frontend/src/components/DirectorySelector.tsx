/**
 * DirectorySelector Component
 *
 * Visual directory browser + input fields for batch processing.
 * Users can either type a path or click through a folder tree.
 *
 * Works in local, remote, and HPC modes.
 */

import React, { useState, useEffect } from 'react';
import {
  FolderOpen, File, AlertCircle, CheckCircle2,
  ChevronRight, ArrowUp, Loader2, FileText,
} from 'lucide-react';
import { apiService } from '../services/api';
import type { DirectoryInfo } from '../types';

interface DirectorySelectorProps {
  mode: 'local' | 'remote' | 'hpc';
  onSubmit: (inputDir: string, outputDir: string, files: string[]) => void;
  onSubmitDirectory?: (inputDir: string, outputDir: string) => void;
  onCancel?: () => void;
}

interface BrowseEntry {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
}

const isNifti = (name: string) => /\.(nii|nii\.gz)$/i.test(name);

export const DirectorySelector: React.FC<DirectorySelectorProps> = ({
  mode,
  onSubmit,
  onSubmitDirectory,
  onCancel,
}) => {
  const [inputDir, setInputDir] = useState('');
  const [outputDir, setOutputDir] = useState('');
  const [directoryInfo, setDirectoryInfo] = useState<DirectoryInfo | null>(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [browserOpen, setBrowserOpen] = useState(false);
  const [browserPath, setBrowserPath] = useState(mode === 'local' ? './data' : '~');
  const [browserParent, setBrowserParent] = useState<string | null>(null);
  const [browserEntries, setBrowserEntries] = useState<BrowseEntry[]>([]);
  const [browserLoading, setBrowserLoading] = useState(false);
  const [browserError, setBrowserError] = useState<string | null>(null);

  const loadBrowserDir = async (path: string) => {
    setBrowserLoading(true);
    setBrowserError(null);
    try {
      const data = await apiService.browseDirectory(path, mode);
      const dirs: BrowseEntry[] = (data.directories || []).map((d: any) => ({
        name: d.name, path: d.path, type: 'directory' as const,
      }));
      const files: BrowseEntry[] = (data.files || []).map((f: any) => ({
        name: f.name, path: f.path, type: 'file' as const, size: f.size,
      }));
      setBrowserEntries([...dirs, ...files]);
      setBrowserPath(data.path || path);
      setBrowserParent(data.parent || null);
    } catch (err: any) {
      setBrowserError(err.response?.data?.detail || 'Failed to browse');
      setBrowserEntries([]);
    } finally {
      setBrowserLoading(false);
    }
  };

  useEffect(() => {
    if (browserOpen) {
      loadBrowserDir(browserPath);
    }
  }, [browserOpen]);

  const handleBrowserSelect = (dirPath: string) => {
    setInputDir(dirPath);
    setOutputDir(dirPath.replace(/\/?$/, '') + '_output');
    setBrowserOpen(false);
    scanDirectory(dirPath);
  };

  const scanDirectory = async (path: string) => {
    if (!path.trim()) {
      setError('Please enter a directory path');
      return;
    }
    setScanning(true);
    setError(null);

    try {
      const info = await apiService.browseDirectory(path, mode);
      setDirectoryInfo(info);
      if (info.nifti_files.length === 0) {
        setError('No NIfTI files at this level. For BIDS pipelines, use "Submit Directory as Input" below.');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to browse directory');
      setDirectoryInfo(null);
    } finally {
      setScanning(false);
    }
  };

  const handleBrowseInput = () => scanDirectory(inputDir);

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

  const niftiInBrowser = browserEntries.filter(e => e.type === 'file' && isNifti(e.name)).length;
  const dirsInBrowser = browserEntries.filter(e => e.type === 'directory').length;

  return (
    <div className="space-y-4">
      {/* Input Directory */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-gray-700">
          Input Directory <span className="text-red-500">*</span>
        </label>
        <p className="text-[11px] text-gray-500">
          Directory containing NIfTI files (.nii / .nii.gz)
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            value={inputDir}
            onChange={(e) => { setInputDir(e.target.value); setDirectoryInfo(null); }}
            placeholder={mode === 'local' ? './data/uploads' : '/scratch/username/scans'}
            className="flex-1 px-2.5 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#003d7a] focus:border-[#003d7a]"
            onKeyDown={(e) => e.key === 'Enter' && handleBrowseInput()}
          />
          <button
            onClick={() => setBrowserOpen(!browserOpen)}
            className="px-3 py-1.5 text-xs font-medium border border-gray-300 rounded-md hover:bg-gray-50 text-gray-700 flex items-center gap-1"
            title="Open visual browser"
          >
            <FolderOpen className="h-3.5 w-3.5" />
            Browse
          </button>
          <button
            onClick={handleBrowseInput}
            disabled={scanning || !inputDir.trim()}
            className="px-3 py-1.5 text-xs font-medium bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {scanning ? 'Scanning...' : 'Scan'}
          </button>
        </div>
      </div>

      {/* Visual Directory Browser */}
      {browserOpen && (
        <div className="border border-[#003d7a]/30 rounded-lg overflow-hidden bg-white shadow-sm">
          {/* Browser header */}
          <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200">
            <FolderOpen className="h-3.5 w-3.5 text-[#003d7a]" />
            <span className="text-xs font-semibold text-gray-700">
              {mode === 'local' ? 'Server' : mode === 'remote' ? 'Remote' : 'HPC'} File Browser
            </span>
            <span className="text-[10px] text-gray-400 ml-auto">Click a folder to select it as input</span>
          </div>

          {/* Toolbar */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-gray-100">
            <button
              onClick={() => browserParent && loadBrowserDir(browserParent)}
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
              onClick={() => handleBrowserSelect(browserPath)}
              className="px-2.5 py-1 text-[10px] font-semibold text-white bg-teal-600 rounded hover:bg-teal-700 whitespace-nowrap"
              title="Use the current directory as input"
            >
              Use This Directory
            </button>
          </div>

          {/* Entries */}
          <div className="max-h-52 overflow-y-auto">
            {browserLoading && (
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

            {!browserLoading && browserEntries.length === 0 && !browserError && (
              <p className="text-xs text-gray-400 py-6 text-center">Empty directory</p>
            )}

            {!browserLoading && browserEntries.map((entry) => {
              const nifti = entry.type === 'file' && isNifti(entry.name);
              return (
                <div
                  key={entry.path}
                  className="flex items-center px-3 py-1.5 text-xs hover:bg-gray-50 cursor-pointer border-b border-gray-50 group"
                  onClick={() => {
                    if (entry.type === 'directory') loadBrowserDir(entry.path);
                  }}
                >
                  {entry.type === 'directory' ? (
                    <FolderOpen className="h-3.5 w-3.5 text-yellow-500 mr-2 flex-shrink-0" />
                  ) : nifti ? (
                    <FileText className="h-3.5 w-3.5 text-green-600 mr-2 flex-shrink-0" />
                  ) : (
                    <File className="h-3.5 w-3.5 text-gray-400 mr-2 flex-shrink-0" />
                  )}
                  <span className={`flex-1 truncate ${
                    entry.type === 'directory' ? 'font-medium text-gray-800' :
                    nifti ? 'text-green-700' : 'text-gray-600'
                  }`}>
                    {entry.name}
                  </span>
                  {nifti && (
                    <span className="text-[9px] bg-green-100 text-green-700 px-1 py-0.5 rounded font-medium mr-2">NIfTI</span>
                  )}
                  {entry.type === 'directory' && (
                    <>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleBrowserSelect(entry.path); }}
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
                onClick={() => handleBrowserSelect(browserPath)}
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

      {/* Output Directory */}
      <div className="space-y-1.5">
        <label className="block text-xs font-semibold text-gray-700">
          Output Directory <span className="text-red-500">*</span>
        </label>
        <p className="text-[11px] text-gray-500">
          Where results will be saved (created if it doesn't exist)
        </p>
        <input
          type="text"
          value={outputDir}
          onChange={(e) => setOutputDir(e.target.value)}
          placeholder={mode === 'local' ? './data/outputs' : '/scratch/username/results'}
          className="w-full px-2.5 py-1.5 text-xs border border-gray-300 rounded-md focus:outline-none focus:ring-1 focus:ring-[#003d7a] focus:border-[#003d7a]"
        />
      </div>

      {/* Error */}
      {error && (
        <div className="p-2.5 bg-red-50 border border-red-200 rounded-md flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-red-700">{error}</p>
        </div>
      )}

      {/* Files Found */}
      {directoryInfo && directoryInfo.nifti_files.length > 0 && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-md">
          <div className="flex items-center mb-2">
            <CheckCircle2 className="h-4 w-4 text-green-600 mr-2" />
            <span className="text-xs font-semibold text-green-800">
              Found {directoryInfo.nifti_files.length} NIfTI file{directoryInfo.nifti_files.length !== 1 ? 's' : ''}
            </span>
          </div>
          <div className="max-h-32 overflow-y-auto space-y-0.5 bg-white rounded p-2">
            {directoryInfo.nifti_files.slice(0, 10).map((file, idx) => (
              <div key={idx} className="text-[11px] text-gray-700 flex items-center py-0.5">
                <FileText className="h-3 w-3 mr-1.5 text-green-500 flex-shrink-0" />
                <span className="truncate">{file}</span>
              </div>
            ))}
            {directoryInfo.nifti_files.length > 10 && (
              <p className="text-[11px] text-gray-500 italic pt-1 border-t">
                ... and {directoryInfo.nifti_files.length - 10} more
              </p>
            )}
          </div>
          <div className="mt-2 text-[10px] text-gray-600 space-y-0.5">
            <p><strong>Input:</strong> {inputDir}</p>
            <p><strong>Output:</strong> {outputDir || '(not set)'}</p>
          </div>
        </div>
      )}

      {/* Submit buttons */}
      <div className="space-y-2">
        <button
          onClick={handleSubmit}
          disabled={!inputDir || !outputDir || !directoryInfo || directoryInfo.nifti_files.length === 0}
          className="w-full py-2 px-4 bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm flex items-center justify-center gap-2"
        >
          <CheckCircle2 className="h-4 w-4" />
          Process {directoryInfo?.nifti_files.length || 0} File{directoryInfo?.nifti_files.length !== 1 ? 's' : ''} (one job per file)
        </button>

        {onSubmitDirectory && (
          <button
            onClick={() => { if (inputDir && outputDir) onSubmitDirectory(inputDir, outputDir); }}
            disabled={!inputDir || !outputDir}
            className="w-full py-2 px-4 bg-teal-600 text-white rounded-md hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm flex items-center justify-center gap-2"
          >
            <FolderOpen className="h-4 w-4" />
            Submit Directory as Input (BIDS / multi-file pipelines)
          </button>
        )}
      </div>

      {/* Help */}
      <div className="p-2.5 bg-gray-50 border border-gray-200 rounded-md">
        <p className="text-[11px] text-gray-600">
          <strong>Tip:</strong> Click <strong>Browse</strong> to visually navigate the server's filesystem,
          or type a path directly and click <strong>Scan</strong> to find NIfTI files.
        </p>
      </div>
    </div>
  );
};
