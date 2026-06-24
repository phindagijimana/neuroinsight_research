/**
 * updater — guarded auto-update wiring (electron-updater).
 *
 * Safe in all environments:
 *  - dev (unpackaged) builds skip (no update feed),
 *  - missing/unconfigured feed fails gracefully (logged, never crashes),
 *  - users can disable via settings { autoUpdate: false }.
 *
 * Full functionality requires the release workflow to publish update metadata
 * (electron-builder --publish, which emits latest*.yml alongside the installers
 * to the configured GitHub releases provider).
 */
const { app } = require("electron");
const desktopState = require("./desktopState");

let autoUpdater = null;
let wired = false;

function getUpdater() {
  if (autoUpdater) return autoUpdater;
  try {
    ({ autoUpdater } = require("electron-updater"));
  } catch (e) {
    desktopState.appendLog("updater_unavailable", { error: String(e) });
    return null;
  }
  if (!wired) {
    wired = true;
    autoUpdater.autoDownload = true;
    autoUpdater.autoInstallOnAppQuit = true;
    autoUpdater.on("error", (e) => desktopState.appendLog("updater_error", { error: String(e) }));
    autoUpdater.on("update-available", (i) => desktopState.appendLog("update_available", { version: i && i.version }));
    autoUpdater.on("update-downloaded", (i) =>
      desktopState.appendLog("update_downloaded", { version: i && i.version })
    );
  }
  return autoUpdater;
}

async function checkForUpdates({ silent = true } = {}) {
  if (!app.isPackaged) return { ok: true, skipped: "dev build" };
  let settings = {};
  try {
    settings = desktopState.readSettings();
  } catch (_e) {
    // use defaults
  }
  if (settings.autoUpdate === false) return { ok: true, skipped: "disabled in settings" };

  const u = getUpdater();
  if (!u) return { ok: false, error: "updater unavailable" };
  try {
    const r = await u.checkForUpdates();
    const version = r && r.updateInfo ? r.updateInfo.version : null;
    return { ok: true, version };
  } catch (e) {
    desktopState.appendLog("update_check_failed", { error: String(e) });
    // A missing feed (no published release yet) is expected, not an error to surface.
    return silent ? { ok: true, skipped: "no update feed" } : { ok: false, error: String(e) };
  }
}

module.exports = { checkForUpdates, getUpdater };
