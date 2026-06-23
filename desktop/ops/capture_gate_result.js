#!/usr/bin/env node
"use strict";

/**
 * capture_gate_result.js — run the pilot reliability gate and persist its
 * decision for the go-live record (Phase 7 exit criterion: "automated gate
 * result reviewed and captured in go-live recommendation").
 *
 * Usage:
 *   node capture_gate_result.js [reportPath] [outDir]
 *
 * Reuses evaluate() from evaluate_pilot_gate.js (single source of truth) and
 * writes, into outDir (default desktop/ops/):
 *   - pilot_gate_result.json   machine-readable {decision, failures, warnings, ...}
 *   - GO_LIVE_DECISION.md      human-readable stamp to paste into the go-live doc
 *
 * Exits non-zero on `no_go` so it doubles as a CI gate.
 */
const fs = require("fs");
const path = require("path");
const { evaluate, THRESHOLDS } = require("./evaluate_pilot_gate.js");

function main() {
  const repoRoot = path.resolve(__dirname, "..", "..");
  const opsDir = path.join(repoRoot, "desktop", "ops");
  const reportPath = process.argv[2] ? path.resolve(process.argv[2]) : path.join(opsDir, "pilot_reliability_report.json");
  const outDir = process.argv[3] ? path.resolve(process.argv[3]) : opsDir;

  if (!fs.existsSync(reportPath)) {
    throw new Error(`Report not found: ${reportPath}`);
  }
  const report = JSON.parse(fs.readFileSync(reportPath, "utf8"));
  const result = evaluate(report);
  // Timestamp comes from the environment to keep the script deterministic for tests.
  const evaluatedAt = process.env.NIR_GATE_TIMESTAMP || "";

  const resultObj = {
    decision: result.decision,
    failures: result.failures,
    warnings: result.warnings,
    thresholds: THRESHOLDS,
    build_tag: report.build_tag || null,
    pilot_window: report.pilot_window || null,
    report: path.relative(repoRoot, reportPath),
    evaluated_at: evaluatedAt,
  };

  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, "pilot_gate_result.json"), JSON.stringify(resultObj, null, 2) + "\n");

  const box = { go: "✅ GO", conditional_go: "⚠️ CONDITIONAL GO", no_go: "⛔ NO GO" }[result.decision] || result.decision;
  const md = `# Pilot Reliability Gate Decision

- **Decision:** ${box}
- **Build tag:** ${report.build_tag || "(unset)"}
- **Pilot window:** ${report.pilot_window || "(unset)"}
- **Evaluated at:** ${evaluatedAt || "(set NIR_GATE_TIMESTAMP)"}
- **Report:** \`${resultObj.report}\`

## Thresholds
core flow ≥ ${THRESHOLDS.coreFlowCompletionRate}% · parity ≥ ${THRESHOLDS.parityCompletionRate}% · crash-free ≥ ${THRESHOLDS.crashFreeLaunchRate}% · SLA ≥ ${THRESHOLDS.slaAdherenceRate}% · P0/P1 = 0

## Failures (block GA)
${result.failures.length ? result.failures.map((f) => `- ${f}`).join("\n") : "- none"}

## Warnings
${result.warnings.length ? result.warnings.map((w) => `- ${w}`).join("\n") : "- none"}

> Paste this into \`GO_LIVE_RECOMMENDATION_TEMPLATE.md\` under "Reliability Evidence".
`;
  fs.writeFileSync(path.join(outDir, "GO_LIVE_DECISION.md"), md);

  process.stdout.write(`Gate decision: ${result.decision}\n- pilot_gate_result.json + GO_LIVE_DECISION.md written to ${outDir}\n`);
  if (result.decision === "no_go") process.exit(2);
}

if (require.main === module) {
  main();
}

module.exports = { main };
