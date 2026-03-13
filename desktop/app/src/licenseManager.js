const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

let stateDir = null;
let licenseFilePath = null;
let licenseStatePath = null;
const MAX_LICENSE_TEXT_BYTES = 256 * 1024;

function initLicenseManager(baseStateDir) {
  stateDir = baseStateDir;
  const licenseDir = path.join(stateDir, "license");
  fs.mkdirSync(licenseDir, { recursive: true });
  licenseFilePath = path.join(licenseDir, "current_license.json");
  licenseStatePath = path.join(licenseDir, "license_state.json");
}

function requireInit() {
  if (!stateDir) {
    throw new Error("licenseManager.initLicenseManager must be called before use");
  }
}

function readJson(filePath) {
  try {
    if (!fs.existsSync(filePath)) return null;
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch (_e) {
    return null;
  }
}

function writeJson(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), "utf8");
}

function getPublicKeyCandidates() {
  const envPem = process.env.NIR_DESKTOP_LICENSE_PUBLIC_KEY;
  const candidates = [];
  if (envPem && envPem.trim()) {
    candidates.push(envPem.replace(/\\n/g, "\n"));
  }
  candidates.push(path.resolve(__dirname, "..", "config", "license_public_key.pem"));
  candidates.push(path.join(stateDir, "license_public_key.pem"));
  return candidates;
}

function loadPublicKey() {
  for (const c of getPublicKeyCandidates()) {
    if (!c) continue;
    if (c.includes("BEGIN PUBLIC KEY")) return c;
    try {
      if (fs.existsSync(c)) {
        const pem = fs.readFileSync(c, "utf8");
        if (pem.includes("BEGIN PUBLIC KEY")) return pem;
      }
    } catch (_e) {
      // continue
    }
  }
  return null;
}

function normalizeLicense(raw) {
  if (!raw || typeof raw !== "object") return null;
  if (!raw.payload || !raw.signature) return null;
  if (typeof raw.payload !== "object") return null;
  if (typeof raw.signature !== "string") return null;
  return { payload: raw.payload, signature: raw.signature };
}

function validatePayloadSchema(payload) {
  const requiredStringFields = [
    "license_id",
    "organization_id",
    "plan_tier",
    "issued_at",
    "expires_at",
  ];
  for (const key of requiredStringFields) {
    if (typeof payload[key] !== "string" || !payload[key].trim()) {
      return `License payload missing required field: ${key}`;
    }
  }
  if (!Array.isArray(payload.features)) {
    return "License payload field `features` must be an array.";
  }
  const hasBadFeature = payload.features.some(
    (f) => typeof f !== "string" || !f.trim()
  );
  if (hasBadFeature) {
    return "License payload contains invalid feature entries.";
  }
  const issued = Date.parse(payload.issued_at);
  const expires = Date.parse(payload.expires_at);
  if (!Number.isFinite(issued)) {
    return "License payload has invalid issued_at timestamp.";
  }
  if (!Number.isFinite(expires)) {
    return "License payload has invalid expires_at timestamp.";
  }
  if (expires <= issued) {
    return "License payload has expires_at earlier than issued_at.";
  }
  if (
    Object.prototype.hasOwnProperty.call(payload, "offline_grace_days") &&
    (!Number.isInteger(payload.offline_grace_days) || payload.offline_grace_days < 0)
  ) {
    return "License payload field offline_grace_days must be a non-negative integer.";
  }
  if (
    Object.prototype.hasOwnProperty.call(payload, "seat_limit") &&
    (!Number.isInteger(payload.seat_limit) || payload.seat_limit < 1)
  ) {
    return "License payload field seat_limit must be an integer >= 1.";
  }
  return null;
}

function verifySignature(payload, signatureB64, publicKeyPem) {
  try {
    const data = Buffer.from(JSON.stringify(payload), "utf8");
    const sig = Buffer.from(signatureB64, "base64");
    return crypto.verify(null, data, publicKeyPem, sig);
  } catch (_e) {
    return false;
  }
}

function computeLicenseStatus(licenseObj) {
  const now = Date.now();
  const state = readJson(licenseStatePath) || {};
  const publicKey = loadPublicKey();
  if (!licenseObj) {
    return {
      present: false,
      valid: false,
      reason: "No license file imported.",
      payload: null,
      expiresAt: null,
      daysRemaining: null,
      keyConfigured: !!publicKey,
      lastValidatedAt: state.lastValidatedAt || null,
    };
  }

  const { payload, signature } = licenseObj;
  const schemaErr = validatePayloadSchema(payload);
  if (schemaErr) {
    return {
      present: true,
      valid: false,
      reason: schemaErr,
      payload,
      expiresAt: payload.expires_at || null,
      daysRemaining: null,
      keyConfigured: !!publicKey,
      lastValidatedAt: state.lastValidatedAt || null,
    };
  }
  if (!publicKey) {
    return {
      present: true,
      valid: false,
      reason: "No license public key configured.",
      payload,
      expiresAt: null,
      daysRemaining: null,
      keyConfigured: false,
      lastValidatedAt: state.lastValidatedAt || null,
    };
  }
  const sigOk = verifySignature(payload, signature, publicKey);
  if (!sigOk) {
    return {
      present: true,
      valid: false,
      reason: "License signature verification failed.",
      payload,
      expiresAt: payload.expires_at || null,
      daysRemaining: null,
      keyConfigured: true,
      lastValidatedAt: state.lastValidatedAt || null,
    };
  }

  const exp = payload.expires_at ? Date.parse(payload.expires_at) : NaN;
  if (!Number.isFinite(exp)) {
    return {
      present: true,
      valid: false,
      reason: "License missing valid expires_at.",
      payload,
      expiresAt: null,
      daysRemaining: null,
      keyConfigured: true,
      lastValidatedAt: state.lastValidatedAt || null,
    };
  }

  const msRemaining = exp - now;
  const daysRemaining = Math.floor(msRemaining / (24 * 60 * 60 * 1000));
  if (msRemaining < 0) {
    return {
      present: true,
      valid: false,
      reason: "License expired.",
      payload,
      expiresAt: payload.expires_at,
      daysRemaining,
      keyConfigured: true,
      lastValidatedAt: state.lastValidatedAt || null,
    };
  }

  const status = {
    present: true,
    valid: true,
    reason: null,
    payload,
    expiresAt: payload.expires_at,
    daysRemaining,
    planTier: payload.plan_tier,
    organizationId: payload.organization_id,
    featureCount: Array.isArray(payload.features) ? payload.features.length : 0,
    keyConfigured: true,
    lastValidatedAt: new Date().toISOString(),
  };
  writeJson(licenseStatePath, { lastValidatedAt: status.lastValidatedAt });
  return status;
}

function importLicenseObject(obj) {
  requireInit();
  const normalized = normalizeLicense(obj);
  if (!normalized) {
    return { ok: false, error: "Invalid license format. Expected { payload, signature }." };
  }
  const status = computeLicenseStatus(normalized);
  if (!status.valid) {
    return { ok: false, error: status.reason || "License is not valid.", status };
  }
  writeJson(licenseFilePath, normalized);
  return { ok: true, status };
}

function importLicenseFromText(text) {
  requireInit();
  try {
    if (Buffer.byteLength(String(text || ""), "utf8") > MAX_LICENSE_TEXT_BYTES) {
      return {
        ok: false,
        error: `License text is too large (>${MAX_LICENSE_TEXT_BYTES} bytes).`,
      };
    }
    const obj = JSON.parse(text);
    return importLicenseObject(obj);
  } catch (e) {
    return { ok: false, error: `Could not parse license JSON: ${e.message}` };
  }
}

function importLicenseFromFile(filePath) {
  requireInit();
  try {
    const text = fs.readFileSync(filePath, "utf8");
    return importLicenseFromText(text);
  } catch (e) {
    return { ok: false, error: `Could not read license file: ${e.message}` };
  }
}

function getLicenseStatus() {
  requireInit();
  const obj = readJson(licenseFilePath);
  const normalized = normalizeLicense(obj);
  return computeLicenseStatus(normalized);
}

function getLicensePaths() {
  requireInit();
  return {
    licenseFilePath,
    licenseStatePath,
  };
}

module.exports = {
  initLicenseManager,
  getLicenseStatus,
  importLicenseFromText,
  importLicenseFromFile,
  getLicensePaths,
};
