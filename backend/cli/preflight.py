"""
Pre-flight system check for NeuroInsight Research.

Runs at startup (or standalone) to verify that all runtime dependencies
are satisfied before accepting jobs.  Checks include:

  1. Docker daemon reachability
  2. Container images (cached vs. missing, size)
  3. License files (FreeSurfer, MELD Graph)
  4. Disk space
  5. System resources (RAM, CPU)
  6. Infrastructure services (PostgreSQL, Redis, MinIO)

Exit codes:
  0  All checks passed
  1  One or more critical checks failed (app may not function)
  2  Warnings only (app will work, but some workflows may fail)
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Terminal colours
# ---------------------------------------------------------------------------
_NO_COLOR = os.environ.get("NO_COLOR") is not None or not sys.stdout.isatty()

_GREEN = "" if _NO_COLOR else "\033[0;32m"
_YELLOW = "" if _NO_COLOR else "\033[0;33m"
_RED = "" if _NO_COLOR else "\033[0;31m"
_CYAN = "" if _NO_COLOR else "\033[0;36m"
_BOLD = "" if _NO_COLOR else "\033[1m"
_DIM = "" if _NO_COLOR else "\033[2m"
_NC = "" if _NO_COLOR else "\033[0m"

_OK = f"  {_GREEN}[OK]{_NC}"
_WARN = f"  {_YELLOW}[!!]{_NC}"
_FAIL = f"  {_RED}[FAIL]{_NC}"
_INFO = f"  {_CYAN}[--]{_NC}"

_QUIET = False


def _header(title: str) -> None:
    if not _QUIET:
        print(f"\n{_BOLD}-- {title} --{_NC}")


def _ok(msg: str) -> None:
    if not _QUIET:
        print(f"{_OK} {msg}")


def _warn(msg: str) -> None:
    if not _QUIET:
        print(f"{_WARN} {msg}")


def _fail(msg: str) -> None:
    if not _QUIET:
        print(f"{_FAIL} {msg}")


def _info(msg: str) -> None:
    if not _QUIET:
        print(f"{_INFO} {msg}")


# ---------------------------------------------------------------------------
# Result collector
# ---------------------------------------------------------------------------
@dataclass
class PreflightResult:
    passed: int = 0
    warnings: int = 0
    failures: int = 0
    details: List[str] = field(default_factory=list)

    def ok(self, msg: str) -> None:
        self.passed += 1
        self.details.append(f"OK: {msg}")
        _ok(msg)

    def warn(self, msg: str) -> None:
        self.warnings += 1
        self.details.append(f"WARN: {msg}")
        _warn(msg)

    def fail(self, msg: str) -> None:
        self.failures += 1
        self.details.append(f"FAIL: {msg}")
        _fail(msg)

    @property
    def exit_code(self) -> int:
        if self.failures > 0:
            return 1
        if self.warnings > 0:
            return 2
        return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _bytes_human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f} PB"


def _run(cmd: List[str], timeout: int = 15) -> Tuple[int, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"command timed out after {timeout}s"
    except Exception as e:
        return 1, str(e)


# ---------------------------------------------------------------------------
# 1. Docker daemon
# ---------------------------------------------------------------------------
def check_docker(result: PreflightResult) -> bool:
    _header("Docker daemon")

    rc, out = _run(["docker", "info", "--format", "{{.ServerVersion}}"])
    if rc != 0:
        result.fail("Docker daemon not reachable")
        _info("Start Docker Desktop or run: sudo systemctl start docker")
        return False

    result.ok(f"Docker daemon v{out.splitlines()[0] if out else '?'}")

    rc2, out2 = _run(["docker", "info", "--format", "{{.Driver}}"])
    if rc2 == 0 and out2:
        _info(f"Storage driver: {out2.strip()}")

    return True


# ---------------------------------------------------------------------------
# 2. Container images
# ---------------------------------------------------------------------------
def _get_required_images() -> Dict[str, List[str]]:
    """Read plugin YAMLs to build image -> [plugin_ids] mapping."""
    try:
        import yaml as _yaml
    except ImportError:
        return {}

    base = Path(__file__).resolve().parent.parent.parent
    plugins_dir = base / "plugins"
    if not plugins_dir.exists():
        return {}

    images: Dict[str, List[str]] = {}
    for yf in sorted(plugins_dir.glob("*.yaml")):
        try:
            with open(yf) as f:
                data = _yaml.safe_load(f)
            if not data or data.get("type") != "plugin":
                continue
            img = (data.get("container", {}) or {}).get("image", "")
            if img:
                images.setdefault(img, []).append(data.get("id", yf.stem))
        except Exception:
            continue
    return images


def _docker_image_size(image: str) -> Optional[int]:
    """Return image size in bytes, or None if not present."""
    rc, out = _run(["docker", "image", "inspect", image,
                     "--format", "{{.Size}}"])
    if rc == 0:
        try:
            return int(out.strip())
        except ValueError:
            return None
    return None


def check_images(result: PreflightResult, docker_ok: bool) -> None:
    _header("Container images")

    if not docker_ok:
        result.warn("Skipped (Docker not available)")
        return

    images = _get_required_images()
    if not images:
        result.warn("Could not discover plugin images (PyYAML missing?)")
        return

    cached = 0
    missing = 0
    total_size = 0

    for image in sorted(images.keys()):
        plugin_ids = images[image]
        plugins_str = ", ".join(plugin_ids)
        size = _docker_image_size(image)

        if size is not None:
            cached += 1
            total_size += size
            result.ok(f"{image}  ({_bytes_human(size)})  [{plugins_str}]")
        else:
            missing += 1
            result.warn(f"{image}  (not pulled)  [{plugins_str}]")
            _info(f"  Pull with: docker pull {image}")

    print()
    _info(f"Images: {cached} cached ({_bytes_human(total_size)}), {missing} missing")
    if missing > 0:
        _info(f"Pull all missing: ./research pull")


# ---------------------------------------------------------------------------
# 3. License files
# ---------------------------------------------------------------------------
def _find_license(
    env_var: Optional[str],
    configured_path: Optional[str],
    search_paths: List[Path],
) -> Optional[str]:
    """Search for a license file, returning the first path found."""
    if configured_path:
        p = Path(configured_path).resolve()
        if p.is_file():
            return str(p)
    if env_var:
        env_val = os.environ.get(env_var)
        if env_val:
            p = Path(env_val).resolve()
            if p.is_file():
                return str(p)
    for candidate in search_paths:
        resolved = candidate.resolve()
        if resolved.is_file():
            return str(resolved)
    return None


def _plugins_needing_license(license_key: str) -> List[str]:
    """Return plugin IDs whose inputs reference a license key."""
    try:
        import yaml as _yaml
    except ImportError:
        return []

    base = Path(__file__).resolve().parent.parent.parent
    plugins_dir = base / "plugins"
    if not plugins_dir.exists():
        return []

    needing: List[str] = []
    for yf in sorted(plugins_dir.glob("*.yaml")):
        try:
            with open(yf) as f:
                data = _yaml.safe_load(f)
            if not data or data.get("type") != "plugin":
                continue
            for inp in data.get("inputs", {}).get("required", []):
                key = inp.get("key", "") if isinstance(inp, dict) else ""
                if license_key in key:
                    needing.append(data.get("id", yf.stem))
                    break
        except Exception:
            continue
    return needing


def check_licenses(result: PreflightResult) -> None:
    _header("License files")

    # FreeSurfer
    fs_path = _find_license(
        env_var="FS_LICENSE",
        configured_path=os.environ.get("FS_LICENSE_PATH"),
        search_paths=[
            Path("./license.txt"),
            Path("./data/license.txt"),
            Path(os.environ.get("FREESURFER_HOME", "/nonexistent")) / "license.txt",
            Path.home() / ".freesurfer" / "license.txt",
        ],
    )
    fs_plugins = _plugins_needing_license("fs_license")
    if fs_path:
        result.ok(f"FreeSurfer license  ->  {fs_path}")
    elif fs_plugins:
        result.warn(f"FreeSurfer license not found (needed by: {', '.join(fs_plugins)})")
        _info("Get a free license: https://surfer.nmr.mgh.harvard.edu/registration.html")
        _info("Place as ./license.txt or set FS_LICENSE_PATH in .env")
    else:
        _info("FreeSurfer license not found (no plugins require it)")

    # MELD Graph
    meld_path = _find_license(
        env_var=None,
        configured_path=os.environ.get("MELD_LICENSE_PATH"),
        search_paths=[
            Path("./meld_license.txt"),
            Path("./data/meld_license.txt"),
            Path.home() / ".meld" / "meld_license.txt",
        ],
    )
    meld_plugins = _plugins_needing_license("meld_license")
    if meld_path:
        result.ok(f"MELD Graph license  ->  {meld_path}")
    elif meld_plugins:
        result.warn(f"MELD Graph license not found (needed by: {', '.join(meld_plugins)})")
        _info("Place as ./meld_license.txt or set MELD_LICENSE_PATH in .env")
    else:
        _info("MELD Graph license not found (no plugins require it)")


# ---------------------------------------------------------------------------
# 4. Disk space
# ---------------------------------------------------------------------------
MIN_DISK_GB = 20
WARN_DISK_GB = 50


def check_disk(result: PreflightResult) -> None:
    _header("Disk space")

    data_dir = Path(os.environ.get("DATA_DIR", "./data")).resolve()
    try:
        usage = shutil.disk_usage(str(data_dir if data_dir.exists() else Path(".")))
    except OSError as e:
        result.warn(f"Could not check disk space: {e}")
        return

    free_gb = usage.free / (1024 ** 3)
    total_gb = usage.total / (1024 ** 3)
    used_pct = (usage.used / usage.total) * 100

    msg = f"{free_gb:.1f} GB free / {total_gb:.1f} GB total ({used_pct:.0f}% used)"

    if free_gb < MIN_DISK_GB:
        result.fail(f"{msg}  — below {MIN_DISK_GB} GB minimum")
        _info("Free space with: docker system prune -f")
    elif free_gb < WARN_DISK_GB:
        result.warn(f"{msg}  — below {WARN_DISK_GB} GB recommended")
        _info("Neuroimaging containers are large (5-15 GB each)")
    else:
        result.ok(msg)

    # Docker-specific disk usage
    rc, out = _run(["docker", "system", "df", "--format",
                     "{{.Type}}\t{{.Size}}\t{{.Reclaimable}}"])
    if rc == 0 and out:
        _info("Docker disk usage:")
        for line in out.strip().splitlines():
            _info(f"  {line}")


# ---------------------------------------------------------------------------
# 5. System resources
# ---------------------------------------------------------------------------
MIN_RAM_GB = 4
WARN_RAM_GB = 8


def check_resources(result: PreflightResult) -> None:
    _header("System resources")

    # CPU
    try:
        cpu_count = os.cpu_count() or 0
        if cpu_count >= 4:
            result.ok(f"CPU: {cpu_count} cores")
        elif cpu_count >= 2:
            result.warn(f"CPU: {cpu_count} cores (4+ recommended for neuroimaging)")
        else:
            result.fail(f"CPU: {cpu_count} core(s) (minimum 2 required)")
    except Exception:
        result.warn("CPU: could not detect")

    # RAM
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    ram_gb = kb / (1024 * 1024)
                    if ram_gb >= WARN_RAM_GB:
                        result.ok(f"RAM: {ram_gb:.1f} GB")
                    elif ram_gb >= MIN_RAM_GB:
                        result.warn(f"RAM: {ram_gb:.1f} GB ({WARN_RAM_GB}+ GB recommended)")
                    else:
                        result.fail(f"RAM: {ram_gb:.1f} GB (minimum {MIN_RAM_GB} GB)")
                    break
    except FileNotFoundError:
        # macOS fallback
        rc, out = _run(["sysctl", "-n", "hw.memsize"])
        if rc == 0:
            try:
                ram_gb = int(out.strip()) / (1024 ** 3)
                if ram_gb >= WARN_RAM_GB:
                    result.ok(f"RAM: {ram_gb:.1f} GB")
                elif ram_gb >= MIN_RAM_GB:
                    result.warn(f"RAM: {ram_gb:.1f} GB ({WARN_RAM_GB}+ GB recommended)")
                else:
                    result.fail(f"RAM: {ram_gb:.1f} GB (minimum {MIN_RAM_GB} GB)")
            except ValueError:
                result.warn("RAM: could not detect")
        else:
            result.warn("RAM: could not detect")

    # GPU (optional, nice to know)
    rc, out = _run(["nvidia-smi", "--query-gpu=name,memory.total",
                     "--format=csv,noheader,nounits"])
    if rc == 0 and out:
        for line in out.strip().splitlines():
            _info(f"GPU: {line.strip()}")
    else:
        _info("GPU: not detected (optional — CPU-only execution supported)")


# ---------------------------------------------------------------------------
# 6. Infrastructure services
# ---------------------------------------------------------------------------
def _tcp_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False


def check_infrastructure(result: PreflightResult) -> None:
    _header("Infrastructure services")

    # PostgreSQL
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = int(os.environ.get("POSTGRES_PORT", "5432"))
    if _tcp_reachable(pg_host, pg_port):
        result.ok(f"PostgreSQL  ({pg_host}:{pg_port})")
    else:
        result.fail(f"PostgreSQL not reachable ({pg_host}:{pg_port})")
        _info("Start with: ./research infra up")

    # Redis
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))
    if _tcp_reachable(redis_host, redis_port):
        result.ok(f"Redis  ({redis_host}:{redis_port})")
    else:
        result.fail(f"Redis not reachable ({redis_host}:{redis_port})")

    # MinIO
    minio_host = os.environ.get("MINIO_HOST", "localhost")
    minio_port = int(os.environ.get("MINIO_PORT", "9000"))
    if _tcp_reachable(minio_host, minio_port):
        result.ok(f"MinIO  ({minio_host}:{minio_port})")
    else:
        result.warn(f"MinIO not reachable ({minio_host}:{minio_port})")


# ---------------------------------------------------------------------------
# 7. Plugin/Workflow registry sanity
# ---------------------------------------------------------------------------
def check_registry(result: PreflightResult) -> None:
    _header("Plugin & Workflow registry")

    try:
        import yaml as _yaml
    except ImportError:
        result.warn("PyYAML not installed — cannot validate registry")
        return

    base = Path(__file__).resolve().parent.parent.parent
    plugins_dir = base / "plugins"
    workflows_dir = base / "workflows"

    plugin_count = len(list(plugins_dir.glob("*.yaml"))) if plugins_dir.exists() else 0
    workflow_count = len(list(workflows_dir.glob("*.yaml"))) if workflows_dir.exists() else 0

    if plugin_count == 0:
        result.fail("No plugin definitions found")
    else:
        result.ok(f"{plugin_count} plugins loaded")

    if workflow_count == 0:
        result.warn("No workflow definitions found")
    else:
        result.ok(f"{workflow_count} workflows loaded")

    # Validate workflow -> plugin references
    plugins = set()
    for yf in plugins_dir.glob("*.yaml"):
        try:
            with open(yf) as f:
                data = _yaml.safe_load(f)
            if data and data.get("type") == "plugin":
                plugins.add(data.get("id", yf.stem))
        except Exception:
            pass

    broken_refs = []
    for yf in workflows_dir.glob("*.yaml"):
        try:
            with open(yf) as f:
                data = _yaml.safe_load(f)
            if not data or data.get("type") != "workflow":
                continue
            wf_id = data.get("id", yf.stem)
            for step in data.get("steps", []):
                uses = step.get("uses", "")
                if uses and uses not in plugins:
                    broken_refs.append(f"{wf_id} -> {uses}")
        except Exception:
            pass

    if broken_refs:
        for ref in broken_refs:
            result.warn(f"Broken reference: {ref}")
    else:
        _info("All workflow references valid")


# ---------------------------------------------------------------------------
# Master runner
# ---------------------------------------------------------------------------
def run_preflight(
    *,
    skip_images: bool = False,
    skip_infra: bool = False,
    output_json: bool = False,
) -> PreflightResult:
    """Run the full pre-flight check suite.

    Returns a PreflightResult with counts and exit code.
    """
    global _QUIET
    _QUIET = output_json

    result = PreflightResult()

    if not output_json:
        print(f"\n{_BOLD}{'=' * 60}{_NC}")
        print(f"{_BOLD}  NeuroInsight Research — Pre-flight System Check{_NC}")
        print(f"{_BOLD}{'=' * 60}{_NC}")

    docker_ok = check_docker(result)

    if not skip_images:
        check_images(result, docker_ok)

    check_licenses(result)
    check_disk(result)
    check_resources(result)

    if not skip_infra:
        check_infrastructure(result)

    check_registry(result)

    # Summary
    if not output_json:
        print(f"\n{_BOLD}{'=' * 60}{_NC}")
        parts = [f"{_GREEN}{result.passed} passed{_NC}"]
        if result.warnings:
            parts.append(f"{_YELLOW}{result.warnings} warnings{_NC}")
        if result.failures:
            parts.append(f"{_RED}{result.failures} failed{_NC}")
        summary = ", ".join(parts)
        print(f"  Pre-flight: {summary}")

        if result.failures:
            print(f"\n  {_RED}Some checks failed. The app may not function correctly.{_NC}")
            print(f"  {_RED}Fix the issues above and re-run: ./research preflight{_NC}")
        elif result.warnings:
            print(f"\n  {_YELLOW}Warnings detected. Some workflows may not be available.{_NC}")
            print(f"  {_YELLOW}Address warnings above for full functionality.{_NC}")
        else:
            print(f"\n  {_GREEN}All systems go!{_NC}")
        print()

    if output_json:
        print(json.dumps({
            "passed": result.passed,
            "warnings": result.warnings,
            "failures": result.failures,
            "exit_code": result.exit_code,
            "details": result.details,
        }, indent=2))

    return result


# ---------------------------------------------------------------------------
# Standalone entry: python -m backend.cli.preflight [--json] [--skip-images]
# ---------------------------------------------------------------------------
def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="NeuroInsight Research — Pre-flight System Check",
    )
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--skip-images", action="store_true",
                        help="Skip Docker image checks (faster)")
    parser.add_argument("--skip-infra", action="store_true",
                        help="Skip infrastructure service checks")
    args = parser.parse_args()

    result = run_preflight(
        skip_images=args.skip_images,
        skip_infra=args.skip_infra,
        output_json=args.json,
    )
    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
