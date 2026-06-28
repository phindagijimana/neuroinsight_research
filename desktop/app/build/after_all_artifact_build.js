/**
 * electron-builder afterAllArtifactBuild hook.
 *
 *  1. On macOS, notarize + staple each final .dmg (when Apple credentials are
 *     present). The .app was already notarized/stapled in the afterSign hook,
 *     but the .dmg is a distinct artifact that needs its own ticket — Apple
 *     recommends stapling the distributed installer and verify_trust.js enforces
 *     it. Stapling changes the .dmg bytes, so this runs BEFORE checksums and
 *     best-effort-refreshes the .dmg hash in latest-mac.yml. (macOS auto-update
 *     uses the .zip, which is unaffected.)
 *  2. Write SHA256SUMS.txt next to the installers on EVERY build (local and CI)
 *     as the integrity mechanism for downloads and the bundled install helpers.
 *     The file uses the standard `sha256sum` line format ("<hash>  <name>").
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { credsPresent, notarizeAndStaple } = require("./notarize_util");

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

/**
 * Stapling a .dmg changes its bytes, so the sha512/size electron-builder wrote
 * into latest-mac.yml for that .dmg become stale. macOS auto-update downloads
 * the .zip (untouched), so this is cosmetic — but refresh it anyway when we can.
 * Fully best-effort: never throws.
 */
function refreshLatestYmlDmgHashes(outDir, dmgPaths) {
  let yaml;
  try {
    yaml = require("js-yaml");
  } catch (_e) {
    console.log("[notarize] js-yaml unavailable — skipping latest-mac.yml refresh.");
    return;
  }
  const ymlPath = path.join(outDir, "latest-mac.yml");
  if (!fs.existsSync(ymlPath)) return;
  const doc = yaml.load(fs.readFileSync(ymlPath, "utf8"));
  if (!doc || !Array.isArray(doc.files)) return;
  const byName = new Map(dmgPaths.map((p) => [path.basename(p), p]));
  let changed = false;
  for (const entry of doc.files) {
    const p = byName.get(entry.url);
    if (!p) continue;
    const buf = fs.readFileSync(p);
    entry.sha512 = crypto.createHash("sha512").update(buf).digest("base64");
    entry.size = buf.length;
    changed = true;
  }
  if (changed) {
    fs.writeFileSync(ymlPath, yaml.dump(doc, { lineWidth: -1 }));
    console.log("[notarize] Refreshed .dmg hashes in latest-mac.yml.");
  }
}

exports.default = async function afterAllArtifactBuild(context) {
  const outDir = context.outDir;
  const artifacts = (context.artifactPaths || []).filter((p) =>
    INSTALLER_EXT.has(path.extname(p).toLowerCase())
  );
  if (!artifacts.length) return [];

  // 1. Notarize + staple the macOS DMG installer(s).
  const dmgs = artifacts.filter((p) => path.extname(p).toLowerCase() === ".dmg");
  if (dmgs.length && credsPresent()) {
    for (const dmg of dmgs) {
      /* eslint-disable no-await-in-loop */
      await notarizeAndStaple(dmg, path.basename(dmg));
      /* eslint-enable no-await-in-loop */
    }
    try {
      refreshLatestYmlDmgHashes(outDir, dmgs);
    } catch (e) {
      console.log("[notarize] latest-mac.yml refresh skipped:", e.message);
    }
  }

  // 2. Write SHA256SUMS.txt (after any stapling, so hashes match the artifacts).
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
