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
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { app, BrowserWindow, Menu, ipcMain, shell, dialog, crashReporter } = require("electron");

// Collect native crash minidumps locally (never uploaded — no server). Stored
// under userData/Crashpad. Must start before app is ready.
try {
  crashReporter.start({
    productName: "NeuroInsight",
    companyName: "NeuroInsight",
    submitURL: "",
    uploadToServer: false,
  });
} catch (_e) {
  // non-fatal — crash reporting is best-effort
}

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
let splashWindow = null;
let stateDir = null;

function initModules() {
  const userData = app.getPath("userData");
  desktopState.initState(userData);
  const paths = desktopState.getPaths();
  stateDir = paths.stateDir;

  // Runtime mode: packaged builds default to the self-contained container (user
  // needs only Docker); dev defaults to the local process (venv). An explicit
  // NIR_RUNTIME or a saved setting always wins.
  if (!process.env.NIR_RUNTIME) {
    let saved = "";
    try {
      saved = desktopState.readSettings().runtimeMode || "";
    } catch (_e) {
      saved = "";
    }
    process.env.NIR_RUNTIME = saved || (app.isPackaged ? "container" : "process");
  }
  // In container mode, a packaged build pulls the versioned GHCR image by default.
  if (process.env.NIR_RUNTIME === "container" && !process.env.NIR_IMAGE && app.isPackaged) {
    process.env.NIR_IMAGE = `ghcr.io/phindagijimana/nir-allinone:v${app.getVersion()}`;
  }

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

function createWindow({ show = true } = {}) {
  // Restore the last window size/position (native-app behavior).
  let saved = {};
  try {
    saved = desktopState.readSettings().windowBounds || {};
  } catch (_e) {
    saved = {};
  }
  mainWindow = new BrowserWindow({
    width: saved.width || 1100,
    height: saved.height || 800,
    x: typeof saved.x === "number" ? saved.x : undefined,
    y: typeof saved.y === "number" ? saved.y : undefined,
    minWidth: 880,
    minHeight: 600,
    title: "NeuroInsight",
    backgroundColor: "#0b1f3a",
    show,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });
  if (saved.maximized) mainWindow.maximize();

  const saveBounds = () => {
    try {
      if (!mainWindow) return;
      const b = mainWindow.getNormalBounds();
      desktopState.updateSettings({ windowBounds: { ...b, maximized: mainWindow.isMaximized() } });
    } catch (_e) {
      // non-fatal
    }
  };
  mainWindow.on("close", saveBounds);

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
    injectStatusBar();
  }
  return { ok: true, url: status.backend.url };
}

/** Inject a persistent bottom status bar into the NIR workspace page: an engine
 *  health dot (polled) and a gear button back to the control center (Settings).
 *  The preload runs on this page too, so window.nir.* is available. */
function injectStatusBar() {
  if (!mainWindow) return;
  mainWindow.webContents
    .executeJavaScript(
      `(function () {
        if (document.getElementById('nir-desktop-statusbar')) return;
        var bar = document.createElement('div');
        bar.id = 'nir-desktop-statusbar';
        bar.style.cssText = 'position:fixed;left:0;right:0;bottom:0;height:30px;z-index:2147483647;' +
          'display:flex;align-items:center;justify-content:space-between;padding:0 12px;' +
          'background:#0b1f3a;color:#cdd9ea;font:600 11px -apple-system,BlinkMacSystemFont,sans-serif;' +
          'box-shadow:0 -1px 4px rgba(0,0,0,.25)';
        bar.innerHTML =
          '<span style="display:flex;align-items:center;gap:7px">' +
            '<span id="nir-dot" style="width:8px;height:8px;border-radius:50%;background:#16a34a;display:inline-block"></span>' +
            '<span id="nir-engine">Engine: healthy</span></span>' +
          '<button id="nir-settings" style="background:transparent;color:#cdd9ea;border:1px solid rgba(255,255,255,.25);' +
            'border-radius:6px;padding:3px 10px;font:inherit;cursor:pointer">\\u2699 Settings</button>';
        document.body.appendChild(bar);
        document.body.style.paddingBottom = '34px';
        document.getElementById('nir-settings').onclick = function () {
          if (window.nir && window.nir.ui) window.nir.ui.control();
        };
        function refresh() {
          if (!window.nir || !window.nir.backend) return;
          window.nir.backend.status().then(function (s) {
            var dot = document.getElementById('nir-dot');
            var eng = document.getElementById('nir-engine');
            if (!dot || !eng) return;
            if (s.backend && s.backend.healthy) { dot.style.background = '#16a34a'; eng.textContent = 'Engine: healthy'; }
            else if (s.backend && s.backend.running) { dot.style.background = '#d97706'; eng.textContent = 'Engine: starting'; }
            else { dot.style.background = '#9ca3af'; eng.textContent = 'Engine: stopped'; }
          }).catch(function () {});
        }
        refresh();
        setInterval(refresh, 5000);
      })();`
    )
    .catch(() => {});
}

// --------------------------------------------------------------------------
// Native "Open Data" — load a local volume into the workspace viewer via a
// native file dialog / menu (and remember recents).
// --------------------------------------------------------------------------
function getRecentVolumes() {
  try {
    const r = desktopState.readSettings().recentVolumes;
    return Array.isArray(r) ? r : [];
  } catch (_e) {
    return [];
  }
}

function recordRecentVolume(filePath) {
  try {
    const name = path.basename(filePath);
    const recents = getRecentVolumes().filter((r) => r.path !== filePath);
    desktopState.updateSettings({ recentVolumes: [{ path: filePath, name }, ...recents].slice(0, 8) });
    buildAppMenu();
  } catch (_e) {
    // non-fatal
  }
}

function openVolumeFromPath(filePath) {
  if (!mainWindow) return { ok: false, error: "No window." };
  if (isOnControlCenter()) {
    dialog.showMessageBox(mainWindow, { type: "info", message: "Open the workspace first, then load data." });
    return { ok: false, error: "not on workspace" };
  }
  let data;
  try {
    data = fs.readFileSync(filePath);
  } catch (e) {
    dialog.showMessageBox(mainWindow, { type: "error", message: `Could not read file: ${e.message}` });
    return { ok: false, error: String(e) };
  }
  // Send raw bytes; the renderer rebuilds a File and opens it in the Viewer.
  mainWindow.webContents.send("nir:openVolume", { name: path.basename(filePath), data });
  recordRecentVolume(filePath);
  return { ok: true };
}

async function openDataDialog() {
  if (!mainWindow) return;
  if (isOnControlCenter()) {
    dialog.showMessageBox(mainWindow, { type: "info", message: "Open the workspace first, then load data." });
    return;
  }
  const res = await dialog.showOpenDialog(mainWindow, {
    title: "Open imaging volume",
    properties: ["openFile"],
    filters: [{ name: "Imaging", extensions: ["nii", "gz", "mgz", "mgh"] }],
  });
  if (res.canceled || !res.filePaths[0]) return;
  openVolumeFromPath(res.filePaths[0]);
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
        label: "Settings",
        accelerator: "CmdOrCtrl+,",
        enabled: !onControl,
        click: () => navigateToControl(),
      },
      {
        label: "Open Workspace",
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

  // File menu: native Open Data + Open Recent (reopen by path).
  const recents = getRecentVolumes();
  const fileMenu = {
    label: "File",
    submenu: [
      { label: "Open Data…", accelerator: "CmdOrCtrl+O", click: () => openDataDialog() },
      {
        label: "Open Recent",
        submenu: recents.length
          ? recents
              .map((r) => ({ label: r.name, click: () => openVolumeFromPath(r.path) }))
              .concat([
                { type: "separator" },
                {
                  label: "Clear Recent",
                  click: () => {
                    desktopState.updateSettings({ recentVolumes: [] });
                    buildAppMenu();
                  },
                },
              ])
          : [{ label: "No recent files", enabled: false }],
      },
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
        label: "NeuroInsight on GitHub",
        click: () => shell.openExternal("https://github.com/phindagijimana/neuroinsight_research"),
      },
    ],
  };

  Menu.setApplicationMenu(Menu.buildFromTemplate([appMenu, fileMenu, { role: "editMenu" }, viewMenu, helpMenu]));
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

  // Native open-data dialog (also available via File > Open Data… / Cmd+O)
  ipcMain.handle("data:openDialog", wrap(() => openDataDialog()));

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
// Smooth launch: splash -> silent preflight + backend auto-start -> workspace.
// The control center is the fallback/Settings view, shown only if something
// needs attention (or if the user opts to start there).
// --------------------------------------------------------------------------
function createSplash() {
  splashWindow = new BrowserWindow({
    width: 460,
    height: 300,
    frame: false,
    resizable: false,
    center: true,
    backgroundColor: "#0b1f3a",
    alwaysOnTop: true,
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  splashWindow.loadFile(path.join(__dirname, "..", "renderer", "splash.html"));
  splashWindow.on("closed", () => {
    splashWindow = null;
  });
}

function setSplashStatus(text) {
  if (splashWindow && !splashWindow.isDestroyed()) {
    splashWindow.webContents
      .executeJavaScript(`window.setStatus && window.setStatus(${JSON.stringify(text)});`)
      .catch(() => {});
  }
}

function closeSplash() {
  if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close();
  splashWindow = null;
}

function showMainWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.show();
    mainWindow.focus();
  }
  closeSplash();
}

/** Fall back to the control center (Settings) and surface an optional reason. */
async function revealControlCenter(reason) {
  if (mainWindow) {
    await mainWindow.loadFile(controlCenterPath(), {
      search: reason ? "notice=" + encodeURIComponent(String(reason)) : "",
    });
    buildAppMenu();
  }
  showMainWindow();
}

async function runStartupSequence() {
  let settings = {};
  try {
    settings = desktopState.readSettings();
  } catch (_e) {
    // defaults
  }
  // Power users (and tests) can choose to land in the control center.
  if (settings.startInControlCenter === true || process.env.NIR_START_IN_CONTROL === "1") {
    return revealControlCenter();
  }

  setSplashStatus("Running checks…");
  let report;
  try {
    report = await preflight.runPreflight();
    desktopState.updateSettings({ lastPreflightAt: report.generatedAt, lastPreflightReady: report.ready });
  } catch (e) {
    desktopState.appendLog("startup_preflight_error", { error: String(e) });
    return revealControlCenter("Could not run startup checks — see Preflight.");
  }
  if (!report.ready) {
    desktopState.appendLog("startup_blocked", { blockers: report.blockers });
    // First-run guidance: in container mode the blocker is almost always Docker.
    const dockerMissing = (report.checks && report.checks.docker && !report.checks.docker.ok) || false;
    if (process.env.NIR_RUNTIME === "container" && dockerMissing && mainWindow) {
      const choice = dialog.showMessageBoxSync(mainWindow, {
        type: "warning",
        message: "Docker is required",
        detail: "NeuroInsight runs its engine in Docker. Install/start Docker Desktop, then reopen the app.",
        buttons: ["Get Docker", "Open Settings"],
        defaultId: 0,
        cancelId: 1,
      });
      if (choice === 0) shell.openExternal("https://www.docker.com/products/docker-desktop/");
    }
    return revealControlCenter((report.blockers && report.blockers[0]) || "Environment not ready.");
  }

  // The container engine may pull a multi-GB image on first run.
  setSplashStatus(process.env.NIR_RUNTIME === "container" ? "Starting engine (first run may download)…" : "Starting engine…");
  const start = await backendManager.start({ onProgress: (m) => setSplashStatus(m) });
  desktopState.appendLog("backend_autostart", { ok: start.ok });
  if (!start.ok) {
    const err = (start.backend && start.backend.error) || start.error || "Backend failed to start.";
    return revealControlCenter(err);
  }

  setSplashStatus("Opening workspace…");
  const nav = await navigateToNIR();
  if (!nav.ok) {
    return revealControlCenter(nav.error || "Could not open the workspace.");
  }
  showMainWindow();
}

// --------------------------------------------------------------------------
// Crash & error capture — log everything to the desktop state dir (the same
// place the diagnostics bundle reads), and show the user one clear dialog
// instead of a silent failure. Errors stay local; nothing is uploaded.
// (To forward to a service later, init Sentry here behind process.env.NIR_SENTRY_DSN.)
// --------------------------------------------------------------------------
let crashDialogShown = false;
function reportFatal(kind, err) {
  const message = err && err.stack ? err.stack : String(err);
  try {
    desktopState.appendLog("fatal_error", { kind, message });
  } catch (_e) {
    // logging is best-effort
  }
  if (crashDialogShown) return;
  crashDialogShown = true;
  try {
    dialog.showMessageBox({
      type: "error",
      title: "NeuroInsight hit an unexpected error",
      message: "Something went wrong. You can keep working, but if it persists, export a diagnostics bundle from Settings and share it.",
      detail: String(message).slice(0, 1500),
      buttons: ["OK"],
    });
  } catch (_e) {
    // dialog may be unavailable very early — already logged above
  }
}

/** Self-verify the packaged app against the baked-in integrity manifest
 *  (build/after_pack.js writes app-integrity.json next to app.asar). While the
 *  app is unsigned this catches tampering/corruption of the app's code. No-op in
 *  dev (no asar) or if the manifest is absent. */
function verifyIntegrity() {
  if (!app.isPackaged) return;
  try {
    const manifestPath = path.join(process.resourcesPath, "app-integrity.json");
    const asarPath = path.join(process.resourcesPath, "app.asar");
    if (!fs.existsSync(manifestPath) || !fs.existsSync(asarPath)) return;
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    const expected = manifest && manifest.files && manifest.files["app.asar"];
    if (!expected) return;
    const hash = crypto.createHash("sha256");
    const stream = fs.createReadStream(asarPath);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("end", () => {
      const actual = hash.digest("hex");
      if (actual === expected) {
        desktopState.appendLog("integrity_ok", {});
      } else {
        desktopState.appendLog("integrity_mismatch", { expected, actual });
        try {
          dialog.showMessageBox({
            type: "warning",
            title: "Integrity check failed",
            message:
              "This installation appears to have been modified or corrupted. For your safety, reinstall NeuroInsight from an official release.",
            buttons: ["Continue anyway"],
          });
        } catch (_e) {
          // dialog best-effort
        }
      }
    });
    stream.on("error", () => {
      /* best effort */
    });
  } catch (_e) {
    // integrity check is best-effort
  }
}

function installCrashHandlers() {
  process.on("uncaughtException", (err) => reportFatal("uncaughtException", err));
  process.on("unhandledRejection", (reason) => reportFatal("unhandledRejection", reason));
  app.on("render-process-gone", (_e, _wc, details) =>
    reportFatal("render-process-gone", `${details.reason} (exitCode ${details.exitCode})`)
  );
  app.on("child-process-gone", (_e, details) =>
    reportFatal("child-process-gone", `${details.type}: ${details.reason}`)
  );
}

// --------------------------------------------------------------------------
// App lifecycle
// --------------------------------------------------------------------------
app.whenReady().then(async () => {
  initModules();
  installCrashHandlers();
  verifyIntegrity();
  registerIpc();
  tryAutoImportLicense();
  buildAppMenu();

  // Silent auto-update check (no-op in dev / when no feed is published).
  updater.checkForUpdates({ silent: true }).then((r) => {
    if (r && (r.version || r.skipped)) desktopState.appendLog("update_check", r);
  });

  createSplash();
  createWindow({ show: false });
  await runStartupSequence();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow({ show: true });
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
