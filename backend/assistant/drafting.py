"""Rule-based drafting: request text + input path -> a job form the user can edit.

No model API is used. Every field the assistant fills is listed in
``filled_by`` so the UI can mark it, and the user can overwrite any of them.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# (target_type, target_id, keywords). First match wins, so specific intents
# come before generic ones.
_INTENTS: List[Tuple[str, str, Tuple[str, ...]]] = [
    ("workflow", "hippo_subfields_t1", ("hippocampal subfield", "hippocampus subfield", "subfield")),
    ("workflow", "diffusion_full", ("diffusion", "dwi", "tractograph", "connectome", "qsiprep")),
    ("workflow", "fmri_full", ("fmri", "functional", "bold", "resting state", "resting-state")),
    ("plugin", "dcm2niix", ("dicom", "dcm2niix", "convert to nifti")),
    ("plugin", "freesurfer_recon", ("freesurfer", "recon-all", "cortical thickness", "surfaces", "surface reconstruction")),
    ("plugin", "fastsurfer", ("fastsurfer", "segment", "segmentation", "parcellat", "volume", "volumes", "morphometry")),
]

_DEFAULT_TARGET = ("plugin", "fastsurfer")

_BIDS_ENTITY = re.compile(r"(?:^|_)(sub|ses|space|atlas|desc|run|acq)-([A-Za-z0-9]+)")
_BIDS_SUFFIX = re.compile(r"_([A-Za-z0-9]+)\.(?:nii(?:\.gz)?|mgz)$")

_SUFFIX_MODALITY = {"T1w": "T1w", "T2w": "T2w", "FLAIR": "FLAIR", "dwi": "dwi", "bold": "bold"}

# Labels the pipeline writes. This describes outputs only; it is not put on the
# input instance, where SciCap would then demand an input atlas.
_PIPELINE_OUTPUT_LABELS = {"fastsurfer": "DKT (aparc.DKTatlas+aseg)"}


@dataclass
class Draft:
    target_type: str
    target_id: str
    input_files: List[str]
    parameters: Dict[str, Any] = field(default_factory=dict)
    instance: Dict[str, Any] = field(default_factory=dict)
    filled_by: Dict[str, str] = field(default_factory=dict)
    rationale: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    request: str = ""
    drafted_by: str = "rules"
    fallback_reason: str = ""
    # What each drafter proposed for this request, kept for later comparison.
    proposals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Draft":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


_NO_SURFACES = ("no surface", "without surface", "skip surface")


def _pick_target(text: str, available: Dict[str, set]) -> Tuple[str, str, Optional[str], List[str]]:
    lowered = text.lower()
    matches: List[Tuple[str, str, str]] = []
    for ttype, tid, words in _INTENTS:
        if tid not in available.get(ttype, set()):
            continue
        if tid == "freesurfer_recon" and any(n in lowered for n in _NO_SURFACES):
            continue
        hit = next((w for w in words if w in lowered), None)
        if hit:
            matches.append((ttype, tid, hit))
    if matches:
        ttype, tid, hit = matches[0]
        others = [m[1] for m in matches[1:]]
        return ttype, tid, hit, others
    ttype, tid = _DEFAULT_TARGET
    return ttype, tid, None, []


def _parameters_from_text(target_id: str, text: str) -> Tuple[Dict[str, Any], List[str]]:
    lowered = text.lower()
    params: Dict[str, Any] = {}
    notes: List[str] = []
    if target_id == "fastsurfer":
        if any(w in lowered for w in ("cpu", "no gpu", "without gpu", "laptop")):
            params["use_cpu"] = True
            notes.append("use_cpu=true because the request mentions CPU / no GPU")
        if any(w in lowered for w in ("seg only", "segmentation only", "no surface", "without surface", "quick")):
            params["seg_only"] = True
            notes.append("seg_only=true because the request asks for segmentation without surfaces")
    return params, notes


def _read_sidecar(path: Path) -> Dict[str, Any]:
    name = path.name
    for ext in (".nii.gz", ".nii", ".mgz"):
        if name.endswith(ext):
            sidecar = path.with_name(name[: -len(ext)] + ".json")
            break
    else:
        return {}
    if not sidecar.is_file():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def infer_instance(input_path: str) -> Tuple[Dict[str, Any], Dict[str, str], List[str]]:
    """Metadata SciCap binds against, read from the BIDS filename and sidecar.

    Only the filename and JSON sidecar are read; image bytes are never opened.
    Fields that cannot be established are left out so SciCap can ABSTAIN.
    """
    instance: Dict[str, Any] = {"path": input_path, "format": "nifti"}
    filled: Dict[str, str] = {}
    notes: List[str] = []
    if not input_path:
        return instance, filled, ["No input path given; modality and space are unknown."]

    path = Path(input_path)
    name = path.name
    entities = dict(_BIDS_ENTITY.findall(name))
    suffix_match = _BIDS_SUFFIX.search(name)
    suffix = suffix_match.group(1) if suffix_match else None

    if "sub" in entities:
        instance["subject"] = f"sub-{entities['sub']}"
        filled["instance.subject"] = "BIDS filename"
    if suffix in _SUFFIX_MODALITY:
        instance["modality"] = _SUFFIX_MODALITY[suffix]
        filled["instance.modality"] = "BIDS suffix"
    if "space" in entities:
        space = entities["space"]
        instance["space"] = "subject_native" if space in ("T1w", "orig", "native") else space
        filled["instance.space"] = "BIDS space entity"
    elif "sub" in entities and suffix in _SUFFIX_MODALITY and "derivatives" not in path.parts:
        instance["space"] = "subject_native"
        filled["instance.space"] = "BIDS raw data has no space entity and is in scanner-native space"
    if "atlas" in entities:
        instance["atlas"] = entities["atlas"]
        filled["instance.atlas"] = "BIDS atlas entity"

    sidecar = _read_sidecar(path)
    for key in ("modality", "space", "atlas", "label_set"):
        if key in sidecar and isinstance(sidecar[key], str):
            instance[key] = sidecar[key]
            filled[f"instance.{key}"] = "JSON sidecar"

    if "modality" not in instance:
        notes.append("Modality could not be read from the filename; set it before approving.")
    if "space" not in instance:
        notes.append("Space could not be established; SciCap will ABSTAIN until you set it.")
    return instance, filled, notes


def draft_job(
    request: str,
    input_path: str,
    available: Dict[str, set],
    instance_overrides: Optional[Dict[str, Any]] = None,
    proposer: Optional[Callable[[str, List[Dict[str, Any]]], Dict[str, Any]]] = None,
    catalog: Optional[List[Dict[str, Any]]] = None,
) -> Draft:
    """Draft a job form. ``available`` maps "plugin"/"workflow" to registry ids.

    With a ``proposer`` (the optional local model) and its ``catalog``, the
    model's validated pick replaces the keyword pick; on any model failure
    the keyword pick is used and ``fallback_reason`` says why.
    """
    ttype, tid, hit, others = _pick_target(request or "", available)
    rationale: List[str] = []
    if hit:
        rationale.append(f"Picked {tid} because the request mentions '{hit}'.")
    else:
        rationale.append(f"No specific pipeline named; defaulting to {tid} for a T1w scan.")

    params, param_notes = _parameters_from_text(tid, request or "")
    rationale.extend(param_notes)
    proposals: Dict[str, Any] = {"rules": {"target_id": tid, "parameters": dict(params)}}
    drafted_by, fallback_reason, source = "rules", "", "request keywords"

    if proposer is not None and (request or "").strip():
        try:
            suggestion = proposer(request, catalog or [])
        except Exception as exc:  # any model failure falls back to rules
            fallback_reason = str(exc) or exc.__class__.__name__
            rationale.append(f"Local model not used ({fallback_reason}); used keyword rules.")
        else:
            proposals["model"] = {"target_id": suggestion["target_id"], "parameters": dict(suggestion["parameters"])}
            ttype, tid = suggestion["target_type"], suggestion["target_id"]
            params = dict(suggestion["parameters"])
            others = [o for o in others if o != tid]
            drafted_by, source, hit = "model", "local model", hit or "model"
            rationale = [f"Local model picked {tid}" + (f": {suggestion['reason']}" if suggestion["reason"] else ".")]
            if suggestion.get("dropped_parameters"):
                rationale.append("Ignored settings the pipeline does not have: " + ", ".join(suggestion["dropped_parameters"]))
            if proposals["rules"]["target_id"] != tid:
                rationale.append(f"Keyword rules would have picked {proposals['rules']['target_id']}.")

    instance, filled, notes = infer_instance(input_path)
    if tid in _PIPELINE_OUTPUT_LABELS:
        rationale.append(f"{tid} writes {_PIPELINE_OUTPUT_LABELS[tid]} labels.")
    rationale.extend(notes)

    for key, value in (instance_overrides or {}).items():
        instance[key] = value
        filled.pop(f"instance.{key}", None)

    filled["target_id"] = source if hit else "default"
    for key in params:
        filled[f"parameters.{key}"] = source

    if ttype == "workflow" and "subject" in instance:
        params.setdefault("subject_id", instance["subject"].removeprefix("sub-"))
        filled.setdefault("parameters.subject_id", "BIDS filename")

    return Draft(
        target_type=ttype,
        target_id=tid,
        input_files=[input_path] if input_path else [],
        parameters=params,
        instance=instance,
        filled_by=filled,
        rationale=rationale,
        alternatives=others,
        request=request or "",
        drafted_by=drafted_by,
        fallback_reason=fallback_reason,
        proposals=proposals,
    )
