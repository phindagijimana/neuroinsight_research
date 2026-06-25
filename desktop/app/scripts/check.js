#!/usr/bin/env node
/**
 * Cross-platform syntax check for the desktop main/renderer JS.
 * Replaces a bash `for` loop that failed on Windows CI (cmd shell).
 */
const { execFileSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
let failed = false;

for (const dir of ["src", "renderer"]) {
  const abs = path.join(root, dir);
  if (!fs.existsSync(abs)) continue;
  for (const file of fs.readdirSync(abs)) {
    if (!file.endsWith(".js")) continue;
    const p = path.join(abs, file);
    try {
      execFileSync(process.execPath, ["--check", p], { stdio: "pipe" });
    } catch (e) {
      failed = true;
      console.error(`✖ syntax error: ${dir}/${file}`);
      process.stderr.write((e.stderr || e.stdout || Buffer.from(String(e.message))).toString());
    }
  }
}

if (failed) process.exit(1);
console.log("✓ desktop sources OK");
