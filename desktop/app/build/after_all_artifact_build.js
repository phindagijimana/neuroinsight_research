/**
 * electron-builder afterAllArtifactBuild hook — write SHA256SUMS.txt next to the
 * installers on EVERY build (local and CI).
 *
 * While the app is unsigned, checksums are the interim integrity mechanism:
 * users (and the bundled install helpers) can verify a download before running
 * it. The file uses the standard `sha256sum` line format ("<hash>  <name>").
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const INSTALLER_EXT = new Set([".dmg", ".pkg", ".exe", ".msi", ".appimage", ".deb", ".zip"]);

function sha256File(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    const stream = fs.createReadStream(filePath);
    stream.on("error", reject);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("end", () => resolve(hash.digest("hex")));
  });
}

exports.default = async function afterAllArtifactBuild(context) {
  const outDir = context.outDir;
  const artifacts = (context.artifactPaths || []).filter((p) =>
    INSTALLER_EXT.has(path.extname(p).toLowerCase())
  );
  if (!artifacts.length) return [];

  const lines = [];
  for (const p of artifacts) {
    /* eslint-disable no-await-in-loop */
    lines.push(`${await sha256File(p)}  ${path.basename(p)}`);
    /* eslint-enable no-await-in-loop */
  }
  lines.sort();

  const out = path.join(outDir, "SHA256SUMS.txt");
  fs.writeFileSync(out, lines.join("\n") + "\n");
  console.log(`[checksums] wrote ${out} (${lines.length} artifact(s))`);
  // Returning the path tells electron-builder to publish it alongside the apps.
  return [out];
};
