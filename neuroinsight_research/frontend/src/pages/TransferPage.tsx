/**
 * TransferPage -- WinSCP-style dual-pane file manager.
 *
 * Left pane  = Source
 * Right pane = Destination
 *
 * Supports all transfer combinations:
 *   Local <-> Remote <-> HPC <-> Pennsieve <-> XNAT
 *
 * Features:
 *   - Visual directory browsing on both sides
 *   - Platform selector for each pane
 *   - Transfer selected files from left to right (or right to left)
 *   - Transfer queue with real-time progress
 *   - Recent transfer history
 */

import { useState, useEffect, useCallback } from 'react';
import {
  ArrowRight, ArrowLeft, RefreshCw, AlertCircle,
  Monitor, Cloud, Server, Database, Globe,
  ChevronDown,
} from 'lucide-react';
import { apiService } from '../services/api';
import FileBrowserPane from '../components/FileBrowserPane';
import ConnectionPanel from '../components/ConnectionPanel';
import { TransferProgress } from '../components/TransferProgress';
import type { FileEntry, PlatformType } from '../components/FileBrowserPane';

interface PlatformTabDef {
  id: PlatformType;
  label: string;
  icon: React.ReactNode;
  activeClass: string;
}

const PLATFORM_TABS: PlatformTabDef[] = [
  { id: 'local',     label: 'Local Server',  icon: <Monitor className="h-3.5 w-3.5" />,  activeClass: 'border-navy-600 bg-navy-50 text-navy-700' },
  { id: 'remote',    label: 'Remote',        icon: <Cloud className="h-3.5 w-3.5" />,    activeClass: 'border-green-600 bg-green-50 text-green-700' },
  { id: 'hpc',       label: 'HPC',           icon: <Server className="h-3.5 w-3.5" />,   activeClass: 'border-navy-600 bg-navy-50 text-navy-700' },
  { id: 'pennsieve', label: 'Pennsieve',     icon: <Database className="h-3.5 w-3.5" />, activeClass: 'border-navy-600 bg-navy-50 text-navy-700' },
  { id: 'xnat',      label: 'XNAT',          icon: <Globe className="h-3.5 w-3.5" />,    activeClass: 'border-navy-600 bg-navy-50 text-navy-700' },
];

interface ActiveTransfer {
  id: string;
  direction: 'left-to-right' | 'right-to-left';
  sourceLabel: string;
  destLabel: string;
}

function TransferPage() {
  // Pane platforms
  const [leftPlatform, setLeftPlatform] = useState<PlatformType>('local');
  const [rightPlatform, setRightPlatform] = useState<PlatformType>('remote');

  // Pane paths (for backend platforms, used as source_path / dest_path)
  const [leftPath, setLeftPath] = useState('/home');
  const [rightPath, setRightPath] = useState('~');

  // Selected files in each pane
  const [leftSelected, setLeftSelected] = useState<FileEntry[]>([]);
  const [rightSelected, setRightSelected] = useState<FileEntry[]>([]);

  // Connection state per pane
  const [leftConnected, setLeftConnected] = useState(false);
  const [rightConnected, setRightConnected] = useState(false);

  // Transfer state
  const [activeTransfers, setActiveTransfers] = useState<ActiveTransfer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [recentTransfers, setRecentTransfers] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const data = await apiService.getTransferHistory();
      setRecentTransfers(data.transfers || []);
    } catch { /* ignore */ }
  };

  const isExternal = (p: PlatformType) => p === 'pennsieve' || p === 'xnat';

  // Start transfer left -> right
  const transferLeftToRight = useCallback(async () => {
    if (leftSelected.length === 0) return;
    if (leftPlatform === rightPlatform) {
      setError('Source and destination cannot be the same platform');
      return;
    }
    setError(null);

    const fileIds = leftSelected.map(f => f.id || f.path || f.name);
    const srcIsExternal = isExternal(leftPlatform);

    try {
      const result = await apiService.startTransferMove(
        leftPlatform,
        srcIsExternal ? '' : leftPath,
        srcIsExternal ? fileIds : null,
        rightPlatform,
        rightPath,
      );
      setActiveTransfers(prev => [...prev, {
        id: result.transfer_id,
        direction: 'left-to-right',
        sourceLabel: PLATFORM_TABS.find(t => t.id === leftPlatform)?.label || leftPlatform,
        destLabel: PLATFORM_TABS.find(t => t.id === rightPlatform)?.label || rightPlatform,
      }]);
      setLeftSelected([]);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to start transfer');
    }
  }, [leftSelected, leftPlatform, rightPlatform, leftPath, rightPath]);

  // Start transfer right -> left
  const transferRightToLeft = useCallback(async () => {
    if (rightSelected.length === 0) return;
    if (leftPlatform === rightPlatform) {
      setError('Source and destination cannot be the same platform');
      return;
    }
    setError(null);

    const fileIds = rightSelected.map(f => f.id || f.path || f.name);
    const srcIsExternal = isExternal(rightPlatform);

    try {
      const result = await apiService.startTransferMove(
        rightPlatform,
        srcIsExternal ? '' : rightPath,
        srcIsExternal ? fileIds : null,
        leftPlatform,
        leftPath,
      );
      setActiveTransfers(prev => [...prev, {
        id: result.transfer_id,
        direction: 'right-to-left',
        sourceLabel: PLATFORM_TABS.find(t => t.id === rightPlatform)?.label || rightPlatform,
        destLabel: PLATFORM_TABS.find(t => t.id === leftPlatform)?.label || leftPlatform,
      }]);
      setRightSelected([]);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to start transfer');
    }
  }, [rightSelected, leftPlatform, rightPlatform, leftPath, rightPath]);

  const handleTransferComplete = (transferId: string) => {
    setActiveTransfers(prev => prev.filter(t => t.id !== transferId));
    loadHistory();
  };

  const handleSwapPlatforms = () => {
    const tmpP = leftPlatform;
    const tmpPa = leftPath;
    const tmpS = leftSelected;
    setLeftPlatform(rightPlatform);
    setLeftPath(rightPath);
    setLeftSelected(rightSelected);
    setRightPlatform(tmpP);
    setRightPath(tmpPa);
    setRightSelected(tmpS);
  };

  const leftTab = PLATFORM_TABS.find(t => t.id === leftPlatform)!;
  const rightTab = PLATFORM_TABS.find(t => t.id === rightPlatform)!;

  return (
    <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col" style={{ height: 'calc(100vh - 140px)' }}>
      {/* Title */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Data Transfer</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Browse and transfer data between any two platforms
          </p>
        </div>
        <button
          onClick={() => setShowHistory(!showHistory)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs border border-gray-300 rounded-lg hover:bg-gray-50 text-gray-600"
        >
          <ChevronDown className={`h-3 w-3 transition ${showHistory ? 'rotate-180' : ''}`} />
          History ({recentTransfers.length})
        </button>
      </div>

      {/* Error bar */}
      {error && (
        <div className="flex items-center gap-2 p-2.5 mb-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700 font-medium">Dismiss</button>
        </div>
      )}

      {/* Main dual-pane area */}
      <div className="flex-1 flex gap-2 min-h-0">
        {/* Left pane */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Platform tabs */}
          <div className="flex gap-1 mb-2 flex-wrap">
            {PLATFORM_TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => { setLeftPlatform(tab.id); setLeftSelected([]); }}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-medium border transition ${
                  leftPlatform === tab.id ? tab.activeClass : 'border-gray-200 text-gray-500 hover:border-gray-300'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
          {/* Connection panel */}
          <div className="mb-2">
            <ConnectionPanel
              key={`left-${leftPlatform}`}
              platform={leftPlatform}
              onConnectionChange={setLeftConnected}
            />
          </div>
          <div className="flex-1 min-h-0">
            {leftConnected ? (
              <FileBrowserPane
                platform={leftPlatform}
                side="source"
                selectedFiles={leftSelected}
                onSelectionChange={setLeftSelected}
                onPathChange={setLeftPath}
              />
            ) : (
              <div className="h-full flex items-center justify-center bg-white rounded-lg border border-gray-200">
                <p className="text-xs text-gray-400">Connect to {leftTab.label} to browse files</p>
              </div>
            )}
          </div>
        </div>

        {/* Center controls */}
        <div className="flex flex-col items-center justify-center gap-2 px-1 py-4">
          <button
            onClick={transferLeftToRight}
            disabled={leftSelected.length === 0 || leftPlatform === rightPlatform || !leftConnected || !rightConnected}
            className="p-2 rounded-lg border border-gray-300 text-gray-500 hover:text-white hover:bg-[#003d7a] hover:border-[#003d7a] transition disabled:opacity-30 disabled:cursor-not-allowed"
            title={!leftConnected || !rightConnected ? 'Connect both platforms first' : `Transfer ${leftSelected.length} file(s) to ${rightTab.label}`}
          >
            <ArrowRight className="h-5 w-5" />
          </button>

          <button
            onClick={handleSwapPlatforms}
            className="p-1.5 rounded-full border border-gray-200 text-gray-400 hover:text-[#003d7a] hover:border-[#003d7a] transition"
            title="Swap panes"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>

          <button
            onClick={transferRightToLeft}
            disabled={rightSelected.length === 0 || leftPlatform === rightPlatform || !leftConnected || !rightConnected}
            className="p-2 rounded-lg border border-gray-300 text-gray-500 hover:text-white hover:bg-[#003d7a] hover:border-[#003d7a] transition disabled:opacity-30 disabled:cursor-not-allowed"
            title={!leftConnected || !rightConnected ? 'Connect both platforms first' : `Transfer ${rightSelected.length} file(s) to ${leftTab.label}`}
          >
            <ArrowLeft className="h-5 w-5" />
          </button>

          {(leftSelected.length > 0 || rightSelected.length > 0) && (
            <div className="text-[10px] text-center text-gray-500 mt-1 max-w-[60px]">
              {leftSelected.length > 0 && <div>{leftSelected.length} left</div>}
              {rightSelected.length > 0 && <div>{rightSelected.length} right</div>}
            </div>
          )}
        </div>

        {/* Right pane */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Platform tabs */}
          <div className="flex gap-1 mb-2 flex-wrap">
            {PLATFORM_TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => { setRightPlatform(tab.id); setRightSelected([]); }}
                className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-medium border transition ${
                  rightPlatform === tab.id ? tab.activeClass : 'border-gray-200 text-gray-500 hover:border-gray-300'
                }`}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
          {/* Connection panel */}
          <div className="mb-2">
            <ConnectionPanel
              key={`right-${rightPlatform}`}
              platform={rightPlatform}
              onConnectionChange={setRightConnected}
            />
          </div>
          <div className="flex-1 min-h-0">
            {rightConnected ? (
              <FileBrowserPane
                platform={rightPlatform}
                side="destination"
                selectedFiles={rightSelected}
                onSelectionChange={setRightSelected}
                onPathChange={setRightPath}
              />
            ) : (
              <div className="h-full flex items-center justify-center bg-white rounded-lg border border-gray-200">
                <p className="text-xs text-gray-400">Connect to {rightTab.label} to browse files</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Active transfers queue */}
      {activeTransfers.length > 0 && (
        <div className="mt-3 space-y-2">
          <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Active Transfers</h3>
          {activeTransfers.map(t => (
            <div key={t.id} className="flex items-center gap-3">
              <span className="text-[10px] text-gray-500 whitespace-nowrap">
                {t.sourceLabel} {t.direction === 'left-to-right' ? '\u2192' : '\u2190'} {t.destLabel}
              </span>
              <div className="flex-1">
                <TransferProgress
                  transferId={t.id}
                  direction="download"
                  onComplete={() => handleTransferComplete(t.id)}
                  onCancel={() => handleTransferComplete(t.id)}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Transfer history */}
      {showHistory && recentTransfers.length > 0 && (
        <div className="mt-3 bg-white rounded-lg border border-gray-200 p-3 max-h-40 overflow-y-auto">
          <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wider mb-2">Recent Transfers</h3>
          <div className="divide-y divide-gray-50">
            {recentTransfers.slice(0, 20).map((t: any) => (
              <div key={t.id} className="py-1.5 flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-2">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                    t.status === 'completed' ? 'bg-green-500' :
                    t.status === 'failed' ? 'bg-red-500' :
                    t.status === 'cancelled' ? 'bg-gray-400' :
                    'bg-[#003d7a] animate-pulse'
                  }`} />
                  <span className="text-gray-700">{t.platform || t.direction}</span>
                </div>
                <div className="flex items-center gap-3 text-gray-400">
                  <span>{t.files_completed}/{t.total_files} files</span>
                  <span>{Math.round(t.progress_percent)}%</span>
                  <span className={`font-medium ${
                    t.status === 'completed' ? 'text-green-600' :
                    t.status === 'failed' ? 'text-red-500' : ''
                  }`}>{t.status}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default TransferPage;
