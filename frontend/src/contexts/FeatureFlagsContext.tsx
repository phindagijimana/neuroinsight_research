/**
 * FeatureFlagsContext
 *
 * Fetches public feature flags from /api/config once on load and exposes them
 * to the app. EEG/multimodal UI is gated on `eegEnabled`; the job assistant
 * panel on `assistantEnabled`.
 *
 * Defaults are off so optional UI stays hidden while config is loading or if
 * the backend is unreachable.
 */
import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiService } from '../services/api';

interface FeatureFlags {
  eegEnabled: boolean;
  assistantEnabled: boolean;
}

const DEFAULT_FLAGS: FeatureFlags = {
  eegEnabled: false,
  assistantEnabled: false,
};

const FeatureFlagsContext = createContext<FeatureFlags>(DEFAULT_FLAGS);

export const FeatureFlagsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [flags, setFlags] = useState<FeatureFlags>(DEFAULT_FLAGS);

  useEffect(() => {
    let cancelled = false;
    apiService
      .getConfig()
      .then((cfg) => {
        if (!cancelled) {
          setFlags({
            eegEnabled: !!cfg?.features?.eeg_enabled,
            assistantEnabled: !!cfg?.features?.assistant_enabled,
          });
        }
      })
      .catch(() => {
        if (!cancelled) setFlags(DEFAULT_FLAGS);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <FeatureFlagsContext.Provider value={flags}>{children}</FeatureFlagsContext.Provider>;
};

/** Read the current feature flags (e.g. `const { eegEnabled } = useFeatureFlags()`). */
export function useFeatureFlags(): FeatureFlags {
  return useContext(FeatureFlagsContext);
}
