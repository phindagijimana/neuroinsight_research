/**
 * DashboardPage Component
 * Deep dive into ONE completed job at a time
 * - Job selector
 * - QC summary cards with real metrics
 * - Provenance & reproducibility info
 * - Export bundle download
 * - File browser with downloads
 * - Statistics viewer (CSV format)
 */

import { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { getMockJobs } from '../data/mockJobs';
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
  container_image: string;
  parameters: Record<string, unknown>;
  input_hashes: Record<string, string>;
  reproduce_command?: string;
}

const DashboardPage: React.FC<DashboardPageProps> = ({
  selectedJobId,
  setSelectedJobId,
  setActivePage
}) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(true);
  const [useMockData, setUseMockData] = useState(true);
  const [provenance, setProvenance] = useState<Provenance | null>(null);
  const [provenanceLoading, setProvenanceLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [activeTab, setActiveTab] = useState<'files' | 'stats' | 'provenance'>('files');

  useEffect(() => {
    fetchJobs();
  }, [useMockData]);

  useEffect(() => {
    if (selectedJobId) {
      const job = jobs.find(j => j.id === selectedJobId);
      setSelectedJob(job || null);
      if (job && !useMockData) {
        fetchProvenance(job.id);
      } else {
        setProvenance(null);
      }
    } else {
      setSelectedJob(null);
      setProvenance(null);
    }
  }, [selectedJobId, jobs]);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      let jobsData;
      if (useMockData) {
        jobsData = await getMockJobs();
      } else {
        jobsData = await apiService.getJobs();
      }
      setJobs(jobsData);

      // Auto-select first completed job if none selected
      if (!selectedJobId) {
        const firstCompleted = jobsData.find((j: Job) => j.status === 'completed');
        if (firstCompleted) {
          setSelectedJobId(firstCompleted.id);
        }
      }
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
      if (!useMockData) {
        setUseMockData(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchProvenance = async (jobId: string) => {
    setProvenanceLoading(true);
    try {
      const baseUrl = apiService.getBaseUrl ? apiService.getBaseUrl() : 'http://localhost:3001';
      const resp = await fetch(`${baseUrl}/api/results/${jobId}/provenance`);
      if (resp.ok) {
        setProvenance(await resp.json());
      }
    } catch {
      setProvenance(null);
    } finally {
      setProvenanceLoading(false);
    }
  };

  const handleExportBundle = async () => {
    if (!selectedJob) return;
    setExporting(true);
    try {
      const baseUrl = apiService.getBaseUrl ? apiService.getBaseUrl() : 'http://localhost:3001';
      const resp = await fetch(`${baseUrl}/api/results/${selectedJob.id}/export`);
      if (resp.ok) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${selectedJob.id}_results.tar.gz`;
        a.click();
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setExporting(false);
    }
  };

  const handleViewInViewer = () => {
    if (selectedJobId) {
      setActivePage('viewer');
    }
  };

  const completedJobs = jobs.filter(j => j.status === 'completed');

  // Compute QC summary metrics from selectedJob
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
              {useMockData && (
                <span className="px-3 py-1 bg-navy-100 text-navy-800 text-sm font-medium rounded-full">
                  Demo Data
                </span>
              )}
            </div>
            <p className="text-gray-600">
              Detailed view of completed job results, files, and statistics
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={useMockData}
                onChange={(e) => setUseMockData(e.target.checked)}
                className="w-4 h-4 text-[#003d7a] rounded focus:ring-[#003d7a]"
              />
              Use Sample Data
            </label>
            <button
              onClick={fetchJobs}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh
            </button>
          </div>
        </div>

        {/* Job Selector */}
        {!loading && (
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
        {!loading && completedJobs.length === 0 && (
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
                    Job ID: {selectedJob.id} &middot; {selectedJob.execution_mode === 'plugin' ? 'Plugin' : 'Workflow'} Execution
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="px-4 py-2 rounded-full text-sm font-medium bg-green-100 text-green-800">
                    Completed
                  </span>
                  <button
                    onClick={handleExportBundle}
                    disabled={exporting || useMockData}
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
                </div>
              </div>
            </div>

            {/* QC Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Status</p>
                <p className="text-lg font-bold text-green-700">Completed</p>
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
            <div className="bg-white rounded-lg border border-gray-200">
              <div className="border-b border-gray-200">
                <nav className="flex -mb-px">
                  {(['files', 'stats', 'provenance'] as const).map((tab) => (
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

              <div className="p-0">
                {/* File Browser */}
                {activeTab === 'files' && (
                  <FileBrowser
                    jobId={selectedJob.id}
                    onFileSelect={(path) => console.log('Selected:', path)}
                    showDownload={true}
                    showViewButton={false}
                  />
                )}

                {/* Statistics Viewer */}
                {activeTab === 'stats' && (
                  <StatsViewer jobId={selectedJob.id} pipelineName={selectedJob.pipeline_name} />
                )}

                {/* Provenance */}
                {activeTab === 'provenance' && (
                  <div className="p-6">
                    {useMockData ? (
                      <p className="text-sm text-gray-500">
                        Provenance data is available for real jobs only. Switch off "Use Sample Data" to see provenance info.
                      </p>
                    ) : provenanceLoading ? (
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
                        {provenance.reproduce_command && (
                          <div>
                            <h4 className="text-sm font-semibold text-gray-700 mb-2">Reproduce Command</h4>
                            <pre className="text-xs bg-gray-900 text-green-400 rounded p-3 overflow-x-auto font-mono">
                              {provenance.reproduce_command}
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
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardPage;
