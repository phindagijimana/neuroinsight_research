/**
 * containerManager — runs the NIR backend as the all-in-one Docker container
 * (the single-container deployment built by docker/allinone/).
 *
 * Mirrors backendManager's interface (init/start/stopBackend/stopAll/getStatus/
 * getRuntimeInfo) so it can be swapped in transparently when NIR_RUNTIME=container.
 * The desktop then needs only Docker — no venv, no separate infra.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const http = require("http");
const net = require("net");
const { spawnSync, spawn } = require("child_process");

const IMAGE_DEFAULT = "nir-allinone:dev";
const CONTAINER_NAME = "nir-allinone";
const DEFAULT_PORT = 8800;
const PORT_SCAN = 20;

let cfg = null;

function isWindows() {
  return process.platform === "win32";
}

function docker(args, opts = {}) {
  return spawnSync("docker", args, { encoding: "utf8", timeout: opts.timeout || 30000 });
}

function dockerAvailable() {
  const r = docker(["version", "--format", "{{.Server.Version}}"], { timeout: 8000 });
  return !r.error && r.status === 0;
}

function imageExists(image) {
  return docker(["image", "inspect", image]).status === 0;
}

function containerExists(name) {
  return docker(["inspect", "-f", "{{.State.Running}}", name]).status === 0;
}

function init({ stateDir, repoDir } = {}) {
  if (!stateDir) throw new Error("containerManager.init requires { stateDir }");
  const runtimeDir = path.join(stateDir, "runtime");
  fs.mkdirSync(runtimeDir, { recursive: true });
  const dataDir = process.env.NIR_DATA_DIR || path.join(os.homedir(), ".nir", "data");
  fs.mkdirSync(dataDir, { recursive: true });
  cfg = {
    stateDir,
    runtimeDir,
    repoDir: repoDir || "",
    image: process.env.NIR_IMAGE || IMAGE_DEFAULT,
    name: process.env.NIR_CONTAINER_NAME || CONTAINER_NAME,
    dataDir,
    port: Number(process.env.NIR_DESKTOP_BACKEND_PORT) || DEFAULT_PORT,
    logFiles: {
      backend: path.join(runtimeDir, "container.log"),
      celery: path.join(runtimeDir, "container.log"),
    },
  };
  return cfg;
}

function requireInit() {
  if (!cfg) throw new Error("containerManager.init must be called before use");
  return cfg;
}

// ---- health ---------------------------------------------------------------
function probeHealth(port, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port, path: "/health", timeout: timeoutMs }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
  });
}

async function waitForHealth(port, totalMs = 150000, stepMs = 2000) {
  const start = Date.now();
  while (Date.now() - start < totalMs) {
    /* eslint-disable no-await-in-loop */
    if (await probeHealth(port)) return true;
    await new Promise((r) => setTimeout(r, stepMs));
    /* eslint-enable no-await-in-loop */
  }
  return false;
}

function portListening(port) {
  return new Promise((resolve) => {
    const s = net.createConnection({ host: "127.0.0.1", port });
    s.setTimeout(400);
    s.once("connect", () => {
      s.destroy();
      resolve(true);
    });
    s.once("timeout", () => {
      s.destroy();
      resolve(false);
    });
    s.once("error", () => resolve(false));
  });
}

async function findUsablePort(preferred) {
  for (let i = 0; i <= PORT_SCAN; i += 1) {
    const port = preferred + i;
    /* eslint-disable no-await-in-loop */
    if (await probeHealth(port, 500)) return { port, reused: true };
    if (!(await portListening(port))) return { port, reused: false };
    /* eslint-enable no-await-in-loop */
  }
  return { port: preferred, reused: false };
}

// ---- run args (mirror docker/allinone/run.sh) -----------------------------
function buildRunArgs(c) {
  const args = ["run", "-d", "--name", c.name, "-p", `127.0.0.1:${c.port}:8000`, "-v", `${c.dataDir}:/data`];
  if (!isWindows() && fs.existsSync("/var/run/docker.sock")) {
    args.push("-v", "/var/run/docker.sock:/var/run/docker.sock");
  }
  const sshDir = path.join(os.homedir(), ".ssh");
  if (fs.existsSync(sshDir)) {
    args.push("-v", `${sshDir}:/home/neuroinsight/.ssh:ro`);
  }
  // Docker Desktop (macOS/Windows) exposes the host SSH agent at a magic socket.
  if (fs.existsSync("/run/host-services/ssh-auth.sock")) {
    args.push("-v", "/run/host-services/ssh-auth.sock:/ssh-agent", "-e", "SSH_AUTH_SOCK=/ssh-agent");
  } else if (process.env.SSH_AUTH_SOCK && fs.existsSync(process.env.SSH_AUTH_SOCK)) {
    args.push("-v", `${process.env.SSH_AUTH_SOCK}:/ssh-agent`, "-e", "SSH_AUTH_SOCK=/ssh-agent");
  }
  args.push(c.image);
  return args;
}

async function start() {
  const c = requireInit();
  if (!dockerAvailable()) {
    return { ok: false, error: "Docker is not available — install/start Docker Desktop." };
  }
  if (!imageExists(c.image)) {
    // Try to pull (published image); local dev images won't pull and will error clearly.
    const pull = docker(["pull", c.image], { timeout: 600000 });
    if (pull.status !== 0) {
      return {
        ok: false,
        error: `Image ${c.image} not found locally and pull failed. Build it with docker/allinone or set NIR_IMAGE.`,
      };
    }
  }

  // Already healthy on the port? reuse.
  if (await probeHealth(c.port, 800)) {
    return { ok: true, reused: true, port: c.port, url: `http://localhost:${c.port}`, backend: { reused: true } };
  }
  const picked = await findUsablePort(c.port);
  c.port = picked.port;
  if (picked.reused) {
    return { ok: true, reused: true, port: c.port, url: `http://localhost:${c.port}`, backend: { reused: true } };
  }

  // Remove any stale container of the same name, then run.
  docker(["rm", "-f", c.name]);
  const run = docker(buildRunArgs(c), { timeout: 60000 });
  if (run.status !== 0) {
    return { ok: false, error: `docker run failed: ${(run.stderr || "").trim()}`, backend: { error: run.stderr } };
  }

  const healthy = await waitForHealth(c.port);
  if (!healthy) {
    return {
      ok: false,
      error: `Container did not become healthy on :${c.port} (first run can take ~1 min). docker logs ${c.name}`,
      port: c.port,
      backend: { error: "health timeout" },
    };
  }
  return { ok: true, reused: false, port: c.port, url: `http://localhost:${c.port}`, backend: { reused: false } };
}

function dumpLogs() {
  const c = requireInit();
  try {
    const r = docker(["logs", "--tail", "400", c.name]);
    fs.writeFileSync(c.logFiles.backend, (r.stdout || "") + (r.stderr || ""));
  } catch (_e) {
    // best effort
  }
}

function stopBackend() {
  const c = requireInit();
  dumpLogs();
  const stop = docker(["stop", c.name]);
  docker(["rm", "-f", c.name]);
  return { ok: true, killed: stop.status === 0 };
}

function stopAll() {
  return { ok: true, backend: stopBackend() };
}

async function getStatus() {
  const c = requireInit();
  const healthy = await probeHealth(c.port, 1500);
  const running = containerExists(c.name) || healthy;
  return {
    backend: { running, healthy, pid: null, port: c.port, url: `http://localhost:${c.port}`, container: c.name },
    celery: { running, pid: null }, // worker runs inside the same container
    repoDir: c.repoDir,
    mode: "container",
    image: c.image,
  };
}

function getRuntimeInfo() {
  const c = requireInit();
  return {
    mode: "container",
    image: c.image,
    container: c.name,
    dataDir: c.dataDir,
    port: c.port,
    runtimeDir: c.runtimeDir,
    logFiles: { ...c.logFiles },
  };
}

module.exports = {
  init,
  start,
  startBackend: start,
  stopBackend,
  stopAll,
  getStatus,
  getRuntimeInfo,
  dockerAvailable,
  imageExists,
};
