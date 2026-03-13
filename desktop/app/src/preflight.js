const fs = require("fs");
const os = require("os");
const { spawnSync } = require("child_process");
const net = require("net");
const platformAdapter = require("./platformAdapter");

function cmdExists(cmd, args = ["--version"]) {
  try {
    const res = spawnSync(cmd, args, { encoding: "utf8", timeout: 5000 });
    return {
      found: !res.error,
      code: typeof res.status === "number" ? res.status : -1,
      stdout: (res.stdout || "").trim(),
      stderr: (res.stderr || "").trim(),
    };
  } catch (e) {
    return { found: false, code: -1, stdout: "", stderr: String(e) };
  }
}

function checkPortOpen(port) {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    let settled = false;

    const done = (open) => {
      if (settled) return;
      settled = true;
      try {
        socket.destroy();
      } catch (_e) {
        // no-op
      }
      resolve(open);
    };

    socket.setTimeout(1000);
    socket.once("connect", () => done(true));
    socket.once("timeout", () => done(false));
    socket.once("error", () => done(false));
    socket.connect(port, "127.0.0.1");
  });
}

function getDiskFreeGB() {
  // Conservative fallback for Linux/macOS style fs stats.
  const dataDir = os.homedir();
  try {
    const st = fs.statfsSync(dataDir);
    const free = (st.bsize * st.bavail) / (1024 ** 3);
    const total = (st.bsize * st.blocks) / (1024 ** 3);
    return {
      ok: true,
      freeGB: Number(free.toFixed(2)),
      totalGB: Number(total.toFixed(2)),
      dataDir,
    };
  } catch (e) {
    return { ok: false, error: String(e), dataDir };
  }
}

function checkPythonRuntime() {
  const pythonCmd = platformAdapter.resolvePythonCommand();
  if (!pythonCmd) {
    return {
      ok: false,
      command: null,
      detail: "Python runtime not found (set NIR_DESKTOP_PYTHON or install python3).",
    };
  }
  const parts = pythonCmd.split(/\s+/);
  const cmd = parts[0];
  const args = [...parts.slice(1), "--version"];
  const res = cmdExists(cmd, args);
  return {
    ok: res.found && res.code === 0,
    command: pythonCmd,
    detail: (res.stdout || res.stderr || "").trim(),
  };
}

function checkCeleryImport(pythonCmd) {
  if (!pythonCmd) {
    return { ok: false, detail: "Python runtime not available." };
  }
  const parts = pythonCmd.split(/\s+/);
  const cmd = parts[0];
  const args = [...parts.slice(1), "-c", "import celery; print(celery.__version__)"];
  const res = cmdExists(cmd, args);
  return {
    ok: res.found && res.code === 0,
    detail: res.stdout || res.stderr || "Celery import check failed",
  };
}

function checkKeychainAvailability() {
  if (process.platform === "darwin") {
    const r = cmdExists("security", ["-h"]);
    return { available: r.found, backend: "macOS Keychain", detail: r.stderr || r.stdout };
  }
  if (process.platform === "win32") {
    const r = cmdExists("cmdkey", ["/?"]);
    return { available: r.found, backend: "Windows Credential Manager", detail: r.stderr || r.stdout };
  }
  // Linux
  const secretTool = cmdExists("secret-tool", ["--help"]);
  if (secretTool.found) {
    return { available: true, backend: "Secret Service (secret-tool)", detail: "" };
  }
  const kwallet = cmdExists("kwallet-query", ["--help"]);
  if (kwallet.found) {
    return { available: true, backend: "KWallet", detail: "" };
  }
  return {
    available: false,
    backend: "Linux keyring",
    detail: "secret-tool/KWallet not detected; keychain integration may be limited",
  };
}

async function runPreflight() {
  const docker = cmdExists("docker", ["--version"]);
  const node = cmdExists("node", ["--version"]);
  const npm = cmdExists("npm", ["--version"]);
  const python = checkPythonRuntime();
  const celery = checkCeleryImport(python.command);
  const keychain = checkKeychainAvailability();
  const disk = getDiskFreeGB();
  const port3000 = await checkPortOpen(3000);
  const port3001 = await checkPortOpen(3001);

  const checks = {
    platform: {
      os: process.platform,
      arch: process.arch,
      release: os.release(),
      hostname: os.hostname(),
    },
    docker: {
      ok: docker.found,
      detail: docker.stdout || docker.stderr || "docker not found",
    },
    node: {
      ok: node.found,
      detail: node.stdout || node.stderr || "node not found",
    },
    npm: {
      ok: npm.found,
      detail: npm.stdout || npm.stderr || "npm not found",
    },
    python: {
      ok: python.ok,
      command: python.command,
      detail: python.detail,
    },
    celery: {
      ok: celery.ok,
      detail: celery.detail,
    },
    keychain: {
      ok: keychain.available,
      backend: keychain.backend,
      detail: keychain.detail || "",
    },
    disk,
    ports: {
      p3000_open: port3000,
      p3001_open: port3001,
    },
  };

  const warnings = [];
  if (!checks.docker.ok) warnings.push("Docker not detected.");
  if (!checks.python.ok) warnings.push("Python runtime not detected.");
  if (!checks.celery.ok) warnings.push("Celery Python package import failed.");
  if (!checks.keychain.ok) warnings.push("OS keychain backend not detected.");
  if (checks.disk.ok && checks.disk.freeGB < 20) warnings.push("Low free disk space (<20GB).");
  if (checks.ports.p3000_open && checks.ports.p3001_open) {
    warnings.push("Both desktop candidate ports (3000 and 3001) are already in use.");
  }

  return {
    ok: warnings.length === 0,
    warnings,
    checks,
    generatedAt: new Date().toISOString(),
  };
}

module.exports = {
  runPreflight,
};
