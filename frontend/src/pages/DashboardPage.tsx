/**
 * DashboardPage Component
 * Deep dive into ONE completed job at a time.
 * All data comes from real backend API calls -- no mock data.
 */

import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import type { Job } from '../types';
import JobSelector from '../components/JobSelector';
import FileBrowser from '../components/FileBrowser';
import StatsViewer from '../components/StatsViewer';
import BarChart from '../components/icons/BarChart';
import RefreshCw from '../components/icons/RefreshCw';
import Eye from '../components/icons/Eye';
import Activity from '../components/icons/Activity';
import Download from '../components/icons/Download';

interface DashboardPageProps {
  selectedJobId: string | null;
  setSelectedJobId: (jobId: string | null) => void;
  setActivePage: (page: string) => void;
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
  const [activeTab, setActiveTab] = useState<'files' | 'stats' | 'provenance'>('files');

  useEffect(() => {
    fetchJobs();
  }, []);

  useEffect(() => {
    if (selectedJobId) {
      const job = jobs.find(j => j.id === selectedJobId);
      setSelectedJob(job || null);
      if (job) {
        fetchProvenance(job.id);
      }
    } else {
      setSelectedJob(null);
      setProvenance(null);
    }
  }, [selectedJobId, jobs]);

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
    if (selectedJobId) {
      setActivePage('viewer');
    }
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
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <BarChart className="w-8 h-8 text-[#003d7a]" />
              <h1 className="text-3xl font-bold text-gray-900">Job Dashboard</h1>
            </div>
            <p className="text-gray-600">
              Detailed view of completed job results, files, and statistics
            </p>
          </div>
          <button
            onClick={fetchJobs}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

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
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <Activity className="w-8 h-8 text-[#003d7a] animate-spin mx-auto mb-3" />
            <p className="text-gray-600">Loading jobs...</p>
          </div>
        )}

        {/* Job Selector */}
        {!loading && jobs.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
            <JobSelector
              jobs={jobs}
              selectedJobId={selectedJobId}
              onJobSelect={setSelectedJobId}
              label="Select a Completed Job"
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
            <p className="text-gray-600 mb-6">
              Submit and complete a processing job to view detailed results here
            </p>
            <button
              onClick={() => setActivePage('jobs')}
              className="px-6 py-2 bg-[#003d7a] text-white rounded-lg hover:bg-[#002b55] transition"
            >
              Go to Jobs
            </button>
          </div>
        )}

        {/* Job Details */}
        {selectedJob && (
          <div className="space-y-6">
            {/* Job Info Card */}
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-1">
                    {selectedJob.pipeline_name}
                  </h2>
                  <p className="text-gray-600">
                    Job ID: {selectedJob.id} &middot;{' '}
                    {selectedJob.execution_mode === 'plugin' ? 'Plugin' : 'Workflow'} Execution
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`px-4 py-2 rounded-full text-sm font-medium ${
                    selectedJob.status === 'completed' ? 'bg-green-100 text-green-800' :
                    selectedJob.status === 'running' ? 'bg-navy-100 text-navy-800' :
                    selectedJob.status === 'failed' ? 'bg-red-100 text-red-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {selectedJob.status.charAt(0).toUpperCase() + selectedJob.status.slice(1)}
                  </span>
                  {selectedJob.status === 'completed' && (
                    <>
                      <button
                        onClick={handleExportBundle}
                        disabled={exporting}
                        className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition disabled:opacity-50"
                      >
                        {exporting ? <Activity className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                        Export Bundle
                      </button>
                      <button
                        onClick={handleViewInViewer}
                        className="flex items-center gap-2 px-4 py-2 bg-[#003d7a] text-white rounded-lg hover:bg-[#002b55] transition"
                      >
                        <Eye className="w-4 h-4" />
                        Open in Viewer
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* QC Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Status</p>
                <p className={`text-lg font-bold ${
                  selectedJob.status === 'completed' ? 'text-green-700' :
                  selectedJob.status === 'failed' ? 'text-red-700' : 'text-gray-900'
                }`}>
                  {selectedJob.status.charAt(0).toUpperCase() + selectedJob.status.slice(1)}
                </p>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Duration</p>
                <p className="text-lg font-bold text-gray-900">{getJobDuration(selectedJob)}</p>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Submitted</p>
                <p className="text-lg font-bold text-gray-900">
                  {new Date(selectedJob.submitted_at).toLocaleDateString()}
                </p>
                <p className="text-xs text-gray-500">
                  {new Date(selectedJob.submitted_at).toLocaleTimeString()}
                </p>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Pipeline</p>
                <p className="text-lg font-bold text-[#003d7a] truncate">{selectedJob.pipeline_name}</p>
              </div>
            </div>

            {/* Tab Navigation */}
            {selectedJob.status === 'completed' && (
              <div className="bg-white rounded-lg border border-gray-200">
                <div className="border-b border-gray-200">
                  <nav className="flex -mb-px">
                    {(['files', 'stats', 'provenance'] as const).map(tab => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={`px-6 py-3 text-sm font-medium border-b-2 transition ${
                          activeTab === tab
                            ? 'border-[#003d7a] text-[#003d7a]'
                            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                        }`}
                      >
                        {tab === 'files' && 'Output Files'}
                        {tab === 'stats' && 'Statistics'}
                        {tab === 'provenance' && 'Provenance'}
                      </button>
                    ))}
                  </nav>
                </div>

                <div>
                  {activeTab === 'files' && (
                    <FileBrowser
                      jobId={selectedJob.id}
                      showDownload={true}
                      showViewButton={false}
                    />
                  )}

                  {activeTab === 'stats' && (
                    <div className="p-4">
                      <StatsViewer jobId={selectedJob.id} pipelineName={selectedJob.pipeline_name} />
                    </div>
                  )}

                  {activeTab === 'provenance' && (
                    <div className="p-6">
                      {provenanceLoading ? (
                        <div className="flex items-center gap-3">
                          <Activity className="w-5 h-5 text-[#003d7a] animate-spin" />
                          <span className="text-gray-600">Loading provenance...</span>
                        </div>
                      ) : provenance ? (
                        <div className="space-y-4">
                          <div>
                            <h4 className="text-sm font-semibold text-gray-700 mb-2">Container Image</h4>
                            <code className="text-sm bg-gray-100 px-3 py-1.5 rounded font-mono">
                              {provenance.container_image || 'N/A'}
                            </code>
                          </div>
                          {provenance.input_hashes && Object.keys(provenance.input_hashes).length > 0 && (
                            <div>
                              <h4 className="text-sm font-semibold text-gray-700 mb-2">Input File Hashes (SHA-256)</h4>
                              <div className="bg-gray-50 rounded p-3 space-y-1">
                                {Object.entries(provenance.input_hashes).map(([file, hash]) => (
                                  <div key={file} className="text-xs font-mono">
                                    <span className="text-gray-600">{file}:</span>{' '}
                                    <span className="text-gray-900">{hash}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                          {provenance.parameters && Object.keys(provenance.parameters).length > 0 && (
                            <div>
                              <h4 className="text-sm font-semibold text-gray-700 mb-2">Parameters</h4>
                              <pre className="text-xs bg-gray-50 rounded p-3 overflow-x-auto font-mono">
                                {JSON.stringify(provenance.parameters, null, 2)}
                              </pre>
                            </div>
                          )}
                          {provenance.reproducibility_command && (
                            <div>
                              <h4 className="text-sm font-semibold text-gray-700 mb-2">Reproduce Command</h4>
                              <pre className="text-xs bg-gray-900 text-green-400 rounded p-3 overflow-x-auto font-mono">
                                {provenance.reproducibility_command}
                              </pre>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-sm text-gray-500">No provenance data available for this job.</p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Running/Failed job message */}
            {selectedJob.status !== 'completed' && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6 text-center">
                <p className="text-sm text-yellow-800">
                  {selectedJob.status === 'running' && 'This job is still running. Results will appear when processing completes.'}
                  {selectedJob.status === 'pending' && 'This job is pending. Results will be available after processing.'}
                  {selectedJob.status === 'failed' && 'This job failed. Check the job logs for details.'}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardPage;
