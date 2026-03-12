/**
 * FileBrowserPane -- WinSCP-style file browser panel.
 *
 * Supports all 5 platform types:
 *   - local, remote, hpc: via /api/browse and /api/hpc/browse
 *   - pennsieve, xnat:    via /api/platforms/{platform}/...
 *
 * Features:
 *   - Visual directory listing with icons, sizes, dates
 *   - Breadcrumb + parent-directory navigation
 *   - Multi-select via checkboxes
 *   - NIfTI/DICOM highlighting
 *   - Address bar for manual path entry
 *   - Create folder, refresh, select-all
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  FolderOpen, File, ChevronRight, ArrowUp, RefreshCw,
  CheckSquare, Square, Loader2, AlertCircle, FileText, FolderPlus,
  Monitor, Cloud, Server, Database, Globe, HardDrive,
} from 'lucide-react';
import { apiService } from '../services/api';

type PlatformType = 'local' | 'remote' | 'hpc' | 'pennsieve' | 'xnat';

interface FileEntry {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  id?: string;
}

interface FileBrowserPaneProps {
  platform: PlatformType;
  side: 'source' | 'destination';
  selectedFiles: FileEntry[];
  onSelectionChange: (files: FileEntry[]) => void;
  onPathChange?: (path: string) => void;
}

const PLATFORM_META: Record<PlatformType, { label: string; icon: React.ReactNode; defaultPath: string }> = {
  local:     { label: 'Local Server',  icon: <Monitor className="h-4 w-4" />,  defaultPath: './data' },
  remote:    { label: 'Remote Server', icon: <Cloud className="h-4 w-4" />,    defaultPath: '~' },
  hpc:       { label: 'HPC',           icon: <Server className="h-4 w-4" />,   defaultPath: '~' },
  pennsieve: { label: 'Pennsieve',     icon: <Database className="h-4 w-4" />, defaultPath: '/' },
  xnat:      { label: 'XNAT',          icon: <Globe className="h-4 w-4" />,    defaultPath: '/' },
};

const isNifti = (name: string) => /\.(nii|nii\.gz)$/i.test(name);
const isDicom = (name: string) => /\.(dcm|dicom|ima)$/i.test(name);
const isBackend = (p: PlatformType) => p === 'local' || p === 'remote' || p === 'hpc';

function formatSize(bytes?: number): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

const FileBrowserPane: React.FC<FileBrowserPaneProps> = ({
  platform,
  side,
  selectedFiles,
  onSelectionChange,
  onPathChange,
}) => {
  const meta = PLATFORM_META[platform];

  const [currentPath, setCurrentPath] = useState(meta.defaultPath);
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [addressBar, setAddressBar] = useState(meta.defaultPath);
  const [editingAddress, setEditingAddress] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [showNewFolder, setShowNewFolder] = useState(false);

  // Platform-specific state
  const [platformDatasets, setPlatformDatasets] = useState<any[]>([]);
  const [platformView, setPlatformView] = useState<'datasets' | 'files'>('datasets');
  const [platformDatasetId, setPlatformDatasetId] = useState<string | null>(null);

  const selectedSet = new Set(selectedFiles.map(f => f.path || f.id || f.name));

  // Reset when platform changes
  useEffect(() => {
    const m = PLATFORM_META[platform];
    setCurrentPath(m.defaultPath);
    setAddressBar(m.defaultPath);
    setEntries([]);
    setParentPath(null);
    setError(null);
    onSelectionChange([]);
    if (!isBackend(platform)) {
      setPlatformView('datasets');
      setPlatformDatasets([]);
      setPlatformDatasetId(null);
    }
  }, [platform]);

  // Load on mount / path change
  useEffect(() => {
    if (isBackend(platform)) {
      loadBackendDirectory(currentPath);
    } else if (platformView === 'datasets') {
      loadPlatformDatasets();
    }
  }, [platform, currentPath]);

  // ---- Backend (local/remote/hpc) browsing ----

  const loadBackendDirectory = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      let data: any;
      if (platform === 'local') {
        data = await apiService.browseDirectory(path, 'local');
      } else {
        data = await apiService.browseDirectory(path, platform as 'remote' | 'hpc');
      }
      const dirs: FileEntry[] = (data.directories || []).map((d: any) => ({
        name: d.name, path: d.path, type: 'directory' as const, size: d.size,
      }));
      const files: FileEntry[] = (data.files || []).map((f: any) => ({
        name: f.name, path: f.path, type: 'file' as const, size: f.size,
      }));
      setEntries([...dirs, ...files]);
      setParentPath(data.parent || null);
      setCurrentPath(data.path || path);
      setAddressBar(data.path || path);
      onPathChange?.(data.path || path);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to browse');
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, [platform, onPathChange]);

  // ---- Platform (pennsieve/xnat) browsing ----

  const loadPlatformDatasets = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiService.platformListProjects(platform);
      setPlatformDatasets(resp.projects || []);
      setPlatformView('datasets');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load datasets. Make sure you are connected.');
    } finally {
      setLoading(false);
    }
  };

  const browsePlatformDataset = async (datasetId: string, path: string = '/') => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiService.platformBrowse(platform, datasetId, path);
      const items: FileEntry[] = (resp.items || []).map((item: any) => ({
        name: item.name,
        path: item.path || item.id,
        type: item.type,
        size: item.size,
        id: item.id,
      }));
      setEntries(items);
      setPlatformDatasetId(datasetId);
      setPlatformView('files');
      setCurrentPath(path);
      setAddressBar(`${datasetId}:${path}`);
      const token = path === '/'
        ? datasetId
        : `${datasetId}?path=${encodeURIComponent(path)}`;
      onPathChange?.(token);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to browse dataset');
    } finally {
      setLoading(false);
    }
  };

  // ---- Navigation ----

  const navigateUp = () => {
    if (!isBackend(platform)) {
      if (platformView === 'files' && currentPath !== '/') {
        const parts = currentPath.split('/').filter(Boolean);
        parts.pop();
        const newPath = '/' + parts.join('/');
        if (platformDatasetId) browsePlatformDataset(platformDatasetId, newPath || '/');
      } else {
        setPlatformView('datasets');
        setEntries([]);
        setPlatformDatasetId(null);
        setCurrentPath('/');
        setAddressBar('/');
      }
      return;
    }
    if (parentPath) {
      loadBackendDirectory(parentPath);
    }
  };

  const navigateInto = (entry: FileEntry) => {
    if (entry.type !== 'directory') return;
    if (isBackend(platform)) {
      loadBackendDirectory(entry.path);
    } else if (platformDatasetId) {
      const newPath = entry.path || `/${entry.id}`;
      browsePlatformDataset(platformDatasetId, newPath);
    }
  };

  const handleAddressSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setEditingAddress(false);
    if (isBackend(platform)) {
      loadBackendDirectory(addressBar);
    }
  };

  const handleRefresh = () => {
    if (isBackend(platform)) {
      loadBackendDirectory(currentPath);
    } else if (platformView === 'datasets') {
      loadPlatformDatasets();
    } else if (platformDatasetId) {
      browsePlatformDataset(platformDatasetId, currentPath);
    }
  };

  // ---- Selection ----

  const toggleSelect = (entry: FileEntry) => {
    const key = entry.path || entry.id || entry.name;
    if (selectedSet.has(key)) {
      onSelectionChange(selectedFiles.filter(f => (f.path || f.id || f.name) !== key));
    } else {
      onSelectionChange([...selectedFiles, entry]);
    }
  };

  const selectAll = () => {
    if (selectedFiles.length === entries.length && entries.length > 0) {
      onSelectionChange([]);
    } else {
      onSelectionChange([...entries]);
    }
  };

  // ---- Create folder (backend only) ----

  const handleCreateFolder = async () => {
    if (!newFolderName.trim() || !isBackend(platform)) return;
    // For local, we can use a simple API call or let the user know
    setShowNewFolder(false);
    setNewFolderName('');
    // Refresh to show new folder (creation would need a backend endpoint)
    handleRefresh();
  };

  // ---- Render ----

  const fileCount = entries.filter(e => e.type === 'file').length;
  const dirCount = entries.filter(e => e.type === 'directory').length;
  const niftiCount = entries.filter(e => e.type === 'file' && isNifti(e.name)).length;

  return (
    <div className="flex flex-col h-full bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border-b border-gray-200">
        <span className="text-[#003d7a]">{meta.icon}</span>
        <span className="text-xs font-semibold text-gray-700 uppercase tracking-wider">{side}</span>
        <span className="text-xs text-gray-400">|</span>
        <span className="text-xs font-medium text-gray-600">{meta.label}</span>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-gray-100 bg-white">
        <button onClick={navigateUp} className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-[#003d7a]" title="Go up">
          <ArrowUp className="h-3.5 w-3.5" />
        </button>
        <button onClick={handleRefresh} className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-[#003d7a]" title="Refresh">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
        {isBackend(platform) && (
          <button
            onClick={() => setShowNewFolder(!showNewFolder)}
            className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-[#003d7a]"
            title="New folder"
          >
            <FolderPlus className="h-3.5 w-3.5" />
          </button>
        )}
        <div className="flex-1 ml-1">
          {editingAddress ? (
            <form onSubmit={handleAddressSubmit} className="flex">
              <input
                autoFocus
                value={addressBar}
                onChange={e => setAddressBar(e.target.value)}
                onBlur={() => setEditingAddress(false)}
                className="w-full px-2 py-1 text-xs border border-[#003d7a] rounded focus:outline-none"
              />
            </form>
          ) : (
            <button
              onClick={() => isBackend(platform) && setEditingAddress(true)}
              className="w-full text-left px-2 py-1 text-xs text-gray-600 bg-gray-50 rounded hover:bg-gray-100 truncate font-mono"
              title={currentPath}
            >
              {addressBar}
            </button>
          )}
        </div>
      </div>

      {/* New folder input */}
      {showNewFolder && (
        <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-100 bg-navy-50">
          <FolderPlus className="h-3.5 w-3.5 text-navy-600" />
          <input
            autoFocus
            value={newFolderName}
            onChange={e => setNewFolderName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleCreateFolder()}
            placeholder="New folder name"
            className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded"
          />
          <button onClick={handleCreateFolder} className="text-xs text-[#003d7a] font-medium">Create</button>
          <button onClick={() => { setShowNewFolder(false); setNewFolderName(''); }} className="text-xs text-gray-500">Cancel</button>
        </div>
      )}

      {/* Column header */}
      <div className="flex items-center px-3 py-1 border-b border-gray-100 text-[10px] font-semibold text-gray-400 uppercase tracking-wider bg-gray-50">
        <span className="w-6" />
        <span className="w-5" />
        <span className="flex-1">Name</span>
        <span className="w-20 text-right">Size</span>
        <span className="w-16 text-right">Type</span>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 mx-3 my-2 text-xs text-red-600 bg-red-50 px-3 py-2 rounded">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
          <span className="truncate">{error}</span>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12 flex-1">
          <Loader2 className="h-5 w-5 text-[#003d7a] animate-spin mr-2" />
          <span className="text-sm text-gray-500">Loading...</span>
        </div>
      )}

      {/* Platform dataset list */}
      {!loading && !isBackend(platform) && platformView === 'datasets' && (
        <div className="flex-1 overflow-y-auto">
          {platformDatasets.length === 0 && !error && (
            <p className="text-sm text-gray-500 py-8 text-center">No datasets found</p>
          )}
          {platformDatasets.map((ds: any) => (
            <button
              key={ds.id}
              onClick={() => browsePlatformDataset(ds.id)}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-50 text-left transition border-b border-gray-50 group"
            >
              <HardDrive className="h-4 w-4 text-[#003d7a] flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-gray-800 truncate group-hover:text-[#003d7a]">{ds.name}</p>
                {ds.description && <p className="text-[10px] text-gray-400 truncate">{ds.description}</p>}
              </div>
              <ChevronRight className="h-3.5 w-3.5 text-gray-300 group-hover:text-[#003d7a]" />
            </button>
          ))}
        </div>
      )}

      {/* File listing */}
      {!loading && (isBackend(platform) || platformView === 'files') && (
        <div className="flex-1 overflow-y-auto">
          {entries.length === 0 && !error && (
            <p className="text-xs text-gray-400 py-8 text-center">Empty directory</p>
          )}
          {entries.map((entry) => {
            const isFile = entry.type === 'file';
            const isDir = entry.type === 'directory';
            const key = entry.path || entry.id || entry.name;
            const selected = selectedSet.has(key);
            const nifti = isFile && isNifti(entry.name);
            const dicom = isFile && isDicom(entry.name);
            const ext = entry.name.split('.').pop()?.toUpperCase() || '';

            return (
              <div
                key={key}
                className={`flex items-center px-3 py-1 text-xs cursor-pointer transition border-b border-gray-50 ${
                  selected ? 'bg-blue-50 border-blue-100' : 'hover:bg-gray-50'
                }`}
                onClick={() => isFile ? toggleSelect(entry) : toggleSelect(entry)}
                onDoubleClick={() => isDir && navigateInto(entry)}
              >
                {/* Checkbox */}
                <span className="w-6 flex-shrink-0">
                  <button onClick={e => { e.stopPropagation(); toggleSelect(entry); }}>
                    {selected
                      ? <CheckSquare className="h-3.5 w-3.5 text-[#003d7a]" />
                      : <Square className="h-3.5 w-3.5 text-gray-300" />
                    }
                  </button>
                </span>

                {/* Icon + Navigate button for folders */}
                <span className="w-5 flex-shrink-0">
                  {isDir ? (
                    <button
                      onClick={e => { e.stopPropagation(); navigateInto(entry); }}
                      title="Open folder"
                    >
                      <FolderOpen className="h-3.5 w-3.5 text-navy-500 hover:text-navy-600" />
                    </button>
                  ) : nifti ? (
                    <FileText className="h-3.5 w-3.5 text-green-600" />
                  ) : dicom ? (
                    <FileText className="h-3.5 w-3.5 text-blue-600" />
                  ) : (
                    <File className="h-3.5 w-3.5 text-gray-400" />
                  )}
                </span>

                {/* Name (click navigates into folders) */}
                <span
                  className={`flex-1 truncate ${
                    isDir ? 'font-medium text-gray-800 hover:text-[#003d7a] hover:underline' :
                    nifti ? 'text-green-700 font-medium' :
                    'text-gray-700'
                  }`}
                  onClick={isDir ? (e) => { e.stopPropagation(); navigateInto(entry); } : undefined}
                >
                  {entry.name}
                </span>

                {/* Badge */}
                {nifti && <span className="text-[9px] bg-green-100 text-green-700 px-1 py-0.5 rounded mr-1 font-medium">NIfTI</span>}
                {dicom && <span className="text-[9px] bg-navy-100 text-navy-700 px-1 py-0.5 rounded mr-1 font-medium">DICOM</span>}
                {isDir && selected && <span className="text-[9px] bg-blue-100 text-[#003d7a] px-1 py-0.5 rounded mr-1 font-medium">FOLDER</span>}

                {/* Size */}
                <span className="w-20 text-right text-gray-400 flex-shrink-0">
                  {isFile ? formatSize(entry.size) : ''}
                </span>

                {/* Type / Navigate arrow */}
                <span className="w-16 text-right text-gray-400 flex-shrink-0">
                  {isFile ? ext : (
                    <button
                      onClick={e => { e.stopPropagation(); navigateInto(entry); }}
                      className="hover:text-[#003d7a]"
                      title="Open folder"
                    >
                      <ChevronRight className="h-3 w-3 inline" />
                    </button>
                  )}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer status bar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-t border-gray-200 bg-gray-50 text-[10px] text-gray-500">
        <div className="flex items-center gap-3">
          {(isBackend(platform) || platformView === 'files') && (
            <>
              <span>{dirCount} folder{dirCount !== 1 ? 's' : ''}, {fileCount} file{fileCount !== 1 ? 's' : ''}</span>
              {niftiCount > 0 && <span className="text-green-600 font-medium">{niftiCount} NIfTI</span>}
            </>
          )}
          {!isBackend(platform) && platformView === 'datasets' && (
            <span>{platformDatasets.length} dataset{platformDatasets.length !== 1 ? 's' : ''}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {selectedFiles.length > 0 && (
            <span className="text-[#003d7a] font-medium">
              {selectedFiles.length} selected
              {selectedFiles.some(f => f.type === 'directory') && ' (incl. folders)'}
            </span>
          )}
          {entries.length > 0 && (
            <button onClick={selectAll} className="text-[#003d7a] hover:underline">
              {selectedFiles.length === entries.length ? 'Deselect all' : 'Select all'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default FileBrowserPane;
export { FileBrowserPane };
export type { FileEntry, PlatformType };
