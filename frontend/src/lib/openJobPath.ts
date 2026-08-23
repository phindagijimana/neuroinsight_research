import type { Job } from '../types';
import type { PlatformType } from '../components/FileBrowserPane';
import { canRevealInFinder, revealPathInFinder } from './desktopBridge';

export const TRANSFER_OPEN_AT_KEY = 'nir.transfer.openAt';

export type PathKind = 'input' | 'output';

export type PathOpenAction =
  | { type: 'finder'; path: string; label: string; title: string }
  | { type: 'transfer'; platform: PlatformType; path: string; label: string; title: string }
  | { type: 'copy'; label: string; title: string; reason?: string };

const LOCAL_PATH_PREFIXES = ['/Users/', '/Volumes/', '/private/var/', '/tmp/'];
const HPC_PATH_PREFIXES = ['/scratch/', '/mnt/', '/work/', '/lustre/', '/gpfs/', '/project/', '/home/'];

function isPlatformType(value: string): value is PlatformType {
  return ['local', 'remote', 'hpc', 'pennsieve', 'xnat'].includes(value);
}

function normalizePlatform(platform?: string | null): PlatformType | null {
  if (!platform) return null;
  const normalized = platform.toLowerCase();
  return isPlatformType(normalized) ? normalized : null;
}

function backendToPlatform(backendType?: string): PlatformType | null {
  switch (backendType) {
    case 'slurm':
      return 'hpc';
    case 'remote_docker':
      return 'remote';
    case 'local_docker':
      return 'local';
    default:
      return null;
  }
}

function isLikelyLocalPath(path: string, homeDir?: string | null): boolean {
  if (!path) return false;
  if (path.startsWith('~/')) return true;
  if (LOCAL_PATH_PREFIXES.some((prefix) => path.startsWith(prefix))) return true;
  if (/^[A-Za-z]:\\/.test(path)) return true;
  if (homeDir) {
    const home = homeDir.replace(/\/$/, '');
    if (path === home || path.startsWith(`${home}/`)) return true;
  }
  return false;
}

function isLikelyHpcPath(path: string, homeDir?: string | null): boolean {
  if (!path || isLikelyLocalPath(path, homeDir)) return false;
  if (path.startsWith('~')) return true;
  if (HPC_PATH_PREFIXES.some((prefix) => path.startsWith(prefix))) return true;
  return path.startsWith('/') && !path.startsWith('/Users/');
}

/** Prefer a directory for Transfer browsing (files → parent folder). */
export function browseDirectoryForPath(path: string, pathKind: PathKind): string {
  if (!path) return '~';
  if (path.endsWith('/')) return path.replace(/\/+$/, '') || '/';
  const looksLikeFile =
    pathKind === 'input' &&
    /\.[A-Za-z0-9]{2,5}$/.test(path.split('/').pop() || '');
  if (looksLikeFile) {
    const parent = path.replace(/\/[^/]+$/, '');
    return parent || '~';
  }
  return path;
}

export interface ResolvePathOpenOptions {
  path: string;
  pathKind: PathKind;
  job?: Job | null;
  homeDir?: string | null;
}

export function resolvePathOpenAction(opts: ResolvePathOpenOptions): PathOpenAction {
  const { path, pathKind, job, homeDir } = opts;
  const trimmed = (path || '').trim();

  if (!trimmed || trimmed === 'N/A' || trimmed === 'Bundled sample data') {
    return {
      type: 'copy',
      label: 'Copy',
      title: 'Copy path',
      reason: 'No filesystem path is available for this job.',
    };
  }

  const sourcePlatform = normalizePlatform(job?.data_source_platform);
  if (pathKind === 'input' && sourcePlatform && (sourcePlatform === 'xnat' || sourcePlatform === 'pennsieve')) {
    return {
      type: 'transfer',
      platform: sourcePlatform,
      path: job?.data_source_dataset_id ? `/${job.data_source_dataset_id}` : '/',
      label: sourcePlatform === 'xnat' ? 'XNAT' : 'Pennsieve',
      title: `Browse on ${sourcePlatform === 'xnat' ? 'XNAT' : 'Pennsieve'}`,
    };
  }

  if (isLikelyLocalPath(trimmed, homeDir) && canRevealInFinder()) {
    return {
      type: 'finder',
      path: trimmed,
      label: 'Finder',
      title: `Open in Finder: ${trimmed}`,
    };
  }

  if (job?.backend_type === 'slurm' || isLikelyHpcPath(trimmed, homeDir)) {
    const browsePath = browseDirectoryForPath(trimmed, pathKind);
    return {
      type: 'transfer',
      platform: 'hpc',
      path: browsePath,
      label: 'Browse HPC',
      title: `Browse on HPC: ${trimmed}`,
    };
  }

  if (job?.backend_type === 'remote_docker') {
    const browsePath = browseDirectoryForPath(trimmed, pathKind);
    return {
      type: 'transfer',
      platform: 'remote',
      path: browsePath,
      label: 'Browse Remote',
      title: `Browse on remote server: ${trimmed}`,
    };
  }

  if (isLikelyLocalPath(trimmed, homeDir)) {
    const browsePath = browseDirectoryForPath(trimmed, pathKind);
    return {
      type: 'transfer',
      platform: 'local',
      path: browsePath,
      label: 'Browse',
      title: `Browse: ${trimmed}`,
    };
  }

  if (trimmed.startsWith('/data/')) {
    const platform = backendToPlatform(job?.backend_type) || 'local';
    const browsePath = browseDirectoryForPath(trimmed, pathKind);
    return {
      type: 'transfer',
      platform,
      path: browsePath,
      label: 'Browse',
      title: `Browse output location: ${trimmed}`,
    };
  }

  return {
    type: 'copy',
    label: 'Copy',
    title: trimmed,
    reason: 'Path copied. Use Transfer to browse connected data sources.',
  };
}

export function pathLocationHeading(label: string, action: PathOpenAction): string {
  if (action.type === 'finder') return `${label} on this Mac`;
  if (action.type === 'transfer') {
    switch (action.platform) {
      case 'hpc':
        return `${label} on HPC`;
      case 'remote':
        return `${label} on remote server`;
      case 'xnat':
        return `${label} on XNAT`;
      case 'pennsieve':
        return `${label} on Pennsieve`;
      default:
        return `${label} location`;
    }
  }
  return label;
}

export interface TransferOpenAt {
  pane: 'left' | 'right';
  platform: PlatformType;
  path: string;
}

export function stashTransferOpenAt(target: TransferOpenAt): void {
  try {
    window.sessionStorage.setItem(TRANSFER_OPEN_AT_KEY, JSON.stringify(target));
  } catch {
    // Ignore storage errors.
  }
}

export function consumeTransferOpenAt(): TransferOpenAt | null {
  try {
    const raw = window.sessionStorage.getItem(TRANSFER_OPEN_AT_KEY);
    if (!raw) return null;
    window.sessionStorage.removeItem(TRANSFER_OPEN_AT_KEY);
    const parsed = JSON.parse(raw);
    if (
      parsed &&
      (parsed.pane === 'left' || parsed.pane === 'right') &&
      typeof parsed.platform === 'string' &&
      isPlatformType(parsed.platform) &&
      typeof parsed.path === 'string'
    ) {
      return parsed as TransferOpenAt;
    }
  } catch {
    // Ignore parse errors.
  }
  return null;
}

export async function executePathOpenAction(
  action: PathOpenAction,
  onNavigateToTransfer?: () => void,
): Promise<'ok' | 'copied' | 'failed'> {
  if (action.type === 'finder') {
    const ok = await revealPathInFinder(action.path);
    return ok ? 'ok' : 'failed';
  }
  if (action.type === 'transfer') {
    stashTransferOpenAt({
      pane: 'left',
      platform: action.platform,
      path: action.path,
    });
    onNavigateToTransfer?.();
    return 'ok';
  }
  return 'copied';
}
