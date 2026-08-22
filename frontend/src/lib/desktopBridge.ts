/** Desktop (Electron) bridge exposed via preload as `window.nir`. */

export interface PickInputResult {
  ok: boolean;
  canceled?: boolean;
  path?: string;
  isDirectory?: boolean;
  error?: string;
}

export interface BackendStatus {
  running?: boolean;
  healthy?: boolean;
  pid?: number | null;
  port?: number;
  url?: string;
  container?: string;
}

export interface NirBackendStatusResponse {
  backend?: BackendStatus;
  celery?: { running?: boolean };
}

export interface NirDesktopBridge {
  pickInputPath?: () => Promise<PickInputResult>;
  openDataDialog?: () => Promise<void>;
  backend?: {
    status: () => Promise<NirBackendStatusResponse>;
  };
  ui?: {
    control: () => Promise<{ ok?: boolean }>;
  };
  onOpenVolume?: (
    cb: (payload: { name: string; data: ArrayBuffer | Uint8Array }) => void
  ) => () => void;
}

declare global {
  interface Window {
    nir?: NirDesktopBridge;
  }
}

export function isDesktopApp(): boolean {
  return typeof window !== 'undefined' && typeof window.nir?.pickInputPath === 'function';
}

export async function pickLocalInputPath(): Promise<PickInputResult | null> {
  if (!isDesktopApp()) return null;
  return window.nir!.pickInputPath!();
}

export async function getDesktopBackendStatus(): Promise<NirBackendStatusResponse | null> {
  if (!window.nir?.backend?.status) return null;
  try {
    return await window.nir.backend.status();
  } catch {
    return null;
  }
}

export function openControlCenter(): void {
  window.nir?.ui?.control?.();
}
