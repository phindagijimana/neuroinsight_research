/**
 * NIR Desktop — Electron UI end-to-end tests (Playwright).
 *
 * Drives the REAL renderer (clicks actual buttons, asserts the DOM).
 *
 * - "control center" suite forces the control center (NIR_START_IN_CONTROL=1) and
 *   needs no backend — runs anywhere (incl. CI).
 * - "smooth launch" suite exercises the default flow (splash -> auto-start ->
 *   land in the NIR workspace) and is gated on NIR_E2E_BACKEND (needs the venv).
 */
const path = require("path");
const os = require("os");
const fs = require("fs");
const { test, expect, _electron: electron } = require("@playwright/test");

const APP_DIR = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(APP_DIR, "..", "..");

function baseEnv(extra) {
  const env = { ...process.env, NIR_REPO_DIR: REPO_ROOT };
  delete env.ELECTRON_RUN_AS_NODE; // sandbox sets this; it breaks the GUI launch
  return Object.assign(env, extra || {});
}

async function launch(extraEnv) {
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "nir-ui-"));
  const app = await electron.launch({
    args: [APP_DIR, `--user-data-dir=${userDataDir}`],
    cwd: APP_DIR,
    env: baseEnv(extraEnv),
  });
  return app;
}

/** Wait for the window that contains a given selector (skips the splash window). */
async function pageWithSelector(app, selector, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    for (const w of app.windows()) {
      try {
        if (await w.$(selector)) return w;
      } catch (_e) {
        // window may be navigating
      }
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`No window with selector ${selector} appeared`);
}

test.describe("control center", () => {
  let app;
  let page;

  test.beforeAll(async () => {
    app = await launch({ NIR_START_IN_CONTROL: "1" });
    page = await pageWithSelector(app, "#btnPreflight");
    // Advanced tools (credentials, app lock, diagnostics) live in a collapsed
    // <details> — expand it so those cards are interactable.
    await page
      .locator("details.advanced")
      .evaluate((d) => {
        d.open = true;
      })
      .catch(() => {});
  });
  test.afterAll(async () => {
    if (app) await app.close();
  });

  test("loads the control center shell", async () => {
    await expect(page.locator("h1")).toContainText("Settings");
    await expect(page.locator("#startupBanner")).toBeVisible();
  });

  test("preflight runs and populates checks + banner", async () => {
    await page.locator("#btnPreflight").click();
    await expect(page.locator("#preflightList li")).not.toHaveCount(0);
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

  test("manual: start backend, become healthy, open the NIR UI", async () => {
    test.skip(process.env.NIR_E2E_BACKEND !== "1", "set NIR_E2E_BACKEND=1 (needs repo venv)");
    await page.locator("#btnStart").click();
    await expect(page.locator("#backendStatus")).toContainText("Running (healthy)", { timeout: 90_000 });
    await expect(page.locator("#btnOpenUI")).toBeEnabled();
    await page.locator("#btnOpenUI").click();
    await page.waitForURL(/127\.0\.0\.1:\d+|localhost:\d+/, { timeout: 30_000 });
    // the persistent status bar is injected into the workspace
    await expect(page.locator("#nir-desktop-statusbar")).toBeVisible({ timeout: 15_000 });
  });
});

test.describe("smooth launch (default flow)", () => {
  test.skip(process.env.NIR_E2E_BACKEND !== "1", "set NIR_E2E_BACKEND=1 (needs repo venv)");
  let app;
  let page;

  test.beforeAll(async () => {
    app = await launch(); // no NIR_START_IN_CONTROL: exercise the real launch
    page = await pageWithSelector(app, "#nir-desktop-statusbar", 120_000);
  });
  test.afterAll(async () => {
    if (app) await app.close();
  });

  test("splash -> auto-start backend -> lands directly in the NIR workspace", async () => {
    await expect(page.locator("#nir-desktop-statusbar")).toBeVisible();
    await expect(page.locator("#nir-engine")).toContainText(/healthy|starting/);
    expect(page.url()).toMatch(/127\.0\.0\.1:\d+|localhost:\d+/);
  });

  test("data-first home: open a local NIfTI -> Viewer (no upload)", async () => {
    const sample = process.env.NIR_E2E_SAMPLE;
    test.skip(!sample, "set NIR_E2E_SAMPLE to a .nii.gz path");
    // The data-first actions are on the Home landing.
    await expect(page.getByText("Open Imaging File")).toBeVisible();
    await page.setInputFiles('input[type="file"][accept*=".nii"]', sample);
    // Lands in the Viewer with the local-file banner (proves the volume was wired through).
    await expect(page.getByText(/Viewing local file/i)).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(/sample\.nii\.gz/)).toBeVisible();
  });

  test("native Open Data bridge: main pushes a volume -> Viewer", async () => {
    const sample = process.env.NIR_E2E_SAMPLE;
    test.skip(!sample, "set NIR_E2E_SAMPLE to a .nii.gz path");
    // Simulate the native File > Open Data… by pushing bytes from the MAIN process
    // (the OS file dialog itself can't be automated). Exercises the full bridge:
    // main -> preload onOpenVolume -> App -> Viewer. Bytes are read here (Node)
    // since require() isn't available inside app.evaluate.
    const bytes = Array.from(fs.readFileSync(sample));
    await app.evaluate(({ BrowserWindow }, payload) => {
      const data = new Uint8Array(payload.arr);
      const win = BrowserWindow.getAllWindows().find((w) => !w.webContents.getURL().startsWith("file:"));
      win.webContents.send("nir:openVolume", { name: payload.name, data });
    }, { arr: bytes, name: "native-open.nii.gz" });
    await expect(page.getByText(/native-open\.nii\.gz/)).toBeVisible({ timeout: 20_000 });
  });
});

test.describe("container runtime (all-in-one)", () => {
  test.skip(process.env.NIR_E2E_CONTAINER !== "1", "set NIR_E2E_CONTAINER=1 (needs Docker + built nir-allinone image)");
  let app;

  test.afterAll(async () => {
    if (app) await app.close();
  });

  test("launches the all-in-one container and lands in the workspace", async () => {
    app = await launch({
      NIR_RUNTIME: "container",
      NIR_DESKTOP_BACKEND_PORT: "8814",
      NIR_DATA_DIR: path.join(os.tmpdir(), "nir-e2e-ctr"),
    });
    // First container run (init + migrations) can take a while.
    const page = await pageWithSelector(app, "#nir-desktop-statusbar", 180_000);
    await expect(page.locator("#nir-desktop-statusbar")).toBeVisible();
    expect(page.url()).toMatch(/127\.0\.0\.1:\d+|localhost:\d+/);
  });
});
