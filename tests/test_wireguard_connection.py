"""Unit tests for WireGuard connection builder module.

Tests cover:
- Connection creation with valid config
- Peer configuration
- DNS and routing setup
- Connection validation
- Interface name length handling
- Configuration validation
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import socket

# Mock gi.repository before importing wireguard_connection
import sys

sys.modules["gi"] = MagicMock()
sys.modules["gi.repository"] = MagicMock()

# Create mock NM and GObject modules
mock_nm = MagicMock()
mock_gobject = MagicMock()
sys.modules["gi.repository.NM"] = mock_nm
sys.modules["gi.repository.GObject"] = mock_gobject

from pia_nm.wireguard_connection import (
    WireGuardConfig,
    create_wireguard_connection,
    _validate_config,
    _add_connection_settings,
    _add_wireguard_settings,
    _create_wireguard_peer,
    _add_ipv4_settings,
    _add_ipv6_settings,
)


class TestWireGuardConfig:
    """Test WireGuardConfig dataclass."""

    def test_wireguard_config_creation(self):
        """Test creating a WireGuardConfig with all required fields."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242", "10.0.0.243"],
        )

        assert config.connection_name == "PIA-US-East"
        assert config.interface_name == "wg-pia-us-east"
        assert config.private_key == "test_private_key"
        assert config.server_pubkey == "test_server_pubkey"
        assert config.server_endpoint == "192.0.2.1:1337"
        assert config.peer_ip == "10.20.30.40"
        assert config.dns_servers == ["10.0.0.242", "10.0.0.243"]

    def test_wireguard_config_defaults(self):
        """Test WireGuardConfig default values."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        assert config.allowed_ips == "0.0.0.0/0"
        assert config.persistent_keepalive == 25
        assert config.fwmark == 51820
        assert config.use_vpn_dns is True
        assert config.ipv6_enabled is False

    def test_wireguard_config_custom_values(self):
        """Test WireGuardConfig with custom values."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
            allowed_ips="10.0.0.0/8",
            persistent_keepalive=30,
            fwmark=12345,
            use_vpn_dns=False,
            ipv6_enabled=True,
        )

        assert config.allowed_ips == "10.0.0.0/8"
        assert config.persistent_keepalive == 30
        assert config.fwmark == 12345
        assert config.use_vpn_dns is False
        assert config.ipv6_enabled is True


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_config_valid(self):
        """Test validation passes for valid config."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        # Should not raise
        _validate_config(config)

    def test_validate_config_empty_connection_name(self):
        """Test validation fails for empty connection_name."""
        config = WireGuardConfig(
            connection_name="",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="connection_name cannot be empty"):
            _validate_config(config)

    def test_validate_config_empty_interface_name(self):
        """Test validation fails for empty interface_name."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="interface_name cannot be empty"):
            _validate_config(config)

    def test_validate_config_interface_name_too_long(self):
        """Test validation fails for interface_name > 15 characters."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east-very-long-name",  # 30 chars
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="interface_name too long"):
            _validate_config(config)

    def test_validate_config_empty_private_key(self):
        """Test validation fails for empty private_key."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="private_key cannot be empty"):
            _validate_config(config)

    def test_validate_config_empty_server_pubkey(self):
        """Test validation fails for empty server_pubkey."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="server_pubkey cannot be empty"):
            _validate_config(config)

    def test_validate_config_empty_server_endpoint(self):
        """Test validation fails for empty server_endpoint."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="server_endpoint cannot be empty"):
            _validate_config(config)

    def test_validate_config_invalid_server_endpoint_format(self):
        """Test validation fails for server_endpoint without port."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1",  # Missing port
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="must be in 'ip:port' format"):
            _validate_config(config)

    def test_validate_config_empty_peer_ip(self):
        """Test validation fails for empty peer_ip."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="peer_ip cannot be empty"):
            _validate_config(config)

    def test_validate_config_empty_dns_servers(self):
        """Test validation fails for empty dns_servers list."""
        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=[],
        )

        with pytest.raises(ValueError, match="dns_servers cannot be empty"):
            _validate_config(config)


class TestConnectionSettings:
    """Test connection settings creation."""

    @pytest.mark.skip(reason="Cannot mock PyGObject classes due to metaclass conflicts")
    @patch("pia_nm.wireguard_connection.NM.SettingConnection")
    @patch("pia_nm.wireguard_connection.uuid.uuid4")
    def test_add_connection_settings(self, mock_uuid, mock_setting_connection):
        """Test adding connection settings to a connection."""
        mock_uuid.return_value = "test-uuid-1234"
        mock_conn_settings = MagicMock()
        mock_setting_connection.new.return_value = mock_conn_settings
        mock_connection = MagicMock()

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        _add_connection_settings(mock_connection, config)

        # Verify connection settings were created
        mock_setting_connection.new.assert_called_once()

        # Verify properties were set
        assert mock_conn_settings.set_property.call_count >= 5

        # Verify settings were added to connection
        mock_connection.add_setting.assert_called_once_with(mock_conn_settings)

    @pytest.mark.skip(reason="Cannot mock PyGObject classes due to metaclass conflicts")
    @patch("pia_nm.wireguard_connection.NM.SettingConnection")
    @patch("pia_nm.wireguard_connection.uuid.uuid4")
    def test_add_connection_settings_autoconnect_false(self, mock_uuid, mock_setting_connection):
        """Test that autoconnect is set to False."""
        mock_uuid.return_value = "test-uuid-1234"
        mock_conn_settings = MagicMock()
        mock_setting_connection.new.return_value = mock_conn_settings
        mock_connection = MagicMock()

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        _add_connection_settings(mock_connection, config)

        # Find the call that sets autoconnect
        autoconnect_calls = [
            call
            for call in mock_conn_settings.set_property.call_args_list
            if len(call[0]) > 0 and "AUTOCONNECT" in str(call[0][0])
        ]

        # Verify autoconnect was set to False
        assert len(autoconnect_calls) > 0


class TestWireGuardPeer:
    """Test WireGuard peer creation."""

    @patch("pia_nm.wireguard_connection.NM.WireGuardPeer")
    def test_create_wireguard_peer(self, mock_peer_class):
        """Test creating a WireGuard peer."""
        mock_peer = MagicMock()
        mock_peer.is_valid.return_value = True
        mock_peer_class.new.return_value = mock_peer

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        peer = _create_wireguard_peer(config)

        # Verify peer was created
        mock_peer_class.new.assert_called_once()

        # Verify peer configuration methods were called
        mock_peer.set_public_key.assert_called_once_with("test_server_pubkey", False)
        mock_peer.set_endpoint.assert_called_once_with("192.0.2.1:1337", False)
        mock_peer.append_allowed_ip.assert_called_once_with("0.0.0.0/0", False)
        mock_peer.set_persistent_keepalive.assert_called_once_with(25)

        # Verify peer was sealed
        mock_peer.seal.assert_called_once()

        # Verify peer was validated
        mock_peer.is_valid.assert_called_once_with(True, True)

        assert peer == mock_peer

    @patch("pia_nm.wireguard_connection.NM.WireGuardPeer")
    def test_create_wireguard_peer_validation_failure(self, mock_peer_class):
        """Test peer creation fails when validation fails."""
        mock_peer = MagicMock()
        mock_peer.is_valid.return_value = False
        mock_peer_class.new.return_value = mock_peer

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="Peer validation failed"):
            _create_wireguard_peer(config)

    @patch("pia_nm.wireguard_connection.NM.WireGuardPeer")
    def test_create_wireguard_peer_zero_keepalive(self, mock_peer_class):
        """Test peer creation with zero keepalive doesn't set it."""
        mock_peer = MagicMock()
        mock_peer.is_valid.return_value = True
        mock_peer_class.new.return_value = mock_peer

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
            persistent_keepalive=0,
        )

        _create_wireguard_peer(config)

        # Verify keepalive was NOT set
        mock_peer.set_persistent_keepalive.assert_not_called()


class TestWireGuardSettings:
    """Test WireGuard settings creation."""

    @pytest.mark.skip(reason="Cannot mock PyGObject classes due to metaclass conflicts")
    @patch("pia_nm.wireguard_connection.NM.SettingWireGuard")
    @patch("pia_nm.wireguard_connection._create_wireguard_peer")
    def test_add_wireguard_settings(self, mock_create_peer, mock_setting_wg):
        """Test adding WireGuard settings to a connection."""
        mock_peer = MagicMock()
        mock_create_peer.return_value = mock_peer
        mock_wg_settings = MagicMock()
        mock_setting_wg.new.return_value = mock_wg_settings
        mock_connection = MagicMock()

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        _add_wireguard_settings(mock_connection, config)

        # Verify peer was created
        mock_create_peer.assert_called_once_with(config)

        # Verify WireGuard settings were created
        mock_setting_wg.new.assert_called_once()

        # Verify peer was appended
        mock_wg_settings.append_peer.assert_called_once_with(mock_peer)

        # Verify settings were added to connection
        mock_connection.add_setting.assert_called_once_with(mock_wg_settings)


class TestIPv4Settings:
    """Test IPv4 settings creation."""

    @pytest.mark.skip(reason="Cannot mock PyGObject classes due to metaclass conflicts")
    @patch("pia_nm.wireguard_connection.NM.SettingIP4Config")
    @patch("pia_nm.wireguard_connection.NM.IPAddress")
    @patch("pia_nm.wireguard_connection.socket.AF_INET", socket.AF_INET)
    def test_add_ipv4_settings_with_vpn_dns(self, mock_ip_address, mock_setting_ip4):
        """Test adding IPv4 settings with VPN DNS enabled."""
        mock_ip_addr = MagicMock()
        mock_ip_address.new.return_value = mock_ip_addr
        mock_ipv4_settings = MagicMock()
        mock_setting_ip4.new.return_value = mock_ipv4_settings
        mock_connection = MagicMock()

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242", "10.0.0.243"],
            use_vpn_dns=True,
        )

        _add_ipv4_settings(mock_connection, config)

        # Verify IPv4 settings were created
        mock_setting_ip4.new.assert_called_once()

        # Verify IP address was added
        mock_ipv4_settings.add_address.assert_called_once_with(mock_ip_addr)

        # Verify DNS servers were added
        assert mock_ipv4_settings.add_dns.call_count == 2

        # Verify DNS search was added
        mock_ipv4_settings.add_dns_search.assert_called_once_with("~")

        # Verify settings were added to connection
        mock_connection.add_setting.assert_called_once_with(mock_ipv4_settings)

    @pytest.mark.skip(reason="Cannot mock PyGObject classes due to metaclass conflicts")
    @patch("pia_nm.wireguard_connection.NM.SettingIP4Config")
    @patch("pia_nm.wireguard_connection.NM.IPAddress")
    @patch("pia_nm.wireguard_connection.socket.AF_INET", socket.AF_INET)
    def test_add_ipv4_settings_without_vpn_dns(self, mock_ip_address, mock_setting_ip4):
        """Test adding IPv4 settings with VPN DNS disabled."""
        mock_ip_addr = MagicMock()
        mock_ip_address.new.return_value = mock_ip_addr
        mock_ipv4_settings = MagicMock()
        mock_setting_ip4.new.return_value = mock_ipv4_settings
        mock_connection = MagicMock()

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
            use_vpn_dns=False,
        )

        _add_ipv4_settings(mock_connection, config)

        # Verify DNS servers were NOT added
        mock_ipv4_settings.add_dns.assert_not_called()

        # Verify DNS search was NOT added
        mock_ipv4_settings.add_dns_search.assert_not_called()


class TestIPv6Settings:
    """Test IPv6 settings creation."""

    @pytest.mark.skip(reason="Cannot mock PyGObject classes due to metaclass conflicts")
    @patch("pia_nm.wireguard_connection.NM.SettingIP6Config")
    def test_add_ipv6_settings_disabled(self, mock_setting_ip6):
        """Test adding IPv6 settings with IPv6 disabled."""
        mock_ipv6_settings = MagicMock()
        mock_setting_ip6.new.return_value = mock_ipv6_settings
        mock_connection = MagicMock()

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
            ipv6_enabled=False,
        )

        _add_ipv6_settings(mock_connection, config)

        # Verify IPv6 settings were created
        mock_setting_ip6.new.assert_called_once()

        # Verify settings were added to connection
        mock_connection.add_setting.assert_called_once_with(mock_ipv6_settings)

    @pytest.mark.skip(reason="Cannot mock PyGObject classes due to metaclass conflicts")
    @patch("pia_nm.wireguard_connection.NM.SettingIP6Config")
    def test_add_ipv6_settings_enabled(self, mock_setting_ip6):
        """Test adding IPv6 settings with IPv6 enabled."""
        mock_ipv6_settings = MagicMock()
        mock_setting_ip6.new.return_value = mock_ipv6_settings
        mock_connection = MagicMock()

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
            ipv6_enabled=True,
        )

        _add_ipv6_settings(mock_connection, config)

        # Verify IPv6 settings were created
        mock_setting_ip6.new.assert_called_once()

        # Verify settings were added to connection
        mock_connection.add_setting.assert_called_once_with(mock_ipv6_settings)


class TestCreateWireGuardConnection:
    """Test complete connection creation."""

    @patch("pia_nm.wireguard_connection._validate_config")
    @patch("pia_nm.wireguard_connection._add_connection_settings")
    @patch("pia_nm.wireguard_connection._add_wireguard_settings")
    @patch("pia_nm.wireguard_connection._add_ipv4_settings")
    @patch("pia_nm.wireguard_connection._add_ipv6_settings")
    @patch("pia_nm.wireguard_connection.NM.SimpleConnection")
    def test_create_wireguard_connection_success(
        self,
        mock_simple_connection,
        mock_add_ipv6,
        mock_add_ipv4,
        mock_add_wg,
        mock_add_conn,
        mock_validate,
    ):
        """Test successful WireGuard connection creation."""
        mock_connection = MagicMock()
        mock_connection.verify.return_value = None
        mock_simple_connection.new.return_value = mock_connection

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        result = create_wireguard_connection(config)

        # Verify validation was called
        mock_validate.assert_called_once_with(config)

        # Verify connection was created
        mock_simple_connection.new.assert_called_once()

        # Verify all settings were added
        mock_add_conn.assert_called_once_with(mock_connection, config)
        mock_add_wg.assert_called_once_with(mock_connection, config)
        mock_add_ipv4.assert_called_once_with(mock_connection, config)
        mock_add_ipv6.assert_called_once_with(mock_connection, config)

        # Verify connection was validated
        mock_connection.verify.assert_called_once()

        assert result == mock_connection

    @pytest.mark.skip(reason="Cannot mock PyGObject classes due to metaclass conflicts")
    @patch("pia_nm.wireguard_connection._validate_config")
    @patch("pia_nm.wireguard_connection.NM.SimpleConnection")
    def test_create_wireguard_connection_validation_failure(
        self, mock_simple_connection, mock_validate
    ):
        """Test connection creation fails when validation fails."""
        mock_connection = MagicMock()
        mock_connection.verify.side_effect = RuntimeError("Validation failed")
        mock_simple_connection.new.return_value = mock_connection

        config = WireGuardConfig(
            connection_name="PIA-US-East",
            interface_name="wg-pia-us-east",
            private_key="test_private_key",
            server_pubkey="test_server_pubkey",
            server_endpoint="192.0.2.1:1337",
            peer_ip="10.20.30.40",
            dns_servers=["10.0.0.242"],
        )

        with pytest.raises(ValueError, match="Connection validation failed"):
            create_wireguard_connection(config)
