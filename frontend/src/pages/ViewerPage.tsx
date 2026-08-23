/**
 * ViewerPage — Signal | Imaging | Multimodal (single page, one mode visible at a time).
 */
import { useState, useEffect, useCallback } from 'react';
import { Download } from 'lucide-react';
import { apiService } from '../services/api';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import type { Job } from '../types';
import NiivueViewer from '../components/NiivueViewer';
import EegViewerPanel from '../components/EegViewerPanel';
import EegBrainFusionPanel from '../components/EegBrainFusionPanel';
import JobSelector from '../components/JobSelector';
import ViewerFileDrawer from '../components/ViewerFileDrawer';
import { type ViewerFileMode } from '../components/FileBrowser';
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
import { LoadingState } from '../components/LoadingState';
import StatusBadge from '../components/StatusBadge';
import WorkspacePageHeader from '../components/WorkspacePageHeader';
import Button from '../components/Button';
import {
  deriveJobSubjectLabel,
  jobPipelineLabel,
  jobShortId,
} from '../lib/jobLabels';

export type { ViewerTab } from '../utils/viewerQuery';

interface ViewerPageProps {
  selectedJobId: string | null;
  setSelectedJobId: (jobId: string | null) => void;
  viewerNavEpoch?: number;
  localVolume?: { url: string; name: string } | null;
}

const VIEWER_TABS: { id: ViewerTab; label: string }[] = [
  { id: 'eeg', label: 'Signal' },
  { id: 'imaging', label: 'Imaging' },
  { id: 'eeg-brain', label: 'Multimodal' },
];

const VIEWER_DRAWER_KEY = 'nir.viewer.drawerOpen';

const ViewerPage: React.FC<ViewerPageProps> = ({
  selectedJobId,
  setSelectedJobId,
  viewerNavEpoch = 0,
  localVolume = null,
}) => {
  const { eegEnabled } = useFeatureFlags();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string>('');
  const [segmentationUrl, setSegmentationUrl] = useState<string>('');
  const [drawerOpen, setDrawerOpen] = useState(() => {
    try {
      const stored = window.sessionStorage.getItem(VIEWER_DRAWER_KEY);
      return stored === null ? true : stored === '1';
    } catch {
      return true;
    }
  });
  const [viewportHeight, setViewportHeight] = useState(
    typeof window !== 'undefined' ? window.innerHeight : 800,
  );
  const [viewerReady, setViewerReady] = useState(false);
  const [viewerTab, setViewerTab] = useState<ViewerTab>(() =>
    typeof window !== 'undefined'
      ? parseViewerTabFromSearch(window.location.search) ?? 'imaging'
      : 'imaging',
  );
  const [eegFileRelPath, setEegFileRelPath] = useState<string | null>(null);

  const commitViewerTab = useCallback((tab: ViewerTab) => {
    setViewerTab(tab);
    setViewerQueryParam(tab);
  }, []);

  const effectiveImageUrl = localVolume?.url || imageUrl;

  useEffect(() => {
    if (localVolume) commitViewerTab('imaging');
  }, [localVolume, commitViewerTab]);

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

  useEffect(() => {
    if (!eegEnabled && (viewerTab === 'eeg' || viewerTab === 'eeg-brain')) {
      commitViewerTab('imaging');
    }
  }, [eegEnabled, viewerTab, commitViewerTab]);

  useEffect(() => {
    fetchJobs();
  }, []);

  useEffect(() => {
    const onResize = () => setViewportHeight(window.innerHeight);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const toggleDrawer = useCallback(() => {
    setDrawerOpen((open) => {
      const next = !open;
      try {
        window.sessionStorage.setItem(VIEWER_DRAWER_KEY, next ? '1' : '0');
      } catch {
        // ignore
      }
      return next;
    });
  }, []);

  const canvasHeightPx = Math.min(820, Math.max(480, Math.floor(viewportHeight * 0.62)));

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
              'Cannot access remote results — reconnect to HPC from Jobs, then try again.',
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

  const handleExportAll = () => {
    if (selectedJobId) {
      window.open(apiService.exportJobResultsUrl(selectedJobId), '_blank');
    }
  };

  const completedJobs = jobs.filter((j) => j.status === 'completed');
  const visibleTabs = VIEWER_TABS.filter(
    (t) => eegEnabled || t.id === 'imaging',
  );

  const fileMode: ViewerFileMode =
    viewerTab === 'imaging' ? 'imaging' : viewerTab === 'eeg' ? 'eeg' : 'multimodal';

  const subjectLabel = job
    ? job.is_sample_job
      ? 'Sample EEG demo'
      : deriveJobSubjectLabel(job)
    : null;
  const pipelineLabel = job ? jobPipelineLabel(job) : '';

  const viewerSubtitle =
    viewerTab === 'eeg'
      ? 'Time-series preview from job outputs.'
      : viewerTab === 'eeg-brain'
        ? 'Combined EEG and brain imaging.'
        : 'Multi-planar NIfTI / MGZ viewer with overlays.';

  return (
    <div className="flex min-h-full flex-col bg-gray-50">
      <div className="mx-auto flex w-full max-w-[1800px] flex-1 flex-col px-4 py-6 sm:px-6 lg:px-8">
        <WorkspacePageHeader
          title="Viewer"
          subtitle={viewerSubtitle}
          actions={
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
              {!loading && completedJobs.length > 0 && (
                <JobSelector
                  compact
                  jobs={jobs}
                  selectedJobId={selectedJobId}
                  onJobSelect={setSelectedJobId}
                  label="Job"
                />
              )}
              <Button variant="secondary" onClick={fetchJobs}>
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
            </div>
          }
        />

        <div className="mb-5 inline-flex rounded-lg border border-gray-200 bg-white p-1 shadow-sm">
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => commitViewerTab(tab.id)}
              className={`rounded-md px-4 py-2 text-sm font-medium transition ${
                viewerTab === tab.id
                  ? 'bg-navy-600 text-white shadow-sm'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {!loading && !selectedJob && completedJobs.length > 0 && (
          <div className="mb-4 rounded-lg border border-gray-200 bg-white p-4">
            <JobSelector
              jobs={jobs}
              selectedJobId={selectedJobId}
              onJobSelect={setSelectedJobId}
              label="Select a completed job"
            />
          </div>
        )}

        {job && (
          <div className="mb-4 flex flex-col gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="truncate text-base font-semibold text-gray-900">
                {subjectLabel || pipelineLabel}
              </p>
              <p className="mt-0.5 text-sm text-gray-500">
                {subjectLabel && (
                  <>
                    <span>{pipelineLabel}</span>
                    <span className="mx-1.5 text-gray-300">·</span>
                  </>
                )}
                <span className="font-mono text-gray-600">{jobShortId(job)}</span>
                {localVolume && (
                  <>
                    <span className="mx-1.5 text-gray-300">·</span>
                    <span className="text-navy-600">Local file: {localVolume.name}</span>
                  </>
                )}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <StatusBadge status={job.status} />
              {selectedJobId && (
                <Button variant="secondary" size="sm" onClick={handleExportAll}>
                  <Download className="w-4 h-4" />
                  Export
                </Button>
              )}
            </div>
          </div>
        )}

        <div className="flex min-h-[calc(100vh-14rem)] flex-1 overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
          {selectedJobId && job?.status === 'completed' && (
            <ViewerFileDrawer
              open={drawerOpen}
              onToggle={toggleDrawer}
              jobId={selectedJobId}
              onFileSelect={handleFileSelect}
              viewerFileMode={fileMode}
            />
          )}

          <div className="min-w-0 flex-1 overflow-y-auto p-4">
            {loading && (
              <div className="rounded-lg border border-gray-200 bg-white">
                <LoadingState message="Loading jobs…" />
              </div>
            )}

            {!loading && viewerTab === 'eeg' && (
              <EegViewerPanel jobId={selectedJobId} eegRelativePath={eegFileRelPath} />
            )}

            {!loading && viewerTab === 'imaging' && effectiveImageUrl && (
              <NiivueViewer
                imageUrl={effectiveImageUrl}
                segmentationUrl={localVolume ? undefined : segmentationUrl || undefined}
                pipelineName={job?.pipeline_name}
                imageName={localVolume?.name}
                onLoad={() => setViewerReady(true)}
                canvasHeightPx={canvasHeightPx}
              />
            )}

            {!loading && viewerTab === 'eeg-brain' && imageUrl && (
              <EegBrainFusionPanel
                jobId={selectedJobId}
                eegRelativePath={eegFileRelPath}
                imageUrl={imageUrl}
                segmentationUrl={segmentationUrl || undefined}
                pipelineName={job?.pipeline_name}
                onNiivueLoad={() => setViewerReady(true)}
              />
            )}

            {!loading && viewerTab === 'imaging' && !effectiveImageUrl && !error && (
              <div className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 bg-gray-50/80 p-12 text-center">
                <Brain className="mx-auto mb-4 h-16 w-16 text-gray-300" />
                <h3 className="mb-2 text-lg font-semibold text-gray-900">
                  {completedJobs.length === 0 ? 'No completed jobs yet' : 'Choose a volume to view'}
                </h3>
                <p className="mx-auto max-w-md text-sm text-gray-600">
                  {completedJobs.length === 0
                    ? 'Run a job first, then open its outputs here.'
                    : drawerOpen
                      ? 'Select a NIfTI or MGZ file from the list on the left.'
                      : 'Open the file list on the left, then pick a volume.'}
                </p>
                {completedJobs.length > 0 && selectedJobId && !drawerOpen && (
                  <Button className="mt-4" onClick={toggleDrawer}>
                    Show file list
                  </Button>
                )}
              </div>
            )}

            {!loading && viewerTab === 'eeg-brain' && !imageUrl && !error && (
              <div className="flex h-full min-h-[420px] flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 bg-gray-50/80 p-12 text-center">
                <Brain className="mx-auto mb-4 h-16 w-16 text-gray-300" />
                <h3 className="mb-2 text-lg font-semibold text-gray-900">Add a brain volume</h3>
                <p className="mb-4 text-sm text-gray-600">
                  Pick a NIfTI / MGZ volume from the file list on the left.
                </p>
                <EegViewerPanel jobId={selectedJobId} eegRelativePath={eegFileRelPath} compact />
              </div>
            )}

            {viewerReady && effectiveImageUrl && viewerTab === 'imaging' && (
              <p className="mt-3 text-center text-xs text-gray-400">
                L/R = patient orientation · Press{' '}
                <kbd className="rounded bg-gray-100 px-1">?</kbd> for shortcuts
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ViewerPage;
