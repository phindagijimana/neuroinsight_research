/* global nirDesktop */

// ── Element refs ────────────────────────────────────────────────────────────
const statusDot       = document.getElementById("statusDot");
const statusLabel     = document.getElementById("statusLabel");
const statusText      = document.getElementById("statusText");
const statusToast     = document.getElementById("statusToast");

const licensePill     = document.getElementById("licensePill");
const licensePillText = document.getElementById("licensePillText");
const lockPill        = document.getElementById("lockPill");
const lockPillText    = document.getElementById("lockPillText");

const licenseBadge    = document.getElementById("licenseBadge");
const licenseStatusText = document.getElementById("licenseStatusText");
const licenseText     = document.getElementById("licenseText");

const lockBadge       = document.getElementById("lockBadge");
const lockStatusText  = document.getElementById("lockStatusText");
const lockPin         = document.getElementById("lockPin");

const vaultBadge      = document.getElementById("vaultBadge");
const vaultStatusText = document.getElementById("vaultStatusText");
const secretKey       = document.getElementById("secretKey");
const secretValue     = document.getElementById("secretValue");
const secretPreset    = document.getElementById("secretPreset");

const preflightOut    = document.getElementById("preflightOut");
const pathsText       = document.getElementById("pathsText");

const openBtn             = document.getElementById("openBtn");
const startBtn            = document.getElementById("startBtn");
const stopAppBtn          = document.getElementById("stopAppBtn");
const stopAllBtn          = document.getElementById("stopAllBtn");
const refreshBtn          = document.getElementById("refreshBtn");
const preflightBtn        = document.getElementById("preflightBtn");
const diagBtn             = document.getElementById("diagBtn");
const licenseRefreshBtn   = document.getElementById("licenseRefreshBtn");
const licenseImportFileBtn= document.getElementById("licenseImportFileBtn");
const licenseImportTextBtn= document.getElementById("licenseImportTextBtn");
const lockEnableBtn       = document.getElementById("lockEnableBtn");
const lockDisableBtn      = document.getElementById("lockDisableBtn");
const lockUnlockBtn       = document.getElementById("lockUnlockBtn");
const lockNowBtn          = document.getElementById("lockNowBtn");
const saveSecretBtn       = document.getElementById("saveSecretBtn");
const loadSecretBtn       = document.getElementById("loadSecretBtn");
const deleteSecretBtn     = document.getElementById("deleteSecretBtn");

// ── Status toast ─────────────────────────────────────────────────────────────
let toastTimer = null;
function showToast(msg, type = "neutral") {
  if (!statusToast) return;
  statusToast.textContent = msg;
  statusToast.className = "visible" + (type === "ok" ? " ok" : type === "err" ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    statusToast.className = "";
  }, 6000);
}

// Legacy printResult shim used by event handlers below
function printResult(title, result) {
  const parts = [title];
  if (result && result.stdout && result.stdout.trim()) parts.push(result.stdout.trim());
  if (result && result.stderr && result.stderr.trim()) parts.push(result.stderr.trim());
  const msg = parts.filter(Boolean).join(" — ");
  const isErr = !!(result && result.stderr && result.stderr.trim() && !(result && result.ok));
  showToast(msg, isErr ? "err" : "ok");
}

// ── Busy state ────────────────────────────────────────────────────────────────
const allBtns = [
  openBtn, startBtn, stopAppBtn, stopAllBtn, refreshBtn,
  preflightBtn, diagBtn, licenseRefreshBtn, licenseImportFileBtn, licenseImportTextBtn,
  lockEnableBtn, lockDisableBtn, lockUnlockBtn, lockNowBtn,
  saveSecretBtn, loadSecretBtn, deleteSecretBtn,
].filter(Boolean);

function setBusy(busy) {
  allBtns.forEach((b) => { b.disabled = busy; });
}

// ── Validators ────────────────────────────────────────────────────────────────
function validateNamespacedSecretKey(key) {
  if (!key) return "Secret key is required.";
  if (!/^[a-z0-9_]+\.[a-z0-9_.-]+$/i.test(key)) {
    return "Secret key must be namespaced (e.g. pennsieve.api_key).";
  }
  return null;
}

// ── Refresh helpers ──────────────────────────────────────────────────────────
async function refreshStatus() {
  const s = await nirDesktop.getStatus();
  if (s.running) {
    statusDot.className = "status-dot on";
    statusLabel.textContent = "Backend Running";
    statusText.textContent = s.managed
      ? `Desktop-managed · port ${s.port}`
      : `External backend · port ${s.port}`;
    openBtn.disabled = false;
  } else {
    statusDot.className = "status-dot off";
    statusLabel.textContent = "Backend Stopped";
    statusText.textContent = "Not reachable on ports 3000–3050";
    openBtn.disabled = false;
  }
}

async function refreshLicenseStatus() {
  const st = await nirDesktop.getLicenseStatus();
  if (!st.present) {
    licenseBadge.textContent = "Missing";
    licenseBadge.className = "summary-badge bad";
    licenseStatusText.textContent = st.reason || "No license file imported.";
    licensePill.className = "pill bad";
    licensePillText.textContent = "No License";
    return;
  }
  if (!st.valid) {
    licenseBadge.textContent = "Invalid";
    licenseBadge.className = "summary-badge bad";
    licenseStatusText.textContent = `Invalid: ${st.reason || "unknown"}`;
    licensePill.className = "pill bad";
    licensePillText.textContent = "Invalid";
    return;
  }
  const days = st.daysRemaining ?? "?";
  const tier = st.planTier || (st.payload && st.payload.plan_tier) || "";
  licenseBadge.textContent = `Valid · ${days}d`;
  licenseBadge.className = "summary-badge ok";
  licenseStatusText.textContent = `Valid${tier ? ` (${tier})` : ""}. Expires: ${st.expiresAt} (${days} days remaining)`;
  licensePill.className = "pill ok";
  licensePillText.textContent = `License · ${days}d`;
}

async function refreshLockStatus() {
  const st = await nirDesktop.getAppLockStatus();
  if (!st.enabled) {
    lockBadge.textContent = "Disabled";
    lockBadge.className = "summary-badge";
    lockStatusText.textContent = "App lock is disabled.";
    lockPill.className = "pill";
    lockPillText.textContent = "Unlocked";
    return;
  }
  if (st.unlocked) {
    lockBadge.textContent = "Unlocked";
    lockBadge.className = "summary-badge ok";
    lockStatusText.textContent = "App lock enabled — currently unlocked.";
    lockPill.className = "pill ok";
    lockPillText.textContent = "Unlocked";
  } else {
    lockBadge.textContent = "Locked";
    lockBadge.className = "summary-badge bad";
    lockStatusText.textContent = "App lock enabled — currently locked.";
    lockPill.className = "pill warn";
    lockPillText.textContent = "Locked";
  }
}

async function refreshVaultStatus() {
  const st = await nirDesktop.getCredentialStoreStatus();
  vaultBadge.textContent = st.backend || "…";
  vaultStatusText.textContent = `Backend: ${st.backend} (service: ${st.serviceName})`;
}

async function refreshPaths() {
  const paths = await nirDesktop.getDesktopPaths();
  if (pathsText) {
    pathsText.textContent = `Settings: ${paths.settingsFile}\nLog: ${paths.logFile}`;
  }
}

// ── Event handlers ────────────────────────────────────────────────────────────
startBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    showToast("Starting backend…");
    const res = await nirDesktop.startBackend();
    printResult("Start", res);
    await refreshStatus();
  } finally { setBusy(false); }
});

stopAppBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.stopBackendApp();
    printResult("Stop services", res);
    await refreshStatus();
  } finally { setBusy(false); }
});

stopAllBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.stopBackendAll();
    printResult("Stop all", res);
    await refreshStatus();
  } finally { setBusy(false); }
});

openBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.openAppInMainWindow();
    if (!res.ok) showToast(res.error || "Backend not running.", "err");
  } finally { setBusy(false); }
});

refreshBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    await Promise.all([
      refreshStatus(), refreshLicenseStatus(),
      refreshLockStatus(), refreshVaultStatus(), refreshPaths(),
    ]);
  } finally { setBusy(false); }
});

preflightBtn.addEventListener("click", async () => {
  setBusy(true);
  preflightOut.textContent = "Running…";
  preflightOut.classList.add("visible");
  try {
    const result = await nirDesktop.runPreflight();
    preflightOut.textContent = JSON.stringify(result, null, 2);
    showToast(result.ok ? "Preflight passed." : "Preflight completed with warnings.", result.ok ? "ok" : "neutral");
  } catch (e) {
    preflightOut.textContent = String(e);
    showToast("Preflight failed.", "err");
  } finally { setBusy(false); }
});

diagBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.exportDiagnostics();
    if (res.ok) {
      showToast(`Diagnostics exported: ${res.path}`, "ok");
    } else {
      showToast("Diagnostics export failed.", "err");
    }
  } catch (e) {
    showToast(String(e), "err");
  } finally { setBusy(false); }
});

licenseRefreshBtn.addEventListener("click", async () => {
  setBusy(true);
  try { await refreshLicenseStatus(); } finally { setBusy(false); }
});

licenseImportFileBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.importLicenseFile();
    if (!res.ok) { showToast(res.error || "Import failed.", "err"); return; }
    showToast("License imported successfully.", "ok");
    await refreshLicenseStatus();
  } finally { setBusy(false); }
});

licenseImportTextBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.importLicenseText(licenseText.value || "");
    if (!res.ok) { showToast(res.error || "Import failed.", "err"); return; }
    showToast("License imported successfully.", "ok");
    licenseText.value = "";
    await refreshLicenseStatus();
  } finally { setBusy(false); }
});

lockEnableBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.enableAppLock(lockPin.value || "");
    if (!res.ok) { showToast(res.error || "Failed to enable lock.", "err"); return; }
    showToast("App lock enabled.", "ok");
    lockPin.value = "";
    await refreshLockStatus();
  } finally { setBusy(false); }
});

lockDisableBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.disableAppLock(lockPin.value || "");
    if (!res.ok) { showToast(res.error || "Failed to disable lock.", "err"); return; }
    showToast("App lock disabled.", "ok");
    lockPin.value = "";
    await refreshLockStatus();
  } finally { setBusy(false); }
});

lockUnlockBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.unlockApp(lockPin.value || "");
    if (!res.ok) { showToast(res.error || "Invalid PIN.", "err"); return; }
    showToast("App unlocked.", "ok");
    lockPin.value = "";
    await refreshLockStatus();
  } finally { setBusy(false); }
});

lockNowBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.lockNow();
    if (!res.ok) { showToast(res.error || "Lock failed.", "err"); return; }
    showToast("App locked.", "ok");
    await refreshLockStatus();
  } finally { setBusy(false); }
});

saveSecretBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const key = (secretKey.value || "").trim();
    const err = validateNamespacedSecretKey(key);
    if (err) { showToast(err, "err"); return; }
    const res = await nirDesktop.saveSecret(key, secretValue.value || "");
    if (!res.ok) { showToast(res.error || "Save failed.", "err"); return; }
    showToast(`Saved via ${res.backend}.`, "ok");
    await refreshVaultStatus();
  } finally { setBusy(false); }
});

loadSecretBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const key = (secretKey.value || "").trim();
    const err = validateNamespacedSecretKey(key);
    if (err) { showToast(err, "err"); return; }
    const res = await nirDesktop.loadSecret(key);
    if (!res.ok) { showToast(res.error || "Load failed.", "err"); return; }
    if (res.value === null || res.value === "") { showToast("No value found for key.", "neutral"); return; }
    secretValue.value = res.value;
    showToast("Secret loaded.", "ok");
  } finally { setBusy(false); }
});

deleteSecretBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const key = (secretKey.value || "").trim();
    const err = validateNamespacedSecretKey(key);
    if (err) { showToast(err, "err"); return; }
    const res = await nirDesktop.deleteSecret(key);
    if (!res.ok) { showToast(res.error || "Delete failed.", "err"); return; }
    secretValue.value = "";
    showToast("Secret deleted.", "ok");
  } finally { setBusy(false); }
});

secretPreset.addEventListener("change", () => {
  if (secretPreset.value) secretKey.value = secretPreset.value;
});

// ── Init ──────────────────────────────────────────────────────────────────────
Promise.all([
  refreshStatus(),
  refreshLicenseStatus(),
  refreshLockStatus(),
  refreshVaultStatus(),
  refreshPaths(),
]).catch((e) => {
  showToast("Initialisation error: " + String(e), "err");
});
