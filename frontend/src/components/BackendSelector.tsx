/**
 * BackendSelector Component
 * 
 * Allows users to select between Local and Remote (HPC) execution backends.
 * For Remote mode, provides SSH connection configuration using SSH agent authentication.
 */

import React, { useState, useEffect } from 'react';
import { Monitor, Server, CheckCircle, AlertCircle } from 'lucide-react';

export type BackendType = 'local' | 'remote';

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

export const BackendSelector: React.FC<BackendSelectorProps> = ({
  selectedBackend,
  onBackendChange,
  sshConfig,
  onSSHConfigChange,
}) => {
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connected' | 'error'>('disconnected');
  const [errorMessage, setErrorMessage] = useState<string>('');

  // Local SSH config state
  const [host, setHost] = useState(sshConfig?.host || '');
  const [username, setUsername] = useState(sshConfig?.username || '');
  const [port, setPort] = useState(sshConfig?.port || 22);

  useEffect(() => {
    // Update parent when SSH config changes
    if (onSSHConfigChange && selectedBackend === 'remote') {
      onSSHConfigChange({ host, username, port });
    }
  }, [host, username, port, selectedBackend]);

  const testConnection = async () => {
    setIsConnecting(true);
    setErrorMessage('');

    try {
      // TODO: Implement actual SSH connection test via backend API
      // For now, just simulate
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      if (!host || !username) {
        throw new Error('Host and username are required');
      }

      setConnectionStatus('connected');
    } catch (error: any) {
      setConnectionStatus('error');
      setErrorMessage(error.message || 'Connection failed');
    } finally {
      setIsConnecting(false);
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Backend</h3>
        <div className="flex gap-2">
          {/* Local Backend */}
          <button
            onClick={() => {
              onBackendChange('local');
              setConnectionStatus('disconnected');
            }}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border transition-all text-sm ${
              selectedBackend === 'local'
                ? 'border-navy-600 bg-navy-50 text-navy-700'
                : 'border-gray-300 bg-white text-gray-600 hover:border-gray-400'
            }`}
          >
            <Monitor className="h-4 w-4" />
            <span className="font-medium">Local</span>
          </button>

          {/* Remote Backend */}
          <button
            onClick={() => onBackendChange('remote')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md border transition-all text-sm ${
              selectedBackend === 'remote'
                ? 'border-green-600 bg-green-50 text-green-700'
                : 'border-gray-300 bg-white text-gray-600 hover:border-gray-400'
            }`}
          >
            <Server className="h-4 w-4" />
            <span className="font-medium">Remote (HPC)</span>
          </button>
        </div>
      </div>

      {/* Remote Configuration */}
      {selectedBackend === 'remote' && (
        <div className="border-t border-gray-200 pt-3 mt-3">
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
                className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent"
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
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent"
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
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-green-500 focus:border-transparent"
                />
              </div>
            </div>

            {/* Test Connection Button & Status */}
            <div className="flex items-center gap-2">
              <button
                onClick={testConnection}
                disabled={!host || !username || isConnecting}
                className="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed font-medium transition"
              >
                {isConnecting ? 'Testing...' : 'Test'}
              </button>
              
              {connectionStatus !== 'disconnected' && (
                <div className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs ${
                  connectionStatus === 'connected' 
                    ? 'bg-green-50 text-green-700'
                    : 'bg-red-50 text-red-700'
                }`}>
                  {connectionStatus === 'connected' ? (
                    <>
                      <CheckCircle className="h-3.5 w-3.5" />
                      <span>Connected</span>
                    </>
                  ) : (
                    <>
                      <AlertCircle className="h-3.5 w-3.5" />
                      <span>{errorMessage}</span>
                    </>
                  )}
                </div>
              )}
            </div>
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
        <div className="border-t border-gray-200 pt-3 mt-3">
          <p className="text-xs text-gray-600">
            Jobs run on this machine using Docker. No SLURM scheduling.
          </p>
        </div>
      )}
    </div>
  );
};
