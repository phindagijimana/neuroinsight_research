/**
 * DataSourceSelector Component
 *
 * First step in the job submission flow -- lets users choose where their data lives.
 * Supports filesystem backends (Local/Remote/HPC) and external platforms (Pennsieve/XNAT).
 *
 * For filesystem backends, delegates to BackendSelector for SSH config.
 * For platforms, shows authentication forms and connects via API.
 */

import React, { useState } from 'react';
import {
  Monitor, Cloud, Server, Database, Globe,
  Loader2, AlertCircle, CheckCircle2, KeyRound,
} from 'lucide-react';
import { apiService } from '../services/api';
import type { DataSourceType, PlatformConnection } from '../types';

interface DataSourceSelectorProps {
  selected: DataSourceType;
  onSelect: (source: DataSourceType) => void;
  platformConnection: PlatformConnection | null;
  onPlatformConnect: (conn: PlatformConnection) => void;
  onPlatformDisconnect: () => void;
}

const DATA_SOURCES: { id: DataSourceType; label: string; icon: React.ReactNode; color: string; desc: string }[] = [
  { id: 'local', label: 'Local', icon: <Monitor className="h-4 w-4" />, color: 'navy', desc: 'Files on this machine' },
  { id: 'remote', label: 'Remote Server', icon: <Cloud className="h-4 w-4" />, color: 'green', desc: 'SSH-accessible server' },
  { id: 'hpc', label: 'HPC', icon: <Server className="h-4 w-4" />, color: 'purple', desc: 'SLURM cluster via SSH' },
  { id: 'pennsieve', label: 'Pennsieve', icon: <Database className="h-4 w-4" />, color: 'blue', desc: 'Pennsieve platform' },
  { id: 'xnat', label: 'XNAT', icon: <Globe className="h-4 w-4" />, color: 'orange', desc: 'XNAT data platform' },
];

const colorMap: Record<string, { active: string; hover: string }> = {
  navy: { active: 'border-navy-600 bg-navy-50 text-navy-700', hover: 'hover:border-navy-300' },
  green: { active: 'border-green-600 bg-green-50 text-green-700', hover: 'hover:border-green-300' },
  purple: { active: 'border-purple-600 bg-purple-50 text-purple-700', hover: 'hover:border-purple-300' },
  blue: { active: 'border-blue-600 bg-blue-50 text-blue-700', hover: 'hover:border-blue-300' },
  orange: { active: 'border-orange-600 bg-orange-50 text-orange-700', hover: 'hover:border-orange-300' },
};

export const DataSourceSelector: React.FC<DataSourceSelectorProps> = ({
  selected,
  onSelect,
  platformConnection,
  onPlatformConnect,
  onPlatformDisconnect,
}) => {
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pennsieve credentials
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');

  // XNAT credentials
  const [xnatUrl, setXnatUrl] = useState('');
  const [xnatUser, setXnatUser] = useState('');
  const [xnatPass, setXnatPass] = useState('');

  const isPlatform = selected === 'pennsieve' || selected === 'xnat';
  const isConnected = platformConnection?.connected && platformConnection.platform === selected;

  const handleConnect = async () => {
    setConnecting(true);
    setError(null);
    try {
      let result;
      if (selected === 'pennsieve') {
        if (!apiKey || !apiSecret) { setError('API Key and Secret are required'); setConnecting(false); return; }
        result = await apiService.platformConnect('pennsieve', { api_key: apiKey, api_secret: apiSecret });
      } else if (selected === 'xnat') {
        if (!xnatUrl || !xnatUser || !xnatPass) { setError('URL, username, and password are required'); setConnecting(false); return; }
        result = await apiService.platformConnect('xnat', { url: xnatUrl, username: xnatUser, password: xnatPass });
      }
      if (result?.connected) {
        onPlatformConnect({
          platform: selected,
          connected: true,
          user: result.user,
          workspace: result.workspace,
        });
      } else {
        setError('Connection failed');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Connection failed');
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await apiService.platformDisconnect(selected);
    } catch { /* ignore */ }
    onPlatformDisconnect();
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">Data Source</h3>

      {/* Source Tabs */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {DATA_SOURCES.map((src) => {
          const isActive = selected === src.id;
          const colors = colorMap[src.color];
          return (
            <button
              key={src.id}
              onClick={() => { onSelect(src.id); setError(null); }}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border transition-all text-xs ${
                isActive ? colors.active : `border-gray-300 bg-white text-gray-600 ${colors.hover}`
              }`}
            >
              {src.icon}
              <span className="font-medium">{src.label}</span>
            </button>
          );
        })}
      </div>

      <p className="text-xs text-gray-500 mb-3">
        {DATA_SOURCES.find(s => s.id === selected)?.desc}
      </p>

      {/* Platform Auth Forms */}
      {isPlatform && !isConnected && (
        <div className="border-t border-gray-200 pt-3 space-y-3">
          <h4 className="text-xs font-semibold text-gray-700 flex items-center gap-1.5">
            <KeyRound className="h-3.5 w-3.5" />
            {selected === 'pennsieve' ? 'Pennsieve API Credentials' : 'XNAT Login'}
          </h4>

          {selected === 'pennsieve' && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Key</label>
                <input
                  type="text"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">API Secret</label>
                <input
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  placeholder="Enter API secret"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <p className="text-xs text-gray-400">
                Find your API keys at <a href="https://app.pennsieve.io" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">app.pennsieve.io</a> &rarr; User Menu &rarr; API Keys
              </p>
            </>
          )}

          {selected === 'xnat' && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">XNAT URL</label>
                <input
                  type="text"
                  value={xnatUrl}
                  onChange={(e) => setXnatUrl(e.target.value)}
                  placeholder="https://cidur.urmc-sh.rochester.edu"
                  className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-orange-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Username</label>
                  <input
                    type="text"
                    value={xnatUser}
                    onChange={(e) => setXnatUser(e.target.value)}
                    placeholder="username"
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-orange-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Password</label>
                  <input
                    type="password"
                    value={xnatPass}
                    onChange={(e) => setXnatPass(e.target.value)}
                    placeholder="password"
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-1 focus:ring-orange-500"
                  />
                </div>
              </div>
            </>
          )}

          {error && (
            <div className="flex items-center gap-1.5 text-xs text-red-600 bg-red-50 px-2 py-1.5 rounded">
              <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full px-3 py-2 text-sm bg-[#003d7a] text-white rounded-md hover:bg-[#002b55] disabled:bg-gray-300 font-medium transition flex items-center justify-center gap-2"
          >
            {connecting ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Connecting...</>
            ) : (
              'Connect'
            )}
          </button>
        </div>
      )}

      {/* Connected Status */}
      {isPlatform && isConnected && (
        <div className="border-t border-gray-200 pt-3">
          <div className="flex items-center justify-between px-2 py-1.5 bg-green-50 border border-green-200 rounded text-xs">
            <div className="flex items-center gap-1.5 text-green-700">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>
                Connected to <strong>{platformConnection?.workspace || selected}</strong>
                {platformConnection?.user && <> as {platformConnection.user}</>}
              </span>
            </div>
            <button
              onClick={handleDisconnect}
              className="text-green-600 hover:text-red-600 font-medium transition"
            >
              Disconnect
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataSourceSelector;
