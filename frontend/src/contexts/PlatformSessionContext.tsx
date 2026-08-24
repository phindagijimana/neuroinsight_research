/**
 * Shared Pennsieve / XNAT session state for the whole workspace.
 *
 * Backend credentials live in ~/.nir/data/.platform_config.json and are
 * auto-restored on API calls. This context mirrors that on the frontend so
 * navigating Jobs → Results → Transfer does not look "logged out".
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { apiService } from '../services/api';
import type { PlatformConnection } from '../types';

export type PlatformSessionId = 'pennsieve' | 'xnat';

interface PlatformSessionContextValue {
  /** Latest known session per platform (undefined = not checked yet). */
  sessions: Partial<Record<PlatformSessionId, PlatformConnection | null>>;
  getSession: (platform: PlatformSessionId) => PlatformConnection | null | undefined;
  setSession: (platform: PlatformSessionId, session: PlatformConnection | null) => void;
  refreshPlatform: (platform: PlatformSessionId) => Promise<PlatformConnection | null>;
  refreshAll: () => Promise<void>;
  /** End session server-side and clear saved credentials. */
  logOut: (platform: PlatformSessionId) => Promise<void>;
  hydrating: boolean;
}

const PlatformSessionContext = createContext<PlatformSessionContextValue | null>(null);

const PLATFORMS: PlatformSessionId[] = ['pennsieve', 'xnat'];

function statusToSession(
  platform: PlatformSessionId,
  status: { connected: boolean; user?: string; workspace?: string },
): PlatformConnection | null {
  if (!status.connected) return null;
  return {
    platform,
    connected: true,
    user: status.user,
    workspace: status.workspace,
  };
}

export const PlatformSessionProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [sessions, setSessions] = useState<
    Partial<Record<PlatformSessionId, PlatformConnection | null>>
  >({});
  const [hydrating, setHydrating] = useState(true);

  const refreshPlatform = useCallback(async (platform: PlatformSessionId) => {
    try {
      const status = await apiService.platformStatus(platform);
      const session = statusToSession(platform, status);
      setSessions((prev) => ({ ...prev, [platform]: session }));
      return session;
    } catch {
      setSessions((prev) => ({ ...prev, [platform]: null }));
      return null;
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setHydrating(true);
    await Promise.all(PLATFORMS.map((p) => refreshPlatform(p)));
    setHydrating(false);
  }, [refreshPlatform]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const getSession = useCallback(
    (platform: PlatformSessionId) => sessions[platform],
    [sessions],
  );

  const setSession = useCallback(
    (platform: PlatformSessionId, session: PlatformConnection | null) => {
      setSessions((prev) => ({ ...prev, [platform]: session }));
    },
    [],
  );

  const logOut = useCallback(async (platform: PlatformSessionId) => {
    try {
      await apiService.platformDisconnect(platform);
    } catch {
      /* still clear local state */
    }
    setSessions((prev) => ({ ...prev, [platform]: null }));
  }, []);

  const value = useMemo(
    () => ({
      sessions,
      getSession,
      setSession,
      refreshPlatform,
      refreshAll,
      logOut,
      hydrating,
    }),
    [sessions, getSession, setSession, refreshPlatform, refreshAll, logOut, hydrating],
  );

  return (
    <PlatformSessionContext.Provider value={value}>
      {children}
    </PlatformSessionContext.Provider>
  );
};

export function usePlatformSession(): PlatformSessionContextValue {
  const ctx = useContext(PlatformSessionContext);
  if (!ctx) {
    throw new Error('usePlatformSession must be used within PlatformSessionProvider');
  }
  return ctx;
}
