/**
 * NIR Desktop — Electron main process (Phase 1 scaffold).
 *
 * Responsibilities:
 *  - initialize desktop state, license, credential vault, app lock
 *  - manage the backend lifecycle via backendManager (start/stop/status)
 *  - run startup preflight and export diagnostics bundles
 *  - host a "control center" renderer and open the live NIR UI in-window
 *
 * Isolated and additive: it does not modify the core backend/frontend code or
 * the ./research workflows.
 */
const path = require("path");
const { app, BrowserWindow, ipcMain, shell, dialog } = require("electron");

const desktopState = require("./desktopState");
const backendManager = require("./backendManager");
const preflight = require("./preflight");
const diagnostics = require("./diagnostics");
const licenseManager = require("./licenseManager");
const credentialStore = require("./credentialStore");
const appLock = require("./appLock");
const platformAdapter = require("./platformAdapter");

let mainWindow = null;
let stateDir = null;

function initModules() {
  const userData = app.getPath("userData");
  desktopState.initState(userData);
  const paths = desktopState.getPaths();
  stateDir = paths.stateDir;

  backendManager.init({ stateDir });
  licenseManager.initLicenseManager(stateDir);
  credentialStore.initCredentialStore(stateDir);
  appLock.initAppLock(stateDir);

  desktopState.appendLog("desktop_start", {
    platform: platformAdapter.getPlatformSummary(),
    stateDir,
  });
}

/** License files placed next to the binary/app bundle are auto-imported on start. */
function licenseAutoImportCandidates() {
  const candidates = [];
  const exeDir = path.dirname(app.getPath("exe"));
  candidates.push(path.join(exeDir, "nir_license.txt"));
  // macOS .app bundle: exe is in Contents/MacOS — also check alongside the .app
  candidates.push(path.resolve(exeDir, "..", "..", "..", "nir_license.txt"));
  // Dev: alongside the desktop app folder and repo root
  candidates.push(path.resolve(__dirname, "..", "nir_license.txt"));
  candidates.push(path.resolve(__dirname, "..", "..", "..", "nir_license.txt"));
  return candidates;
}

function tryAutoImportLicense() {
  try {
    const result = licenseManager.tryAutoImportFromCandidates(licenseAutoImportCandidates());
    desktopState.appendLog("license_auto_import", { result });
  } catch (e) {
    desktopState.appendLog("license_auto_import_error", { error: String(e) });
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 800,
    minWidth: 880,
    minHeight: 600,
    title: "NeuroInsight Research",
    backgroundColor: "#0b1f3a",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.loadFile(path.join(__dirname, "..", "renderer", "index.html"));

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// --------------------------------------------------------------------------
// IPC handlers — the renderer's window.nir.* surface (see preload.js)
// --------------------------------------------------------------------------
function registerIpc() {
  const wrap = (fn) => async (_event, ...args) => {
    try {
      return await fn(...args);
    } catch (e) {
      return { ok: false, error: String(e && e.message ? e.message : e) };
    }
  };

  // Preflight & diagnostics
  ipcMain.handle("preflight:run", wrap(() => preflight.runPreflight()));
  ipcMain.handle("diagnostics:export", wrap(() => diagnostics.exportDiagnosticsBundle()));

  // Backend lifecycle
  ipcMain.handle("backend:start", wrap(() => backendManager.start()));
  ipcMain.handle("backend:stop", wrap(() => backendManager.stopBackend()));
  ipcMain.handle("backend:stopAll", wrap(() => backendManager.stopAll()));
  ipcMain.handle("backend:status", wrap(() => backendManager.getStatus()));
  ipcMain.handle("backend:runtime", wrap(() => backendManager.getRuntimeInfo()));

  // Open the live NIR UI inside the desktop window
  ipcMain.handle(
    "backend:openUI",
    wrap(async () => {
      const status = await backendManager.getStatus();
      if (!status.backend.healthy) {
        return { ok: false, error: "Backend is not healthy yet. Start it first." };
      }
      if (mainWindow) {
        await mainWindow.loadURL(status.backend.url);
        desktopState.updateSettings({ lastMode: "nir", lastKnownPort: status.backend.port });
      }
      return { ok: true, url: status.backend.url };
    })
  );

  // Return to the control center
  ipcMain.handle(
    "ui:control",
    wrap(async () => {
      if (mainWindow) {
        await mainWindow.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
        desktopState.updateSettings({ lastMode: "control" });
      }
      return { ok: true };
    })
  );

  // Open a URL in the OS browser
  ipcMain.handle(
    "shell:openExternal",
    wrap(async (url) => {
      await shell.openExternal(url);
      return { ok: true };
    })
  );

  // Settings
  ipcMain.handle("settings:get", wrap(() => desktopState.readSettings()));
  ipcMain.handle("settings:update", wrap((patch) => desktopState.updateSettings(patch || {})));

  // License
  ipcMain.handle("license:status", wrap(() => licenseManager.getLicenseStatus()));
  ipcMain.handle("license:importText", wrap((text) => licenseManager.importLicenseFromText(text)));
  ipcMain.handle(
    "license:importFile",
    wrap(async () => {
      const res = await dialog.showOpenDialog(mainWindow, {
        title: "Import NIR license token",
        properties: ["openFile"],
        filters: [{ name: "License", extensions: ["txt", "json"] }],
      });
      if (res.canceled || !res.filePaths[0]) return { ok: false, error: "No file selected." };
      return licenseManager.importLicenseFromFile(res.filePaths[0]);
    })
  );

  // App lock
  ipcMain.handle("lock:status", wrap(() => appLock.getStatus()));
  ipcMain.handle("lock:enable", wrap((pin) => appLock.enable(pin)));
  ipcMain.handle("lock:disable", wrap((pin) => appLock.disable(pin)));
  ipcMain.handle("lock:unlock", wrap((pin) => appLock.unlock(pin)));
  ipcMain.handle("lock:lockNow", wrap(() => appLock.lockNow()));

  // Credential vault — sensitive actions gated by app lock
  const gateSensitive = () => {
    if (!appLock.isUnlockedForSensitiveActions()) {
      throw new Error("App is locked. Unlock to perform this action.");
    }
  };
  ipcMain.handle("creds:status", wrap(() => credentialStore.getStoreStatus()));
  ipcMain.handle(
    "creds:set",
    wrap((name, value) => {
      gateSensitive();
      return credentialStore.setSecret(name, value);
    })
  );
  ipcMain.handle(
    "creds:get",
    wrap((name) => {
      gateSensitive();
      return credentialStore.getSecret(name);
    })
  );
  ipcMain.handle(
    "creds:delete",
    wrap((name) => {
      gateSensitive();
      return credentialStore.deleteSecret(name);
    })
  );
}

// --------------------------------------------------------------------------
// App lifecycle
// --------------------------------------------------------------------------
app.whenReady().then(() => {
  initModules();
  registerIpc();
  tryAutoImportLicense();
  createWindow();

  // Optionally auto-start the backend if the user enabled it.
  try {
    const settings = desktopState.readSettings();
    if (settings.autoOpenOnStart) {
      backendManager.start().then((r) => {
        desktopState.appendLog("backend_autostart", { ok: r.ok });
      });
    }
  } catch (_e) {
    // non-fatal
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

// Stop desktop-managed backend processes on quit.
let cleanedUp = false;
function cleanup() {
  if (cleanedUp) return;
  cleanedUp = true;
  try {
    backendManager.stopAll();
    desktopState.appendLog("desktop_quit", {});
  } catch (_e) {
    // best effort
  }
}
app.on("before-quit", cleanup);
app.on("will-quit", cleanup);
process.on("exit", cleanup);
