"""
License management — upload / status / remove the third-party licenses some
pipelines require (FreeSurfer, MELD Graph, ...).

Files are written to the data directory under the canonical names the existing
resolver (`Settings.fs_license_resolved` / `meld_license_resolved`) already
searches, so an uploaded license is picked up by jobs with no other wiring —
locally and (after staging) on HPC.

Extensible by design: add an entry to ``LICENSE_REGISTRY`` and both the API and
the Settings UI pick it up — including, in future, an app-activation license.
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.config import get_settings

router = APIRouter(prefix="/api/licenses", tags=["licenses"])

MAX_LICENSE_BYTES = 256 * 1024

# id -> metadata. `filename` MUST match what the resolver looks for in the data dir.
LICENSE_REGISTRY = {
    "freesurfer": {
        "name": "FreeSurfer",
        "filename": "license.txt",
        "required_by": ["FreeSurfer", "FastSurfer", "fMRIPrep", "MELD Graph"],
        "registration_url": "https://surfer.nmr.mgh.harvard.edu/registration.html",
        "description": "Free academic license — a short text file emailed after registration.",
        "format_hint": "Four lines (email, key, two signature lines).",
    },
    "meld": {
        "name": "MELD Graph",
        "filename": "meld_license.txt",
        "required_by": ["MELD Graph (v2.2.4+)"],
        "registration_url": "https://docs.google.com/forms/d/e/1FAIpQLSdocMWtxbmh9T7Sv8NT4f0Kpev-tmRI-kngDhUeBF9VcZXcfg/viewform",
        "description": "License key from the MELD registration form. Needed for MELD lesion detection.",
        "format_hint": "The license key text from the MELD registration response.",
    },
}


class LicenseUpload(BaseModel):
    content: str


def _path(meta: dict) -> Path:
    return Path(get_settings().data_dir).resolve() / meta["filename"]


def _entry(license_id: str, meta: dict) -> dict:
    p = _path(meta)
    installed = p.is_file()
    return {
        "id": license_id,
        "name": meta["name"],
        "filename": meta["filename"],
        "required_by": meta["required_by"],
        "registration_url": meta["registration_url"],
        "description": meta["description"],
        "format_hint": meta.get("format_hint", ""),
        "installed": installed,
        "size": p.stat().st_size if installed else 0,
    }


@router.get("")
def list_licenses():
    """List known licenses and whether each is installed."""
    return {"licenses": [_entry(lid, meta) for lid, meta in LICENSE_REGISTRY.items()]}


@router.post("/{license_id}")
def upload_license(license_id: str, body: LicenseUpload):
    """Save a license to the data directory (where jobs find it)."""
    meta = LICENSE_REGISTRY.get(license_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown license: {license_id}")
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="License content is empty.")
    if len(content.encode("utf-8")) > MAX_LICENSE_BYTES:
        raise HTTPException(status_code=400, detail="License content is too large.")
    p = _path(meta)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content + "\n")
    try:
        p.chmod(0o600)
    except OSError:
        pass  # best effort on filesystems without POSIX modes
    return _entry(license_id, meta)


@router.delete("/{license_id}")
def delete_license(license_id: str):
    """Remove an installed license."""
    meta = LICENSE_REGISTRY.get(license_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Unknown license: {license_id}")
    p = _path(meta)
    if p.is_file():
        p.unlink()
    return _entry(license_id, meta)
