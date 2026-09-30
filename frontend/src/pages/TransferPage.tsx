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
  ChevronDown, Plus, X,
} from 'lucide-react';
import { apiService } from '../services/api';
import type { ConnectionInfo } from '../services/api';
import FileBrowserPane from '../components/FileBrowserPane';
import ConnectionPanel from '../components/ConnectionPanel';
import { TransferProgress } from '../components/TransferProgress';
import type { FileEntry, PlatformType } from '../components/FileBrowserPane';
import { consumeTransferOpenAt, stashJobsOpenAt, platformToJobsBackend, browseDirectoryForPath } from '../lib/openJobPath';
import { canBrowsePlatform, isLocalPlatform, probePlatformConnected } from '../lib/platformConnection';
import { usePlatformSession } from '../contexts/PlatformSessionContext';
import WorkspacePageHeader from '../components/WorkspacePageHeader';
import WorkspaceEmptyState from '../components/WorkspaceEmptyState';
import { WORKSPACE_PAGE_INNER, WORKSPACE_PAGE_OUTER } from '../lib/workspaceLayout';
import { Wifi } from 'lucide-react';

interface TransferPageProps {
  setActivePage?: (page: string) => void;
}

interface ActiveTransfer {
  id: string;
  direction: 'left-to-right' | 'right-to-left';
  sourceLabel: string;
  destLabel: string;
  destPlatform: PlatformType;
}

interface JobsHandoff {
  backend: 'local' | 'remote' | 'remote_hpc';
  path: string;
  destLabel: string;
}
interface PlatformTabDef {
  id: PlatformType;
  label: string;
  icon: React.ReactNode;
  activeClass: string;
}

const PLATFORM_TABS: PlatformTabDef[] = [
  { id: 'local',     label: 'Local',  icon: <Monitor className="h-3.5 w-3.5" />,  activeClass: 'border-navy-600 bg-navy-50 text-navy-700' },
  { id: 'remote',    label: 'Remote',        icon: <Cloud className="h-3.5 w-3.5" />,    activeClass: 'border-navy-600 bg-navy-50 text-navy-700' },
  { id: 'hpc',       label: 'HPC',           icon: <Server className="h-3.5 w-3.5" />,   activeClass: 'border-navy-600 bg-navy-50 text-navy-700' },
  { id: 'pennsieve', label: 'Pennsieve',     icon: <Database className="h-3.5 w-3.5" />, activeClass: 'border-navy-600 bg-navy-50 text-navy-700' },
  { id: 'xnat',      label: 'XNAT',          icon: <Globe className="h-3.5 w-3.5" />,    activeClass: 'border-navy-600 bg-navy-50 text-navy-700' },
];

const ACTIVE_TRANSFERS_STORAGE_KEY = 'neuroinsight.activeTransfers.v1';

function isPlatformType(value: string): value is PlatformType {
  return ['local', 'remote', 'hpc', 'pennsieve', 'xnat'].includes(value);
}

/** SSH-backed panes that can carry a specific connection id. */
function isBackendHost(p: PlatformType): boolean {
  return p === 'hpc' || p === 'remote';
}

function TransferPage({ setActivePage }: TransferPageProps) {
  const { sessions, hydrating, getSession } = usePlatformSession();
  // Pane platforms
  const [leftPlatform, setLeftPlatform] = useState<PlatformType>('local');
  const [rightPlatform, setRightPlatform] = useState<PlatformType>('remote');

  // Pane paths (for backend platforms, used as source_path / dest_path)
  const [leftPath, setLeftPath] = useState('~');
  const [rightPath, setRightPath] = useState('~');
  const [leftInitialPath, setLeftInitialPath] = useState<string | null>(null);
  const [rightInitialPath, setRightInitialPath] = useState<string | null>(null);

  // Selected files in each pane
  const [leftSelected, setLeftSelected] = useState<FileEntry[]>([]);
  const [rightSelected, setRightSelected] = useState<FileEntry[]>([]);

  // Connection state per pane (local is always browsable)
  const [leftConnected, setLeftConnected] = useState(true);
  const [rightConnected, setRightConnected] = useState(false);
  const [leftUploadReady, setLeftUploadReady] = useState(true);
  const [rightUploadReady, setRightUploadReady] = useState(true);
  const [leftUploadError, setLeftUploadError] = useState<string | null>(null);
  const [rightUploadError, setRightUploadError] = useState<string | null>(null);

  // Multi-host connections (extras beside the single active session)
  const [connections, setConnections] = useState<ConnectionInfo[]>([]);
  const [leftConnId, setLeftConnId] = useState<string>('active');
  const [rightConnId, setRightConnId] = useState<string>('active');
  const [showAddConn, setShowAddConn] = useState(false);
  const [addConnBusy, setAddConnBusy] = useState(false);
  const [addConnError, setAddConnError] = useState<string | null>(null);
  const [newConn, setNewConn] = useState({
    name: '', host: '', username: '', port: '22', password: '', work_dir: '',
  });

  // Transfer state
  const [activeTransfers, setActiveTransfers] = useState<ActiveTransfer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [recentTransfers, setRecentTransfers] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [jobsHandoff, setJobsHandoff] = useState<JobsHandoff | null>(null);

  const refreshConnections = useCallback(async () => {
    try {
      const data = await apiService.listConnections();
      setConnections(data.connections || []);
    } catch {
      // Non-fatal: leave the current list in place.
    }
  }, []);

  useEffect(() => {
    refreshConnections();
    const t = setInterval(refreshConnections, 8000);
    return () => clearInterval(t);
  }, [refreshConnections]);

  // If a pane points at an extra connection that went away, fall back to active.
  useEffect(() => {
    const ids = new Set(['active', ...connections.map((c) => c.id)]);
    if (!ids.has(leftConnId)) setLeftConnId('active');
    if (!ids.has(rightConnId)) setRightConnId('active');
  }, [connections, leftConnId, rightConnId]);

  const persistActiveTransfers = useCallback((items: ActiveTransfer[]) => {
    try {
      window.sessionStorage.setItem(
        ACTIVE_TRANSFERS_STORAGE_KEY,
        JSON.stringify(items),
      );
    } catch {
      // Ignore storage errors.
    }
  }, []);

  const hydrateActiveTransfers = useCallback((): ActiveTransfer[] => {
    try {
      const raw = window.sessionStorage.getItem(ACTIVE_TRANSFERS_STORAGE_KEY);
      if (!raw) return [];
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter(
          (t: any) =>
            t &&
            typeof t.id === 'string' &&
            (t.direction === 'left-to-right' || t.direction === 'right-to-left') &&
            typeof t.sourceLabel === 'string' &&
            typeof t.destLabel === 'string',
        )
        .map((t: any) => ({
          id: t.id,
          direction: t.direction,
          sourceLabel: t.sourceLabel,
          destLabel: t.destLabel,
          destPlatform: isPlatformType(t.destPlatform) ? t.destPlatform : 'local',
        }));
    } catch {
      return [];
    }
  }, []);

  const mergeWithoutDuplicates = useCallback((base: ActiveTransfer[], extra: ActiveTransfer[]) => {
    const byId = new Map<string, ActiveTransfer>();
    [...base, ...extra].forEach((item) => byId.set(item.id, item));
    return Array.from(byId.values());
  }, []);

  const enqueueTransfers = useCallback((incoming: ActiveTransfer[]) => {
    setActiveTransfers((prev) => mergeWithoutDuplicates(prev, incoming));
  }, [mergeWithoutDuplicates]);

  useEffect(() => {
    const restored = hydrateActiveTransfers();
    if (restored.length > 0) {
      setActiveTransfers(restored);
    }
    loadHistory();

    const openAt = consumeTransferOpenAt();
    if (openAt) {
      if (openAt.pane === 'left') {
        setLeftPlatform(openAt.platform);
        setLeftPath(openAt.path);
        setLeftInitialPath(openAt.path);
      } else {
        setRightPlatform(openAt.platform);
        setRightPath(openAt.path);
        setRightInitialPath(openAt.path);
      }
    }
  }, [hydrateActiveTransfers]);

  useEffect(() => {
    persistActiveTransfers(activeTransfers);
  }, [activeTransfers, persistActiveTransfers]);

  const syncPaneConnection = useCallback(
    async (platform: PlatformType, setConnected: (v: boolean) => void) => {
      if (isLocalPlatform(platform)) {
        setConnected(true);
        return;
      }
      setConnected(false);
      try {
        setConnected(await probePlatformConnected(platform));
      } catch {
        setConnected(false);
      }
    },
    [],
  );

  useEffect(() => {
    syncPaneConnection(leftPlatform, setLeftConnected);
  }, [leftPlatform, syncPaneConnection]);

  useEffect(() => {
    syncPaneConnection(rightPlatform, setRightConnected);
  }, [rightPlatform, syncPaneConnection]);

  // After platform sessions hydrate, enable browse for connected Pennsieve/XNAT tabs.
  useEffect(() => {
    if (hydrating) return;
    if (leftPlatform === 'pennsieve' || leftPlatform === 'xnat') {
      if (getSession(leftPlatform)?.connected) setLeftConnected(true);
    }
    if (rightPlatform === 'pennsieve' || rightPlatform === 'xnat') {
      if (getSession(rightPlatform)?.connected) setRightConnected(true);
    }
  }, [hydrating, sessions, leftPlatform, rightPlatform, getSession]);

  useEffect(() => {
    if (leftPlatform !== 'pennsieve') {
      setLeftUploadReady(true);
      setLeftUploadError(null);
    }
  }, [leftPlatform]);

  useEffect(() => {
    if (rightPlatform !== 'pennsieve') {
      setRightUploadReady(true);
      setRightUploadError(null);
    }
  }, [rightPlatform]);

  const loadHistory = async () => {
    try {
      const data = await apiService.getTransferHistory();
      const transfers = data.transfers || [];
      setRecentTransfers(transfers);

      const running = transfers.filter((t: any) =>
        ['pending', 'downloading', 'uploading', 'transferring'].includes(t.status),
      );
      if (running.length > 0) {
        const recovered: ActiveTransfer[] = running.map((t: any) => ({
          id: t.id,
          direction: 'left-to-right',
          sourceLabel: String(t.platform || 'Source'),
          destLabel: 'Destination',
          destPlatform: 'local',
        }));
        enqueueTransfers(recovered);
      }
    } catch { /* ignore */ }
  };

  const isExternal = (p: PlatformType) => p === 'pennsieve' || p === 'xnat';

  // Start transfer left -> right
  const transferLeftToRight = useCallback(async () => {
    if (leftSelected.length === 0) return;
    const bothBackendHosts = isBackendHost(leftPlatform) && isBackendHost(rightPlatform);
    if (leftPlatform === rightPlatform && !(bothBackendHosts && leftConnId !== rightConnId)) {
      setError('Source and destination are the same. Pick a different connection on one side to copy between two hosts.');
      return;
    }
    setError(null);
    if (rightPlatform === 'pennsieve' && !rightUploadReady) {
      setError(rightUploadError || 'Pennsieve Agent is not ready. Start pennsieve agent and verify profile.');
      return;
    }

    const fileIds = leftSelected.map(f => f.id || f.path || f.name);
    const srcIsExternal = isExternal(leftPlatform);

    try {
      const result = await apiService.startTransferMove(
        leftPlatform,
        srcIsExternal ? '' : leftPath,
        fileIds,
        rightPlatform,
        rightPath,
        isBackendHost(leftPlatform) ? leftConnId : null,
        isBackendHost(rightPlatform) ? rightConnId : null,
      );
      enqueueTransfers([{
        id: result.transfer_id,
        direction: 'left-to-right',
        sourceLabel: PLATFORM_TABS.find(t => t.id === leftPlatform)?.label || leftPlatform,
        destLabel: PLATFORM_TABS.find(t => t.id === rightPlatform)?.label || rightPlatform,
        destPlatform: rightPlatform,
      }]);
      setLeftSelected([]);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to start transfer');
    }
  }, [
    leftSelected,
    leftPlatform,
    rightPlatform,
    leftPath,
    rightPath,
    leftConnId,
    rightConnId,
    rightUploadReady,
    rightUploadError,
    enqueueTransfers,
  ]);

  // Start transfer right -> left
  const transferRightToLeft = useCallback(async () => {
    if (rightSelected.length === 0) return;
    const bothBackendHosts = isBackendHost(leftPlatform) && isBackendHost(rightPlatform);
    if (leftPlatform === rightPlatform && !(bothBackendHosts && leftConnId !== rightConnId)) {
      setError('Source and destination are the same. Pick a different connection on one side to copy between two hosts.');
      return;
    }
    setError(null);
    if (leftPlatform === 'pennsieve' && !leftUploadReady) {
      setError(leftUploadError || 'Pennsieve Agent is not ready. Start pennsieve agent and verify profile.');
      return;
    }

    const fileIds = rightSelected.map(f => f.id || f.path || f.name);
    const srcIsExternal = isExternal(rightPlatform);

    try {
      const result = await apiService.startTransferMove(
        rightPlatform,
        srcIsExternal ? '' : rightPath,
        fileIds,
        leftPlatform,
        leftPath,
        isBackendHost(rightPlatform) ? rightConnId : null,
        isBackendHost(leftPlatform) ? leftConnId : null,
      );
      enqueueTransfers([{
        id: result.transfer_id,
        direction: 'right-to-left',
        sourceLabel: PLATFORM_TABS.find(t => t.id === rightPlatform)?.label || rightPlatform,
        destLabel: PLATFORM_TABS.find(t => t.id === leftPlatform)?.label || leftPlatform,
        destPlatform: leftPlatform,
      }]);
      setRightSelected([]);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to start transfer');
    }
  }, [
    rightSelected,
    leftPlatform,
    rightPlatform,
    leftPath,
    rightPath,
    leftConnId,
    rightConnId,
    leftUploadReady,
    leftUploadError,
    enqueueTransfers,
  ]);

  const handleTransferComplete = (
    transfer: ActiveTransfer,
    info?: { localPaths: string[]; targetPath: string },
  ) => {
    if (info?.targetPath) {
      const backend = platformToJobsBackend(transfer.destPlatform);
      if (backend) {
        setJobsHandoff({
          backend,
          path: browseDirectoryForPath(info.targetPath, 'input'),
          destLabel: transfer.destLabel,
        });
      }
    }
    setActiveTransfers((prev) => prev.filter((item) => item.id !== transfer.id));
    loadHistory();
  };

  const openTransferInJobs = () => {
    if (!jobsHandoff || !setActivePage) return;
    stashJobsOpenAt({ backend: jobsHandoff.backend, path: jobsHandoff.path });
    setActivePage('jobs');
    setJobsHandoff(null);
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

  // A pane pointed at an extra connection is "connected" when that connection
  // is live, independent of the single active session the ConnectionPanel tracks.
  const leftExtra = leftConnId !== 'active' ? connections.find(c => c.id === leftConnId) : null;
  const rightExtra = rightConnId !== 'active' ? connections.find(c => c.id === rightConnId) : null;
  const leftEffConnected = leftExtra ? !!leftExtra.connected : leftConnected;
  const rightEffConnected = rightExtra ? !!rightExtra.connected : rightConnected;

  const leftCanBrowse = canBrowsePlatform(leftPlatform, leftEffConnected);
  const rightCanBrowse = canBrowsePlatform(rightPlatform, rightEffConnected);

  // Same endpoint = same platform AND (not SSH-backed, or same connection).
  const sameEndpoint =
    leftPlatform === rightPlatform &&
    (!isBackendHost(leftPlatform) || leftConnId === rightConnId);

  // Connection options a pane can pick (active + extras), for the per-pane picker.
  const connOptions = [
    { id: 'active', label: (connections.find(c => c.is_active)?.host) || 'Active session', is_active: true },
    ...connections.filter(c => !c.is_active).map(c => ({ id: c.id, label: c.name || c.host || c.id, is_active: false })),
  ];
  const showConnPicker = connections.length > 1 || connections.some(c => !c.is_active);

  const leftTab = PLATFORM_TABS.find(t => t.id === leftPlatform)!;
  const rightTab = PLATFORM_TABS.find(t => t.id === rightPlatform)!;

  const submitAddConnection = async () => {
    setAddConnError(null);
    if (!newConn.host || !newConn.username) {
      setAddConnError('Host and username are required.');
      return;
    }
    setAddConnBusy(true);
    try {
      const created = await apiService.addConnection({
        name: newConn.name || newConn.host,
        host: newConn.host,
        username: newConn.username,
        port: parseInt(newConn.port || '22', 10) || 22,
        password: newConn.password || null,
        work_dir: newConn.work_dir || null,
        kind: 'hpc',
      });
      await refreshConnections();
      setShowAddConn(false);
      setNewConn({ name: '', host: '', username: '', port: '22', password: '', work_dir: '' });
      // Point the destination pane at the new connection for immediate use.
      setRightPlatform('hpc');
      setRightConnId(created.id);
    } catch (err: any) {
      setAddConnError(err.response?.data?.detail || err.message || 'Could not connect.');
    } finally {
      setAddConnBusy(false);
    }
  };

  return (
    <div className={WORKSPACE_PAGE_OUTER}>
      <div
        className={`${WORKSPACE_PAGE_INNER} flex flex-col`}
        style={{ minHeight: 'calc(100vh - 3.5rem)' }}
      >
        <WorkspacePageHeader
          title="Transfer"
          subtitle="Move data between Local, Remote Server, HPC, Pennsieve, and XNAT. Stage files here before running jobs."
          actions={
            <button
              type="button"
              onClick={() => setShowHistory(!showHistory)}
              className="flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
            >
              <ChevronDown className={`h-3 w-3 transition ${showHistory ? 'rotate-180' : ''}`} />
              History ({recentTransfers.length})
            </button>
          }
        />

      {jobsHandoff && (
        <div className="flex flex-wrap items-center justify-between gap-2 p-2.5 mb-3 bg-emerald-50 border border-emerald-200 rounded-lg text-xs text-emerald-900">
          <span>
            Transfer complete on <strong>{jobsHandoff.destLabel}</strong> at{' '}
            <code className="font-mono text-[11px]">{jobsHandoff.path}</code>
          </span>
          {setActivePage ? (
            <button
              type="button"
              onClick={openTransferInJobs}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-navy-600 text-white font-medium hover:bg-navy-800"
            >
              Open in Jobs
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      )}

      {/* Error bar */}
      {error && (
        <div className="flex items-center gap-2 p-2.5 mb-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700 font-medium">Dismiss</button>
        </div>
      )}

      {/* Connections rail */}
      <div className="mb-3 rounded-2xl border border-gray-200/90 bg-white shadow-sm">
        <div className="flex items-center justify-between gap-3 px-4 sm:px-5 py-3 border-b border-gray-100">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-gray-900">Connections</h2>
            <p className="text-xs text-gray-500 mt-0.5">
              {connections.filter(c => !c.is_active).length > 0
                ? 'Multiple hosts connected — pick a connection per pane to copy between them.'
                : 'Add a second HPC to copy directly between two clusters.'}
            </p>
          </div>
          <button
            type="button"
            onClick={() => { setAddConnError(null); setShowAddConn(true); }}
            className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-navy-200 bg-navy-50 px-3 py-1.5 text-xs font-medium text-navy-600 hover:bg-navy-100"
          >
            <Plus className="h-3.5 w-3.5" /> Add connection
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-2 px-4 sm:px-5 py-3">
          {connections.length === 0 && (
            <span className="text-xs text-gray-400">No SSH connections yet — connect an HPC in a pane below, or add one.</span>
          )}
          {connections.map(c => (
            <span
              key={c.id}
              className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs shadow-sm"
            >
              <span className={`h-2 w-2 rounded-full ${c.connected ? 'bg-emerald-500 ring-2 ring-emerald-100' : 'bg-gray-300'}`} />
              <span className="rounded border border-navy-200 bg-navy-50 px-1.5 text-[10px] font-semibold uppercase tracking-wide text-navy-600">
                {c.kind}
              </span>
              <span className="font-medium text-gray-900">{c.is_active ? (c.host || 'Active') : (c.name || c.host)}</span>
              {c.host && <span className="font-mono text-[11px] text-gray-400">{c.host}</span>}
              {!c.is_active && (
                <button
                  type="button"
                  title={`Disconnect ${c.name || c.host}`}
                  onClick={async () => { await apiService.removeConnection(c.id); await refreshConnections(); }}
                  className="text-gray-400 hover:text-red-600"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </span>
          ))}
        </div>
      </div>

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
          {/* Per-pane connection picker (SSH-backed panes with >1 connection) */}
          {isBackendHost(leftPlatform) && showConnPicker && (
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[11px] font-medium text-gray-400">Connection</span>
              <select
                value={leftConnId}
                onChange={(e) => { setLeftConnId(e.target.value); setLeftSelected([]); }}
                className="flex-1 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-800 focus:border-navy-600 focus:outline-none focus:ring-1 focus:ring-navy-600/40"
              >
                {connOptions.map(o => (
                  <option key={o.id} value={o.id}>{o.label}{o.is_active ? ' (active)' : ''}</option>
                ))}
              </select>
            </div>
          )}
          {/* Connection panel (only for the active session) */}
          {leftConnId === 'active' && (
            <div className="mb-2">
              <ConnectionPanel
                key={`left-${leftPlatform}`}
                platform={leftPlatform}
                onConnectionChange={setLeftConnected}
                onPlatformStatusChange={(status) => {
                  setLeftUploadReady(status.uploadReady ?? status.connected);
                  setLeftUploadError(status.uploadError ?? null);
                }}
              />
            </div>
          )}
          <div className="flex-1 min-h-0">
            {leftCanBrowse ? (
              <FileBrowserPane
                key={`left-${leftPlatform}-${leftConnId}-${leftInitialPath || ''}`}
                platform={leftPlatform}
                side="source"
                selectedFiles={leftSelected}
                onSelectionChange={setLeftSelected}
                onPathChange={setLeftPath}
                initialPath={leftInitialPath}
                connectionId={isBackendHost(leftPlatform) ? leftConnId : null}
              />
            ) : (
              <div className="flex h-full min-h-[12rem] items-stretch rounded-lg border border-gray-200 bg-white">
                <WorkspaceEmptyState
                  icon={<Wifi className="h-6 w-6" />}
                  title={`Connect to ${leftTab.label}`}
                  description="Use the connection panel above to sign in, then browse files here."
                />
              </div>
            )}
          </div>
        </div>

        {/* Center controls */}
        <div className="flex flex-col items-center justify-center gap-2 px-1 py-4">
          <button
            onClick={transferLeftToRight}
            disabled={
              leftSelected.length === 0 ||
              sameEndpoint ||
              !leftEffConnected ||
              !rightEffConnected ||
              (rightPlatform === 'pennsieve' && !rightUploadReady)
            }
            className="p-2 rounded-lg border border-gray-300 text-gray-500 hover:text-white hover:bg-navy-600 hover:border-navy-600 transition disabled:opacity-30 disabled:cursor-not-allowed"
            title={
              !leftEffConnected || !rightEffConnected
                ? 'Connect both sides first'
                : sameEndpoint
                  ? 'Pick a different connection on one side'
                  : rightPlatform === 'pennsieve' && !rightUploadReady
                    ? (rightUploadError || 'Pennsieve Agent is not ready for upload')
                    : `Transfer ${leftSelected.length} file(s) to ${rightTab.label}`
            }
            aria-label={`Transfer selected files to ${rightTab.label}`}
          >
            <ArrowRight className="h-5 w-5" />
          </button>

          <button
            onClick={handleSwapPlatforms}
            className="p-1.5 rounded-full border border-gray-200 text-gray-400 hover:text-navy-600 hover:border-navy-600 transition"
            title="Swap panes"
            aria-label="Swap panes"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>

          <button
            onClick={transferRightToLeft}
            disabled={
              rightSelected.length === 0 ||
              sameEndpoint ||
              !leftEffConnected ||
              !rightEffConnected ||
              (leftPlatform === 'pennsieve' && !leftUploadReady)
            }
            className="p-2 rounded-lg border border-gray-300 text-gray-500 hover:text-white hover:bg-navy-600 hover:border-navy-600 transition disabled:opacity-30 disabled:cursor-not-allowed"
            title={
              !leftEffConnected || !rightEffConnected
                ? 'Connect both sides first'
                : sameEndpoint
                  ? 'Pick a different connection on one side'
                  : leftPlatform === 'pennsieve' && !leftUploadReady
                    ? (leftUploadError || 'Pennsieve Agent is not ready for upload')
                    : `Transfer ${rightSelected.length} file(s) to ${leftTab.label}`
            }
            aria-label={`Transfer selected files to ${leftTab.label}`}
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
          {/* Per-pane connection picker (SSH-backed panes with >1 connection) */}
          {isBackendHost(rightPlatform) && showConnPicker && (
            <div className="mb-2 flex items-center gap-2">
              <span className="text-[11px] font-medium text-gray-400">Connection</span>
              <select
                value={rightConnId}
                onChange={(e) => { setRightConnId(e.target.value); setRightSelected([]); }}
                className="flex-1 rounded-md border border-gray-200 bg-white px-2.5 py-1.5 text-xs text-gray-800 focus:border-navy-600 focus:outline-none focus:ring-1 focus:ring-navy-600/40"
              >
                {connOptions.map(o => (
                  <option key={o.id} value={o.id}>{o.label}{o.is_active ? ' (active)' : ''}</option>
                ))}
              </select>
            </div>
          )}
          {/* Connection panel (only for the active session) */}
          {rightConnId === 'active' && (
            <div className="mb-2">
              <ConnectionPanel
                key={`right-${rightPlatform}`}
                platform={rightPlatform}
                onConnectionChange={setRightConnected}
                onPlatformStatusChange={(status) => {
                  setRightUploadReady(status.uploadReady ?? status.connected);
                  setRightUploadError(status.uploadError ?? null);
                }}
              />
            </div>
          )}
          <div className="flex-1 min-h-0">
            {rightCanBrowse ? (
              <FileBrowserPane
                key={`right-${rightPlatform}-${rightConnId}-${rightInitialPath || ''}`}
                platform={rightPlatform}
                side="destination"
                selectedFiles={rightSelected}
                onSelectionChange={setRightSelected}
                onPathChange={setRightPath}
                initialPath={rightInitialPath}
                connectionId={isBackendHost(rightPlatform) ? rightConnId : null}
              />
            ) : (
              <div className="flex h-full min-h-[12rem] items-stretch rounded-lg border border-gray-200 bg-white">
                <WorkspaceEmptyState
                  icon={<Wifi className="h-6 w-6" />}
                  title={`Connect to ${rightTab.label}`}
                  description="Use the connection panel above to sign in, then browse files here."
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Active transfers queue */}
      {activeTransfers.length > 0 && (
        <div className="mt-3 space-y-2">
          <h3 className="text-xs font-semibold text-gray-600 tracking-wider">Active Transfers</h3>
          <div className="nir-scroll-list space-y-2">
          {activeTransfers.map(t => (
            <div key={t.id} className="flex items-center gap-3">
              <span className="text-[10px] text-gray-500 whitespace-nowrap">
                {t.sourceLabel} {t.direction === 'left-to-right' ? '\u2192' : '\u2190'} {t.destLabel}
              </span>
              <div className="flex-1">
                <TransferProgress
                  transferId={t.id}
                  direction="download"
                  onComplete={(info) => handleTransferComplete(t, info)}
                  onCancel={() => handleTransferComplete(t)}
                />
              </div>
            </div>
          ))}
          </div>
        </div>
      )}

      {/* Transfer history */}
      {showHistory && recentTransfers.length > 0 && (
        <div className="mt-3 bg-white rounded-lg border border-gray-200 p-3 nir-scroll-list">
          <h3 className="text-xs font-semibold text-gray-600 tracking-wider mb-2">Recent Transfers</h3>
          <div className="divide-y divide-gray-50">
            {recentTransfers.slice(0, 20).map((t: any) => (
              <div key={t.id} className="py-1.5 flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-2">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${
                    t.status === 'completed' ? 'bg-green-500' :
                    t.status === 'failed' ? 'bg-red-500' :
                    t.status === 'cancelled' ? 'bg-gray-400' :
                    'bg-navy-600 animate-pulse'
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

      {/* Add-connection modal */}
      {showAddConn && (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-gray-900/50 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setShowAddConn(false); }}
        >
          <div className="w-full max-w-md overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-gray-100 px-5 py-4">
              <h3 className="text-base font-semibold text-gray-900">Add HPC / remote connection</h3>
              <button onClick={() => setShowAddConn(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid gap-3.5 px-5 py-4">
              <div className="grid gap-1.5">
                <label className="text-xs font-medium text-gray-700">Display name</label>
                <input
                  value={newConn.name}
                  onChange={(e) => setNewConn({ ...newConn, name: e.target.value })}
                  placeholder="e.g. BlueHive3"
                  className="rounded-md border border-gray-200 bg-white px-3 py-2 text-sm focus:border-navy-600 focus:outline-none focus:ring-1 focus:ring-navy-600/40"
                />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2 grid gap-1.5">
                  <label className="text-xs font-medium text-gray-700">Host</label>
                  <input
                    value={newConn.host}
                    onChange={(e) => setNewConn({ ...newConn, host: e.target.value })}
                    placeholder="login.hpc.edu"
                    className="rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm focus:border-navy-600 focus:outline-none focus:ring-1 focus:ring-navy-600/40"
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-xs font-medium text-gray-700">Port</label>
                  <input
                    value={newConn.port}
                    onChange={(e) => setNewConn({ ...newConn, port: e.target.value })}
                    className="rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm focus:border-navy-600 focus:outline-none focus:ring-1 focus:ring-navy-600/40"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-1.5">
                  <label className="text-xs font-medium text-gray-700">Username</label>
                  <input
                    value={newConn.username}
                    onChange={(e) => setNewConn({ ...newConn, username: e.target.value })}
                    placeholder="netid"
                    className="rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm focus:border-navy-600 focus:outline-none focus:ring-1 focus:ring-navy-600/40"
                  />
                </div>
                <div className="grid gap-1.5">
                  <label className="text-xs font-medium text-gray-700">Password (if no key)</label>
                  <input
                    type="password"
                    value={newConn.password}
                    onChange={(e) => setNewConn({ ...newConn, password: e.target.value })}
                    placeholder="optional"
                    className="rounded-md border border-gray-200 bg-white px-3 py-2 text-sm focus:border-navy-600 focus:outline-none focus:ring-1 focus:ring-navy-600/40"
                  />
                </div>
              </div>
              <div className="grid gap-1.5">
                <label className="text-xs font-medium text-gray-700">Default working directory</label>
                <input
                  value={newConn.work_dir}
                  onChange={(e) => setNewConn({ ...newConn, work_dir: e.target.value })}
                  placeholder="~"
                  className="rounded-md border border-gray-200 bg-white px-3 py-2 font-mono text-sm focus:border-navy-600 focus:outline-none focus:ring-1 focus:ring-navy-600/40"
                />
              </div>
              <p className="text-xs text-gray-400">
                Saved connections stay live alongside your others — no disconnect needed to switch clusters.
              </p>
              {addConnError && (
                <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{addConnError}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 border-t border-gray-100 px-5 py-3.5">
              <button
                onClick={() => setShowAddConn(false)}
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={submitAddConnection}
                disabled={addConnBusy}
                className="rounded-md bg-navy-600 px-4 py-2 text-sm font-medium text-white hover:bg-navy-800 disabled:opacity-50"
              >
                {addConnBusy ? 'Connecting…' : 'Save & connect'}
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}

export default TransferPage;
