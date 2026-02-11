/**
 * SlurmQueueMonitor Component
 *
 * Displays real-time SLURM queue information when using the HPC backend.
 * Shows user's jobs in the SLURM queue with state, time, partition, etc.
 * Auto-refreshes every 10 seconds.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Server, RefreshCw, AlertCircle } from 'lucide-react';
import { apiService } from '../services/api';

interface QueueJob {
  slurm_id: string;
  name: string;
  state: string;
  time: string;
  partition: string;
  timelimit: string;
  nodes: string;
  reason: string;
}

interface SlurmQueueMonitorProps {
  /** Only show when HPC backend is active */
  visible?: boolean;
  /** Auto-refresh interval in ms (default: 10000) */
  refreshInterval?: number;
}

const stateColors: Record<string, string> = {
  RUNNING: 'bg-green-100 text-green-800',
  PENDING: 'bg-yellow-100 text-yellow-800',
  COMPLETING: 'bg-navy-100 text-navy-800',
  FAILED: 'bg-red-100 text-red-800',
  CANCELLED: 'bg-gray-100 text-gray-600',
  TIMEOUT: 'bg-orange-100 text-orange-800',
};

const SlurmQueueMonitor: React.FC<SlurmQueueMonitorProps> = ({
  visible = true,
  refreshInterval = 10000,
}) => {
  const [queue, setQueue] = useState<QueueJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchQueue = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiService.hpcQueue(true);
      setQueue(data.queue || []);
      setLastRefresh(new Date());
    } catch (err: any) {
      if (err.response?.status === 400) {
        // Not using SLURM backend -- ignore
        setQueue([]);
      } else {
        setError('Failed to fetch queue');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!visible) return;
    fetchQueue();
    const interval = setInterval(fetchQueue, refreshInterval);
    return () => clearInterval(interval);
  }, [visible, refreshInterval, fetchQueue]);

  if (!visible) return null;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-1.5">
          <Server className="h-4 w-4 text-navy-600" />
          SLURM Queue
        </h3>
        <div className="flex items-center gap-2">
          {lastRefresh && (
            <span className="text-xs text-gray-400">
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchQueue}
            disabled={loading}
            className="p-1 rounded hover:bg-gray-100 text-gray-500 transition"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-1.5 text-xs text-red-600 mb-2">
          <AlertCircle className="h-3.5 w-3.5" />
          <span>{error}</span>
        </div>
      )}

      {queue.length === 0 && !error ? (
        <p className="text-xs text-gray-500 text-center py-3">
          No jobs in SLURM queue
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-1.5 px-2 font-medium text-gray-500">ID</th>
                <th className="text-left py-1.5 px-2 font-medium text-gray-500">Name</th>
                <th className="text-left py-1.5 px-2 font-medium text-gray-500">State</th>
                <th className="text-left py-1.5 px-2 font-medium text-gray-500">Time</th>
                <th className="text-left py-1.5 px-2 font-medium text-gray-500">Partition</th>
                <th className="text-left py-1.5 px-2 font-medium text-gray-500">Nodes</th>
                <th className="text-left py-1.5 px-2 font-medium text-gray-500">Reason</th>
              </tr>
            </thead>
            <tbody>
              {queue.map((job) => (
                <tr key={job.slurm_id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-1.5 px-2 font-mono text-navy-600">{job.slurm_id}</td>
                  <td className="py-1.5 px-2 truncate max-w-[120px]">{job.name}</td>
                  <td className="py-1.5 px-2">
                    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-medium ${stateColors[job.state] || 'bg-gray-100 text-gray-600'}`}>
                      {job.state}
                    </span>
                  </td>
                  <td className="py-1.5 px-2 font-mono">{job.time}</td>
                  <td className="py-1.5 px-2">{job.partition}</td>
                  <td className="py-1.5 px-2 text-center">{job.nodes}</td>
                  <td className="py-1.5 px-2 text-gray-500 truncate max-w-[100px]">{job.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {queue.length > 0 && (
        <div className="mt-2 flex gap-3 text-[10px] text-gray-400">
          <span>Running: {queue.filter(j => j.state === 'RUNNING').length}</span>
          <span>Pending: {queue.filter(j => j.state === 'PENDING').length}</span>
          <span>Total: {queue.length}</span>
        </div>
      )}
    </div>
  );
};

export default SlurmQueueMonitor;
