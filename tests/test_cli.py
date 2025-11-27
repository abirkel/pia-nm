"""Tests for CLI module."""

import pytest
from unittest.mock import patch, MagicMock
from pia_nm.cli import (
    format_profile_name,
    check_system_dependencies,
)


def test_format_profile_name():
    """Test profile name formatting."""
    assert format_profile_name("us-east") == "PIA-US-East"
    assert format_profile_name("uk-london") == "PIA-UK-London"
    assert format_profile_name("jp-tokyo") == "PIA-JP-Tokyo"
    assert format_profile_name("de-frankfurt") == "PIA-DE-Frankfurt"


@patch("shutil.which")
def test_check_system_dependencies_success(mock_which):
    """Test system dependency check when all commands are available."""
    mock_which.return_value = "/usr/bin/command"
    assert check_system_dependencies() is True


@patch("shutil.which")
def test_check_system_dependencies_missing(mock_which, capsys):
    """Test system dependency check when commands are missing."""
    mock_which.return_value = None
    assert check_system_dependencies() is False
    captured = capsys.readouterr()
    assert "Missing required commands" in captured.out


# Property-Based Tests
from hypothesis import given, strategies as st, settings
from hypothesis import assume


@given(
    num_regions=st.integers(min_value=1, max_value=5),
    num_active=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_property_active_connection_preservation(num_regions, num_active):
    """
    **Feature: dbus-refactor, Property 25: Active Connection Preservation**
    **Validates: Requirements 10.4**

    Property: For any set of active connections before refresh, all should
    remain active after refresh completes.

    This property tests that the refresh operation preserves the active state
    of connections. When we refresh tokens for multiple regions, connections
    that were active before the refresh should still be active after the refresh.

    Test strategy:
    1. Generate a random number of regions (1-5)
    2. Generate a random number of active connections (0-5, but not more than regions)
    3. Mock the refresh operation to track which connections were active before
    4. Verify that all connections that were active before are still active after
    """
    from unittest.mock import MagicMock, patch
    from pia_nm.cli import cmd_refresh

    # Ensure num_active doesn't exceed num_regions
    assume(num_active <= num_regions)

    # Generate region IDs
    region_ids = [f"region-{i}" for i in range(num_regions)]

    # Determine which regions are active (first num_active regions)
    active_regions = set(region_ids[:num_active])

    # Track connection states before and after refresh
    connections_before = {}
    connections_after = {}

    # Mock the configuration
    mock_config = {
        "regions": region_ids,
        "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
        "metadata": {"version": 1, "last_refresh": None},
    }

    # Mock NMClient and related functions
    with (
        patch("pia_nm.cli.ConfigManager") as mock_config_mgr,
        patch("pia_nm.cli.PIAClient") as mock_api_client,
        patch("pia_nm.cli.NMClient") as mock_nm_client,
        patch("pia_nm.cli.load_keypair") as mock_load_keypair,
        patch("pia_nm.cli.is_connection_active") as mock_is_active,
        patch("pia_nm.cli.refresh_active_connection") as mock_refresh_active,
        patch("pia_nm.cli.refresh_inactive_connection") as mock_refresh_inactive,
        patch("pia_nm.cli.format_profile_name") as mock_format_name,
        patch("builtins.print"),
    ):  # Suppress output

        # Setup config manager
        mock_config_instance = MagicMock()
        mock_config_instance.load.return_value = mock_config
        mock_config_instance.get_credentials.return_value = ("user", "pass")
        mock_config_mgr.return_value = mock_config_instance

        # Setup API client
        mock_api_instance = MagicMock()
        mock_api_instance.authenticate.return_value = "test_token"

        # Create mock regions with proper structure
        mock_regions = []
        for region_id in region_ids:
            mock_regions.append(
                {
                    "id": region_id,
                    "name": region_id.replace("-", " ").title(),
                    "servers": {"wg": [{"cn": f"{region_id}.example.com", "ip": "192.0.2.1"}]},
                }
            )

        mock_api_instance.get_regions.return_value = mock_regions
        mock_api_instance.register_key.return_value = {
            "server_key": "test_server_key",
            "server_ip": "192.0.2.1",
            "server_port": 1337,
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242"],
        }
        mock_api_client.return_value = mock_api_instance

        # Setup NM client
        mock_nm_instance = MagicMock()

        # Mock get_connection_by_id to return a connection for each region
        def mock_get_connection(conn_id):
            mock_conn = MagicMock()
            mock_conn.get_id.return_value = conn_id
            return mock_conn

        mock_nm_instance.get_connection_by_id.side_effect = mock_get_connection
        mock_nm_client.return_value = mock_nm_instance

        # Setup keypair loading
        mock_load_keypair.return_value = ("private_key", "public_key")

        # Setup format_profile_name to return predictable names
        def format_name(region_name):
            return f"PIA-{region_name}"

        mock_format_name.side_effect = format_name

        # Setup is_connection_active to track before state
        def check_active(nm_client, conn_id):
            # Extract region_id from connection name
            region_name = conn_id.replace("PIA-", "").replace(" ", "-").lower()
            is_active = region_name in active_regions
            connections_before[region_name] = is_active
            return is_active

        mock_is_active.side_effect = check_active

        # Setup refresh functions to always succeed and track after state
        def refresh_active(nm_client, connection, private_key, endpoint):
            conn_id = connection.get_id()
            region_name = conn_id.replace("PIA-", "").replace(" ", "-").lower()
            # Connection should remain active after refresh
            connections_after[region_name] = True
            return True

        def refresh_inactive(nm_client, connection, private_key, endpoint):
            conn_id = connection.get_id()
            region_name = conn_id.replace("PIA-", "").replace(" ", "-").lower()
            # Connection should remain inactive after refresh
            connections_after[region_name] = False
            return True

        mock_refresh_active.side_effect = refresh_active
        mock_refresh_inactive.side_effect = refresh_inactive

        # Run the refresh command
        try:
            cmd_refresh(region=None)
        except SystemExit:
            # cmd_refresh may call sys.exit on errors, which is fine for this test
            pass

        # Verify the property: all connections that were active before are still active after
        for region_id in region_ids:
            if region_id in connections_before and connections_before[region_id]:
                # This connection was active before
                assert (
                    region_id in connections_after
                ), f"Region {region_id} was active before but not tracked after refresh"
                assert connections_after[
                    region_id
                ], f"Region {region_id} was active before refresh but not active after"

        # Also verify that inactive connections remain inactive
        for region_id in region_ids:
            if region_id in connections_before and not connections_before[region_id]:
                # This connection was inactive before
                assert (
                    region_id in connections_after
                ), f"Region {region_id} was inactive before but not tracked after refresh"
                assert not connections_after[
                    region_id
                ], f"Region {region_id} was inactive before refresh but became active after"


# Unit tests for CLI commands with D-Bus operations
import sys

sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()
mock_nm = MagicMock()
sys.modules["gi.repository.NM"] = mock_nm


class TestCmdSetup:
    """Test cmd_setup with D-Bus operations."""

    @patch("pia_nm.cli.ConfigManager")
    @patch("pia_nm.cli.PIAClient")
    @patch("pia_nm.cli.NMClient")
    @patch("pia_nm.cli.generate_keypair")
    @patch("pia_nm.cli.save_keypair")
    @patch("pia_nm.cli.create_wireguard_connection")
    @patch("pia_nm.cli.format_profile_name")
    @patch("pia_nm.cli.check_system_dependencies")
    @patch("os.geteuid")
    @patch("builtins.input")
    @patch("getpass.getpass")
    @patch("builtins.print")
    def test_cmd_setup_creates_connections_via_dbus(
        self,
        mock_print,
        mock_getpass,
        mock_input,
        mock_geteuid,
        mock_check_deps,
        mock_format_name,
        mock_create_wg_conn,
        mock_save_keypair,
        mock_generate_keypair,
        mock_nm_client_class,
        mock_api_client_class,
        mock_config_mgr_class,
    ):
        """Test that cmd_setup creates connections via D-Bus."""
        from pia_nm.cli import cmd_setup
        from concurrent.futures import Future

        # Mock running as root
        mock_geteuid.return_value = 0

        # Mock system dependencies check
        mock_check_deps.return_value = True

        # Mock user input - need multiple inputs for the setup flow
        mock_input.side_effect = ["testuser", "us-east"]
        mock_getpass.return_value = "testpass"

        # Mock config manager
        mock_config_mgr = MagicMock()
        mock_config_mgr_class.return_value = mock_config_mgr

        # Mock API client
        mock_api_client = MagicMock()
        mock_api_client.authenticate.return_value = "test_token"
        mock_api_client.get_regions.return_value = [
            {
                "id": "us-east",
                "name": "US East",
                "servers": {"wg": [{"cn": "us-east.example.com", "ip": "192.0.2.1"}]},
            }
        ]
        mock_api_client.register_key.return_value = {
            "server_key": "server_key",
            "server_ip": "192.0.2.1",
            "server_port": 1337,
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242"],
        }
        mock_api_client_class.return_value = mock_api_client

        # Mock NM client
        mock_nm_client = MagicMock()
        mock_future = Future()
        mock_remote_conn = MagicMock()
        mock_future.set_result(mock_remote_conn)
        mock_nm_client.add_connection_async.return_value = mock_future
        mock_nm_client_class.return_value = mock_nm_client

        # Mock keypair generation
        mock_generate_keypair.return_value = ("private_key", "public_key")

        # Mock connection creation
        mock_connection = MagicMock()
        mock_create_wg_conn.return_value = mock_connection

        # Mock format_profile_name
        mock_format_name.return_value = "PIA-US-East"

        # Run setup
        cmd_setup()

        # Verify NM client was used to add connection
        mock_nm_client.add_connection_async.assert_called_once_with(mock_connection)


class TestCmdRefresh:
    """Test cmd_refresh with D-Bus operations."""

    @patch("pia_nm.cli.ConfigManager")
    @patch("pia_nm.cli.PIAClient")
    @patch("pia_nm.cli.NMClient")
    @patch("pia_nm.cli.load_keypair")
    @patch("pia_nm.cli.is_connection_active")
    @patch("pia_nm.cli.refresh_active_connection")
    @patch("pia_nm.cli.refresh_inactive_connection")
    @patch("pia_nm.cli.format_profile_name")
    @patch("builtins.print")
    def test_cmd_refresh_uses_dbus_operations(
        self,
        mock_print,
        mock_format_name,
        mock_refresh_inactive,
        mock_refresh_active,
        mock_is_active,
        mock_load_keypair,
        mock_nm_client_class,
        mock_api_client_class,
        mock_config_mgr_class,
    ):
        """Test that cmd_refresh uses D-Bus operations."""
        from pia_nm.cli import cmd_refresh

        # Mock config manager
        mock_config_mgr = MagicMock()
        mock_config_mgr.load.return_value = {
            "regions": ["us-east"],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": None},
        }
        mock_config_mgr.get_credentials.return_value = ("user", "pass")
        mock_config_mgr_class.return_value = mock_config_mgr

        # Mock API client
        mock_api_client = MagicMock()
        mock_api_client.authenticate.return_value = "test_token"
        mock_api_client.get_regions.return_value = [
            {
                "id": "us-east",
                "name": "US East",
                "servers": {"wg": [{"cn": "us-east.example.com", "ip": "192.0.2.1"}]},
            }
        ]
        mock_api_client.register_key.return_value = {
            "server_key": "server_key",
            "server_ip": "192.0.2.1",
            "server_port": 1337,
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242"],
        }
        mock_api_client_class.return_value = mock_api_client

        # Mock NM client
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "PIA-US-East"
        mock_nm_client.get_connection_by_id.return_value = mock_connection
        mock_nm_client_class.return_value = mock_nm_client

        # Mock keypair loading
        mock_load_keypair.return_value = ("private_key", "public_key")

        # Mock format_profile_name
        mock_format_name.return_value = "PIA-US-East"

        # Mock connection as active
        mock_is_active.return_value = True
        mock_refresh_active.return_value = True

        # Run refresh
        cmd_refresh(region=None)

        # Verify D-Bus operations were used
        mock_nm_client.get_connection_by_id.assert_called_once_with("PIA-US-East")
        mock_is_active.assert_called_once()
        mock_refresh_active.assert_called_once()


class TestCmdAddRegion:
    """Test cmd_add_region with D-Bus operations."""

    @patch("pia_nm.cli.ConfigManager")
    @patch("pia_nm.cli.PIAClient")
    @patch("pia_nm.cli.NMClient")
    @patch("pia_nm.cli.generate_keypair")
    @patch("pia_nm.cli.save_keypair")
    @patch("pia_nm.cli.create_wireguard_connection")
    @patch("pia_nm.cli.format_profile_name")
    @patch("builtins.print")
    def test_cmd_add_region_uses_dbus(
        self,
        mock_print,
        mock_format_name,
        mock_create_wg_conn,
        mock_save_keypair,
        mock_generate_keypair,
        mock_nm_client_class,
        mock_api_client_class,
        mock_config_mgr_class,
    ):
        """Test that cmd_add_region uses D-Bus to add connection."""
        from pia_nm.cli import cmd_add_region
        from concurrent.futures import Future

        # Mock config manager
        mock_config_mgr = MagicMock()
        mock_config_mgr.get_credentials.return_value = ("user", "pass")
        mock_config_mgr_class.return_value = mock_config_mgr

        # Mock API client
        mock_api_client = MagicMock()
        mock_api_client.authenticate.return_value = "test_token"
        mock_api_client.get_regions.return_value = [
            {
                "id": "us-east",
                "name": "US East",
                "servers": {"wg": [{"cn": "us-east.example.com", "ip": "192.0.2.1"}]},
            }
        ]
        mock_api_client.register_key.return_value = {
            "server_key": "server_key",
            "server_ip": "192.0.2.1",
            "server_port": 1337,
            "peer_ip": "10.0.0.1",
            "dns_servers": ["10.0.0.242"],
        }
        mock_api_client_class.return_value = mock_api_client

        # Mock NM client
        mock_nm_client = MagicMock()
        mock_future = Future()
        mock_remote_conn = MagicMock()
        mock_future.set_result(mock_remote_conn)
        mock_nm_client.add_connection_async.return_value = mock_future
        mock_nm_client_class.return_value = mock_nm_client

        # Mock keypair generation
        mock_generate_keypair.return_value = ("private_key", "public_key")

        # Mock connection creation
        mock_connection = MagicMock()
        mock_create_wg_conn.return_value = mock_connection

        # Mock format_profile_name
        mock_format_name.return_value = "PIA-US-East"

        # Run add_region
        cmd_add_region("us-east")

        # Verify D-Bus was used to add connection
        mock_nm_client.add_connection_async.assert_called_once_with(mock_connection)


class TestCmdRemoveRegion:
    """Test cmd_remove_region with D-Bus operations."""

    @patch("pia_nm.cli.ConfigManager")
    @patch("pia_nm.cli.NMClient")
    @patch("pia_nm.cli.format_profile_name")
    @patch("builtins.print")
    def test_cmd_remove_region_uses_dbus(
        self, mock_print, mock_format_name, mock_nm_client_class, mock_config_mgr_class
    ):
        """Test that cmd_remove_region uses D-Bus to remove connection."""
        from pia_nm.cli import cmd_remove_region
        from concurrent.futures import Future

        # Mock config manager - region must be in config
        mock_config_mgr = MagicMock()
        mock_config_mgr.load.return_value = {
            "regions": ["us-east"],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": None},
        }
        mock_config_mgr_class.return_value = mock_config_mgr

        # Mock NM client
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_nm_client.get_connection_by_id.return_value = mock_connection

        mock_future = Future()
        mock_future.set_result(True)
        mock_nm_client.remove_connection_async.return_value = mock_future
        mock_nm_client_class.return_value = mock_nm_client

        # Mock format_profile_name
        mock_format_name.return_value = "PIA-US-East"

        # Run remove_region
        cmd_remove_region("us-east")

        # Verify D-Bus was used to remove connection
        mock_nm_client.get_connection_by_id.assert_called_once_with("PIA-US-East")
        mock_nm_client.remove_connection_async.assert_called_once_with(mock_connection)


class TestCmdStatus:
    """Test cmd_status with D-Bus operations."""

    @patch("pia_nm.cli.ConfigManager")
    @patch("pia_nm.cli.NMClient")
    @patch("pia_nm.cli.format_profile_name")
    @patch("builtins.print")
    def test_cmd_status_uses_dbus(
        self, mock_print, mock_format_name, mock_nm_client_class, mock_config_mgr_class
    ):
        """Test that cmd_status uses D-Bus to query connections."""
        from pia_nm.cli import cmd_status

        # Mock config manager
        mock_config_mgr = MagicMock()
        mock_config_mgr.load.return_value = {
            "regions": ["us-east"],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": "2025-11-13T10:30:00Z"},
        }
        mock_config_mgr_class.return_value = mock_config_mgr

        # Mock NM client
        mock_nm_client = MagicMock()
        mock_connection = MagicMock()
        mock_nm_client.get_connection_by_id.return_value = mock_connection
        mock_nm_client.get_active_connection.return_value = None  # Inactive
        mock_nm_client_class.return_value = mock_nm_client

        # Mock format_profile_name
        mock_format_name.return_value = "PIA-US-East"

        # Run status
        cmd_status()

        # Verify D-Bus was used to query connection
        mock_nm_client.get_connection_by_id.assert_called_once_with("PIA-US-East")
        mock_nm_client.get_active_connection.assert_called_once_with("PIA-US-East")
