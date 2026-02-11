/**
 * JobsPage Component
 * Adapted from NeuroInsight for NeuroInsight Research
 * 
 * Combines file upload/directory selection with job list
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { FileUpload } from '../components/FileUpload';
import { apiService } from '../services/api';
import type { Job } from '../types';
import Brain from '../components/icons/Brain';
import CheckCircle from '../components/icons/CheckCircle';
import XCircle from '../components/icons/XCircle';
import Clock from '../components/icons/Clock';
import Activity from '../components/icons/Activity';
import Trash2 from '../components/icons/Trash2';
import Eye from '../components/icons/Eye';
import JobProgressBar from '../components/JobProgressBar';
import SlurmQueueMonitor from '../components/SlurmQueueMonitor';

interface JobsPageProps {
  setActivePage: (page: string) => void;
  setSelectedJobId: (jobId: string) => void;
}

const JobsPage: React.FC<JobsPageProps> = ({ setActivePage, setSelectedJobId }) => {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [lastRefreshTime, setLastRefreshTime] = useState<Date | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [deletingJobs, setDeletingJobs] = useState<Set<string>>(new Set());
  const [stats, setStats] = useState({
    total: 0,
    completed: 0,
    running: 0,
    pending: 0,
    failed: 0,
  });

  // Fetch jobs
  const fetchJobs = async (showRefreshing = false) => {
    try {
      if (showRefreshing) setIsRefreshing(true);
      else setJobsLoading(true);

      const jobsData = await apiService.getJobs();
      setJobs(jobsData);
      setLastRefreshTime(new Date());
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
      setJobs([]);
    } finally {
      setJobsLoading(false);
      setIsRefreshing(false);
    }
  };

  // Calculate statistics
  useEffect(() => {
    const counts = jobs.reduce(
      (acc, job) => {
        acc.total += 1;
        if (job.status === 'completed') acc.completed += 1;
        if (job.status === 'running') acc.running += 1;
        if (job.status === 'pending') acc.pending += 1;
        if (job.status === 'failed') acc.failed += 1;
        return acc;
      },
      { total: 0, completed: 0, running: 0, pending: 0, failed: 0 }
    );
    setStats(counts);
  }, [jobs]);

  // -- Progress polling for active jobs (lightweight, 2.5s interval) ------
  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fullRefreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const pollProgress = useCallback(async () => {
    try {
      const progressData = await apiService.getJobsProgress();
      if (progressData.length === 0) return;

      setJobs(prev =>
        prev.map(job => {
          const update = progressData.find(p => p.id === job.id);
          if (update) {
            return {
              ...job,
              status: update.status as Job['status'],
              progress: update.progress,
              current_phase: update.current_phase,
            };
          }
          return job;
        })
      );
    } catch {
      // Silent — progress polling is best-effort
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchJobs();
  }, []);

  // Start/stop progress polling based on active jobs
  useEffect(() => {
    const hasActiveJobs = jobs.some(
      (j) => j.status === 'pending' || j.status === 'running'
    );

    // Fast progress poll (2.5s)
    if (hasActiveJobs && !progressTimerRef.current) {
      progressTimerRef.current = setInterval(pollProgress, 2500);
    } else if (!hasActiveJobs && progressTimerRef.current) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }

    // Slower full refresh (8s) to catch status transitions (running->completed)
    if (hasActiveJobs && !fullRefreshTimerRef.current) {
      fullRefreshTimerRef.current = setInterval(() => fetchJobs(true), 8000);
    } else if (!hasActiveJobs && fullRefreshTimerRef.current) {
      clearInterval(fullRefreshTimerRef.current);
      fullRefreshTimerRef.current = null;
    }

    return () => {
      if (progressTimerRef.current) clearInterval(progressTimerRef.current);
      if (fullRefreshTimerRef.current) clearInterval(fullRefreshTimerRef.current);
      progressTimerRef.current = null;
      fullRefreshTimerRef.current = null;
    };
  }, [jobs, pollProgress]);

  const handleJobsSubmitted = (jobIds: string[]) => {
    console.log(`Submitted ${jobIds.length} jobs`);
    fetchJobs();
  };

  const handleDeleteJob = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();

    if (deletingJobs.has(jobId)) return;

    if (!confirm('Delete this job? This action cannot be undone.')) {
      return;
    }

    setDeletingJobs((prev) => new Set(prev).add(jobId));

    try {
      await apiService.deleteJob(jobId);
      fetchJobs();
    } catch (error) {
      console.error('Failed to delete job:', error);
      alert('Failed to delete job.');
    } finally {
      setDeletingJobs((prev) => {
        const newSet = new Set(prev);
        newSet.delete(jobId);
        return newSet;
      });
    }
  };

  const handleViewJob = (jobId: string) => {
    setSelectedJobId(jobId);
    setActivePage('dashboard');
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'running':
        return <Activity className="w-5 h-5 text-[#003d7a] animate-pulse" />;
      case 'pending':
        return <Clock className="w-5 h-5 text-yellow-600" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-600" />;
      default:
        return <Clock className="w-5 h-5 text-gray-600" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-100';
      case 'running':
        return 'text-[#003d7a] bg-navy-100';
      case 'failed':
        return 'text-red-600 bg-red-100';
      case 'pending':
        return 'text-yellow-600 bg-yellow-100';
      case 'cancelled':
        return 'text-gray-600 bg-gray-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  const formatRuntime = (seconds?: number) => {
    if (!seconds) return 'N/A';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-navy-50 to-white">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Upload Section */}
        <div className="mb-8">
          <FileUpload
            onJobsSubmitted={handleJobsSubmitted}
            onBack={() => setActivePage('home')}
          />
        </div>

        {/* Statistics */}
        {stats.total > 0 && (
          <div className="mb-6 grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-gray-400">
              <div className="text-2xl font-bold text-gray-900">{stats.total}</div>
              <div className="text-sm text-gray-600">Total Jobs</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-yellow-400">
              <div className="text-2xl font-bold text-yellow-600">{stats.pending}</div>
              <div className="text-sm text-gray-600">Pending</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-[#003d7a]">
              <div className="text-2xl font-bold text-[#003d7a]">{stats.running}</div>
              <div className="text-sm text-gray-600">Running</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-400">
              <div className="text-2xl font-bold text-green-600">{stats.completed}</div>
              <div className="text-sm text-gray-600">Completed</div>
            </div>
            <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-400">
              <div className="text-2xl font-bold text-red-600">{stats.failed}</div>
              <div className="text-sm text-gray-600">Failed</div>
            </div>
          </div>
        )}

        {/* SLURM Queue Monitor (auto-detects if HPC backend is active) */}
        <div className="mb-6">
          <SlurmQueueMonitor visible={true} />
        </div>

        {/* Jobs List */}
        <div className="bg-white rounded-xl shadow-lg border border-navy-100">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Overview of All Processing Jobs</h2>
              <p className="text-sm text-gray-500 mt-1">
                {lastRefreshTime && `Last updated: ${formatDate(lastRefreshTime.toISOString())}`}
              </p>
              <p className="text-xs text-navy-600 mt-1">
                Click on a completed job to view detailed results in Dashboard
              </p>
            </div>
            <button
              onClick={() => fetchJobs(true)}
              disabled={isRefreshing}
              className="px-4 py-2 bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] disabled:opacity-50 text-sm font-medium"
            >
              {isRefreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          {jobsLoading ? (
            <div className="px-6 py-12 text-center">
              <div className="animate-spin h-8 w-8 border-4 border-navy-600 border-t-transparent rounded-full mx-auto"></div>
              <p className="text-gray-600 mt-4">Loading jobs...</p>
            </div>
          ) : jobs.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <Brain className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-600">No jobs yet. Process some data to get started!</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200 max-h-96 overflow-y-auto">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className="px-6 py-4 hover:bg-gray-50 transition cursor-pointer"
                  onClick={() => handleViewJob(job.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        {getStatusIcon(job.status)}
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-900">
                              {job.pipeline_name}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded bg-navy-50 text-[#003d7a] border border-navy-200">
                              {job.execution_mode === 'plugin' ? 'Plugin' : 'Workflow'}
                            </span>
                            <span
                              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(
                                job.status
                              )}`}
                            >
                              {job.status}
                            </span>
                          </div>
                          <div className="mt-1 flex items-center gap-4 text-xs text-gray-500">
                            <span>ID: {job.id.slice(0, 8)}</span>
                            <span>-</span>
                            <span>Backend: {job.backend_type}</span>
                            {!!job.runtime_seconds && (
                              <>
                                <span>-</span>
                                <span>Runtime: {formatRuntime(job.runtime_seconds)}</span>
                              </>
                            )}
                          </div>
                          <div className="mt-1 text-xs text-gray-500 truncate">
                            Input: {job.input_files[0] || 'N/A'}
                          </div>
                          <div className="text-xs text-gray-400 mt-1">
                            Submitted: {formatDate(job.submitted_at)}
                          </div>
                          {/* Progress bar — always shown for running/pending, shown at 100% for completed */}
                          {(job.status === 'running' || job.status === 'pending' || job.status === 'completed' || job.status === 'failed') && (
                            <JobProgressBar
                              progress={job.status === 'completed' ? 100 : (job.progress ?? 0)}
                              currentPhase={job.status === 'completed' ? 'Completed' : job.current_phase}
                              status={job.status}
                            />
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 ml-4">
                      {job.status === 'completed' && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleViewJob(job.id);
                          }}
                          className="p-2 text-navy-600 hover:bg-navy-50 rounded-md transition"
                          title="View results"
                        >
                          <Eye className="w-5 h-5" />
                        </button>
                      )}
                      
                      <button
                        onClick={(e) => handleDeleteJob(job.id, e)}
                        disabled={deletingJobs.has(job.id)}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition disabled:opacity-50"
                        title="Delete job"
                      >
                        {deletingJobs.has(job.id) ? (
                          <div className="animate-spin h-5 w-5 border-2 border-gray-400 border-t-transparent rounded-full"></div>
                        ) : (
                          <Trash2 className="w-5 h-5" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default JobsPage;
