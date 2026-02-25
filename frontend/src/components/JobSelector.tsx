/**
 * JobSelector Component
 * Dropdown to select a completed job
 */

import React from 'react';
import type { Job } from '../types';
import CheckCircle from './icons/CheckCircle';

interface JobSelectorProps {
  jobs: Job[];
  selectedJobId: string | null;
  onJobSelect: (jobId: string) => void;
  label?: string;
}

export const JobSelector: React.FC<JobSelectorProps> = ({
  jobs,
  selectedJobId,
  onJobSelect,
  label = 'Select Job'
}) => {
  const completedJobs = jobs.filter(j => j.status === 'completed');

  if (completedJobs.length === 0) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-sm text-yellow-800">
          No completed jobs available. Submit and complete a job first.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <label className="block text-sm font-semibold text-gray-700">
        {label}
      </label>
      <select
        value={selectedJobId || ''}
        onChange={(e) => onJobSelect(e.target.value)}
        className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[#003d7a] focus:border-[#003d7a] bg-white text-gray-900"
      >
        <option value="">-- Select a completed job --</option>
        {completedJobs.map((job) => (
          <option key={job.id} value={job.id}>
            {job.id} - {job.pipeline_name} [{job.execution_mode === 'plugin' ? 'Plugin' : 'Workflow'}] ({new Date(job.completed_at || job.submitted_at).toLocaleDateString()})
          </option>
        ))}
      </select>
      {selectedJobId && (
        <div className="flex items-center gap-2 text-sm text-green-600">
          <CheckCircle className="w-4 h-4" />
          <span>Job selected</span>
        </div>
      )}
    </div>
  );
};

export default JobSelector;
