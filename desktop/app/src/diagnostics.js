const fs = require("fs");
const path = require("path");
const os = require("os");
const backendManager = require("./backendManager");
const preflight = require("./preflight");
const desktopState = require("./desktopState");

function safeRead(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    return fs.readFileSync(filePath, "utf8");
  } catch (_e) {
    return null;
  }
}

function tailLines(text, maxLines = 200) {
  if (!text) return null;
  return text.split("\n").slice(-maxLines).join("\n");
}

async function exportDiagnosticsBundle() {
  const paths = desktopState.getPaths();
  const status = await backendManager.getStatus();
  let runtime = null;
  try {
    runtime = backendManager.getRuntimeInfo();
  } catch (_e) {
    runtime = null;
  }
  const checks = await preflight.runPreflight();
  const settings = desktopState.readSettings();
  const desktopLog = safeRead(paths.logFile);
  const backendRuntimeLog = runtime ? safeRead(runtime.logFiles.backend) : null;
  const celeryRuntimeLog = runtime ? safeRead(runtime.logFiles.celery) : null;

  const payload = {
    generatedAt: new Date().toISOString(),
    machine: {
      platform: process.platform,
      arch: process.arch,
      hostname: os.hostname(),
      release: os.release(),
    },
    nirDesktop: {
      settings,
      status,
      runtime,
      preflight: checks,
      paths,
    },
    logs: {
      desktopLog: tailLines(desktopLog, 400),
      backendRuntimeLog: tailLines(backendRuntimeLog, 400),
      celeryRuntimeLog: tailLines(celeryRuntimeLog, 400),
    },
  };

  const outDir = path.join(paths.stateDir, "diagnostics");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(
    outDir,
    `nir-desktop-support-${new Date().toISOString().replace(/[:.]/g, "-")}.json`
  );
  fs.writeFileSync(outFile, JSON.stringify(payload, null, 2), "utf8");
  desktopState.appendLog("diagnostics_export", { outFile });
  return { ok: true, path: outFile };
}

module.exports = {
  exportDiagnosticsBundle,
};
