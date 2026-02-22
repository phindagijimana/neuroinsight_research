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

interface ApiFile {
  name: string;
  type: string;       // volume, metadata, metrics, image, report, log, file
  path: string;       // download URL
  size: string;       // human-readable
  size_bytes?: number;
}

interface FileBrowserProps {
  jobId: string;
  onFileSelect?: (path: string) => void;
  showDownload?: boolean;
  showViewButton?: boolean;
}

/** Check if a file is a viewable medical image. */
export const isViewableImage = (filename: string): boolean => {
  const imageExtensions = [
    '.nii.gz', '.nii', '.mgz', '.mgh', '.nrrd', '.mif', '.mhd',
  ];
  return imageExtensions.some(ext => filename.toLowerCase().endsWith(ext));
};

/** Group flat file list into a folder tree. */
function buildTree(files: ApiFile[]): TreeNode[] {
  const root: TreeNode = { name: '', type: 'folder', path: '', children: [] };

  for (const f of files) {
    const parts = f.name.split('/');
    let current = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isLast = i === parts.length - 1;
      if (isLast) {
        current.children!.push({
          name: part,
          type: 'file',
          path: f.path,
          size: f.size,
          isImage: isViewableImage(part),
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
    } else if (onFileSelect && item.isImage) {
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
          <Brain className="w-4 h-4 text-purple-500 flex-shrink-0" />
        ) : (
          <File className="w-4 h-4 text-gray-500 flex-shrink-0" />
        )}

        <span className="flex-1 text-sm text-gray-900 truncate">{item.name}</span>

        {item.type === 'file' && item.size && (
          <span className="text-xs text-gray-500 flex-shrink-0">{item.size}</span>
        )}

        {item.type === 'file' && (
          <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
            {showViewButton && item.isImage && (
              <button
                onClick={() => onFileSelect && onFileSelect(item.path)}
                className="p-1 text-[#003d7a] hover:bg-navy-100 rounded transition"
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
}) => {
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
          setTree(buildTree(data.files));
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
  }, [jobId]);

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
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <div className="flex items-center justify-center gap-3">
          <Activity className="w-5 h-5 text-[#003d7a] animate-spin" />
          <span className="text-gray-600">Loading files...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <p className="text-sm text-gray-500">{error}</p>
      </div>
    );
  }

  if (tree.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <p className="text-sm text-gray-500">No output files found.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">
          Output Files <span className="text-gray-500 font-normal">({totalFiles})</span>
        </h3>
        {showDownload && (
          <button
            onClick={handleDownloadAll}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] transition"
          >
            <Download className="w-4 h-4" />
            Export All
          </button>
        )}
      </div>
      <div className="p-2 max-h-96 overflow-y-auto">
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
