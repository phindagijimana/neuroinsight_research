/**
 * Host SSH broker.
 *
 * The engine runs inside the container, which has no ssh-agent, no access to the
 * user's unlocked keys, no ~/.ssh/config, no Kerberos ticket and no way to answer
 * a Duo prompt. The host (where Electron runs) has all of that and already
 * connects to every cluster fine. So instead of doing SSH from the container, the
 * container asks THIS host-side broker to run commands / move files over an OS
 * `ssh` connection that is multiplexed with ControlMaster — one auth, reused for
 * everything. The broker inherits whatever auth the host uses (agent key for
 * URMC-SH, password+Duo for CIRC via interactive, Kerberos, ProxyJump, config
 * aliases) with no per-cluster code.
 *
 * Transport: a tiny HTTP server bound so the container can reach it via
 * host.docker.internal, protected by a per-launch bearer token. Container
 * `/data/...` paths are translated to the host bind-mount path for scp.
 *
 * CLI self-test (runs on the host, uses your real agent):
 *   node sshBroker.js selftest <user> <host> [port]
 */
const http = require("http");
const crypto = require("crypto");
const { spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

function socketDir() {
  // Prefer a short, private path (ssh control sockets have a ~104 char limit).
  const d = path.join(os.tmpdir(), "nir-ssh");
  try {
    fs.mkdirSync(d, { recursive: true, mode: 0o700 });
  } catch (_e) {
    /* best effort */
  }
  return d;
}

class SshBroker {
  /**
   * @param {object} opts
   * @param {string} [opts.hostDataDir]  host path bind-mounted to the container's /data
   * @param {string} [opts.containerDataDir] mount point inside the container (default /data)
   */
  constructor(opts = {}) {
    this.token = crypto.randomBytes(32).toString("hex");
    this.hostDataDir = opts.hostDataDir || null;
    this.containerDataDir = opts.containerDataDir || "/data";
    this.conns = new Map(); // key -> { cp, host, user, port }
    this.server = null;
    this.port = null;
  }

  _key(host, user, port) {
    return `${user}@${host}:${port}`;
  }

  _controlPath(key) {
    const h = crypto.createHash("sha1").update(key).digest("hex").slice(0, 16);
    return path.join(socketDir(), `cm-${h}`);
  }

  _baseOpts(cp) {
    return [
      "-o", `ControlPath=${cp}`,
      "-o", "StrictHostKeyChecking=accept-new",
      "-o", "BatchMode=yes", // Phase 1: non-interactive (agent key / Kerberos)
    ];
  }

  // Translate a container /data/... path to the host bind-mount path so scp
  // (running on the host) can read/write the same file the engine sees.
  toHostPath(p) {
    if (this.hostDataDir && p && p.startsWith(this.containerDataDir)) {
      return path.join(this.hostDataDir, p.slice(this.containerDataDir.length));
    }
    return p;
  }

  isAlive(host, user, port = 22) {
    const cp = this._controlPath(this._key(host, user, port));
    const r = spawnSync(
      "ssh",
      [...this._baseOpts(cp), "-p", String(port), `${user}@${host}`, "-O", "check"],
      { timeout: 8000 }
    );
    return r.status === 0;
  }

  connect({ host, user, port = 22, persist = "8h" }) {
    const key = this._key(host, user, port);
    const cp = this._controlPath(key);
    if (this.isAlive(host, user, port)) {
      this.conns.set(key, { cp, host, user, port });
      return { connected: true, multiplexed: true, reused: true };
    }
    const args = [
      "-fNM",
      "-o", `ControlPersist=${persist}`,
      "-o", "ConnectTimeout=15",
      ...this._baseOpts(cp),
      "-p", String(port),
      `${user}@${host}`,
    ];
    const r = spawnSync("ssh", args, { timeout: 35000 });
    if (r.status !== 0) {
      const err = (r.stderr || "").toString();
      // Cluster wants interactive auth (e.g. password + Duo). Phase 2 handles
      // this by dropping BatchMode and relaying the prompt to the UI.
      const needsInteractive = /password|keyboard-interactive|Permission denied/i.test(err);
      return { connected: false, needsInteractive, error: err.slice(0, 400) };
    }
    this.conns.set(key, { cp, host, user, port });
    return { connected: true, multiplexed: true };
  }

  exec({ host, user, port = 22, command, timeout = 120 }) {
    const key = this._key(host, user, port);
    const c = this.conns.get(key) || { cp: this._controlPath(key) };
    const r = spawnSync(
      "ssh",
      [...this._baseOpts(c.cp), "-p", String(port), `${user}@${host}`, command],
      { timeout: timeout * 1000, maxBuffer: 64 * 1024 * 1024 }
    );
    return {
      rc: r.status == null ? 255 : r.status,
      stdout: (r.stdout || "").toString(),
      stderr: (r.stderr || "").toString(),
    };
  }

  put({ host, user, port = 22, localPath, remotePath }) {
    const key = this._key(host, user, port);
    const c = this.conns.get(key) || { cp: this._controlPath(key) };
    const src = this.toHostPath(localPath);
    const r = spawnSync(
      "scp",
      [...this._baseOpts(c.cp), "-p", "-P", String(port), src, `${user}@${host}:${remotePath}`],
      { timeout: 1800000, maxBuffer: 16 * 1024 * 1024 }
    );
    return { ok: r.status === 0, error: (r.stderr || "").toString().slice(0, 400) };
  }

  get({ host, user, port = 22, remotePath, localPath }) {
    const key = this._key(host, user, port);
    const c = this.conns.get(key) || { cp: this._controlPath(key) };
    const dst = this.toHostPath(localPath);
    try {
      fs.mkdirSync(path.dirname(dst), { recursive: true });
    } catch (_e) {
      /* best effort */
    }
    const r = spawnSync(
      "scp",
      [...this._baseOpts(c.cp), "-p", "-P", String(port), `${user}@${host}:${remotePath}`, dst],
      { timeout: 1800000, maxBuffer: 16 * 1024 * 1024 }
    );
    return { ok: r.status === 0, error: (r.stderr || "").toString().slice(0, 400) };
  }

  disconnect({ host, user, port = 22 }) {
    const key = this._key(host, user, port);
    const cp = this._controlPath(key);
    spawnSync("ssh", [...this._baseOpts(cp), "-p", String(port), `${user}@${host}`, "-O", "exit"], {
      timeout: 8000,
    });
    this.conns.delete(key);
    return { connected: false };
  }

  // ---- HTTP transport ------------------------------------------------------
  _route(name, body) {
    switch (name) {
      case "connect": return this.connect(body);
      case "exec": return this.exec(body);
      case "put": return this.put(body);
      case "get": return this.get(body);
      case "check": return { alive: this.isAlive(body.host, body.user, body.port || 22) };
      case "disconnect": return this.disconnect(body);
      default: return { error: `unknown op: ${name}` };
    }
  }

  listen(port = 0, hostBind = "0.0.0.0") {
    return new Promise((resolve) => {
      this.server = http.createServer((req, res) => {
        const auth = req.headers["authorization"] || "";
        if (auth !== `Bearer ${this.token}`) {
          res.writeHead(401).end('{"error":"unauthorized"}');
          return;
        }
        let raw = "";
        req.on("data", (d) => { raw += d; if (raw.length > 256 * 1024 * 1024) req.destroy(); });
        req.on("end", () => {
          let out;
          try {
            const body = raw ? JSON.parse(raw) : {};
            const op = (req.url || "/").replace(/^\//, "");
            out = this._route(op, body);
          } catch (e) {
            res.writeHead(400).end(JSON.stringify({ error: String(e).slice(0, 200) }));
            return;
          }
          res.writeHead(200, { "content-type": "application/json" }).end(JSON.stringify(out));
        });
      });
      // Bind on the docker-reachable interface so the container can call us via
      // host.docker.internal. Token-protected; bound only for the app session.
      this.server.listen(port, hostBind, () => {
        this.port = this.server.address().port;
        resolve({ port: this.port, token: this.token });
      });
    });
  }

  close() {
    if (this.server) this.server.close();
    for (const { host, user, port } of this.conns.values()) {
      try { this.disconnect({ host, user, port }); } catch (_e) { /* best effort */ }
    }
  }
}

module.exports = { SshBroker };

// ---- self-test CLI (host-side, real agent) ---------------------------------
if (require.main === module) {
  const [cmd, user, host, port] = process.argv.slice(2);
  if (cmd !== "selftest" || !user || !host) {
    process.stderr.write("usage: node sshBroker.js selftest <user> <host> [port]\n");
    process.exit(2);
  }
  const b = new SshBroker({});
  const p = Number(port) || 22;
  process.stdout.write(`connect ${user}@${host}:${p} ...\n`);
  const c = b.connect({ host, user, port: p });
  process.stdout.write("connect -> " + JSON.stringify(c) + "\n");
  if (!c.connected) process.exit(1);
  const t0 = Date.now();
  const e = b.exec({ host, user, port: p, command: "hostname; echo '---'; which sbatch; sinfo -s 2>&1 | head -4" });
  process.stdout.write(`exec (${Date.now() - t0}ms, multiplexed) rc=${e.rc}\n${e.stdout}${e.stderr}\n`);
  const t1 = Date.now();
  const e2 = b.exec({ host, user, port: p, command: "echo reuse-ok" });
  process.stdout.write(`second exec (${Date.now() - t1}ms — should be fast, reusing master): ${e2.stdout.trim()}\n`);
  b.disconnect({ host, user, port: p });
  process.stdout.write("disconnected.\n");
}
