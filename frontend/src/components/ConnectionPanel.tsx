/**
 * ConnectionPanel -- collapsible connection form for a platform.
 *
 * Checks connection status on mount and shows:
 *   - Green "Connected" badge when already connected
 *   - Expandable credential form when not connected
 *
 * Supports: remote, hpc (SSH), pennsieve (API key), xnat (URL+user+pass).
 * "local" is always connected -- renders nothing.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  ChevronDown, Loader2, AlertCircle, CheckCircle2, Wifi, KeyRound, Server, Cloud,
} from 'lucide-react';
import { apiService } from '../services/api';
import type { PlatformType } from './FileBrowserPane';

interface ConnectionPanelProps {
  platform: PlatformType;
  onConnectionChange: (connected: boolean) => void;
  onPlatformStatusChange?: (status: {
    connected: boolean;
    uploadReady?: boolean;
    uploadError?: string | null;
    agentTarget?: string;
  }) => void;
}

const ConnectionPanel: React.FC<ConnectionPanelProps> = ({
  platform,
  onConnectionChange,
  onPlatformStatusChange,
}) => {
  const [connected, setConnected] = useState(false);
  const [checking, setChecking] = useState(true);
  const [expanded, setExpanded] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [connectedInfo, setConnectedInfo] = useState<string>('');

  // SSH fields
  const [host, setHost] = useState('');
  const [username, setUsername] = useState('');
  const [port, setPort] = useState(22);

  // Pennsieve fields
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');

  // XNAT fields
  const [xnatUrl, setXnatUrl] = useState('');
  const [xnatUser, setXnatUser] = useState('');
  const [xnatPass, setXnatPass] = useState('');
  const [xnatSkipSsl, setXnatSkipSsl] = useState(false);

  const needsConnection = platform !== 'local';

  const checkStatus = useCallback(async () => {
    if (platform === 'local') {
      setConnected(true);
      setChecking(false);
      onConnectionChange(true);
      onPlatformStatusChange?.({ connected: true, uploadReady: true });
      return;
    }

    setChecking(true);
    try {
      if (platform === 'remote' || platform === 'hpc') {
        const status = await apiService.hpcStatus();
        setConnected(status.connected);
        onConnectionChange(status.connected);
        onPlatformStatusChange?.({ connected: status.connected, uploadReady: status.connected });
        if (status.connected) {
          setConnectedInfo(`${status.username}@${status.host}`);
          if (status.host) setHost(status.host);
          if (status.username) setUsername(status.username);
        }
      } else if (platform === 'pennsieve' || platform === 'xnat') {
        const status = await apiService.platformStatus(platform);
        setConnected(status.connected);
        onConnectionChange(status.connected);
        if (platform === 'pennsieve' && status.connected) {
          try {
            const agent = await apiService.getPennsieveAgentStatus();
            onPlatformStatusChange?.({
              connected: true,
              uploadReady: !!agent.ready_for_upload,
              uploadError: agent.error || null,
              agentTarget: agent.agent_target,
            });
          } catch (agentErr: any) {
            onPlatformStatusChange?.({
              connected: true,
              uploadReady: false,
              uploadError: agentErr.response?.data?.detail || agentErr.message || 'Agent status unavailable',
            });
          }
        } else {
          onPlatformStatusChange?.({ connected: status.connected, uploadReady: status.connected });
        }
        if (status.connected) {
          setConnectedInfo(status.user ? `${status.user} @ ${status.workspace || platform}` : (status.workspace || platform));
        }
      }
    } catch {
      setConnected(false);
      onConnectionChange(false);
      onPlatformStatusChange?.({ connected: false, uploadReady: false });
    } finally {
      setChecking(false);
    }
  }, [platform, onConnectionChange]);

  useEffect(() => {
    checkStatus();
  }, [platform]);

  if (!needsConnection) return null;

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      if (platform === 'remote' || platform === 'hpc') {
        if (!host || !username) { setError('Host and username are required'); setConnecting(false); return; }
        const resp = await fetch(`${apiService.getBaseUrl()}/api/hpc/connect`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ host, username, port }),
        });
        const data = await resp.json();
        if (data.connected) {
          setConnected(true);
          setConnectedInfo(`${username}@${host}`);
          onConnectionChange(true);
          setExpanded(false);
        } else {
          setError(data.message || 'Connection failed');
        }
      } else if (platform === 'pennsieve') {
        if (!apiKey || !apiSecret) { setError('API Key and Secret are required'); setConnecting(false); return; }
        const result = await apiService.platformConnect('pennsieve', { api_key: apiKey, api_secret: apiSecret });
        if (result?.connected) {
          setConnected(true);
          setConnectedInfo(result.user || 'Pennsieve');
          onConnectionChange(true);
          try {
            const agent = await apiService.getPennsieveAgentStatus();
            onPlatformStatusChange?.({
              connected: true,
              uploadReady: !!agent.ready_for_upload,
              uploadError: agent.error || null,
              agentTarget: agent.agent_target,
            });
          } catch (agentErr: any) {
            onPlatformStatusChange?.({
              connected: true,
              uploadReady: false,
              uploadError: agentErr.response?.data?.detail || agentErr.message || 'Agent status unavailable',
            });
          }
          setExpanded(false);
        } else {
          setError('Connection failed');
        }
      } else if (platform === 'xnat') {
        if (!xnatUrl || !xnatUser || !xnatPass) { setError('URL, username, and password are required'); setConnecting(false); return; }
        const result = await apiService.platformConnect('xnat', {
          url: xnatUrl, username: xnatUser, password: xnatPass,
          verify_ssl: !xnatSkipSsl,
        });
        if (result?.connected) {
          setConnected(true);
          setConnectedInfo(result.user || 'XNAT');
          onConnectionChange(true);
          setExpanded(false);
        } else {
          setError('Connection failed');
        }
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Connection failed');
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      if (platform === 'remote' || platform === 'hpc') {
        await fetch(`${apiService.getBaseUrl()}/api/hpc/disconnect`, { method: 'POST' });
      } else {
        await apiService.platformDisconnect(platform);
      }
    } catch { /* ignore */ }
    setConnected(false);
    setConnectedInfo('');
    onConnectionChange(false);
    onPlatformStatusChange?.({ connected: false, uploadReady: false });
  };

  const platformLabel = platform === 'remote' ? 'Remote Server' : platform === 'hpc' ? 'HPC' : platform === 'pennsieve' ? 'Pennsieve' : 'XNAT';

  if (checking) {
    return (
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs text-gray-500">
        <Loader2 className="h-3 w-3 animate-spin" />
        Checking {platformLabel} connection...
      </div>
    );
  }

  if (connected) {
    return (
      <div className="flex items-center justify-between px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-xs">
        <div className="flex items-center gap-1.5 text-green-700">
          <CheckCircle2 className="h-3.5 w-3.5" />
          <span>Connected{connectedInfo ? `: ${connectedInfo}` : ''}</span>
        </div>
        <button onClick={handleDisconnect} className="text-green-600 hover:text-red-600 font-medium transition">
          Disconnect
        </button>
      </div>
    );
  }

  return (
    <div className="border border-navy-200 bg-navy-50 rounded-lg overflow-hidden">
      {/* Collapsed header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-amber-700 hover:bg-amber-100 transition"
      >
        <div className="flex items-center gap-1.5">
          <AlertCircle className="h-3.5 w-3.5" />
          <span className="font-medium">Not connected to {platformLabel}</span>
        </div>
        <ChevronDown className={`h-3.5 w-3.5 transition ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {/* Expanded form */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2.5 border-t border-navy-200">
          {/* SSH form */}
          {(platform === 'remote' || platform === 'hpc') && (
            <>
              <div className="pt-2">
                <h4 className="text-[11px] font-semibold text-gray-700 flex items-center gap-1.5 mb-2">
                  {platform === 'hpc' ? <Server className="h-3 w-3" /> : <Cloud className="h-3 w-3" />}
                  SSH Connection
                </h4>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-600 mb-0.5">Hostname</label>
                <input type="text" value={host} onChange={e => setHost(e.target.value)}
                  placeholder={platform === 'hpc' ? 'hpc.university.edu' : 'ec2-xx-xx.compute.amazonaws.com'}
                  className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-green-500 focus:border-transparent" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-medium text-gray-600 mb-0.5">Username</label>
                  <input type="text" value={username} onChange={e => setUsername(e.target.value)}
                    placeholder="your_username"
                    className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-green-500 focus:border-transparent" />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-gray-600 mb-0.5">Port</label>
                  <input type="number" value={port} onChange={e => setPort(parseInt(e.target.value) || 22)}
                    className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-green-500 focus:border-transparent" />
                </div>
              </div>
              <p className="text-[10px] text-gray-400">Uses SSH agent. Load keys: <code className="bg-gray-100 px-1 rounded">ssh-add ~/.ssh/id_ed25519</code></p>
            </>
          )}

          {/* Pennsieve form */}
          {platform === 'pennsieve' && (
            <>
              <div className="pt-2">
                <h4 className="text-[11px] font-semibold text-gray-700 flex items-center gap-1.5 mb-2">
                  <KeyRound className="h-3 w-3" />
                  Pennsieve API Credentials
                </h4>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-600 mb-0.5">API Key</label>
                <input type="text" value={apiKey} onChange={e => setApiKey(e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent" />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-600 mb-0.5">API Secret</label>
                <input type="password" value={apiSecret} onChange={e => setApiSecret(e.target.value)}
                  placeholder="Enter API secret"
                  className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent" />
              </div>
              <p className="text-[10px] text-gray-400">
                Get keys at <a href="https://app.pennsieve.io" target="_blank" rel="noopener noreferrer" className="text-navy-600 underline">app.pennsieve.io</a> &rarr; User Menu &rarr; API Keys
              </p>
            </>
          )}

          {/* XNAT form */}
          {platform === 'xnat' && (
            <>
              <div className="pt-2">
                <h4 className="text-[11px] font-semibold text-gray-700 flex items-center gap-1.5 mb-2">
                  <KeyRound className="h-3 w-3" />
                  XNAT Login
                </h4>
              </div>
              <div>
                <label className="block text-[11px] font-medium text-gray-600 mb-0.5">XNAT URL</label>
                <input type="text" value={xnatUrl} onChange={e => setXnatUrl(e.target.value)}
                  placeholder="https://xnat.example.edu"
                  className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-orange-500 focus:border-transparent" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-[11px] font-medium text-gray-600 mb-0.5">Username</label>
                  <input type="text" value={xnatUser} onChange={e => setXnatUser(e.target.value)}
                    placeholder="your_username"
                    className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-orange-500 focus:border-transparent" />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-gray-600 mb-0.5">Password</label>
                  <input type="password" value={xnatPass} onChange={e => setXnatPass(e.target.value)}
                    placeholder="password"
                    className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-orange-500 focus:border-transparent" />
                </div>
              </div>
              <label className="flex items-center gap-1.5 text-[11px] text-gray-600 cursor-pointer select-none">
                <input type="checkbox" checked={xnatSkipSsl} onChange={e => setXnatSkipSsl(e.target.checked)}
                  className="rounded border-gray-300 text-navy-500 focus:ring-navy-500 h-3 w-3" />
                Skip SSL verification (for self-signed certificates)
              </label>
              <p className="text-[10px] text-gray-400">
                Enter your XNAT instance URL and credentials. The server must be reachable from this machine.
              </p>
            </>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-start gap-1.5 text-[11px] text-red-600 bg-red-50 px-2 py-2 rounded">
              <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
              <span className="break-words whitespace-pre-wrap">{error}</span>
            </div>
          )}

          {/* Connect button */}
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full px-3 py-1.5 text-xs bg-[#003d7a] text-white rounded hover:bg-[#002b55] disabled:bg-gray-300 font-medium transition flex items-center justify-center gap-1.5"
          >
            {connecting ? (<><Loader2 className="h-3 w-3 animate-spin" />Connecting...</>) : (
              <><Wifi className="h-3 w-3" />Connect to {platformLabel}</>
            )}
          </button>
        </div>
      )}
    </div>
  );
};

export default ConnectionPanel;
export { ConnectionPanel };
