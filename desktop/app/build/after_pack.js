/**
 * electron-builder afterPack hook — bake an integrity manifest INTO the app.
 *
 * Runs after the app directory (including app.asar) is laid out and before
 * code signing, so the manifest is sealed by the signature once signing exists.
 * Writes app-integrity.json next to app.asar with the asar's SHA-256; the main
 * process re-checks it at startup (see verifyIntegrity in src/main.js) and warns
 * if the app's code has been modified or corrupted — useful while unsigned.
 *
 * The manifest lives OUTSIDE app.asar (so the asar can be hashed independently),
 * which is why this isn't circular.
 */
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function sha256File(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    const stream = fs.createReadStream(filePath);
    stream.on("error", reject);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("end", () => resolve(hash.digest("hex")));
  });
}

exports.default = async function afterPack(context) {
  const { appOutDir, packager, electronPlatformName } = context;
  const product = packager.appInfo.productFilename;
  const resourcesDir =
    electronPlatformName === "darwin"
      ? path.join(appOutDir, `${product}.app`, "Contents", "Resources")
      : path.join(appOutDir, "resources");

  const asar = path.join(resourcesDir, "app.asar");
  if (!fs.existsSync(asar)) {
    console.log("[integrity] app.asar not found (asar disabled?) — skipping manifest");
    return;
  }

  const manifest = {
    algorithm: "sha256",
    version: packager.appInfo.version,
    files: { "app.asar": await sha256File(asar) },
  };
  fs.writeFileSync(path.join(resourcesDir, "app-integrity.json"), JSON.stringify(manifest, null, 2) + "\n");
  console.log("[integrity] wrote app-integrity.json (app.asar sha256)");
};
