/**
 * electron-builder afterSign hook — macOS notarization.
 *
 * Runs ONLY on macOS and ONLY when Apple credentials are present in the
 * environment. Without credentials (local/unsigned/internal builds) it is a
 * no-op so the unsigned fallback path keeps working.
 *
 * Required env for the signed path (set as CI secrets, see SIGNING_AND_TRUST.md):
 *   APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, APPLE_TEAM_ID
 *
 * Uses the system `xcrun notarytool`/`stapler` (no extra npm dependency):
 *   1. zip the signed .app
 *   2. notarytool submit --wait
 *   3. stapler staple the .app  (electron-builder then packages it into the dmg)
 */
const fs = require("fs");
const path = require("path");
const os = require("os");
const { execFileSync } = require("child_process");

exports.default = async function notarize(context) {
  const { electronPlatformName, appOutDir, packager } = context;
  if (electronPlatformName !== "darwin") return;

  const appleId = process.env.APPLE_ID;
  const applePassword = process.env.APPLE_APP_SPECIFIC_PASSWORD;
  const teamId = process.env.APPLE_TEAM_ID;
  if (!appleId || !applePassword || !teamId) {
    console.log("[notarize] Apple credentials not set — skipping notarization (unsigned/internal build).");
    return;
  }

  const appName = packager.appInfo.productFilename;
  const appPath = path.join(appOutDir, `${appName}.app`);
  if (!fs.existsSync(appPath)) {
    console.log(`[notarize] App not found at ${appPath} — skipping.`);
    return;
  }

  const zipPath = path.join(os.tmpdir(), `${appName}-notarize.zip`);
  console.log(`[notarize] Zipping ${appPath}`);
  execFileSync("ditto", ["-c", "-k", "--keepParent", appPath, zipPath], { stdio: "inherit" });

  try {
    console.log("[notarize] Submitting to Apple notary service (notarytool --wait)…");
    execFileSync(
      "xcrun",
      [
        "notarytool",
        "submit",
        zipPath,
        "--apple-id",
        appleId,
        "--password",
        applePassword,
        "--team-id",
        teamId,
        "--wait",
      ],
      { stdio: "inherit" }
    );
    console.log("[notarize] Stapling ticket to the app…");
    execFileSync("xcrun", ["stapler", "staple", appPath], { stdio: "inherit" });
    console.log("[notarize] Notarization complete.");
  } finally {
    try {
      fs.unlinkSync(zipPath);
    } catch (_e) {
      // best effort
    }
  }
};
