const path = require("path");
const fs = require("fs");
const { app, BrowserWindow, Menu, ipcMain, dialog } = require("electron");
const backendManager = require("./src/backendManager");
const desktopState = require("./src/desktopState");
const preflight = require("./src/preflight");
const diagnostics = require("./src/diagnostics");
const licenseManager = require("./src/licenseManager");
const credentialStore = require("./src/credentialStore");
const appLock = require("./src/appLock");

let mainWindow = null;

function openControlCenter() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  mainWindow.loadFile(path.join(__dirname, "renderer", "index.html"));
  mainWindow.setTitle("NIR Desktop");
}

async function openNirInMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return { ok: false, error: "Desktop window is not available." };
  }
  const status = await backendManager.getStatus();
  if (!status.running || !status.port) {
    return { ok: false, error: "Backend is not running." };
  }
  const url = `http://localhost:${status.port}`;
  mainWindow.loadURL(url);
  mainWindow.setTitle(`NeuroInsight Research - ${status.port}`);
  desktopState.updateSettings({ lastMode: "nir", lastKnownPort: status.port });
  desktopState.appendLog("open_nir_window", { port: status.port, url });
  return { ok: true, port: status.port };
}

function buildAppMenu() {
  const template = [
    {
      label: "NIR Desktop",
      submenu: [
        {
          label: "Control Center",
          click: () => openControlCenter(),
        },
        {
          label: "Open NIR",
          click: async () => {
            await openNirInMainWindow();
          },
        },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { role: "toggleDevTools" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createMainWindow() {
  const windowIcon = path.join(__dirname, "assets", "icon.png");
  mainWindow = new BrowserWindow({
    width: 980,
    height: 720,
    minWidth: 900,
    minHeight: 640,
    title: "NIR Desktop",
    icon: windowIcon,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  openControlCenter();
}

function getAutoLicenseCandidates() {
  const candidates = [];
  const seen = new Set();
  const addFile = (p) => {
    if (!p || typeof p !== "string") return;
    const resolved = path.resolve(p);
    if (seen.has(resolved)) return;
    seen.add(resolved);
    candidates.push(resolved);
  };
  const addDirCandidate = (dirPath) => {
    if (!dirPath || typeof dirPath !== "string") return;
    addFile(path.join(dirPath, "nir_license.txt"));
  };

  addDirCandidate(path.dirname(process.execPath));
  addDirCandidate(process.cwd());
  if (process.env.APPIMAGE) {
    addDirCandidate(path.dirname(process.env.APPIMAGE));
  }

  const lowerExecPath = String(process.execPath || "").toLowerCase();
  const appMarker = ".app/";
  const markerIdx = lowerExecPath.lastIndexOf(appMarker);
  if (markerIdx > 0) {
    const bundlePath = process.execPath.slice(0, markerIdx + ".app".length);
    addDirCandidate(bundlePath);
    addDirCandidate(path.dirname(bundlePath));
  }
  return candidates;
}

function tryAutoImportNearbyLicense() {
  const candidates = getAutoLicenseCandidates().filter((p) => fs.existsSync(p));
  if (!candidates.length) {
    return { ok: false, skipped: false, reason: "No nearby nir_license.txt file found." };
  }
  return licenseManager.tryAutoImportFromCandidates(candidates);
}

ipcMain.handle("nir:getStatus", async () => {
  return backendManager.getStatus();
});

ipcMain.handle("nir:startBackend", async () => {
  if (!appLock.isUnlockedForSensitiveActions()) {
    return {
      ok: false,
      code: 423,
      stdout: "",
      stderr: "App lock is enabled. Unlock the app to start backend services.",
      locked: true,
    };
  }
  const res = await backendManager.startBackend();
  const patch = {};
  if (res.port) patch.lastKnownPort = res.port;
  desktopState.updateSettings(patch);
  desktopState.appendLog("backend_start", {
    ok: res.ok,
    code: res.code,
    port: res.port || null,
  });
  return res;
});

ipcMain.handle("nir:stopBackendApp", async () => {
  const res = await backendManager.stopBackendAppOnly();
  desktopState.appendLog("backend_stop_app", { ok: res.ok, code: res.code });
  return res;
});

ipcMain.handle("nir:stopBackendAll", async () => {
  const res = await backendManager.stopBackendAll();
  desktopState.appendLog("backend_stop_all", { ok: res.ok, code: res.code });
  return res;
});

ipcMain.handle("nir:openAppInMainWindow", async () => {
  if (!appLock.isUnlockedForSensitiveActions()) {
    return { ok: false, error: "App lock is enabled. Unlock to open NIR.", locked: true };
  }
  return openNirInMainWindow();
});

ipcMain.handle("nir:openControlCenter", async () => {
  openControlCenter();
  desktopState.updateSettings({ lastMode: "control" });
  desktopState.appendLog("open_control_center");
  return { ok: true };
});

ipcMain.handle("nir:getDesktopSettings", async () => {
  return desktopState.readSettings();
});

ipcMain.handle("nir:updateDesktopSettings", async (_event, patch) => {
  const next = desktopState.updateSettings(patch || {});
  desktopState.appendLog("settings_update", { patch: patch || {} });
  return next;
});

ipcMain.handle("nir:getDesktopPaths", async () => {
  return desktopState.getPaths();
});

ipcMain.handle("nir:runPreflight", async () => {
  const result = await preflight.runPreflight();
  desktopState.appendLog("preflight_run", {
    ok: result.ok,
    warnings: result.warnings,
  });
  return result;
});

ipcMain.handle("nir:exportDiagnostics", async () => {
  return diagnostics.exportDiagnosticsBundle();
});

ipcMain.handle("nir:getLicenseStatus", async () => {
  return licenseManager.getLicenseStatus();
});

ipcMain.handle("nir:importLicenseText", async (_event, text) => {
  if (!appLock.isUnlockedForSensitiveActions()) {
    return { ok: false, error: "App lock is enabled. Unlock to import a license.", locked: true };
  }
  const res = licenseManager.importLicenseFromText(String(text || ""));
  desktopState.appendLog("license_import_text", { ok: res.ok, error: res.error || null });
  return res;
});

ipcMain.handle("nir:importLicenseFile", async () => {
  if (!appLock.isUnlockedForSensitiveActions()) {
    return { ok: false, error: "App lock is enabled. Unlock to import a license.", locked: true };
  }
  const win = mainWindow && !mainWindow.isDestroyed() ? mainWindow : null;
  const pick = await dialog.showOpenDialog(win, {
    properties: ["openFile"],
    title: "Select NIR License File",
    filters: [
      { name: "License", extensions: ["json", "txt"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });
  if (pick.canceled || !pick.filePaths?.length) {
    return { ok: false, error: "No file selected." };
  }
  const res = licenseManager.importLicenseFromFile(pick.filePaths[0]);
  desktopState.appendLog("license_import_file", {
    ok: res.ok,
    path: pick.filePaths[0],
    error: res.error || null,
  });
  return res;
});

ipcMain.handle("nir:getCredentialStoreStatus", async () => {
  return credentialStore.getStoreStatus();
});

ipcMain.handle("nir:saveSecret", async (_event, key, value) => {
  if (!appLock.isUnlockedForSensitiveActions()) {
    return { ok: false, backend: "app-lock", error: "App lock is enabled. Unlock to save secrets." };
  }
  const res = credentialStore.setSecret(String(key || ""), String(value || ""));
  desktopState.appendLog("secret_save", { key: String(key || ""), ok: res.ok, backend: res.backend });
  return res;
});

ipcMain.handle("nir:loadSecret", async (_event, key) => {
  if (!appLock.isUnlockedForSensitiveActions()) {
    return { ok: false, backend: "app-lock", error: "App lock is enabled. Unlock to load secrets." };
  }
  const res = credentialStore.getSecret(String(key || ""));
  desktopState.appendLog("secret_load", { key: String(key || ""), ok: res.ok, backend: res.backend });
  return res;
});

ipcMain.handle("nir:deleteSecret", async (_event, key) => {
  if (!appLock.isUnlockedForSensitiveActions()) {
    return { ok: false, backend: "app-lock", error: "App lock is enabled. Unlock to delete secrets." };
  }
  const res = credentialStore.deleteSecret(String(key || ""));
  desktopState.appendLog("secret_delete", { key: String(key || ""), ok: res.ok, backend: res.backend });
  return res;
});

ipcMain.handle("nir:getAppLockStatus", async () => {
  return appLock.getStatus();
});

ipcMain.handle("nir:enableAppLock", async (_event, pin) => {
  const res = appLock.enable(String(pin || ""));
  desktopState.appendLog("app_lock_enable", { ok: res.ok, error: res.error || null });
  return res;
});

ipcMain.handle("nir:disableAppLock", async (_event, pin) => {
  const res = appLock.disable(String(pin || ""));
  desktopState.appendLog("app_lock_disable", { ok: res.ok, error: res.error || null });
  return res;
});

ipcMain.handle("nir:unlockApp", async (_event, pin) => {
  const res = appLock.unlock(String(pin || ""));
  desktopState.appendLog("app_lock_unlock", { ok: res.ok, error: res.error || null });
  return res;
});

ipcMain.handle("nir:lockNow", async () => {
  const res = appLock.lockNow();
  desktopState.appendLog("app_lock_lock_now", { ok: res.ok });
  return res;
});

app.whenReady().then(() => {
  desktopState.initState(app.getPath("userData"));
  const paths = desktopState.getPaths();
  backendManager.initDesktopRuntime(paths);
  licenseManager.initLicenseManager(paths.stateDir);
  credentialStore.initCredentialStore(paths.stateDir);
  appLock.initAppLock(paths.stateDir);
  const autoImport = tryAutoImportNearbyLicense();
  if (autoImport.ok && !autoImport.skipped && autoImport.importedFrom) {
    desktopState.appendLog("license_auto_import", {
      ok: true,
      importedFrom: autoImport.importedFrom,
    });
  } else if (!autoImport.ok && Array.isArray(autoImport.errors) && autoImport.errors.length) {
    desktopState.appendLog("license_auto_import", {
      ok: false,
      errorCount: autoImport.errors.length,
    });
  }
  buildAppMenu();
  createMainWindow();
  desktopState.appendLog("app_ready");

  const settings = desktopState.readSettings();
  if (settings.autoOpenOnStart) {
    openNirInMainWindow().catch((_e) => {
      // keep control center if backend is unavailable
    });
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
