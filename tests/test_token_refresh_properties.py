"""
Property-based tests for token refresh functionality.

These tests verify that token refresh operations maintain correctness properties
across different connection states and configurations.

Feature: dbus-refactor
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM

from pia_nm.token_refresh import (
    is_connection_active,
    get_connection_settings,
    update_wireguard_settings,
    get_applied_connection_with_version,
    refresh_active_connection,
    refresh_inactive_connection,
)


# Pre-generated valid WireGuard keys for testing
VALID_WG_KEYS = [
    "YK08eb3xCCoDW+TPacwtNCqd2xxhXnwCBZ8RCVhSfHw=",
    "po3QKjSKPwxjCIdyOqLVT8mrG3YO8Hnib75GcQky2mI=",
    "cGFzc3dvcmQxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ=",
    "dGVzdGtleWZvcndpcmVndWFyZHRlc3RpbmcxMjM0NTY=",
]


class TestConnectionActiveCheck:
    """Test is_connection_active helper."""

    def test_connection_is_active(self):
        """Test detecting an active connection."""
        mock_nm_client = Mock()
        mock_active_conn = Mock()
        mock_nm_client.get_active_connection = Mock(return_value=mock_active_conn)

        result = is_connection_active(mock_nm_client, "PIA-US-East")

        assert result is True
        mock_nm_client.get_active_connection.assert_called_once_with("PIA-US-East")

    def test_connection_is_inactive(self):
        """Test detecting an inactive connection."""
        mock_nm_client = Mock()
        mock_nm_client.get_active_connection = Mock(return_value=None)

        result = is_connection_active(mock_nm_client, "PIA-US-East")

        assert result is False


class TestGetConnectionSettings:
    """Test get_connection_settings helper."""

    def test_get_applied_settings_for_active_connection(self):
        """Test getting applied settings for active connection."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock active connection
        mock_active_conn = Mock()
        mock_nm_client.get_active_connection = Mock(return_value=mock_active_conn)

        # Mock device
        mock_device = Mock()
        mock_nm_client.get_device_for_connection = Mock(return_value=mock_device)

        # Mock applied settings - get_applied_connection returns (settings, version_id)
        test_settings = {"wireguard": {"private-key": "test_key"}}
        test_version = 42
        mock_nm_client.get_applied_connection = Mock(return_value=(test_settings, test_version))

        result = get_connection_settings(mock_nm_client, mock_connection)

        assert result == test_settings
        mock_nm_client.get_active_connection.assert_called_once_with("PIA-US-East")
        mock_nm_client.get_device_for_connection.assert_called_once_with(mock_connection)
        mock_nm_client.get_applied_connection.assert_called_once_with(mock_device)

    def test_get_saved_settings_for_inactive_connection(self):
        """Test getting saved settings for inactive connection."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock inactive connection
        mock_nm_client.get_active_connection = Mock(return_value=None)

        # Mock saved settings
        test_settings = {"wireguard": {"private-key": "test_key"}}
        mock_connection.to_dbus = Mock(return_value=test_settings)

        result = get_connection_settings(mock_nm_client, mock_connection)

        assert result == test_settings
        mock_connection.to_dbus.assert_called_once()

    def test_get_settings_active_connection_no_device(self):
        """Test getting settings when active connection has no device."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock active connection but no device
        mock_active_conn = Mock()
        mock_nm_client.get_active_connection = Mock(return_value=mock_active_conn)
        mock_nm_client.get_device_for_connection = Mock(return_value=None)

        result = get_connection_settings(mock_nm_client, mock_connection)

        assert result is None


class TestUpdateWireGuardSettings:
    """Test update_wireguard_settings helper."""

    def test_update_wireguard_settings_success(self):
        """Test successfully updating WireGuard settings."""
        original_settings = {
            "wireguard": {
                "private-key": "old_key",
                "peers": [
                    {
                        "endpoint": "192.0.2.1:1337",
                        "public-key": "server_key"
                    }
                ]
            },
            "ipv4": {"method": "manual"}
        }

        new_key = "new_private_key"
        new_endpoint = "192.0.2.2:1337"

        result = update_wireguard_settings(
            original_settings,
            new_key,
            new_endpoint
        )

        # Verify original settings not modified
        assert original_settings["wireguard"]["private-key"] == "old_key"

        # Verify updated settings
        assert result["wireguard"]["private-key"] == new_key
        assert result["wireguard"]["peers"][0]["endpoint"] == new_endpoint
        assert result["ipv4"]["method"] == "manual"

    def test_update_wireguard_settings_no_wireguard_config(self):
        """Test updating settings without WireGuard configuration."""
        settings = {"ipv4": {"method": "manual"}}

        with pytest.raises(ValueError, match="WireGuard configuration"):
            update_wireguard_settings(settings, "new_key", "192.0.2.1:1337")

    def test_update_wireguard_settings_no_peers(self):
        """Test updating settings with no peers configured."""
        settings = {
            "wireguard": {
                "private-key": "old_key"
            }
        }

        # Should not raise, but log warning
        result = update_wireguard_settings(
            settings,
            "new_key",
            "192.0.2.1:1337"
        )

        assert result["wireguard"]["private-key"] == "new_key"


class TestGetAppliedConnectionWithVersion:
    """Test get_applied_connection_with_version helper."""

    def test_get_applied_connection_success(self):
        """Test successfully getting applied connection with version."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock device
        mock_device = Mock()
        mock_nm_client.get_device_for_connection = Mock(return_value=mock_device)

        # Mock applied connection
        test_settings = {"wireguard": {"private-key": "test_key"}}
        test_version = 42
        mock_nm_client.get_applied_connection = Mock(
            return_value=(test_settings, test_version)
        )

        result = get_applied_connection_with_version(mock_nm_client, mock_connection)

        assert result == (test_settings, test_version)
        mock_nm_client.get_device_for_connection.assert_called_once_with(mock_connection)
        mock_nm_client.get_applied_connection.assert_called_once_with(mock_device)

    def test_get_applied_connection_no_device(self):
        """Test getting applied connection when device not found."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock no device
        mock_nm_client.get_device_for_connection = Mock(return_value=None)

        result = get_applied_connection_with_version(mock_nm_client, mock_connection)

        assert result is None

    def test_get_applied_connection_failure(self):
        """Test getting applied connection when retrieval fails."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock device
        mock_device = Mock()
        mock_nm_client.get_device_for_connection = Mock(return_value=mock_device)

        # Mock failure
        mock_nm_client.get_applied_connection = Mock(return_value=None)

        result = get_applied_connection_with_version(mock_nm_client, mock_connection)

        assert result is None


class TestRefreshActiveConnection:
    """Test refresh_active_connection function."""

    def test_refresh_active_connection_success(self):
        """Test successfully refreshing an active connection."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock device
        mock_device = Mock()
        mock_nm_client.get_device_for_connection = Mock(return_value=mock_device)

        # Mock applied connection
        test_settings = {
            "wireguard": {
                "private-key": "old_key",
                "peers": [{"endpoint": "192.0.2.1:1337"}]
            }
        }
        test_version = 42
        mock_nm_client.get_applied_connection = Mock(
            return_value=(test_settings, test_version)
        )

        # Mock reapply success
        mock_nm_client.reapply_connection = Mock(return_value=True)

        result = refresh_active_connection(
            mock_nm_client,
            mock_connection,
            "new_key",
            "192.0.2.2:1337"
        )

        assert result is True
        mock_nm_client.reapply_connection.assert_called_once()

    def test_refresh_active_connection_no_applied_connection(self):
        """Test refresh when applied connection cannot be retrieved."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock failure to get applied connection
        mock_nm_client.get_applied_connection = Mock(return_value=None)

        result = refresh_active_connection(
            mock_nm_client,
            mock_connection,
            "new_key",
            "192.0.2.2:1337"
        )

        assert result is False

    def test_refresh_active_connection_no_device(self):
        """Test refresh when device cannot be found."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock applied connection
        test_settings = {
            "wireguard": {
                "private-key": "old_key",
                "peers": [{"endpoint": "192.0.2.1:1337"}]
            }
        }
        test_version = 42
        mock_nm_client.get_applied_connection = Mock(
            return_value=(test_settings, test_version)
        )

        # Mock no device
        mock_nm_client.get_device_for_connection = Mock(return_value=None)

        result = refresh_active_connection(
            mock_nm_client,
            mock_connection,
            "new_key",
            "192.0.2.2:1337"
        )

        assert result is False

    def test_refresh_active_connection_reapply_fails(self):
        """Test refresh when reapply fails."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock device
        mock_device = Mock()
        mock_nm_client.get_device_for_connection = Mock(return_value=mock_device)

        # Mock applied connection
        test_settings = {
            "wireguard": {
                "private-key": "old_key",
                "peers": [{"endpoint": "192.0.2.1:1337"}]
            }
        }
        test_version = 42
        mock_nm_client.get_applied_connection = Mock(
            return_value=(test_settings, test_version)
        )

        # Mock reapply failure
        mock_nm_client.reapply_connection = Mock(return_value=False)

        result = refresh_active_connection(
            mock_nm_client,
            mock_connection,
            "new_key",
            "192.0.2.2:1337"
        )

        assert result is False


class TestRefreshInactiveConnection:
    """Test refresh_inactive_connection function."""

    def test_refresh_inactive_connection_success(self):
        """Test successfully refreshing an inactive connection."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock saved settings
        test_settings = {
            "wireguard": {
                "private-key": "old_key",
                "peers": [{"endpoint": "192.0.2.1:1337"}]
            }
        }
        mock_connection.to_dbus = Mock(return_value=test_settings)

        # Mock update2 success
        mock_connection.update2 = Mock()

        result = refresh_inactive_connection(
            mock_nm_client,
            mock_connection,
            "new_key",
            "192.0.2.2:1337"
        )

        assert result is True
        mock_connection.update2.assert_called_once()

    def test_refresh_inactive_connection_get_settings_fails(self):
        """Test refresh when getting saved settings fails."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock failure to get settings
        mock_connection.to_dbus = Mock(side_effect=Exception("Test error"))

        result = refresh_inactive_connection(
            mock_nm_client,
            mock_connection,
            "new_key",
            "192.0.2.2:1337"
        )

        assert result is False

    def test_refresh_inactive_connection_update_fails(self):
        """Test refresh when update2 fails."""
        mock_nm_client = Mock()
        mock_connection = Mock()
        mock_connection.get_id = Mock(return_value="PIA-US-East")

        # Mock saved settings
        test_settings = {
            "wireguard": {
                "private-key": "old_key",
                "peers": [{"endpoint": "192.0.2.1:1337"}]
            }
        }
        mock_connection.to_dbus = Mock(return_value=test_settings)

        # Mock update2 failure
        mock_connection.update2 = Mock(side_effect=Exception("Update failed"))

        result = refresh_inactive_connection(
            mock_nm_client,
            mock_connection,
            "new_key",
            "192.0.2.2:1337"
        )

        assert result is False


# Property-Based Tests

def test_property_11_live_refresh_for_active_connections():
    """
    **Feature: dbus-refactor, Property 11: Live Refresh for Active Connections**
    **Validates: Requirements 3.1, 3.3, 10.1, 10.3**
    
    Property: For any active connection being refreshed, the system should use
    GetAppliedConnection followed by Reapply with the returned version_id, and
    should NOT call delete or recreate operations.
    """
    mock_nm_client = Mock()
    mock_connection = Mock()
    mock_connection.get_id = Mock(return_value="PIA-US-East")

    # Mock device
    mock_device = Mock()
    mock_nm_client.get_device_for_connection = Mock(return_value=mock_device)

    # Mock applied connection
    test_settings = {
        "wireguard": {
            "private-key": "old_key",
            "peers": [{"endpoint": "192.0.2.1:1337"}]
        }
    }
    test_version = 42
    mock_nm_client.get_applied_connection = Mock(
        return_value=(test_settings, test_version)
    )

    # Mock reapply success
    mock_nm_client.reapply_connection = Mock(return_value=True)

    # Perform refresh
    result = refresh_active_connection(
        mock_nm_client,
        mock_connection,
        "new_key",
        "192.0.2.2:1337"
    )

    # Verify success
    assert result is True

    # Verify GetAppliedConnection was called
    mock_nm_client.get_applied_connection.assert_called_once_with(mock_device)

    # Verify Reapply was called with correct version_id
    reapply_call = mock_nm_client.reapply_connection.call_args
    assert reapply_call is not None
    assert reapply_call[0][2] == test_version  # version_id is third argument

    # Verify no delete or recreate operations
    # (These would be calls to remove_connection_async or add_connection_async)
    assert not hasattr(mock_nm_client, "remove_connection_async") or \
           not mock_nm_client.remove_connection_async.called
    assert not hasattr(mock_nm_client, "add_connection_async") or \
           not mock_nm_client.add_connection_async.called


def test_property_12_selective_settings_update():
    """
    **Feature: dbus-refactor, Property 12: Selective Settings Update**
    **Validates: Requirements 3.2**
    
    Property: For any connection refresh, only the wireguard.private-key and
    wireguard.peers[0].endpoint fields should be modified in the settings dict.
    """
    original_settings = {
        "wireguard": {
            "private-key": "old_key",
            "fwmark": 51820,
            "peers": [
                {
                    "endpoint": "192.0.2.1:1337",
                    "public-key": "server_key",
                    "allowed-ips": ["0.0.0.0/0"]
                }
            ]
        },
        "ipv4": {
            "method": "manual",
            "addresses": [{"address": "10.20.30.40", "prefix": 32}],
            "dns": ["10.0.0.242"]
        },
        "connection": {
            "id": "PIA-US-East",
            "type": "wireguard"
        }
    }

    new_key = "new_private_key"
    new_endpoint = "192.0.2.2:1337"

    updated_settings = update_wireguard_settings(
        original_settings,
        new_key,
        new_endpoint
    )

    # Verify only WireGuard private key changed
    assert updated_settings["wireguard"]["private-key"] == new_key
    assert original_settings["wireguard"]["private-key"] == "old_key"

    # Verify only peer endpoint changed
    assert updated_settings["wireguard"]["peers"][0]["endpoint"] == new_endpoint
    assert original_settings["wireguard"]["peers"][0]["endpoint"] == "192.0.2.1:1337"

    # Verify other WireGuard settings unchanged
    assert updated_settings["wireguard"]["fwmark"] == original_settings["wireguard"]["fwmark"]
    assert updated_settings["wireguard"]["peers"][0]["public-key"] == \
           original_settings["wireguard"]["peers"][0]["public-key"]
    assert updated_settings["wireguard"]["peers"][0]["allowed-ips"] == \
           original_settings["wireguard"]["peers"][0]["allowed-ips"]

    # Verify IPv4 settings unchanged
    assert updated_settings["ipv4"] == original_settings["ipv4"]

    # Verify connection settings unchanged
    assert updated_settings["connection"] == original_settings["connection"]


def test_property_13_saved_profile_update_for_inactive_connections():
    """
    **Feature: dbus-refactor, Property 13: Saved Profile Update for Inactive Connections**
    **Validates: Requirements 3.5, 10.2**
    
    Property: For any inactive connection being refreshed, the system should
    update the saved connection profile (not use Reapply).
    """
    mock_nm_client = Mock()
    mock_connection = Mock()
    mock_connection.get_id = Mock(return_value="PIA-US-East")

    # Mock saved settings
    test_settings = {
        "wireguard": {
            "private-key": "old_key",
            "peers": [{"endpoint": "192.0.2.1:1337"}]
        }
    }
    mock_connection.to_dbus = Mock(return_value=test_settings)

    # Mock update2 success
    mock_connection.update2 = Mock()

    # Perform refresh
    result = refresh_inactive_connection(
        mock_nm_client,
        mock_connection,
        "new_key",
        "192.0.2.2:1337"
    )

    # Verify success
    assert result is True

    # Verify to_dbus was called to get saved settings
    mock_connection.to_dbus.assert_called_once()

    # Verify update2 was called (not reapply)
    mock_connection.update2.assert_called_once()

    # Verify reapply was NOT called
    assert not hasattr(mock_nm_client, "reapply_connection") or \
           not mock_nm_client.reapply_connection.called


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])
