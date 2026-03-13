#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function sha256(filePath) {
  const data = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(data).digest("hex");
}

function isReleaseArtifact(name) {
  return (
    name.endsWith(".AppImage") ||
    name.endsWith(".deb") ||
    name.endsWith(".exe") ||
    name.endsWith(".msi") ||
    name.endsWith(".dmg") ||
    name.endsWith(".pkg") ||
    name.endsWith(".zip") ||
    name.endsWith(".yml") ||
    name.endsWith(".yaml")
  );
}

function buildMetadata(distDir, outDir) {
  if (!fs.existsSync(distDir)) {
    throw new Error(`Dist directory not found: ${distDir}`);
  }
  fs.mkdirSync(outDir, { recursive: true });

  const files = fs
    .readdirSync(distDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && isReleaseArtifact(entry.name))
    .map((entry) => path.join(distDir, entry.name))
    .map((p) => {
      const stat = fs.statSync(p);
      return {
        file: path.basename(p),
        size_bytes: stat.size,
        sha256: sha256(p),
      };
    })
    .sort((a, b) => a.file.localeCompare(b.file));

  const releaseTag =
    process.env.GITHUB_REF_NAME ||
    process.env.RELEASE_TAG ||
    `local-${new Date().toISOString().slice(0, 10)}`;

  const metadata = {
    product: "NeuroInsight Research Desktop",
    channel: "stable",
    version: releaseTag,
    generated_at: new Date().toISOString(),
    artifacts: files,
  };

  const metadataPath = path.join(outDir, "desktop-release-metadata.json");
  fs.writeFileSync(metadataPath, JSON.stringify(metadata, null, 2), "utf8");

  const checksumsPath = path.join(outDir, "desktop-release-sha256.txt");
  const checksums = files
    .map((f) => `${f.sha256}  ${f.file}`)
    .join("\n");
  fs.writeFileSync(checksumsPath, `${checksums}\n`, "utf8");

  return { metadataPath, checksumsPath, artifactCount: files.length };
}

function main() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  const distDir = process.argv[2]
    ? path.resolve(process.argv[2])
    : path.join(repoRoot, "desktop", "dist");
  const outDir = process.argv[3]
    ? path.resolve(process.argv[3])
    : path.join(repoRoot, "desktop", "dist");

  const result = buildMetadata(distDir, outDir);
  process.stdout.write(
    `Generated metadata for ${result.artifactCount} artifact(s)\n` +
      `- ${result.metadataPath}\n` +
      `- ${result.checksumsPath}\n`
  );
}

if (require.main === module) {
  main();
}

