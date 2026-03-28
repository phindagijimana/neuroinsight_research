/**
 * Parse job-relative file_path from /api/results/.../download?file_path=...
 */
export function parseResultFilePathFromDownloadUrl(downloadPath: string): string {
  const qIdx = downloadPath.indexOf('?');
  if (qIdx === -1) return '';
  return new URLSearchParams(downloadPath.slice(qIdx + 1)).get('file_path') || '';
}

export function isImagingResultPath(path: string): boolean {
  const l = path.toLowerCase();
  return (
    l.includes('.nii') ||
    l.includes('.mgz') ||
    l.includes('.mgh') ||
    l.includes('.nrrd')
  );
}

export function isEegResultPath(path: string): boolean {
  const l = path.toLowerCase();
  return (
    l.includes('.edf') ||
    l.includes('.fif') ||
    l.includes('.vhdr') ||
    l.includes('.bdf')
  );
}
