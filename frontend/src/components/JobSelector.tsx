/**
 * JobSelector — pick a completed job (subject-first labels, optional search).
 */
import React, { useMemo, useState } from 'react';
import type { Job } from '../types';
import { formatJobPickerLabel, jobMatchesFilter } from '../lib/jobLabels';

interface JobSelectorProps {
  jobs: Job[];
  selectedJobId: string | null;
  onJobSelect: (jobId: string) => void;
  label?: string;
  /** Inline layout for page headers (no block label). */
  compact?: boolean;
  className?: string;
}

export const JobSelector: React.FC<JobSelectorProps> = ({
  jobs,
  selectedJobId,
  onJobSelect,
  label = 'Completed job',
  compact = false,
  className = '',
}) => {
  const [filter, setFilter] = useState('');
  const completedJobs = jobs.filter((j) => j.status === 'completed');

  const visibleJobs = useMemo(() => {
    if (!filter.trim()) return completedJobs;
    return completedJobs.filter((job) => jobMatchesFilter(job, filter));
  }, [completedJobs, filter]);

  if (completedJobs.length === 0) {
    return (
      <div className={`rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 ${className}`}>
        <p className="text-xs text-amber-900">No completed jobs yet.</p>
      </div>
    );
  }

  const selectControl = (
    <select
      value={selectedJobId || ''}
      onChange={(e) => onJobSelect(e.target.value)}
      aria-label={label}
      className={`min-w-0 rounded-lg border border-gray-300 bg-white text-gray-900 focus:border-navy-600 focus:ring-2 focus:ring-navy-600 ${
        compact ? 'max-w-md px-3 py-1.5 text-sm' : 'w-full px-4 py-2'
      }`}
    >
      <option value="">Choose a job…</option>
      {visibleJobs.map((job) => (
        <option key={job.id} value={job.id}>
          {formatJobPickerLabel(job)}
        </option>
      ))}
    </select>
  );

  const showFilter = completedJobs.length > 4;

  if (compact) {
    return (
      <div className={`flex min-w-0 flex-col gap-1.5 sm:flex-row sm:items-center ${className}`}>
        <span className="shrink-0 text-xs font-medium text-gray-500">{label}</span>
        <div className="flex min-w-0 flex-1 flex-col gap-1.5 sm:flex-row sm:items-center">
          {selectControl}
          {showFilter && (
            <input
              type="search"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter…"
              aria-label="Filter completed jobs"
              className="w-full rounded-lg border border-gray-300 px-2.5 py-1.5 text-sm sm:w-36"
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      <label className="block text-sm font-semibold text-gray-700">{label}</label>
      {showFilter && (
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter by subject, pipeline, or ID…"
          aria-label="Filter completed jobs"
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
      )}
      {selectControl}
      {filter.trim() && visibleJobs.length === 0 && (
        <p className="text-xs text-gray-500">No jobs match &ldquo;{filter}&rdquo;.</p>
      )}
    </div>
  );
};

export default JobSelector;
