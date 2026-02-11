/**
 * JobProgressBar — Weighted phase-based progress indicator.
 *
 * Shows a smooth, animated progress bar that jumps to fixed
 * milestone percentages as each pipeline phase is reached.
 * The percentages are pre-weighted by typical wall-clock time
 * so the bar reflects "how much total work is done", not just
 * the number of steps completed.
 *
 * Props:
 *   progress:      0–100 integer from the backend
 *   currentPhase:  human-readable phase label (or null)
 *   status:        job status string
 */

import React from 'react';

interface JobProgressBarProps {
  progress: number;
  currentPhase?: string | null;
  status: string;
}

const JobProgressBar: React.FC<JobProgressBarProps> = ({
  progress,
  currentPhase,
  status,
}) => {
  // -- Colour scheme by status -------------------------------------------
  const getBarColor = () => {
    switch (status) {
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'cancelled':
        return 'bg-gray-400';
      case 'running':
        return 'bg-[#003d7a]';
      case 'pending':
        return 'bg-yellow-400';
      default:
        return 'bg-navy-400';
    }
  };

  const getTrackColor = () => {
    switch (status) {
      case 'completed':
        return 'bg-green-100';
      case 'failed':
        return 'bg-red-100';
      case 'cancelled':
        return 'bg-gray-100';
      default:
        return 'bg-navy-100';
    }
  };

  const getPctTextColor = () => {
    switch (status) {
      case 'completed':
        return 'text-green-700';
      case 'failed':
        return 'text-red-700';
      case 'cancelled':
        return 'text-gray-500';
      case 'running':
        return 'text-[#003d7a]';
      case 'pending':
        return 'text-yellow-700';
      default:
        return 'text-navy-700';
    }
  };

  // Clamp to 0–100
  const pct = Math.max(0, Math.min(100, progress));
  const isActive = status === 'running' || status === 'pending';

  return (
    <div className="w-full mt-1.5">
      {/* Progress bar track */}
      <div className={`relative w-full h-2 rounded-full ${getTrackColor()} overflow-hidden`}>
        <div
          className={`
            absolute top-0 left-0 h-full rounded-full
            ${getBarColor()}
            transition-all duration-700 ease-out
          `}
          style={{ width: `${pct}%` }}
        />
        {/* Animated shimmer for active jobs */}
        {isActive && pct > 0 && pct < 100 && (
          <div
            className="absolute top-0 left-0 h-full rounded-full opacity-30 animate-pulse bg-white"
            style={{ width: `${pct}%` }}
          />
        )}
      </div>

      {/* Label row: phase name + percentage */}
      <div className="flex items-center justify-between mt-1">
        <span className="text-[11px] text-gray-500 truncate max-w-[70%]">
          {currentPhase || (status === 'pending' ? 'Waiting in queue' : status === 'completed' ? 'Completed' : status === 'failed' ? 'Failed' : '')}
        </span>
        <span className={`text-[11px] font-semibold tabular-nums ${getPctTextColor()}`}>
          {pct}%
        </span>
      </div>
    </div>
  );
};

export default JobProgressBar;
