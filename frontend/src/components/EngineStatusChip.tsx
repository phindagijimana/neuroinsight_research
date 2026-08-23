/**
 * Engine health indicator for the desktop app sidebar.
 * Polls the Electron backend bridge (not the HTTP /health endpoint).
 */
import { useEffect, useState } from 'react';
import { getDesktopBackendStatus, isDesktopApp, openControlCenter } from '../lib/desktopBridge';

type EngineState = 'healthy' | 'starting' | 'stopped' | 'unknown';

const LABELS: Record<EngineState, string> = {
  healthy: 'Engine ready',
  starting: 'Engine starting…',
  stopped: 'Engine stopped',
  unknown: 'Engine status…',
};

const DOT: Record<EngineState, string> = {
  healthy: 'bg-emerald-500',
  starting: 'bg-amber-500 animate-pulse',
  stopped: 'bg-gray-400',
  unknown: 'bg-gray-300',
};

export default function EngineStatusChip() {
  const [state, setState] = useState<EngineState>('unknown');

  useEffect(() => {
    if (!isDesktopApp()) return;

    let cancelled = false;
    const poll = async () => {
      const status = await getDesktopBackendStatus();
      if (cancelled || !status?.backend) return;
      if (status.backend.healthy) setState('healthy');
      else if (status.backend.running) setState('starting');
      else setState('stopped');
    };

    poll();
    const id = window.setInterval(poll, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  if (!isDesktopApp()) return null;

  const openCenter = () => openControlCenter();

  return (
    <button
      type="button"
      onClick={openCenter}
      className="flex w-full items-center gap-2 rounded-lg bg-slate-50 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-slate-100 transition-colors border-none text-left"
      data-testid="nir-engine-status"
      title="Open Control Center"
    >
      <span className={`h-2 w-2 shrink-0 rounded-full ${DOT[state]}`} aria-hidden />
      <span>{LABELS[state]}</span>
    </button>
  );
}
