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
const { app, BrowserWindow, Menu, ipcMain, shell, dialog } = require("electron");

const desktopState = require("./desktopState");
const backendManager = require("./backendManager");
const preflight = require("./preflight");
const diagnostics = require("./diagnostics");
const licenseManager = require("./licenseManager");
const credentialStore = require("./credentialStore");
const appLock = require("./appLock");
const platformAdapter = require("./platformAdapter");
const updater = require("./updater");

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

/** Allow navigation only to the local control center (file://) and the local
 *  backend (127.0.0.1 / localhost). Everything else opens in the OS browser. */
function isAllowedAppUrl(url) {
  try {
    if (url.startsWith("file:")) return true;
    const u = new URL(url);
    return (u.protocol === "http:" || u.protocol === "https:") && (u.hostname === "127.0.0.1" || u.hostname === "localhost");
  } catch (_e) {
    return false;
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
      sandbox: true,
      webSecurity: true,
    },
  });

  // Security: keep in-window navigation on trusted local origins; send anything
  // else (external links) to the OS browser instead of loading it in-app.
  const wc = mainWindow.webContents;
  wc.on("will-navigate", (event, url) => {
    if (!isAllowedAppUrl(url)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });
  wc.setWindowOpenHandler(({ url }) => {
    if (isAllowedAppUrl(url)) return { action: "allow" };
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.loadFile(path.join(__dirname, "..", "renderer", "index.html"));

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// --------------------------------------------------------------------------
// Navigation (shared by IPC handlers and the application menu)
// --------------------------------------------------------------------------
function controlCenterPath() {
  return path.join(__dirname, "..", "renderer", "index.html");
}

function isOnControlCenter() {
  if (!mainWindow) return false;
  const url = mainWindow.webContents.getURL();
  return !url || url.startsWith("file:");
}

async function navigateToControl() {
  if (mainWindow) {
    await mainWindow.loadFile(controlCenterPath());
    desktopState.updateSettings({ lastMode: "control" });
    buildAppMenu();
  }
  return { ok: true };
}

async function navigateToNIR() {
  // Licensing policy: a licensed build (key configured) with an expired/invalid
  // license drops to limited mode and cannot open the UI. Unlicensed/community
  // and active/grace licenses are allowed.
  const enf = licenseManager.getEnforcement();
  if (!enf.allowFullFeatures) {
    return { ok: false, error: enf.reason || "A valid license is required to open the app." };
  }
  const status = await backendManager.getStatus();
  if (!status.backend.healthy) {
    return { ok: false, error: "Backend is not healthy yet. Start it first." };
  }
  if (mainWindow) {
    await mainWindow.loadURL(status.backend.url);
    desktopState.updateSettings({ lastMode: "nir", lastKnownPort: status.backend.port });
    buildAppMenu();
    // Inject an always-visible affordance back to the control center. The
    // preload runs on this page too, so window.nir.ui.control() is available.
    await mainWindow.webContents
      .executeJavaScript(
        `(function () {
          if (document.getElementById('nir-desktop-back')) return;
          var b = document.createElement('button');
          b.id = 'nir-desktop-back';
          b.textContent = '\\u2039 Control Center';
          b.style.cssText = 'position:fixed;bottom:16px;right:16px;z-index:2147483647;' +
            'background:#003d7a;color:#fff;border:none;border-radius:999px;padding:10px 16px;' +
            'font:600 12px -apple-system,BlinkMacSystemFont,sans-serif;cursor:pointer;' +
            'box-shadow:0 3px 10px rgba(0,0,0,.3)';
          b.onmouseenter = function () { b.style.background = '#002b55'; };
          b.onmouseleave = function () { b.style.background = '#003d7a'; };
          b.onclick = function () { if (window.nir && window.nir.ui) window.nir.ui.control(); };
          document.body.appendChild(b);
        })();`
      )
      .catch(() => {});
  }
  return { ok: true, url: status.backend.url };
}

// --------------------------------------------------------------------------
// Native application menu — always-available navigation + backend controls.
// This is the supported way back to the control center after opening the NIR UI.
// --------------------------------------------------------------------------
function buildAppMenu() {
  const onControl = isOnControlCenter();
  const isMac = process.platform === "darwin";

  const appMenu = {
    label: "NeuroInsight",
    submenu: [
      {
        label: "Control Center",
        accelerator: "CmdOrCtrl+Shift+C",
        enabled: !onControl,
        click: () => navigateToControl(),
      },
      {
        label: "Open NIR UI",
        accelerator: "CmdOrCtrl+Shift+O",
        click: async () => {
          const res = await navigateToNIR();
          if (!res.ok && mainWindow) {
            dialog.showMessageBox(mainWindow, { type: "info", message: res.error });
          }
        },
      },
      { type: "separator" },
      { label: "Start Backend", click: () => backendManager.start() },
      { label: "Stop Backend", click: () => backendManager.stopBackend() },
      { type: "separator" },
      ...(isMac ? [{ role: "hide" }, { role: "hideOthers" }, { type: "separator" }] : []),
      { role: "quit" },
    ],
  };

  const viewMenu = {
    label: "View",
    submenu: [
      { role: "reload" },
      { role: "toggleDevTools" },
      { type: "separator" },
      { role: "resetZoom" },
      { role: "zoomIn" },
      { role: "zoomOut" },
      { type: "separator" },
      { role: "togglefullscreen" },
    ],
  };

  const helpMenu = {
    role: "help",
    submenu: [
      {
        label: "Check for Updates…",
        click: async () => {
          const res = await updater.checkForUpdates({ silent: false });
          if (mainWindow) {
            const msg = res.skipped
              ? `Updates: ${res.skipped}.`
              : res.ok
              ? res.version
                ? `Update available: ${res.version} (downloading).`
                : "You are on the latest version."
              : `Update check failed: ${res.error}`;
            dialog.showMessageBox(mainWindow, { type: "info", message: msg });
          }
        },
      },
      { type: "separator" },
      {
        label: "NeuroInsight Research on GitHub",
        click: () => shell.openExternal("https://github.com/phindagijimana/neuroinsight_research"),
      },
    ],
  };

  Menu.setApplicationMenu(Menu.buildFromTemplate([appMenu, { role: "editMenu" }, viewMenu, helpMenu]));
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
  ipcMain.handle(
    "preflight:run",
    wrap(async () => {
      const report = await preflight.runPreflight();
      try {
        desktopState.updateSettings({ lastPreflightAt: report.generatedAt, lastPreflightReady: report.ready });
      } catch (_e) {
        // non-fatal
      }
      return report;
    })
  );
  ipcMain.handle("diagnostics:export", wrap(() => diagnostics.exportDiagnosticsBundle()));
  ipcMain.handle(
    "diagnostics:reveal",
    wrap((filePath) => {
      if (!filePath) return { ok: false, error: "No path to reveal." };
      shell.showItemInFolder(filePath);
      return { ok: true };
    })
  );
  ipcMain.handle("platform:summary", wrap(() => platformAdapter.getPlatformSummary()));
  ipcMain.handle("updates:check", wrap(() => updater.checkForUpdates({ silent: false })));

  // Backend lifecycle
  ipcMain.handle("backend:start", wrap(() => backendManager.start()));
  ipcMain.handle("backend:stop", wrap(() => backendManager.stopBackend()));
  ipcMain.handle("backend:stopAll", wrap(() => backendManager.stopAll()));
  ipcMain.handle("backend:status", wrap(() => backendManager.getStatus()));
  ipcMain.handle("backend:runtime", wrap(() => backendManager.getRuntimeInfo()));

  // Open the live NIR UI inside the desktop window
  ipcMain.handle("backend:openUI", wrap(() => navigateToNIR()));

  // Return to the control center
  ipcMain.handle("ui:control", wrap(() => navigateToControl()));

  // Open a URL in the OS browser (http/https only — never file:// or custom schemes)
  ipcMain.handle(
    "shell:openExternal",
    wrap(async (url) => {
      let parsed;
      try {
        parsed = new URL(String(url));
      } catch (_e) {
        return { ok: false, error: "Invalid URL." };
      }
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return { ok: false, error: "Only http/https URLs may be opened." };
      }
      await shell.openExternal(parsed.toString());
      return { ok: true };
    })
  );

  // Settings
  ipcMain.handle("settings:get", wrap(() => desktopState.readSettings()));
  ipcMain.handle("settings:update", wrap((patch) => desktopState.updateSettings(patch || {})));

  // License
  ipcMain.handle("license:status", wrap(() => licenseManager.getLicenseStatus()));
  ipcMain.handle("license:enforcement", wrap(() => licenseManager.getEnforcement()));
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
  buildAppMenu();

  // Silent auto-update check (no-op in dev / when no feed is published).
  updater.checkForUpdates({ silent: true }).then((r) => {
    if (r && (r.version || r.skipped)) desktopState.appendLog("update_check", r);
  });

  // Startup preflight: run once, record the result, and only auto-start the
  // backend when the environment is actually ready (no blockers).
  preflight
    .runPreflight()
    .then((report) => {
      desktopState.appendLog("startup_preflight", {
        ready: report.ready,
        summary: report.summary,
        blockers: report.blockers,
      });
      try {
        desktopState.updateSettings({
          lastPreflightAt: report.generatedAt,
          lastPreflightReady: report.ready,
        });
      } catch (_e) {
        // non-fatal
      }

      const settings = desktopState.readSettings();
      if (settings.autoOpenOnStart && report.ready) {
        backendManager.start().then((r) => {
          desktopState.appendLog("backend_autostart", { ok: r.ok });
        });
      } else if (settings.autoOpenOnStart && !report.ready) {
        desktopState.appendLog("backend_autostart_skipped", { reason: "preflight blockers", blockers: report.blockers });
      }
    })
    .catch((e) => desktopState.appendLog("startup_preflight_error", { error: String(e) }));

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
