import { apiService } from '../services/api';

export type FilesystemBrowseMode = 'local' | 'remote' | 'hpc';

/** Resolve the starting directory for local / remote / HPC browsing. */
export async function resolveBrowseRoot(mode: FilesystemBrowseMode): Promise<string | null> {
  if (mode === 'local') {
    try {
      const { local_root } = await apiService.getBrowseRoot();
      return local_root;
    } catch {
      return './data';
    }
  }
  try {
    const status = await apiService.hpcStatus();
    if (status.connected) return '~';
  } catch {
    /* not connected yet */
  }
  return null;
}
