/**
 * ViewerPage Component
 * PACS-like viewer for NIfTI brain imaging with colored segmentation.
 * All data comes from real backend API calls.
 */

import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import type { Job } from '../types';
import NiivueViewer from '../components/NiivueViewer';
import JobSelector from '../components/JobSelector';
import FileBrowser from '../components/FileBrowser';
import Eye from '../components/icons/Eye';
import Activity from '../components/icons/Activity';
import Download from '../components/icons/Download';
import RefreshCw from '../components/icons/RefreshCw';
import Brain from '../components/icons/Brain';

interface ViewerPageProps {
  selectedJobId: string | null;
  setSelectedJobId: (jobId: string | null) => void;
}

const ViewerPage: React.FC<ViewerPageProps> = ({ selectedJobId, setSelectedJobId }) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string>('');
  const [segmentationUrl, setSegmentationUrl] = useState<string>('');
  const [showFileBrowser, setShowFileBrowser] = useState(false);
  const [viewerReady, setViewerReady] = useState(false);

  useEffect(() => {
    fetchJobs();
  }, []);

  useEffect(() => {
    if (selectedJobId) {
      const selectedJob = jobs.find(j => j.id === selectedJobId);
      setJob(selectedJob || null);
      if (selectedJob && selectedJob.status === 'completed') {
        loadJobResults(selectedJobId);
      }
    } else {
      setJob(null);
      setImageUrl('');
      setSegmentationUrl('');
    }
  }, [selectedJobId, jobs]);

  const fetchJobs = async () => {
    setLoading(true);
    setError(null);
    try {
      const jobsData = await apiService.getJobs();
      setJobs(jobsData);
      if (!selectedJobId) {
        const firstCompleted = jobsData.find((j: Job) => j.status === 'completed');
        if (firstCompleted) {
          setSelectedJobId(firstCompleted.id);
        }
      }
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
      setError('Could not connect to backend.');
    } finally {
      setLoading(false);
    }
  };

  const loadJobResults = async (jobId: string) => {
    try {
      // Find volume and segmentation files from the real results API
      const [volData, segData] = await Promise.allSettled([
        apiService.getJobVolumes(jobId),
        apiService.getJobSegmentations(jobId),
      ]);

      const baseUrl = apiService.getBaseUrl();

      if (volData.status === 'fulfilled' && volData.value.volumes.length > 0) {
        setImageUrl(`${baseUrl}${volData.value.volumes[0].path}`);
      } else {
        setImageUrl('');
      }

      if (segData.status === 'fulfilled' && segData.value.segmentations.length > 0) {
        setSegmentationUrl(`${baseUrl}${segData.value.segmentations[0].path}`);
      } else {
        setSegmentationUrl('');
      }

      setViewerReady(true);
    } catch {
      setImageUrl('');
      setSegmentationUrl('');
    }
  };

  const handleFileSelect = (downloadPath: string) => {
    // downloadPath is a relative API path like /api/results/{jobId}/download?file_path=...
    const baseUrl = apiService.getBaseUrl();
    const fullUrl = downloadPath.startsWith('http') ? downloadPath : `${baseUrl}${downloadPath}`;

    // Check if it's a viewable image
    const lower = downloadPath.toLowerCase();
    if (lower.includes('.nii') || lower.includes('.mgz') || lower.includes('.mgh') || lower.includes('.nrrd')) {
      setImageUrl(fullUrl);
      setSegmentationUrl(''); // Clear segmentation when loading a new file
      setViewerReady(true);
    }
  };

  const handleDownloadVolume = () => {
    if (imageUrl) window.open(imageUrl, '_blank');
  };

  const handleDownloadSegmentation = () => {
    if (segmentationUrl) window.open(segmentationUrl, '_blank');
  };

  const handleExportAll = () => {
    if (selectedJobId) {
      const url = apiService.exportJobResultsUrl(selectedJobId);
      window.open(url, '_blank');
    }
  };

  const completedJobs = jobs.filter(j => j.status === 'completed');

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-3">
              <Eye className="w-8 h-8 text-[#003d7a]" />
              <div>
                <h1 className="text-3xl font-bold text-gray-900">NIfTI Viewer</h1>
                <p className="text-gray-600">
                  Multi-planar visualization with segmentation overlays
                </p>
              </div>
            </div>
            <button
              onClick={fetchJobs}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Job Selector */}
        {!loading && completedJobs.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <div className="flex items-center justify-between gap-4">
              <div className="flex-1">
                <JobSelector
                  jobs={jobs}
                  selectedJobId={selectedJobId}
                  onJobSelect={(jobId) => {
                    setSelectedJobId(jobId);
                    setShowFileBrowser(true);
                  }}
                  label="Select Job to View"
                />
              </div>
              {selectedJobId && (
                <button
                  onClick={() => setShowFileBrowser(!showFileBrowser)}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition text-sm"
                >
                  {showFileBrowser ? 'Hide' : 'Show'} Files
                </button>
              )}
            </div>
          </div>
        )}

        {/* File Browser */}
        {!loading && selectedJobId && showFileBrowser && (
          <div className="mb-6 max-h-80 overflow-y-auto">
            <FileBrowser
              jobId={selectedJobId}
              onFileSelect={handleFileSelect}
              showDownload={true}
              showViewButton={true}
            />
          </div>
        )}

        {/* Job Info */}
        {job && (
          <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium text-gray-900">{job.pipeline_name}</span>
                <span className="text-sm text-gray-500 ml-3">Job: {job.id.slice(0, 8)}</span>
              </div>
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                job.status === 'completed' ? 'bg-green-100 text-green-800' :
                job.status === 'running' ? 'bg-navy-100 text-navy-800' :
                job.status === 'failed' ? 'bg-red-100 text-red-800' :
                'bg-gray-100 text-gray-800'
              }`}>
                {job.status}
              </span>
            </div>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
            <Activity className="w-6 h-6 text-[#003d7a] animate-spin mx-auto mb-3" />
            <span className="text-gray-600">Loading...</span>
          </div>
        )}

        {/* Niivue Viewer */}
        {!loading && imageUrl && (
          <div className="space-y-6">
            <NiivueViewer
              imageUrl={imageUrl}
              segmentationUrl={segmentationUrl || undefined}
              onLoad={() => setViewerReady(true)}
            />

            {/* Export Options */}
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={handleDownloadVolume}
                  className="flex items-center gap-2 px-4 py-2 bg-[#003d7a] text-white rounded-lg hover:bg-[#002b55] transition text-sm"
                >
                  <Download className="w-4 h-4" />
                  Download Volume
                </button>
                {segmentationUrl && (
                  <button
                    onClick={handleDownloadSegmentation}
                    className="flex items-center gap-2 px-4 py-2 bg-[#003d7a] text-white rounded-lg hover:bg-[#002b55] transition text-sm"
                  >
                    <Download className="w-4 h-4" />
                    Download Segmentation
                  </button>
                )}
                {selectedJobId && (
                  <button
                    onClick={handleExportAll}
                    className="flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition text-sm"
                  >
                    <Download className="w-4 h-4" />
                    Export All Results
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* No image loaded state */}
        {!loading && !imageUrl && !error && (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <Brain className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              {completedJobs.length === 0
                ? 'No Completed Jobs Yet'
                : 'Select a Job to View'}
            </h3>
            <p className="text-gray-600">
              {completedJobs.length === 0
                ? 'Complete a processing job first, then view results here.'
                : 'Select a completed job above, then click a NIfTI file to visualize it.'}
            </p>
          </div>
        )}

        {/* Orientation legend */}
        {viewerReady && imageUrl && (
          <div className="mt-6 py-3 px-4 bg-[#003d7a]/10 border border-[#003d7a]/20 rounded-lg text-center text-sm text-gray-700">
            <span className="font-medium text-[#003d7a]">L/R</span> markers indicate patient orientation (radiological view).
            Click any NIfTI/MGZ file in the file browser to load it in the viewer.
          </div>
        )}
      </div>
    </div>
  );
};

export default ViewerPage;
