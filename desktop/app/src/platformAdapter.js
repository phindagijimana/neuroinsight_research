const { spawnSync } = require("child_process");

function isWindows() {
  return process.platform === "win32";
}

function getShellSpawnSpec(command) {
  if (isWindows()) {
    return {
      command: "cmd.exe",
      args: ["/d", "/s", "/c", command],
    };
  }
  return {
    command: "bash",
    args: ["-lc", command],
  };
}

function commandWorks(cmd, args) {
  try {
    const res = spawnSync(cmd, args, {
      encoding: "utf8",
      timeout: 6000,
    });
    if (res.error) return false;
    return res.status === 0;
  } catch (_e) {
    return false;
  }
}

function resolvePythonCommand() {
  const preferred = process.env.NIR_DESKTOP_PYTHON;
  if (preferred && commandWorks(preferred, ["--version"])) {
    return preferred;
  }
  if (!isWindows()) {
    if (commandWorks("python3", ["--version"])) return "python3";
    if (commandWorks("python", ["--version"])) return "python";
    return null;
  }
  if (commandWorks("py", ["-3", "--version"])) return "py -3";
  if (commandWorks("python", ["--version"])) return "python";
  return null;
}

function resolveNpmCommand() {
  return isWindows() ? "npm.cmd" : "npm";
}

function getPlatformSummary() {
  return {
    os: process.platform,
    arch: process.arch,
    windows: isWindows(),
  };
}

module.exports = {
  getShellSpawnSpec,
  resolvePythonCommand,
  resolveNpmCommand,
  getPlatformSummary,
};
