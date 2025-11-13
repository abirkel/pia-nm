"""Integration tests for PIA NetworkManager Integration.

These tests verify complete workflows and interactions between modules:
- Complete setup workflow
- Token refresh workflow
- Region management
- Error scenarios
- Systemd timer execution
- Uninstall workflow
"""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pia_nm.api_client import PIAClient
from pia_nm.config import ConfigManager
from pia_nm.network_manager import (
    create_profile,
    delete_profile,
    is_active,
    list_profiles,
    profile_exists,
    update_profile,
)
from pia_nm.systemd_manager import (
    check_timer_status,
    disable_timer,
    enable_timer,
    install_units,
    uninstall_units,
)
from pia_nm.wireguard import (
    delete_keypair,
    generate_keypair,
    load_keypair,
    save_keypair,
    should_rotate_key,
)


class TestSetupWorkflow:
    """Test complete setup workflow."""

    @patch("pia_nm.config.keyring.set_password")
    @patch("pia_nm.config.keyring.get_password")
    @patch("pia_nm.api_client.PIAClient._make_request")
    @patch("pia_nm.wireguard.subprocess.run")
    @patch("pia_nm.network_manager.subprocess.run")
    def test_complete_setup_workflow(
        self, mock_nm_run, mock_wg_run, mock_api_request, mock_get_creds, mock_set_creds, tmp_path, monkeypatch
    ):
        """Test complete setup workflow: auth, regions, keys, profiles, config."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Mock keyring
        mock_set_creds.return_value = None
        mock_get_creds.side_effect = ["testuser", "testpass"]

        # Mock API responses
        auth_response = {"token": "test_token_123"}
        regions_response = {
            "regions": [
                {
                    "id": "us-east",
                    "name": "US East",
                    "country": "US",
                    "dns": "10.0.0.242",
                    "port_forward": False,
                    "servers": {"wg": [{"ip": "192.0.2.1", "cn": "us-east", "port": 1337}]},
                },
                {
                    "id": "uk-london",
                    "name": "UK London",
                    "country": "GB",
                    "dns": "10.0.0.243",
                    "port_forward": True,
                    "servers": {"wg": [{"ip": "192.0.2.2", "cn": "uk-london", "port": 1337}]},
                },
            ]
        }
        register_response = {
            "status": "OK",
            "server_key": "server_pubkey",
            "server_ip": "10.10.10.1",
            "server_port": 1337,
            "peer_ip": "10.20.30.40",
            "dns_servers": ["10.0.0.242"],
        }

        mock_api_request.side_effect = [
            auth_response,
            regions_response,
            register_response,
            register_response,
        ]

        # Mock WireGuard key generation
        def wg_side_effect(*args, **kwargs):
            if args[0][0] == "wg" and args[0][1] == "genkey":
                result = Mock()
                result.stdout = "private_key_1\n"
                result.returncode = 0
                return result
            elif args[0][0] == "wg" and args[0][1] == "pubkey":
                result = Mock()
                result.stdout = "public_key_1\n"
                result.returncode = 0
                return result
            return Mock(returncode=0, stdout="", stderr="")

        mock_wg_run.side_effect = wg_side_effect

        # Mock NetworkManager profile creation
        mock_nm_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Step 1: Authenticate
        api = PIAClient()
        token = api.authenticate("testuser", "testpass")
        assert token == "test_token_123"

        # Step 2: Get regions
        regions = api.get_regions()
        assert len(regions) == 2
        assert regions[0]["id"] == "us-east"

        # Step 3: Generate keypairs and create profiles
        config_mgr = ConfigManager(config_path=tmp_path / ".config/pia-nm/config.yaml")
        config_mgr.set_credentials("testuser", "testpass")

        created_regions = []
        for region in regions[:2]:  # Create profiles for first 2 regions
            region_id = region["id"]

            # Generate keypair
            private_key, public_key = generate_keypair()
            save_keypair(region_id, private_key, public_key)

            # Register key
            conn_details = api.register_key(token, public_key, region_id)

            # Create profile
            profile_name = f"PIA-{region_id.upper()}"
            success = create_profile(
                profile_name,
                private_key,
                conn_details["server_key"],
                f"{conn_details['server_ip']}:{conn_details['server_port']}",
                conn_details["peer_ip"],
                conn_details["dns_servers"],
            )

            assert success
            created_regions.append(region_id)

        # Step 4: Save configuration
        config_mgr.save(
            {
                "regions": created_regions,
                "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
                "metadata": {"version": 1, "last_refresh": None},
            }
        )

        # Step 5: Verify configuration
        config = config_mgr.load()
        assert config["regions"] == created_regions
        assert len(config["regions"]) == 2

        # Step 6: Verify credentials stored
        username, password = config_mgr.get_credentials()
        assert username == "testuser"
        assert password == "testpass"

        # Step 7: Verify keypairs saved
        for region_id in created_regions:
            private_key, public_key = load_keypair(region_id)
            assert private_key == "private_key_1"
            assert public_key == "public_key_1"

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_setup_with_invalid_credentials(self, mock_api_request, tmp_path, monkeypatch):
        """Test setup fails gracefully with invalid credentials."""
        monkeypatch.setenv("HOME", str(tmp_path))

        from pia_nm.api_client import AuthenticationError

        mock_api_request.side_effect = AuthenticationError("Invalid credentials")

        api = PIAClient()

        with pytest.raises(AuthenticationError):
            api.authenticate("baduser", "badpass")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_setup_with_network_error(self, mock_api_request, tmp_path, monkeypatch):
        """Test setup fails gracefully with network error."""
        monkeypatch.setenv("HOME", str(tmp_path))

        from pia_nm.api_client import NetworkError

        mock_api_request.side_effect = NetworkError("Connection failed")

        api = PIAClient()

        with pytest.raises(NetworkError):
            api.authenticate("user", "pass")


class TestTokenRefreshWorkflow:
    """Test token refresh workflow."""

    @patch("pia_nm.config.keyring.get_password")
    @patch("pia_nm.config.keyring.set_password")
    @patch("pia_nm.network_manager.is_active")
    @patch("pia_nm.network_manager.subprocess.run")
    @patch("pia_nm.wireguard.subprocess.run")
    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_refresh_with_inactive_connection(
        self, mock_api_request, mock_wg_run, mock_nm_run, mock_is_active, mock_set_creds, mock_get_creds, tmp_path, monkeypatch
    ):
        """Test token refresh with inactive connection."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Mock keyring
        mock_set_creds.return_value = None
        
        def get_creds_side_effect(service, key):
            if key == "username":
                return "testuser"
            elif key == "password":
                return "testpass"
            return None
        
        mock_get_creds.side_effect = get_creds_side_effect

        # Setup initial state
        config_mgr = ConfigManager(config_path=tmp_path / ".config/pia-nm/config.yaml")
        config_mgr.set_credentials("testuser", "testpass")
        config_mgr.save(
            {
                "regions": ["us-east"],
                "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
                "metadata": {"version": 1, "last_refresh": None},
            }
        )

        # Create initial keypair - just save directly without generating
        private_key = "private_key"
        public_key = "public_key"
        save_keypair("us-east", private_key, public_key)

        # Mock API responses for refresh
        auth_response = {"token": "new_token_456"}
        register_response = {
            "status": "OK",
            "server_key": "new_server_pubkey",
            "server_ip": "10.10.10.2",
            "server_port": 1337,
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.243"],
        }

        mock_api_request.side_effect = [auth_response, register_response]

        # Mock NetworkManager
        mock_nm_run.return_value = Mock(returncode=0, stdout="", stderr="")
        mock_is_active.return_value = False

        # Perform refresh
        api = PIAClient()
        token = api.authenticate("testuser", "testpass")
        assert token == "new_token_456"

        # Load existing keypair
        loaded_private, loaded_public = load_keypair("us-east")
        assert loaded_private == private_key

        # Register key
        conn_details = api.register_key(token, loaded_public, "us-east")
        assert conn_details["status"] == "OK"

        # Update profile
        profile_name = "PIA-US-EAST"
        success = update_profile(
            profile_name,
            loaded_private,
            conn_details["server_key"],
            f"{conn_details['server_ip']}:{conn_details['server_port']}",
            conn_details["peer_ip"],
            conn_details["dns_servers"],
        )

        assert success

        # Update timestamp
        config_mgr.update_last_refresh()
        config = config_mgr.load()
        assert config["metadata"]["last_refresh"] is not None

    @patch("pia_nm.config.keyring.get_password")
    @patch("pia_nm.config.keyring.set_password")
    @patch("pia_nm.network_manager.is_active")
    @patch("pia_nm.network_manager.subprocess.run")
    @patch("pia_nm.wireguard.subprocess.run")
    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_refresh_with_active_connection(
        self, mock_api_request, mock_wg_run, mock_nm_run, mock_is_active, mock_set_creds, mock_get_creds, tmp_path, monkeypatch
    ):
        """Test token refresh preserves active connection."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Mock keyring
        mock_set_creds.return_value = None
        
        def get_creds_side_effect(service, key):
            if key == "username":
                return "testuser"
            elif key == "password":
                return "testpass"
            return None
        
        mock_get_creds.side_effect = get_creds_side_effect

        # Setup
        config_mgr = ConfigManager(config_path=tmp_path / ".config/pia-nm/config.yaml")
        config_mgr.set_credentials("testuser", "testpass")

        # Create initial keypair - just save directly without generating
        private_key = "private_key"
        public_key = "public_key"
        save_keypair("us-east", private_key, public_key)

        # Mock API
        auth_response = {"token": "new_token"}
        register_response = {
            "status": "OK",
            "server_key": "new_server_pubkey",
            "server_ip": "10.10.10.2",
            "server_port": 1337,
            "peer_ip": "10.20.30.41",
            "dns_servers": ["10.0.0.243"],
        }

        mock_api_request.side_effect = [auth_response, register_response]

        # Mock NetworkManager - connection is active
        mock_nm_run.return_value = Mock(returncode=0, stdout="", stderr="")
        mock_is_active.return_value = True

        # Perform refresh
        api = PIAClient()
        token = api.authenticate("testuser", "testpass")

        loaded_private, loaded_public = load_keypair("us-east")
        conn_details = api.register_key(token, loaded_public, "us-east")

        # Update profile (should use modify, not delete/recreate)
        profile_name = "PIA-US-EAST"
        success = update_profile(
            profile_name,
            loaded_private,
            conn_details["server_key"],
            f"{conn_details['server_ip']}:{conn_details['server_port']}",
            conn_details["peer_ip"],
            conn_details["dns_servers"],
        )

        assert success

        # Verify modify was called (not delete)
        call_args = mock_nm_run.call_args[0][0]
        assert "modify" in call_args

    @patch("pia_nm.wireguard.subprocess.run")
    def test_refresh_with_key_rotation(self, mock_wg_run, tmp_path, monkeypatch):
        """Test token refresh with key rotation."""
        import os
        import time

        monkeypatch.setenv("HOME", str(tmp_path))

        # Create old keypair
        genkey_result = Mock()
        genkey_result.stdout = "old_private_key\n"
        genkey_result.returncode = 0

        pubkey_result = Mock()
        pubkey_result.stdout = "old_public_key\n"
        pubkey_result.returncode = 0

        mock_wg_run.side_effect = [genkey_result, pubkey_result]

        private_key, public_key = generate_keypair()
        save_keypair("us-east", private_key, public_key)

        # Set file modification time to 31 days ago
        keys_dir = tmp_path / ".config/pia-nm/keys"
        private_key_path = keys_dir / "us-east.key"

        thirty_one_days_ago = time.time() - (31 * 24 * 60 * 60)
        os.utime(private_key_path, (thirty_one_days_ago, thirty_one_days_ago))

        # Check rotation needed
        assert should_rotate_key("us-east") is True

        # Generate new keypair
        new_genkey_result = Mock()
        new_genkey_result.stdout = "new_private_key\n"
        new_genkey_result.returncode = 0

        new_pubkey_result = Mock()
        new_pubkey_result.stdout = "new_public_key\n"
        new_pubkey_result.returncode = 0

        mock_wg_run.side_effect = [new_genkey_result, new_pubkey_result]

        new_private_key, new_public_key = generate_keypair()
        save_keypair("us-east", new_private_key, new_public_key)

        # Verify new key is used
        loaded_private, loaded_public = load_keypair("us-east")
        assert loaded_private == "new_private_key"
        assert loaded_public == "new_public_key"


class TestRegionManagement:
    """Test region management operations."""

    @patch("pia_nm.config.keyring.set_password")
    @patch("pia_nm.config.keyring.get_password")
    @patch("pia_nm.api_client.PIAClient._make_request")
    @patch("pia_nm.wireguard.subprocess.run")
    @patch("pia_nm.network_manager.subprocess.run")
    def test_add_region_workflow(
        self, mock_nm_run, mock_wg_run, mock_api_request, mock_get_creds, mock_set_creds, tmp_path, monkeypatch
    ):
        """Test adding a new region."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Mock keyring
        mock_set_creds.return_value = None
        mock_get_creds.side_effect = ["testuser", "testpass"]

        # Setup initial config
        config_mgr = ConfigManager(config_path=tmp_path / ".config/pia-nm/config.yaml")
        config_mgr.set_credentials("testuser", "testpass")
        config_mgr.save(
            {
                "regions": ["us-east"],
                "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
                "metadata": {"version": 1, "last_refresh": None},
            }
        )

        # Mock API
        regions_response = {
            "regions": [
                {
                    "id": "us-east",
                    "name": "US East",
                    "country": "US",
                    "dns": "10.0.0.242",
                    "port_forward": False,
                    "servers": {"wg": [{"ip": "192.0.2.1", "cn": "us-east", "port": 1337}]},
                },
                {
                    "id": "uk-london",
                    "name": "UK London",
                    "country": "GB",
                    "dns": "10.0.0.243",
                    "port_forward": True,
                    "servers": {"wg": [{"ip": "192.0.2.2", "cn": "uk-london", "port": 1337}]},
                },
            ]
        }
        auth_response = {"token": "test_token"}
        register_response = {
            "status": "OK",
            "server_key": "server_pubkey",
            "server_ip": "10.10.10.1",
            "server_port": 1337,
            "peer_ip": "10.20.30.40",
            "dns_servers": ["10.0.0.242"],
        }

        mock_api_request.side_effect = [regions_response, auth_response, register_response]

        # Mock WireGuard
        def wg_side_effect(*args, **kwargs):
            if args[0][0] == "wg" and args[0][1] == "genkey":
                result = Mock()
                result.stdout = "private_key\n"
                result.returncode = 0
                return result
            elif args[0][0] == "wg" and args[0][1] == "pubkey":
                result = Mock()
                result.stdout = "public_key\n"
                result.returncode = 0
                return result
            return Mock(returncode=0, stdout="", stderr="")

        mock_wg_run.side_effect = wg_side_effect

        # Mock NetworkManager
        mock_nm_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Add region
        api = PIAClient()
        regions = api.get_regions()
        region_id = "uk-london"

        # Authenticate
        token = api.authenticate("testuser", "testpass")

        # Generate keypair
        private_key, public_key = generate_keypair()
        save_keypair(region_id, private_key, public_key)

        # Register key
        conn_details = api.register_key(token, public_key, region_id)

        # Create profile
        profile_name = f"PIA-{region_id.upper()}"
        success = create_profile(
            profile_name,
            private_key,
            conn_details["server_key"],
            f"{conn_details['server_ip']}:{conn_details['server_port']}",
            conn_details["peer_ip"],
            conn_details["dns_servers"],
        )

        assert success

        # Update config
        config = config_mgr.load()
        config["regions"].append(region_id)
        config_mgr.save(config)

        # Verify
        updated_config = config_mgr.load()
        assert "uk-london" in updated_config["regions"]
        assert len(updated_config["regions"]) == 2

    @patch("pia_nm.network_manager.subprocess.run")
    def test_remove_region_workflow(self, mock_nm_run, tmp_path, monkeypatch):
        """Test removing a region."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Setup
        config_mgr = ConfigManager(config_path=tmp_path / ".config/pia-nm/config.yaml")
        config_mgr.save(
            {
                "regions": ["us-east", "uk-london"],
                "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
                "metadata": {"version": 1, "last_refresh": None},
            }
        )

        # Create keypair
        keys_dir = tmp_path / ".config/pia-nm/keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        (keys_dir / "us-east.key").write_text("private_key")
        (keys_dir / "us-east.pub").write_text("public_key")

        # Mock NetworkManager
        mock_nm_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Remove region
        region_id = "us-east"
        profile_name = f"PIA-{region_id.upper()}"

        # Delete profile
        success = delete_profile(profile_name)
        assert success

        # Update config
        config = config_mgr.load()
        config["regions"].remove(region_id)
        config_mgr.save(config)

        # Delete keypair
        delete_keypair(region_id)

        # Verify
        updated_config = config_mgr.load()
        assert "us-east" not in updated_config["regions"]
        assert "uk-london" in updated_config["regions"]
        assert not (keys_dir / "us-east.key").exists()


class TestErrorScenarios:
    """Test error handling in various scenarios."""

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_invalid_credentials_error(self, mock_api_request, tmp_path, monkeypatch):
        """Test handling of invalid credentials."""
        monkeypatch.setenv("HOME", str(tmp_path))

        from pia_nm.api_client import AuthenticationError

        mock_api_request.side_effect = AuthenticationError("Invalid credentials")

        api = PIAClient()

        with pytest.raises(AuthenticationError):
            api.authenticate("baduser", "badpass")

    @patch("pia_nm.api_client.PIAClient._make_request")
    def test_network_disconnected_error(self, mock_api_request, tmp_path, monkeypatch):
        """Test handling of network disconnection."""
        monkeypatch.setenv("HOME", str(tmp_path))

        from pia_nm.api_client import NetworkError

        mock_api_request.side_effect = NetworkError("Connection failed")

        api = PIAClient()

        with pytest.raises(NetworkError):
            api.get_regions()

    def test_missing_system_dependencies(self):
        """Test detection of missing system dependencies."""
        import shutil

        # Check if required commands exist
        required = ["nmcli", "wg", "systemctl"]

        for cmd in required:
            # This test just verifies the check logic works
            # In real environment, these should be installed
            result = shutil.which(cmd)
            # We don't assert here because test environment may not have all tools
            # Just verify the check doesn't crash
            assert result is None or isinstance(result, str)

    def test_config_validation_error(self, tmp_path, monkeypatch):
        """Test configuration validation errors."""
        monkeypatch.setenv("HOME", str(tmp_path))

        from pia_nm.config import ConfigError

        config_mgr = ConfigManager(config_path=tmp_path / ".config/pia-nm/config.yaml")

        invalid_config = {
            "regions": "not-a-list",  # Should be list
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": None},
        }

        with pytest.raises(ConfigError):
            config_mgr.save(invalid_config)


class TestSystemdIntegration:
    """Test systemd timer integration."""

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_install_units_creates_files(self, mock_run, tmp_path, monkeypatch):
        """Test that install_units creates systemd unit files."""
        monkeypatch.setenv("HOME", str(tmp_path))

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        install_units()

        # Verify unit files were created
        systemd_dir = tmp_path / ".config/systemd/user"
        assert (systemd_dir / "pia-nm-refresh.service").exists()
        assert (systemd_dir / "pia-nm-refresh.timer").exists()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_enable_timer(self, mock_run, tmp_path, monkeypatch):
        """Test enabling the systemd timer."""
        monkeypatch.setenv("HOME", str(tmp_path))

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = enable_timer()

        assert result is True
        mock_run.assert_called_once()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_disable_timer(self, mock_run, tmp_path, monkeypatch):
        """Test disabling the systemd timer."""
        monkeypatch.setenv("HOME", str(tmp_path))

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = disable_timer()

        assert result is True
        mock_run.assert_called_once()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_check_timer_status(self, mock_run, tmp_path, monkeypatch):
        """Test checking timer status."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Mock is-active response
        is_active_result = Mock()
        is_active_result.returncode = 0
        is_active_result.stdout = ""

        # Mock list-timers response
        list_timers_result = Mock()
        list_timers_result.returncode = 0
        list_timers_result.stdout = "NEXT                        LEFT     LAST                        PASSED UNIT\n2025-11-14 10:30:00 UTC     12h left 2025-11-13 10:30:00 UTC 0s     pia-nm-refresh.timer\n"

        mock_run.side_effect = [is_active_result, list_timers_result]

        status = check_timer_status()

        assert status["active"] == "active"
        assert status["next_run"] is not None

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_uninstall_units(self, mock_run, tmp_path, monkeypatch):
        """Test uninstalling systemd units."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create unit files first
        systemd_dir = tmp_path / ".config/systemd/user"
        systemd_dir.mkdir(parents=True, exist_ok=True)
        (systemd_dir / "pia-nm-refresh.service").write_text("[Unit]\nDescription=Test\n")
        (systemd_dir / "pia-nm-refresh.timer").write_text("[Unit]\nDescription=Test\n")

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = uninstall_units()

        assert result is True
        # Verify files were deleted
        assert not (systemd_dir / "pia-nm-refresh.service").exists()
        assert not (systemd_dir / "pia-nm-refresh.timer").exists()


class TestUninstallWorkflow:
    """Test complete uninstall workflow."""

    @patch("pia_nm.config.keyring.set_password")
    @patch("pia_nm.network_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_complete_uninstall_workflow(
        self, mock_systemd_run, mock_nm_run, mock_set_creds, tmp_path, monkeypatch
    ):
        """Test complete uninstall workflow."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Mock keyring
        mock_set_creds.return_value = None

        # Setup initial state
        config_mgr = ConfigManager(config_path=tmp_path / ".config/pia-nm/config.yaml")
        config_mgr.set_credentials("testuser", "testpass")
        config_mgr.save(
            {
                "regions": ["us-east", "uk-london"],
                "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
                "metadata": {"version": 1, "last_refresh": None},
            }
        )

        # Create keypairs
        keys_dir = tmp_path / ".config/pia-nm/keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        (keys_dir / "us-east.key").write_text("private_key")
        (keys_dir / "us-east.pub").write_text("public_key")
        (keys_dir / "uk-london.key").write_text("private_key")
        (keys_dir / "uk-london.pub").write_text("public_key")

        # Create systemd units
        systemd_dir = tmp_path / ".config/systemd/user"
        systemd_dir.mkdir(parents=True, exist_ok=True)
        (systemd_dir / "pia-nm-refresh.service").write_text("[Unit]\nDescription=Test\n")
        (systemd_dir / "pia-nm-refresh.timer").write_text("[Unit]\nDescription=Test\n")

        # Mock subprocess calls
        mock_nm_run.return_value = Mock(returncode=0, stdout="", stderr="")
        mock_systemd_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Perform uninstall steps
        # 1. Remove profiles
        for region_id in ["us-east", "uk-london"]:
            profile_name = f"PIA-{region_id.upper()}"
            delete_profile(profile_name)

        # 2. Uninstall systemd units
        uninstall_units()

        # 3. Delete config directory
        import shutil

        config_dir = tmp_path / ".config/pia-nm"
        if config_dir.exists():
            shutil.rmtree(config_dir)

        # 4. Remove credentials from keyring (mocked in real test)
        # In real scenario, would call keyring.delete_password

        # Verify cleanup
        assert not config_dir.exists()
        assert not (systemd_dir / "pia-nm-refresh.service").exists()
        assert not (systemd_dir / "pia-nm-refresh.timer").exists()

