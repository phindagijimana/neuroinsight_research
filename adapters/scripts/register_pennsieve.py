#!/usr/bin/env python3
"""
Register NeuroInsight adapters as Pennsieve processors.

Pennsieve expects Docker images to be built and published; it pulls them
on demand. This script builds and tags the adapter images for local testing
or pushes them to a registry for production use.

Usage:
    python register_pennsieve.py --plugin freesurfer_recon --push
    python register_pennsieve.py --all --push
    python register_pennsieve.py --all --list
    python register_pennsieve.py --workflows --list
"""

import argparse
import os
import shutil
import subprocess
import sys

ADAPTERS_DIR = os.path.join(os.path.dirname(__file__), "..", "pennsieve")

PLUGIN_ADAPTERS = {
    "freesurfer_recon": {
        "dir": os.path.join(ADAPTERS_DIR, "freesurfer_recon"),
        "image": "neuroinsight/freesurfer-recon-pennsieve",
        "tag": "7.4.1",
        "base": "freesurfer/freesurfer:7.4.1",
    },
    "fastsurfer": {
        "dir": os.path.join(ADAPTERS_DIR, "fastsurfer"),
        "image": "neuroinsight/fastsurfer-pennsieve",
        "tag": "2.4.2",
        "base": "deepmi/fastsurfer:v2.4.2",
    },
    "fmriprep": {
        "dir": os.path.join(ADAPTERS_DIR, "fmriprep"),
        "image": "neuroinsight/fmriprep-pennsieve",
        "tag": "23.2.1",
        "base": "nipreps/fmriprep:23.2.1",
    },
    "qsiprep": {
        "dir": os.path.join(ADAPTERS_DIR, "qsiprep"),
        "image": "neuroinsight/qsiprep-pennsieve",
        "tag": "0.20.0",
        "base": "pennbbl/qsiprep:0.20.0",
    },
    "qsirecon": {
        "dir": os.path.join(ADAPTERS_DIR, "qsirecon"),
        "image": "neuroinsight/qsirecon-pennsieve",
        "tag": "1.1.1",
        "base": "pennlinc/qsirecon:1.1.1",
    },
    "dcm2niix": {
        "dir": os.path.join(ADAPTERS_DIR, "dcm2niix"),
        "image": "neuroinsight/dcm2niix-pennsieve",
        "tag": "1.3.4",
        "base": "nipy/heudiconv:1.3.4",
    },
    "meld_graph": {
        "dir": os.path.join(ADAPTERS_DIR, "meld_graph"),
        "image": "neuroinsight/meld-graph-pennsieve",
        "tag": "2.2.4",
        "base": "meldproject/meld_graph:v2.2.4",
    },
    "xcpd": {
        "dir": os.path.join(ADAPTERS_DIR, "xcpd"),
        "image": "neuroinsight/xcpd-pennsieve",
        "tag": "0.6.1",
        "base": "pennlinc/xcp_d:0.6.1",
    },
    "segmentha_t1": {
        "dir": os.path.join(ADAPTERS_DIR, "segmentha_t1"),
        "image": "neuroinsight/segmentha-t1-pennsieve",
        "tag": "7.4.1",
        "base": "phindagijimana321/freesurfer-mcr:7.4.1",
    },
    "segmentha_t2": {
        "dir": os.path.join(ADAPTERS_DIR, "segmentha_t2"),
        "image": "neuroinsight/segmentha-t2-pennsieve",
        "tag": "7.4.1",
        "base": "phindagijimana321/freesurfer-mcr:7.4.1",
    },
    "freesurfer_longitudinal": {
        "dir": os.path.join(ADAPTERS_DIR, "freesurfer_longitudinal"),
        "image": "neuroinsight/freesurfer-longitudinal-pennsieve",
        "tag": "7.4.1",
        "base": "freesurfer/freesurfer:7.4.1",
    },
    "freesurfer_longitudinal_stats": {
        "dir": os.path.join(ADAPTERS_DIR, "freesurfer_longitudinal_stats"),
        "image": "neuroinsight/freesurfer-longitudinal-stats-pennsieve",
        "tag": "7.4.1",
        "base": "freesurfer/freesurfer:7.4.1",
    },
    "freesurfer_autorecon_volonly": {
        "dir": os.path.join(ADAPTERS_DIR, "freesurfer_autorecon_volonly"),
        "image": "neuroinsight/freesurfer-autorecon-volonly-pennsieve",
        "tag": "7.4.1",
        "base": "freesurfer/freesurfer:7.4.1",
    },
    "hs_postprocess": {
        "dir": os.path.join(ADAPTERS_DIR, "hs_postprocess"),
        "image": "phindagijimana321/hs-postprocess-pennsieve",
        "tag": "1.0.0",
        "base": "phindagijimana321/hs-postprocess:1.0.0",
    },
}

WORKFLOW_ADAPTERS = {
    "wf_hippo_subfields_t1": {
        "dir": os.path.join(ADAPTERS_DIR, "workflows", "hippo_subfields_t1"),
        "image": "neuroinsight/wf-hippo-subfields-t1-pennsieve",
        "tag": "7.4.1",
        "base": "phindagijimana321/freesurfer-mcr:7.4.1",
    },
    "wf_hippo_subfields_t2": {
        "dir": os.path.join(ADAPTERS_DIR, "workflows", "hippo_subfields_t2"),
        "image": "neuroinsight/wf-hippo-subfields-t2-pennsieve",
        "tag": "7.4.1",
        "base": "phindagijimana321/freesurfer-mcr:7.4.1",
    },
    "wf_freesurfer_longitudinal_full": {
        "dir": os.path.join(ADAPTERS_DIR, "workflows", "freesurfer_longitudinal_full"),
        "image": "neuroinsight/wf-freesurfer-longitudinal-full-pennsieve",
        "tag": "7.4.1",
        "base": "freesurfer/freesurfer:7.4.1",
    },
    "wf_cortical_lesion_detection": {
        "dir": os.path.join(ADAPTERS_DIR, "workflows", "cortical_lesion_detection"),
        "image": "neuroinsight/wf-cortical-lesion-detection-pennsieve",
        "tag": "1.0.0",
        "base": "freesurfer:7.4.1 + meld_graph:v2.2.4 (multi-stage)",
    },
    "wf_fmri_full": {
        "dir": os.path.join(ADAPTERS_DIR, "workflows", "fmri_full"),
        "image": "neuroinsight/wf-fmri-full-pennsieve",
        "tag": "1.0.0",
        "base": "fmriprep:23.2.1 + xcp_d:0.6.1 (multi-stage)",
    },
    "wf_diffusion_full": {
        "dir": os.path.join(ADAPTERS_DIR, "workflows", "diffusion_full"),
        "image": "neuroinsight/wf-diffusion-full-pennsieve",
        "tag": "1.0.0",
        "base": "qsiprep:0.20.0 + qsirecon:1.1.1 (multi-stage)",
    },
    "wf_hs_detection": {
        "dir": os.path.join(ADAPTERS_DIR, "workflows", "hs_detection"),
        "image": "neuroinsight/wf-hs-detection-pennsieve",
        "tag": "1.0.0",
        "base": "freesurfer:7.4.1 + hs-postprocess:1.0.0 (multi-stage)",
    },
}

ALL_ADAPTERS = {**PLUGIN_ADAPTERS, **WORKFLOW_ADAPTERS}


def build(name: str, push: bool = False) -> None:
    info = ALL_ADAPTERS[name]
    image_tag = f"{info['image']}:{info['tag']}"
    adapter_dir = info["dir"]
    print(f"\nBuilding {image_tag} from {adapter_dir}...")
    print(f"  Base: {info['base']}")

    # Copy shared/ into the adapter's build context so COPY works
    shared_src = os.path.join(ADAPTERS_DIR, "shared")
    shared_dst = os.path.join(adapter_dir, "shared")
    if os.path.isdir(shared_src) and not os.path.isdir(shared_dst):
        shutil.copytree(shared_src, shared_dst)

    try:
        subprocess.run(
            ["docker", "build", "-t", image_tag, adapter_dir],
            check=True,
        )
        print(f"Built: {image_tag}")
    finally:
        # Clean up copied shared/ to avoid bloating the repo
        if os.path.isdir(shared_dst) and os.path.isdir(shared_src):
            if os.path.realpath(shared_dst) != os.path.realpath(shared_src):
                shutil.rmtree(shared_dst, ignore_errors=True)

    if push:
        print(f"Pushing {image_tag}...")
        subprocess.run(["docker", "push", image_tag], check=True)
        print(f"Pushed: {image_tag}")


def main() -> None:
    all_names = list(ALL_ADAPTERS.keys())
    parser = argparse.ArgumentParser(description="Register NeuroInsight Pennsieve adapters")
    parser.add_argument("--plugin", choices=list(PLUGIN_ADAPTERS.keys()), help="Specific plugin adapter to build")
    parser.add_argument("--workflow", choices=list(WORKFLOW_ADAPTERS.keys()), help="Specific workflow adapter to build")
    parser.add_argument("--plugins", action="store_true", help="Build all plugin adapters")
    parser.add_argument("--workflows", action="store_true", help="Build all workflow adapters")
    parser.add_argument("--all", action="store_true", help="Build all adapters (plugins + workflows)")
    parser.add_argument("--push", action="store_true", help="Push to Docker Hub after building")
    parser.add_argument("--list", action="store_true", help="List available adapters")
    args = parser.parse_args()

    if args.list:
        print(f"Plugin adapters ({len(PLUGIN_ADAPTERS)}):")
        for name, info in PLUGIN_ADAPTERS.items():
            print(f"  {name:35s} {info['image']}:{info['tag']}")
        print(f"\nWorkflow adapters ({len(WORKFLOW_ADAPTERS)}):")
        for name, info in WORKFLOW_ADAPTERS.items():
            print(f"  {name:35s} {info['image']}:{info['tag']}")
        print(f"\nTotal: {len(ALL_ADAPTERS)} adapters")
        return

    targets = []
    if args.all:
        targets = all_names
    elif args.plugins:
        targets = list(PLUGIN_ADAPTERS.keys())
    elif args.workflows:
        targets = list(WORKFLOW_ADAPTERS.keys())
    elif args.plugin:
        targets = [args.plugin]
    elif args.workflow:
        targets = [args.workflow]
    else:
        parser.print_help()
        sys.exit(1)

    for name in targets:
        build(name, push=args.push)

    print(f"\nDone. Built {len(targets)} adapter(s).")


if __name__ == "__main__":
    main()
