#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

function listFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isFile())
    .map((e) => e.name);
}

function expectedExtensions(platform) {
  if (platform === "linux") return [".AppImage", ".deb"];
  if (platform === "windows") return [".exe", ".msi"];
  if (platform === "macos") return [".dmg", ".pkg", ".zip"];
  return [];
}

function hasAnyInstaller(files, exts) {
  return files.some((f) => exts.some((ext) => f.endsWith(ext)));
}

function ensureExists(filePath, label) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`${label} not found: ${filePath}`);
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

  const files = listFiles(distDir);
  const exts = expectedExtensions(platform);
  if (!exts.length) {
    throw new Error(`Unsupported platform '${platform}'.`);
  }
  if (!hasAnyInstaller(files, exts)) {
    throw new Error(
      `No installer artifact found for ${platform}. Expected one of: ${exts.join(", ")}`
    );
  }

  const metadataScoped = path.join(distDir, `desktop-release-metadata-${platform}.json`);
  const checksumsScoped = path.join(distDir, `desktop-release-sha256-${platform}.txt`);
  ensureExists(metadataScoped, "Platform metadata");
  ensureExists(checksumsScoped, "Platform checksums");

  process.stdout.write(
    `Verified ${platform} release artifacts in ${distDir}\n` +
      `- ${metadataScoped}\n` +
      `- ${checksumsScoped}\n`
  );
}

if (require.main === module) {
  main();
}
