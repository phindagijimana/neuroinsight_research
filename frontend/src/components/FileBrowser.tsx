/**
 * FileBrowser Component
 * Browse REAL job output files from the backend API.
 *
 * Fetches the actual file listing from /api/results/{jobId}/files
 * and renders a flat list with download and view options.
 */

import React, { useState, useEffect } from 'react';
import Folder from './icons/Folder';
import File from './icons/File';
import Download from './icons/Download';
import Eye from './icons/Eye';
import Brain from './icons/Brain';
import Activity from './icons/Activity';
import { apiService } from '../services/api';
import { Spinner } from './LoadingState';

interface ApiFile {
  name: string;
  type: string;       // volume, metadata, metrics, image, report, log, file
  path: string;       // download URL
  size: string;       // human-readable
  size_bytes?: number;
}

/** Which viewer tab is picking files (controls View button + row open). */
export type ViewerFileMode = 'imaging' | 'eeg' | 'multimodal';

interface FileBrowserProps {
  jobId: string;
  onFileSelect?: (path: string) => void;
  showDownload?: boolean;
  showViewButton?: boolean;
  /** Default imaging — matches legacy NIfTI-only viewer. */
  viewerFileMode?: ViewerFileMode;
  /** Card layout for Results; embedded fills a parent panel (Viewer drawer). */
  variant?: 'card' | 'embedded';
}

/** Check if a file is a viewable medical image. */
export const isViewableImage = (filename: string): boolean => {
  const imageExtensions = [
    '.nii.gz', '.nii', '.mgz', '.mgh', '.nrrd', '.mif', '.mhd',
  ];
  return imageExtensions.some(ext => filename.toLowerCase().endsWith(ext));
};

/** EEG formats supported by backend MNE preview. */
export const isViewableEegFile = (filename: string): boolean => {
  const l = filename.toLowerCase();
  return (
    l.endsWith('.edf') ||
    l.endsWith('.fif') ||
    l.endsWith('.fif.gz') ||
    l.endsWith('.vhdr') ||
    l.endsWith('.bdf')
  );
};

function viewableInViewerMode(
  isImage: boolean,
  isEeg: boolean,
  mode: ViewerFileMode
): boolean {
  if (mode === 'imaging') return isImage;
  if (mode === 'eeg') return isEeg;
  return isImage || isEeg;
}

/** Group flat file list into a folder tree. */
function buildTree(files: ApiFile[], viewerFileMode: ViewerFileMode): TreeNode[] {
  const root: TreeNode = { name: '', type: 'folder', path: '', children: [] };

  for (const f of files) {
    const parts = f.name.split('/');
    let current = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      if (isLast) {
        const isImage = isViewableImage(part);
        const isEeg = isViewableEegFile(part);
        current.children!.push({
          name: part,
          type: 'file',
          path: f.path,
          size: f.size,
          isImage,
          isEeg,
          viewInViewer: viewableInViewerMode(isImage, isEeg, viewerFileMode),
          fileType: f.type,
        });
      } else {
        let child = current.children!.find(c => c.name === part && c.type === 'folder');
        if (!child) {
          child = { name: part, type: 'folder', path: '', children: [] };
          current.children!.push(child);
        }
        current = child;
      }
    }
  }

  return root.children || [];
}

interface TreeNode {
  name: string;
  type: 'file' | 'folder';
  path: string;
  size?: string;
  children?: TreeNode[];
  isImage?: boolean;
  isEeg?: boolean;
  viewInViewer?: boolean;
  fileType?: string;
}

const FileTreeItem: React.FC<{
  item: TreeNode;
  depth: number;
  onFileSelect?: (path: string) => void;
  onDownload: (path: string, name: string) => void;
  showDownload: boolean;
  showViewButton: boolean;
}> = ({ item, depth, onFileSelect, onDownload, showDownload, showViewButton }) => {
  const [isExpanded, setIsExpanded] = useState(depth === 0);

  const handleClick = () => {
    if (item.type === 'folder') {
      setIsExpanded(!isExpanded);
    } else if (onFileSelect && item.viewInViewer) {
      onFileSelect(item.path);
    }
  };

  return (
    <div>
      <div
        className={`flex items-center gap-2 px-3 py-1.5 rounded-md hover:bg-gray-100 cursor-pointer transition ${
          item.type === 'file' ? 'hover:bg-navy-50' : ''
        }`}
        style={{ paddingLeft: `${depth * 16 + 12}px` }}
        onClick={handleClick}
      >
        {item.type === 'folder' ? (
          <Folder className="w-4 h-4 text-navy-500 flex-shrink-0" />
        ) : item.isImage ? (
          <Brain className="w-4 h-4 text-navy-500 flex-shrink-0" />
        ) : item.isEeg ? (
          <Activity className="w-4 h-4 text-emerald-600 flex-shrink-0" />
        ) : (
          <File className="w-4 h-4 text-gray-500 flex-shrink-0" />
        )}

        <span className="flex-1 text-sm text-gray-900 truncate">{item.name}</span>

        {item.type === 'file' && item.size && (
          <span className="text-xs text-gray-500 flex-shrink-0">{item.size}</span>
        )}

        {item.type === 'file' && (
          <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
            {showViewButton && item.viewInViewer && (
              <button
                onClick={() => onFileSelect && onFileSelect(item.path)}
                className="p-1 text-navy-600 hover:bg-navy-100 rounded transition"
                title="View in viewer"
              >
                <Eye className="w-3.5 h-3.5" />
              </button>
            )}
            {showDownload && (
              <button
                onClick={() => onDownload(item.path, item.name)}
                className="p-1 text-gray-600 hover:bg-gray-200 rounded transition"
                title="Download file"
              >
                <Download className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        )}
      </div>

      {item.type === 'folder' && isExpanded && item.children && (
        <div>
          {item.children.map((child, idx) => (
            <FileTreeItem
              key={`${child.name}-${idx}`}
              item={child}
              depth={depth + 1}
              onFileSelect={onFileSelect}
              onDownload={onDownload}
              showDownload={showDownload}
              showViewButton={showViewButton}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const FileBrowser: React.FC<FileBrowserProps> = ({
  jobId,
  onFileSelect,
  showDownload = true,
  showViewButton = false,
  viewerFileMode = 'imaging',
  variant = 'card',
}) => {
  const embedded = variant === 'embedded';
  const shellClass = embedded
    ? 'flex h-full min-h-0 flex-col bg-white'
    : 'rounded-lg border border-gray-200 bg-white';
  const stateShellClass = embedded
    ? 'flex h-full min-h-0 flex-1 items-center justify-center p-4'
    : 'rounded-lg border border-gray-200 bg-white p-6';
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [totalFiles, setTotalFiles] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const fetchFiles = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiService.getJobFiles(jobId);
        if (!cancelled) {
          setTree(buildTree(data.files, viewerFileMode));
          setTotalFiles(data.total);
        }
      } catch (err: any) {
        if (!cancelled) {
          const status = err?.response?.status;
          if (status === 404) {
            setError('No output files yet. Job may still be running.');
          } else {
            setError('Failed to load output files.');
          }
          setTree([]);
          setTotalFiles(0);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchFiles();
    return () => { cancelled = true; };
  }, [jobId, viewerFileMode]);

  const handleDownload = async (downloadPath: string, name: string) => {
    try {
      // downloadPath is already a full /api/results/... URL path
      const baseUrl = apiService.getBaseUrl();
      window.open(`${baseUrl}${downloadPath}`, '_blank');
    } catch {
      console.error(`Download failed: ${name}`);
    }
  };

  const handleDownloadAll = () => {
    const url = apiService.exportJobResultsUrl(jobId);
    window.open(url, '_blank');
  };

  if (loading) {
    return (
      <div className={stateShellClass}>
        <div className="flex items-center justify-center gap-3">
          <Spinner size="md" className="text-navy-600" />
          <span className="text-sm text-gray-600">Loading files…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={stateShellClass}>
        <p className="text-sm text-gray-500">{error}</p>
      </div>
    );
  }

  if (tree.length === 0) {
    return (
      <div className={stateShellClass}>
        <p className="text-sm text-gray-500">No output files found.</p>
      </div>
    );
  }

  return (
    <div className={shellClass}>
      <div className={`flex shrink-0 items-center justify-between border-b border-gray-200 px-3 py-2 ${embedded ? 'bg-gray-50' : 'px-4 py-3'}`}>
        <h3 className="text-xs font-semibold text-gray-900 sm:text-sm">
          {embedded ? (
            <span className="text-gray-600">{totalFiles} file{totalFiles !== 1 ? 's' : ''}</span>
          ) : (
            <>
              Output Files <span className="font-normal text-gray-500">({totalFiles})</span>
            </>
          )}
        </h3>
        {showDownload && (
          <button
            onClick={handleDownloadAll}
            className="flex items-center gap-1.5 rounded-md bg-navy-600 px-2.5 py-1 text-xs text-white transition hover:bg-navy-800 sm:px-3 sm:py-1.5 sm:text-sm"
          >
            <Download className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            Export
          </button>
        )}
      </div>
      <div className={`min-h-0 flex-1 overflow-y-auto p-1.5 ${embedded ? '' : 'max-h-96'}`}>
        {tree.map((item, idx) => (
          <FileTreeItem
            key={`${item.name}-${idx}`}
            item={item}
            depth={0}
            onFileSelect={onFileSelect}
            onDownload={handleDownload}
            showDownload={showDownload}
            showViewButton={showViewButton}
          />
        ))}
      </div>
    </div>
  );
};

export default FileBrowser;
