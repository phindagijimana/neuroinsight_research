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

/** Client-side fallback when API has not attached subject_label yet. */
export function deriveJobSubjectLabel(job: Job): string | null {
  if (job.subject_label) return job.subject_label;

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
