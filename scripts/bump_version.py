#!/usr/bin/env python3
"""Bump the project version in one place.

The repo-root VERSION file is the single source of truth. This script writes it
and syncs the two package.json files (desktop app + frontend) so the desktop
build, the backend's reported version, and the all-in-one image tag all agree.

Usage:
    python3 scripts/bump_version.py 0.2.0

Release flow after bumping (commit first), tags drive CI:
    git tag nir-v0.2.0      && git push origin nir-v0.2.0      # builds GHCR image v0.2.0
    git tag desktop-v0.2.0  && git push origin desktop-v0.2.0  # builds signed installers
The desktop app pulls ghcr.io/.../nir-allinone:v<VERSION>, so always release the
nir-v tag before (or with) the matching desktop-v tag.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_FILES = [ROOT / "desktop" / "app" / "package.json", ROOT / "frontend" / "package.json"]


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    version = sys.argv[1].lstrip("v").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        print(f"error: '{version}' is not a valid semver (e.g. 0.2.0 or 1.0.0-rc1)")
        return 2

    (ROOT / "VERSION").write_text(version + "\n", encoding="utf-8")
    print(f"VERSION -> {version}")

    for pkg in PKG_FILES:
        data = json.loads(pkg.read_text(encoding="utf-8"))
        data["version"] = version
        # preserve 2-space indentation + trailing newline (npm style)
        pkg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"{pkg.relative_to(ROOT)} -> {version}")

    print(
        f"\nNext:\n"
        f"  git commit -am 'chore: release v{version}'\n"
        f"  git tag nir-v{version} && git push origin nir-v{version}\n"
        f"  git tag desktop-v{version} && git push origin desktop-v{version}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
