# Design: In-App Interactive SSH Auth (MFA-capable HPC connect)

**Status:** Proposed (design only — not implemented)
**Problem:** Many HPC clusters require **password + Duo/MFA** (or Kerberos) on SSH.
The current connector (`backend/core/ssh_manager.py`, paramiko) only does
**key/agent** auth, so it cannot drive an interactive MFA prompt. And because the
backend runs **inside the all-in-one container**, the usual "authenticate once in
your terminal, reuse the ControlMaster socket" trick fails — a control socket
created on the macOS host can't be reached across the Docker Desktop VM boundary.

**Goal:** Let a user connect to an MFA HPC by authenticating **once, through the
app**. After that, every job submission / browse / transfer reuses the
authenticated session with **no re-auth**, until it expires.

---

## Key idea

The **engine owns the SSH master connection**, with the ControlMaster control
socket living **entirely inside the container** (no cross-VM socket sharing). The
interactive auth (password, Duo push/passcode, Kerberos, host-key prompts) is
relayed between the engine's `ssh` process — run under a **PTY** — and the user,
over a **WebSocket**. Once the master is up, exec/SFTP attach to it via
`-o ControlPath=<socket>` and never re-authenticate.

```
Browser (auth modal) ⇄ WS /api/hpc/auth ⇄ Engine PTY-wrapped `ssh -M`
                                              │ writes control socket (in-container)
                          exec/sftp ── ssh -S <socket> … ──┘  (no auth, reused)
```

This works because the socket and the `ssh` master both live on the same side
(the container); MFA happens exactly once, when the master opens.

---

## Components

### 1. Engine: `SystemSSHSession` (new)
Wraps the OS `ssh` client (already in the image: `openssh-client`) instead of
paramiko. Honors the mounted `~/.ssh/config` (aliases, `ProxyJump`, `IdentityFile`).

- **Open master** (under a PTY, e.g. `ptyprocess`/`pexpect`):
  ```
  ssh -tt -o ControlMaster=yes -o ControlPath=$SOCK \
      -o ControlPersist=8h -o ServerAliveInterval=30 \
      -o StrictHostKeyChecking=accept-new \
      <user>@<host> 'echo NIR_MASTER_READY; exec sleep infinity'
  ```
  - `$SOCK` = `/run/nir/ssh/cm-<host>-<port>` (tmpfs, mode 600, owned by `neuroinsight`).
  - Stream PTY output to the client; detect prompts and the `NIR_MASTER_READY`
    success sentinel; detect failure ("Permission denied", "Too many auth failures").
- **Exec:** `ssh -o ControlPath=$SOCK <user>@<host> <cmd>` (no auth; instant).
- **SFTP/browse/transfer:** `sftp -o ControlPath=$SOCK …` (openssh sftp supports
  ControlPath) — replaces the paramiko SFTP browse.
- **Health:** `ssh -O check -S $SOCK …`; **close:** `ssh -O exit -S $SOCK …`.
- Keep the master process supervised so the socket persists; on death, mark
  disconnected so the next op triggers re-auth.

One master per `(host, port, user)`, tracked in a registry.

### 2. Transport: WebSocket auth relay (new route)
`WS /api/hpc/auth` (localhost-only; the app is local). Bidirectional so prompts
and responses interleave naturally.

| Direction | Message |
|---|---|
| client→server | `{"type":"start","host","username","port"}` |
| server→client | `{"type":"prompt","text":"Password:","secret":true}` |
| server→client | `{"type":"info","text":"Pushed a login request to your device…"}` |
| client→server | `{"type":"input","data":"<password / passcode / 1>"}` |
| server→client | `{"type":"status","state":"connected"\|"failed","message":…}` |

- The PTY's raw prompts are forwarded verbatim (`prompt`/`info`), so **any**
  scheme works generically — password, Duo "Passcode or option (1-3)", push-only
  (no input; just wait for the sentinel), Kerberos, sequential **ProxyJump** MFA.
- `secret:true` tells the UI to mask input.

### 3. Frontend: "Connect (interactive)" modal
A small terminal-style panel: shows server `info`/`prompt` lines, with a single
input box (masked when `secret`). On `status: connected` → close, mark the HPC
backend connected (reuses the existing connected-state UX). On `failed` → show
the message + Retry. Replaces nothing; it's an additional connect path chosen
when the user picks "HPC (uses MFA)".

### 4. Reuse by the execution backends
`remote_docker` / `slurm` execution currently call `ssh_manager`. Point them at
the live `SystemSSHSession` (by ControlPath) for all remote commands and file
transfer. Submission, `squeue`/`sinfo`, staging, and result pull all reuse the
one authenticated master — **no MFA per job**.

---

## Security
- **Secrets are transient:** passwords/passcodes are written straight to the ssh
  PTY and never persisted or logged. The WS carries them only in-memory, on
  loopback.
- **Socket hardening:** control socket in a root-only-traversable dir, mode 600,
  owned by `neuroinsight`; one per host.
- **Session lifetime:** `ControlPersist=8h` (configurable) bounds exposure; after
  expiry or container restart, the user re-authenticates. `ssh -O exit` on
  explicit disconnect/logout.
- **Host keys:** `accept-new` (TOFU) using the mounted `known_hosts`; a host-key
  change surfaces as a prompt rather than silent trust.
- **Audit:** reuse `backend.core.audit` to log connect/disconnect (host, user,
  time) — never the secret.
- **Loopback + token:** the WS requires the same-origin app; add a short-lived
  per-attempt token to prevent other local processes from driving it.

## Phasing (each independently testable)
1. **`SystemSSHSession`** (master + exec + sftp via ControlMaster), proven on a
   **key-based host (AWS EC2)** — confirms multiplexing + SFTP browse parity with
   paramiko. *(No UI yet.)*
2. **WS relay + auth modal**, proven against a **real MFA HPC** (password + Duo).
3. **Wire `remote_docker`/`slurm`** to the session; status/health/disconnect;
   `ControlPersist` config; audit. Deprecate the paramiko path (or keep as the
   key-only fast path).

## Risks / open questions
- **Container restart loses the master** (in-container socket) → re-auth needed.
  Acceptable; note in UX. (A host-side SSH broker could avoid this but reintroduces
  the VM-boundary problem.)
- **Push-only Duo** sends no prompt text — detect the "approve on your device"
  banner and show a spinner until the sentinel/timeout.
- **ProxyJump that also needs MFA** → multiple sequential prompts; the generic
  PTY relay handles it, but test it.
- **pexpect/ptyprocess dependency** added to the backend image (small).
- **Process mode** (non-container dev) can keep using the host's own ssh +
  ControlMaster directly — even simpler there.

## Out of scope
- Changing the key-based/non-MFA path (still works; gets faster via multiplexing
  if we adopt `SystemSSHSession` there too).
- Storing or caching credentials.
