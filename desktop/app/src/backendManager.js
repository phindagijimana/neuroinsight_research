/**
 * backendManager — local process manager for the NIR backend lifecycle.
 *
 * Phase 1 deliverable: start/stop the existing FastAPI backend (uvicorn) and the
 * Celery worker as child processes, track PIDs + logs under the desktop state
 * directory, and report status (including a /health probe).
 *
 * This does NOT modify or call ./research — it launches the same backend the CLI
 * does, directly, using the repo's virtualenv Python when available.
 */
const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");
const platformAdapter = require("./platformAdapter");
const containerManager = require("./containerManager");

const DEFAULT_PORT = 3001;
const PORT_SCAN_LIMIT = 10; // try DEFAULT_PORT .. DEFAULT_PORT+10

let cfg = null;
// When NIR_RUNTIME=container (or settings.runtimeMode), the backend runs as the
// all-in-one Docker container and every call delegates to containerManager.
let containerMode = false;
const procs = { backend: null, celery: null };

function detectMode() {
  if (process.env.NIR_RUNTIME) return process.env.NIR_RUNTIME;
  try {
    const s = require("./desktopState").readSettings();
    if (s && s.runtimeMode) return s.runtimeMode;
  } catch (_e) {
    // desktopState not initialized yet / no setting — fall through
  }
  return "process";
}

function isWindows() {
  return process.platform === "win32";
}

function resolveRepoDir() {
  if (process.env.NIR_REPO_DIR && fs.existsSync(process.env.NIR_REPO_DIR)) {
    return path.resolve(process.env.NIR_REPO_DIR);
  }
  // desktop/app/src -> repo root is three levels up
  const guess = path.resolve(__dirname, "..", "..", "..");
  return guess;
}

function resolvePython(repoDir) {
  // Prefer the repo virtualenv created by `./research install`.
  const venvPython = isWindows()
    ? path.join(repoDir, "venv", "Scripts", "python.exe")
    : path.join(repoDir, "venv", "bin", "python");
  if (fs.existsSync(venvPython)) return venvPython;
  return platformAdapter.resolvePythonCommand();
}

/** Locate a self-contained backend binary (PyInstaller bundle), if shipped.
 *  When present it removes the need for a Python venv on the target machine. */
function resolveBackendBin(repoDir) {
  const exe = isWindows() ? "nir-backend.exe" : "nir-backend";
  const candidates = [];
  if (process.env.NIR_BACKEND_BIN) candidates.push(process.env.NIR_BACKEND_BIN);
  // Packaged app: shipped under resources/backend/nir-backend/.
  if (process.resourcesPath) candidates.push(path.join(process.resourcesPath, "backend", "nir-backend", exe));
  // Local build output.
  candidates.push(path.join(repoDir, "desktop", "dist", "backend", "nir-backend", exe));
  for (const c of candidates) {
    if (c && fs.existsSync(c)) return c;
  }
  return null;
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function init({ stateDir, repoDir } = {}) {
  if (!stateDir) throw new Error("backendManager.init requires { stateDir }");
  containerMode = detectMode() === "container";
  if (containerMode) {
    containerManager.init({ stateDir, repoDir });
  }
  const runtimeDir = path.join(stateDir, "runtime");
  ensureDir(runtimeDir);
  const resolvedRepo = repoDir || resolveRepoDir();
  cfg = {
    stateDir,
    runtimeDir,
    repoDir: resolvedRepo,
    pythonCmd: resolvePython(resolvedRepo),
    backendBin: resolveBackendBin(resolvedRepo),
    port: Number(process.env.NIR_DESKTOP_BACKEND_PORT) || DEFAULT_PORT,
    logFiles: {
      backend: path.join(runtimeDir, "backend.log"),
      celery: path.join(runtimeDir, "celery.log"),
    },
    pidFiles: {
      backend: path.join(runtimeDir, "backend.pid"),
      celery: path.join(runtimeDir, "celery.pid"),
    },
  };
  return cfg;
}

function requireInit() {
  if (!cfg) throw new Error("backendManager.init must be called before use");
  return cfg;
}

function backendEntryExists() {
  const c = requireInit();
  return fs.existsSync(path.join(c.repoDir, "backend", "main.py"));
}

// ---- PID helpers ---------------------------------------------------------
function readPid(file) {
  try {
    const txt = fs.readFileSync(file, "utf8").trim();
    const pid = Number(txt);
    return Number.isInteger(pid) && pid > 0 ? pid : null;
  } catch (_e) {
    return null;
  }
}

function writePid(file, pid) {
  try {
    fs.writeFileSync(file, String(pid), "utf8");
  } catch (_e) {
    // best effort
  }
}

function clearPid(file) {
  try {
    if (fs.existsSync(file)) fs.unlinkSync(file);
  } catch (_e) {
    // best effort
  }
}

function isPidAlive(pid) {
  if (!pid) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === "EPERM"; // exists but not signalable
  }
}

// ---- health probe --------------------------------------------------------
function probeHealth(port, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(
      { host: "127.0.0.1", port, path: "/health", timeout: timeoutMs },
      (res) => {
        res.resume();
        resolve(res.statusCode === 200);
      }
    );
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
  });
}

async function waitForHealth(port, totalMs = 60000, stepMs = 1000) {
  const start = Date.now();
  while (Date.now() - start < totalMs) {
    /* eslint-disable no-await-in-loop */
    if (await probeHealth(port)) return true;
    await new Promise((r) => setTimeout(r, stepMs));
    /* eslint-enable no-await-in-loop */
  }
  return false;
}

async function findUsablePort(preferred) {
  // Reuse the preferred port if a healthy NIR backend already answers there;
  // otherwise pick the first port in range with nothing listening.
  for (let i = 0; i <= PORT_SCAN_LIMIT; i += 1) {
    const port = preferred + i;
    /* eslint-disable no-await-in-loop */
    const healthy = await probeHealth(port, 500);
    if (healthy) return { port, reused: true };
    const inUse = await isPortListening(port);
    if (!inUse) return { port, reused: false };
    /* eslint-enable no-await-in-loop */
  }
  return { port: preferred, reused: false };
}

function isPortListening(port) {
  return new Promise((resolve) => {
    const socket = require("net").createConnection({ host: "127.0.0.1", port });
    socket.setTimeout(500);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.once("error", () => resolve(false));
  });
}

// ---- spawning ------------------------------------------------------------
function spawnLogged(name, command, args, logFile) {
  const c = requireInit();
  const out = fs.openSync(logFile, "a");
  const errOut = fs.openSync(logFile, "a");
  const child = spawn(command, args, {
    cwd: c.repoDir,
    // NIR_REPO_DIR lets a bundled (frozen) backend find the real .env + plugins.
    env: { ...process.env, PYTHONUNBUFFERED: "1", NIR_REPO_DIR: c.repoDir },
    stdio: ["ignore", out, errOut],
    detached: false,
    windowsHide: true,
  });
  child.on("exit", (code, signal) => {
    try {
      fs.appendFileSync(
        logFile,
        `\n[nir-desktop] ${name} exited code=${code} signal=${signal} at ${new Date().toISOString()}\n`
      );
    } catch (_e) {
      // ignore
    }
  });
  return child;
}

async function startBackend() {
  if (containerMode) return containerManager.start();
  const c = requireInit();
  // Prefer the venv backend when the repo is present — it serves the SPA and
  // Celery fully. The bundled self-contained binary is the fallback that removes
  // the Python/venv requirement for distribution.
  const venvOk = !!(c.pythonCmd && backendEntryExists());
  if (!venvOk && !c.backendBin) {
    return {
      ok: false,
      error: "No backend available — install the venv (./research install) or ship the bundled backend.",
    };
  }

  // Already healthy? Reuse.
  if (await probeHealth(c.port, 800)) {
    return { ok: true, reused: true, port: c.port, url: `http://localhost:${c.port}` };
  }

  const picked = await findUsablePort(c.port);
  c.port = picked.port;
  if (picked.reused) {
    return { ok: true, reused: true, port: c.port, url: `http://localhost:${c.port}` };
  }

  let cmd;
  let args;
  if (venvOk) {
    const parts = String(c.pythonCmd).split(/\s+/);
    cmd = parts[0];
    args = [...parts.slice(1), "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", String(c.port)];
  } else {
    cmd = c.backendBin;
    args = ["--host", "127.0.0.1", "--port", String(c.port)];
  }

  fs.appendFileSync(
    c.logFiles.backend,
    `\n[nir-desktop] starting backend: ${cmd} ${args.join(" ")} (cwd=${c.repoDir}) at ${new Date().toISOString()}\n`
  );

  const child = spawnLogged("backend", cmd, args, c.logFiles.backend);
  procs.backend = child;
  writePid(c.pidFiles.backend, child.pid);

  const healthy = await waitForHealth(c.port);
  if (!healthy) {
    return {
      ok: false,
      error: `Backend did not become healthy on port ${c.port}. See ${c.logFiles.backend}.`,
      port: c.port,
    };
  }
  return { ok: true, reused: false, port: c.port, url: `http://localhost:${c.port}` };
}

function startCelery() {
  const c = requireInit();
  if (!c.pythonCmd) return { ok: false, error: "Python runtime not found." };

  if (isPidAlive(readPid(c.pidFiles.celery))) {
    return { ok: true, reused: true };
  }

  const parts = String(c.pythonCmd).split(/\s+/);
  const cmd = parts[0];
  const baseArgs = parts.slice(1);
  const args = [
    ...baseArgs,
    "-m",
    "celery",
    "-A",
    "backend.core.celery_app:celery_app",
    "worker",
    "--loglevel=info",
    "--concurrency=2",
    "-Q",
    "docker_jobs,celery",
  ];

  try {
    fs.appendFileSync(
      c.logFiles.celery,
      `\n[nir-desktop] starting celery worker at ${new Date().toISOString()}\n`
    );
    const child = spawnLogged("celery", cmd, args, c.logFiles.celery);
    procs.celery = child;
    writePid(c.pidFiles.celery, child.pid);
    return { ok: true, reused: false };
  } catch (e) {
    // Celery is best-effort in Phase 1.
    return { ok: false, error: String(e) };
  }
}

async function start() {
  if (containerMode) return containerManager.start();
  const backend = await startBackend();
  let celery = { ok: false, skipped: true };
  if (backend.ok) {
    celery = startCelery();
  }
  const status = await getStatus();
  return { ok: backend.ok, backend, celery, status };
}

function killByPidFile(pidFile, child) {
  const c = requireInit();
  let killed = false;
  if (child && !child.killed) {
    try {
      child.kill("SIGTERM");
      killed = true;
    } catch (_e) {
      // fall through to pid kill
    }
  }
  const pid = readPid(pidFile);
  if (pid && isPidAlive(pid)) {
    try {
      process.kill(pid, "SIGTERM");
      killed = true;
    } catch (_e) {
      // best effort
    }
  }
  clearPid(pidFile);
  return killed;
}

function stopBackend() {
  if (containerMode) return containerManager.stopBackend();
  const c = requireInit();
  const killed = killByPidFile(c.pidFiles.backend, procs.backend);
  procs.backend = null;
  return { ok: true, killed };
}

function stopCelery() {
  const c = requireInit();
  const killed = killByPidFile(c.pidFiles.celery, procs.celery);
  procs.celery = null;
  return { ok: true, killed };
}

function stopAll() {
  if (containerMode) return containerManager.stopAll();
  const b = stopBackend();
  const ce = stopCelery();
  return { ok: true, backend: b, celery: ce };
}

async function getStatus() {
  if (containerMode) return containerManager.getStatus();
  const c = requireInit();
  const backendPid = procs.backend ? procs.backend.pid : readPid(c.pidFiles.backend);
  const celeryPid = procs.celery ? procs.celery.pid : readPid(c.pidFiles.celery);
  const healthy = await probeHealth(c.port, 1200);
  const backendRunning = healthy || isPidAlive(backendPid);
  return {
    backend: {
      running: backendRunning,
      healthy,
      pid: backendPid || null,
      port: c.port,
      url: `http://localhost:${c.port}`,
    },
    celery: {
      running: isPidAlive(celeryPid),
      pid: celeryPid || null,
    },
    repoDir: c.repoDir,
    pythonCmd: c.pythonCmd,
  };
}

function getRuntimeInfo() {
  if (containerMode) return containerManager.getRuntimeInfo();
  const c = requireInit();
  return {
    repoDir: c.repoDir,
    pythonCmd: c.pythonCmd,
    port: c.port,
    runtimeDir: c.runtimeDir,
    logFiles: { ...c.logFiles },
    pidFiles: { ...c.pidFiles },
  };
}

module.exports = {
  init,
  start,
  startBackend,
  startCelery,
  stopBackend,
  stopCelery,
  stopAll,
  getStatus,
  getRuntimeInfo,
  backendEntryExists,
};
