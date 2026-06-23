/* NIR Desktop control center — renderer logic (uses window.nir bridge). */
/* global window, document */
(function () {
  "use strict";

const nir = window.nir;
const $ = (id) => document.getElementById(id);

// Tracks whether the environment has blockers (gates the Start button) and the
// most recent diagnostics bundle path (gates the reveal button).
const state = { preflightReady: true, lastBundlePath: null };

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2600);
}

// ---- Backend -------------------------------------------------------------
async function refreshStatus() {
  const status = await nir.backend.status();
  const dot = $("backendDot");
  const label = $("backendStatus");
  const meta = $("backendMeta");
  const openBtn = $("btnOpenUI");

  if (status.backend && status.backend.healthy) {
    dot.className = "dot dot-on";
    label.textContent = "Running (healthy)";
    openBtn.disabled = false;
  } else if (status.backend && status.backend.running) {
    dot.className = "dot dot-warn";
    label.textContent = "Starting / not healthy yet";
    openBtn.disabled = true;
  } else {
    dot.className = "dot dot-off";
    label.textContent = "Stopped";
    openBtn.disabled = true;
  }

  if (status.backend) {
    meta.textContent = `URL ${status.backend.url} · backend PID ${
      status.backend.pid || "—"
    } · celery ${status.celery && status.celery.running ? "running" : "stopped"}`;
  }

  const runtime = await nir.backend.runtime();
  $("runtimeInfo").textContent = JSON.stringify(runtime, null, 2);
}

function applyStartGate() {
  // The Start button is disabled while preflight reports blockers.
  $("btnStart").disabled = !state.preflightReady;
  $("btnStart").title = state.preflightReady
    ? ""
    : "Resolve preflight blockers before starting the backend.";
}

async function startBackend() {
  if (!state.preflightReady) {
    toast("Cannot start: resolve preflight blockers first.");
    return;
  }
  $("btnStart").disabled = true;
  toast("Starting backend…");
  const res = await nir.backend.start();
  applyStartGate();
  if (res.ok) {
    toast(res.backend && res.backend.reused ? "Backend already running." : "Backend started.");
  } else {
    const err = (res.backend && res.backend.error) || res.error || "Failed to start.";
    toast(`Backend error: ${err}`);
  }
  refreshStatus();
}

async function stopBackend() {
  toast("Stopping backend…");
  await nir.backend.stop();
  refreshStatus();
}

async function openUI() {
  const res = await nir.backend.openUI();
  if (!res.ok) toast(res.error || "Could not open UI.");
}

// ---- Preflight -----------------------------------------------------------
function renderBanner(report) {
  const banner = $("startupBanner");
  const parts = [report.summary || ""];
  if (report.blockers && report.blockers.length) parts.push(report.blockers.join(" "));
  if (report.warnings && report.warnings.length) parts.push(report.warnings.join(" "));
  banner.textContent = parts.filter(Boolean).join(" — ");
  if (!report.ready) banner.className = "banner banner-bad";
  else if (report.warnings && report.warnings.length) banner.className = "banner banner-warn";
  else banner.className = "banner banner-ok";
}

async function runPreflight(silent) {
  $("btnPreflight").disabled = true;
  if (!silent) toast("Running preflight…");
  const report = await nir.preflight.run();
  $("btnPreflight").disabled = false;

  // Gate the Start button + update the startup banner.
  state.preflightReady = !!report.ready;
  applyStartGate();
  renderBanner(report);

  const list = $("preflightList");
  list.innerHTML = "";

  const checks = report.checks || {};
  const rows = [
    ["Docker", checks.docker && checks.docker.ok],
    ["Node", checks.node && checks.node.ok],
    ["npm", checks.npm && checks.npm.ok],
    ["Python", checks.python && checks.python.ok],
    ["Celery", checks.celery && checks.celery.ok],
    ["Keychain", checks.keychain && checks.keychain.ok],
    [
      "Disk (>20GB)",
      checks.disk && checks.disk.ok ? checks.disk.freeGB >= 20 : false,
    ],
  ];
  for (const [name, ok] of rows) {
    const li = document.createElement("li");
    const n = document.createElement("span");
    n.textContent = name;
    const v = document.createElement("span");
    v.textContent = ok ? "OK" : "Check";
    v.className = ok ? "ok" : "bad";
    li.append(n, v);
    list.appendChild(li);
  }
  if (!silent) {
    if (!report.ready) {
      toast(`${report.blockers.length} blocker(s) — see banner.`);
    } else if (report.warnings && report.warnings.length) {
      toast(`${report.warnings.length} warning(s) — see list.`);
    } else {
      toast("Preflight passed.");
    }
  }
}

// ---- License -------------------------------------------------------------
async function refreshLicense() {
  const status = await nir.license.status();
  const badge = $("licenseBadge");
  const detail = $("licenseDetail");
  if (status.valid) {
    badge.className = "badge badge-ok";
    badge.textContent = `License: ${status.planTier || "active"}`;
    detail.textContent = `Valid · org ${status.organizationId || "—"} · ${
      status.daysRemaining
    } days remaining · ${status.featureCount || 0} feature(s).`;
  } else {
    badge.className = "badge badge-warn";
    badge.textContent = "License: none";
    detail.textContent = status.reason || "No valid license imported.";
  }
}

async function importLicense() {
  const res = await nir.license.importFile();
  if (res.ok) toast("License imported.");
  else toast(res.error || "License import failed.");
  refreshLicense();
}

// ---- App lock ------------------------------------------------------------
async function refreshLock() {
  const st = await nir.lock.status();
  $("lockDetail").textContent = st.enabled
    ? st.unlocked
      ? "Enabled · unlocked for this session."
      : "Enabled · LOCKED. Unlock to use sensitive actions."
    : "Disabled (no PIN). Sensitive actions are allowed.";
}

function pin() {
  return $("pinInput").value;
}

async function lockAction(fn, okMsg) {
  const res = await fn(pin());
  if (res.ok) {
    toast(okMsg);
    $("pinInput").value = "";
  } else {
    toast(res.error || "Action failed.");
  }
  refreshLock();
}

// ---- Diagnostics ---------------------------------------------------------
async function exportDiagnostics() {
  toast("Exporting diagnostics…");
  const res = await nir.diagnostics.export();
  if (res.ok) {
    state.lastBundlePath = res.path;
    $("diagnosticsDetail").textContent = `Saved: ${res.path}`;
    $("btnRevealBundle").disabled = false;
    toast("Diagnostics exported.");
  } else {
    toast(res.error || "Export failed.");
  }
}

async function revealBundle() {
  if (!state.lastBundlePath) return;
  await nir.diagnostics.reveal(state.lastBundlePath);
}

async function loadPlatform() {
  try {
    const p = await nir.platform.summary();
    $("platformLine").textContent = `Platform: ${p.os} / ${p.arch}`;
  } catch (_e) {
    $("platformLine").textContent = "Platform: unknown";
  }
}

// ---- Wire up -------------------------------------------------------------
function init() {
  $("btnStart").addEventListener("click", startBackend);
  $("btnStop").addEventListener("click", stopBackend);
  $("btnOpenUI").addEventListener("click", openUI);
  $("btnRefresh").addEventListener("click", refreshStatus);
  $("btnPreflight").addEventListener("click", () => runPreflight(false));
  $("btnImportLicense").addEventListener("click", importLicense);
  $("btnDiagnostics").addEventListener("click", exportDiagnostics);
  $("btnRevealBundle").addEventListener("click", revealBundle);

  $("btnLockEnable").addEventListener("click", () => lockAction(nir.lock.enable, "App lock enabled."));
  $("btnLockUnlock").addEventListener("click", () => lockAction(nir.lock.unlock, "Unlocked."));
  $("btnLockDisable").addEventListener("click", () => lockAction(nir.lock.disable, "App lock disabled."));
  $("btnLockNow").addEventListener("click", async () => {
    await nir.lock.lockNow();
    refreshLock();
    toast("Locked.");
  });

  loadPlatform();
  refreshStatus();
  refreshLicense();
  refreshLock();
  // Auto-run preflight on load so startup state (banner + Start gating) is set.
  runPreflight(true);
}

document.addEventListener("DOMContentLoaded", init);
})();
