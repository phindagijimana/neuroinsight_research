import type { Job } from '../types';

const SUB_PATH_RE = /sub-([^/]+)/i;
const SES_PATH_RE = /ses-([^/]+)/i;
const SUB_FILE_RE = /sub-([^_.]+)/i;
const SES_FILE_RE = /ses-([^_.]+)/i;

function normalizeSubId(raw: string): string {
  const value = raw.trim();
  if (!value) return '';
  return value.toLowerCase().startsWith('sub-') ? value : `sub-${value}`;
}

function normalizeSesId(raw: string): string {
  const value = raw.trim();
  if (!value) return '';
  return value.toLowerCase().startsWith('ses-') ? value : `ses-${value}`;
}

function basenameLabel(path: string): string {
  const name = path.replace(/\\/g, '/').split('/').pop() || path;
  const lower = name.toLowerCase();
  if (lower.endsWith('.nii.gz')) return name.slice(0, -7);
  if (lower.endsWith('.nii')) return name.slice(0, -4);
  return name;
}

export function jobPipelineLabel(job: Job): string {
  return job.display_name || job.pipeline_name || 'Unknown pipeline';
}

export function jobShortId(job: Job): string {
  return job.id.slice(0, 8);
}

export function jobComputeLabel(job: Job): string {
  switch (job.backend_type) {
    case 'local_docker':
      return 'Local';
    case 'slurm':
      return 'HPC';
    case 'remote_docker':
      return 'Remote';
    default:
      return job.backend_type || 'Unknown';
  }
}

/** Dropdown / picker label — subject first, never the full UUID. */
export function formatJobPickerLabel(job: Job): string {
  const subject = job.is_sample_job ? 'Sample EEG demo' : deriveJobSubjectLabel(job);
  const pipeline = jobPipelineLabel(job);
  const when = new Date(job.completed_at || job.submitted_at).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
  if (subject) return `${subject} — ${pipeline} (${when})`;
  return `${pipeline} (${when}) · ${jobShortId(job)}`;
}

/** Client-side fallback when API has not attached subject_label yet. */
export function deriveJobSubjectLabel(job: Job): string | null {
  if (job.subject_label) return job.subject_label;
  if (job.input_label) {
    const fromInput = job.input_label.replace(/\.(nii\.gz|nii|mgz)$/i, '');
    if (fromInput) return fromInput;
  }

  const params = job.parameters || {};
  let subjectId = String(params.subject_id || '').trim();
  let sessionId = String(params.session_id || params.session || '').trim();

  const primaryInput = job.input_files?.[0] || '';
  if (primaryInput) {
    const normalized = primaryInput.replace(/\\/g, '/');
    if (!subjectId) {
      const m = normalized.match(SUB_PATH_RE);
      if (m) subjectId = m[1];
    }
    if (!sessionId) {
      const m = normalized.match(SES_PATH_RE);
      if (m) sessionId = m[1];
    }
    const name = normalized.split('/').pop() || '';
    if (!subjectId) {
      const m = name.match(SUB_FILE_RE);
      if (m) subjectId = m[1];
    }
    if (!sessionId) {
      const m = name.match(SES_FILE_RE);
      if (m) sessionId = m[1];
    }
  }

  if (subjectId) {
    let label = normalizeSubId(subjectId);
    if (sessionId) label = `${label} · ${normalizeSesId(sessionId)}`;
    return label;
  }

  if (primaryInput) {
    const base = basenameLabel(primaryInput);
    return base || null;
  }

  return null;
}

/** Keep auto-refreshing jobs that may still be running or get reconciled after a false failure. */
const STATUS_WATCH_WINDOW_MS = 12 * 60 * 60 * 1000;
const SUSPICIOUS_FAIL_RUNTIME_SEC = 300;

export function jobNeedsStatusWatch(job: Job, now = Date.now()): boolean {
  if (job.status === 'pending' || job.status === 'running') return true;
  if (job.status !== 'failed') return false;

  const submitted = new Date(job.submitted_at).getTime();
  if (Number.isNaN(submitted) || now - submitted > STATUS_WATCH_WINDOW_MS) return false;

  const runtime = job.runtime_seconds ?? 0;
  // Fast "failed" on long pipelines (e.g. FreeSurfer) is often a monitoring glitch.
  if (runtime > 0 && runtime < SUSPICIOUS_FAIL_RUNTIME_SEC) return true;

  // Recent failure — Celery retry or reaper may still update the DB.
  return true;
}

export function jobMatchesFilter(job: Job, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;

  const subject = (deriveJobSubjectLabel(job) || '').toLowerCase();
  const pipeline = (job.display_name || job.pipeline_name || '').toLowerCase();
  const input = (job.input_files?.[0] || '').toLowerCase();
  const id = job.id.toLowerCase();
  const shortId = job.id.slice(0, 8).toLowerCase();

  return (
    subject.includes(q) ||
    pipeline.includes(q) ||
    input.includes(q) ||
    id.includes(q) ||
    shortId.includes(q)
  );
}
