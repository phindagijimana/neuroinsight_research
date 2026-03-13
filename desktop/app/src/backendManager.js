const fs = require("fs");
const net = require("net");
const { spawn } = require("child_process");
const http = require("http");
const path = require("path");
const platformAdapter = require("./platformAdapter");

const repoRoot = path.resolve(__dirname, "..", "..", "..");
const candidatePorts = [3000, 3001];
const START_TIMEOUT_MS = 45000;

let managerPaths = null;
let runtimeState = {
  backendPid: null,
  celeryPid: null,
  port: null,
  pythonCmd: null,
};

function initDesktopRuntime(paths) {
  managerPaths = {
    stateDir: paths.stateDir,
    logsDir: path.join(paths.stateDir, "logs"),
    backendLogFile: path.join(paths.stateDir, "logs", "backend-runtime.log"),
    celeryLogFile: path.join(paths.stateDir, "logs", "celery-runtime.log"),
  };
  fs.mkdirSync(managerPaths.logsDir, { recursive: true });
}

function ensureInit() {
  if (!managerPaths) {
    throw new Error("backendManager.initDesktopRuntime must be called before use");
  }
}

function isPidAlive(pid) {
  if (!pid || typeof pid !== "number") return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (_e) {
    return false;
  }
}

function appendRuntimeLog(filePath, message) {
  const line = `[${new Date().toISOString()}] ${message}\n`;
  fs.appendFileSync(filePath, line, "utf8");
}

function runShellCommand(command, cwd, timeoutMs = 600000) {
  return new Promise((resolve) => {
    const shellSpec = platformAdapter.getShellSpawnSpec(command);
    const child = spawn(shellSpec.command, shellSpec.args, {
      cwd,
      env: process.env,
    });
    let stdout = "";
    let stderr = "";
    let finished = false;

    const done = (result) => {
      if (finished) return;
      finished = true;
      resolve(result);
    };

    const timer = setTimeout(() => {
      try {
        child.kill("SIGTERM");
      } catch (_e) {
        // no-op
      }
      done({
        ok: false,
        code: -1,
        stdout,
        stderr: `${stderr}\nCommand timed out after ${timeoutMs}ms`,
      });
    }, timeoutMs);

    child.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      done({
        ok: false,
        code: -1,
        stdout,
        stderr: `${stderr}\n${err.message}`,
      });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      done({
        ok: code === 0,
        code: code ?? -1,
        stdout,
        stderr,
      });
    });
  });
}

function waitForMs(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function healthCheck(port) {
  return new Promise((resolve) => {
    const req = http.get(
      {
        host: "127.0.0.1",
        port,
        path: "/health",
        timeout: 2500,
      },
      (res) => {
        const ok = res.statusCode === 200;
        res.resume();
        resolve(ok);
      }
    );

    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
  });
}

async function detectRunningPort() {
  for (const p of candidatePorts) {
    // eslint-disable-next-line no-await-in-loop
    if (await healthCheck(p)) return p;
  }
  return null;
}

function findAvailablePort() {
  return new Promise((resolve) => {
    const tryNext = (idx) => {
      if (idx >= candidatePorts.length) {
        resolve(null);
        return;
      }
      const port = candidatePorts[idx];
      const server = net.createServer();
      server.unref();
      server.on("error", () => tryNext(idx + 1));
      server.listen(port, "127.0.0.1", () => {
        server.close(() => resolve(port));
      });
    };
    tryNext(0);
  });
}

async function ensureFrontendBuild() {
  const frontendDir = path.join(repoRoot, "frontend");
  const distDir = path.join(frontendDir, "dist");
  if (!fs.existsSync(frontendDir)) {
    return { ok: true, skipped: true, reason: "frontend directory missing" };
  }
  if (fs.existsSync(distDir)) {
    return { ok: true, skipped: true, reason: "frontend/dist already exists" };
  }
  const hasPackageJson = fs.existsSync(path.join(frontendDir, "package.json"));
  if (!hasPackageJson) {
    return { ok: true, skipped: true, reason: "frontend package.json missing" };
  }
  const npmCommand = platformAdapter.resolveNpmCommand();
  const buildRes = await runShellCommand(`${npmCommand} run build`, frontendDir, 900000);
  return { ...buildRes, skipped: false };
}

function spawnManagedProcess(command, args, logFile, extraEnv = {}) {
  const outFd = fs.openSync(logFile, "a");
  const child = spawn(command, args, {
    cwd: repoRoot,
    env: { ...process.env, ...extraEnv },
    detached: true,
    stdio: ["ignore", outFd, outFd],
  });
  child.unref();
  fs.closeSync(outFd);
  return child.pid;
}

function spawnPythonModule(pythonCmd, moduleName, moduleArgs, logFile, extraEnv = {}) {
  const cmdParts = String(pythonCmd).trim().split(/\s+/);
  const command = cmdParts[0];
  const prefixArgs = cmdParts.slice(1);
  return spawnManagedProcess(command, [...prefixArgs, "-m", moduleName, ...moduleArgs], logFile, extraEnv);
}

async function waitForBackendHealth(port, timeoutMs = START_TIMEOUT_MS) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    // eslint-disable-next-line no-await-in-loop
    if (await healthCheck(port)) return true;
    // eslint-disable-next-line no-await-in-loop
    await waitForMs(1000);
  }
  return false;
}

async function terminatePid(pid) {
  if (!isPidAlive(pid)) return;
  try {
    process.kill(pid, "SIGTERM");
  } catch (_e) {
    return;
  }
  const start = Date.now();
  while (Date.now() - start < 6000) {
    // eslint-disable-next-line no-await-in-loop
    await waitForMs(200);
    if (!isPidAlive(pid)) return;
  }
  try {
    process.kill(pid, "SIGKILL");
  } catch (_e) {
    // already dead
  }
}

async function getStatus() {
  const port = await detectRunningPort();
  return {
    running: port !== null,
    port,
    managed: Boolean(runtimeState.backendPid && isPidAlive(runtimeState.backendPid)),
  };
}

function getRuntimeInfo() {
  ensureInit();
  return {
    managedPids: {
      backendPid: runtimeState.backendPid,
      backendAlive: isPidAlive(runtimeState.backendPid),
      celeryPid: runtimeState.celeryPid,
      celeryAlive: isPidAlive(runtimeState.celeryPid),
    },
    configuredPort: runtimeState.port,
    pythonCmd: runtimeState.pythonCmd,
    logFiles: {
      backend: managerPaths.backendLogFile,
      celery: managerPaths.celeryLogFile,
    },
  };
}

async function startBackend() {
  ensureInit();
  const pythonCmd = platformAdapter.resolvePythonCommand();
  runtimeState.pythonCmd = pythonCmd;
  if (!pythonCmd) {
    return {
      ok: false,
      code: -1,
      stdout: "",
      stderr: "Python runtime not found. Set NIR_DESKTOP_PYTHON or install python3.",
      running: false,
      port: null,
      managed: false,
    };
  }

  const existing = await detectRunningPort();
  if (existing) {
    runtimeState.port = existing;
    return {
      ok: true,
      code: 0,
      stdout: `Backend already running on port ${existing}.`,
      stderr: "",
      running: true,
      port: existing,
      managed: Boolean(runtimeState.backendPid && isPidAlive(runtimeState.backendPid)),
    };
  }

  const frontendRes = await ensureFrontendBuild();
  if (!frontendRes.ok) {
    return {
      ...frontendRes,
      running: false,
      port: null,
      managed: false,
    };
  }

  const port = await findAvailablePort();
  if (!port) {
    return {
      ok: false,
      code: -1,
      stdout: "",
      stderr: "No free desktop backend port found (expected 3000 or 3001).",
      running: false,
      port: null,
      managed: false,
    };
  }

  appendRuntimeLog(managerPaths.backendLogFile, `Starting backend on port ${port}`);
  const backendPid = spawnPythonModule(
    pythonCmd,
    "uvicorn",
    ["backend.main:app", "--host", "0.0.0.0", "--port", String(port), "--workers", "2"],
    managerPaths.backendLogFile,
    {
      ENVIRONMENT: process.env.ENVIRONMENT || "development",
      API_PORT: String(port),
      PYTHONPATH: repoRoot,
    }
  );
  runtimeState.backendPid = backendPid;
  runtimeState.port = port;

  const healthy = await waitForBackendHealth(port);
  if (!healthy) {
    await terminatePid(backendPid);
    runtimeState.backendPid = null;
    runtimeState.port = null;
    return {
      ok: false,
      code: -1,
      stdout: "",
      stderr: `Backend failed health check on port ${port}. See ${managerPaths.backendLogFile}`,
      running: false,
      port: null,
      managed: false,
    };
  }

  // Celery is best-effort in Phase 1 runtime decoupling.
  appendRuntimeLog(managerPaths.celeryLogFile, "Starting celery worker");
  const celeryPid = spawnPythonModule(
    pythonCmd,
    "celery",
    ["-A", "backend.core.celery_app", "worker", "--loglevel=info", "-Q", "docker_jobs,celery", "--hostname=nir-desktop-worker@%h"],
    managerPaths.celeryLogFile,
    {
      ENVIRONMENT: process.env.ENVIRONMENT || "development",
      PYTHONPATH: repoRoot,
    }
  );
  runtimeState.celeryPid = celeryPid;

  let stdout = `Backend started on port ${port} (pid=${backendPid}).`;
  if (frontendRes.skipped) {
    stdout += ` Frontend build: ${frontendRes.reason}.`;
  } else {
    stdout += " Frontend build completed.";
  }

  const celeryAlive = isPidAlive(celeryPid);
  if (!celeryAlive) {
    runtimeState.celeryPid = null;
    return {
      ok: true,
      code: 0,
      stdout,
      stderr: `Celery worker did not stay alive. Check ${managerPaths.celeryLogFile}`,
      running: true,
      port,
      managed: true,
    };
  }

  const detectedPort = await detectRunningPort();
  return {
    ok: true,
    code: 0,
    stdout: `${stdout} Celery started (pid=${celeryPid}).`,
    stderr: "",
    running: detectedPort !== null,
    port: detectedPort,
    managed: true,
  };
}

async function stopBackendAppOnly() {
  const lines = [];
  if (runtimeState.backendPid && isPidAlive(runtimeState.backendPid)) {
    await terminatePid(runtimeState.backendPid);
    lines.push(`Stopped backend pid ${runtimeState.backendPid}.`);
  } else {
    lines.push("No managed backend process found.");
  }
  runtimeState.backendPid = null;
  runtimeState.port = null;
  const port = await detectRunningPort();
  return {
    ok: true,
    code: 0,
    stdout: lines.join(" "),
    stderr: "",
    running: port !== null,
    port,
    managed: false,
  };
}

async function stopBackendAll() {
  const lines = [];
  if (runtimeState.celeryPid && isPidAlive(runtimeState.celeryPid)) {
    await terminatePid(runtimeState.celeryPid);
    lines.push(`Stopped celery pid ${runtimeState.celeryPid}.`);
  } else {
    lines.push("No managed celery process found.");
  }
  if (runtimeState.backendPid && isPidAlive(runtimeState.backendPid)) {
    await terminatePid(runtimeState.backendPid);
    lines.push(`Stopped backend pid ${runtimeState.backendPid}.`);
  } else {
    lines.push("No managed backend process found.");
  }
  runtimeState.celeryPid = null;
  runtimeState.backendPid = null;
  runtimeState.port = null;
  const port = await detectRunningPort();
  return {
    ok: true,
    code: 0,
    stdout: lines.join(" "),
    stderr: "",
    running: port !== null,
    port,
    managed: false,
  };
}

module.exports = {
  repoRoot,
  initDesktopRuntime,
  getStatus,
  getRuntimeInfo,
  startBackend,
  stopBackendAppOnly,
  stopBackendAll,
};
