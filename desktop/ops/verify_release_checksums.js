#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function sha256(filePath) {
  const data = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(data).digest("hex");
}

function expectedExtensions(platform) {
  if (platform === "linux") return [".AppImage", ".deb"];
  if (platform === "windows") return [".exe", ".msi"];
  if (platform === "macos") return [".dmg", ".pkg", ".zip"];
  return [];
}

function listFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isFile())
    .map((e) => e.name);
}

function parseChecksumFile(filePath) {
  const text = fs.readFileSync(filePath, "utf8");
  const out = new Map();
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const parts = line.split(/\s+/);
    if (parts.length < 2) {
      throw new Error(`Invalid checksum line in ${filePath}: '${rawLine}'`);
    }
    const hash = parts[0].toLowerCase();
    const file = parts.slice(1).join(" ").replace(/^\*/, "");
    out.set(file, hash);
  }
  return out;
}

function verifyEntries(distDir, checksumEntries, label) {
  let verifiedCount = 0;
  for (const [file, expected] of checksumEntries.entries()) {
    const full = path.join(distDir, file);
    if (!fs.existsSync(full)) {
      throw new Error(`${label}: listed file not found: ${full}`);
    }
    const actual = sha256(full);
    if (actual !== expected) {
      throw new Error(
        `${label}: checksum mismatch for ${file}\nexpected=${expected}\nactual=${actual}`
      );
    }
    verifiedCount += 1;
  }
  return verifiedCount;
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

  const exts = expectedExtensions(platform);
  if (!exts.length) {
    throw new Error(`Unsupported platform '${platform}'.`);
  }

  const files = listFiles(distDir);
  const installers = files.filter((f) => exts.some((ext) => f.endsWith(ext)));
  if (!installers.length) {
    throw new Error(
      `No installer artifact found for ${platform}. Expected one of: ${exts.join(", ")}`
    );
  }

  const genericChecksum = path.join(distDir, "desktop-release-sha256.txt");
  const platformChecksum = path.join(distDir, `desktop-release-sha256-${platform}.txt`);
  if (!fs.existsSync(genericChecksum)) {
    throw new Error(`Generic checksum file not found: ${genericChecksum}`);
  }
  if (!fs.existsSync(platformChecksum)) {
    throw new Error(`Platform checksum file not found: ${platformChecksum}`);
  }

  const genericEntries = parseChecksumFile(genericChecksum);
  const platformEntries = parseChecksumFile(platformChecksum);

  for (const installer of installers) {
    if (!genericEntries.has(installer)) {
      throw new Error(`Installer ${installer} missing from desktop-release-sha256.txt`);
    }
    if (!platformEntries.has(installer)) {
      throw new Error(
        `Installer ${installer} missing from desktop-release-sha256-${platform}.txt`
      );
    }
  }

  const genericVerified = verifyEntries(distDir, genericEntries, "Generic checksums");
  const platformVerified = verifyEntries(distDir, platformEntries, "Platform checksums");

  process.stdout.write(
    `Verified checksums for ${platform} artifacts in ${distDir}\n` +
      `- installers covered: ${installers.length}\n` +
      `- generic checksum entries verified: ${genericVerified}\n` +
      `- platform checksum entries verified: ${platformVerified}\n`
  );
}

if (require.main === module) {
  main();
}

