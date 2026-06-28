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
 * Uses the system `xcrun notarytool`/`stapler` (no extra npm dependency).
 *
 * Resilience: Apple's notary service can stay "In Progress" for a long time,
 * and GitHub macOS runners intermittently drop their connection to
 * appstoreconnect.apple.com (NSURLErrorDomain Code=-1009). A single failed poll
 * must NOT discard the whole submission. So instead of `submit --wait`, we:
 *   1. zip the signed .app
 *   2. `submit --no-wait` ONCE to upload and get a submission id
 *   3. poll `info <id>` on an interval, retrying transient network errors,
 *      until the status is terminal or we hit an overall timeout
 *   4. on Invalid/Rejected, fetch `log <id>` for diagnostics and fail
 *   5. `stapler staple` the .app (electron-builder then packages it into the dmg)
 *
 * Secrets are passed as CLI args; GitHub Actions masks registered secrets in
 * logs (they appear as ***), so error text remains safe to print.
 */
const fs = require("fs");
const path = require("path");
const os = require("os");
const { execFileSync } = require("child_process");

const POLL_INTERVAL_MS = 30_000; // seconds between status checks
const OVERALL_TIMEOUT_MS = 90 * 60_000; // give Apple up to 90 min to finish
const SUBMIT_RETRIES = 3; // re-upload attempts if the upload itself drops

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function isTransientNetworkError(message) {
  return (
    /-1009/.test(message) ||
    /connection appears to be offline/i.test(message) ||
    /could not connect|network (?:is )?(?:down|unreachable|route)|timed out|timeout|temporarily/i.test(
      message
    )
  );
}

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

  const cred = [
    "--apple-id",
    appleId,
    "--password",
    applePassword,
    "--team-id",
    teamId,
  ];
  // Capture stdout as a string; surface stderr through the thrown error.
  const notarytool = (args) =>
    execFileSync("xcrun", ["notarytool", ...args], { encoding: "utf8" });

  const zipPath = path.join(os.tmpdir(), `${appName}-notarize.zip`);
  console.log(`[notarize] Zipping ${appPath}`);
  execFileSync("ditto", ["-c", "-k", "--keepParent", appPath, zipPath], { stdio: "inherit" });

  try {
    // 1. Upload once (retry only if the upload itself fails on a transient error).
    let submissionId;
    for (let attempt = 1; attempt <= SUBMIT_RETRIES; attempt++) {
      try {
        console.log(`[notarize] Uploading to Apple notary service (attempt ${attempt}/${SUBMIT_RETRIES})…`);
        const out = notarytool([
          "submit",
          zipPath,
          ...cred,
          "--no-wait",
          "--output-format",
          "json",
        ]);
        submissionId = JSON.parse(out).id;
        console.log(`[notarize] Submission id: ${submissionId}`);
        break;
      } catch (e) {
        const msg = (e.stderr || e.message || "").toString().split("\n")[0];
        if (attempt < SUBMIT_RETRIES && isTransientNetworkError(msg)) {
          console.log(`[notarize] Upload hit a transient error, retrying: ${msg}`);
          await sleep(POLL_INTERVAL_MS);
          continue;
        }
        throw e;
      }
    }
    if (!submissionId) throw new Error("[notarize] Failed to obtain a submission id.");

    // 2. Poll for a terminal status, tolerating dropped polls.
    const deadline = Date.now() + OVERALL_TIMEOUT_MS;
    let status = "In Progress";
    while (Date.now() < deadline) {
      await sleep(POLL_INTERVAL_MS);
      let info;
      try {
        info = notarytool(["info", submissionId, ...cred, "--output-format", "json"]);
      } catch (e) {
        const msg = (e.stderr || e.message || "").toString().split("\n")[0];
        if (isTransientNetworkError(msg)) {
          console.log(`[notarize] Poll hit a transient error, will retry: ${msg}`);
          continue; // keep the submission; just try the next poll
        }
        throw e;
      }
      try {
        status = JSON.parse(info).status;
      } catch (_e) {
        console.log("[notarize] Could not parse status JSON, will retry next poll.");
        continue;
      }
      console.log(`[notarize] Status: ${status}`);
      if (status === "Accepted") break;
      if (status === "Invalid" || status === "Rejected") {
        try {
          const log = notarytool(["log", submissionId, ...cred]);
          console.log("[notarize] Notary log:\n" + log);
        } catch (_e) {
          /* best effort */
        }
        throw new Error(`[notarize] Notarization failed with status: ${status}`);
      }
      // otherwise still "In Progress" — keep polling
    }
    if (status !== "Accepted") {
      throw new Error(
        `[notarize] Timed out after ${Math.round(OVERALL_TIMEOUT_MS / 60000)} min (last status: ${status}).`
      );
    }

    // 3. Staple the ticket (small retry for transient download hiccups).
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        console.log("[notarize] Stapling ticket to the app…");
        execFileSync("xcrun", ["stapler", "staple", appPath], { stdio: "inherit" });
        break;
      } catch (e) {
        if (attempt < 3) {
          console.log(`[notarize] Staple attempt ${attempt} failed, retrying…`);
          await sleep(10_000);
          continue;
        }
        throw e;
      }
    }
    console.log("[notarize] Notarization complete.");
  } finally {
    try {
      fs.unlinkSync(zipPath);
    } catch (_e) {
      // best effort
    }
  }
};
