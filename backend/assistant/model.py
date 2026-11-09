"""Optional local language model that proposes the pipeline and settings.

The model fills the same fields the keyword rules fill. Its output is
validated against the registry (known target, known parameter, right type and
range); anything else is discarded and the rules are used instead. It receives
only the user's request text and the pipeline catalog: no file paths, subject
IDs, or image bytes. Checks and approval are unchanged.
"""
from __future__ import annotations

import ipaddress
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

SYSTEM_PROMPT = (
    "You map a neuroimaging request to one pipeline from a catalog. "
    "Reply with JSON only: "
    '{"target_type": "plugin"|"workflow", "target_id": "<id from catalog>", '
    '"parameters": {"<name>": <value>}, "reason": "<one short sentence>"}. '
    "Only use target ids and parameter names that appear in the catalog. "
    "Only set a parameter when the request asks for it. "
    'If no pipeline fits, use "target_id": "none".'
)


class ModelUnavailable(RuntimeError):
    """The model is off, unreachable, or answered with something unusable."""


@dataclass
class ModelConfig:
    backend: str = ""
    url: str = "http://127.0.0.1:11434"
    name: str = ""
    timeout_s: float = 60.0
    allow_remote: bool = False

    @property
    def enabled(self) -> bool:
        return self.backend in ("ollama", "openai") and bool(self.name)

    @classmethod
    def from_settings(cls) -> "ModelConfig":
        from backend.core.config import get_settings

        s = get_settings()
        return cls(
            backend=(s.assistant_model_backend or "").strip().lower(),
            url=s.assistant_model_url,
            name=s.assistant_model_name,
            timeout_s=s.assistant_model_timeout_s,
            allow_remote=s.assistant_model_allow_remote,
        )


def is_loopback(url: str) -> bool:
    host = urlparse(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def build_catalog(targets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Trim registry entries to what the model needs to choose."""
    catalog = []
    for t in targets:
        catalog.append({
            "target_type": t["target_type"],
            "target_id": t["target_id"],
            "name": t.get("name", ""),
            "description": " ".join((t.get("description") or "").split())[:240],
            "parameters": [
                {k: p[k] for k in ("name", "type", "description", "min_value", "max_value", "options") if k in p}
                for p in t.get("parameters", [])
            ],
        })
    return catalog


def build_messages(request: str, catalog: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    user = "Catalog:\n" + json.dumps(catalog, separators=(",", ":")) + "\n\nRequest:\n" + request.strip()
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def _post_json(url: str, body: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(
        url, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise ModelUnavailable(f"model server error: {exc}") from exc


def _call(cfg: ModelConfig, messages: List[Dict[str, str]]) -> str:
    base = cfg.url.rstrip("/")
    if cfg.backend == "ollama":
        data = _post_json(
            f"{base}/api/chat",
            {"model": cfg.name, "messages": messages, "stream": False, "format": "json",
             "options": {"temperature": 0}},
            cfg.timeout_s,
        )
        return (data.get("message") or {}).get("content", "")
    data = _post_json(
        f"{base}/v1/chat/completions",
        {"model": cfg.name, "messages": messages, "temperature": 0,
         "response_format": {"type": "json_object"}},
        cfg.timeout_s,
    )
    choices = data.get("choices") or [{}]
    return (choices[0].get("message") or {}).get("content", "")


def _coerce(value: Any, spec: Dict[str, Any]) -> Any:
    kind = spec.get("type")
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise ValueError("not a bool")
    if kind in ("int", "float"):
        if isinstance(value, bool):
            raise ValueError("bool given for number")
        number = int(value) if kind == "int" else float(value)
        if "min_value" in spec and number < spec["min_value"]:
            raise ValueError("below min")
        if "max_value" in spec and number > spec["max_value"]:
            raise ValueError("above max")
        return number
    if kind == "choice":
        if value not in (spec.get("options") or []):
            raise ValueError("not an allowed option")
        return value
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value)
    raise ValueError("unsupported value")


def validate_suggestion(raw: str, catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Parse the model reply; raise ModelUnavailable unless it names a real target."""
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ModelUnavailable("model reply was not JSON") from exc
    if not isinstance(data, dict):
        raise ModelUnavailable("model reply was not a JSON object")

    target_id = str(data.get("target_id", ""))
    entry = next((c for c in catalog if c["target_id"] == target_id), None)
    if entry is None:
        raise ModelUnavailable(f"model picked an unknown pipeline: {target_id or 'none'}")

    specs = {p["name"]: p for p in entry["parameters"]}
    params: Dict[str, Any] = {}
    dropped: List[str] = []
    raw_params = data.get("parameters") or {}
    if isinstance(raw_params, dict):
        for name, value in raw_params.items():
            if name not in specs:
                dropped.append(name)
                continue
            try:
                params[name] = _coerce(value, specs[name])
            except (ValueError, TypeError):
                dropped.append(name)

    reason = data.get("reason")
    return {
        "target_type": entry["target_type"],
        "target_id": target_id,
        "parameters": params,
        "reason": reason if isinstance(reason, str) else "",
        "dropped_parameters": dropped,
    }


Proposer = Callable[[str, List[Dict[str, Any]]], Dict[str, Any]]


def make_proposer(cfg: Optional[ModelConfig] = None) -> Optional[Proposer]:
    """Return a callable (request, catalog) -> suggestion, or None when off."""
    cfg = cfg or ModelConfig.from_settings()
    if not cfg.enabled:
        return None

    def propose(request: str, catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not cfg.allow_remote and not is_loopback(cfg.url):
            raise ModelUnavailable("model URL is not on this machine; set assistant_model_allow_remote to permit it")
        return validate_suggestion(_call(cfg, build_messages(request, catalog)), catalog)

    return propose


def model_status(cfg: Optional[ModelConfig] = None) -> Dict[str, Any]:
    cfg = cfg or ModelConfig.from_settings()
    status: Dict[str, Any] = {
        "backend": cfg.backend or None,
        "name": cfg.name or None,
        "local": is_loopback(cfg.url),
        "reachable": None,
    }
    if not cfg.enabled:
        return status
    probe = "/api/tags" if cfg.backend == "ollama" else "/v1/models"
    try:
        with urllib.request.urlopen(cfg.url.rstrip("/") + probe, timeout=3) as resp:
            status["reachable"] = resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        status["reachable"] = False
    return status
