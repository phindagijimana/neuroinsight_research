/**
 * Input/output path with click-to-open (Finder or connected data source), Copy, and open button.
 */
import React, { useMemo, useState } from 'react';
import { FolderOpen, Copy, Check } from 'lucide-react';
import Button from './Button';
import { useToast } from '../contexts/NotificationContext';
import type { Job } from '../types';
import {
  executePathOpenAction,
  pathLocationHeading,
  resolvePathOpenAction,
  type PathKind,
} from '../lib/openJobPath';

interface PathLocationBarProps {
  label: string;
  /** Absolute host path (file or folder). */
  hostPath: string;
  /** Shorter display path (e.g. ~/Documents/…). */
  displayPath: string;
  compact?: boolean;
  className?: string;
  pathKind?: PathKind;
  job?: Job | null;
  homeDir?: string | null;
  onNavigateToTransfer?: () => void;
}

const PathLocationBar: React.FC<PathLocationBarProps> = ({
  label,
  hostPath,
  displayPath,
  compact = false,
  className = '',
  pathKind = 'output',
  job = null,
  homeDir = null,
  onNavigateToTransfer,
}) => {
  const toast = useToast();
  const [copied, setCopied] = useState(false);

  const openAction = useMemo(
    () => resolvePathOpenAction({ path: hostPath, pathKind, job, homeDir }),
    [hostPath, pathKind, job, homeDir],
  );

  const canOpen = openAction.type === 'finder' || openAction.type === 'transfer';
  const openLabel = openAction.type === 'finder' ? 'Finder' : openAction.label;
  const heading = pathLocationHeading(label, openAction);

  const copyPath = async (e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await navigator.clipboard.writeText(hostPath);
      setCopied(true);
      toast.success(`${label} path copied.`);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Could not copy the path.');
    }
  };

  const openLocation = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!canOpen) {
      await copyPath();
      if (openAction.reason) toast.info(openAction.reason);
      return;
    }
    const result = await executePathOpenAction(openAction, onNavigateToTransfer);
    if (result === 'failed') {
      toast.error(`Could not open ${label.toLowerCase()} in ${openLabel}.`);
      return;
    }
    if (result === 'ok' && openAction.type === 'transfer') {
      toast.success(`Opened Transfer — browse ${openLabel}.`);
    }
  };

  if (!hostPath) return null;

  const pathButton = (
    <button
      type="button"
      onClick={openLocation}
      className={`text-left font-mono break-all leading-relaxed min-w-0 ${
        canOpen
          ? 'text-navy-700 hover:text-navy-900 hover:underline cursor-pointer'
          : 'text-gray-500 cursor-default'
      }`}
      title={openAction.title}
    >
      {displayPath}
    </button>
  );

  if (compact) {
    return (
      <div className={`flex flex-wrap items-center gap-2 ${className}`} onClick={(e) => e.stopPropagation()}>
        <div className="min-w-0 flex-1 text-xs">
          <span className="font-sans font-medium text-gray-600">{label}: </span>
          {pathButton}
        </div>
        <div className="flex shrink-0 gap-1">
          <button
            type="button"
            onClick={copyPath}
            className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
            title="Copy full path"
          >
            {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
            Copy
          </button>
          {canOpen && (
            <button
              type="button"
              onClick={openLocation}
              className="inline-flex items-center gap-1 rounded-md border border-navy-200 bg-navy-50 px-2 py-1 text-xs font-medium text-navy-700 hover:bg-navy-100"
              title={openAction.title}
            >
              <FolderOpen className="h-3.5 w-3.5" />
              {openLabel}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-lg border border-gray-200 bg-gray-50 px-4 py-3 ${className}`}>
      <p className="text-xs font-medium text-gray-600 mb-1">{heading}</p>
      <div className="text-sm">{pathButton}</div>
      {label === 'Output' && openAction.type === 'finder' && (
        <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
          Click the path or use <strong>Open in Finder</strong> — no need to browse for the hidden{' '}
          <span className="font-mono">.nir</span> folder.
        </p>
      )}
      {label === 'Output' && openAction.type === 'transfer' && (
        <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
          Click the path to open <strong>Transfer</strong> on the connected {openLabel} source.
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="secondary" size="sm" onClick={copyPath}>
          {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
          Copy path
        </Button>
        {canOpen && (
          <Button size="sm" onClick={openLocation}>
            <FolderOpen className="w-4 h-4" />
            {openAction.type === 'finder' ? 'Open in Finder' : openLabel}
          </Button>
        )}
      </div>
    </div>
  );
};

export default PathLocationBar;
