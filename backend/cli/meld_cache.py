"""
MELD cache management utilities for production-safe focal workflow setup.

This CLI provides:
- Local cache verification
- HPC cache verification (via persisted SSH/HPC config)
- Local -> HPC cache sync for first-time setup

Usage examples:
  python3 -m backend.cli.meld_cache verify
  python3 -m backend.cli.meld_cache verify-local
  python3 -m backend.cli.meld_cache verify-hpc
  python3 -m backend.cli.meld_cache sync-hpc
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.core.hpc_config_store import load_hpc_config
from backend.core.ssh_manager import SSHConnectionError, get_ssh_manager


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


def _warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def _err(msg: str) -> None:
    print(f"[ERR] {msg}")


REQUIRED_REL_FILES = (
    "meld_params/fsaverage_sym/surf/lh.inflated",
    "meld_params/fsaverage_sym/surf/rh.inflated",
)


@dataclass
class CacheCheck:
    root: str
    valid: bool
    reason: str


def _check_local_root(root: Path) -> CacheCheck:
    missing = [rel for rel in REQUIRED_REL_FILES if not (root / rel).is_file()]
    models_dir = root / "models"
    models_ok = models_dir.is_dir() and any(models_dir.iterdir())
    if missing:
        return CacheCheck(str(root), False, f"missing files: {', '.join(missing)}")
    if not models_ok:
        return CacheCheck(str(root), False, "models directory missing or empty")
    return CacheCheck(str(root), True, "ready")


def _candidate_local_roots() -> list[Path]:
    data_dir = Path(os.environ.get("DATA_DIR", "./data"))
    return [data_dir / "meld_data", data_dir / "meld_data" / "meld_data"]


def verify_local(verbose: bool = True) -> tuple[bool, Optional[Path]]:
    for root in _candidate_local_roots():
        check = _check_local_root(root)
        if check.valid:
            if verbose:
                _ok(f"Local MELD cache ready at {check.root}")
            return True, root
        if verbose:
            _warn(f"Local MELD cache not ready at {check.root}: {check.reason}")
    return False, None


def _configure_ssh_from_persisted() -> tuple[Optional[dict], Optional[object]]:
    cfg = load_hpc_config()
    if not cfg:
        return None, None
    ssh = get_ssh_manager()
    if not ssh.is_connected:
        ssh.configure(
            host=cfg["ssh_host"],
            username=cfg["ssh_user"],
            port=int(cfg.get("ssh_port", 22)),
        )
        ssh.connect()
    return cfg, ssh


def _resolve_remote_path(ssh, raw_path: str) -> str:
    cmd = f'eval echo "{raw_path}"'
    code, out, _ = ssh.execute(cmd, timeout=15)
    resolved = out.strip()
    if code == 0 and resolved.startswith("/"):
        return resolved
    return raw_path


def _check_remote_root(ssh, root: str) -> CacheCheck:
    missing = []
    for rel in REQUIRED_REL_FILES:
        target = f'{root}/{rel}'
        code, out, _ = ssh.execute(f'test -f "{target}" && echo yes || echo no', timeout=20)
        if code != 0 or "yes" not in out:
            missing.append(rel)
    code2, out2, _ = ssh.execute(
        f'test -d "{root}/models" && ls -A "{root}/models" 2>/dev/null | head -1 || true',
        timeout=20,
    )
    models_ok = code2 == 0 and bool((out2 or "").strip())
    if missing:
        return CacheCheck(root, False, f"missing files: {', '.join(missing)}")
    if not models_ok:
        return CacheCheck(root, False, "models directory missing or empty")
    return CacheCheck(root, True, "ready")


def _candidate_remote_roots(cfg: Optional[dict], ssh) -> list[str]:
    work_dir = "~"
    if cfg and cfg.get("work_dir"):
        work_dir = str(cfg["work_dir"])
    resolved_work = _resolve_remote_path(ssh, work_dir)
    return [
        f"{resolved_work}/meld_data/meld_data",
        f"{resolved_work}/meld_data",
    ]


def verify_hpc(verbose: bool = True) -> tuple[bool, Optional[str]]:
    try:
        cfg, ssh = _configure_ssh_from_persisted()
    except SSHConnectionError as e:
        if verbose:
            _err(f"Could not connect to HPC for MELD cache check: {e}")
        return False, None
    if not ssh:
        if verbose:
            _warn("No persisted HPC config found. Connect HPC first, then rerun.")
        return False, None
    for root in _candidate_remote_roots(cfg, ssh):
        check = _check_remote_root(ssh, root)
        if check.valid:
            if verbose:
                _ok(f"HPC MELD cache ready at {check.root}")
            return True, root
        if verbose:
            _warn(f"HPC MELD cache not ready at {check.root}: {check.reason}")
    return False, None


def _mkdir_remote_tree(ssh, remote_dir: str) -> None:
    ssh.execute(f'mkdir -p "{remote_dir}"', check=True, timeout=30)


def _sync_local_to_hpc(local_root: Path, remote_root: str) -> None:
    _, ssh = _configure_ssh_from_persisted()
    if not ssh:
        raise RuntimeError("No persisted HPC config found. Connect HPC first.")
    _mkdir_remote_tree(ssh, remote_root)
    # Upload files recursively. Keep structure relative to local_root.
    for current_root, _, files in os.walk(local_root):
        for name in files:
            lp = Path(current_root) / name
            rel = lp.relative_to(local_root).as_posix()
            rp = f"{remote_root}/{rel}"
            ssh.put_file(str(lp), rp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage MELD cache for focal workflow")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("verify", help="Verify local and (if configured) HPC MELD cache")
    sub.add_parser("verify-local", help="Verify local MELD cache only")
    sub.add_parser("verify-hpc", help="Verify HPC MELD cache only")
    sync = sub.add_parser("sync-hpc", help="Sync local MELD cache to HPC")
    sync.add_argument(
        "--remote-root",
        default=None,
        help="Remote destination root (default: resolved HPC work_dir + /meld_data/meld_data)",
    )

    args = parser.parse_args()
    cmd = args.cmd or "verify"

    if cmd == "verify-local":
        ok, _ = verify_local(verbose=True)
        sys.exit(0 if ok else 1)

    if cmd == "verify-hpc":
        ok, _ = verify_hpc(verbose=True)
        sys.exit(0 if ok else 1)

    if cmd == "sync-hpc":
        local_ok, local_root = verify_local(verbose=True)
        if not local_ok or not local_root:
            _err("Local cache is not ready. Stage local assets first, then sync.")
            sys.exit(1)
        try:
            cfg, ssh = _configure_ssh_from_persisted()
            if not ssh:
                _err("No persisted HPC config found. Connect HPC first.")
                sys.exit(1)
            if args.remote_root:
                remote_root = _resolve_remote_path(ssh, args.remote_root)
            else:
                remote_root = _candidate_remote_roots(cfg, ssh)[0]
            print(f"[INFO] Syncing {local_root} -> {remote_root} ...")
            _sync_local_to_hpc(local_root, remote_root)
            _ok("Sync complete.")
            hpc_ok, _ = verify_hpc(verbose=True)
            sys.exit(0 if hpc_ok else 1)
        except Exception as e:
            _err(f"Sync failed: {e}")
            sys.exit(1)

    # default: verify both
    local_ok, _ = verify_local(verbose=True)
    hpc_ok, _ = verify_hpc(verbose=True)
    if local_ok and hpc_ok:
        _ok("MELD cache is ready for focal workflow submission.")
        sys.exit(0)
    _warn("MELD cache is not fully ready.")
    _warn("Run: ./research meld-cache verify-local / verify-hpc / sync-hpc")
    sys.exit(1)


if __name__ == "__main__":
    main()
