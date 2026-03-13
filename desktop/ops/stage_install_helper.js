#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function copy(src, dst) {
  fs.copyFileSync(src, dst);
}

function makeExecutable(p) {
  try {
    fs.chmodSync(p, 0o755);
  } catch (_e) {
    // Best effort for non-POSIX filesystems.
  }
}

function main() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  const distDir = process.argv[2]
    ? path.resolve(process.argv[2])
    : path.join(repoRoot, "desktop", "dist");
  const platform = (process.argv[3] || "").trim().toLowerCase();
  if (!platform) {
    throw new Error("Platform argument is required (linux|windows|macos).");
  }

  fs.mkdirSync(distDir, { recursive: true });
  const helperDir = path.join(repoRoot, "desktop", "ops", "install_helpers");

  if (platform === "linux") {
    const src = path.join(helperDir, "install-nir-linux.sh");
    const dst = path.join(distDir, "install-nir-linux.sh");
    copy(src, dst);
    makeExecutable(dst);
    process.stdout.write(`Staged ${dst}\n`);
    return;
  }

  if (platform === "macos") {
    const src = path.join(helperDir, "install-nir-macos.sh");
    const dst = path.join(distDir, "install-nir-macos.sh");
    copy(src, dst);
    makeExecutable(dst);
    process.stdout.write(`Staged ${dst}\n`);
    return;
  }

  if (platform === "windows") {
    const srcPs1 = path.join(helperDir, "install-nir-windows.ps1");
    const srcCmd = path.join(helperDir, "install-nir-windows.cmd");
    const dstPs1 = path.join(distDir, "install-nir-windows.ps1");
    const dstCmd = path.join(distDir, "install-nir-windows.cmd");
    copy(srcPs1, dstPs1);
    copy(srcCmd, dstCmd);
    process.stdout.write(`Staged ${dstPs1}\nStaged ${dstCmd}\n`);
    return;
  }

  throw new Error(`Unsupported platform '${platform}'.`);
}

if (require.main === module) {
  main();
}

