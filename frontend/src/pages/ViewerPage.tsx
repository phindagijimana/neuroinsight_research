/**
 * ViewerPage — Signal | Imaging | Multimodal (single page, one mode visible at a time).
 * Imaging View uses Niivue; Signal View uses MNE-backed /api/results/.../eeg_preview.
 */

import { useState, useEffect, useCallback } from 'react';
import { apiService } from '../services/api';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import type { Job } from '../types';
import NiivueViewer from '../components/NiivueViewer';
import EegViewerPanel from '../components/EegViewerPanel';
import EegBrainFusionPanel from '../components/EegBrainFusionPanel';
import JobSelector from '../components/JobSelector';
import FileBrowser, { type ViewerFileMode } from '../components/FileBrowser';
import Eye from '../components/icons/Eye';
import Activity from '../components/icons/Activity';
import Download from '../components/icons/Download';
import RefreshCw from '../components/icons/RefreshCw';
import Brain from '../components/icons/Brain';
import {
  parseResultFilePathFromDownloadUrl,
  isImagingResultPath,
  isEegResultPath,
} from '../utils/resultFiles';
import {
  type ViewerTab,
  parseViewerTabFromSearch,
  setViewerQueryParam,
} from '../utils/viewerQuery';

export type { ViewerTab } from '../utils/viewerQuery';

interface ViewerPageProps {
  selectedJobId: string | null;
  setSelectedJobId: (jobId: string | null) => void;
  /** Incremented when app navigates to Viewer (re-sync tab from URL). */
  viewerNavEpoch?: number;
}

const ViewerPage: React.FC<ViewerPageProps> = ({
  selectedJobId,
  setSelectedJobId,
  viewerNavEpoch = 0,
}) => {
  const { eegEnabled } = useFeatureFlags();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string>('');
  const [segmentationUrl, setSegmentationUrl] = useState<string>('');
  const [showFileBrowser, setShowFileBrowser] = useState(false);
  const [viewerReady, setViewerReady] = useState(false);
  const [viewerTab, setViewerTab] = useState<ViewerTab>(() =>
    typeof window !== 'undefined'
      ? parseViewerTabFromSearch(window.location.search) ?? 'imaging'
      : 'imaging'
  );
  const [eegFileRelPath, setEegFileRelPath] = useState<string | null>(null);

  const commitViewerTab = useCallback((tab: ViewerTab) => {
    setViewerTab(tab);
    setViewerQueryParam(tab);
  }, []);

  useEffect(() => {
    const onPopState = () => {
      const t = parseViewerTabFromSearch(window.location.search);
      setViewerTab(t ?? 'imaging');
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    const t = parseViewerTabFromSearch(window.location.search) ?? 'imaging';
    setViewerTab(t);
  }, [viewerNavEpoch]);

  // When EEG is disabled, the Signal/Multimodal tabs are hidden — force any
  // EEG-only tab (e.g. from a stale deep link) back to the Imaging view.
  useEffect(() => {
    if (!eegEnabled && (viewerTab === 'eeg' || viewerTab === 'eeg-brain')) {
      commitViewerTab('imaging');
    }
  }, [eegEnabled, viewerTab, commitViewerTab]);

  useEffect(() => {
    fetchJobs();
  }, []);

  useEffect(() => {
    setEegFileRelPath(null);
  }, [selectedJobId]);

  useEffect(() => {
    if (selectedJobId) {
      const selectedJob = jobs.find((j) => j.id === selectedJobId);
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
    setError(null);
    try {
      const [volData, segData] = await Promise.allSettled([
        apiService.getJobVolumes(jobId),
        apiService.getJobSegmentations(jobId),
      ]);

      const baseUrl = apiService.getBaseUrl();

      const volFailed = volData.status === 'rejected';
      const volNotFound = volFailed && String(volData.reason).includes('404');

      if (volData.status === 'fulfilled' && volData.value.volumes.length > 0) {
        setImageUrl(`${baseUrl}${volData.value.volumes[0].path}`);
      } else {
        setImageUrl('');
        if (volNotFound) {
          const selectedJob = jobs.find((j) => j.id === jobId);
          const isRemote =
            selectedJob?.backend_type === 'slurm' ||
            selectedJob?.backend_type === 'remote_docker';
          if (isRemote) {
            setError(
              'Cannot access remote results — HPC connection may be lost. ' +
                'Go to Jobs page and reconnect to the HPC, then try again.'
            );
          }
        }
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
    const baseUrl = apiService.getBaseUrl();
    const fullUrl = downloadPath.startsWith('http') ? downloadPath : `${baseUrl}${downloadPath}`;
    const rel = parseResultFilePathFromDownloadUrl(downloadPath);

    if (isImagingResultPath(downloadPath)) {
      setImageUrl(fullUrl);
      setSegmentationUrl('');
      setViewerReady(true);
      if (viewerTab !== 'eeg-brain') {
        commitViewerTab('imaging');
      }
    }

    if (isEegResultPath(downloadPath) && rel) {
      setEegFileRelPath(rel);
      if (viewerTab !== 'eeg-brain') {
        commitViewerTab('eeg');
      }
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

  const completedJobs = jobs.filter((j) => j.status === 'completed');

  const fileMode: ViewerFileMode =
    viewerTab === 'imaging' ? 'imaging' : viewerTab === 'eeg' ? 'eeg' : 'multimodal';

  const tabBtn = (id: ViewerTab, label: string) => (
    <button
      type="button"
      key={id}
      onClick={() => commitViewerTab(id)}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
        viewerTab === id
          ? 'bg-[#003d7a] text-white shadow-sm'
          : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-2">
            <div className="flex items-center gap-3">
              <Eye className="w-8 h-8 text-[#003d7a]" />
              <div>
                <h1 className="text-3xl font-bold text-gray-900">Viewer</h1>
                <p className="text-gray-600">
                  {eegEnabled
                    ? 'Signal View (time series), Imaging View (Niivue), or Multimodal View (combined)'
                    : 'Imaging View (Niivue)'}
                </p>
              </div>
            </div>
            <button
              onClick={fetchJobs}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition self-start"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>

          <div className="flex flex-wrap gap-2 mt-4">
            {eegEnabled && tabBtn('eeg', 'Signal View')}
            {tabBtn('imaging', 'Imaging View')}
            {eegEnabled && tabBtn('eeg-brain', 'Multimodal View')}
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

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

        {!loading && selectedJobId && showFileBrowser && (
          <div className="mb-6 max-h-80 overflow-y-auto">
            <FileBrowser
              jobId={selectedJobId}
              onFileSelect={handleFileSelect}
              showDownload={true}
              showViewButton={true}
              viewerFileMode={fileMode}
            />
          </div>
        )}

        {job && (
          <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-sm font-medium text-gray-900">{job.pipeline_name}</span>
                <span className="text-sm text-gray-500 ml-3">Job: {job.id.slice(0, 8)}</span>
              </div>
              <span
                className={`px-3 py-1 rounded-full text-xs font-medium ${
                  job.status === 'completed'
                    ? 'bg-green-100 text-green-800'
                    : job.status === 'running'
                      ? 'bg-navy-100 text-navy-800'
                      : job.status === 'failed'
                        ? 'bg-red-100 text-red-800'
                        : 'bg-gray-100 text-gray-800'
                }`}
              >
                {job.status}
              </span>
            </div>
          </div>
        )}

        {loading && (
          <div className="bg-white rounded-lg border border-gray-200 p-8 text-center">
            <Activity className="w-6 h-6 text-[#003d7a] animate-spin mx-auto mb-3" />
            <span className="text-gray-600">Loading...</span>
          </div>
        )}

        {!loading && viewerTab === 'eeg' && (
          <EegViewerPanel jobId={selectedJobId} eegRelativePath={eegFileRelPath} />
        )}

        {!loading && viewerTab === 'imaging' && imageUrl && (
          <div className="space-y-6">
            <NiivueViewer
              imageUrl={imageUrl}
              segmentationUrl={segmentationUrl || undefined}
              pipelineName={job?.pipeline_name}
              onLoad={() => setViewerReady(true)}
            />
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

        {!loading && viewerTab === 'eeg-brain' && imageUrl && (
          <div className="space-y-6">
            <EegBrainFusionPanel
              jobId={selectedJobId}
              eegRelativePath={eegFileRelPath}
              imageUrl={imageUrl}
              segmentationUrl={segmentationUrl || undefined}
              pipelineName={job?.pipeline_name}
              onNiivueLoad={() => setViewerReady(true)}
            />
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

        {!loading && viewerTab === 'imaging' && !imageUrl && !error && (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <Brain className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              {completedJobs.length === 0 ? 'No Completed Jobs Yet' : 'Open an imaging volume'}
            </h3>
            <p className="text-gray-600">
              {completedJobs.length === 0
                ? 'Complete a processing job first, then view results here.'
                : eegEnabled
                ? 'Select a job, show files, and open a NIfTI / MGZ file — or switch to Signal View.'
                : 'Select a job, show files, and open a NIfTI / MGZ file.'}
            </p>
          </div>
        )}

        {!loading && viewerTab === 'eeg-brain' && !imageUrl && !error && (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <Brain className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Add a brain volume</h3>
            <p className="text-gray-600 mb-2">
              Multimodal View needs a NIfTI / MGZ volume for the imaging pane. Pick one from files,
              then optionally add a signal file (.edf, .fif, …) for Signal View above.
            </p>
            <EegViewerPanel jobId={selectedJobId} eegRelativePath={eegFileRelPath} compact />
          </div>
        )}

        {viewerReady && imageUrl && viewerTab === 'imaging' && (
          <div className="mt-6 py-3 px-4 bg-[#003d7a]/10 border border-[#003d7a]/20 rounded-lg text-center text-sm text-gray-700">
            <span className="font-medium text-[#003d7a]">L/R</span> markers indicate patient
            orientation. Use files to load a different volume.
          </div>
        )}

        {viewerTab === 'eeg-brain' && imageUrl && (
          <div className="mt-6 py-3 px-4 bg-[#003d7a]/10 border border-[#003d7a]/20 rounded-lg text-center text-sm text-gray-700">
            Multimodal View: Signal View (MNE preview, first seconds) above; Imaging View (Niivue)
            below — anatomy or source-level maps from your pipeline outputs.
          </div>
        )}
      </div>
    </div>
  );
};

export default ViewerPage;
