#!/usr/bin/env python3
"""
Register NeuroInsight adapters with XNAT Container Service.

Builds adapter Docker images and optionally pushes them to Docker Hub.
The XNAT admin then registers the image URL in the XNAT Container Service UI,
and XNAT reads the command.json from the image labels.

Usage:
    python register_xnat.py --plugin freesurfer_recon --push
    python register_xnat.py --all --push
"""

import argparse
import os
import subprocess
import sys

ADAPTERS_DIR = os.path.join(os.path.dirname(__file__), "..", "xnat")

ADAPTERS = {
    "freesurfer_recon": {
        "dir": os.path.join(ADAPTERS_DIR, "freesurfer_recon"),
        "image": "neuroinsight/freesurfer-recon-xnat",
        "tag": "7.4.1",
    },
    "fastsurfer": {
        "dir": os.path.join(ADAPTERS_DIR, "fastsurfer"),
        "image": "neuroinsight/fastsurfer-xnat",
        "tag": "2.4.2",
    },
    "freesurfer_autorecon_volonly": {
        "dir": os.path.join(ADAPTERS_DIR, "freesurfer_autorecon_volonly"),
        "image": "neuroinsight/freesurfer-volonly-xnat",
        "tag": "7.4.1",
    },
}


def build(plugin: str, push: bool = False) -> None:
    info = ADAPTERS[plugin]
    image_tag = f"{info['image']}:{info['tag']}"
    print(f"Building {image_tag} from {info['dir']}...")

    subprocess.run(
        ["docker", "build", "-t", image_tag, info["dir"]],
        check=True,
    )
    print(f"Built: {image_tag}")

    if push:
        print(f"Pushing {image_tag}...")
        subprocess.run(["docker", "push", image_tag], check=True)
        print(f"Pushed: {image_tag}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Register NeuroInsight XNAT adapters")
    parser.add_argument("--plugin", choices=list(ADAPTERS.keys()), help="Specific plugin to build")
    parser.add_argument("--all", action="store_true", help="Build all adapters")
    parser.add_argument("--push", action="store_true", help="Push to Docker Hub after building")
    args = parser.parse_args()

    if not args.plugin and not args.all:
        parser.print_help()
        sys.exit(1)

    plugins = list(ADAPTERS.keys()) if args.all else [args.plugin]
    for p in plugins:
        build(p, push=args.push)


if __name__ == "__main__":
    main()
