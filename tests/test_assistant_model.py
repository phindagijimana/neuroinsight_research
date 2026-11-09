"""Optional local model for drafting, opt-in feedback log, and the evaluator.

A fake model server on 127.0.0.1 stands in for Ollama / an OpenAI-compatible
server, so these tests need no model download.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.assistant import feedback
from backend.assistant.drafting import draft_job
from backend.assistant.evaluate import evaluate, load_records
from backend.assistant.model import (
    ModelConfig,
    ModelUnavailable,
    build_catalog,
    is_loopback,
    make_proposer,
    model_status,
    validate_suggestion,
)

CASES = Path(__file__).resolve().parents[1] / "backend" / "assistant" / "eval_cases.yaml"
AVAILABLE = {"plugin": {"fastsurfer", "freesurfer_recon", "dcm2niix"}, "workflow": {"diffusion_full"}}
CATALOG = build_catalog([
    {"target_type": "plugin", "target_id": "fastsurfer", "name": "FastSurfer", "description": "segmentation",
     "parameters": [
         {"name": "use_cpu", "type": "bool", "description": "cpu"},
         {"name": "seg_only", "type": "bool", "description": "seg only"},
         {"name": "batch_size", "type": "int", "min_value": 1, "max_value": 8},
     ]},
    {"target_type": "plugin", "target_id": "freesurfer_recon", "name": "FreeSurfer", "description": "recon", "parameters": []},
    {"target_type": "workflow", "target_id": "diffusion_full", "name": "Diffusion", "description": "dwi", "parameters": []},
])
T1W = "/data/private-site/sub-JDOE01/anat/sub-JDOE01_T1w.nii.gz"


class FakeModel:
    """Minimal Ollama + OpenAI-compatible server that replays a canned reply."""

    def __init__(self, reply):
        self.reply = reply
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, payload):
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._send({"models": []} if self.path == "/api/tags" else {"data": []})

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((self.path, data))
                content = outer.reply if isinstance(outer.reply, str) else json.dumps(outer.reply)
                if self.path == "/api/chat":
                    self._send({"message": {"role": "assistant", "content": content}})
                else:
                    self._send({"choices": [{"message": {"role": "assistant", "content": content}}]})

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def fake_model():
    servers = []

    def start(reply):
        server = FakeModel(reply)
        servers.append(server)
        return server

    yield start
    for s in servers:
        s.close()


# ---------------------------------------------------------------------------
# Validation of model output
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_reply(self):
        s = validate_suggestion(json.dumps({"target_id": "fastsurfer", "parameters": {"use_cpu": True}, "reason": "T1"}), CATALOG)
        assert s["target_type"] == "plugin" and s["parameters"] == {"use_cpu": True}

    @pytest.mark.parametrize("raw", ["not json", "[]", json.dumps({"target_id": "none"}), json.dumps({"target_id": "rm -rf"})])
    def test_unusable_reply_raises(self, raw):
        with pytest.raises(ModelUnavailable):
            validate_suggestion(raw, CATALOG)

    def test_unknown_or_bad_parameters_are_dropped(self):
        s = validate_suggestion(json.dumps({
            "target_id": "fastsurfer",
            "parameters": {"use_cpu": "yes", "batch_size": 99, "seg_only": "true", "_proposer": "model", "rm": 1},
        }), CATALOG)
        assert s["parameters"] == {"seg_only": True}
        assert set(s["dropped_parameters"]) == {"use_cpu", "batch_size", "_proposer", "rm"}

    def test_target_type_comes_from_catalog_not_model(self):
        s = validate_suggestion(json.dumps({"target_type": "plugin", "target_id": "diffusion_full"}), CATALOG)
        assert s["target_type"] == "workflow"


# ---------------------------------------------------------------------------
# Drafting with a proposer
# ---------------------------------------------------------------------------

class TestDraftingWithModel:
    def test_model_pick_replaces_rules(self):
        proposer = lambda req, cat: {"target_type": "workflow", "target_id": "diffusion_full",
                                      "parameters": {}, "reason": "tracts", "dropped_parameters": []}
        d = draft_job("estimate white matter tracts", T1W, AVAILABLE, proposer=proposer, catalog=CATALOG)
        assert (d.target_id, d.drafted_by) == ("diffusion_full", "model")
        assert d.filled_by["target_id"] == "local model"
        assert d.proposals["rules"]["target_id"] == "fastsurfer"
        assert d.proposals["model"]["target_id"] == "diffusion_full"
        assert any("Keyword rules would have picked fastsurfer" in r for r in d.rationale)

    def test_model_failure_falls_back_to_rules(self):
        def broken(req, cat):
            raise ModelUnavailable("model server error: connection refused")
        d = draft_job("segment on cpu", T1W, AVAILABLE, proposer=broken, catalog=CATALOG)
        assert (d.target_id, d.drafted_by) == ("fastsurfer", "rules")
        assert "connection refused" in d.fallback_reason
        assert d.parameters == {"use_cpu": True}

    def test_model_never_sees_paths_or_subject(self):
        seen = []
        def spy(req, cat):
            seen.append(json.dumps([req, cat]))
            return {"target_type": "plugin", "target_id": "fastsurfer", "parameters": {}, "reason": "", "dropped_parameters": []}
        d = draft_job("segment", T1W, AVAILABLE, proposer=spy, catalog=CATALOG)
        assert d.instance["subject"] == "sub-JDOE01"
        assert "JDOE01" not in seen[0] and "private-site" not in seen[0]

    def test_metadata_still_comes_from_rules(self):
        proposer = lambda req, cat: {"target_type": "plugin", "target_id": "fastsurfer", "parameters": {},
                                      "reason": "", "dropped_parameters": []}
        d = draft_job("segment", T1W, AVAILABLE, proposer=proposer, catalog=CATALOG)
        assert d.instance["modality"] == "T1w" and d.filled_by["instance.modality"] == "BIDS suffix"


# ---------------------------------------------------------------------------
# HTTP adapters against a fake local server
# ---------------------------------------------------------------------------

class TestAdapters:
    @pytest.mark.parametrize("backend,path", [("ollama", "/api/chat"), ("openai", "/v1/chat/completions")])
    def test_round_trip(self, fake_model, backend, path):
        server = fake_model({"target_id": "freesurfer_recon", "parameters": {}, "reason": "thickness"})
        propose = make_proposer(ModelConfig(backend=backend, url=server.url, name="fake"))
        s = propose("cortical thickness", CATALOG)
        assert s["target_id"] == "freesurfer_recon"
        sent_path, body = server.requests[0]
        assert sent_path == path
        assert body["model"] == "fake"
        assert "cortical thickness" in body["messages"][-1]["content"]

    def test_garbage_reply_falls_back(self, fake_model):
        server = fake_model("I think you want FreeSurfer!")
        propose = make_proposer(ModelConfig(backend="ollama", url=server.url, name="fake"))
        d = draft_job("cortical thickness", "", AVAILABLE, proposer=propose, catalog=CATALOG)
        assert d.drafted_by == "rules" and "not JSON" in d.fallback_reason

    def test_unreachable_server_falls_back(self):
        propose = make_proposer(ModelConfig(backend="ollama", url="http://127.0.0.1:9", name="x", timeout_s=2))
        d = draft_job("segment", "", AVAILABLE, proposer=propose, catalog=CATALOG)
        assert d.drafted_by == "rules" and d.fallback_reason

    def test_remote_url_refused_by_default(self):
        propose = make_proposer(ModelConfig(backend="openai", url="https://api.example.com", name="x"))
        with pytest.raises(ModelUnavailable, match="not on this machine"):
            propose("segment", CATALOG)

    def test_off_by_default(self):
        assert make_proposer(ModelConfig()) is None
        assert make_proposer(ModelConfig(backend="ollama")) is None

    def test_status(self, fake_model):
        server = fake_model("{}")
        assert model_status(ModelConfig(backend="ollama", url=server.url, name="m"))["reachable"] is True
        assert model_status(ModelConfig(backend="ollama", url="http://127.0.0.1:9", name="m"))["reachable"] is False
        assert model_status(ModelConfig())["reachable"] is None

    @pytest.mark.parametrize("url,local", [
        ("http://127.0.0.1:11434", True), ("http://localhost:8080", True), ("http://[::1]:1", True),
        ("http://10.0.0.5:11434", False), ("https://api.example.com", False),
    ])
    def test_loopback(self, url, local):
        assert is_loopback(url) is local


# ---------------------------------------------------------------------------
# Opt-in feedback log
# ---------------------------------------------------------------------------

class TestFeedback:
    def test_record_strips_paths_and_subject(self):
        original = draft_job("segment", T1W, AVAILABLE)
        final = draft_job("segment", T1W, AVAILABLE)
        final.parameters["use_cpu"] = True
        final.instance["space"] = "MNI152NLin2009cAsym"
        rec = feedback.build_record(original, final, "job-1")
        text = json.dumps(rec)
        assert "JDOE01" not in text and "private-site" not in text
        assert rec["edited_fields"] == ["parameters.use_cpu", "instance.space"]
        assert rec["final"]["target_id"] == "fastsurfer"

    def test_target_change_is_an_edit(self):
        original = draft_job("segment", "", AVAILABLE)
        final = draft_job("cortical thickness", "", AVAILABLE)
        assert "target_id" in feedback.build_record(original, final, None)["edited_fields"]

    def test_append_and_load(self, tmp_dir):
        path = feedback.feedback_path(str(tmp_dir))
        feedback.append({"request": "a", "final": {"target_id": "fastsurfer"}}, path)
        feedback.append({"request": "b", "final": {"target_id": "dcm2niix"}}, path)
        assert [r["request"] for r in feedback.load(path)] == ["a", "b"]


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    with patch("backend.core.database.engine", MagicMock()), \
         patch("backend.core.database.SessionLocal", MagicMock()), \
         patch("backend.core.storage.storage", MagicMock()):
        from backend.main import app
        yield TestClient(app)


class TestRoutes:
    def _approve(self, client, body):
        with patch("backend.main.get_backend", return_value=MagicMock()), \
             patch("backend.main._check_licenses"), \
             patch("backend.main._enforce_disk_guard_for_submission"), \
             patch("backend.assistant.gates.find_gate", return_value=None):
            return client.post("/api/assistant/approve", json=body)

    def test_feedback_saved_only_with_consent(self, client, tmp_dir, sample_nifti, monkeypatch):
        from backend.core.config import get_settings
        monkeypatch.setattr(get_settings(), "data_dir", str(tmp_dir))
        original = draft_job("segment", sample_nifti, AVAILABLE).to_dict()
        final = {**original, "parameters": {"use_cpu": True}}
        path = feedback.feedback_path(str(tmp_dir))

        assert self._approve(client, {"draft": final, "original_draft": original}).status_code == 200
        assert not path.exists()

        assert self._approve(client, {"draft": final, "original_draft": original, "save_feedback": True}).status_code == 200
        records = list(feedback.load(path))
        assert len(records) == 1 and records[0]["edited_fields"] == ["parameters.use_cpu"]
        assert sample_nifti not in json.dumps(records[0])

    def test_draft_uses_configured_model(self, client, fake_model, monkeypatch):
        from backend.core.config import get_settings
        server = fake_model({"target_id": "diffusion_full", "parameters": {}, "reason": "tracts"})
        s = get_settings()
        monkeypatch.setattr(s, "assistant_model_backend", "ollama")
        monkeypatch.setattr(s, "assistant_model_url", server.url)
        monkeypatch.setattr(s, "assistant_model_name", "fake")
        with patch("backend.assistant.gates.find_gate", return_value=None):
            data = client.post("/api/assistant/draft", json={"request": "estimate white matter tracts"}).json()
        assert data["draft"]["drafted_by"] == "model"
        assert data["draft"]["target_id"] == "diffusion_full"
        status = client.get("/api/assistant/status").json()
        assert status["mode"] == "local_model" and status["model"]["reachable"] is True

    def test_rules_only_by_default(self, client):
        status = client.get("/api/assistant/status").json()
        assert status["mode"] == "rules" and status["model"]["backend"] is None


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class TestEvaluate:
    def test_authored_cases_name_real_targets(self):
        from backend.core.plugin_registry import get_plugin_workflow_registry
        from backend.assistant.catalog import available_targets

        available = available_targets(get_plugin_workflow_registry())
        ids = available["plugin"] | available["workflow"]
        for case in load_records(CASES):
            assert case["final"]["target_id"] in ids, case

    def test_scores_rules_and_model(self):
        from backend.core.plugin_registry import get_plugin_workflow_registry

        records = load_records(CASES)
        answers = {r["request"]: r["final"] for r in records}
        catalog_ids = {}

        def oracle(req, catalog):
            catalog_ids.update({c["target_id"]: c["target_type"] for c in catalog})
            final = answers[req]
            return {"target_type": catalog_ids[final["target_id"]], "target_id": final["target_id"],
                    "parameters": final.get("parameters", {}), "reason": "", "dropped_parameters": []}

        report = evaluate(records, get_plugin_workflow_registry(), oracle)
        assert report["model"]["target_and_params_match"] == report["model"]["n"] == len(records)
        assert report["model"]["fell_back_to_rules"] == 0
        assert 0 <= report["rules"]["target_match"] <= len(records)
        assert len(report["rules"]["rows"]) == len(records)
