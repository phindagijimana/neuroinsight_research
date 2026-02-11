/**
 * BackendSelector Component
 * 
 * Allows users to select between three execution backends:
 *   1. Local (Docker on this machine)
 *   2. Remote Server (Docker over SSH -- EC2, cloud VMs, any Linux)
 *   3. Remote HPC (SLURM scheduler via SSH -- university clusters)
 * 
 * For Remote modes, provides SSH connection configuration and test.
 * Wired to real backend API endpoints at /api/hpc/*.
 */

import React, { useState, useEffect } from 'react';
import { Monitor, Server, AlertCircle, Loader2, Wifi, Settings2, Cloud } from 'lucide-react';
import { apiService } from '../services/api';

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
}

// HPC configuration state
interface HPCConfig {
  workDir: string;
  partition: string;
  account: string;
  qos: string;
  modules: string;
}

export const BackendSelector: React.FC<BackendSelectorProps> = ({
  selectedBackend,
  onBackendChange,
  sshConfig,
  onSSHConfigChange,
}) => {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isSwitching, setIsSwitching] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connected' | 'error'>('disconnected');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Local SSH config state
  const [host, setHost] = useState(sshConfig?.host || '');
  const [username, setUsername] = useState(sshConfig?.username || '');
  const [port, setPort] = useState(sshConfig?.port || 22);

  // HPC-specific config
  const [hpcConfig, setHpcConfig] = useState<HPCConfig>({
    workDir: '/scratch',
    partition: 'general',
    account: '',
    qos: '',
    modules: '',
  });

  // Available partitions (fetched after connection)
  const [partitions, setPartitions] = useState<Array<{ name: string; timelimit: string; nodes: string }>>([]);

  // Check current backend status on mount
  useEffect(() => {
    checkCurrentBackend();
  }, []);

  // Update parent when SSH config changes
  useEffect(() => {
    if (onSSHConfigChange && (selectedBackend === 'remote' || selectedBackend === 'remote_hpc')) {
      onSSHConfigChange({ host, username, port });
    }
  }, [host, username, port, selectedBackend]);

  const checkCurrentBackend = async () => {
    try {
      const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/backend/current`);
      const data = await resp.json();
      if (data.backend_type === 'slurm') {
        onBackendChange('remote_hpc');
        // Check SSH status
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
    } catch {
      // Backend not available, default to local
    }
  };

  const testConnection = async () => {
    setIsConnecting(true);
    setErrorMessage('');

    try {
      if (!host || !username) {
        throw new Error('Host and username are required');
      }

      const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host, username, port }),
      });
      const data = await resp.json();

      if (data.connected) {
        setConnectionStatus('connected');
        // Only fetch SLURM partitions for HPC mode
        if (selectedBackend === 'remote_hpc') {
          fetchPartitions();
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
        // Auto-select first partition if none set
        if (data.partitions?.length > 0 && !hpcConfig.partition) {
          const defaultPartition = data.partitions.find((p: any) => p.is_default)?.name || data.partitions[0].name;
          setHpcConfig(prev => ({ ...prev, partition: defaultPartition }));
        }
      }
    } catch {
      // Partitions endpoint may not be available if not on SLURM yet
    }
  };

  const switchToRemote = async () => {
    if (connectionStatus !== 'connected') {
      setErrorMessage('Connect to the remote server first');
      return;
    }

    // Determine which backend type to request
    const backendType = selectedBackend === 'remote_hpc' ? 'slurm' : 'remote_docker';

    setIsSwitching(true);
    try {
      const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/backend/switch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          backend_type: backendType,
          ssh_host: host,
          ssh_user: username,
          ssh_port: port,
          work_dir: hpcConfig.workDir,
          partition: hpcConfig.partition,
          account: hpcConfig.account || null,
          qos: hpcConfig.qos || null,
          modules: hpcConfig.modules || null,
        }),
      });
      const data = await resp.json();
      if (resp.ok) {
        onBackendChange('remote');
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
      // Switch locally anyway
      onBackendChange('local');
    } finally {
      setIsSwitching(false);
    }
  };

  const disconnect = async () => {
    try {
      await fetch(`${apiService.getBaseUrl()}/api/hpc/disconnect`, { method: 'POST' });
    } catch {
      // Ignore errors
    }
    setConnectionStatus('disconnected');
    setPartitions([]);
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Execution Backend</h3>
        <div className="flex gap-1.5">
          {/* Local Backend */}
          <button
            onClick={() => {
              if (selectedBackend !== 'local') switchToLocal();
            }}
            disabled={isSwitching}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border transition-all text-xs ${
              selectedBackend === 'local'
                ? 'border-navy-600 bg-navy-50 text-navy-700'
                : 'border-gray-300 bg-white text-gray-600 hover:border-gray-400'
            }`}
          >
            <Monitor className="h-3.5 w-3.5" />
            <span className="font-medium">Local</span>
          </button>

          {/* Remote Server (EC2, cloud VMs, any Linux) */}
          <button
            onClick={() => {
              if (selectedBackend !== 'remote') {
                onBackendChange('remote');
              }
            }}
            disabled={isSwitching}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border transition-all text-xs ${
              selectedBackend === 'remote'
                ? 'border-green-600 bg-green-50 text-green-700'
                : 'border-gray-300 bg-white text-gray-600 hover:border-gray-400'
            }`}
          >
            <Cloud className="h-3.5 w-3.5" />
            <span className="font-medium">Remote Server</span>
          </button>

          {/* Remote HPC (SLURM clusters) */}
          <button
            onClick={() => {
              if (selectedBackend !== 'remote_hpc') {
                onBackendChange('remote_hpc');
              }
            }}
            disabled={isSwitching}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border transition-all text-xs ${
              selectedBackend === 'remote_hpc'
                ? 'border-purple-600 bg-purple-50 text-purple-700'
                : 'border-gray-300 bg-white text-gray-600 hover:border-gray-400'
            }`}
          >
            <Server className="h-3.5 w-3.5" />
            <span className="font-medium">HPC (SLURM)</span>
          </button>
        </div>
      </div>

      {/* Backend description */}
      <p className="text-xs text-gray-500 mb-3">
        {selectedBackend === 'local' && 'Run jobs in Docker on this machine.'}
        {selectedBackend === 'remote' && 'Run jobs via Docker on any SSH server (AWS EC2, Google Cloud, Azure, etc.)'}
        {selectedBackend === 'remote_hpc' && 'Submit jobs to a SLURM scheduler on an HPC cluster.'}
      </p>

      {/* Remote Configuration (shown for both remote and remote_hpc) */}
      {(selectedBackend === 'remote' || selectedBackend === 'remote_hpc') && (
        <div className="border-t border-gray-200 pt-3 mt-1 flex-1 overflow-y-auto">
          {/* Connection Status Banner */}
          {connectionStatus === 'connected' && (
            <div className="flex items-center justify-between mb-3 px-2 py-1.5 bg-green-50 border border-green-200 rounded text-xs">
              <div className="flex items-center gap-1.5 text-green-700">
                <Wifi className="h-3.5 w-3.5" />
                <span>Connected to <strong>{host}</strong></span>
              </div>
              <button
                onClick={disconnect}
                className="text-green-600 hover:text-red-600 font-medium transition"
              >
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

          {/* SSH Configuration Form */}
          <div className="space-y-3">
            {/* Hostname */}
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Hostname *
              </label>
              <input
                type="text"
                value={host}
                onChange={(e) => setHost(e.target.value)}
                placeholder="hpc.university.edu"
                disabled={connectionStatus === 'connected'}
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
              />
            </div>

            {/* Username & Port */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Username *
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="your_username"
                  disabled={connectionStatus === 'connected'}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  Port
                </label>
                <input
                  type="number"
                  value={port}
                  onChange={(e) => setPort(parseInt(e.target.value) || 22)}
                  placeholder="22"
                  disabled={connectionStatus === 'connected'}
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
                />
              </div>
            </div>

            {/* Test Connection / Activate Buttons */}
            {connectionStatus !== 'connected' && (
              <div className="flex items-center gap-2">
                <button
                  onClick={testConnection}
                  disabled={!host || !username || isConnecting}
                  className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium transition flex items-center gap-1.5"
                >
                  {isConnecting ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    'Connect'
                  )}
                </button>

                {connectionStatus === 'error' && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded text-xs bg-red-50 text-red-700">
                    <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                    <span className="truncate max-w-[200px]">{errorMessage}</span>
                  </div>
                )}
              </div>
            )}

            {/* Advanced Settings (shown after connection) */}
            {connectionStatus === 'connected' && (
              <>
                {/* Work Directory -- applicable to both remote modes */}
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Work Directory
                  </label>
                  <input
                    type="text"
                    value={hpcConfig.workDir}
                    onChange={(e) => setHpcConfig(prev => ({ ...prev, workDir: e.target.value }))}
                    placeholder={selectedBackend === 'remote_hpc' ? '/scratch/username' : '/tmp/neuroinsight'}
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md"
                  />
                </div>

                {/* SLURM-only settings */}
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
                        {/* Partition */}
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
                              type="text"
                              value={hpcConfig.partition}
                              onChange={(e) => setHpcConfig(prev => ({ ...prev, partition: e.target.value }))}
                              placeholder="general"
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md"
                            />
                          )}
                        </div>

                        {/* Account & QoS */}
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">Account</label>
                            <input
                              type="text"
                              value={hpcConfig.account}
                              onChange={(e) => setHpcConfig(prev => ({ ...prev, account: e.target.value }))}
                              placeholder="Optional"
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">QoS</label>
                            <input
                              type="text"
                              value={hpcConfig.qos}
                              onChange={(e) => setHpcConfig(prev => ({ ...prev, qos: e.target.value }))}
                              placeholder="Optional"
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md"
                            />
                          </div>
                        </div>

                        {/* Modules */}
                        <div>
                          <label className="block text-xs font-medium text-gray-600 mb-1">Modules (comma-separated)</label>
                          <input
                            type="text"
                            value={hpcConfig.modules}
                            onChange={(e) => setHpcConfig(prev => ({ ...prev, modules: e.target.value }))}
                            placeholder="singularity/3.8, cuda/11.8"
                            className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md"
                          />
                        </div>
                      </div>
                    )}
                  </>
                )}

                {/* Activate Backend Button */}
                <button
                  onClick={switchToRemote}
                  disabled={isSwitching}
                  className="w-full px-3 py-2 text-sm bg-navy-600 text-white rounded-md hover:bg-navy-700 disabled:bg-gray-300 font-medium transition flex items-center justify-center gap-2"
                >
                  {isSwitching ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Activating...
                    </>
                  ) : (
                    <>
                      {selectedBackend === 'remote_hpc' ? (
                        <Server className="h-4 w-4" />
                      ) : (
                        <Cloud className="h-4 w-4" />
                      )}
                      {selectedBackend === 'remote_hpc' ? 'Activate SLURM Backend' : 'Activate Remote Docker'}
                    </>
                  )}
                </button>
              </>
            )}
          </div>

          {/* SSH Agent Info */}
          <div className="mt-3 p-2 bg-navy-50 border border-navy-200 rounded">
            <p className="text-xs text-navy-700">
              <strong>Note:</strong> Uses SSH agent (no password). Load keys: <code className="bg-navy-100 px-1 rounded">ssh-add ~/.ssh/id_rsa</code>
            </p>
          </div>
        </div>
      )}

      {/* Local Backend Info */}
      {selectedBackend === 'local' && (
        <div className="border-t border-gray-200 pt-3 mt-1">
          <div className="flex items-center gap-1.5 text-xs text-gray-600">
            <Monitor className="h-3.5 w-3.5" />
            <span>Jobs run on this machine using Docker containers. No HPC scheduling.</span>
          </div>
        </div>
      )}
    </div>
  );
};
