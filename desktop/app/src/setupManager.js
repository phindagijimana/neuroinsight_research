const path = require("path");
const fs = require("fs");
const net = require("net");
const crypto = require("crypto");
const { spawnSync, spawn } = require("child_process");
const platformAdapter = require("./platformAdapter");

const repoRoot = path.resolve(__dirname, "..", "..", "..");

function isWindows() {
  return process.platform === "win32";
}

function venvPythonPath() {
  return isWindows()
    ? path.join(repoRoot, "venv", "Scripts", "python.exe")
    : path.join(repoRoot, "venv", "bin", "python");
}

function venvExists() {
  return fs.existsSync(venvPythonPath());
}

function randomToken(bytes = 20) {
  return crypto.randomBytes(bytes).toString("hex");
}

function waitForMs(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function waitForPort(port, timeoutMs = 30000) {
  return new Promise((resolve) => {
    const start = Date.now();
    const tryConnect = () => {
      const sock = new net.Socket();
      sock.setTimeout(1000);
      sock.connect(port, "127.0.0.1", () => {
        sock.destroy();
        resolve(true);
      });
      sock.on("error", () => {
        sock.destroy();
        if (Date.now() - start > timeoutMs) { resolve(false); return; }
        setTimeout(tryConnect, 1000);
      });
      sock.on("timeout", () => {
        sock.destroy();
        if (Date.now() - start > timeoutMs) { resolve(false); return; }
        setTimeout(tryConnect, 1000);
      });
    };
    tryConnect();
  });
}

function runSync(cmd, args, cwd) {
  const res = spawnSync(cmd, args, {
    cwd: cwd || repoRoot,
    env: process.env,
    encoding: "utf8",
    timeout: 10000,
  });
  return {
    ok: res.status === 0 && !res.error,
    stdout: res.stdout || "",
    stderr: res.stderr || "",
  };
}

function runAsync(cmd, args, cwd, timeoutMs = 600000) {
  return new Promise((resolve) => {
    const child = spawn(cmd, args, {
      cwd: cwd || repoRoot,
      env: process.env,
    });
    let stdout = "";
    let stderr = "";
    let finished = false;
    const done = (r) => { if (!finished) { finished = true; resolve(r); } };
    const timer = setTimeout(() => {
      try { child.kill("SIGTERM"); } catch (_) {}
      done({ ok: false, stdout, stderr: stderr + "\nTimed out." });
    }, timeoutMs);
    child.stdout && child.stdout.on("data", (d) => { stdout += d.toString(); });
    child.stderr && child.stderr.on("data", (d) => { stderr += d.toString(); });
    child.on("error", (e) => { clearTimeout(timer); done({ ok: false, stdout, stderr: stderr + "\n" + e.message }); });
    child.on("close", (code) => { clearTimeout(timer); done({ ok: code === 0, stdout, stderr }); });
  });
}

// ---------------------------------------------------------------------------
// Setup steps
// ---------------------------------------------------------------------------

async function stepCheckPython(onProgress) {
  onProgress({ step: "python", label: "Checking Python 3.10+", status: "running" });
  const pyCmd = platformAdapter.resolvePythonCommand();
  if (!pyCmd) {
    onProgress({ step: "python", label: "Python not found — install Python 3.10+ from python.org", status: "error" });
    return { ok: false, error: "Python not found. Install Python 3.10+ from python.org and relaunch." };
  }
  const parts = pyCmd.split(" ");
  const res = runSync(parts[0], [...parts.slice(1), "--version"]);
  const match = (res.stdout + res.stderr).match(/Python (\d+)\.(\d+)/);
  if (match) {
    const [major, minor] = [parseInt(match[1]), parseInt(match[2])];
    if (major < 3 || (major === 3 && minor < 10)) {
      onProgress({ step: "python", label: `Python ${match[0]} is too old — 3.10+ required`, status: "error" });
      return { ok: false, error: `Python ${match[0]} found but 3.10+ is required.` };
    }
  }
  onProgress({ step: "python", label: "Python ready", status: "done" });
  return { ok: true, pythonCmd: pyCmd };
}

async function stepCreateVenv(pythonCmd, onProgress) {
  if (venvExists()) {
    onProgress({ step: "venv", label: "Python environment ready", status: "done" });
    return { ok: true };
  }
  onProgress({ step: "venv", label: "Creating Python environment…", status: "running" });
  const parts = pythonCmd.split(" ");
  const venvDir = path.join(repoRoot, "venv");
  const res = runSync(parts[0], [...parts.slice(1), "-m", "venv", venvDir]);
  if (!res.ok) {
    onProgress({ step: "venv", label: "Failed to create Python environment", status: "error" });
    return { ok: false, error: res.stderr || "venv creation failed." };
  }
  onProgress({ step: "venv", label: "Python environment created", status: "done" });
  return { ok: true };
}

async function stepInstallDeps(onProgress) {
  onProgress({ step: "deps", label: "Installing Python dependencies…", status: "running" });
  const reqFile = path.join(repoRoot, "requirements.txt");
  if (!fs.existsSync(reqFile)) {
    onProgress({ step: "deps", label: "No requirements.txt — skipped", status: "skipped" });
    return { ok: true };
  }
  const venvPy = venvPythonPath();
  const res = await runAsync(venvPy, ["-m", "pip", "install", "-r", reqFile, "-q", "--disable-pip-version-check"]);
  if (!res.ok) {
    onProgress({ step: "deps", label: "Dependency install failed — check network", status: "error" });
    return { ok: false, error: res.stderr };
  }
  onProgress({ step: "deps", label: "Python dependencies ready", status: "done" });
  return { ok: true };
}

async function stepEnsureEnv(onProgress) {
  const envPath = path.join(repoRoot, ".env");
  if (fs.existsSync(envPath)) {
    onProgress({ step: "env", label: "Configuration ready", status: "done" });
    return { ok: true };
  }
  onProgress({ step: "env", label: "Creating configuration…", status: "running" });
  const examplePath = path.join(repoRoot, ".env.example");
  if (!fs.existsSync(examplePath)) {
    onProgress({ step: "env", label: ".env.example not found — skipped", status: "skipped" });
    return { ok: true };
  }
  let content = fs.readFileSync(examplePath, "utf8");
  content = content
    .replace(/CHANGEME_postgres_password/g, randomToken(16))
    .replace(/CHANGEME_redis_password/g, randomToken(16))
    .replace(/CHANGEME_minio_access_key/g, "nirdesktop")
    .replace(/CHANGEME_minio_secret_key/g, randomToken(16))
    .replace(/CHANGEME_secret_key_at_least_32_characters_long/g, randomToken(32));
  try {
    fs.writeFileSync(envPath, content, "utf8");
  } catch (e) {
    onProgress({ step: "env", label: "Failed to write .env", status: "error" });
    return { ok: false, error: e.message };
  }
  onProgress({ step: "env", label: "Configuration created", status: "done" });
  return { ok: true };
}

async function stepStartInfrastructure(onProgress) {
  onProgress({ step: "infra", label: "Starting PostgreSQL, Redis, MinIO…", status: "running" });
  const composeFile = path.join(repoRoot, "docker-compose.infra.yml");
  if (!fs.existsSync(composeFile)) {
    onProgress({ step: "infra", label: "docker-compose.infra.yml not found — skipped", status: "skipped" });
    return { ok: true };
  }
  const res = await runAsync("docker", ["compose", "-f", composeFile, "up", "-d", "--remove-orphans"]);
  if (!res.ok) {
    const errLower = (res.stderr + res.stdout).toLowerCase();
    if (errLower.includes("cannot connect") || errLower.includes("daemon") || errLower.includes("not running") || errLower.includes("is the docker daemon")) {
      onProgress({ step: "infra", label: "Docker Desktop not running — please start it and relaunch", status: "error" });
      return { ok: false, error: "Docker Desktop is not running. Start Docker Desktop and relaunch the app." };
    }
    onProgress({ step: "infra", label: "Infrastructure failed to start", status: "error" });
    return { ok: false, error: res.stderr };
  }
  onProgress({ step: "infra", label: "Waiting for services to be ready…", status: "running" });
  const healthy = await waitForPort(5432, 30000);
  if (!healthy) {
    onProgress({ step: "infra", label: "PostgreSQL did not become ready in time", status: "error" });
    return { ok: false, error: "Infrastructure services did not become ready." };
  }
  await waitForMs(1000);
  onProgress({ step: "infra", label: "Infrastructure ready", status: "done" });
  return { ok: true };
}

async function stepRunMigrations(onProgress) {
  onProgress({ step: "migrations", label: "Applying database migrations…", status: "running" });
  const venvPy = venvPythonPath();
  if (!fs.existsSync(venvPy)) {
    onProgress({ step: "migrations", label: "Migrations skipped — no venv", status: "skipped" });
    return { ok: true };
  }
  const res = await runAsync(venvPy, ["-m", "alembic", "upgrade", "head"]);
  if (!res.ok) {
    onProgress({ step: "migrations", label: "Migration warning (non-fatal) — continuing", status: "skipped" });
    return { ok: true };
  }
  onProgress({ step: "migrations", label: "Database ready", status: "done" });
  return { ok: true };
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

async function runSetup(onProgress) {
  const progress = onProgress || (() => {});

  const pyRes = await stepCheckPython(progress);
  if (!pyRes.ok) return pyRes;

  const venvRes = await stepCreateVenv(pyRes.pythonCmd, progress);
  if (!venvRes.ok) return venvRes;

  // Point backendManager at the venv Python from here on
  process.env.NIR_DESKTOP_PYTHON = venvPythonPath();

  const depsRes = await stepInstallDeps(progress);
  if (!depsRes.ok) return depsRes;

  const envRes = await stepEnsureEnv(progress);
  if (!envRes.ok) return envRes;

  const infraRes = await stepStartInfrastructure(progress);
  if (!infraRes.ok) return infraRes;

  await stepRunMigrations(progress);

  return { ok: true };
}

module.exports = { runSetup, venvPythonPath, venvExists };
