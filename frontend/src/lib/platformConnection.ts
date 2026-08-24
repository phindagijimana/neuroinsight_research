import { apiService } from '../services/api';
import type { PlatformType } from '../components/FileBrowserPane';

/** Local filesystem needs no connect step. */
export function isLocalPlatform(platform: PlatformType): boolean {
  return platform === 'local';
}

/** Whether the file browser can render for this pane. */
export function canBrowsePlatform(platform: PlatformType, connected: boolean): boolean {
  return isLocalPlatform(platform) || connected;
}

/** Ask the backend whether a platform is already connected (SSH session, saved API creds, etc.). */
export async function probePlatformConnected(platform: PlatformType): Promise<boolean> {
  if (isLocalPlatform(platform)) return true;

  if (platform === 'remote' || platform === 'hpc') {
    const status = await apiService.hpcStatus();
    return status.connected;
  }

  if (platform === 'pennsieve' || platform === 'xnat') {
    const status = await apiService.platformStatus(platform);
    return status.connected;
  }

  return false;
}
