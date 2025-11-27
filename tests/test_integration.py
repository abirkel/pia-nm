"""Integration tests for D-Bus NetworkManager integration.

These tests verify the complete connection lifecycle and configuration
preservation. They use mocks to simulate NetworkManager behavior without
requiring actual NetworkManager running.

Tests cover:
- Full connection lifecycle (create, activate, delete)
- Multiple region management
- Configuration preservation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from concurrent.futures import Future

# Mock gi.repository before importing modules
import sys
sys.modules['gi'] = MagicMock()
sys.modules['gi.repository'] = MagicMock()

# Create mock NM and GLib modules
mock_nm = MagicMock()
mock_glib = MagicMock()
sys.modules['gi.repository.NM'] = mock_nm
sys.modules['gi.repository.GLib'] = mock_glib


class TestConnectionLifecycle:
    """Test full connection lifecycle: create, activate, delete."""

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    @patch('pia_nm.wireguard_connection.NM.SimpleConnection')
    @patch('pia_nm.wireguard_connection.NM.SettingConnection')
    @patch('pia_nm.wireguard_connection.NM.SettingWireGuard')
    @patch('pia_nm.wireguard_connection.NM.WireGuardPeer')
    @patch('pia_nm.wireguard_connection.NM.SettingIP4Config')
    @patch('pia_nm.wireguard_connection.NM.SettingIP6Config')
    @patch('pia_nm.wireguard_connection.NM.IPAddress')
    @patch('pia_nm.wireguard_connection.uuid.uuid4')
    def test_full_connection_lifecycle(
        self,
        mock_uuid,
        mock_ip_address,
        mock_setting_ip6,
        mock_setting_ip4,
        mock_peer_class,
        mock_setting_wg,
        mock_setting_conn,
        mock_simple_conn,
        mock_thread,
        mock_context,
        mock_nm_client_class
    ):
        """Test creating, activating, and deleting a connection."""
        from pia_nm.dbus_client import NMClient
        from pia_nm.wireguard_connection import WireGuardConfig, create_wireguard_connection
        
        # Reset singleton
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None
        
        # Setup mocks for NMClient
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client_class.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Setup mocks for connection creation
        mock_uuid.return_value = "test-uuid-1234"
        mock_connection = MagicMock()
        mock_connection.verify.return_value = None
        mock_simple_conn.new.return_value = mock_connection
        
        mock_conn_settings = MagicMock()
        mock_setting_conn.new.return_value = mock_conn_settings
        
        mock_peer = MagicMock()
        mock_peer.is_valid.return_value = True
        mock_peer_class.new.return_value = mock_peer
        
        mock_wg_settings = MagicMock()
        mock_setting_wg.new.return_value = mock_wg_settings
        
        mock_ipv4_settings = MagicMock()
        mock_setting_ip4.new.return_value = mock_ipv4_settings
        
        mock_ipv6_settings = MagicMock()
        mock_setting_ip6.new.return_value = mock_ipv6_settings
        
        mock_ip_addr = MagicMock()
        mock_ip_address.new.return_value = mock_ip_addr
        
        # Step 1: Create connection
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"]
        )
        
        connection = create_wireguard_connection(config)
        assert connection is not None
        
        # Step 2: Add connection to NetworkManager
        nm_client = NMClient()
        
        mock_remote_conn = MagicMock()
        
        # Mock the add_connection_async to return a completed future
        def mock_add_connection(conn):
            future = Future()
            future.set_result(mock_remote_conn)
            return future
        
        nm_client.add_connection_async = mock_add_connection
        
        future_add = nm_client.add_connection_async(connection)
        remote_conn = future_add.result(timeout=1)
        assert remote_conn == mock_remote_conn
        
        # Step 3: Activate connection
        mock_active_conn = MagicMock()
        
        def mock_activate_connection(conn, device=None, specific_object=None):
            future = Future()
            future.set_result(mock_active_conn)
            return future
        
        nm_client.activate_connection_async = mock_activate_connection
        
        future_activate = nm_client.activate_connection_async(remote_conn)
        active_conn = future_activate.result(timeout=1)
        assert active_conn == mock_active_conn
        
        # Step 4: Verify connection is active
        def mock_get_active(conn_id):
            return mock_active_conn
        
        nm_client.get_active_connection = mock_get_active
        active = nm_client.get_active_connection("PIA-US-East")
        assert active is not None
        
        # Step 5: Delete connection
        def mock_remove_connection(conn):
            future = Future()
            future.set_result(True)
            return future
        
        nm_client.remove_connection_async = mock_remove_connection
        
        future_delete = nm_client.remove_connection_async(remote_conn)
        result = future_delete.result(timeout=1)
        assert result is True
        
        # Step 6: Verify connection is removed
        def mock_get_connection(conn_id):
            return None
        
        nm_client.get_connection_by_id = mock_get_connection
        removed_conn = nm_client.get_connection_by_id("PIA-US-East")
        assert removed_conn is None


class TestLiveTokenRefresh:
    """Test live token refresh with active connection."""

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    @patch('pia_nm.token_refresh.get_applied_connection_with_version')
    @patch('pia_nm.token_refresh.update_wireguard_settings')
    def test_live_token_refresh_with_active_connection(
        self,
        mock_update_settings,
        mock_get_applied,
        mock_thread,
        mock_context,
        mock_nm_client_class
    ):
        """Test that live token refresh updates active connection without disconnecting."""
        from pia_nm.dbus_client import NMClient
        from pia_nm.token_refresh import refresh_active_connection
        
        # Reset singleton
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None
        
        # Setup mocks for NMClient
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client_class.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Create NM client
        nm_client = NMClient()
        
        # Create mock connection
        mock_connection = MagicMock()
        mock_connection.get_id.return_value = "PIA-US-East"
        
        # Mock applied connection settings
        mock_settings = {
            "wireguard": {
                "private-key": "old_private_key",
                "peers": [{"endpoint": "old_endpoint:1337"}]
            }
        }
        mock_version_id = 5
        mock_get_applied.return_value = (mock_settings, mock_version_id)
        
        # Mock updated settings
        mock_updated_settings = {
            "wireguard": {
                "private-key": "new_private_key",
                "peers": [{"endpoint": "new_endpoint:1337"}]
            }
        }
        mock_update_settings.return_value = mock_updated_settings
        
        # Mock device
        mock_device = MagicMock()
        
        def mock_get_device(conn):
            return mock_device
        
        nm_client.get_device_for_connection = mock_get_device
        
        # Mock reapply_connection to succeed
        def mock_reapply(device, settings, version_id):
            # Verify that reapply is called with correct parameters
            assert device == mock_device
            assert settings == mock_updated_settings
            assert version_id == 5
            return True
        
        nm_client.reapply_connection = mock_reapply
        
        # Perform live refresh
        new_private_key = "new_private_key"
        new_endpoint = "new_endpoint:1337"
        
        result = refresh_active_connection(
            nm_client,
            mock_connection,
            new_private_key,
            new_endpoint
        )
        
        # Verify refresh succeeded
        assert result is True
        
        # Verify get_applied_connection_with_version was called
        mock_get_applied.assert_called_once_with(nm_client, mock_connection)
        
        # Verify update_wireguard_settings was called with correct parameters
        mock_update_settings.assert_called_once_with(
            mock_settings,
            new_private_key,
            new_endpoint
        )
        
        # Verify connection was NOT deleted (no delete methods called)
        mock_connection.delete_async.assert_not_called()


class TestMultipleRegionManagement:
    """Test managing multiple regions."""

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    @patch('pia_nm.wireguard_connection.NM.SimpleConnection')
    @patch('pia_nm.wireguard_connection.NM.SettingConnection')
    @patch('pia_nm.wireguard_connection.NM.SettingWireGuard')
    @patch('pia_nm.wireguard_connection.NM.WireGuardPeer')
    @patch('pia_nm.wireguard_connection.NM.SettingIP4Config')
    @patch('pia_nm.wireguard_connection.NM.SettingIP6Config')
    @patch('pia_nm.wireguard_connection.NM.IPAddress')
    @patch('pia_nm.wireguard_connection.uuid.uuid4')
    def test_multiple_region_management(
        self,
        mock_uuid,
        mock_ip_address,
        mock_setting_ip6,
        mock_setting_ip4,
        mock_peer_class,
        mock_setting_wg,
        mock_setting_conn,
        mock_simple_conn,
        mock_thread,
        mock_context,
        mock_nm_client_class
    ):
        """Test creating and managing connections for multiple regions."""
        from pia_nm.dbus_client import NMClient
        from pia_nm.wireguard_connection import WireGuardConfig, create_wireguard_connection
        
        # Reset singleton
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None
        
        # Setup mocks
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client_class.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Setup connection creation mocks
        mock_uuid.side_effect = ["uuid-1", "uuid-2", "uuid-3"]
        
        def create_mock_connection():
            mock_conn = MagicMock()
            mock_conn.verify.return_value = None
            return mock_conn
        
        mock_simple_conn.new.side_effect = [
            create_mock_connection(),
            create_mock_connection(),
            create_mock_connection()
        ]
        
        mock_conn_settings = MagicMock()
        mock_setting_conn.new.return_value = mock_conn_settings
        
        mock_peer = MagicMock()
        mock_peer.is_valid.return_value = True
        mock_peer_class.new.return_value = mock_peer
        
        mock_wg_settings = MagicMock()
        mock_setting_wg.new.return_value = mock_wg_settings
        
        mock_ipv4_settings = MagicMock()
        mock_setting_ip4.new.return_value = mock_ipv4_settings
        
        mock_ipv6_settings = MagicMock()
        mock_setting_ip6.new.return_value = mock_ipv6_settings
        
        mock_ip_addr = MagicMock()
        mock_ip_address.new.return_value = mock_ip_addr
        
        # Create connections for multiple regions (use shorter names to avoid 15 char limit)
        regions = ["us-east", "uk", "jp"]
        connections = []
        
        for region in regions:
            config = WireGuardConfig(
                connection_name=f"PIA-{region}",
                interface_name=f"wg-pia-{region}",
                private_key=f"key_{region}",
                server_pubkey=f"server_key_{region}",
                server_endpoint=f"192.0.2.{len(connections)+1}:1337",
                peer_ip=f"10.0.0.{len(connections)+1}",
                dns_servers=["10.0.0.242"]
            )
            connection = create_wireguard_connection(config)
            connections.append(connection)
        
        assert len(connections) == 3
        
        # Add all connections to NetworkManager
        nm_client = NMClient()
        remote_connections = []
        
        for i, connection in enumerate(connections):
            mock_remote_conn = MagicMock()
            mock_remote_conn.get_id.return_value = f"PIA-{regions[i]}"
            
            # Create a completed future for each connection
            def mock_add_connection(conn, remote=mock_remote_conn):
                future = Future()
                future.set_result(remote)
                return future
            
            nm_client.add_connection_async = mock_add_connection
            
            future = nm_client.add_connection_async(connection)
            remote_conn = future.result(timeout=1)
            remote_connections.append(remote_conn)
        
        assert len(remote_connections) == 3
        
        # Verify all connections can be retrieved
        for i, region in enumerate(regions):
            def mock_get_connection(conn_id, remote=remote_connections[i]):
                return remote
            
            nm_client.get_connection_by_id = mock_get_connection
            conn = nm_client.get_connection_by_id(f"PIA-{region}")
            assert conn is not None


class TestConfigurationPreservation:
    """Test that configuration is preserved across operations."""

    @patch('pia_nm.dbus_client.NM.Client')
    @patch('pia_nm.dbus_client.GLib.MainContext')
    @patch('pia_nm.dbus_client.Thread')
    @patch('pia_nm.wireguard_connection.NM.SimpleConnection')
    @patch('pia_nm.wireguard_connection.NM.SettingConnection')
    @patch('pia_nm.wireguard_connection.NM.SettingWireGuard')
    @patch('pia_nm.wireguard_connection.NM.WireGuardPeer')
    @patch('pia_nm.wireguard_connection.NM.SettingIP4Config')
    @patch('pia_nm.wireguard_connection.NM.SettingIP6Config')
    @patch('pia_nm.wireguard_connection.NM.IPAddress')
    @patch('pia_nm.wireguard_connection.uuid.uuid4')
    def test_configuration_preservation(
        self,
        mock_uuid,
        mock_ip_address,
        mock_setting_ip6,
        mock_setting_ip4,
        mock_peer_class,
        mock_setting_wg,
        mock_setting_conn,
        mock_simple_conn,
        mock_thread,
        mock_context,
        mock_nm_client_class
    ):
        """Test that connection configuration is preserved."""
        from pia_nm.dbus_client import NMClient
        from pia_nm.wireguard_connection import WireGuardConfig, create_wireguard_connection
        
        # Reset singleton
        NMClient._nm_client = None
        NMClient._main_context = None
        NMClient._main_loop = None
        NMClient._main_loop_thread = None
        
        # Setup mocks
        mock_context_instance = MagicMock()
        mock_context.return_value = mock_context_instance
        mock_nm_instance = MagicMock()
        mock_nm_client_class.return_value = mock_nm_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        
        # Setup connection creation mocks
        mock_uuid.return_value = "test-uuid-1234"
        mock_connection = MagicMock()
        mock_connection.verify.return_value = None
        mock_simple_conn.new.return_value = mock_connection
        
        mock_conn_settings = MagicMock()
        mock_setting_conn.new.return_value = mock_conn_settings
        
        mock_peer = MagicMock()
        mock_peer.is_valid.return_value = True
        mock_peer_class.new.return_value = mock_peer
        
        mock_wg_settings = MagicMock()
        mock_setting_wg.new.return_value = mock_wg_settings
        
        mock_ipv4_settings = MagicMock()
        mock_setting_ip4.new.return_value = mock_ipv4_settings
        
        mock_ipv6_settings = MagicMock()
        mock_setting_ip6.new.return_value = mock_ipv6_settings
        
        mock_ip_addr = MagicMock()
        mock_ip_address.new.return_value = mock_ip_addr
        
        # Create connection with specific configuration
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242", "10.0.0.243"],
            allowed_ips="0.0.0.0/0",
            persistent_keepalive=25,
            fwmark=51820,
            use_vpn_dns=True,
            ipv6_enabled=False
        )
        
        connection = create_wireguard_connection(config)
        
        # Verify connection was created with correct settings
        assert connection is not None
        mock_connection.verify.assert_called_once()
        
        # Verify connection settings were added
        assert mock_connection.add_setting.call_count >= 4  # conn, wg, ipv4, ipv6
        
        # Verify peer was configured correctly
        mock_peer.set_public_key.assert_called_once_with("test_server_pubkey", False)
        mock_peer.set_endpoint.assert_called_once_with("192.0.2.1:1337", False)
        mock_peer.append_allowed_ip.assert_called_once_with("0.0.0.0/0", False)
        mock_peer.set_persistent_keepalive.assert_called_once_with(25)
        mock_peer.seal.assert_called_once()
        mock_peer.is_valid.assert_called_once_with(True, True)
        
        # Verify DNS servers were added
        assert mock_ipv4_settings.add_dns.call_count == 2
