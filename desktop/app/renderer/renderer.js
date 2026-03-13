/* global nirDesktop */

const statusBadge = document.getElementById("statusBadge");
const statusText = document.getElementById("statusText");
const logOut = document.getElementById("logOut");
const autoOpenChk = document.getElementById("autoOpenChk");
const pathsText = document.getElementById("pathsText");
const preflightOut = document.getElementById("preflightOut");
const licenseStatusText = document.getElementById("licenseStatusText");
const licenseBadge = document.getElementById("licenseBadge");
const licenseText = document.getElementById("licenseText");
const vaultStatusText = document.getElementById("vaultStatusText");

const startBtn = document.getElementById("startBtn");
const stopAppBtn = document.getElementById("stopAppBtn");
const stopAllBtn = document.getElementById("stopAllBtn");
const openBtn = document.getElementById("openBtn");
const refreshBtn = document.getElementById("refreshBtn");
const controlBtn = document.getElementById("controlBtn");
const preflightBtn = document.getElementById("preflightBtn");
const diagBtn = document.getElementById("diagBtn");
const licenseRefreshBtn = document.getElementById("licenseRefreshBtn");
const licenseImportFileBtn = document.getElementById("licenseImportFileBtn");
const licenseImportTextBtn = document.getElementById("licenseImportTextBtn");
const vaultStatusBtn = document.getElementById("vaultStatusBtn");
const saveSecretBtn = document.getElementById("saveSecretBtn");
const loadSecretBtn = document.getElementById("loadSecretBtn");
const deleteSecretBtn = document.getElementById("deleteSecretBtn");
const secretKey = document.getElementById("secretKey");
const secretValue = document.getElementById("secretValue");
const secretPreset = document.getElementById("secretPreset");

function updateLicenseBadge(label, isGood) {
  licenseBadge.textContent = label;
  if (isGood) {
    licenseBadge.classList.remove("off");
  } else {
    licenseBadge.classList.add("off");
  }
}

function validateNamespacedSecretKey(key) {
  if (!key) return "Secret key is required.";
  if (!/^[a-z0-9_]+\.[a-z0-9_.-]+$/i.test(key)) {
    return "Secret key must be namespaced (example: pennsieve.api_key).";
  }
  return null;
}

function setBusy(busy) {
  [
    startBtn,
    stopAppBtn,
    stopAllBtn,
    openBtn,
    refreshBtn,
    controlBtn,
    preflightBtn,
    diagBtn,
    licenseRefreshBtn,
    licenseImportFileBtn,
    licenseImportTextBtn,
    vaultStatusBtn,
    saveSecretBtn,
    loadSecretBtn,
    deleteSecretBtn,
  ].forEach((b) => {
    b.disabled = busy;
  });
}

function printResult(title, result) {
  const out = [
    `[${new Date().toISOString()}] ${title}`,
    result && result.stdout ? result.stdout.trim() : "",
    result && result.stderr ? result.stderr.trim() : "",
  ]
    .filter(Boolean)
    .join("\n\n");
  logOut.textContent = out || "No command output.";
}

async function refreshStatus() {
  const s = await nirDesktop.getStatus();
  if (s.running) {
    statusBadge.textContent = "Running";
    statusBadge.classList.remove("off");
    statusText.textContent = `Backend reachable on port ${s.port}`;
  } else {
    statusBadge.textContent = "Stopped";
    statusBadge.classList.add("off");
    statusText.textContent = "Backend not reachable on 3000/3001";
  }
}

async function refreshSettings() {
  const settings = await nirDesktop.getDesktopSettings();
  autoOpenChk.checked = Boolean(settings.autoOpenOnStart);
}

async function refreshPaths() {
  const paths = await nirDesktop.getDesktopPaths();
  pathsText.textContent = `Settings: ${paths.settingsFile} | Log: ${paths.logFile}`;
}

async function refreshLicenseStatus() {
  const st = await nirDesktop.getLicenseStatus();
  if (!st.present) {
    licenseStatusText.textContent = `No license imported. ${st.reason || ""}`.trim();
    updateLicenseBadge("License: Missing", false);
    return;
  }
  if (!st.valid) {
    licenseStatusText.textContent = `License invalid: ${st.reason || "unknown"}`;
    updateLicenseBadge("License: Invalid", false);
    return;
  }
  const tier = st.planTier || (st.payload && st.payload.plan_tier) || "unknown";
  const org = st.organizationId || (st.payload && st.payload.organization_id) || "unknown";
  const feat = typeof st.featureCount === "number"
    ? st.featureCount
    : ((st.payload && Array.isArray(st.payload.features)) ? st.payload.features.length : 0);
  licenseStatusText.textContent = `License valid (${tier}, org: ${org}, features: ${feat}). Expires: ${st.expiresAt} (${st.daysRemaining} days remaining)`;
  updateLicenseBadge(`License: Valid (${st.daysRemaining}d)`, true);
}

async function refreshVaultStatus() {
  const st = await nirDesktop.getCredentialStoreStatus();
  vaultStatusText.textContent = `Backend: ${st.backend} (service: ${st.serviceName})`;
}

startBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.startBackend();
    printResult("Start backend", res);
    await refreshStatus();
  } finally {
    setBusy(false);
  }
});

stopAppBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.stopBackendApp();
    printResult("Stop app services", res);
    await refreshStatus();
  } finally {
    setBusy(false);
  }
});

stopAllBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.stopBackendAll();
    printResult("Stop app + infra", res);
    await refreshStatus();
  } finally {
    setBusy(false);
  }
});

openBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.openAppInMainWindow();
    if (!res.ok) {
      printResult("Open NIR in same window", { stderr: res.error || "Backend not running." });
    } else {
      printResult("Open NIR in same window", { stdout: `Opened http://localhost:${res.port}` });
    }
  } finally {
    setBusy(false);
  }
});

controlBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    await nirDesktop.openControlCenter();
    printResult("Control center", { stdout: "Control center opened." });
  } finally {
    setBusy(false);
  }
});

refreshBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    await refreshStatus();
    await refreshSettings();
    await refreshPaths();
    await refreshLicenseStatus();
    await refreshVaultStatus();
  } finally {
    setBusy(false);
  }
});

autoOpenChk.addEventListener("change", async () => {
  try {
    const next = await nirDesktop.updateDesktopSettings({
      autoOpenOnStart: autoOpenChk.checked,
    });
    printResult("Settings updated", { stdout: `autoOpenOnStart=${next.autoOpenOnStart}` });
  } catch (e) {
    printResult("Settings update failed", { stderr: String(e) });
  }
});

preflightBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const result = await nirDesktop.runPreflight();
    preflightOut.textContent = JSON.stringify(result, null, 2);
    printResult("Preflight", {
      stdout: result.ok ? "Preflight passed." : "Preflight completed with warnings.",
      stderr: result.warnings && result.warnings.length ? result.warnings.join("\n") : "",
    });
  } catch (e) {
    printResult("Preflight failed", { stderr: String(e) });
  } finally {
    setBusy(false);
  }
});

diagBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.exportDiagnostics();
    if (res.ok) {
      printResult("Diagnostics exported", { stdout: res.path });
    } else {
      printResult("Diagnostics export failed", { stderr: JSON.stringify(res) });
    }
  } catch (e) {
    printResult("Diagnostics export failed", { stderr: String(e) });
  } finally {
    setBusy(false);
  }
});

licenseRefreshBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    await refreshLicenseStatus();
  } finally {
    setBusy(false);
  }
});

licenseImportFileBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.importLicenseFile();
    if (!res.ok) {
      printResult("License import file failed", { stderr: res.error || "Import failed" });
    } else {
      printResult("License import file", { stdout: "Imported license file successfully." });
      await refreshLicenseStatus();
    }
  } finally {
    setBusy(false);
  }
});

licenseImportTextBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const res = await nirDesktop.importLicenseText(licenseText.value || "");
    if (!res.ok) {
      printResult("License import text failed", { stderr: res.error || "Import failed" });
    } else {
      printResult("License import text", { stdout: "Imported license text successfully." });
      await refreshLicenseStatus();
    }
  } finally {
    setBusy(false);
  }
});

vaultStatusBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    await refreshVaultStatus();
  } finally {
    setBusy(false);
  }
});

saveSecretBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const key = (secretKey.value || "").trim();
    const keyErr = validateNamespacedSecretKey(key);
    if (keyErr) {
      printResult("Save secret failed", { stderr: keyErr });
      return;
    }
    const res = await nirDesktop.saveSecret(key, secretValue.value || "");
    if (!res.ok) {
      printResult("Save secret failed", { stderr: res.error || "Unknown error." });
      return;
    }
    printResult("Save secret", { stdout: `Saved using backend: ${res.backend}` });
    await refreshVaultStatus();
  } finally {
    setBusy(false);
  }
});

loadSecretBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const key = (secretKey.value || "").trim();
    const keyErr = validateNamespacedSecretKey(key);
    if (keyErr) {
      printResult("Load secret failed", { stderr: keyErr });
      return;
    }
    const res = await nirDesktop.loadSecret(key);
    if (!res.ok) {
      printResult("Load secret failed", { stderr: res.error || "Unknown error." });
      return;
    }
    if (res.value === null || res.value === "") {
      printResult("Load secret", { stdout: "No value found for key." });
      return;
    }
    secretValue.value = res.value;
    printResult("Load secret", { stdout: `Loaded using backend: ${res.backend}` });
  } finally {
    setBusy(false);
  }
});

deleteSecretBtn.addEventListener("click", async () => {
  setBusy(true);
  try {
    const key = (secretKey.value || "").trim();
    const keyErr = validateNamespacedSecretKey(key);
    if (keyErr) {
      printResult("Delete secret failed", { stderr: keyErr });
      return;
    }
    const res = await nirDesktop.deleteSecret(key);
    if (!res.ok) {
      printResult("Delete secret failed", { stderr: res.error || "Unknown error." });
      return;
    }
    secretValue.value = "";
    printResult("Delete secret", { stdout: `Deleted using backend: ${res.backend}` });
  } finally {
    setBusy(false);
  }
});

secretPreset.addEventListener("change", () => {
  if (secretPreset.value) {
    secretKey.value = secretPreset.value;
  }
});

Promise.all([
  refreshStatus(),
  refreshSettings(),
  refreshPaths(),
  refreshLicenseStatus(),
  refreshVaultStatus(),
]).catch((e) => {
  printResult("Desktop init failed", { stderr: String(e) });
});
