/**
 * DashboardPage Component
 * Deep dive into ONE completed job at a time.
 * All data comes from real backend API calls -- no mock data.
 */

import { useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import { apiService } from '../services/api';
import type { Job } from '../types';
import JobSelector from '../components/JobSelector';
import FileBrowser from '../components/FileBrowser';
import StatsViewer from '../components/StatsViewer';
import QCImageGallery from '../components/QCImageGallery';
import BarChart from '../components/icons/BarChart';
import RefreshCw from '../components/icons/RefreshCw';
import Eye from '../components/icons/Eye';
import Download from '../components/icons/Download';
import type { ViewerTab } from '../utils/viewerQuery';
import { LoadingState, Spinner } from '../components/LoadingState';
import WorkspacePageHeader from '../components/WorkspacePageHeader';
import Button from '../components/Button';
import StatusBadge from '../components/StatusBadge';
import { deriveJobSubjectLabel, jobComputeLabel, jobPipelineLabel, jobShortId } from '../lib/jobLabels';
import PathLocationBar from '../components/PathLocationBar';
import { formatJobOutput, resolveJobOutputPath } from '../lib/jobPaths';

const VIEWER_TABS: ViewerTab[] = ['eeg', 'imaging', 'eeg-brain'];

interface DashboardPageProps {
  selectedJobId: string | null;
  setSelectedJobId: (jobId: string | null) => void;
  setActivePage: (page: string, opts?: { viewerTab?: ViewerTab }) => void;
}

interface Provenance {
  job_id: string;
  container_image: string | null;
  plugin_id: string | null;
  workflow_id: string | null;
  parameters: Record<string, unknown>;
  resources: Record<string, unknown>;
  input_hashes: Record<string, string>;
  execution: Record<string, unknown>;
  reproducibility_command: string;
  metadata_audit?: string;
  metadata_audit_path?: string;
}

const DashboardPage: React.FC<DashboardPageProps> = ({
  selectedJobId,
  setSelectedJobId,
  setActivePage,
}) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [provenance, setProvenance] = useState<Provenance | null>(null);
  const [provenanceLoading, setProvenanceLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [activeTab, setActiveTab] = useState<'stats' | 'files' | 'qc'>('stats');
  const [provenanceOpen, setProvenanceOpen] = useState(false);
  const [pathContext, setPathContext] = useState<{
    dataDir: string;
    hostDataDir: string | null;
    homeDir: string | null;
  }>({ dataDir: './data', hostDataDir: null, homeDir: null });

  useEffect(() => {
    fetchJobs();
    apiService
      .getBrowseRoot()
      .then(({ data_dir, host_data_dir, local_root }) => {
        setPathContext({
          dataDir: data_dir,
          hostDataDir: host_data_dir ?? null,
          homeDir: local_root ?? null,
        });
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (selectedJobId) {
      const job = jobs.find((j) => j.id === selectedJobId);
      setSelectedJob(job || null);
    } else {
      setSelectedJob(null);
    }
    setProvenance(null);
    setProvenanceOpen(false);
  }, [selectedJobId, jobs]);

  useEffect(() => {
    if (!selectedJobId || !provenanceOpen) return;
    fetchProvenance(selectedJobId);
  }, [selectedJobId, provenanceOpen]);

  const fetchJobs = async () => {
    setLoading(true);
    setError(null);
    try {
      const jobsData = await apiService.getJobs();
      setJobs(jobsData);
      // Auto-select first completed job if none selected
      if (!selectedJobId) {
        const firstCompleted = jobsData.find((j: Job) => j.status === 'completed');
        if (firstCompleted) {
          setSelectedJobId(firstCompleted.id);
        }
      }
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
      setError('Could not connect to backend. Make sure the app is running.');
    } finally {
      setLoading(false);
    }
  };

  const fetchProvenance = async (jobId: string) => {
    setProvenanceLoading(true);
    try {
      const data = await apiService.getJobProvenance(jobId);
      setProvenance(data);
    } catch {
      setProvenance(null);
    } finally {
      setProvenanceLoading(false);
    }
  };

  const handleExportBundle = () => {
    if (!selectedJob) return;
    setExporting(true);
    const url = apiService.exportJobResultsUrl(selectedJob.id);
    window.open(url, '_blank');
    // Reset exporting after a brief delay (download starts in new tab)
    setTimeout(() => setExporting(false), 2000);
  };

  const handleViewInViewer = () => {
    if (!selectedJobId || !selectedJob) return;
    const hint = selectedJob.parameters?._sample_viewer_tab as string | undefined;
    const tab =
      hint && VIEWER_TABS.includes(hint as ViewerTab) ? (hint as ViewerTab) : 'imaging';
    setActivePage('viewer', { viewerTab: tab });
  };

  const completedJobs = jobs.filter(j => j.status === 'completed');

  const getJobDuration = (job: Job) => {
    if (job.submitted_at && job.completed_at) {
      const ms = new Date(job.completed_at).getTime() - new Date(job.submitted_at).getTime();
      const mins = Math.floor(ms / 60000);
      const secs = Math.floor((ms % 60000) / 1000);
      return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
    }
    return 'N/A';
  };

  return (
    <div className="min-h-full bg-gray-50">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        <WorkspacePageHeader
          title="Results"
          subtitle={
            selectedJob
              ? undefined
              : 'Review statistics, output files, and QC for completed jobs.'
          }
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

        {/* Error state */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-sm text-red-800">{error}</p>
            <button
              onClick={fetchJobs}
              className="mt-2 text-sm text-red-700 underline hover:no-underline"
            >
              Try again
            </button>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className="bg-white rounded-lg border border-gray-200">
            <LoadingState message="Loading jobs…" />
          </div>
        )}

        {/* Job Selector — only when nothing selected and header selector is not enough */}
        {!loading && jobs.length > 0 && !selectedJobId && completedJobs.length > 0 && (
          <div className="mb-6 rounded-lg border border-gray-200 bg-white p-4">
            <JobSelector
              jobs={jobs}
              selectedJobId={selectedJobId}
              onJobSelect={setSelectedJobId}
              label="Select a completed job"
            />
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && completedJobs.length === 0 && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-12 text-center">
            <BarChart className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              No Completed Jobs Yet
            </h3>
            <p className="text-gray-600 mb-6">Run a job to see results here.</p>
            <Button onClick={() => setActivePage('jobs')}>Go to Jobs</Button>
          </div>
        )}

        {/* Job Details */}
        {selectedJob && (
          <div className="space-y-6">
            {/* Job summary */}
            <div className="rounded-xl border border-gray-200 bg-white p-5 sm:p-6">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 flex-1">
                  {(() => {
                    const subject = selectedJob.is_sample_job
                      ? 'Sample EEG demo'
                      : deriveJobSubjectLabel(selectedJob);
                    const pipeline = jobPipelineLabel(selectedJob);
                    return (
                      <>
                        <h2 className="text-xl font-bold tracking-tight text-gray-900 sm:text-2xl">
                          {subject || pipeline}
                        </h2>
                        {subject && (
                          <p className="mt-0.5 text-base text-gray-600">{pipeline}</p>
                        )}
                      </>
                    );
                  })()}
                  <p className="mt-2 text-sm text-gray-500">
                    <span className="font-mono text-gray-700">{jobShortId(selectedJob)}</span>
                    {' · '}
                    {jobComputeLabel(selectedJob)}
                    {' · '}
                    {getJobDuration(selectedJob)}
                    {' · '}
                    {new Date(selectedJob.submitted_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                    {selectedJob.is_sample_job && (
                      <>
                        {' · '}
                        <span className="font-medium text-emerald-700">Sample</span>
                      </>
                    )}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <StatusBadge status={selectedJob.status} />
                  {selectedJob.status === 'completed' && (
                    <>
                      <Button variant="secondary" onClick={handleExportBundle} disabled={exporting}>
                        {exporting ? <Spinner size="sm" /> : <Download className="w-4 h-4" />}
                        Export
                      </Button>
                      <Button onClick={handleViewInViewer}>
                        <Eye className="w-4 h-4" />
                        Open in Viewer
                      </Button>
                    </>
                  )}
                </div>
              </div>
              {selectedJob.output_dir && (
                <PathLocationBar
                  compact
                  className="mt-4"
                  label="Output"
                  pathKind="output"
                  job={selectedJob}
                  homeDir={pathContext.homeDir}
                  hostPath={resolveJobOutputPath(selectedJob, {
                    containerDataDir: pathContext.dataDir,
                    hostDataDir: pathContext.hostDataDir,
                  })}
                  displayPath={formatJobOutput(selectedJob, {
                    containerDataDir: pathContext.dataDir,
                    hostDataDir: pathContext.hostDataDir,
                    homeDir: pathContext.homeDir,
                  })}
                  onNavigateToTransfer={() => setActivePage('transfer')}
                />
              )}
            </div>

            {/* Primary results tabs */}
            {selectedJob.status === 'completed' && (
              <>
              <div className="rounded-xl border border-gray-200 bg-white">
                <div className="border-b border-gray-200">
                  <nav className="flex -mb-px overflow-x-auto">
                    {(['stats', 'files', 'qc'] as const).map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`whitespace-nowrap px-5 py-3 text-sm font-medium border-b-2 transition ${
                          activeTab === tab
                            ? 'border-navy-600 text-navy-600'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                        }`}
                      >
                        {tab === 'stats' && 'Statistics'}
                        {tab === 'files' && 'Output Files'}
                        {tab === 'qc' && 'QC Images'}
                      </button>
                    ))}
                  </nav>
                </div>

                <div>
                  {activeTab === 'stats' && (
                    <div className="p-4">
                      <StatsViewer jobId={selectedJob.id} pipelineName={selectedJob.pipeline_name} />
                    </div>
                  )}

                  {activeTab === 'files' && (
                    <FileBrowser
                      jobId={selectedJob.id}
                      showDownload={true}
                      showViewButton={false}
                    />
                  )}

                  {activeTab === 'qc' && (
                    <QCImageGallery jobId={selectedJob.id} />
                  )}
                </div>
              </div>

              {/* Provenance — collapsed by default, loaded on expand */}
              <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
                <button
                  type="button"
                  onClick={() => setProvenanceOpen((open) => !open)}
                  className="flex w-full items-center justify-between gap-3 px-5 py-3.5 text-left hover:bg-gray-50/80 transition"
                  aria-expanded={provenanceOpen}
                >
                  <span className="text-sm font-semibold text-gray-800">
                    Reproducibility &amp; provenance
                  </span>
                  <ChevronDown
                    className={`h-4 w-4 shrink-0 text-gray-400 transition-transform ${provenanceOpen ? 'rotate-180' : ''}`}
                  />
                </button>

                {provenanceOpen && (
                  <div className="border-t border-gray-100 px-5 py-4 space-y-4">
                    {provenanceLoading ? (
                      <div className="flex items-center gap-3 py-2">
                        <Spinner size="md" className="text-navy-600" />
                        <span className="text-sm text-gray-600">Loading provenance…</span>
                      </div>
                    ) : provenance ? (
                      <>
                        <div>
                          <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1.5">
                            Container image
                          </h4>
                          <code className="block text-sm bg-gray-100 px-3 py-1.5 rounded font-mono break-all">
                            {provenance.container_image || 'N/A'}
                          </code>
                        </div>

                        {provenance.reproducibility_command && (
                          <div>
                            <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1.5">
                              Reproduce command
                            </h4>
                            <pre className="text-xs bg-gray-900 text-green-400 rounded p-3 overflow-x-auto font-mono nir-scroll-list">
                              {provenance.reproducibility_command}
                            </pre>
                          </div>
                        )}

                        {provenance.input_hashes && Object.keys(provenance.input_hashes).length > 0 && (
                          <details className="group rounded-lg border border-gray-200 bg-gray-50/50">
                            <summary className="cursor-pointer list-none px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg [&::-webkit-details-marker]:hidden">
                              Input file hashes ({Object.keys(provenance.input_hashes).length})
                            </summary>
                            <div className="border-t border-gray-200 px-3 py-2 space-y-1 nir-scroll-list">
                              {Object.entries(provenance.input_hashes).map(([file, hash]) => (
                                <div key={file} className="text-xs font-mono break-all">
                                  <span className="text-gray-600">{file}:</span>{' '}
                                  <span className="text-gray-900">{hash}</span>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}

                        {provenance.parameters && Object.keys(provenance.parameters).length > 0 && (
                          <details className="group rounded-lg border border-gray-200 bg-gray-50/50">
                            <summary className="cursor-pointer list-none px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg [&::-webkit-details-marker]:hidden">
                              Parameters
                            </summary>
                            <pre className="border-t border-gray-200 px-3 py-2 text-xs overflow-x-auto font-mono nir-scroll-list">
                              {JSON.stringify(provenance.parameters, null, 2)}
                            </pre>
                          </details>
                        )}

                        {provenance.metadata_audit && (
                          <details className="group rounded-lg border border-gray-200 bg-gray-50/50">
                            <summary className="cursor-pointer list-none px-3 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 rounded-lg [&::-webkit-details-marker]:hidden">
                              Metadata audit
                              {provenance.metadata_audit_path
                                ? ` (${provenance.metadata_audit_path})`
                                : ''}
                            </summary>
                            <pre className="border-t border-gray-200 px-3 py-2 text-xs overflow-x-auto font-mono nir-scroll-list">
                              {provenance.metadata_audit}
                            </pre>
                          </details>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-gray-500 py-1">No provenance data available for this job.</p>
                    )}
                  </div>
                )}
              </div>
              </>
            )}

            {/* Running / pending / failed (show backend error_message when failed) */}
            {selectedJob.status !== 'completed' && (
              <div
                className={
                  selectedJob.status === 'failed'
                    ? 'bg-red-50 border border-red-200 rounded-lg p-6 text-left'
                    : 'bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center'
                }
              >
                {selectedJob.status === 'running' && (
                  <p className="text-sm text-yellow-800">
                    This job is still running. Results will appear when processing completes.
                  </p>
                )}
                {selectedJob.status === 'pending' && (
                  <p className="text-sm text-yellow-800">
                    This job is pending. Results will be available after processing.
                  </p>
                )}
                {selectedJob.status === 'failed' && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-red-900">This job failed</p>
                    {selectedJob.error_message ? (
                      <pre className="text-xs text-red-900 whitespace-pre-wrap break-words font-mono bg-white/60 rounded p-3 border border-red-200 nir-scroll-list">
                        {selectedJob.error_message}
                      </pre>
                    ) : (
                      <p className="text-sm text-red-800">
                        No error details were recorded. Use the API or backend logs for this job if you need more context.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardPage;
