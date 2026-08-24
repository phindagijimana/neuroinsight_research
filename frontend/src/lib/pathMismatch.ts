import type { BackendType } from '../components/BackendSelector';

const LOCAL_PATH_PREFIXES = ['/Users/', '/Volumes/', '/private/var/', '/tmp/'];
const HPC_CLUSTER_PREFIXES = ['/scratch/', '/lustre/', '/gpfs/', '/project/'];

export interface PathMismatchWarning {
  message: string;
  blockSubmit: boolean;
}

function isLikelyLocalMacPath(path: string): boolean {
  if (!path) return false;
  if (path.startsWith('~/')) return true;
  if (LOCAL_PATH_PREFIXES.some((p) => path.startsWith(p))) return true;
  if (/^[A-Za-z]:\\/.test(path)) return true;
  return false;
}

function isLikelyClusterPath(path: string): boolean {
  if (!path) return false;
  if (HPC_CLUSTER_PREFIXES.some((p) => path.startsWith(p))) return true;
  return false;
}

/** Warn when the input path does not match the selected compute backend. */
export function checkPathComputeMismatch(
  path: string | null | undefined,
  backend: BackendType,
  options?: { blockSubmit?: boolean },
): PathMismatchWarning | null {
  const trimmed = (path || '').trim();
  if (!trimmed) return null;

  const blockSubmit = options?.blockSubmit ?? true;

  if (backend === 'local' && isLikelyClusterPath(trimmed)) {
    return {
      message:
        'This path looks like cluster storage (/scratch, /lustre, …). Local Docker cannot read it — use Transfer to copy data here, or switch compute to HPC.',
      blockSubmit,
    };
  }

  if (backend === 'local' && trimmed.startsWith('/') && !isLikelyLocalMacPath(trimmed) && !trimmed.startsWith('/data/')) {
    return {
      message:
        'This path may not exist on this Mac. Local Docker only sees paths on your machine (or /data inside the engine).',
      blockSubmit: false,
    };
  }

  if ((backend === 'remote' || backend === 'remote_hpc') && isLikelyLocalMacPath(trimmed)) {
    const target = backend === 'remote_hpc' ? 'HPC (SLURM)' : 'Remote Server (Docker)';
    return {
      message: `This path looks like a path on your Mac (/Users/…). ${target} jobs need a path on the connected host — copy data with Transfer first.`,
      blockSubmit,
    };
  }

  if (backend === 'remote' && isLikelyClusterPath(trimmed)) {
    return {
      message:
        'This path looks like shared cluster storage. Remote Server mode uses Docker on the SSH host — confirm the path exists there.',
      blockSubmit: false,
    };
  }

  return null;
}
