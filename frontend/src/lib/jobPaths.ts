import type { Job } from '../types';

/** Map in-container paths (e.g. /data/outputs/…) to the host data dir when known. */
export function resolveContainerDataPath(
  path: string,
  containerDataDir: string,
  hostDataDir?: string | null
): string {
  if (!path || !hostDataDir) return path;
  const container = containerDataDir.replace(/\/$/, '');
  const host = hostDataDir.replace(/\/$/, '');
  if (path === container || path.startsWith(`${container}/`)) {
    return host + path.slice(container.length);
  }
  return path;
}

/** Shorten absolute paths under the user home directory to ~/… */
export function formatDisplayPath(path: string, homeDir?: string | null): string {
  if (!path) return path;
  if (homeDir) {
    const home = homeDir.replace(/\/$/, '');
    if (path === home || path.startsWith(`${home}/`)) {
      return `~${path.slice(home.length)}`;
    }
  }
  return path;
}

export function formatJobInput(job: Job): string {
  if (job.is_sample_job) return 'Bundled sample data';
  const files = job.input_files || [];
  if (files.length === 0) return 'N/A';
  if (files.length === 1) return files[0];
  return `${files[0]} (+${files.length - 1} more)`;
}

export function resolveJobOutputPath(
  job: Job,
  opts: { containerDataDir: string; hostDataDir?: string | null }
): string {
  const raw =
    job.output_dir ||
    `${opts.containerDataDir.replace(/\/$/, '')}/outputs/${job.id}`;
  return resolveContainerDataPath(raw, opts.containerDataDir, opts.hostDataDir);
}

export function formatJobOutput(
  job: Job,
  opts: { containerDataDir: string; hostDataDir?: string | null; homeDir?: string | null }
): string {
  return formatDisplayPath(resolveJobOutputPath(job, opts), opts.homeDir);
}
