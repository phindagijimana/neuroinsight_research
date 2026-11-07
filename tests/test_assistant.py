"""Job-drafting assistant: drafts and checks, never submits on its own."""
import ast
import json
import shutil
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.assistant.drafting import Draft, draft_job, infer_instance
from backend.assistant import gates

ASSISTANT_DIR = Path(__file__).resolve().parents[1] / "backend" / "assistant"
AVAILABLE = {
    "plugin": {"fastsurfer", "freesurfer_recon", "dcm2niix"},
    "workflow": {"diffusion_full", "hippo_subfields_t1", "fmri_full"},
}


@pytest.fixture
def t1w(tmp_dir):
    anat = tmp_dir / "ds000003" / "sub-01" / "anat"
    anat.mkdir(parents=True)
    path = anat / "sub-01_T1w.nii.gz"
    path.write_bytes(b"\x1f\x8b" + b"\x00" * 64)
    return str(path)


@pytest.fixture
def bin_dir():
    """Executable scratch dir; /tmp may be mounted noexec."""
    folder = Path(tempfile.mkdtemp(dir=Path(__file__).resolve().parent, prefix=".fake_gates_"))
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


def _fake_gate(folder: Path, name: str, payload: dict) -> None:
    script = folder / name
    script.write_text("#!/bin/sh\ncat <<'EOF'\n" + json.dumps(payload) + "\nEOF\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def no_gates(monkeypatch):
    monkeypatch.setattr(gates, "find_gate", lambda name: None)


# ---------------------------------------------------------------------------
# Drafting
# ---------------------------------------------------------------------------

class TestDrafting:
    def test_segmentation_request_drafts_fastsurfer(self, t1w):
        d = draft_job("segment this brain on my laptop, no GPU", t1w, AVAILABLE)
        assert (d.target_type, d.target_id) == ("plugin", "fastsurfer")
        assert d.parameters == {"use_cpu": True}
        assert d.filled_by["parameters.use_cpu"] == "request keywords"
        assert d.input_files == [t1w]

    def test_output_labels_are_explained_not_bound_to_input(self, t1w):
        d = draft_job("fastsurfer", t1w, AVAILABLE)
        assert "label_set" not in d.instance and "atlas" not in d.instance
        assert any("DKT" in r for r in d.rationale)

    def test_specific_intents_win(self, t1w):
        assert draft_job("hippocampal subfield volumes", t1w, AVAILABLE).target_id == "hippo_subfields_t1"
        assert draft_job("DWI tractography connectome", "/x/bids", AVAILABLE).target_id == "diffusion_full"
        assert draft_job("cortical thickness with freesurfer", t1w, AVAILABLE).target_id == "freesurfer_recon"

    def test_unavailable_target_is_never_drafted(self, t1w):
        d = draft_job("diffusion please", t1w, {"plugin": {"fastsurfer"}, "workflow": set()})
        assert d.target_id == "fastsurfer"

    def test_bids_raw_t1w_metadata(self, t1w):
        instance, filled, notes = infer_instance(t1w)
        assert instance["modality"] == "T1w"
        assert instance["space"] == "subject_native"
        assert instance["subject"] == "sub-01"
        assert "instance.space" in filled
        assert notes == []

    def test_non_bids_name_leaves_space_unknown(self, tmp_dir):
        path = tmp_dir / "scan.nii.gz"
        path.write_bytes(b"\x1f\x8b")
        instance, _, notes = infer_instance(str(path))
        assert "space" not in instance and "modality" not in instance
        assert any("ABSTAIN" in n for n in notes)

    def test_sidecar_overrides_filename(self, t1w):
        Path(t1w.replace(".nii.gz", ".json")).write_text(json.dumps({"space": "MNI152NLin2009cAsym"}))
        instance, filled, _ = infer_instance(t1w)
        assert instance["space"] == "MNI152NLin2009cAsym"
        assert filled["instance.space"] == "JSON sidecar"

    def test_user_override_clears_assistant_marker(self, t1w):
        d = draft_job("fastsurfer", t1w, AVAILABLE, {"space": "subject_native"})
        assert "instance.space" not in d.filled_by

    def test_draft_round_trips(self, t1w):
        d = draft_job("fastsurfer", t1w, AVAILABLE)
        assert Draft.from_dict({**d.to_dict(), "unexpected": 1}) == d


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

class TestChecks:
    def test_missing_gates_are_not_run_not_pass(self, t1w, no_gates):
        checks = gates.run_checks(draft_job("fastsurfer", t1w, AVAILABLE))
        by_gate = {c["gate"]: c for c in checks}
        assert by_gate["scicap"]["status"] == "not_run"
        assert by_gate["sciguard"]["status"] == "not_run"
        assert not gates.is_blocked(checks)

    def test_no_input_blocks(self, no_gates):
        checks = gates.run_checks(draft_job("fastsurfer", "", AVAILABLE))
        assert gates.is_blocked(checks)

    @pytest.mark.parametrize("decision,blocked", [("ALLOW", False), ("ABSTAIN", True), ("REJECT", True)])
    def test_scicap_decision_maps_to_blocking(self, t1w, bin_dir, monkeypatch, decision, blocked):
        _fake_gate(bin_dir, "scicap", {"decision": decision, "reason": "fake", "missing": []})
        monkeypatch.setenv("NIR_GATES_BIN", str(bin_dir))
        check = gates.check_scicap(draft_job("fastsurfer", t1w, AVAILABLE))
        assert check["status"] == decision
        assert check["blocking"] is blocked

    def test_sciguard_fail_blocks(self, bin_dir, monkeypatch):
        _fake_gate(bin_dir, "sciguard", {
            "graph_status": "reject",
            "edges": [{"id": "e", "status": "FAIL", "rule": "RULE-SPACE-002", "reason": "no transform"}],
        })
        monkeypatch.setenv("NIR_GATES_BIN", str(bin_dir))
        check = gates.check_sciguard(draft_job("diffusion", "/x/sub-01_dwi.nii.gz", AVAILABLE))
        assert check["status"] == "FAIL" and check["blocking"]
        assert "RULE-SPACE-002" in check["reason"]

    def test_capability_only_for_mapped_targets(self, no_gates):
        d = draft_job("fmri", "/x/bids", AVAILABLE)
        assert "No SciCap capability" in gates.check_scicap(d)["reason"]


REAL_SCICAP = gates.find_gate("scicap")
REAL_SCIGUARD = gates.find_gate("sciguard")


@pytest.mark.skipif(not (REAL_SCICAP and REAL_SCIGUARD), reason="scicap/sciguard CLIs not installed")
class TestRealGates:
    def test_bids_t1w_is_allowed(self, t1w):
        assert gates.check_scicap(draft_job("fastsurfer", t1w, AVAILABLE))["status"] == "ALLOW"

    def test_unknown_space_abstains(self, tmp_dir):
        path = tmp_dir / "scan_T1w.nii.gz"
        path.write_bytes(b"\x1f\x8b")
        d = draft_job("fastsurfer", str(path), AVAILABLE, {"modality": "T1w"})
        check = gates.check_scicap(d)
        assert check["status"] == "ABSTAIN" and "space" in check["missing"]

    def test_atlas_contradiction_rejects(self, t1w):
        d = draft_job("fastsurfer", t1w, AVAILABLE, {"atlas": "DKT", "label_set": "DK"})
        assert gates.check_scicap(d)["status"] == "REJECT"

    def test_diffusion_annotation_validates(self):
        d = draft_job("diffusion", "/x/sub-01/dwi/sub-01_dwi.nii.gz", AVAILABLE)
        check = gates.check_sciguard(d)
        assert check["status"] in {"PASS", "UNKNOWN", "NEEDS_REVIEW"}
        assert not check["blocking"]

    def test_annotation_without_transform_fails(self, tmp_dir):
        annotation = (ASSISTANT_DIR / "annotations" / "diffusion_full.yaml").read_text()
        cut = annotation.split("  - id: xfm")[0]
        (tmp_dir / "diffusion_full.yaml").write_text(cut)
        d = draft_job("diffusion", "/x/sub-01/dwi/sub-01_dwi.nii.gz", AVAILABLE)
        check = gates.check_sciguard(d, annotations_dir=tmp_dir)
        assert check["status"] == "FAIL" and check["blocking"]


# ---------------------------------------------------------------------------
# Boundary: the assistant package cannot submit
# ---------------------------------------------------------------------------

def test_assistant_package_does_not_import_execution():
    forbidden = ("backend.execution", "backend.main", "backend.core.execution", "backend.routes")
    for path in ASSISTANT_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(forbidden), f"{path.name} imports {name}"
        assert "submit_job" not in path.read_text(), path.name


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with patch("backend.core.database.engine", MagicMock()), \
         patch("backend.core.database.SessionLocal", MagicMock()), \
         patch("backend.core.storage.storage", MagicMock()):
        from backend.main import app
        yield TestClient(app)


class TestRoutes:
    def test_config_exposes_flag(self, client):
        assert client.get("/api/config").json()["features"]["assistant_enabled"] is True

    def test_status_says_it_cannot_submit(self, client):
        data = client.get("/api/assistant/status").json()
        assert data["can_submit"] is False and data["model_api"] is None

    def test_draft_then_explain(self, client, t1w, no_gates):
        data = client.post("/api/assistant/draft", json={"request": "segment", "input_path": t1w}).json()
        assert data["draft"]["target_id"] == "fastsurfer"
        assert {c["gate"] for c in data["checks"]} == {"inputs", "scicap", "sciguard"}
        info = client.get("/api/assistant/explain/plugin/fastsurfer").json()
        assert info["needs_freesurfer_license"] is True
        assert any(p["name"] == "use_cpu" for p in info["parameters"])

    def test_recheck_rejects_unknown_target(self, client, no_gates):
        bad = {"target_type": "plugin", "target_id": "nope", "input_files": ["/x"]}
        assert client.post("/api/assistant/recheck", json={"draft": bad}).status_code == 404

    def test_approve_refused_when_blocked(self, client, no_gates):
        draft = draft_job("fastsurfer", "", AVAILABLE).to_dict()
        with patch("backend.main.get_backend") as get_backend:
            resp = client.post("/api/assistant/approve", json={"draft": draft})
        assert resp.status_code == 409
        get_backend.assert_not_called()

    def test_approve_submits_through_plugin_endpoint(self, client, t1w, no_gates):
        draft = draft_job("segment, cpu only", t1w, AVAILABLE).to_dict()
        backend = MagicMock()
        with patch("backend.main.get_backend", return_value=backend), \
             patch("backend.main._check_licenses"), \
             patch("backend.main._enforce_disk_guard_for_submission"), \
             patch("backend.core.audit.audit_log") as audit:
            resp = client.post("/api/assistant/approve", json={"draft": draft, "approved_by": "tester"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["proposer"] == "assistant" and body["approved_by"] == "tester"
        spec = backend.submit_job.call_args.args[0]
        assert spec.plugin_id == "fastsurfer"
        assert spec.parameters["use_cpu"] is True
        assert spec.parameters["_proposer"] == "assistant"
        assert spec.parameters["_approved_by"] == "tester"
        events = [c.args[0] for c in audit.record.call_args_list]
        assert "assistant_draft_approved" in events

    def test_turned_off_assistant_404s(self, client, t1w, monkeypatch):
        from backend.core.config import get_settings
        monkeypatch.setattr(get_settings(), "assistant_enabled", False)
        assert client.post("/api/assistant/draft", json={"input_path": t1w}).status_code == 404
