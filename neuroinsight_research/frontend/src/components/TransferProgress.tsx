/**
 * TransferProgress Component
 *
 * Shows real-time progress of data transfers between platforms and processing backends.
 * Polls the backend for transfer status and auto-advances when complete.
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Download, Upload, Loader2, CheckCircle2, XCircle, AlertCircle,
} from 'lucide-react';
import { apiService } from '../services/api';
import type { TransferStatus } from '../types';

interface TransferProgressProps {
  transferId: string;
  direction: 'download' | 'upload' | 'move';
  onComplete: () => void;
  onCancel?: () => void;
}

export const TransferProgress: React.FC<TransferProgressProps> = ({
  transferId,
  direction,
  onComplete,
  onCancel,
}) => {
  const [status, setStatus] = useState<TransferStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    pollProgress();
    intervalRef.current = setInterval(pollProgress, 2000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [transferId]);

  useEffect(() => {
    if (status?.status === 'completed') {
      if (intervalRef.current) clearInterval(intervalRef.current);
      const timer = setTimeout(onComplete, 1500);
      return () => clearTimeout(timer);
    }
    if (status?.status === 'failed' || status?.status === 'cancelled') {
      if (intervalRef.current) clearInterval(intervalRef.current);
    }
  }, [status?.status]);

  const pollProgress = async () => {
    try {
      const data = await apiService.getTransferProgress(transferId);
      setStatus(data);
      if (data.error) setError(data.error);
    } catch (err: any) {
      setError(err.message || 'Failed to get transfer progress');
    }
  };

  const handleCancel = async () => {
    try {
      await apiService.cancelTransfer(transferId);
      if (onCancel) onCancel();
    } catch { /* ignore */ }
  };

  const percent = status?.progress_percent || 0;
  const isActive = status?.status === 'downloading' || status?.status === 'uploading' || status?.status === 'pending' || status?.status === 'transferring';
  const isDone = status?.status === 'completed';
  const isFailed = status?.status === 'failed';
  const isCancelled = status?.status === 'cancelled';

  const Icon = direction === 'upload' ? Upload : Download;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Icon className="h-4 w-4 text-[#003d7a]" />
          <h3 className="text-sm font-semibold text-gray-700">
            {direction === 'download' ? 'Downloading Data' : 'Uploading Results'}
          </h3>
        </div>
        {isActive && onCancel && (
          <button
            onClick={handleCancel}
            className="text-xs text-red-600 hover:text-red-800 font-medium"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
          <span>
            {status?.files_completed || 0} / {status?.total_files || 0} files
          </span>
          <span>{Math.round(percent)}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2.5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              isDone ? 'bg-green-500' :
              isFailed ? 'bg-red-500' :
              'bg-[#003d7a]'
            }`}
            style={{ width: `${Math.min(percent, 100)}%` }}
          />
        </div>
      </div>

      {/* Status message */}
      <div className="flex items-center gap-2 text-xs">
        {isActive && (
          <>
            <Loader2 className="h-3.5 w-3.5 text-[#003d7a] animate-spin" />
            <span className="text-gray-600">
              {status?.status === 'pending' ? 'Preparing transfer...' :
               status?.status === 'transferring' ? 'Transferring data...' :
               direction === 'download' ? 'Downloading from platform...' :
               direction === 'upload' ? 'Uploading to platform...' :
               'Transferring data...'}
            </span>
          </>
        )}
        {isDone && (
          <>
            <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
            <span className="text-green-700 font-medium">Transfer complete. Proceeding...</span>
          </>
        )}
        {isFailed && (
          <>
            <XCircle className="h-3.5 w-3.5 text-red-600" />
            <span className="text-red-700">Transfer failed</span>
          </>
        )}
        {isCancelled && (
          <>
            <AlertCircle className="h-3.5 w-3.5 text-gray-500" />
            <span className="text-gray-600">Transfer cancelled</span>
          </>
        )}
      </div>

      {/* Error details */}
      {error && (isFailed || isCancelled) && (
        <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
          {error}
        </div>
      )}
    </div>
  );
};

export default TransferProgress;
