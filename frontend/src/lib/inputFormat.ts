/** Helpers for pipeline/workflow input format (BIDS App vs single NIfTI). */

export interface ExecutionInputProfile {
  inputFormatName?: string;
  inputFormatDescription?: string;
  requiresBidsDir?: boolean;
}

export function isBidsInput(profile?: ExecutionInputProfile | null): boolean {
  if (!profile) return false;
  if (profile.requiresBidsDir) return true;
  const name = (profile.inputFormatName || '').toLowerCase();
  return name.includes('bids');
}

export function isSingleNiftiInput(profile?: ExecutionInputProfile | null): boolean {
  if (!profile) return false;
  const name = (profile.inputFormatName || '').toLowerCase();
  return name.includes('nifti') || name.includes('single');
}

/** Extract BIDS dataset root + subject id from a sub-XXX folder path. */
export function parseBidsSubjectPath(path: string): { bidsDir: string; subjectId: string } | null {
  const normalized = path.replace(/\\/g, '/').replace(/\/+$/, '');
  const match = normalized.match(/^(.*)\/sub-([^/]+)$/);
  if (!match) return null;
  return { bidsDir: match[1], subjectId: match[2] };
}

export function inputProfileFromApi(item: {
  input_format?: { format_name?: string; description?: string };
  inputs?: { required?: Array<{ key?: string; type?: string }> };
}): ExecutionInputProfile {
  const inputFormatName = item.input_format?.format_name;
  const requiresBidsDir = (item.inputs?.required || []).some(
    (inp) => inp.key === 'bids_dir' || inp.type === 'bids'
  );
  return {
    inputFormatName,
    inputFormatDescription: item.input_format?.description,
    requiresBidsDir,
  };
}
