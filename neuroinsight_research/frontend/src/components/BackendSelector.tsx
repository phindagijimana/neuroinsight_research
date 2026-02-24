/**
 * BackendSelector Component
 *
 * Independent data source & compute backend selector.
 *
 * Data Source row:  [Local] [Remote Server] [HPC] [Pennsieve] [XNAT]
 * Compute row:     [Local Docker] [Remote Server] [HPC/SLURM]
 *
 * Data source and compute are independent -- you can browse data on a
 * remote server while running jobs on an HPC cluster, for instance.
 * SSH connection is shared: when either data or compute points to a
 * remote host, the SSH form is shown and the connection serves both.
 */

import React, { useState, useEffect } from 'react';
import {
  Monitor, Server, AlertCircle, Loader2, Wifi,
  Settings2, Cloud, Database, Globe, CheckCircle2, KeyRound,
} from 'lucide-react';
import { apiService } from '../services/api';
import type { DataSourceType, PlatformConnection } from '../types';

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
  showPlatformTabs?: boolean;
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
  { id: 'remote',    backendId: 'remote',      label: 'Remote Server', icon: <Cloud className="h-3.5 w-3.5" />,   activeClass: 'border-green-600 bg-green-50 text-green-700',  hoverClass: 'hover:border-green-300' },
  { id: 'hpc',       backendId: 'remote_hpc',  label: 'HPC',           icon: <Server className="h-3.5 w-3.5" />,  activeClass: 'border-purple-600 bg-purple-50 text-purple-700', hoverClass: 'hover:border-purple-300' },
  { id: 'pennsieve', label: 'Pennsieve',       icon: <Database className="h-3.5 w-3.5" />, activeClass: 'border-blue-600 bg-blue-50 text-blue-700',    hoverClass: 'hover:border-blue-300' },
  { id: 'xnat',      label: 'XNAT',             icon: <Globe className="h-3.5 w-3.5" />,    activeClass: 'border-orange-600 bg-orange-50 text-orange-700', hoverClass: 'hover:border-orange-300' },
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
  showPlatformTabs = true,
}) => {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connected' | 'error'>('disconnected');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [host, setHost] = useState(sshConfig?.host || '');
  const [username, setUsername] = useState(sshConfig?.username || '');
  const [port, setPort] = useState(sshConfig?.port || 22);

  const [hpcConfig, setHpcConfig] = useState<HPCConfig>({
    workDir: '~', partition: 'general', account: '', qos: '', modules: '',
  });

  const [partitions, setPartitions] = useState<Array<{ name: string; timelimit: string; nodes: string }>>([]);

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
  const needsSSH = !isPlatformSelected && (dataSourceNeedsSSH || computeNeedsSSH);

  useEffect(() => { checkCurrentBackend(); }, []);

  useEffect(() => {
    if (onSSHConfigChange && (dataSourceNeedsSSH || computeNeedsSSH)) {
      onSSHConfigChange({ host, username, port });
    }
  }, [host, username, port, selectedBackend, dataSource]);

  const checkCurrentBackend = async () => {
    try {
      const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/backend/current`);
      const data = await resp.json();
      if (data.backend_type === 'slurm') {
        onBackendChange('remote_hpc');
        const statusResp = await fetch(`${apiService.getBaseUrl()}/api/hpc/status`);
        const status = await statusResp.json();
        if (status.connected) {
          setConnectionStatus('connected');
          if (status.host) setHost(status.host);
          if (status.username) setUsername(status.username);
          fetchPartitions();
        }
      } else if (data.backend_type === 'remote_docker') {
        onBackendChange('remote');
        const statusResp = await fetch(`${apiService.getBaseUrl()}/api/hpc/status`);
        const status = await statusResp.json();
        if (status.connected) {
          setConnectionStatus('connected');
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
        body: JSON.stringify({ host, username, port }),
      });
      const data = await resp.json();
      if (data.connected) {
        setConnectionStatus('connected');
        if (selectedBackend === 'remote_hpc') fetchPartitions();
        if (computeNeedsSSH) {
          switchToRemote(true);
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

  const switchToRemote = async (skipCheck = false) => {
    if (!skipCheck && connectionStatus !== 'connected') {
      setErrorMessage('Connect to the remote server first');
      return;
    }
    const backendType = selectedBackend === 'remote_hpc' ? 'slurm' : 'remote_docker';
    setIsSwitching(true);
    try {
      const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/backend/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          backend_type: backendType,
          ssh_host: host, ssh_user: username, ssh_port: port,
          work_dir: hpcConfig.workDir, partition: hpcConfig.partition,
          account: hpcConfig.account || null, qos: hpcConfig.qos || null,
          modules: hpcConfig.modules || null,
        }),
      });
      const data = await resp.json();
      if (resp.ok) {
        onBackendChange(selectedBackend === 'remote_hpc' ? 'remote_hpc' : 'remote');
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
      setConnectionStatus('disconnected');
    } catch {
      onBackendChange('local');
    } finally {
      setIsSwitching(false);
    }
  };

  const disconnect = async () => {
    try {
      await fetch(`${apiService.getBaseUrl()}/api/hpc/disconnect`, { method: 'POST' });
    } catch { /* ignore */ }
    setConnectionStatus('disconnected');
    setPartitions([]);
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

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 h-full flex flex-col">

      {/* Row 1: Data Source -- all 5 options */}
      {showPlatformTabs && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1.5">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Data Source</h3>
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
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Compute Source</h3>
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
                  } else if (tab.backendId) {
                    onBackendChange(tab.backendId);
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

      {/* Description line */}
      <p className="text-xs text-gray-500 mb-3">
        {isPlatformSelected && activeDataSource === 'pennsieve' && 'Browse and download data from Pennsieve, then process on chosen compute backend.'}
        {isPlatformSelected && activeDataSource === 'xnat' && 'Browse and download data from XNAT, then process on chosen compute backend.'}
        {!isPlatformSelected && dataSource === 'local' && selectedBackend === 'local' && 'Data and processing on this machine using Docker.'}
        {!isPlatformSelected && dataSource === 'local' && selectedBackend === 'remote' && 'Browse data locally, process on a remote Docker server via SSH.'}
        {!isPlatformSelected && dataSource === 'local' && selectedBackend === 'remote_hpc' && 'Browse data locally, process on HPC via SLURM.'}
        {!isPlatformSelected && dataSource === 'remote' && selectedBackend === 'local' && 'Browse data on remote server via SSH, process locally with Docker.'}
        {!isPlatformSelected && dataSource === 'remote' && selectedBackend === 'remote' && 'Data and processing on a remote SSH server.'}
        {!isPlatformSelected && dataSource === 'remote' && selectedBackend === 'remote_hpc' && 'Browse data on remote server, process on HPC via SLURM.'}
        {!isPlatformSelected && dataSource === 'hpc' && selectedBackend === 'local' && 'Browse data on HPC filesystem via SSH, process locally with Docker.'}
        {!isPlatformSelected && dataSource === 'hpc' && selectedBackend === 'remote' && 'Browse data on HPC filesystem, process on remote Docker server.'}
        {!isPlatformSelected && dataSource === 'hpc' && selectedBackend === 'remote_hpc' && 'Data and processing on HPC cluster via SLURM.'}
      </p>

      {/* SSH Configuration -- shown when either data source or compute needs SSH */}
      {needsSSH && (
        <div className="border-t border-gray-200 pt-3 mt-1 flex-1 overflow-y-auto">
          {connectionStatus === 'connected' && (
            <div className="flex items-center justify-between mb-3 px-2 py-1.5 bg-green-50 border border-green-200 rounded text-xs">
              <div className="flex items-center gap-1.5 text-green-700">
                <Wifi className="h-3.5 w-3.5" />
                <span>Connected to <strong>{host}</strong></span>
              </div>
              <button onClick={disconnect} className="text-green-600 hover:text-red-600 font-medium transition">
                Disconnect
              </button>
            </div>
          )}

          <div className="mb-3">
            <h4 className="text-xs font-semibold text-gray-700 mb-1 flex items-center gap-1.5">
              <Server className="h-3.5 w-3.5" />
              SSH Connection
            </h4>
            <p className="text-xs text-gray-500">
              Uses SSH agent authentication (<code className="text-xs bg-gray-100 px-1 rounded">ssh-add -l</code>)
            </p>
          </div>

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Hostname *</label>
              <input
                type="text" value={host} onChange={(e) => setHost(e.target.value)}
                placeholder="hpc.university.edu" disabled={connectionStatus === 'connected'}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Username *</label>
                <input
                  type="text" value={username} onChange={(e) => setUsername(e.target.value)}
                  placeholder="your_username" disabled={connectionStatus === 'connected'}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Port</label>
                <input
                  type="number" value={port} onChange={(e) => setPort(parseInt(e.target.value) || 22)}
                  placeholder="22" disabled={connectionStatus === 'connected'}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
                />
              </div>
            </div>

            {connectionStatus !== 'connected' && (
              <div className="flex items-center gap-2">
                <button
                  onClick={testConnection}
                  disabled={!host || !username || isConnecting}
                  className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium transition flex items-center gap-1.5"
                >
                  {isConnecting ? (<><Loader2 className="h-3.5 w-3.5 animate-spin" />Connecting...</>) : 'Connect'}
                </button>
                {connectionStatus === 'error' && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs bg-red-50 text-red-700">
                    <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                    <span className="truncate max-w-[200px]">{errorMessage}</span>
                  </div>
                )}
              </div>
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
                    {isSwitching ? (<><Loader2 className="h-4 w-4 animate-spin" />Activating...</>) : (
                      <>{selectedBackend === 'remote_hpc' ? <Server className="h-4 w-4" /> : <Cloud className="h-4 w-4" />}
                        {selectedBackend === 'remote_hpc' ? 'Activate SLURM Backend' : 'Activate Remote Docker'}</>
                    )}
                  </button>
                )}
              </>
            )}
          </div>

          <div className="mt-3 p-2 bg-navy-50 border border-navy-200 rounded">
            <p className="text-xs text-navy-700">
              <strong>Note:</strong> Uses SSH agent (no password). Load keys: <code className="bg-navy-100 px-1 rounded">ssh-add ~/.ssh/id_rsa</code>
            </p>
          </div>
        </div>
      )}

      {/* Cross-system info: data and compute on different systems */}
      {!isPlatformSelected && dataSource !== 'local' && selectedBackend === 'local' && dataSourceNeedsSSH && (
        <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded">
          <p className="text-xs text-amber-700">
            <strong>Note:</strong> Data is on a remote host but compute is local.
            Input paths must be accessible from this machine (e.g. NFS mount) or files will be downloaded before processing.
          </p>
        </div>
      )}
      {!isPlatformSelected && dataSource === 'local' && computeNeedsSSH && (
        <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded">
          <p className="text-xs text-amber-700">
            <strong>Note:</strong> Data is local but compute is remote.
            Input files will be uploaded to the remote host before processing.
          </p>
        </div>
      )}
      {!isPlatformSelected && dataSourceNeedsSSH && computeNeedsSSH && dataSource !== (selectedBackend === 'remote_hpc' ? 'hpc' : 'remote') && (
        <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded">
          <p className="text-xs text-amber-700">
            <strong>Note:</strong> Data source and compute are on different remote systems.
            The SSH connection is shared &mdash; input paths must be accessible from the compute server (e.g. shared NFS filesystem).
          </p>
        </div>
      )}

      {/* Local backend info */}
      {!isPlatformSelected && selectedBackend === 'local' && !dataSourceNeedsSSH && (
        <div className="border-t border-gray-200 pt-3 mt-1">
          <div className="flex items-center gap-1.5 text-xs text-gray-600">
            <Monitor className="h-3.5 w-3.5" />
            <span>Jobs run on this machine using Docker containers. No HPC scheduling.</span>
          </div>
        </div>
      )}

      {/* Platform auth forms (Pennsieve / XNAT) */}
      {isPlatformSelected && !isPlatformConnected && (
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
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Secret</label>
                <input type="password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)}
                  placeholder="Enter API secret"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-blue-500" />
              </div>
              <p className="text-xs text-gray-400">
                Find your API keys at <a href="https://app.pennsieve.io" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">app.pennsieve.io</a> &rarr; User Menu &rarr; API Keys
              </p>
            </>
          )}

          {dataSource === 'xnat' && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">XNAT URL</label>
                <input type="text" value={xnatUrl} onChange={(e) => setXnatUrl(e.target.value)}
                  placeholder="https://xnat.example.edu"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-orange-500" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Username</label>
                  <input type="text" value={xnatUser} onChange={(e) => setXnatUser(e.target.value)}
                    placeholder="username"
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-orange-500" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
                  <input type="password" value={xnatPass} onChange={(e) => setXnatPass(e.target.value)}
                    placeholder="password"
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-orange-500" />
                </div>
              </div>
              <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={xnatSkipSsl}
                  onChange={(e) => setXnatSkipSsl(e.target.checked)}
                  className="rounded border-gray-300 text-orange-500 focus:ring-orange-500 h-3.5 w-3.5"
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
            className="w-full px-3 py-2 text-sm bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] disabled:bg-gray-300 font-medium transition flex items-center justify-center gap-2"
          >
            {platformConnecting ? (<><Loader2 className="h-4 w-4 animate-spin" /> Connecting...</>) : 'Connect'}
          </button>
        </div>
      )}

      {/* Platform connected status */}
      {isPlatformSelected && isPlatformConnected && (
        <div className="border-t border-gray-200 pt-3 mt-1">
          <div className="flex items-center justify-between px-2 py-1.5 bg-green-50 border border-green-200 rounded text-xs">
            <div className="flex items-center gap-1.5 text-green-700">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>
                Connected to <strong>{platformConnection?.workspace || dataSource}</strong>
                {platformConnection?.user && <> as {platformConnection.user}</>}
              </span>
            </div>
            <button onClick={handlePlatformDisconnect} className="text-green-600 hover:text-red-600 font-medium transition">
              Disconnect
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
