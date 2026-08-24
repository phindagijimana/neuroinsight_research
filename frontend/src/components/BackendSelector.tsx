/**
 * BackendSelector Component
 *
 * Data source & compute backend selector.
 *
 * Data Source row:  [Local] [Remote Server] [HPC] [Pennsieve] [XNAT]
 * Compute row:     [Local Docker] [Remote Server] [HPC/SLURM]
 *
 * You pick where to browse/select input and where to run jobs independently,
 * but processing always uses filesystem paths on the compute side. Pennsieve and
 * XNAT selections are downloaded (or curled directly to HPC) before submit.
 * Local/remote/HPC filesystem inputs must already be visible to the chosen compute.
 */

import React, { useState, useEffect } from 'react';
import {
  Monitor, Server, AlertCircle, Wifi,
  Settings2, Cloud, Database, Globe, CheckCircle2, KeyRound, ChevronDown,
} from 'lucide-react';
import { apiService } from '../services/api';
import type { DataSourceType, PlatformConnection } from '../types';
import { Spinner } from './LoadingState';
import { USER_GUIDE_URL } from '../userGuide';

export type BackendType = 'local' | 'remote' | 'remote_hpc';

export interface SSHConfig {
  host: string;
  username: string;
  port: number;
}

interface BackendSelectorProps {
  selectedBackend: BackendType;
  onBackendChange: (backend: BackendType) => void;
  sshConfig?: SSHConfig;
  onSSHConfigChange?: (config: SSHConfig) => void;
  dataSource?: DataSourceType;
  onDataSourceChange?: (source: DataSourceType) => void;
  platformConnection?: PlatformConnection | null;
  onPlatformConnect?: (conn: PlatformConnection) => void;
  onPlatformDisconnect?: () => void;
  /** Fired when SSH connect/disconnect state changes (remote / HPC). */
  onSSHConnectionChange?: (connected: boolean) => void;
  showPlatformTabs?: boolean;
  /** Compute row + SSH only (platform transfer step). */
  computeOnly?: boolean;
  /** Jobs page: compute-only; SSH follows selected compute tab only. */
  jobsMode?: boolean;
}

interface HPCConfig {
  workDir: string;
  partition: string;
  account: string;
  qos: string;
  modules: string;
}

const TABS: { id: DataSourceType; backendId?: BackendType; label: string; icon: React.ReactNode; activeClass: string; hoverClass: string }[] = [
  { id: 'local',     backendId: 'local',      label: 'Local',         icon: <Monitor className="h-3.5 w-3.5" />, activeClass: 'border-navy-600 bg-navy-50 text-navy-700',     hoverClass: 'hover:border-navy-300' },
  { id: 'remote',    backendId: 'remote',      label: 'Remote Server', icon: <Cloud className="h-3.5 w-3.5" />,   activeClass: 'border-navy-600 bg-navy-50 text-navy-700',  hoverClass: 'hover:border-navy-300' },
  { id: 'hpc',       backendId: 'remote_hpc',  label: 'HPC',           icon: <Server className="h-3.5 w-3.5" />,  activeClass: 'border-navy-600 bg-navy-50 text-navy-700', hoverClass: 'hover:border-navy-300' },
  { id: 'pennsieve', label: 'Pennsieve',       icon: <Database className="h-3.5 w-3.5" />, activeClass: 'border-navy-600 bg-navy-50 text-navy-700',    hoverClass: 'hover:border-navy-300' },
  { id: 'xnat',      label: 'XNAT',             icon: <Globe className="h-3.5 w-3.5" />,    activeClass: 'border-navy-600 bg-navy-50 text-navy-700', hoverClass: 'hover:border-navy-300' },
];

export const BackendSelector: React.FC<BackendSelectorProps> = ({
  selectedBackend,
  onBackendChange,
  sshConfig,
  onSSHConfigChange,
  dataSource = 'local',
  onDataSourceChange,
  platformConnection,
  onPlatformConnect,
  onPlatformDisconnect,
  onSSHConnectionChange,
  showPlatformTabs = true,
  computeOnly = false,
  jobsMode = false,
}) => {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connected' | 'error'>('disconnected');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [sshExpanded, setSshExpanded] = useState(false);

  const [host, setHost] = useState(sshConfig?.host || '');
  const [username, setUsername] = useState(sshConfig?.username || '');
  const [port, setPort] = useState(sshConfig?.port || 22);
  // Saved hosts from ~/.ssh/config (the alias picker).
  const [sshHosts, setSshHosts] = useState<Array<{ alias: string; hostname: string; user: string; port: number }>>([]);
  // Password for clusters that reject keys and need password + Duo (e.g. BlueHive).
  // Optional: blank uses your SSH key / agent. Never persisted.
  const [password, setPassword] = useState('');

  const [hpcConfig, setHpcConfig] = useState<HPCConfig>({
    workDir: '~', partition: 'general', account: '', qos: '', modules: '',
  });

  const [partitions, setPartitions] = useState<Array<{ name: string; timelimit: string; nodes: string }>>([]);
  /** Active execution backend on the server (may differ from selected tab until switch). */
  const [activeServerBackend, setActiveServerBackend] = useState<'local' | 'remote_docker' | 'slurm'>('local');

  // Platform auth state
  const [platformConnecting, setPlatformConnecting] = useState(false);
  const [platformError, setPlatformError] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [xnatUrl, setXnatUrl] = useState('');
  const [xnatUser, setXnatUser] = useState('');
  const [xnatPass, setXnatPass] = useState('');
  const [xnatSkipSsl, setXnatSkipSsl] = useState(false);

  const isPlatformSelected = dataSource === 'pennsieve' || dataSource === 'xnat';
  const isPlatformConnected = platformConnection?.connected && platformConnection?.platform === dataSource;

  const activeDataSource = dataSource;
  const dataSourceNeedsSSH = dataSource === 'remote' || dataSource === 'hpc';
  const computeNeedsSSH = selectedBackend === 'remote' || selectedBackend === 'remote_hpc';
  const needsSSH = jobsMode
    ? computeNeedsSSH
    : !isPlatformSelected && (dataSourceNeedsSSH || computeNeedsSSH);

  const sshPanelTitle =
    selectedBackend === 'remote_hpc'
      ? 'HPC (SLURM) connection'
      : selectedBackend === 'remote'
        ? 'Remote Server (Docker) connection'
        : 'SSH Connection';

  const sshConnectPrompt =
    selectedBackend === 'remote_hpc'
      ? 'Connect SSH for HPC (SLURM)'
      : selectedBackend === 'remote'
        ? 'Connect SSH for Remote Server (Docker)'
        : 'Connect SSH to browse or run jobs remotely';

  const setSSHConnected = (value: boolean) => {
    setConnectionStatus(value ? 'connected' : 'disconnected');
    onSSHConnectionChange?.(value);
  };

  useEffect(() => { checkCurrentBackend(); }, []);

  // Load saved Host aliases from ~/.ssh/config once SSH is needed.
  useEffect(() => {
    if (needsSSH && sshHosts.length === 0) {
      apiService.getSshHosts().then(setSshHosts).catch(() => {});
    }
  }, [needsSSH]);

  // Expand SSH form when remote/HPC is selected so Connect is visible immediately.
  useEffect(() => {
    if (needsSSH && connectionStatus !== 'connected') {
      setSshExpanded(true);
    } else if (!needsSSH) {
      setSshExpanded(false);
    }
  }, [needsSSH, activeDataSource, selectedBackend, connectionStatus]);

  const applySshAlias = (alias: string) => {
    const h = sshHosts.find((x) => x.alias === alias);
    if (!h) return;
    setHost(h.hostname);
    if (h.user) setUsername(h.user);
    if (h.port) setPort(h.port);
  };

  useEffect(() => {
    if (onSSHConfigChange && (dataSourceNeedsSSH || computeNeedsSSH)) {
      onSSHConfigChange({ host, username, port });
    }
  }, [host, username, port, selectedBackend, dataSource]);

  const checkCurrentBackend = async () => {
    try {
      const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/backend/current`);
      const data = await resp.json();
      const serverType = data.backend_type as 'local' | 'remote_docker' | 'slurm';
      if (serverType === 'local' || serverType === 'remote_docker' || serverType === 'slurm') {
        setActiveServerBackend(serverType);
      }
      if (data.backend_type === 'slurm') {
        onBackendChange('remote_hpc');
        const statusResp = await fetch(`${apiService.getBaseUrl()}/api/hpc/status`);
        const status = await statusResp.json();
        if (status.connected) {
          setSSHConnected(true);
          if (status.host) setHost(status.host);
          if (status.username) setUsername(status.username);
          fetchPartitions();
        }
      } else if (data.backend_type === 'remote_docker') {
        onBackendChange('remote');
        const statusResp = await fetch(`${apiService.getBaseUrl()}/api/hpc/status`);
        const status = await statusResp.json();
        if (status.connected) {
          setSSHConnected(true);
          if (status.host) setHost(status.host);
          if (status.username) setUsername(status.username);
        }
      } else {
        const statusResp = await fetch(`${apiService.getBaseUrl()}/api/hpc/status`);
        const status = await statusResp.json();
        if (status.connected) {
          setSSHConnected(true);
          if (status.host) setHost(status.host);
          if (status.username) setUsername(status.username);
        }
      }
    } catch { /* default to local */ }
  };

  const testConnection = async () => {
    setIsConnecting(true);
    setErrorMessage('');
    try {
      if (!host || !username) throw new Error('Host and username are required');
      const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host, username, port, password: password || null }),
      });
      const data = await resp.json();
      if (data.connected) {
        setSSHConnected(true);
        setSshExpanded(true);
        if (selectedBackend === 'remote_hpc') fetchPartitions();
        if (computeNeedsSSH) {
          switchToRemote(true, selectedBackend);
        }
      } else {
        setConnectionStatus('error');
        setErrorMessage(data.message || 'Connection failed');
      }
    } catch (error: any) {
      setConnectionStatus('error');
      setErrorMessage(error.message || 'Connection failed');
    } finally {
      setIsConnecting(false);
    }
  };

  const fetchPartitions = async () => {
    try {
      const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/partitions`);
      if (resp.ok) {
        const data = await resp.json();
        setPartitions(data.partitions || []);
        if (data.partitions?.length > 0 && !hpcConfig.partition) {
          const defaultPartition = data.partitions.find((p: any) => p.is_default)?.name || data.partitions[0].name;
          setHpcConfig(prev => ({ ...prev, partition: defaultPartition }));
        }
      }
    } catch { /* ignore */ }
  };

  const switchToRemote = async (skipCheck = false, backendOverride?: BackendType) => {
    if (!skipCheck && connectionStatus !== 'connected') {
      setErrorMessage('Connect to the remote server first');
      return;
    }
    const target = backendOverride ?? selectedBackend;
    const backendType = target === 'remote_hpc' ? 'slurm' : 'remote_docker';
    setIsSwitching(true);
    try {
      const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/backend/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          backend_type: backendType,
          ssh_host: host, ssh_user: username, ssh_port: port,
          ssh_password: password || null,
          work_dir: hpcConfig.workDir, partition: hpcConfig.partition,
          account: hpcConfig.account || null, qos: hpcConfig.qos || null,
          modules: hpcConfig.modules || null,
        }),
      });
      const data = await resp.json();
      if (resp.ok) {
        setActiveServerBackend(backendType);
        onBackendChange(target === 'remote_hpc' ? 'remote_hpc' : 'remote');
        if (backendType === 'slurm') fetchPartitions();
      } else {
        setErrorMessage(data.detail || 'Failed to switch backend');
      }
    } catch (error: any) {
      setErrorMessage(error.message || 'Failed to switch backend');
    } finally {
      setIsSwitching(false);
    }
  };

  const switchToLocal = async () => {
    setIsSwitching(true);
    try {
      await fetch(`${apiService.getBaseUrl()}/api/hpc/backend/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ backend_type: 'local' }),
      });
      onBackendChange('local');
      setSSHConnected(false);
      setActiveServerBackend('local');
    } catch {
      onBackendChange('local');
      setSSHConnected(false);
      setActiveServerBackend('local');
    } finally {
      setIsSwitching(false);
    }
  };

  const disconnect = async () => {
    try {
      await fetch(`${apiService.getBaseUrl()}/api/hpc/disconnect`, { method: 'POST' });
    } catch { /* ignore */ }
    setSSHConnected(false);
    setPartitions([]);
    setActiveServerBackend('local');
  };

  const handleTabClick = (tab: typeof TABS[0]) => {
    setPlatformError(null);
    if (onDataSourceChange) onDataSourceChange(tab.id);
  };

  const handlePlatformConnect = async () => {
    setPlatformConnecting(true);
    setPlatformError(null);
    try {
      let result;
      if (dataSource === 'pennsieve') {
        if (!apiKey || !apiSecret) { setPlatformError('API Key and Secret are required'); setPlatformConnecting(false); return; }
        result = await apiService.platformConnect('pennsieve', { api_key: apiKey, api_secret: apiSecret });
      } else if (dataSource === 'xnat') {
        if (!xnatUrl || !xnatUser || !xnatPass) { setPlatformError('URL, username, and password are required'); setPlatformConnecting(false); return; }
        result = await apiService.platformConnect('xnat', { url: xnatUrl, username: xnatUser, password: xnatPass, verify_ssl: !xnatSkipSsl });
      }
      if (result?.connected && onPlatformConnect) {
        onPlatformConnect({ platform: dataSource, connected: true, user: result.user, workspace: result.workspace });
      } else {
        setPlatformError('Connection failed');
      }
    } catch (err: any) {
      setPlatformError(err.response?.data?.detail || err.message || 'Connection failed');
    } finally {
      setPlatformConnecting(false);
    }
  };

  const handlePlatformDisconnect = async () => {
    try { await apiService.platformDisconnect(dataSource); } catch { /* ignore */ }
    if (onPlatformDisconnect) onPlatformDisconnect();
  };

  const backendTabs = TABS.filter(t => t.backendId);

  const serverModeLabel = (() => {
    if (activeServerBackend === 'slurm') return 'HPC (SLURM)';
    if (activeServerBackend === 'remote_docker') return 'Remote Server (Docker)';
    if (connectionStatus === 'connected') return 'SSH only (browse files; compute is local)';
    return '';
  })();

  return (
    <div
      className={`rounded-xl border border-gray-100 flex flex-col shadow-sm h-full ${
        jobsMode
          ? 'bg-white p-5 min-h-[18rem]'
          : 'bg-slate-50/40 p-4'
      }`}
    >

      {/* Row 1: Data Source -- all 5 options */}
      {showPlatformTabs && !computeOnly && !jobsMode && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1.5">
            <h3 className="text-xs font-semibold text-gray-500 tracking-wider">Data Source</h3>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {TABS.map((tab) => {
              const isActive = activeDataSource === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => handleTabClick(tab)}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border transition-all text-xs ${
                    isActive ? tab.activeClass : `border-gray-300 bg-white text-gray-600 ${tab.hoverClass}`
                  }`}
                >
                  {tab.icon}
                  <span className="font-medium">{tab.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Row 2: Compute Source -- Local / Remote / HPC */}
      <div className={showPlatformTabs ? 'mb-2' : 'mb-3'}>
        <div className="flex items-center justify-between mb-1.5">
          <h3 className="text-xs font-semibold text-gray-500 tracking-wider">Compute Source</h3>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {backendTabs.map((tab) => {
            const isActive = selectedBackend === tab.backendId;
            return (
              <button
                key={tab.id}
                onClick={() => {
                  if (tab.backendId === 'local' && selectedBackend !== 'local') {
                    switchToLocal();
                  } else if (tab.backendId && tab.backendId !== selectedBackend) {
                    onBackendChange(tab.backendId);
                    if (connectionStatus === 'connected') {
                      switchToRemote(true, tab.backendId);
                    }
                  }
                }}
                disabled={isSwitching}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border transition-all text-xs ${
                  isActive ? tab.activeClass : `border-gray-300 bg-white text-gray-600 ${tab.hoverClass}`
                }`}
              >
                {tab.icon}
                <span className="font-medium">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* SSH Configuration -- shown when either data source or compute needs SSH */}
      {needsSSH && (
        <div className="border-t border-gray-200 pt-3 mt-1">
          {connectionStatus === 'connected' ? (
            <div className="space-y-1.5">
              <div className="flex items-center justify-between gap-2 px-2 py-1.5 bg-green-50 border border-green-200 rounded text-xs">
                <div className="flex items-center gap-1.5 text-green-700 min-w-0">
                  <Wifi className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate">
                    Connected to <strong>{host}</strong>
                    {serverModeLabel && <> · {serverModeLabel}</>}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => setSshExpanded((open) => !open)}
                    className="text-green-700 hover:text-navy-700 font-medium transition flex items-center gap-0.5"
                  >
                    {sshExpanded ? 'Hide' : 'Settings'}
                    <ChevronDown className={`h-3 w-3 transition-transform ${sshExpanded ? 'rotate-180' : ''}`} />
                  </button>
                  <button onClick={disconnect} className="text-green-600 hover:text-red-600 font-medium transition">
                    Disconnect
                  </button>
                </div>
              </div>
              {(jobsMode ? computeNeedsSSH : dataSource === 'remote' || dataSource === 'hpc') && (
                <p className="text-[10px] text-gray-500 px-1">
                  Remote Server and HPC share this SSH session to the same host.
                  Disconnect and reconnect to use a different machine.
                </p>
              )}
            </div>
          ) : !sshExpanded ? (
            <button
              type="button"
              onClick={() => setSshExpanded(true)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 transition"
            >
              <span className="flex items-center gap-1.5">
                <Server className="h-3.5 w-3.5 text-navy-600" />
                {sshConnectPrompt}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
            </button>
          ) : null}

          {sshExpanded && (
        <div className="mt-3 flex-1 overflow-y-auto nir-scroll-list">
          {connectionStatus !== 'connected' && (
            <>
          <div className="mb-3">
            <h4 className="text-xs font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
              <Server className="h-3.5 w-3.5" />
              {jobsMode ? sshPanelTitle : 'SSH Connection'}
            </h4>
          </div>

          {selectedBackend === 'remote_hpc' && (
            <p className="mb-3 text-xs text-gray-500">
              On a private network? Connect VPN first.{' '}
              <a href={USER_GUIDE_URL} target="_blank" rel="noreferrer" className="text-navy-600 hover:underline">
                Connecting to HPC →
              </a>
            </p>
          )}
            </>
          )}

          <div className="space-y-3">
            {connectionStatus !== 'connected' && (
              <>
            {sshHosts.length > 0 && (
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Saved host (from ~/.ssh/config)</label>
                <select
                  defaultValue=""
                  onChange={(e) => applySshAlias(e.target.value)}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md bg-white focus:ring-1 focus:ring-green-500 focus:border-transparent"
                >
                  <option value="">— pick a saved host or enter manually —</option>
                  {sshHosts.map((h) => (
                    <option key={h.alias} value={h.alias}>
                      {h.alias} ({h.user ? `${h.user}@` : ''}{h.hostname})
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Hostname *</label>
              <input
                type="text" value={host} onChange={(e) => setHost(e.target.value)}
                placeholder="hpc.university.edu"
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Username *</label>
                <input
                  type="text" value={username} onChange={(e) => setUsername(e.target.value)}
                  placeholder="your_username"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Port</label>
                <input
                  type="number" value={port} onChange={(e) => setPort(parseInt(e.target.value) || 22)}
                  placeholder="22"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent"
                />
              </div>
            </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Password <span className="text-gray-400 font-normal">— only if your cluster uses password/Duo</span>
                </label>
                <input
                  type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                  placeholder="leave blank to use your SSH key"
                  autoComplete="off"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent"
                />
                {password && (
                  <p className="text-xs text-gray-500 mt-1">A Duo push may appear on your phone — approve it to finish connecting.</p>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={testConnection}
                  disabled={!host || !username || isConnecting}
                  className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium transition flex items-center gap-1.5"
                >
                  {isConnecting ? (<><Spinner size="sm" />Connecting...</>) : 'Connect'}
                </button>
                {connectionStatus === 'error' && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs bg-red-50 text-red-700">
                    <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                    <span className="truncate max-w-[200px]">{errorMessage}</span>
                  </div>
                )}
              </div>
              </>
            )}

            {connectionStatus === 'connected' && (
              <>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Work Directory</label>
                  <input
                    type="text" value={hpcConfig.workDir}
                    onChange={(e) => setHpcConfig(prev => ({ ...prev, workDir: e.target.value }))}
                    placeholder="~ or /scratch/username or /home/username"
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md"
                  />
                </div>

                {selectedBackend === 'remote_hpc' && (
                  <>
                    <button
                      onClick={() => setShowAdvanced(!showAdvanced)}
                      className="flex items-center gap-1.5 text-xs text-gray-600 hover:text-navy-700 font-medium"
                    >
                      <Settings2 className="h-3.5 w-3.5" />
                      {showAdvanced ? 'Hide' : 'Show'} SLURM Settings
                    </button>

                    {showAdvanced && (
                      <div className="space-y-2 p-2 bg-gray-50 rounded border border-gray-200">
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Partition</label>
                          {partitions.length > 0 ? (
                            <select
                              value={hpcConfig.partition}
                              onChange={(e) => setHpcConfig(prev => ({ ...prev, partition: e.target.value }))}
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md"
                            >
                              {partitions.map(p => (
                                <option key={p.name} value={p.name}>
                                  {p.name} ({p.timelimit}, {p.nodes} nodes)
                                </option>
                              ))}
                            </select>
                          ) : (
                            <input
                              type="text" value={hpcConfig.partition}
                              onChange={(e) => setHpcConfig(prev => ({ ...prev, partition: e.target.value }))}
                              placeholder="general"
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md"
                            />
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">Account</label>
                            <input type="text" value={hpcConfig.account}
                              onChange={(e) => setHpcConfig(prev => ({ ...prev, account: e.target.value }))}
                              placeholder="Optional" className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md" />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">QoS</label>
                            <input type="text" value={hpcConfig.qos}
                              onChange={(e) => setHpcConfig(prev => ({ ...prev, qos: e.target.value }))}
                              placeholder="Optional" className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md" />
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Modules (comma-separated)</label>
                          <input type="text" value={hpcConfig.modules}
                            onChange={(e) => setHpcConfig(prev => ({ ...prev, modules: e.target.value }))}
                            placeholder="singularity/3.8, cuda/11.8"
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md" />
                        </div>
                      </div>
                    )}
                  </>
                )}

                {computeNeedsSSH && (
                  <button
                    onClick={() => switchToRemote()} disabled={isSwitching}
                    className="w-full px-3 py-2 text-sm bg-navy-600 text-white rounded-md hover:bg-navy-700 disabled:bg-gray-300 font-medium transition flex items-center justify-center gap-2"
                  >
                    {isSwitching ? (<><Spinner size="sm" />Activating...</>) : (
                      <>{selectedBackend === 'remote_hpc' ? <Server className="h-4 w-4" /> : <Cloud className="h-4 w-4" />}
                        {selectedBackend === 'remote_hpc' ? 'Activate SLURM' : 'Activate Remote'}</>
                    )}
                  </button>
                )}
              </>
            )}
          </div>
          {connectionStatus !== 'connected' && (
            <button
              type="button"
              onClick={() => setSshExpanded(false)}
              className="mt-3 text-xs text-gray-500 hover:text-gray-700"
            >
              Cancel
            </button>
          )}
        </div>
          )}
        </div>
      )}

      {/* Platform auth forms (Pennsieve / XNAT) */}
      {!computeOnly && !jobsMode && isPlatformSelected && !isPlatformConnected && (
        <div className="border-t border-gray-200 pt-3 mt-1 space-y-3">
          <h4 className="text-xs font-semibold text-gray-700 flex items-center gap-1.5">
            <KeyRound className="h-3.5 w-3.5" />
            {dataSource === 'pennsieve' ? 'Pennsieve API Credentials' : 'XNAT Login'}
          </h4>

          {dataSource === 'pennsieve' && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Key</label>
                <input type="text" value={apiKey} onChange={(e) => setApiKey(e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-navy-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Secret</label>
                <input type="password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)}
                  placeholder="Enter API secret"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-navy-500" />
              </div>
              <p className="text-xs text-gray-400">
                Find your API keys at <a href="https://app.pennsieve.io" target="_blank" rel="noopener noreferrer" className="text-navy-600 underline">app.pennsieve.io</a> &rarr; User Menu &rarr; API Keys
              </p>
            </>
          )}

          {dataSource === 'xnat' && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">XNAT URL</label>
                <input type="text" value={xnatUrl} onChange={(e) => setXnatUrl(e.target.value)}
                  placeholder="https://xnat.example.edu"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-navy-500" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Username</label>
                  <input type="text" value={xnatUser} onChange={(e) => setXnatUser(e.target.value)}
                    placeholder="username"
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-navy-500" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
                  <input type="password" value={xnatPass} onChange={(e) => setXnatPass(e.target.value)}
                    placeholder="password"
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-navy-500" />
                </div>
              </div>
              <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={xnatSkipSsl}
                  onChange={(e) => setXnatSkipSsl(e.target.checked)}
                  className="rounded border-gray-300 text-navy-500 focus:ring-navy-500 h-3.5 w-3.5"
                />
                Skip SSL verification (for tunneled or self-signed connections)
              </label>
            </>
          )}

          {platformError && (
            <div className="flex items-center gap-1.5 text-xs text-red-600 bg-red-50 px-2 py-1.5 rounded">
              <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
              <span>{platformError}</span>
            </div>
          )}

          <button
            onClick={handlePlatformConnect} disabled={platformConnecting}
            className="w-full px-3 py-2 text-sm bg-navy-600 text-white rounded-md hover:bg-navy-800 disabled:bg-gray-300 font-medium transition flex items-center justify-center gap-2"
          >
            {platformConnecting ? (<><Spinner size="sm" /> Connecting...</>) : 'Connect'}
          </button>
        </div>
      )}

      {/* Platform connected status */}
      {isPlatformSelected && isPlatformConnected && !jobsMode && (
        <div className="border-t border-gray-200 pt-3 mt-1">
          <div className="flex items-center justify-between px-2 py-1.5 bg-green-50 border border-green-200 rounded text-xs">
            <div className="flex items-center gap-1.5 text-green-700">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>
                Connected to <strong>{platformConnection?.workspace || dataSource}</strong>
                {platformConnection?.user && <> as {platformConnection.user}</>}
              </span>
            </div>
            <button onClick={handlePlatformDisconnect} className="text-green-600 hover:text-red-600 font-medium transition" title="Clear saved credentials and end session">
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
