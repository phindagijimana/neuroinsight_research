/**
 * electron-builder afterSign hook — notarize + staple the macOS .app.
 *
 * Runs ONLY on macOS and ONLY when Apple credentials are present in the
 * environment (APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, APPLE_TEAM_ID). Without
 * them it is a no-op so the unsigned fallback path keeps working.
 *
 * Stapling the .app here makes the app trusted offline once it is extracted —
 * it travels inside the auto-update .zip. The final .dmg is notarized + stapled
 * separately in the afterAllArtifactBuild hook (the .dmg is a distinct artifact
 * with its own ticket). Both share build/notarize_util.js.
 */
const fs = require("fs");
const path = require("path");
const { notarizeAndStaple } = require("./notarize_util");

exports.default = async function notarize(context) {
  const { electronPlatformName, appOutDir, packager } = context;
  if (electronPlatformName !== "darwin") return;

  const appName = packager.appInfo.productFilename;
  const appPath = path.join(appOutDir, `${appName}.app`);
  if (!fs.existsSync(appPath)) {
    console.log(`[notarize] App not found at ${appPath} — skipping.`);
    return;
  }

  await notarizeAndStaple(appPath, `${appName}.app`);
};
