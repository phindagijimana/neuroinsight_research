/**
 * Deep-link query ?viewer=eeg | imaging | eeg-brain (UI: Signal / Imaging / Multimodal View).
 */

export const VIEWER_QUERY_KEY = 'viewer';

export type ViewerTab = 'eeg' | 'imaging' | 'eeg-brain';

const VALID = new Set<string>(['eeg', 'imaging', 'eeg-brain']);

export function parseViewerTabFromSearch(search: string): ViewerTab | null {
  const q = search.startsWith('?') ? search.slice(1) : search;
  const v = new URLSearchParams(q).get(VIEWER_QUERY_KEY);
  if (!v || !VALID.has(v)) return null;
  return v as ViewerTab;
}

/** If URL names a valid viewer tab, the app should open the Viewer page. */
export function shouldOpenViewerFromUrl(search: string): boolean {
  return parseViewerTabFromSearch(search) !== null;
}

export function setViewerQueryParam(tab: ViewerTab): void {
  if (typeof window === 'undefined') return;
  const u = new URL(window.location.href);
  u.searchParams.set(VIEWER_QUERY_KEY, tab);
  window.history.replaceState({}, '', `${u.pathname}${u.search}${u.hash}`);
}

export function clearViewerQueryParam(): void {
  if (typeof window === 'undefined') return;
  const u = new URL(window.location.href);
  u.searchParams.delete(VIEWER_QUERY_KEY);
  const qs = u.searchParams.toString();
  window.history.replaceState(
    {},
    '',
    `${u.pathname}${qs ? `?${qs}` : ''}${u.hash}`
  );
}
