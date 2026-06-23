#!/usr/bin/env node
"use strict";

/**
 * release_metadata.js — generate release metadata + SHA256 checksums for the
 * desktop installer artifacts produced by electron-builder.
 *
 * Usage:
 *   node release_metadata.js [distDir] [outDir]
 *
 * Writes, into outDir (defaults to distDir):
 *   - desktop-release-metadata.json              (generic — all artifacts)
 *   - desktop-release-sha256.txt                 (generic — sha256sum format)
 *   - desktop-release-metadata-<platform>.json   (per detected platform)
 *   - desktop-release-sha256-<platform>.txt      (per detected platform)
 *
 * The checksum files use the `sha256sum` line format ("<hash>  <file>") and the
 * platform scoping matches desktop/ops/verify_release_*.js.
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const PLATFORM_EXTENSIONS = {
  linux: [".AppImage", ".deb"],
  windows: [".exe", ".msi"],
  macos: [".dmg", ".pkg", ".zip"],
};

function sha256(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function listFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isFile())
    .map((e) => e.name);
}

function platformOf(fileName) {
  for (const [platform, exts] of Object.entries(PLATFORM_EXTENSIONS)) {
    if (exts.some((ext) => fileName.endsWith(ext))) return platform;
  }
  return null;
}

function readAppVersion(repoRoot) {
  try {
    const pkg = JSON.parse(
      fs.readFileSync(path.join(repoRoot, "desktop", "app", "package.json"), "utf8")
    );
    return { version: pkg.version || "0.0.0", productName: (pkg.build && pkg.build.productName) || pkg.name };
  } catch (_e) {
    return { version: "0.0.0", productName: "nir-desktop-app" };
  }
}

function checksumLines(distDir, fileNames) {
  return fileNames.map((name) => `${sha256(path.join(distDir, name))}  ${name}`).join("\n") + "\n";
}

function artifactRecords(distDir, fileNames) {
  return fileNames.map((name) => {
    const full = path.join(distDir, name);
    return {
      name,
      platform: platformOf(name),
      size_bytes: fs.statSync(full).size,
      sha256: sha256(full),
    };
  });
}

function main() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  const distDir = process.argv[2] ? path.resolve(process.argv[2]) : path.join(repoRoot, "desktop", "dist");
  const outDir = process.argv[3] ? path.resolve(process.argv[3]) : distDir;

  if (!fs.existsSync(distDir)) {
    throw new Error(`dist directory not found: ${distDir}`);
  }
  fs.mkdirSync(outDir, { recursive: true });

  const { version, productName } = readAppVersion(repoRoot);
  const all = listFiles(distDir);
  const installers = all.filter((f) => platformOf(f) !== null);
  if (!installers.length) {
    throw new Error(`No installer artifacts (.AppImage/.deb/.dmg/.pkg/.zip/.exe/.msi) found in ${distDir}`);
  }

  // Generated timestamp is taken from the environment so the script stays
  // deterministic for callers that want to pin it; default to file mtime newest.
  const generatedAt =
    process.env.NIR_RELEASE_TIMESTAMP ||
    new Date(
      Math.max(...installers.map((f) => fs.statSync(path.join(distDir, f)).mtimeMs))
    ).toISOString();

  // --- generic (all platforms) ---
  const genericMeta = {
    product: productName,
    version,
    generatedAt,
    platforms: [...new Set(installers.map(platformOf))],
    artifacts: artifactRecords(distDir, installers),
  };
  fs.writeFileSync(
    path.join(outDir, "desktop-release-metadata.json"),
    JSON.stringify(genericMeta, null, 2)
  );
  fs.writeFileSync(path.join(outDir, "desktop-release-sha256.txt"), checksumLines(distDir, installers));

  // --- per platform ---
  const byPlatform = {};
  for (const name of installers) {
    const p = platformOf(name);
    (byPlatform[p] = byPlatform[p] || []).push(name);
  }
  for (const [platform, names] of Object.entries(byPlatform)) {
    const meta = {
      product: productName,
      version,
      generatedAt,
      platform,
      artifacts: artifactRecords(distDir, names),
    };
    fs.writeFileSync(
      path.join(outDir, `desktop-release-metadata-${platform}.json`),
      JSON.stringify(meta, null, 2)
    );
    fs.writeFileSync(
      path.join(outDir, `desktop-release-sha256-${platform}.txt`),
      checksumLines(distDir, names)
    );
  }

  process.stdout.write(
    `Release metadata written to ${outDir}\n` +
      `- product: ${productName} v${version}\n` +
      `- installers: ${installers.length} (${Object.keys(byPlatform).join(", ")})\n` +
      installers.map((n) => `    ${n}`).join("\n") +
      "\n"
  );
}

if (require.main === module) {
  main();
}

module.exports = { main, sha256, platformOf };
