#!/usr/bin/env node
"use strict";

/**
 * verify_trust.js — verify platform code-signing / notarization for the desktop
 * installer artifacts. Complements verify_release_checksums.js (integrity) with
 * trust (authenticity).
 *
 * Usage:
 *   node verify_trust.js [distDir] <linux|macos|windows> [--require-signed]
 *
 * Behavior:
 *   - Reports each artifact as signed / unsigned.
 *   - Unsigned is allowed by default (internal/pilot fallback) and exits 0.
 *   - With --require-signed (or NIR_REQUIRE_SIGNED=1) any unsigned/untrusted
 *     artifact causes a non-zero exit — use this in CI when signing secrets are
 *     configured so the signed build path is actually enforced.
 *   - Linux has no signing in this track; integrity is checksum-only.
 */
const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

function run(cmd, args) {
  const r = spawnSync(cmd, args, { encoding: "utf8" });
  return { code: typeof r.status === "number" ? r.status : -1, out: `${r.stdout || ""}${r.stderr || ""}`, missing: !!r.error };
}

function lastLines(text, n = 1) {
  return (text || "").trim().split(/\r?\n/).filter(Boolean).slice(-n).join(" ");
}

function listFiles(dir, pred) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir).filter(pred).map((f) => path.join(dir, f));
}

function listApps(distDir) {
  const apps = [];
  if (!fs.existsSync(distDir)) return apps;
  for (const e of fs.readdirSync(distDir, { withFileTypes: true })) {
    if (e.isDirectory() && e.name.startsWith("mac")) {
      const sub = path.join(distDir, e.name);
      for (const f of fs.readdirSync(sub)) if (f.endsWith(".app")) apps.push(path.join(sub, f));
    }
  }
  return apps;
}

function verifyMac(distDir) {
  const results = [];
  if (run("codesign", ["--version"]).missing) {
    return { skipped: true, reason: "codesign not available (run on macOS)", results };
  }
  for (const app of listApps(distDir)) {
    const cs = run("codesign", ["--verify", "--deep", "--strict", "--verbose=2", app]);
    const signed = cs.code === 0;
    const gk = signed ? run("spctl", ["--assess", "--type", "exec", "-vv", app]) : null;
    results.push({
      artifact: path.basename(app),
      signed,
      gatekeeper: gk ? (gk.code === 0 ? "accepted" : "rejected") : "n/a",
      detail: lastLines(cs.out, 1),
    });
  }
  for (const dmg of listFiles(distDir, (f) => f.endsWith(".dmg"))) {
    const st = run("xcrun", ["stapler", "validate", dmg]);
    results.push({
      artifact: path.basename(dmg),
      signed: st.code === 0,
      notarized: st.code === 0,
      detail: lastLines(st.out, 1),
    });
  }
  return { skipped: false, results };
}

function verifyWindows(distDir) {
  const results = [];
  if (process.platform !== "win32") {
    return { skipped: true, reason: "Windows signature verification runs on Windows runners", results };
  }
  const installers = listFiles(distDir, (f) => f.endsWith(".exe") || f.endsWith(".msi"));
  for (const file of installers) {
    const ps = run("powershell", [
      "-NoProfile",
      "-Command",
      `(Get-AuthenticodeSignature '${file}').Status`,
    ]);
    const status = lastLines(ps.out, 1);
    results.push({ artifact: path.basename(file), signed: status === "Valid", detail: status });
  }
  return { skipped: false, results };
}

function verifyLinux(distDir) {
  const installers = listFiles(distDir, (f) => f.endsWith(".AppImage") || f.endsWith(".deb"));
  return {
    skipped: true,
    reason: "Linux artifacts are integrity-verified via checksums (no code-signing in this track)",
    results: installers.map((f) => ({ artifact: path.basename(f), signed: null, detail: "checksum-only" })),
  };
}

function main() {
  const args = process.argv.slice(2);
  const requireSigned = args.includes("--require-signed") || process.env.NIR_REQUIRE_SIGNED === "1";
  const positionals = args.filter((a) => !a.startsWith("--"));
  const repoRoot = path.resolve(__dirname, "..", "..");
  const distDir = positionals[0] ? path.resolve(positionals[0]) : path.join(repoRoot, "desktop", "dist");
  const platform = (positionals[1] || "").trim().toLowerCase();
  if (!["linux", "macos", "windows"].includes(platform)) {
    throw new Error("Platform argument required: linux | macos | windows");
  }

  const report =
    platform === "macos" ? verifyMac(distDir) : platform === "windows" ? verifyWindows(distDir) : verifyLinux(distDir);

  process.stdout.write(`Trust verification — ${platform} — ${distDir}\n`);
  if (report.skipped && report.results.length === 0) {
    process.stdout.write(`  SKIPPED: ${report.reason}\n`);
    return;
  }
  if (report.reason) process.stdout.write(`  note: ${report.reason}\n`);

  let unsigned = 0;
  for (const r of report.results) {
    const mark = r.signed === true ? "SIGNED" : r.signed === false ? "UNSIGNED" : "n/a";
    if (r.signed === false) unsigned += 1;
    const extra = [
      r.gatekeeper ? `gatekeeper=${r.gatekeeper}` : null,
      r.notarized !== undefined ? `notarized=${r.notarized}` : null,
      r.detail ? `(${r.detail})` : null,
    ]
      .filter(Boolean)
      .join(" ");
    process.stdout.write(`  [${mark}] ${r.artifact} ${extra}\n`);
  }

  if (unsigned > 0) {
    if (requireSigned) {
      process.stderr.write(`\nFAIL: ${unsigned} unsigned/untrusted artifact(s) with --require-signed.\n`);
      process.exit(2);
    }
    process.stdout.write(`\nWARN: ${unsigned} unsigned artifact(s) — allowed (internal/pilot fallback).\n`);
  } else if (report.results.some((r) => r.signed === true)) {
    process.stdout.write("\nOK: all checked artifacts are signed/trusted.\n");
  }
}

if (require.main === module) {
  main();
}

module.exports = { main };
