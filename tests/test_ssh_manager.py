"""
Tests for the SSH connection manager.
"""
import time
import pytest
from unittest.mock import MagicMock, patch


class TestSSHManager:
    """Test SSHManager configuration, connection, and idle timeout."""

    def test_configure(self):
        """configure() stores connection parameters."""
        from backend.core.ssh_manager import SSHManager
        mgr = SSHManager()
        mgr.configure(host="hpc.test.edu", username="testuser", port=2222, idle_timeout=600)
        assert mgr.host == "hpc.test.edu"
        assert mgr.username == "testuser"
        assert mgr.port == 2222
        assert mgr.idle_timeout == 600

    def test_not_connected_by_default(self):
        """Manager is not connected after init."""
        from backend.core.ssh_manager import SSHManager
        mgr = SSHManager()
        assert mgr.is_connected is False

    def test_connection_info_when_disconnected(self):
        """Connection info reflects disconnected state."""
        from backend.core.ssh_manager import SSHManager
        mgr = SSHManager()
        info = mgr.connection_info
        assert info["connected"] is False
        assert info["host"] is None

    def test_connection_info_idle_timeout_field(self):
        """Connection info includes idle timeout fields."""
        from backend.core.ssh_manager import SSHManager
        mgr = SSHManager()
        mgr.configure(host="test", username="user", idle_timeout=900)
        info = mgr.connection_info
        assert info["idle_timeout_seconds"] == 900

    @patch("backend.core.ssh_manager.paramiko.SSHClient")
    def test_connect_success(self, mock_ssh_cls):
        """Connect succeeds when paramiko client connects."""
        from backend.core.ssh_manager import SSHManager
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_cls.return_value = mock_client

        mgr = SSHManager()
        mgr.configure(host="test.host", username="user")
        mgr.connect()

        mock_client.connect.assert_called_once()
        assert mgr._connected is True

    @patch("backend.core.ssh_manager.paramiko.SSHClient")
    def test_disconnect(self, mock_ssh_cls):
        """Disconnect cleans up client and state."""
        from backend.core.ssh_manager import SSHManager
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_cls.return_value = mock_client

        mgr = SSHManager()
        mgr.configure(host="test.host", username="user")
        mgr.connect()
        mgr.disconnect()

        assert mgr._connected is False

    @patch("backend.core.ssh_manager.paramiko.SSHClient")
    def test_idle_timer_created_on_connect(self, mock_ssh_cls):
        """Idle timer is created when idle_timeout > 0."""
        from backend.core.ssh_manager import SSHManager
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_cls.return_value = mock_client

        mgr = SSHManager()
        mgr.configure(host="test.host", username="user", idle_timeout=60)
        mgr.connect()

        assert mgr._idle_timer is not None
        mgr.disconnect()

    @patch("backend.core.ssh_manager.paramiko.SSHClient")
    def test_idle_timer_not_created_when_disabled(self, mock_ssh_cls):
        """No idle timer when idle_timeout is 0."""
        from backend.core.ssh_manager import SSHManager
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_client.get_transport.return_value = mock_transport
        mock_ssh_cls.return_value = mock_client

        mgr = SSHManager()
        mgr.configure(host="test.host", username="user", idle_timeout=0)
        mgr.connect()

        assert mgr._idle_timer is None
        mgr.disconnect()


class TestSSHManagerExceptions:
    """Test error handling in SSHManager."""

    def test_execute_without_connect_raises(self):
        """Execute raises when not connected."""
        from backend.core.ssh_manager import SSHManager, SSHConnectionError
        mgr = SSHManager()
        with pytest.raises(SSHConnectionError):
            mgr.execute("ls")

    def test_put_file_without_connect_raises(self):
        """SFTP operations raise when not connected."""
        from backend.core.ssh_manager import SSHManager, SSHConnectionError
        mgr = SSHManager()
        with pytest.raises(SSHConnectionError):
            mgr.put_file("/local/file", "/remote/file")
