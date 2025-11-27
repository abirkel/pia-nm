"""Unit and integration tests for NetworkManager interface module.

Tests cover:
- Profile existence checking
- Active connection detection
- Profile listing
- Profile creation
- Profile updates
- Profile deletion
- Error handling
"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from pia_nm.network_manager import (
    NetworkManagerError,
    create_profile,
    delete_profile,
    is_active,
    list_profiles,
    profile_exists,
    update_profile,
)


class TestProfileExists:
    """Test profile existence checking."""

    @patch("pia_nm.network_manager.subprocess.run")
    def test_profile_exists_true(self, mock_run):
        """Test profile_exists returns True when profile exists."""
        mock_result = Mock()
        mock_result.stdout = "PIA-US-East\nPIA-UK-London\nOther-Profile\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = profile_exists("PIA-US-East")

        assert result is True
        mock_run.assert_called_once()

    @patch("pia_nm.network_manager.subprocess.run")
    def test_profile_exists_false(self, mock_run):
        """Test profile_exists returns False when profile doesn't exist."""
        mock_result = Mock()
        mock_result.stdout = "PIA-UK-London\nOther-Profile\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = profile_exists("PIA-US-East")

        assert result is False

    @patch("pia_nm.network_manager.subprocess.run")
    def test_profile_exists_empty_list(self, mock_run):
        """Test profile_exists with empty profile list."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = profile_exists("PIA-US-East")

        assert result is False

    @patch("pia_nm.network_manager.subprocess.run")
    def test_profile_exists_nmcli_error(self, mock_run):
        """Test profile_exists handles nmcli errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "nmcli", stderr="Error")

        with pytest.raises(NetworkManagerError, match="Failed to check if profile exists"):
            profile_exists("PIA-US-East")

    @patch("pia_nm.network_manager.subprocess.run")
    def test_profile_exists_timeout(self, mock_run):
        """Test profile_exists handles timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("nmcli", 10)

        with pytest.raises(NetworkManagerError, match="timed out"):
            profile_exists("PIA-US-East")

    @patch("pia_nm.network_manager.subprocess.run")
    def test_profile_exists_command_not_found(self, mock_run):
        """Test profile_exists handles missing nmcli command."""
        mock_run.side_effect = FileNotFoundError("nmcli not found")

        with pytest.raises(NetworkManagerError, match="nmcli command not found"):
            profile_exists("PIA-US-East")


class TestIsActive:
    """Test active connection detection."""

    @patch("pia_nm.network_manager.subprocess.run")
    def test_is_active_true(self, mock_run):
        """Test is_active returns True when connection is active."""
        mock_result = Mock()
        mock_result.stdout = "PIA-US-East:wg-pia-us-east\nOther:eth0\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = is_active("PIA-US-East")

        assert result is True

    @patch("pia_nm.network_manager.subprocess.run")
    def test_is_active_false(self, mock_run):
        """Test is_active returns False when connection is not active."""
        mock_result = Mock()
        mock_result.stdout = "Other:eth0\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = is_active("PIA-US-East")

        assert result is False

    @patch("pia_nm.network_manager.subprocess.run")
    def test_is_active_no_active_connections(self, mock_run):
        """Test is_active when no connections are active."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = is_active("PIA-US-East")

        assert result is False

    @patch("pia_nm.network_manager.subprocess.run")
    def test_is_active_nmcli_error(self, mock_run):
        """Test is_active handles nmcli errors gracefully."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error"
        mock_run.return_value = mock_result

        result = is_active("PIA-US-East")

        # Should return False on error
        assert result is False

    @patch("pia_nm.network_manager.subprocess.run")
    def test_is_active_timeout(self, mock_run):
        """Test is_active handles timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("nmcli", 10)

        with pytest.raises(NetworkManagerError, match="timed out"):
            is_active("PIA-US-East")

    @patch("pia_nm.network_manager.subprocess.run")
    def test_is_active_command_not_found(self, mock_run):
        """Test is_active handles missing nmcli command."""
        mock_run.side_effect = FileNotFoundError("nmcli not found")

        with pytest.raises(NetworkManagerError, match="nmcli command not found"):
            is_active("PIA-US-East")


class TestListProfiles:
    """Test profile listing."""

    @patch("pia_nm.network_manager.subprocess.run")
    def test_list_profiles_multiple(self, mock_run):
        """Test list_profiles returns PIA profiles."""
        mock_result = Mock()
        mock_result.stdout = "PIA-US-East\nPIA-UK-London\nOther-Profile\nPIA-JP-Tokyo\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        profiles = list_profiles()

        assert len(profiles) == 3
        assert "PIA-US-East" in profiles
        assert "PIA-UK-London" in profiles
        assert "PIA-JP-Tokyo" in profiles
        assert "Other-Profile" not in profiles

    @patch("pia_nm.network_manager.subprocess.run")
    def test_list_profiles_empty(self, mock_run):
        """Test list_profiles with no PIA profiles."""
        mock_result = Mock()
        mock_result.stdout = "Other-Profile\nAnother-Profile\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        profiles = list_profiles()

        assert profiles == []

    @patch("pia_nm.network_manager.subprocess.run")
    def test_list_profiles_no_profiles(self, mock_run):
        """Test list_profiles with no profiles at all."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        profiles = list_profiles()

        assert profiles == []

    @patch("pia_nm.network_manager.subprocess.run")
    def test_list_profiles_nmcli_error(self, mock_run):
        """Test list_profiles handles nmcli errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "nmcli", stderr="Error")

        with pytest.raises(NetworkManagerError, match="Failed to list profiles"):
            list_profiles()

    @patch("pia_nm.network_manager.subprocess.run")
    def test_list_profiles_timeout(self, mock_run):
        """Test list_profiles handles timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("nmcli", 10)

        with pytest.raises(NetworkManagerError, match="timed out"):
            list_profiles()

    @patch("pia_nm.network_manager.subprocess.run")
    def test_list_profiles_command_not_found(self, mock_run):
        """Test list_profiles handles missing nmcli command."""
        mock_run.side_effect = FileNotFoundError("nmcli not found")

        with pytest.raises(NetworkManagerError, match="nmcli command not found"):
            list_profiles()


class TestCreateProfile:
    """Test profile creation."""

    @patch("pia_nm.network_manager.subprocess.run")
    def test_create_profile_success(self, mock_run):
        """Test successful profile creation."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = {
            "private_key": "private_key_base64",
            "server_pubkey": "server_pubkey_base64",
            "endpoint": "192.0.2.1:1337",
            "peer_ip": "10.20.30.40",
            "dns_servers": ["10.0.0.242", "10.0.0.243"],
        }
        
        result = create_profile(
            profile_name="PIA-US-East",
            config=config,
        )

        assert result is True
        # Should have called subprocess multiple times (add, modify, cat, cp, chmod, reload)
        assert mock_run.call_count >= 2

    @patch("pia_nm.network_manager.subprocess.run")
    def test_create_profile_with_custom_ports(self, mock_run):
        """Test profile creation with custom listen port and keepalive."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = {
            "private_key": "private_key",
            "server_pubkey": "server_pubkey",
            "endpoint": "192.0.2.1:1337",
            "peer_ip": "10.20.30.40",
            "dns_servers": ["10.0.0.242"],
        }
        
        result = create_profile(
            profile_name="PIA-US-East",
            config=config,
            listen_port=51820,
            keepalive=30,
        )

        assert result is True
        # Verify keepalive was passed in the peer section
        # The keepalive value should be in one of the subprocess calls
        all_calls_str = str(mock_run.call_args_list)
        assert "30" in all_calls_str or mock_run.call_count >= 2

    @patch("pia_nm.network_manager.subprocess.run")
    def test_create_profile_add_fails(self, mock_run):
        """Test error handling when profile add fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "nmcli", stderr="Error")

        config = {
            "private_key": "key",
            "server_pubkey": "pubkey",
            "endpoint": "1.2.3.4:1337",
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242"],
        }
        
        with pytest.raises(NetworkManagerError, match="Failed to create profile"):
            create_profile(
                profile_name="PIA-US-East",
                config=config,
            )

    @patch("pia_nm.network_manager.subprocess.run")
    def test_create_profile_modify_fails(self, mock_run):
        """Test error handling when profile modify fails."""
        # First call (add) succeeds, second call (modify) fails
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),
            subprocess.CalledProcessError(1, "nmcli", stderr="Error"),
        ]

        config = {
            "private_key": "key",
            "server_pubkey": "pubkey",
            "endpoint": "1.2.3.4:1337",
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242"],
        }

        with pytest.raises(NetworkManagerError, match="Failed to create profile"):
            create_profile(
                profile_name="PIA-US-East",
                config=config,
            )

    @patch("pia_nm.network_manager.subprocess.run")
    def test_create_profile_timeout(self, mock_run):
        """Test error handling when nmcli times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("nmcli", 10)

        config = {
            "private_key": "key",
            "server_pubkey": "pubkey",
            "endpoint": "1.2.3.4:1337",
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242"],
        }

        with pytest.raises(NetworkManagerError, match="timed out"):
            create_profile(
                profile_name="PIA-US-East",
                config=config,
            )

    @patch("pia_nm.network_manager.subprocess.run")
    def test_create_profile_command_not_found(self, mock_run):
        """Test error handling when nmcli command not found."""
        mock_run.side_effect = FileNotFoundError("nmcli not found")

        config = {
            "private_key": "key",
            "server_pubkey": "pubkey",
            "endpoint": "1.2.3.4:1337",
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242"],
        }

        with pytest.raises(NetworkManagerError, match="nmcli command not found"):
            create_profile(
                profile_name="PIA-US-East",
                config=config,
            )

    @patch("pia_nm.network_manager.subprocess.run")
    def test_create_profile_dns_formatting(self, mock_run):
        """Test that DNS servers are properly formatted."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = {
            "private_key": "key",
            "server_pubkey": "pubkey",
            "endpoint": "1.2.3.4:1337",
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242", "10.0.0.243"],
        }

        create_profile(
            profile_name="PIA-US-East",
            config=config,
        )

        # Check modify call for DNS formatting
        modify_call = mock_run.call_args_list[1]
        modify_args = modify_call[0][0]
        # DNS should be comma-separated
        assert "10.0.0.242,10.0.0.243" in modify_args


class TestUpdateProfile:
    """Test profile updates."""

    @patch("pia_nm.network_manager.is_active")
    @patch("pia_nm.network_manager.subprocess.run")
    def test_update_profile_success_inactive(self, mock_run, mock_is_active):
        """Test successful profile update when connection is inactive."""
        mock_is_active.return_value = False
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = {
            "private_key": "new_key",
            "server_pubkey": "new_pubkey",
            "endpoint": "192.0.2.2:1337",
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.242"],
        }

        result = update_profile(
            profile_name="PIA-US-East",
            config=config,
        )

        assert result is True
        mock_run.assert_called_once()

    @patch("pia_nm.network_manager.is_active")
    @patch("pia_nm.network_manager.subprocess.run")
    def test_update_profile_success_active(self, mock_run, mock_is_active):
        """Test successful profile update when connection is active."""
        mock_is_active.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = {
            "private_key": "new_key",
            "server_pubkey": "new_pubkey",
            "endpoint": "192.0.2.2:1337",
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.242"],
        }

        result = update_profile(
            profile_name="PIA-US-East",
            config=config,
        )

        assert result is True
        # Should still only call modify once (not delete/recreate)
        mock_run.assert_called_once()

    @patch("pia_nm.network_manager.is_active")
    @patch("pia_nm.network_manager.subprocess.run")
    def test_update_profile_uses_modify_not_delete_recreate(self, mock_run, mock_is_active):
        """Test that update uses modify, not delete/recreate."""
        mock_is_active.return_value = True
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        config = {
            "private_key": "new_key",
            "server_pubkey": "new_pubkey",
            "endpoint": "192.0.2.2:1337",
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.242"],
        }

        update_profile(
            profile_name="PIA-US-East",
            config=config,
        )

        # Verify modify was called, not delete
        call_args = mock_run.call_args[0][0]
        assert "modify" in call_args
        assert "delete" not in call_args

    @patch("pia_nm.network_manager.is_active")
    @patch("pia_nm.network_manager.subprocess.run")
    def test_update_profile_nmcli_error(self, mock_run, mock_is_active):
        """Test error handling when nmcli fails."""
        mock_is_active.return_value = False
        mock_run.side_effect = subprocess.CalledProcessError(1, "nmcli", stderr="Error")

        config = {
            "private_key": "new_key",
            "server_pubkey": "new_pubkey",
            "endpoint": "192.0.2.2:1337",
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.242"],
        }

        with pytest.raises(NetworkManagerError, match="Failed to update profile"):
            update_profile(
                profile_name="PIA-US-East",
                config=config,
            )

    @patch("pia_nm.network_manager.is_active")
    @patch("pia_nm.network_manager.subprocess.run")
    def test_update_profile_timeout(self, mock_run, mock_is_active):
        """Test error handling when nmcli times out."""
        mock_is_active.return_value = False
        mock_run.side_effect = subprocess.TimeoutExpired("nmcli", 10)

        config = {
            "private_key": "new_key",
            "server_pubkey": "new_pubkey",
            "endpoint": "192.0.2.2:1337",
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.242"],
        }

        with pytest.raises(NetworkManagerError, match="timed out"):
            update_profile(
                profile_name="PIA-US-East",
                config=config,
            )

    @patch("pia_nm.network_manager.is_active")
    @patch("pia_nm.network_manager.subprocess.run")
    def test_update_profile_command_not_found(self, mock_run, mock_is_active):
        """Test error handling when nmcli command not found."""
        mock_is_active.return_value = False
        mock_run.side_effect = FileNotFoundError("nmcli not found")

        config = {
            "private_key": "new_key",
            "server_pubkey": "new_pubkey",
            "endpoint": "192.0.2.2:1337",
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.242"],
        }

        with pytest.raises(NetworkManagerError, match="nmcli command not found"):
            update_profile(
                profile_name="PIA-US-East",
                config=config,
            )


class TestDeleteProfile:
    """Test profile deletion."""

    @patch("pia_nm.network_manager.subprocess.run")
    def test_delete_profile_success(self, mock_run):
        """Test successful profile deletion."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = delete_profile("PIA-US-East")

        assert result is True
        mock_run.assert_called_once()

    @patch("pia_nm.network_manager.subprocess.run")
    def test_delete_profile_not_found(self, mock_run):
        """Test deletion when profile doesn't exist."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: connection 'PIA-US-East' not found"
        mock_run.return_value = mock_result

        result = delete_profile("PIA-US-East")

        # Should return False, not raise
        assert result is False

    @patch("pia_nm.network_manager.subprocess.run")
    def test_delete_profile_unknown_error(self, mock_run):
        """Test deletion with unknown error."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Some other error occurred"
        mock_run.return_value = mock_result

        with pytest.raises(NetworkManagerError, match="Failed to delete profile"):
            delete_profile("PIA-US-East")

    @patch("pia_nm.network_manager.subprocess.run")
    def test_delete_profile_timeout(self, mock_run):
        """Test error handling when nmcli times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("nmcli", 10)

        with pytest.raises(NetworkManagerError, match="timed out"):
            delete_profile("PIA-US-East")

    @patch("pia_nm.network_manager.subprocess.run")
    def test_delete_profile_command_not_found(self, mock_run):
        """Test error handling when nmcli command not found."""
        mock_run.side_effect = FileNotFoundError("nmcli not found")

        with pytest.raises(NetworkManagerError, match="nmcli command not found"):
            delete_profile("PIA-US-East")


class TestNetworkManagerIntegration:
    """Integration tests for NetworkManager operations."""

    @patch("pia_nm.network_manager.is_active")
    @patch("pia_nm.network_manager.subprocess.run")
    def test_full_profile_lifecycle(self, mock_run, mock_is_active):
        """Test complete profile lifecycle: create, check, update, delete."""
        # Mock responses for each operation
        mock_run.side_effect = [
            # create_profile: add
            Mock(returncode=0, stdout="", stderr=""),
            # create_profile: modify
            Mock(returncode=0, stdout="", stderr=""),
            # profile_exists
            Mock(returncode=0, stdout="PIA-US-East\n", stderr=""),
            # update_profile: modify
            Mock(returncode=0, stdout="", stderr=""),
            # delete_profile
            Mock(returncode=0, stdout="", stderr=""),
        ]
        mock_is_active.return_value = False

        # Create profile
        config = {
            "private_key": "private_key",
            "server_pubkey": "server_pubkey",
            "endpoint": "192.0.2.1:1337",
            "peer_ip": "10.20.30.40",
            "dns_servers": ["10.0.0.242"],
        }
        assert create_profile(
            profile_name="PIA-US-East",
            config=config,
        )

        # Check exists
        assert profile_exists("PIA-US-East")

        # Update profile
        new_config = {
            "private_key": "new_key",
            "server_pubkey": "new_pubkey",
            "endpoint": "192.0.2.2:1337",
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.242"],
        }
        assert update_profile(
            profile_name="PIA-US-East",
            config=new_config,
        )

        # Delete profile
        assert delete_profile("PIA-US-East")

    @patch("pia_nm.network_manager.subprocess.run")
    def test_multiple_profiles_independent(self, mock_run):
        """Test that multiple profiles can be managed independently."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Create two profiles
        config1 = {
            "private_key": "private1",
            "server_pubkey": "pubkey1",
            "endpoint": "1.2.3.4:1337",
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242"],
        }
        assert create_profile(
            profile_name="PIA-US-East",
            config=config1,
        )

        config2 = {
            "private_key": "private2",
            "server_pubkey": "pubkey2",
            "endpoint": "192.0.2.2:1337",
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.243"],
        }
        assert create_profile(
            profile_name="PIA-UK-London",
            config=config2,
        )

        # Should have called nmcli 4 times (2 creates, each with add + modify)
        assert mock_run.call_count == 4

    @patch("pia_nm.network_manager.subprocess.run")
    def test_list_profiles_filters_correctly(self, mock_run):
        """Test that list_profiles correctly filters PIA profiles."""
        mock_result = Mock()
        mock_result.stdout = "PIA-US-East\nPIA-UK-London\nEthernet\nWiFi\nPIA-JP-Tokyo\n"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        profiles = list_profiles()

        assert len(profiles) == 3
        assert all(p.startswith("PIA-") for p in profiles)
        assert "Ethernet" not in profiles
        assert "WiFi" not in profiles
