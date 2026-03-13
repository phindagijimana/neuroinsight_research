const fs = require("fs");
const path = require("path");

const defaultSettings = {
  autoOpenOnStart: false,
  lastKnownPort: null,
  lastMode: "control", // control | nir
  updatedAt: null,
};

let paths = null;

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function initState(userDataDir) {
  const stateDir = path.join(userDataDir, "nir-desktop");
  const logsDir = path.join(stateDir, "logs");
  ensureDir(logsDir);
  paths = {
    stateDir,
    settingsFile: path.join(stateDir, "settings.json"),
    logFile: path.join(logsDir, "desktop.log"),
  };
}

function requireInit() {
  if (!paths) {
    throw new Error("desktopState.initState must be called before use");
  }
}

function readSettings() {
  requireInit();
  try {
    if (!fs.existsSync(paths.settingsFile)) return { ...defaultSettings };
    const raw = fs.readFileSync(paths.settingsFile, "utf8");
    const parsed = JSON.parse(raw);
    return { ...defaultSettings, ...parsed };
  } catch (_e) {
    return { ...defaultSettings };
  }
}

function writeSettings(next) {
  requireInit();
  const merged = {
    ...defaultSettings,
    ...next,
    updatedAt: new Date().toISOString(),
  };
  fs.writeFileSync(paths.settingsFile, JSON.stringify(merged, null, 2), "utf8");
  return merged;
}

function updateSettings(patch) {
  const current = readSettings();
  return writeSettings({ ...current, ...patch });
}

function appendLog(event, payload = {}) {
  requireInit();
  const line = JSON.stringify({
    ts: new Date().toISOString(),
    event,
    ...payload,
  });
  fs.appendFileSync(paths.logFile, `${line}\n`, "utf8");
}

function getPaths() {
  requireInit();
  return { ...paths };
}

module.exports = {
  initState,
  readSettings,
  updateSettings,
  appendLog,
  getPaths,
};
