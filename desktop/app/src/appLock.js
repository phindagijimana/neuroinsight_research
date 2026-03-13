const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

let lockFilePath = null;
let sessionUnlocked = false;

const PIN_MIN_LENGTH = 6;

function initAppLock(baseStateDir) {
  const secDir = path.join(baseStateDir, "security");
  fs.mkdirSync(secDir, { recursive: true });
  lockFilePath = path.join(secDir, "app_lock.json");
  const state = readState();
  sessionUnlocked = !state.enabled;
}

function requireInit() {
  if (!lockFilePath) {
    throw new Error("appLock.initAppLock must be called before use");
  }
}

function readState() {
  requireInit();
  try {
    if (!fs.existsSync(lockFilePath)) {
      return {
        enabled: false,
        pinHash: null,
        salt: null,
        updatedAt: null,
      };
    }
    const parsed = JSON.parse(fs.readFileSync(lockFilePath, "utf8"));
    return {
      enabled: Boolean(parsed.enabled),
      pinHash: typeof parsed.pinHash === "string" ? parsed.pinHash : null,
      salt: typeof parsed.salt === "string" ? parsed.salt : null,
      updatedAt: parsed.updatedAt || null,
    };
  } catch (_e) {
    return {
      enabled: false,
      pinHash: null,
      salt: null,
      updatedAt: null,
    };
  }
}

function writeState(next) {
  requireInit();
  const out = {
    enabled: Boolean(next.enabled),
    pinHash: next.pinHash || null,
    salt: next.salt || null,
    updatedAt: new Date().toISOString(),
  };
  fs.writeFileSync(lockFilePath, JSON.stringify(out, null, 2), "utf8");
  return out;
}

function validatePin(pin) {
  const p = String(pin || "").trim();
  if (!p) return { ok: false, error: "PIN is required." };
  if (p.length < PIN_MIN_LENGTH) {
    return { ok: false, error: `PIN must be at least ${PIN_MIN_LENGTH} characters.` };
  }
  return { ok: true, pin: p };
}

function deriveHash(pin, saltB64) {
  const salt = Buffer.from(saltB64, "base64");
  return crypto.scryptSync(pin, salt, 32).toString("base64");
}

function createPinMaterial(pin) {
  const salt = crypto.randomBytes(16).toString("base64");
  const pinHash = deriveHash(pin, salt);
  return { salt, pinHash };
}

function getStatus() {
  const st = readState();
  return {
    enabled: st.enabled,
    unlocked: st.enabled ? sessionUnlocked : true,
    updatedAt: st.updatedAt,
    lockFilePath,
  };
}

function verifyPin(pin) {
  const st = readState();
  if (!st.enabled || !st.pinHash || !st.salt) {
    return { ok: false, error: "App lock is not enabled." };
  }
  const v = validatePin(pin);
  if (!v.ok) return { ok: false, error: v.error };
  const candidate = deriveHash(v.pin, st.salt);
  const ok = crypto.timingSafeEqual(Buffer.from(candidate), Buffer.from(st.pinHash));
  return ok ? { ok: true } : { ok: false, error: "Invalid PIN." };
}

function enable(pin) {
  const v = validatePin(pin);
  if (!v.ok) return { ok: false, error: v.error };
  const material = createPinMaterial(v.pin);
  writeState({
    enabled: true,
    pinHash: material.pinHash,
    salt: material.salt,
  });
  sessionUnlocked = true;
  return { ok: true, status: getStatus() };
}

function disable(pin) {
  const st = readState();
  if (!st.enabled) return { ok: true, status: getStatus() };
  const verified = verifyPin(pin);
  if (!verified.ok) return verified;
  writeState({
    enabled: false,
    pinHash: null,
    salt: null,
  });
  sessionUnlocked = true;
  return { ok: true, status: getStatus() };
}

function unlock(pin) {
  const st = readState();
  if (!st.enabled) {
    sessionUnlocked = true;
    return { ok: true, status: getStatus() };
  }
  const verified = verifyPin(pin);
  if (!verified.ok) return verified;
  sessionUnlocked = true;
  return { ok: true, status: getStatus() };
}

function lockNow() {
  const st = readState();
  if (!st.enabled) return { ok: true, status: getStatus() };
  sessionUnlocked = false;
  return { ok: true, status: getStatus() };
}

function isUnlockedForSensitiveActions() {
  const st = readState();
  if (!st.enabled) return true;
  return sessionUnlocked;
}

module.exports = {
  initAppLock,
  getStatus,
  enable,
  disable,
  unlock,
  lockNow,
  isUnlockedForSensitiveActions,
};
