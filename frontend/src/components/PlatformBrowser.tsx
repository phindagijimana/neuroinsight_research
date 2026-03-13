/**
 * PlatformBrowser Component
 *
 * Hierarchical tree browser for external data platforms (Pennsieve, XNAT).
 * Shows datasets/projects at the top level, drills into packages/subjects/experiments/files.
 *
 * Features:
 *   - Breadcrumb navigation
 *   - NIfTI/DICOM file type highlighting
 *   - Multi-select checkboxes
 *   - File size display
 *   - "Select for Processing" action
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  FolderOpen, File, ChevronRight, ArrowLeft, CheckSquare, Square,
  Loader2, AlertCircle, Database, FileText, HardDrive,
} from 'lucide-react';
import { apiService } from '../services/api';
import type { DataSourceType, PlatformFile, PlatformDataset } from '../types';

interface PlatformBrowserProps {
  platform: DataSourceType;
  onFilesSelected: (files: PlatformFile[], datasetId: string) => void;
  onCancel?: () => void;
}

interface BreadcrumbItem {
  label: string;
  datasetId: string;
  path: string;
}

const isNifti = (name: string) => /\.(nii|nii\.gz)$/i.test(name);
const isDicom = (name: string) => /\.(dcm|dicom|ima)$/i.test(name);

function formatSize(bytes: number): string {
  if (bytes === 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export const PlatformBrowser: React.FC<PlatformBrowserProps> = ({
  platform,
  onFilesSelected,
  onCancel,
}) => {
  const [datasets, setDatasets] = useState<PlatformDataset[]>([]);
  const [items, setItems] = useState<PlatformFile[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [, setCurrentPath] = useState('/');
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<'datasets' | 'files'>('datasets');

  // Load datasets on mount
  useEffect(() => {
    loadDatasets();
  }, [platform]);

  const loadDatasets = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiService.platformListProjects(platform);
      setDatasets(resp.projects || []);
      setView('datasets');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load datasets');
    } finally {
      setLoading(false);
    }
  };

  const browseDataset = useCallback(async (datasetId: string, path: string = '/') => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiService.platformBrowse(platform, datasetId, path);
      setItems(resp.items || []);
      setSelectedDatasetId(datasetId);
      setCurrentPath(path);
      setView('files');

      if (path === '/') {
        const ds = datasets.find(d => d.id === datasetId);
        setBreadcrumbs([{ label: ds?.name || datasetId, datasetId, path: '/' }]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to browse');
    } finally {
      setLoading(false);
    }
  }, [platform, datasets]);

  const navigateTo = (item: PlatformFile) => {
    if (item.type === 'directory' && selectedDatasetId) {
      const newPath = item.path || `/${item.id}`;
      setBreadcrumbs(prev => [...prev, { label: item.name, datasetId: selectedDatasetId, path: newPath }]);
      browseDataset(selectedDatasetId, newPath);
    }
  };

  const navigateBreadcrumb = (index: number) => {
    if (index < 0) {
      setView('datasets');
      setBreadcrumbs([]);
      setSelectedDatasetId(null);
      setItems([]);
      return;
    }
    const crumb = breadcrumbs[index];
    setBreadcrumbs(prev => prev.slice(0, index + 1));
    browseDataset(crumb.datasetId, crumb.path);
  };

  const toggleFileSelection = (fileId: string) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId);
      else next.add(fileId);
      return next;
    });
  };

  const selectAllFiles = () => {
    const allIds = items.map(i => i.id);
    if (selectedFiles.size === allIds.length && allIds.length > 0) {
      setSelectedFiles(new Set());
    } else {
      setSelectedFiles(new Set(allIds));
    }
  };

  const handleSubmit = () => {
    const selected = items.filter(i => selectedFiles.has(i.id));
    if (selected.length > 0 && selectedDatasetId) {
      onFilesSelected(selected, selectedDatasetId);
    }
  };

  const selectableCount = items.length;
  const niftiCount = items.filter(i => i.type === 'file' && isNifti(i.name)).length;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-[#003d7a]" />
          <h3 className="text-sm font-semibold text-gray-700">
            {platform === 'pennsieve' ? 'Pennsieve' : 'XNAT'} Data Browser
          </h3>
        </div>
        {onCancel && (
          <button onClick={onCancel} className="text-xs text-gray-500 hover:text-gray-700">
            Cancel
          </button>
        )}
      </div>

      {/* Breadcrumbs */}
      {view === 'files' && (
        <div className="flex items-center gap-1 text-xs text-gray-500 mb-3 flex-wrap">
          <button
            onClick={() => navigateBreadcrumb(-1)}
            className="hover:text-[#003d7a] font-medium flex items-center gap-1"
          >
            <ArrowLeft className="h-3 w-3" />
            All Datasets
          </button>
          {breadcrumbs.map((crumb, idx) => (
            <React.Fragment key={idx}>
              <ChevronRight className="h-3 w-3 text-gray-400" />
              <button
                onClick={() => navigateBreadcrumb(idx)}
                className={`hover:text-[#003d7a] ${idx === breadcrumbs.length - 1 ? 'font-semibold text-gray-700' : ''}`}
              >
                {crumb.label}
              </button>
            </React.Fragment>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 px-3 py-2 rounded mb-3">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 text-[#003d7a] animate-spin mr-2" />
          <span className="text-sm text-gray-500">Loading...</span>
        </div>
      )}

      {/* Dataset List */}
      {!loading && view === 'datasets' && (
        <div className="space-y-1 max-h-72 overflow-y-auto">
          {datasets.length === 0 && (
            <p className="text-sm text-gray-500 py-4 text-center">No datasets found</p>
          )}
          {datasets.map((ds) => (
            <button
              key={ds.id}
              onClick={() => browseDataset(ds.id)}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-md hover:bg-gray-50 text-left transition group"
            >
              <HardDrive className="h-4 w-4 text-[#003d7a] flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate group-hover:text-[#003d7a]">
                  {ds.name}
                </p>
                {ds.description && (
                  <p className="text-xs text-gray-500 truncate">{ds.description}</p>
                )}
              </div>
              {ds.size_bytes ? (
                <span className="text-xs text-gray-400">{formatSize(ds.size_bytes)}</span>
              ) : null}
              <ChevronRight className="h-4 w-4 text-gray-400 group-hover:text-[#003d7a]" />
            </button>
          ))}
        </div>
      )}

      {/* File List */}
      {!loading && view === 'files' && (
        <>
          {/* Select all / count bar */}
          <div className="flex items-center justify-between mb-2 px-1">
            <button
              onClick={selectAllFiles}
              className="text-xs text-[#003d7a] hover:underline flex items-center gap-1"
            >
              {selectedFiles.size === selectableCount && selectableCount > 0 ? (
                <CheckSquare className="h-3.5 w-3.5" />
              ) : (
                <Square className="h-3.5 w-3.5" />
              )}
              {selectedFiles.size === selectableCount && selectableCount > 0 ? 'Deselect all' : 'Select all'}
            </button>
            <span className="text-xs text-gray-500">
              {items.length} items{niftiCount > 0 && <> ({niftiCount} NIfTI)</>}
            </span>
          </div>

          <div className="space-y-0.5 max-h-72 overflow-y-auto border border-gray-100 rounded-md p-1">
            {items.length === 0 && (
              <p className="text-sm text-gray-500 py-4 text-center">No items found</p>
            )}
            {items.map((item) => {
              const isFile = item.type === 'file';
              const isDir = item.type === 'directory';
              const isSelected = selectedFiles.has(item.id);
              const nifti = isFile && isNifti(item.name);
              const dicom = isFile && isDicom(item.name);

              return (
                <div
                  key={item.id}
                  className={`flex items-center gap-2 px-2 py-1.5 rounded text-sm transition ${
                    isSelected ? 'bg-navy-50 border border-navy-200' : 'hover:bg-gray-50'
                  }`}
                >
                  {/* Checkbox for both files and directories */}
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleFileSelection(item.id); }}
                    className="flex-shrink-0"
                  >
                    {isSelected ? (
                      <CheckSquare className="h-4 w-4 text-[#003d7a]" />
                    ) : (
                      <Square className="h-4 w-4 text-gray-400" />
                    )}
                  </button>

                  {/* Icon */}
                  {isDir ? (
                    <FolderOpen className="h-4 w-4 text-yellow-500 flex-shrink-0" />
                  ) : nifti ? (
                    <FileText className="h-4 w-4 text-green-600 flex-shrink-0" />
                  ) : dicom ? (
                    <FileText className="h-4 w-4 text-blue-600 flex-shrink-0" />
                  ) : (
                    <File className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  )}

                  {/* Name: clickable for dirs (navigate), clickable for files (toggle) */}
                  <span
                    className={`flex-1 truncate cursor-pointer ${
                      nifti ? 'text-green-700 font-medium' :
                      isDir ? 'text-gray-700 hover:text-[#003d7a]' :
                      'text-gray-700'
                    }`}
                    onClick={() => isDir ? navigateTo(item) : toggleFileSelection(item.id)}
                  >
                    {item.name}
                  </span>

                  {nifti && <span className="text-[10px] bg-green-100 text-green-700 px-1.5 py-0.5 rounded font-medium">NIfTI</span>}
                  {dicom && <span className="text-[10px] bg-navy-100 text-navy-700 px-1.5 py-0.5 rounded font-medium">DICOM</span>}

                  {item.size > 0 && (
                    <span className="text-xs text-gray-400 ml-auto">{formatSize(item.size)}</span>
                  )}

                  {isDir && (
                    <button
                      onClick={() => navigateTo(item)}
                      className="flex-shrink-0 text-gray-400 hover:text-[#003d7a]"
                      title="Open"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>

          {/* Action button */}
          {selectedFiles.size > 0 && (
            <button
              onClick={handleSubmit}
              className="mt-3 w-full px-4 py-2.5 bg-[#003d7a] text-white text-sm font-medium rounded-md hover:bg-[#002b55] transition flex items-center justify-center gap-2"
            >
              <CheckSquare className="h-4 w-4" />
              Select {selectedFiles.size} Item{selectedFiles.size !== 1 ? 's' : ''} for Processing
            </button>
          )}
        </>
      )}
    </div>
  );
};

export default PlatformBrowser;
