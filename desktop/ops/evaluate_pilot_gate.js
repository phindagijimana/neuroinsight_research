#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const THRESHOLDS = {
  coreFlowCompletionRate: 90,
  parityCompletionRate: 90,
  crashFreeLaunchRate: 98,
  slaAdherenceRate: 90,
};

function toNum(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

function readReport(reportPath) {
  const raw = fs.readFileSync(reportPath, "utf8");
  return JSON.parse(raw);
}

function platformChecks(name, p = {}) {
  const failures = [];
  if (!p.evidence_present) failures.push(`${name}: evidence missing`);
  if (toNum(p.diagnostics_samples) < 1) failures.push(`${name}: diagnostics sample missing`);
  if (!p.failure_recovery_drill_passed) {
    failures.push(`${name}: failure-recovery drill not passed`);
  }
  return failures;
}

function evaluate(report) {
  const failures = [];
  const warnings = [];

  if (toNum(report.core_flow_completion_rate) < THRESHOLDS.coreFlowCompletionRate) {
    failures.push(
      `core_flow_completion_rate ${report.core_flow_completion_rate} < ${THRESHOLDS.coreFlowCompletionRate}`
    );
  }
  if (toNum(report.parity_completion_rate) < THRESHOLDS.parityCompletionRate) {
    failures.push(
      `parity_completion_rate ${report.parity_completion_rate} < ${THRESHOLDS.parityCompletionRate}`
    );
  }
  if (toNum(report.crash_free_launch_rate) < THRESHOLDS.crashFreeLaunchRate) {
    failures.push(
      `crash_free_launch_rate ${report.crash_free_launch_rate} < ${THRESHOLDS.crashFreeLaunchRate}`
    );
  }
  if (toNum(report.sla_adherence_rate) < THRESHOLDS.slaAdherenceRate) {
    failures.push(
      `sla_adherence_rate ${report.sla_adherence_rate} < ${THRESHOLDS.slaAdherenceRate}`
    );
  }

  const defects = report.open_defects || {};
  const p0 = toNum(defects.p0);
  const p1 = toNum(defects.p1);
  const p2 = toNum(defects.p2);
  const p3 = toNum(defects.p3);
  if (p0 > 0) failures.push(`unresolved p0 defects: ${p0}`);
  if (p1 > 0) failures.push(`unresolved p1 defects: ${p1}`);

  const platforms = report.platforms || {};
  failures.push(...platformChecks("linux", platforms.linux));
  failures.push(...platformChecks("macos", platforms.macos));
  failures.push(...platformChecks("windows", platforms.windows));

  const conditionalNotes = Array.isArray(report.conditional_go_notes)
    ? report.conditional_go_notes.filter((x) => x && String(x.issue || "").trim())
    : [];

  const hasP2P3Only = p0 === 0 && p1 === 0 && (p2 > 0 || p3 > 0);
  if (hasP2P3Only && conditionalNotes.length === 0) {
    warnings.push("p2/p3 defects exist but conditional_go_notes is empty");
  }

  let decision = "go";
  if (failures.length > 0) {
    decision = "no_go";
  } else if (hasP2P3Only) {
    decision = "conditional_go";
  }
  return { decision, failures, warnings };
}

function main() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  const reportPath = process.argv[2]
    ? path.resolve(process.argv[2])
    : path.join(repoRoot, "desktop", "ops", "pilot_reliability_report.json");

  if (!fs.existsSync(reportPath)) {
    throw new Error(`Report not found: ${reportPath}`);
  }
  const report = readReport(reportPath);
  const result = evaluate(report);

  process.stdout.write(
    `Pilot reliability gate result: ${result.decision}\n` +
      `- report: ${reportPath}\n` +
      `- failures: ${result.failures.length}\n` +
      `- warnings: ${result.warnings.length}\n`
  );
  for (const f of result.failures) process.stdout.write(`  FAIL: ${f}\n`);
  for (const w of result.warnings) process.stdout.write(`  WARN: ${w}\n`);

  if (result.decision === "no_go") process.exit(2);
}

if (require.main === module) {
  main();
}

