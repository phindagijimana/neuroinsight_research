/**
 * StatusBadge — a job status shown as icon + label, not colour alone.
 *
 * Colour-only status is hard for colourblind users and reads as less
 * deliberate. This pairs each status with an icon and a capitalised label in a
 * consistent pill, so the same badge looks the same everywhere it appears.
 */
import React from 'react';
import CheckCircle from './icons/CheckCircle';
import XCircle from './icons/XCircle';
import Clock from './icons/Clock';
import Activity from './icons/Activity';

type Status = 'completed' | 'running' | 'pending' | 'failed' | 'cancelled' | string;

const STYLES: Record<string, { cls: string; label: string }> = {
  completed: { cls: 'text-green-700 bg-green-100 border-green-200', label: 'Completed' },
  running: { cls: 'text-[#003d7a] bg-navy-100 border-navy-200', label: 'Running' },
  pending: { cls: 'text-navy-600 bg-navy-50 border-navy-200', label: 'Pending' },
  failed: { cls: 'text-red-700 bg-red-100 border-red-200', label: 'Failed' },
  cancelled: { cls: 'text-gray-600 bg-gray-100 border-gray-200', label: 'Cancelled' },
};

function iconFor(status: Status, cls: string) {
  switch (status) {
    case 'completed':
      return <CheckCircle className={cls} />;
    case 'running':
      return <Activity className={`${cls} animate-pulse`} />;
    case 'failed':
      return <XCircle className={cls} />;
    case 'pending':
    case 'cancelled':
    default:
      return <Clock className={cls} />;
  }
}

const StatusBadge: React.FC<{ status: Status; className?: string }> = ({ status, className = '' }) => {
  const { cls, label } = STYLES[status] || {
    cls: 'text-gray-600 bg-gray-100 border-gray-200',
    label: status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown',
  };
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-xs font-medium ${cls} ${className}`}
    >
      {iconFor(status, 'w-3.5 h-3.5')}
      {label}
    </span>
  );
};

export default StatusBadge;
