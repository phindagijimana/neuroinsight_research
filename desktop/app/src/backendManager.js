const { spawn } = require("child_process");
const http = require("http");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..", "..");
const researchScript = path.join(repoRoot, "research");
const candidatePorts = [3000, 3001];

function runResearchCommand(args, timeoutMs = 180000) {
  return new Promise((resolve) => {
    const child = spawn("bash", ["-lc", `"${researchScript}" ${args.join(" ")}`], {
      cwd: repoRoot,
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

async function getStatus() {
  const port = await detectRunningPort();
  return {
    running: port !== null,
    port,
  };
}

async function startBackend() {
  const result = await runResearchCommand(["start"]);
  const port = await detectRunningPort();
  return {
    ...result,
    running: port !== null,
    port,
  };
}

async function stopBackendAppOnly() {
  const result = await runResearchCommand(["stop", "app"]);
  const port = await detectRunningPort();
  return {
    ...result,
    running: port !== null,
    port,
  };
}

async function stopBackendAll() {
  const result = await runResearchCommand(["stop"]);
  const port = await detectRunningPort();
  return {
    ...result,
    running: port !== null,
    port,
  };
}

module.exports = {
  repoRoot,
  getStatus,
  startBackend,
  stopBackendAppOnly,
  stopBackendAll,
};
