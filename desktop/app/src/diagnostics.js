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

async function exportDiagnosticsBundle() {
  const paths = desktopState.getPaths();
  const status = await backendManager.getStatus();
  const checks = await preflight.runPreflight();
  const settings = desktopState.readSettings();
  const desktopLog = safeRead(paths.logFile);

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
      preflight: checks,
      paths,
    },
    logs: {
      desktopLog: desktopLog ? desktopLog.split("\n").slice(-200).join("\n") : null,
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
