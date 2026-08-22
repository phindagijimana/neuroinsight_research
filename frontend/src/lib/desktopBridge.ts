/** Minimal desktop (Electron) bridge exposed via preload as `window.nir`. */

export interface PickInputResult {
  ok: boolean;
  canceled?: boolean;
  path?: string;
  isDirectory?: boolean;
  error?: string;
}

export interface NirDesktopBridge {
  pickInputPath?: () => Promise<PickInputResult>;
  openDataDialog?: () => Promise<void>;
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
