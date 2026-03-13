const path = require("path");
const { app, BrowserWindow, Menu, ipcMain, dialog } = require("electron");
const backendManager = require("./src/backendManager");
const desktopState = require("./src/desktopState");
const preflight = require("./src/preflight");
const diagnostics = require("./src/diagnostics");
const licenseManager = require("./src/licenseManager");
const credentialStore = require("./src/credentialStore");

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
  mainWindow = new BrowserWindow({
    width: 980,
    height: 720,
    minWidth: 900,
    minHeight: 640,
    title: "NIR Desktop",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  openControlCenter();
}

ipcMain.handle("nir:getStatus", async () => {
  return backendManager.getStatus();
});

ipcMain.handle("nir:startBackend", async () => {
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
  const res = licenseManager.importLicenseFromText(String(text || ""));
  desktopState.appendLog("license_import_text", { ok: res.ok, error: res.error || null });
  return res;
});

ipcMain.handle("nir:importLicenseFile", async () => {
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
  const res = credentialStore.setSecret(String(key || ""), String(value || ""));
  desktopState.appendLog("secret_save", { key: String(key || ""), ok: res.ok, backend: res.backend });
  return res;
});

ipcMain.handle("nir:loadSecret", async (_event, key) => {
  const res = credentialStore.getSecret(String(key || ""));
  desktopState.appendLog("secret_load", { key: String(key || ""), ok: res.ok, backend: res.backend });
  return res;
});

ipcMain.handle("nir:deleteSecret", async (_event, key) => {
  const res = credentialStore.deleteSecret(String(key || ""));
  desktopState.appendLog("secret_delete", { key: String(key || ""), ok: res.ok, backend: res.backend });
  return res;
});

app.whenReady().then(() => {
  desktopState.initState(app.getPath("userData"));
  const paths = desktopState.getPaths();
  backendManager.initDesktopRuntime(paths);
  licenseManager.initLicenseManager(paths.stateDir);
  credentialStore.initCredentialStore(paths.stateDir);
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
