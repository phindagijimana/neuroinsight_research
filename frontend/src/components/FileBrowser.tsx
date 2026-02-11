/**
 * FileBrowser Component
 * Browse job output files and folders with download options
 * 
 * Supports viewing medical imaging formats:
 * - NIfTI: .nii, .nii.gz
 * - FreeSurfer: .mgz, .mgh
 * - NRRD: .nrrd
 * - MRtrix: .mif
 * - ITK: .mhd
 */

import React, { useState, useEffect } from 'react';
import Folder from './icons/Folder';
import File from './icons/File';
import Download from './icons/Download';
import Eye from './icons/Eye';
import Brain from './icons/Brain';
import ChevronRight from './icons/ChevronRight';
import Activity from './icons/Activity';
import { apiService } from '../services/api';

interface FileItem {
  name: string;
  type: 'file' | 'folder';
  path: string;
  size?: number;
  children?: FileItem[];
  isImage?: boolean;
}

interface FileBrowserProps {
  jobId: string;
  onFileSelect?: (path: string) => void;
  showDownload?: boolean;
  showViewButton?: boolean;
}

// Check if file is a viewable medical image
export const isViewableImage = (filename: string): boolean => {
  const imageExtensions = [
    '.nii.gz', '.nii',           // NIfTI
    '.mgz', '.mgh',              // FreeSurfer MGH/MGZ
    '.nrrd',                     // NRRD
    '.mif',                      // MRtrix
    '.mhd',                      // ITK MetaImage
  ];
  return imageExtensions.some(ext => filename.toLowerCase().endsWith(ext));
};

// Mock file structure generator - reflects plugin/workflow architecture
const generateMockFiles = (jobId: string): FileItem[] => {
  // Different structures based on job type
  if (jobId.includes('fmri-full')) {
    // fMRI Full Pipeline (fMRIPrep -> XCP-D workflow)
    return [
      {
        name: 'native',
        type: 'folder',
        path: '/native',
        children: [
          {
            name: 'fmriprep',
            type: 'folder',
            path: '/native/fmriprep',
            children: [
              {
                name: 'sub-001',
                type: 'folder',
                path: '/native/fmriprep/sub-001',
                children: [
                  { name: 'sub-001_desc-preproc_bold.nii.gz', type: 'file', path: '/native/fmriprep/sub-001/sub-001_desc-preproc_bold.nii.gz', size: 45678901, isImage: true },
                  { name: 'sub-001_confounds.tsv', type: 'file', path: '/native/fmriprep/sub-001/sub-001_confounds.tsv', size: 123456 },
                  { name: 'sub-001_desc-brain_mask.nii.gz', type: 'file', path: '/native/fmriprep/sub-001/sub-001_desc-brain_mask.nii.gz', size: 1234567, isImage: true },
                ]
              },
              { name: 'sub-001.html', type: 'file', path: '/native/fmriprep/sub-001.html', size: 234567 },
            ]
          },
          {
            name: 'xcpd',
            type: 'folder',
            path: '/native/xcpd',
            children: [
              {
                name: 'sub-001',
                type: 'folder',
                path: '/native/xcpd/sub-001',
                children: [
                  { name: 'sub-001_desc-denoised_bold.nii.gz', type: 'file', path: '/native/xcpd/sub-001/sub-001_desc-denoised_bold.nii.gz', size: 43210987, isImage: true },
                  { name: 'sub-001_connectivity.csv', type: 'file', path: '/native/xcpd/sub-001/sub-001_connectivity.csv', size: 45678 },
                  { name: 'sub-001_desc-carpetplot.png', type: 'file', path: '/native/xcpd/sub-001/sub-001_desc-carpetplot.png', size: 567890 },
                ]
              },
            ]
          },
        ]
      },
      {
        name: 'bundle',
        type: 'folder',
        path: '/bundle',
        children: [
          {
            name: 'volumes',
            type: 'folder',
            path: '/bundle/volumes',
            children: [
              { name: 'bold_preproc.nii.gz', type: 'file', path: '/bundle/volumes/bold_preproc.nii.gz', size: 45678901, isImage: true },
              { name: 'bold_denoised.nii.gz', type: 'file', path: '/bundle/volumes/bold_denoised.nii.gz', size: 43210987, isImage: true },
            ]
          },
          {
            name: 'metrics',
            type: 'folder',
            path: '/bundle/metrics',
            children: [
              { name: 'connectivity.csv', type: 'file', path: '/bundle/metrics/connectivity.csv', size: 45678 },
              { name: 'motion.csv', type: 'file', path: '/bundle/metrics/motion.csv', size: 12345 },
            ]
          },
          {
            name: 'qc',
            type: 'folder',
            path: '/bundle/qc',
            children: [
              { name: 'carpet_plot.png', type: 'file', path: '/bundle/qc/carpet_plot.png', size: 567890 },
              { name: 'motion_plot.png', type: 'file', path: '/bundle/qc/motion_plot.png', size: 234567 },
            ]
          },
          { name: 'labels.json', type: 'file', path: '/bundle/labels.json', size: 3456 },
        ]
      },
      {
        name: 'logs',
        type: 'folder',
        path: '/logs',
        children: [
          { name: 'fmriprep.log', type: 'file', path: '/logs/fmriprep.log', size: 456789 },
          { name: 'xcpd.log', type: 'file', path: '/logs/xcpd.log', size: 123456 },
        ]
      },
      { name: 'workflow.yaml', type: 'file', path: '/workflow.yaml', size: 2345 },
      { name: 'manifest.json', type: 'file', path: '/manifest.json', size: 5678 },
    ];
  } else if (jobId.includes('structural-seg') || jobId.includes('fastsurfer')) {
    // Structural Segmentation (FastSurfer or FreeSurfer)
    return [
      {
        name: 'native',
        type: 'folder',
        path: '/native',
        children: [
          {
            name: 'fastsurfer',
            type: 'folder',
            path: '/native/fastsurfer',
            children: [
              {
                name: 'mri',
                type: 'folder',
                path: '/native/fastsurfer/mri',
                children: [
                  { name: 'T1.mgz', type: 'file', path: '/native/fastsurfer/mri/T1.mgz', size: 9123456, isImage: true },
                  { name: 'aseg.mgz', type: 'file', path: '/native/fastsurfer/mri/aseg.mgz', size: 8012345, isImage: true },
                  { name: 'aparc+aseg.mgz', type: 'file', path: '/native/fastsurfer/mri/aparc+aseg.mgz', size: 9876543, isImage: true },
                  { name: 'brain.mgz', type: 'file', path: '/native/fastsurfer/mri/brain.mgz', size: 8456789, isImage: true },
                ]
              },
              {
                name: 'stats',
                type: 'folder',
                path: '/native/fastsurfer/stats',
                children: [
                  { name: 'aseg.stats', type: 'file', path: '/native/fastsurfer/stats/aseg.stats', size: 12345 },
                  { name: 'lh.aparc.stats', type: 'file', path: '/native/fastsurfer/stats/lh.aparc.stats', size: 15678 },
                  { name: 'rh.aparc.stats', type: 'file', path: '/native/fastsurfer/stats/rh.aparc.stats', size: 15890 },
                ]
              },
            ]
          },
        ]
      },
      {
        name: 'bundle',
        type: 'folder',
        path: '/bundle',
        children: [
          {
            name: 'volumes',
            type: 'folder',
            path: '/bundle/volumes',
            children: [
              { name: 'segmentation.nii.gz', type: 'file', path: '/bundle/volumes/segmentation.nii.gz', size: 8012345, isImage: true },
              { name: 'brain.nii.gz', type: 'file', path: '/bundle/volumes/brain.nii.gz', size: 8456789, isImage: true },
            ]
          },
          {
            name: 'metrics',
            type: 'folder',
            path: '/bundle/metrics',
            children: [
              { name: 'volumes.csv', type: 'file', path: '/bundle/metrics/volumes.csv', size: 8901 },
              { name: 'cortical_thickness.csv', type: 'file', path: '/bundle/metrics/cortical_thickness.csv', size: 12345 },
            ]
          },
        ]
      },
      {
        name: 'logs',
        type: 'folder',
        path: '/logs',
        children: [
          { name: 'fastsurfer.log', type: 'file', path: '/logs/fastsurfer.log', size: 234567 },
        ]
      },
      { name: 'manifest.json', type: 'file', path: '/manifest.json', size: 4567 },
    ];
  } else {
    // Default generic structure for other workflows
    return [
      {
        name: 'native',
        type: 'folder',
        path: '/native',
        children: [
          {
            name: 'outputs',
            type: 'folder',
            path: '/native/outputs',
            children: [
              { name: 'output_1.nii.gz', type: 'file', path: '/native/outputs/output_1.nii.gz', size: 8945678, isImage: true },
              { name: 'output_2.nii.gz', type: 'file', path: '/native/outputs/output_2.nii.gz', size: 7856234, isImage: true },
            ]
          },
        ]
      },
      {
        name: 'bundle',
        type: 'folder',
        path: '/bundle',
        children: [
          { name: 'results.csv', type: 'file', path: '/bundle/results.csv', size: 12345 },
        ]
      },
      {
        name: 'logs',
        type: 'folder',
        path: '/logs',
        children: [
          { name: 'execution.log', type: 'file', path: '/logs/execution.log', size: 45678 },
        ]
      },
      { name: 'manifest.json', type: 'file', path: '/manifest.json', size: 3456 },
    ];
  }
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
};

const FileTreeItem: React.FC<{
  item: FileItem;
  depth: number;
  onFileSelect?: (path: string) => void;
  onDownload: (path: string, name: string) => void;
  showDownload: boolean;
  showViewButton: boolean;
}> = ({ item, depth, onFileSelect, onDownload, showDownload, showViewButton }) => {
  const [isExpanded, setIsExpanded] = useState(depth === 0); // Auto-expand first level

  const handleClick = () => {
    if (item.type === 'folder') {
      setIsExpanded(!isExpanded);
    } else if (onFileSelect) {
      onFileSelect(item.path);
    }
  };

  return (
    <div>
      <div
        className={`flex items-center gap-2 px-3 py-2 rounded-md hover:bg-gray-100 cursor-pointer transition ${
          item.type === 'file' ? 'hover:bg-navy-50' : ''
        }`}
        style={{ paddingLeft: `${depth * 20 + 12}px` }}
        onClick={handleClick}
      >
        {item.type === 'folder' && (
          <ChevronRight
            className={`w-4 h-4 text-gray-500 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
          />
        )}
        
        {item.type === 'folder' ? (
          <Folder className="w-5 h-5 text-navy-500 flex-shrink-0" />
        ) : item.isImage ? (
          <Brain className="w-5 h-5 text-purple-500 flex-shrink-0" />
        ) : (
          <File className="w-5 h-5 text-gray-500 flex-shrink-0" />
        )}
        
        <span className="flex-1 text-sm text-gray-900 font-medium">
          {item.name}
        </span>
        
        {item.type === 'file' && item.size && (
          <span className="text-xs text-gray-500">{formatFileSize(item.size)}</span>
        )}
        
        {item.type === 'file' && (
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            {showViewButton && item.isImage && (
              <button
                onClick={() => onFileSelect && onFileSelect(item.path)}
                className="p-1 text-[#003d7a] hover:bg-navy-100 rounded transition"
                title="View in viewer"
              >
                <Eye className="w-4 h-4" />
              </button>
            )}
            {showDownload && (
              <button
                onClick={() => onDownload(item.path, item.name)}
                className="p-1 text-gray-600 hover:bg-gray-200 rounded transition"
                title="Download file"
              >
                <Download className="w-4 h-4" />
              </button>
            )}
          </div>
        )}
      </div>
      
      {item.type === 'folder' && isExpanded && item.children && (
        <div>
          {item.children.map((child, idx) => (
            <FileTreeItem
              key={idx}
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
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulate API call to fetch files
    setLoading(true);
    setTimeout(() => {
      setFiles(generateMockFiles(jobId));
      setLoading(false);
    }, 500);
  }, [jobId]);

  const handleDownload = async (path: string, name: string) => {
    try {
      await apiService.downloadFile(jobId, path);
      console.log(`Downloading: ${name} from ${path}`);
    } catch (error) {
      console.error('Download failed:', error);
      alert(`Failed to download ${name}. Please try again.`);
    }
  };

  const handleDownloadAll = () => {
    // TODO: Implement bulk download (create tar.gz of all files)
    alert(`Downloading all files for job: ${jobId}\n\nBulk download feature will be implemented in a future update.`);
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

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">Output Files</h3>
        {showDownload && (
          <button
            onClick={handleDownloadAll}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] transition"
          >
            <Download className="w-4 h-4" />
            Download All
          </button>
        )}
      </div>
      <div className="p-2 max-h-96 overflow-y-auto">
        {files.map((item, idx) => (
          <FileTreeItem
            key={idx}
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
