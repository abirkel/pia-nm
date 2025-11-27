"""Unit tests for token refresh module.

Tests cover:
- Live refresh for active connections
- Saved profile update for inactive connections
- No delete/recreate operations
- Active connection preservation
- Refresh logging
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call

# Mock gi.repository before importing token_refresh
import sys

sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

# Create mock NM module
mock_nm = MagicMock()
sys.modules["gi.repository.NM"] = mock_nm

from pia_nm.token_refresh import (
    is_connection_active,
    get_connection_settings,
    update_wireguard_settings,
    get_applied_connection_with_version,
    refresh_active_connection,
    refresh_inactive_connection,
)


class TestIsConnectionActive:
    """Test connection active status checking."""

    def test_is_connection_active_returns_true_when_active(self):
        """Test that is_connection_active returns True for active connections."""
        mock_nm_client = MagicMock()
        mock_active_conn = MagicMock()
        mock_nm_client.get_active_connection.return_value = mock_active_conn

        result = is_connection_active(mock_nm_client, "test-conn")

        assert result is True
        mock_nm_client.get_active_connection.assert_called_once_with("test-conn")

    def test_is_connection_active_returns_false_when_inactive(self):
        """Test that is_connection_active returns False for inactive connections."""
        mock_nm_client = MagicMock()
        mock_nm_client.get_active_connection.return_value = None

        result = is_connection_active(mock_nm_client, "test-conn")

        assert result is False
        mock_nm_client.get_active_connection.assert_called_once_with("test-conn")


class TestGetConnectionSettings:
    """Test connection settings retrieval."""

    def test_get_connection_settings_for_active_connection(self):
        """Test getting settings for an active connection."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_active_conn = MagicMock()
        mock_nm_client.get_active_connection.return_value = mock_active_conn

        mock_device = MagicMock()
        mock_nm_client.get_device_for_connection.return_value = mock_device

        mock_settings = {"wireguard": {"private-key": "test_key"}}
        mock_nm_client.get_applied_connection.return_value = (mock_settings, 1)

        result = get_connection_settings(mock_nm_client, mock_connection)

        assert result == mock_settings
        mock_nm_client.get_applied_connection.assert_called_once_with(mock_device)

    def test_get_connection_settings_for_inactive_connection(self):
        """Test getting settings for an inactive connection."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_nm_client.get_active_connection.return_value = None

        mock_settings = {"wireguard": {"private-key": "test_key"}}
        mock_connection.to_dbus.return_value = mock_settings

        result = get_connection_settings(mock_nm_client, mock_connection)

        assert result == mock_settings
        mock_connection.to_dbus.assert_called_once()

    def test_get_connection_settings_returns_none_when_device_not_found(self):
        """Test that get_connection_settings returns None when device not found."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_active_conn = MagicMock()
        mock_nm_client.get_active_connection.return_value = mock_active_conn
        mock_nm_client.get_device_for_connection.return_value = None

        result = get_connection_settings(mock_nm_client, mock_connection)

        assert result is None


class TestUpdateWireGuardSettings:
    """Test WireGuard settings update."""

    def test_update_wireguard_settings_updates_private_key(self):
        """Test that update_wireguard_settings updates the private key."""
        settings = {
            "wireguard": {"private-key": "old_key", "peers": [{"endpoint": "old_endpoint:1337"}]}
        }

        result = update_wireguard_settings(settings, "new_key", "new_endpoint:1337")

        assert result["wireguard"]["private-key"] == "new_key"
        # Original settings should not be modified
        assert settings["wireguard"]["private-key"] == "old_key"

    def test_update_wireguard_settings_updates_endpoint(self):
        """Test that update_wireguard_settings updates the endpoint."""
        settings = {
            "wireguard": {"private-key": "test_key", "peers": [{"endpoint": "old_endpoint:1337"}]}
        }

        result = update_wireguard_settings(settings, "new_key", "new_endpoint:1337")

        assert result["wireguard"]["peers"][0]["endpoint"] == "new_endpoint:1337"
        # Original settings should not be modified
        assert settings["wireguard"]["peers"][0]["endpoint"] == "old_endpoint:1337"

    def test_update_wireguard_settings_preserves_other_settings(self):
        """Test that update_wireguard_settings preserves other settings."""
        settings = {
            "wireguard": {
                "private-key": "old_key",
                "fwmark": 51820,
                "peers": [{"endpoint": "old_endpoint:1337", "allowed-ips": "0.0.0.0/0"}],
            },
            "ipv4": {"method": "manual"},
        }

        result = update_wireguard_settings(settings, "new_key", "new_endpoint:1337")

        # Verify other settings are preserved
        assert result["wireguard"]["fwmark"] == 51820
        assert result["wireguard"]["peers"][0]["allowed-ips"] == "0.0.0.0/0"
        assert result["ipv4"]["method"] == "manual"

    def test_update_wireguard_settings_raises_when_no_wireguard_config(self):
        """Test that update_wireguard_settings raises ValueError when no WireGuard config."""
        settings = {"ipv4": {"method": "manual"}}

        with pytest.raises(ValueError, match="do not contain WireGuard configuration"):
            update_wireguard_settings(settings, "new_key", "new_endpoint:1337")


class TestGetAppliedConnectionWithVersion:
    """Test getting applied connection with version ID."""

    def test_get_applied_connection_with_version_success(self):
        """Test successful retrieval of applied connection with version ID."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_device = MagicMock()
        mock_nm_client.get_device_for_connection.return_value = mock_device

        mock_settings = {"wireguard": {"private-key": "test_key"}}
        mock_version_id = 5
        mock_nm_client.get_applied_connection.return_value = (mock_settings, mock_version_id)

        result = get_applied_connection_with_version(mock_nm_client, mock_connection)

        assert result == (mock_settings, mock_version_id)
        mock_nm_client.get_device_for_connection.assert_called_once_with(mock_connection)
        mock_nm_client.get_applied_connection.assert_called_once_with(mock_device)

    def test_get_applied_connection_with_version_returns_none_when_no_device(self):
        """Test that function returns None when device not found."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_nm_client.get_device_for_connection.return_value = None

        result = get_applied_connection_with_version(mock_nm_client, mock_connection)

        assert result is None

    def test_get_applied_connection_with_version_returns_none_when_get_applied_fails(self):
        """Test that function returns None when get_applied_connection fails."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_device = MagicMock()
        mock_nm_client.get_device_for_connection.return_value = mock_device
        mock_nm_client.get_applied_connection.return_value = None

        result = get_applied_connection_with_version(mock_nm_client, mock_connection)

        assert result is None


class TestRefreshActiveConnection:
    """Test live refresh for active connections."""

    @patch("pia_nm.token_refresh.get_applied_connection_with_version")
    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_active_connection_success(self, mock_update_settings, mock_get_applied):
        """Test successful refresh of active connection."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_settings = {"wireguard": {"private-key": "old_key"}}
        mock_version_id = 5
        mock_get_applied.return_value = (mock_settings, mock_version_id)

        mock_updated_settings = {"wireguard": {"private-key": "new_key"}}
        mock_update_settings.return_value = mock_updated_settings

        mock_device = MagicMock()
        mock_nm_client.get_device_for_connection.return_value = mock_device
        mock_nm_client.reapply_connection.return_value = True

        result = refresh_active_connection(
            mock_nm_client, mock_connection, "new_key", "new_endpoint:1337"
        )

        assert result is True
        mock_get_applied.assert_called_once_with(mock_nm_client, mock_connection)
        mock_update_settings.assert_called_once_with(mock_settings, "new_key", "new_endpoint:1337")
        mock_nm_client.reapply_connection.assert_called_once_with(
            mock_device, mock_updated_settings, mock_version_id
        )

    @patch("pia_nm.token_refresh.get_applied_connection_with_version")
    def test_refresh_active_connection_fails_when_get_applied_fails(self, mock_get_applied):
        """Test that refresh fails when get_applied_connection_with_version fails."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_get_applied.return_value = None

        result = refresh_active_connection(
            mock_nm_client, mock_connection, "new_key", "new_endpoint:1337"
        )

        assert result is False

    @patch("pia_nm.token_refresh.get_applied_connection_with_version")
    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_active_connection_fails_when_update_settings_raises(
        self, mock_update_settings, mock_get_applied
    ):
        """Test that refresh fails when update_wireguard_settings raises ValueError."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_settings = {"wireguard": {"private-key": "old_key"}}
        mock_version_id = 5
        mock_get_applied.return_value = (mock_settings, mock_version_id)

        mock_update_settings.side_effect = ValueError("Invalid settings")

        result = refresh_active_connection(
            mock_nm_client, mock_connection, "new_key", "new_endpoint:1337"
        )

        assert result is False

    @patch("pia_nm.token_refresh.get_applied_connection_with_version")
    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_active_connection_fails_when_no_device(
        self, mock_update_settings, mock_get_applied
    ):
        """Test that refresh fails when device not found."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_settings = {"wireguard": {"private-key": "old_key"}}
        mock_version_id = 5
        mock_get_applied.return_value = (mock_settings, mock_version_id)

        mock_updated_settings = {"wireguard": {"private-key": "new_key"}}
        mock_update_settings.return_value = mock_updated_settings

        mock_nm_client.get_device_for_connection.return_value = None

        result = refresh_active_connection(
            mock_nm_client, mock_connection, "new_key", "new_endpoint:1337"
        )

        assert result is False

    @patch("pia_nm.token_refresh.get_applied_connection_with_version")
    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_active_connection_fails_when_reapply_fails(
        self, mock_update_settings, mock_get_applied
    ):
        """Test that refresh fails when reapply_connection fails."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_settings = {"wireguard": {"private-key": "old_key"}}
        mock_version_id = 5
        mock_get_applied.return_value = (mock_settings, mock_version_id)

        mock_updated_settings = {"wireguard": {"private-key": "new_key"}}
        mock_update_settings.return_value = mock_updated_settings

        mock_device = MagicMock()
        mock_nm_client.get_device_for_connection.return_value = mock_device
        mock_nm_client.reapply_connection.return_value = False

        result = refresh_active_connection(
            mock_nm_client, mock_connection, "new_key", "new_endpoint:1337"
        )

        assert result is False


class TestRefreshInactiveConnection:
    """Test saved profile update for inactive connections."""

    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_inactive_connection_success(self, mock_update_settings):
        """Test successful refresh of inactive connection."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_settings = {"wireguard": {"private-key": "old_key"}}
        mock_connection.to_dbus.return_value = mock_settings

        mock_updated_settings = {"wireguard": {"private-key": "new_key"}}
        mock_update_settings.return_value = mock_updated_settings

        result = refresh_inactive_connection(
            mock_nm_client, mock_connection, "new_key", "new_endpoint:1337"
        )

        assert result is True
        mock_connection.to_dbus.assert_called_once()
        mock_update_settings.assert_called_once_with(mock_settings, "new_key", "new_endpoint:1337")
        mock_connection.update2.assert_called_once()

    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_inactive_connection_fails_when_to_dbus_fails(self, mock_update_settings):
        """Test that refresh fails when to_dbus fails."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_connection.to_dbus.side_effect = RuntimeError("Failed to get settings")

        result = refresh_inactive_connection(
            mock_nm_client, mock_connection, "new_key", "new_endpoint:1337"
        )

        assert result is False

    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_inactive_connection_fails_when_update_settings_raises(
        self, mock_update_settings
    ):
        """Test that refresh fails when update_wireguard_settings raises ValueError."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_settings = {"wireguard": {"private-key": "old_key"}}
        mock_connection.to_dbus.return_value = mock_settings

        mock_update_settings.side_effect = ValueError("Invalid settings")

        result = refresh_inactive_connection(
            mock_nm_client, mock_connection, "new_key", "new_endpoint:1337"
        )

        assert result is False

    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_inactive_connection_fails_when_update2_fails(self, mock_update_settings):
        """Test that refresh fails when update2 fails."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_settings = {"wireguard": {"private-key": "old_key"}}
        mock_connection.to_dbus.return_value = mock_settings

        mock_updated_settings = {"wireguard": {"private-key": "new_key"}}
        mock_update_settings.return_value = mock_updated_settings

        mock_connection.update2.side_effect = RuntimeError("Failed to update")

        result = refresh_inactive_connection(
            mock_nm_client, mock_connection, "new_key", "new_endpoint:1337"
        )

        assert result is False


class TestNoDeleteRecreate:
    """Test that refresh operations don't delete and recreate connections."""

    @patch("pia_nm.token_refresh.get_applied_connection_with_version")
    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_active_connection_does_not_delete(
        self, mock_update_settings, mock_get_applied
    ):
        """Test that refresh_active_connection doesn't call delete methods."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_settings = {"wireguard": {"private-key": "old_key"}}
        mock_version_id = 5
        mock_get_applied.return_value = (mock_settings, mock_version_id)

        mock_updated_settings = {"wireguard": {"private-key": "new_key"}}
        mock_update_settings.return_value = mock_updated_settings

        mock_device = MagicMock()
        mock_nm_client.get_device_for_connection.return_value = mock_device
        mock_nm_client.reapply_connection.return_value = True

        refresh_active_connection(mock_nm_client, mock_connection, "new_key", "new_endpoint:1337")

        # Verify delete methods were NOT called
        mock_connection.delete_async.assert_not_called()
        mock_nm_client.remove_connection_async.assert_not_called()

    @patch("pia_nm.token_refresh.update_wireguard_settings")
    def test_refresh_inactive_connection_does_not_delete(self, mock_update_settings):
        """Test that refresh_inactive_connection doesn't call delete methods."""
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "test-conn"

        mock_settings = {"wireguard": {"private-key": "old_key"}}
        mock_connection.to_dbus.return_value = mock_settings

        mock_updated_settings = {"wireguard": {"private-key": "new_key"}}
        mock_update_settings.return_value = mock_updated_settings

        refresh_inactive_connection(mock_nm_client, mock_connection, "new_key", "new_endpoint:1337")

        # Verify delete methods were NOT called
        mock_connection.delete_async.assert_not_called()
        mock_nm_client.remove_connection_async.assert_not_called()
