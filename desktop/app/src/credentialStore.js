const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");
const { spawnSync } = require("child_process");

let stateDir = null;
let fallbackFile = null;
let saltFile = null;
const serviceName = "nir-desktop";
const SECRET_NAME_PATTERN = /^[a-z0-9_]+\.[a-z0-9_.-]+$/i;

function initCredentialStore(baseStateDir) {
  stateDir = baseStateDir;
  const secDir = path.join(stateDir, "secrets");
  fs.mkdirSync(secDir, { recursive: true });
  fallbackFile = path.join(secDir, "vault.enc.json");
  saltFile = path.join(secDir, ".vault_salt");
}

function requireInit() {
  if (!stateDir) {
    throw new Error("credentialStore.initCredentialStore must be called before use");
  }
}

function validateSecretName(name) {
  const normalized = String(name || "").trim();
  if (!normalized) {
    return { ok: false, error: "Secret key is required." };
  }
  if (!SECRET_NAME_PATTERN.test(normalized)) {
    return {
      ok: false,
      error: "Secret key must be namespaced (example: pennsieve.api_key).",
    };
  }
  return { ok: true, name: normalized };
}

function cmdExists(cmd, args = ["--help"]) {
  const res = spawnSync(cmd, args, { encoding: "utf8", timeout: 4000 });
  return !res.error;
}

function detectBackend() {
  if (process.platform === "darwin" && cmdExists("security", ["-h"])) {
    return "macos-keychain";
  }
  if (process.platform === "linux" && cmdExists("secret-tool", ["--help"])) {
    return "linux-secret-tool";
  }
  // Windows direct retrieval via cmdkey is not straightforward for this use.
  // Use encrypted fallback there for phase 3 scaffold.
  return "encrypted-fallback";
}

function ensureSalt() {
  if (!fs.existsSync(saltFile)) {
    fs.writeFileSync(saltFile, crypto.randomBytes(16));
  }
  return fs.readFileSync(saltFile);
}

function fallbackKey() {
  const salt = ensureSalt();
  const material = `${os.userInfo().username}:${os.hostname()}:${serviceName}`;
  return crypto.scryptSync(material, salt, 32);
}

function readFallbackStore() {
  if (!fs.existsSync(fallbackFile)) return {};
  try {
    return JSON.parse(fs.readFileSync(fallbackFile, "utf8"));
  } catch (_e) {
    return {};
  }
}

function writeFallbackStore(data) {
  fs.writeFileSync(fallbackFile, JSON.stringify(data, null, 2), "utf8");
}

function encryptValue(value) {
  const key = fallbackKey();
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", key, iv);
  const enc = Buffer.concat([cipher.update(value, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();
  return {
    iv: iv.toString("base64"),
    tag: tag.toString("base64"),
    data: enc.toString("base64"),
  };
}

function decryptValue(obj) {
  const key = fallbackKey();
  const decipher = crypto.createDecipheriv(
    "aes-256-gcm",
    key,
    Buffer.from(obj.iv, "base64")
  );
  decipher.setAuthTag(Buffer.from(obj.tag, "base64"));
  const out = Buffer.concat([
    decipher.update(Buffer.from(obj.data, "base64")),
    decipher.final(),
  ]);
  return out.toString("utf8");
}

function setSecretFallback(name, value) {
  const store = readFallbackStore();
  store[name] = encryptValue(value);
  writeFallbackStore(store);
  return { ok: true, backend: "encrypted-fallback" };
}

function getSecretFallback(name) {
  const store = readFallbackStore();
  if (!store[name]) return { ok: true, value: null, backend: "encrypted-fallback" };
  try {
    return { ok: true, value: decryptValue(store[name]), backend: "encrypted-fallback" };
  } catch (e) {
    return { ok: false, error: e.message, backend: "encrypted-fallback" };
  }
}

function deleteSecretFallback(name) {
  const store = readFallbackStore();
  delete store[name];
  writeFallbackStore(store);
  return { ok: true, backend: "encrypted-fallback" };
}

function setSecretMac(name, value) {
  const res = spawnSync(
    "security",
    ["add-generic-password", "-a", name, "-s", serviceName, "-w", value, "-U"],
    { encoding: "utf8", timeout: 5000 }
  );
  return {
    ok: !res.error && res.status === 0,
    backend: "macos-keychain",
    error: res.error ? res.error.message : (res.stderr || "").trim(),
  };
}

function getSecretMac(name) {
  const res = spawnSync(
    "security",
    ["find-generic-password", "-a", name, "-s", serviceName, "-w"],
    { encoding: "utf8", timeout: 5000 }
  );
  if (res.error || res.status !== 0) {
    return { ok: true, value: null, backend: "macos-keychain" };
  }
  return { ok: true, value: (res.stdout || "").trim(), backend: "macos-keychain" };
}

function deleteSecretMac(name) {
  const res = spawnSync(
    "security",
    ["delete-generic-password", "-a", name, "-s", serviceName],
    { encoding: "utf8", timeout: 5000 }
  );
  return {
    ok: !res.error && (res.status === 0 || res.status === 44),
    backend: "macos-keychain",
    error: res.error ? res.error.message : "",
  };
}

function setSecretLinux(name, value) {
  const res = spawnSync(
    "secret-tool",
    ["store", "--label=NIR Desktop Secret", "service", serviceName, "account", name],
    { encoding: "utf8", timeout: 5000, input: value }
  );
  return {
    ok: !res.error && res.status === 0,
    backend: "linux-secret-tool",
    error: res.error ? res.error.message : (res.stderr || "").trim(),
  };
}

function getSecretLinux(name) {
  const res = spawnSync(
    "secret-tool",
    ["lookup", "service", serviceName, "account", name],
    { encoding: "utf8", timeout: 5000 }
  );
  if (res.error || res.status !== 0) {
    return { ok: true, value: null, backend: "linux-secret-tool" };
  }
  return { ok: true, value: (res.stdout || "").trim(), backend: "linux-secret-tool" };
}

function deleteSecretLinux(name) {
  const res = spawnSync(
    "secret-tool",
    ["clear", "service", serviceName, "account", name],
    { encoding: "utf8", timeout: 5000 }
  );
  return {
    ok: !res.error && res.status === 0,
    backend: "linux-secret-tool",
    error: res.error ? res.error.message : (res.stderr || "").trim(),
  };
}

function setSecret(name, value) {
  requireInit();
  const v = validateSecretName(name);
  if (!v.ok) return { ok: false, backend: "validation", error: v.error };
  const backend = detectBackend();
  if (backend === "macos-keychain") return setSecretMac(v.name, value);
  if (backend === "linux-secret-tool") return setSecretLinux(v.name, value);
  return setSecretFallback(v.name, value);
}

function getSecret(name) {
  requireInit();
  const v = validateSecretName(name);
  if (!v.ok) return { ok: false, backend: "validation", error: v.error };
  const backend = detectBackend();
  if (backend === "macos-keychain") return getSecretMac(v.name);
  if (backend === "linux-secret-tool") return getSecretLinux(v.name);
  return getSecretFallback(v.name);
}

function deleteSecret(name) {
  requireInit();
  const v = validateSecretName(name);
  if (!v.ok) return { ok: false, backend: "validation", error: v.error };
  const backend = detectBackend();
  if (backend === "macos-keychain") return deleteSecretMac(v.name);
  if (backend === "linux-secret-tool") return deleteSecretLinux(v.name);
  return deleteSecretFallback(v.name);
}

function getStoreStatus() {
  requireInit();
  return {
    backend: detectBackend(),
    serviceName,
    fallbackFile,
  };
}

module.exports = {
  initCredentialStore,
  setSecret,
  getSecret,
  deleteSecret,
  getStoreStatus,
};
