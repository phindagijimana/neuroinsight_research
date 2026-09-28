"""Tests for Pennsieve Agent profile auto-provisioning.

These verify that a fresh environment (e.g. the all-in-one container) gets a
usable ~/.pennsieve/config.ini from the connected API credentials, while an
existing user profile is never clobbered. HOME is redirected to a tmp dir so
the real ~/.pennsieve is untouched.
"""

import configparser
import os
import stat
from pathlib import Path

from backend.connectors.pennsieve import (
    PennsieveConnector,
    PENNSIEVE_AGENT_DEFAULT_PORT,
)


def _connector_with_creds():
    c = PennsieveConnector()
    c._api_key = "KEYABC"
    c._api_secret = "SECRETXYZ"
    return c


def test_provisions_profile_when_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    c = _connector_with_creds()

    c._ensure_agent_profile("127.0.0.1:11285")

    cfg = tmp_path / ".pennsieve" / "config.ini"
    assert cfg.exists()
    parsed = configparser.ConfigParser()
    parsed.read(cfg)
    assert parsed["global"]["default_profile"] == "neuroinsight"
    assert parsed["neuroinsight"]["api_token"] == "KEYABC"
    assert parsed["neuroinsight"]["api_secret"] == "SECRETXYZ"
    assert parsed["agent"]["port"] == "11285"


def test_profile_file_is_owner_only(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    c = _connector_with_creds()

    c._ensure_agent_profile("127.0.0.1:11235")

    cfg = tmp_path / ".pennsieve" / "config.ini"
    assert stat.S_IMODE(os.stat(cfg).st_mode) == 0o600


def test_does_not_clobber_existing_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = tmp_path / ".pennsieve" / "config.ini"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("[global]\ndefault_profile=philbert\n")

    c = _connector_with_creds()
    c._ensure_agent_profile("127.0.0.1:11235")

    assert "philbert" in cfg.read_text()
    assert "neuroinsight" not in cfg.read_text()


def test_noop_without_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    c = PennsieveConnector()  # no creds set

    c._ensure_agent_profile("127.0.0.1:11235")

    assert not (tmp_path / ".pennsieve" / "config.ini").exists()


def test_falls_back_to_default_port_on_bad_target(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    c = _connector_with_creds()

    c._ensure_agent_profile("not-a-valid-target::::")

    cfg = tmp_path / ".pennsieve" / "config.ini"
    parsed = configparser.ConfigParser()
    parsed.read(cfg)
    assert parsed["agent"]["port"] == str(PENNSIEVE_AGENT_DEFAULT_PORT)
