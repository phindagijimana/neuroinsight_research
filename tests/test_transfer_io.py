"""Tests for large-file transfer helpers."""

from unittest.mock import MagicMock

import pytest

from backend.core import transfer_settings as ts
from backend.core.transfer_io import (
    destination_complete,
    shell_single_quote,
)


class TestShellQuote:
    def test_simple(self):
        assert shell_single_quote("hello") == "'hello'"

    def test_embedded_single_quote(self):
        assert shell_single_quote("a'b") == """'a'"'"'b'"""


class TestDestinationComplete:
    def test_skip_when_sizes_match_local(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts, "SKIP_COMPLETE_FILES", True)
        f = tmp_path / "big.bin"
        f.write_bytes(b"x" * 100)
        assert destination_complete(local_path=str(f), expected_size=100)

    def test_no_skip_when_size_differs(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts, "SKIP_COMPLETE_FILES", True)
        f = tmp_path / "partial.bin"
        f.write_bytes(b"x" * 50)
        assert not destination_complete(local_path=str(f), expected_size=100)

    def test_no_skip_without_expected_size(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts, "SKIP_COMPLETE_FILES", True)
        f = tmp_path / "unknown.bin"
        f.write_bytes(b"x" * 50)
        assert not destination_complete(local_path=str(f), expected_size=None)

    def test_remote_complete(self, monkeypatch):
        monkeypatch.setattr(ts, "SKIP_COMPLETE_FILES", True)
        ssh = MagicMock()
        ssh.execute.return_value = (0, "4096", "")
        assert destination_complete(
            ssh=ssh, remote_path="/scratch/huge.nii.gz", expected_size=4096
        )

    def test_disabled_skip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts, "SKIP_COMPLETE_FILES", False)
        f = tmp_path / "done.bin"
        f.write_bytes(b"x" * 10)
        assert not destination_complete(local_path=str(f), expected_size=10)


class TestCopyLocal:
    def test_skip_complete_dest(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts, "SKIP_COMPLETE_FILES", True)
        src = tmp_path / "a.bin"
        dest = tmp_path / "b.bin"
        src.write_bytes(b"12345")
        dest.write_bytes(b"12345")
        from backend.core.transfer_io import copy_local_file

        copy_local_file(str(src), str(dest))
        assert dest.read_bytes() == b"12345"


class TestPlatformDownload:
    def test_skips_when_complete(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ts, "SKIP_COMPLETE_FILES", True)
        dest = tmp_path / "f.nii.gz"
        dest.write_bytes(b"x" * 10)
        connector = MagicMock()
        from backend.core.transfer_io import platform_download_file

        platform_download_file(connector, "id1", str(dest), expected_size=10)
        connector.download_file.assert_not_called()
        connector.get_download_info.assert_not_called()


class TestTransferSettings:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("NIR_TRANSFER_CURL_TIMEOUT_SEC", raising=False)
        assert ts.CURL_TIMEOUT_SEC >= 86400

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("NIR_TRANSFER_CURL_TIMEOUT_SEC", "172800")
        from importlib import reload
        import backend.core.transfer_settings as settings_mod
        reload(settings_mod)
        assert settings_mod.CURL_TIMEOUT_SEC == 172800
