/* NIR Desktop control center — renderer logic (uses window.nir bridge). */
/* global window, document */
(function () {
  "use strict";

const nir = window.nir;
const $ = (id) => document.getElementById(id);

// Licensing is deferred for this version (added later). Flip to true to re-enable
// the License card/badge; enforcement is already permissive in unlicensed mode.
const LICENSE_ENABLED = false;

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
function setEngineBadge(stateName) {
  const badge = $("engineBadge");
  if (!badge) return;
  const map = {
    healthy: ["badge badge-ok", "Engine: healthy"],
    starting: ["badge badge-warn", "Engine: starting…"],
    stopped: ["badge badge-off", "Engine: stopped"],
  };
  const [cls, text] = map[stateName] || map.stopped;
  badge.className = cls;
  badge.textContent = text;
}

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
    setEngineBadge("healthy");
  } else if (status.backend && status.backend.running) {
    dot.className = "dot dot-warn";
    label.textContent = "Starting / not healthy yet";
    openBtn.disabled = true;
    setEngineBadge("starting");
  } else {
    dot.className = "dot dot-off";
    label.textContent = "Stopped";
    openBtn.disabled = true;
    setEngineBadge("stopped");
  }

  if (status.backend) {
    meta.textContent = `${status.backend.url} · backend PID ${
      status.backend.pid || "—"
    } · worker ${status.celery && status.celery.running ? "running" : "stopped"}`;
  }

  renderRuntimeRows(await nir.backend.runtime());
}

// Render runtime info as clean labelled rows (instead of a raw JSON dump).
function renderRuntimeRows(rt) {
  const el = $("runtimeRows");
  if (!el || !rt) return;
  const rows =
    rt.mode === "container"
      ? [
          ["Mode", "Container"],
          ["Image", rt.image],
          ["Container", rt.container],
          ["Port", rt.port],
          ["Data dir", rt.dataDir],
        ]
      : [
          ["Mode", "Local process"],
          ["Python", rt.pythonCmd || "—"],
          ["Port", rt.port],
          ["Repo", rt.repoDir],
        ];
  el.innerHTML = rows
    .map(
      ([k, v]) =>
        `<dt>${k}</dt><dd title="${String(v ?? "—")}">${String(v ?? "—")}</dd>`
    )
    .join("");
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
  if (!silent) toast("Running checks…");
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
      toast("Checks passed.");
    }
  }
}

// ---- License -------------------------------------------------------------
async function refreshLicense() {
  const status = await nir.license.status();
  const enf = await nir.license.enforcement();
  const badge = $("licenseBadge");
  const detail = $("licenseDetail");
  const modeEl = $("licenseMode");
  const warn = $("licenseWarn");

  modeEl.textContent = `Mode: ${enf.mode}${enf.allowFullFeatures ? "" : " (limited)"}`;

  if (status.valid) {
    badge.className = "badge badge-ok";
    badge.textContent = `License: ${status.planTier || "active"}${status.inGrace ? " (grace)" : ""}`;
    const exp = status.expiresAt ? new Date(status.expiresAt).toLocaleDateString() : "—";
    detail.textContent = `Valid · org ${status.organizationId || "—"} · expires ${exp} · ${
      status.daysRemaining
    } day(s) · ${status.featureCount || 0} feature(s).`;
  } else {
    badge.className = enf.mode === "unlicensed" ? "badge badge-muted" : "badge badge-warn";
    badge.textContent = enf.mode === "unlicensed" ? "License: community" : "License: invalid";
    detail.textContent = status.reason || "No valid license imported.";
  }

  // Warnings: grace period, expiring soon, or limited (enforced) mode.
  if (status.inGrace) {
    warn.hidden = false;
    warn.className = "inlinewarn";
    warn.textContent = `Offline grace: ${status.graceDaysRemaining} day(s) left — renew to avoid losing access.`;
  } else if (!enf.allowFullFeatures) {
    warn.hidden = false;
    warn.className = "inlinewarn bad";
    warn.textContent = `Limited mode — ${enf.reason || "valid license required"}. Opening the app is disabled.`;
  } else if (status.valid && status.expiringSoon) {
    warn.hidden = false;
    warn.className = "inlinewarn";
    warn.textContent = `License expires in ${status.daysRemaining} day(s) — plan your renewal.`;
  } else {
    warn.hidden = true;
  }
}

async function importLicense() {
  const res = await nir.license.importFile();
  if (res.ok) toast("License imported.");
  else toast(res.error || "License import failed.");
  refreshLicense();
}

async function importLicenseText() {
  const text = window.prompt("Paste the license token JSON ({ payload, signature }):");
  if (!text) return;
  const res = await nir.license.importText(text);
  if (res.ok) toast("License imported.");
  else toast(res.error || "License import failed.");
  refreshLicense();
}

// ---- Credential vault ----------------------------------------------------
async function refreshCredsBackend() {
  const st = await nir.creds.status();
  $("credsBackend").textContent = `Backend: ${st.backend} (service ${st.serviceName})`;
}

async function credSet() {
  const name = $("credKey").value.trim();
  const value = $("credValue").value;
  if (!name || !value) {
    toast("Enter a namespaced key and value.");
    return;
  }
  const res = await nir.creds.set(name, value);
  $("credsDetail").textContent = res.ok
    ? `Saved "${name}" via ${res.backend}.`
    : `Error: ${res.error || "save failed"}`;
  $("credValue").value = "";
}

async function credGet() {
  const name = $("credKey").value.trim();
  if (!name) {
    toast("Enter a key to retrieve.");
    return;
  }
  const res = await nir.creds.get(name);
  if (!res.ok) {
    $("credsDetail").textContent = `Error: ${res.error}`;
  } else if (res.value == null) {
    $("credsDetail").textContent = `No value stored for "${name}".`;
  } else {
    $("credsDetail").textContent = `"${name}" is set (${res.value.length} chars) via ${res.backend}. Value not displayed.`;
  }
}

async function credDelete() {
  const name = $("credKey").value.trim();
  if (!name) {
    toast("Enter a key to delete.");
    return;
  }
  const res = await nir.creds.delete(name);
  $("credsDetail").textContent = res.ok ? `Deleted "${name}".` : `Error: ${res.error}`;
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
  $("btnImportLicenseText").addEventListener("click", importLicenseText);
  $("btnCredSet").addEventListener("click", credSet);
  $("btnCredGet").addEventListener("click", credGet);
  $("btnCredDelete").addEventListener("click", credDelete);
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
  if (LICENSE_ENABLED) {
    refreshLicense();
  } else {
    // Hide the license card + header badge while licensing is deferred.
    const card = $("licenseCard");
    if (card) card.hidden = true;
    const badge = $("licenseBadge");
    if (badge) badge.hidden = true;
  }
  refreshLock();
  refreshCredsBackend();
  // Auto-run preflight on load so startup state (banner + Start gating) is set.
  // If we landed here because auto-launch couldn't reach the workspace, surface
  // why — after preflight renders, so the notice wins the banner.
  const notice = new URLSearchParams(window.location.search).get("notice");
  runPreflight(true).then(() => {
    if (notice) {
      const banner = $("startupBanner");
      banner.textContent = `Couldn't open the workspace automatically: ${notice} — fix below, then “Open NeuroInsight”.`;
      banner.className = "banner banner-bad";
      toast(notice);
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
})();
