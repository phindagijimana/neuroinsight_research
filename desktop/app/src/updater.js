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
    // Never auto-download. We check, then download ONLY after the user confirms
    // (see promptAndUpdate in main.js). Safe now that signed releases ship a
    // signed `.zip` (Squirrel.Mac needs it on macOS); before signing, downloading
    // threw "ZIP file not provided" at users.
    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = false;
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
    // electron-updater only sets updateInfoAndProvider when isUpdateAvailable is true;
    // returning updateInfo.version without that flag causes downloadUpdate() to throw
    // "Please check update first" (e.g. already on latest, staging, or semver mismatch).
    if (!r?.isUpdateAvailable) {
      return { ok: true, version: null };
    }
    const version = r.updateInfo?.version || null;
    return { ok: true, version };
  } catch (e) {
    desktopState.appendLog("update_check_failed", { error: String(e) });
    // A missing feed (no published release yet) is expected, not an error to surface.
    return silent ? { ok: true, skipped: "no update feed" } : { ok: false, error: String(e) };
  }
}

/** Ensure electron-updater has prepared update metadata for downloadUpdate(). */
async function ensureUpdatePrepared() {
  const u = getUpdater();
  if (!u) throw new Error("updater unavailable");
  if (u.updateInfoAndProvider != null) return u;
  const r = await u.checkForUpdates();
  if (!r?.isUpdateAvailable) {
    throw new Error("No update is available to download");
  }
  return u;
}

/** Download the already-detected update. Resolves when fully downloaded. */
async function downloadUpdate() {
  const u = await ensureUpdatePrepared();
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      u.removeListener("update-downloaded", onDone);
      u.removeListener("error", onErr);
    };
    const onDone = (info) => {
      cleanup();
      resolve(info);
    };
    const onErr = (err) => {
      cleanup();
      reject(err);
    };
    u.once("update-downloaded", onDone);
    u.once("error", onErr);
    Promise.resolve()
      .then(() => u.downloadUpdate())
      .catch(onErr);
  });
}

/** When true, a downloaded update installs automatically on next quit. */
function setInstallOnQuit(enabled) {
  const u = getUpdater();
  if (u) u.autoInstallOnAppQuit = Boolean(enabled);
}

/** Quit and install a downloaded update, relaunching afterwards. */
function quitAndInstall() {
  const u = getUpdater();
  if (!u) return;
  // Defer so the calling IPC/menu handler can return before the app quits.
  setImmediate(() => u.quitAndInstall(false, true));
}

module.exports = {
  checkForUpdates,
  getUpdater,
  downloadUpdate,
  setInstallOnQuit,
  quitAndInstall,
};
