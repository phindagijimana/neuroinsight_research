/**
 * JobsPage Component
 * Adapted from NeuroInsight for NeuroInsight Research
 * 
 * Combines file upload/directory selection with job list
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
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
import StatusBadge from '../components/StatusBadge';
import { LoadingState } from '../components/LoadingState';
import type { ViewerTab } from '../utils/viewerQuery';
import { useFeatureFlags } from '../contexts/FeatureFlagsContext';
import { useToast, useConfirm } from '../contexts/NotificationContext';

const SAMPLE_VIEWER_TABS: ViewerTab[] = ['eeg', 'imaging', 'eeg-brain'];

interface JobsPageProps {
  setActivePage: (page: string, opts?: { viewerTab?: ViewerTab }) => void;
  setSelectedJobId: (jobId: string) => void;
}

const JobsPage: React.FC<JobsPageProps> = ({ setActivePage, setSelectedJobId }) => {
  const { eegEnabled } = useFeatureFlags();
  const toast = useToast();
  const confirm = useConfirm();
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

  // -- Progress polling for active jobs ------
  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fullRefreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const progressInFlightRef = useRef(false);

  const pollProgress = useCallback(async () => {
    if (progressInFlightRef.current) return;
    progressInFlightRef.current = true;
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
      // Silent -- progress polling is best-effort
    } finally {
      progressInFlightRef.current = false;
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

    // Progress poll every 15s (SSH-based, can be slow)
    if (hasActiveJobs && !progressTimerRef.current) {
      progressTimerRef.current = setInterval(pollProgress, 15000);
    } else if (!hasActiveJobs && progressTimerRef.current) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }

    // Slower full refresh (30s) to catch status transitions
    if (hasActiveJobs && !fullRefreshTimerRef.current) {
      fullRefreshTimerRef.current = setInterval(() => fetchJobs(true), 30000);
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

  const handleJobsSubmitted = (_jobIds: string[]) => {
    fetchJobs();
  };

  const handleDeleteJob = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();

    if (deletingJobs.has(jobId)) return;

    const ok = await confirm({
      title: 'Delete job',
      message: 'Delete this job? This action cannot be undone.',
      confirmLabel: 'Delete',
      danger: true,
    });
    if (!ok) return;

    setDeletingJobs((prev) => new Set(prev).add(jobId));

    try {
      await apiService.deleteJob(jobId);
      toast.success('Job deleted.');
      fetchJobs();
    } catch (error) {
      console.error('Failed to delete job:', error);
      toast.error('Could not delete the job. Please try again.');
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

  const openSampleInViewer = (job: Job, e: React.MouseEvent) => {
    e.stopPropagation();
    const hint = job.parameters?._sample_viewer_tab as string | undefined;
    const tab =
      hint && SAMPLE_VIEWER_TABS.includes(hint as ViewerTab)
        ? (hint as ViewerTab)
        : 'imaging';
    setSelectedJobId(job.id);
    setActivePage('viewer', { viewerTab: tab });
  };

  const sortedJobs = useMemo(() => {
    return [...jobs].sort((a, b) => {
      const as = a.is_sample_job ? 1 : 0;
      const bs = b.is_sample_job ? 1 : 0;
      return bs - as;
    });
  }, [jobs]);

  // Sample jobs are EEG demos — only surface them when the EEG feature is on.
  const hasSampleJobs = useMemo(
    () => eegEnabled && jobs.some((j) => j.is_sample_job),
    [jobs, eegEnabled]
  );

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'running':
        return <Activity className="w-5 h-5 text-[#003d7a] animate-pulse" />;
      case 'pending':
        return <Clock className="w-5 h-5 text-navy-400" />;
      case 'failed':
        return <XCircle className="w-5 h-5 text-red-600" />;
      default:
        return <Clock className="w-5 h-5 text-navy-300" />;
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
    <div className="min-h-screen bg-gradient-to-b from-slate-50/90 to-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 md:py-8">
        {/* Submit jobs — single surface above metrics */}
        <div className="relative z-10 mb-6 md:mb-8">
          <FileUpload
            onJobsSubmitted={handleJobsSubmitted}
            onBack={() => setActivePage('home')}
          />
        </div>

        {/* Statistics — one quiet strip */}
        {stats.total > 0 && (
          <div className="mb-6 rounded-2xl border border-gray-200/90 bg-white/90 px-4 py-3.5 shadow-sm backdrop-blur-sm sm:px-6">
            <div className="flex flex-wrap items-center justify-between gap-3 sm:gap-6">
              {[
                { label: 'Total', value: stats.total, valueClass: 'text-gray-900' },
                { label: 'Pending', value: stats.pending, valueClass: 'text-slate-600' },
                { label: 'Running', value: stats.running, valueClass: 'text-[#003d7a]' },
                { label: 'Completed', value: stats.completed, valueClass: 'text-emerald-700' },
                { label: 'Failed', value: stats.failed, valueClass: 'text-red-600' },
              ].map((s) => (
                <div key={s.label} className="flex min-w-[4.5rem] items-baseline gap-2">
                  <span className={`text-lg font-semibold tabular-nums ${s.valueClass}`}>{s.value}</span>
                  <span className="text-xs font-medium tracking-wide text-gray-400">{s.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* SLURM Queue Monitor (auto-detects if HPC backend is active) */}
        <div className="mb-6">
          <SlurmQueueMonitor visible={true} />
        </div>

        {hasSampleJobs && (
          <div className="mb-6 rounded-xl border border-emerald-100/80 bg-emerald-50/50 px-4 py-3 sm:px-5 sm:py-3.5">
            <h3 className="text-xs font-semibold tracking-wide text-emerald-800/90">Sample EEG demos</h3>
            <p className="text-sm text-emerald-900/85 mt-1 leading-relaxed">
              Synthetic data jobs below open the Viewer: <span className="font-medium">EEG preprocessing</span> → Signal View;{' '}
              <span className="font-medium">EEG source localization</span> → Multimodal View.
            </p>
          </div>
        )}

        {/* Jobs List */}
        <div className="rounded-2xl border border-gray-200/90 bg-white shadow-sm">
          <div className="px-4 sm:px-6 py-4 border-b border-gray-100 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 tracking-tight">Jobs</h2>
              <p className="text-sm text-gray-500 mt-0.5">
                {lastRefreshTime ? (
                  <>Updated {formatDate(lastRefreshTime.toISOString())} · completed jobs open in Results</>
                ) : (
                  'Completed jobs open in Results'
                )}
              </p>
            </div>
            <button
              onClick={() => fetchJobs(true)}
              disabled={isRefreshing}
              className="shrink-0 px-4 py-2 rounded-lg bg-[#003d7a] text-white text-sm font-medium hover:bg-[#002b55] disabled:opacity-50 transition-colors"
            >
              {isRefreshing ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>

          {jobsLoading ? (
            <LoadingState message="Loading jobs…" />
          ) : jobs.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <Brain className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-600">No jobs yet — submit a job to see it here.</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
              {sortedJobs.map((job) => (
                <div
                  key={job.id}
                  className="px-4 sm:px-6 py-3.5 hover:bg-slate-50/80 transition cursor-pointer"
                  onClick={() => handleViewJob(job.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-2">
                        {getStatusIcon(job.status)}
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-gray-900">
                              {job.display_name || job.pipeline_name}
                            </span>
                            {job.is_sample_job && (
                              <span className="text-xs px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
                                Sample
                              </span>
                            )}
                            <span className="text-xs px-2 py-0.5 rounded bg-navy-50 text-[#003d7a] border border-navy-200">
                              {job.execution_mode === 'workflow' ? 'Workflow' : 'Plugin'}
                            </span>
                            <StatusBadge status={job.status} />
                          </div>
                          <div className="mt-1 flex items-center gap-4 text-xs text-gray-500">
                            <span>ID: {job.id.slice(0, 8)}</span>
                            <span>-</span>
                            <span>Compute: {job.backend_type === 'local_docker' ? 'Local Docker' : job.backend_type === 'slurm' ? 'HPC (SLURM)' : job.backend_type === 'remote_docker' ? 'Remote Docker' : job.backend_type}</span>
                            {!!job.runtime_seconds && (
                              <>
                                <span>-</span>
                                <span>Runtime: {formatRuntime(job.runtime_seconds)}</span>
                              </>
                            )}
                          </div>
                          <div className="mt-1 text-xs text-gray-500 truncate">
                            {job.is_sample_job ? (
                              <span>Bundled synthetic EEG (and toy T1 for the source demo)</span>
                            ) : (
                              <>Input: {job.input_files[0] || 'N/A'}</>
                            )}
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
                          {job.status === 'failed' && job.error_message && (
                            <p
                              className="mt-2 text-xs text-red-800 font-mono line-clamp-4"
                              title={job.error_message}
                            >
                              {job.error_message}
                            </p>
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
                      {job.status === 'completed' && job.is_sample_job && (
                        <button
                          type="button"
                          onClick={(e) => openSampleInViewer(job, e)}
                          className="px-2 py-1 text-xs font-medium text-white bg-[#003d7a] rounded-md hover:bg-[#002b55] transition"
                          title="Open Viewer with the right tab for this sample"
                        >
                          Viewer
                        </button>
                      )}
                      <button
                        onClick={(e) => handleDeleteJob(job.id, e)}
                        disabled={deletingJobs.has(job.id) || job.is_sample_job}
                        className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-md transition disabled:opacity-40 disabled:pointer-events-none"
                        title={job.is_sample_job ? 'Sample jobs cannot be deleted' : 'Delete job'}
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
