/**
 * NIR Desktop — Electron UI end-to-end tests (Playwright).
 *
 * Drives the REAL renderer (clicks actual buttons, asserts the DOM), replacing
 * the manual click-through of the control center.
 *
 * - The "control center" suite needs no backend and runs anywhere (incl. CI).
 * - The "backend lifecycle" suite starts the real backend and opens the NIR UI;
 *   it requires the repo venv, so it is gated on NIR_E2E_BACKEND=1.
 */
const path = require("path");
const os = require("os");
const fs = require("fs");
const { test, expect, _electron: electron } = require("@playwright/test");

const APP_DIR = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(APP_DIR, "..", "..");

let app;
let page;
let userDataDir;

test.beforeAll(async () => {
  // Clean env: the sandbox may set ELECTRON_RUN_AS_NODE=1, which turns Electron
  // into plain Node and breaks the GUI launch.
  const env = { ...process.env };
  delete env.ELECTRON_RUN_AS_NODE;
  env.NIR_REPO_DIR = REPO_ROOT;

  // Isolate app state per run.
  userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "nir-ui-"));

  app = await electron.launch({
    args: [APP_DIR, `--user-data-dir=${userDataDir}`],
    cwd: APP_DIR,
    env,
  });
  page = await app.firstWindow();
  await page.waitForLoadState("domcontentloaded");
});

test.afterAll(async () => {
  if (app) await app.close();
});

test.describe("control center", () => {
  test("loads the control center shell", async () => {
    await expect(page.locator("h1")).toContainText("NeuroInsight Research");
    await expect(page.locator("#startupBanner")).toBeVisible();
  });

  test("preflight runs and populates checks + banner", async () => {
    await page.locator("#btnPreflight").click();
    await expect(page.locator("#preflightList li")).not.toHaveCount(0);
    // banner leaves the muted "running checks" state
    await expect(page.locator("#startupBanner")).not.toHaveClass(/banner-muted/);
  });

  test("credential vault: set, retrieve, delete (namespaced)", async () => {
    await page.locator("#credKey").fill("pennsieve.api_key");
    await page.locator("#credValue").fill("ui-test-secret-123");
    await page.locator("#btnCredSet").click();
    await expect(page.locator("#credsDetail")).toContainText("Saved");

    await page.locator("#btnCredGet").click();
    await expect(page.locator("#credsDetail")).toContainText("is set");

    await page.locator("#btnCredDelete").click();
    await expect(page.locator("#credsDetail")).toContainText("Deleted");
  });

  test("credential vault rejects a non-namespaced key", async () => {
    await page.locator("#credKey").fill("badkey");
    await page.locator("#credValue").fill("x");
    await page.locator("#btnCredSet").click();
    await expect(page.locator("#credsDetail")).toContainText("namespaced");
  });

  test("app lock: enable, lock, reject wrong PIN, unlock", async () => {
    await page.locator("#pinInput").fill("pilot-pin-123");
    await page.locator("#btnLockEnable").click();
    await expect(page.locator("#lockDetail")).toContainText("Enabled");

    await page.locator("#btnLockNow").click();
    await expect(page.locator("#lockDetail")).toContainText("LOCKED");

    await page.locator("#pinInput").fill("wrong");
    await page.locator("#btnLockUnlock").click();
    await expect(page.locator("#lockDetail")).toContainText("LOCKED");

    await page.locator("#pinInput").fill("pilot-pin-123");
    await page.locator("#btnLockUnlock").click();
    await expect(page.locator("#lockDetail")).toContainText("unlocked");

    await page.locator("#pinInput").fill("pilot-pin-123");
    await page.locator("#btnLockDisable").click();
  });

  test("diagnostics bundle export", async () => {
    await page.locator("#btnDiagnostics").click();
    await expect(page.locator("#diagnosticsDetail")).toContainText("Saved:");
    await expect(page.locator("#btnRevealBundle")).toBeEnabled();
  });
});

test.describe("backend lifecycle", () => {
  test.skip(process.env.NIR_E2E_BACKEND !== "1", "set NIR_E2E_BACKEND=1 (needs repo venv) to run");

  test("start backend, become healthy, open the NIR UI", async () => {
    await page.locator("#btnStart").click();
    // Backend boot + health poll can take a while.
    await expect(page.locator("#backendStatus")).toContainText("Running (healthy)", { timeout: 90_000 });
    await expect(page.locator("#btnOpenUI")).toBeEnabled();

    await page.locator("#btnOpenUI").click();
    // The same window navigates to the live NIR SPA on the backend port.
    await page.waitForURL(/127\.0\.0\.1:\d+|localhost:\d+/, { timeout: 30_000 });
    expect(page.url()).toMatch(/:\d+\/?$/);
  });
});
