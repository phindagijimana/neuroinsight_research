/**
 * JobProgressBar — Weighted phase-based progress indicator.
 *
 * Navy-blue themed progress bar that shows smooth, animated
 * advancement as each pipeline phase is reached.
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
  const pct = Math.max(0, Math.min(100, progress));
  const isActive = status === 'running' || status === 'pending';
  const isCompleted = status === 'completed';
  const isFailed = status === 'failed';
  const isCancelled = status === 'cancelled';

  const barColor = isFailed
    ? 'bg-red-500'
    : isCancelled
    ? 'bg-navy-300'
    : isCompleted
    ? 'bg-[#003d7a]'
    : 'bg-[#003d7a]';

  const trackColor = isFailed ? 'bg-red-50' : 'bg-navy-100/60';

  const pctColor = isFailed
    ? 'text-red-600'
    : isCancelled
    ? 'text-navy-400'
    : 'text-[#003d7a]';

  const phaseColor = isFailed
    ? 'text-red-500'
    : isCancelled
    ? 'text-navy-400'
    : isActive
    ? 'text-navy-600'
    : 'text-navy-500';

  return (
    <div className="w-full mt-1.5">
      {/* Progress bar track */}
      <div className={`relative w-full h-2 rounded-full ${trackColor} overflow-hidden`}>
        <div
          className={`absolute top-0 left-0 h-full rounded-full ${barColor} transition-all duration-700 ease-out`}
          style={{ width: `${pct}%` }}
        />
        {/* Animated shimmer for active jobs */}
        {isActive && pct > 0 && pct < 100 && (
          <div
            className="absolute top-0 left-0 h-full rounded-full animate-pulse"
            style={{
              width: `${pct}%`,
              background: 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.35) 50%, transparent 100%)',
            }}
          />
        )}
        {/* Completed checkmark glow */}
        {isCompleted && (
          <div
            className="absolute top-0 left-0 h-full rounded-full opacity-20 bg-gradient-to-r from-[#003d7a] to-[#1a6ba0]"
            style={{ width: '100%' }}
          />
        )}
      </div>

      {/* Label row: phase name + percentage */}
      <div className="flex items-center justify-between mt-1">
        <span className={`text-[11px] ${phaseColor} truncate max-w-[70%]`}>
          {currentPhase || (
            status === 'pending' ? 'Waiting in queue...' :
            status === 'completed' ? 'Completed' :
            status === 'failed' ? 'Failed' :
            status === 'cancelled' ? 'Cancelled' : ''
          )}
        </span>
        <span className={`text-[11px] font-semibold tabular-nums ${pctColor}`}>
          {pct}%
        </span>
      </div>
    </div>
  );
};

export default JobProgressBar;
