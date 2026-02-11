/**
 * DashboardPage Component
 * Deep dive into ONE completed job at a time
 * - Job selector
 * - File browser with downloads
 * - Statistics viewer (CSV format)
 * - 3D image thumbnail preview
 */

import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { getMockJobs } from '../data/mockJobs';
import type { Job } from '../types';
import JobSelector from '../components/JobSelector';
import FileBrowser from '../components/FileBrowser';
import StatsViewer from '../components/StatsViewer';
import BarChart from '../components/icons/BarChart';
import Brain from '../components/icons/Brain';
import RefreshCw from '../components/icons/RefreshCw';
import Eye from '../components/icons/Eye';

interface DashboardPageProps {
  selectedJobId: string | null;
  setSelectedJobId: (jobId: string | null) => void;
  setActivePage: (page: string) => void;
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

  useEffect(() => {
    fetchJobs();
  }, [useMockData]);

  useEffect(() => {
    if (selectedJobId) {
      const job = jobs.find(j => j.id === selectedJobId);
      setSelectedJob(job || null);
    } else {
      setSelectedJob(null);
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
        const firstCompleted = jobsData.find(j => j.status === 'completed');
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

  const handleViewInViewer = () => {
    if (selectedJobId) {
      setActivePage('viewer');
    }
  };

  const completedJobs = jobs.filter(j => j.status === 'completed');

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
                    Job ID: {selectedJob.id} · {selectedJob.execution_mode === 'plugin' ? 'Plugin' : 'Workflow'} Execution
                  </p>
                  <div className="mt-2 text-sm text-gray-600 space-y-1">
                    <div>Submitted: {new Date(selectedJob.submitted_at).toLocaleString()}</div>
                    {selectedJob.completed_at && (
                      <div>Completed: {new Date(selectedJob.completed_at).toLocaleString()}</div>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className="px-4 py-2 rounded-full text-sm font-medium bg-green-100 text-green-800">
                    Completed
                  </span>
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

            {/* File Browser - Full Width */}
            <FileBrowser
              jobId={selectedJob.id}
              onFileSelect={(path) => console.log('Selected:', path)}
              showDownload={true}
              showViewButton={false}
            />

            {/* Statistics Viewer - Full Width */}
            <StatsViewer jobId={selectedJob.id} pipelineName={selectedJob.pipeline_name} />
          </div>
        )}
      </div>
    </div>
  );
};

export default DashboardPage;
