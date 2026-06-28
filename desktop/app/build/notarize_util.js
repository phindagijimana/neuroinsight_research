/**
 * Shared macOS notarization helper for the electron-builder hooks.
 *
 * Why a shared util: BOTH the .app (afterSign) and the final .dmg
 * (afterAllArtifactBuild) must be notarized and stapled. The .app staple makes
 * the app trusted offline once extracted (it travels in the auto-update .zip);
 * the .dmg staple makes the fresh-download installer trusted, which Apple
 * recommends and which verify_trust.js enforces.
 *
 * Resilience: Apple's notary service can stay "In Progress" for 1-2h, and
 * GitHub macOS runners intermittently drop their connection to
 * appstoreconnect.apple.com (NSURLErrorDomain Code=-1009). A single failed poll
 * must NOT discard the submission. So we `submit --no-wait` once, then poll
 * `info <id>`, retrying transient network errors without re-uploading, until a
 * terminal status or an overall timeout.
 *
 * Secrets are passed as CLI args; GitHub Actions masks registered secrets in
 * logs (they appear as ***), so error text remains safe to print.
 */
const fs = require("fs");
const path = require("path");
const os = require("os");
const { execFileSync } = require("child_process");

const POLL_INTERVAL_MS = 30_000;
const OVERALL_TIMEOUT_MS = 90 * 60_000;
const SUBMIT_RETRIES = 3;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function credsPresent() {
  return Boolean(
    process.env.APPLE_ID &&
      process.env.APPLE_APP_SPECIFIC_PASSWORD &&
      process.env.APPLE_TEAM_ID
  );
}

function isTransientNetworkError(message) {
  return (
    /-1009/.test(message) ||
    /connection appears to be offline/i.test(message) ||
    /could not connect|network (?:is )?(?:down|unreachable|route)|timed out|timeout|temporarily/i.test(
      message
    )
  );
}

/**
 * Notarize `targetPath` (a .app or .dmg) and staple the ticket onto it.
 * A .app is zipped before submission (notarytool needs a zip/dmg/pkg); the
 * staple is always applied to the original targetPath.
 * @returns {Promise<boolean>} true if notarized+stapled, false if creds absent.
 */
async function notarizeAndStaple(targetPath, label = path.basename(targetPath)) {
  if (!credsPresent()) {
    console.log(`[notarize] Apple credentials not set — skipping ${label}.`);
    return false;
  }
  const cred = [
    "--apple-id",
    process.env.APPLE_ID,
    "--password",
    process.env.APPLE_APP_SPECIFIC_PASSWORD,
    "--team-id",
    process.env.APPLE_TEAM_ID,
  ];
  const notarytool = (args) =>
    execFileSync("xcrun", ["notarytool", ...args], { encoding: "utf8" });

  // notarytool cannot take a bare .app bundle — zip it first.
  let submitPath = targetPath;
  let tmpZip = null;
  if (targetPath.endsWith(".app")) {
    tmpZip = path.join(os.tmpdir(), `${path.basename(targetPath)}-notarize.zip`);
    console.log(`[notarize] Zipping ${targetPath}`);
    execFileSync("ditto", ["-c", "-k", "--keepParent", targetPath, tmpZip], { stdio: "inherit" });
    submitPath = tmpZip;
  }

  try {
    // 1. Upload once (retry only the upload on transient errors).
    let submissionId;
    for (let attempt = 1; attempt <= SUBMIT_RETRIES; attempt++) {
      try {
        console.log(`[notarize] Uploading ${label} (attempt ${attempt}/${SUBMIT_RETRIES})…`);
        const out = notarytool(["submit", submitPath, ...cred, "--no-wait", "--output-format", "json"]);
        submissionId = JSON.parse(out).id;
        console.log(`[notarize] ${label} submission id: ${submissionId}`);
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
    if (!submissionId) throw new Error(`[notarize] Failed to obtain a submission id for ${label}.`);

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
          continue;
        }
        throw e;
      }
      try {
        status = JSON.parse(info).status;
      } catch (_e) {
        console.log("[notarize] Could not parse status JSON, will retry next poll.");
        continue;
      }
      console.log(`[notarize] ${label} status: ${status}`);
      if (status === "Accepted") break;
      if (status === "Invalid" || status === "Rejected") {
        try {
          console.log("[notarize] Notary log:\n" + notarytool(["log", submissionId, ...cred]));
        } catch (_e) {
          /* best effort */
        }
        throw new Error(`[notarize] ${label} notarization failed with status: ${status}`);
      }
    }
    if (status !== "Accepted") {
      throw new Error(
        `[notarize] ${label} timed out after ${Math.round(OVERALL_TIMEOUT_MS / 60000)} min (last status: ${status}).`
      );
    }

    // 3. Staple the ticket onto the original artifact (small retry).
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        console.log(`[notarize] Stapling ticket to ${label}…`);
        execFileSync("xcrun", ["stapler", "staple", targetPath], { stdio: "inherit" });
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
    console.log(`[notarize] ${label} notarization complete.`);
    return true;
  } finally {
    if (tmpZip) {
      try {
        fs.unlinkSync(tmpZip);
      } catch (_e) {
        /* best effort */
      }
    }
  }
}

module.exports = { credsPresent, notarizeAndStaple };
