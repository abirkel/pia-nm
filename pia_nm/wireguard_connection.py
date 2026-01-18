"""
WireGuard connection builder for NetworkManager D-Bus API.

This module provides functionality to create WireGuard VPN connections
using NetworkManager's D-Bus API via PyGObject. It handles connection
settings, peer configuration, DNS, and routing.

Adapted from ProtonVPN's python-proton-vpn-network-manager implementation.

Copyright (c) 2023 Proton AG
Adapted for PIA NetworkManager Integration

This file is part of PIA NetworkManager Integration.

PIA NetworkManager Integration is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

PIA NetworkManager Integration is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with PIA NetworkManager Integration.  If not, see <https://www.gnu.org/licenses/>.
"""

import logging
import os
import pwd
import socket
import uuid
from dataclasses import dataclass
from typing import List

import gi

gi.require_version("NM", "1.0")  # noqa: required before importing NM module
# pylint: disable=wrong-import-position
from gi.repository import NM, GObject  # noqa: GObject must be imported for NM to work

logger = logging.getLogger(__name__)


def get_current_username() -> str:
    """
    Get the current user's username.

    Returns:
        Username of the current user

    Raises:
        RuntimeError: If username cannot be determined
    """
    try:
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception as exc:
        logger.error("Failed to get current username: %s", exc)
        raise RuntimeError(f"Failed to get current username: {exc}") from exc


@dataclass
class WireGuardConfig:
    """
    WireGuard connection configuration for PIA VPN.

    This dataclass contains all the necessary information to create a
    WireGuard connection profile in NetworkManager.

    Attributes:
        connection_name: Human-readable connection name (e.g., "PIA-US-East")
        interface_name: Network interface name (e.g., "wg-pia-us-east")
        private_key: WireGuard private key (base64-encoded)
        server_pubkey: Server's WireGuard public key (base64-encoded)
        server_endpoint: Server endpoint in "ip:port" format
        peer_ip: Client IP address assigned by PIA (e.g., "10.x.x.x")
        dns_servers: List of DNS server IP addresses
        allowed_ips: CIDR ranges to route through VPN (default: "0.0.0.0/0")
        persistent_keepalive: Keepalive interval in seconds (default: 25)
        fwmark: Firewall mark for packet routing (default: 0 = disabled)
        use_vpn_dns: Whether to use VPN DNS servers (default: True)
        ipv6_enabled: Whether to enable IPv6 (default: False)

    Note on Routing:
        NetworkManager's wireguard.ip4-auto-default-route (enabled by default when
        peers have 0.0.0.0/0 allowed-ips) uses policy-based routing with a dedicated
        routing table. The route metric is set to 50 to ensure VPN routes take priority
        over regular connections (typically metric 100+). The actual routing decision is
        made by policy rules, not the metric in the main table.
    """

    connection_name: str
    interface_name: str
    private_key: str
    server_pubkey: str
    server_endpoint: str  # "ip:port"
    peer_ip: str  # Client IP (e.g., "10.x.x.x")
    dns_servers: List[str]
    allowed_ips: str = "0.0.0.0/0"  # Default route
    persistent_keepalive: int = 25
    fwmark: int = 0  # No fwmark for simple VPN (0 = disabled)
    use_vpn_dns: bool = True
    ipv6_enabled: bool = False


def create_wireguard_connection(config: WireGuardConfig) -> NM.SimpleConnection:
    """
    Create a WireGuard connection using NetworkManager D-Bus API.

    This function builds a complete NM.SimpleConnection object configured
    for WireGuard VPN with proper peer configuration, DNS, and routing.

    The connection is created with the following characteristics:
    - WireGuard peer with specified public key, endpoint, and allowed-ips
    - Manual IPv4 configuration with /32 prefix
    - VPN DNS with high priority (-1500)
    - IPv6 disabled by default
    - No autoconnect
    - Volatile (not saved to disk)

    Args:
        config: WireGuardConfig containing all connection parameters

    Returns:
        NM.SimpleConnection configured for WireGuard VPN

    Raises:
        ValueError: If configuration is invalid or connection validation fails
        RuntimeError: If connection creation fails

    Example:
        >>> config = WireGuardConfig(
        ...     connection_name="PIA-US-East",
        ...     interface_name="wg-pia-us-east",
        ...     private_key="<base64_key>",
        ...     server_pubkey="<base64_key>",
        ...     server_endpoint="192.0.2.1:1337",
        ...     peer_ip="10.20.30.40",
        ...     dns_servers=["10.0.0.242", "10.0.0.243"]
        ... )
        >>> connection = create_wireguard_connection(config)
    """
    logger.info("Creating WireGuard connection: %s", config.connection_name)

    # Validate configuration
    _validate_config(config)

    # Create the base connection object
    connection = NM.SimpleConnection.new()

    # Add all settings to the connection
    _add_connection_settings(connection, config)
    _add_wireguard_settings(connection, config)
    _add_ipv4_settings(connection, config)
    _add_ipv6_settings(connection, config)

    # Validate the complete connection
    try:
        connection.verify()
        logger.info("Connection validation successful: %s", config.connection_name)
    except Exception as exc:
        logger.error("Connection validation failed: %s", exc)
        raise ValueError(f"Connection validation failed: {exc}") from exc

    return connection


def _validate_config(config: WireGuardConfig) -> None:
    """
    Validate WireGuardConfig parameters.

    Args:
        config: WireGuardConfig to validate

    Raises:
        ValueError: If any configuration parameter is invalid
    """
    if not config.connection_name:
        raise ValueError("connection_name cannot be empty")

    if not config.interface_name:
        raise ValueError("interface_name cannot be empty")

    if len(config.interface_name) > 15:
        raise ValueError(
            f"interface_name too long: {len(config.interface_name)} chars "
            f"(max 15): {config.interface_name}"
        )

    if not config.private_key:
        raise ValueError("private_key cannot be empty")

    if not config.server_pubkey:
        raise ValueError("server_pubkey cannot be empty")

    if not config.server_endpoint:
        raise ValueError("server_endpoint cannot be empty")

    if ":" not in config.server_endpoint:
        raise ValueError(f"server_endpoint must be in 'ip:port' format: {config.server_endpoint}")

    if not config.peer_ip:
        raise ValueError("peer_ip cannot be empty")

    if not config.dns_servers:
        raise ValueError("dns_servers cannot be empty")


def _add_connection_settings(connection: NM.SimpleConnection, config: WireGuardConfig) -> None:
    """
    Add NM.SettingConnection to the connection.

    This sets the connection name, UUID, type, interface name, and
    autoconnect behavior. Also sets permissions to allow the current
    user to modify the connection.

    Args:
        connection: NM.SimpleConnection to add settings to
        config: WireGuardConfig with connection parameters
    """
    logger.debug("Adding connection settings for: %s", config.connection_name)

    # Create connection settings
    conn_settings = NM.SettingConnection.new()

    # Set connection ID (human-readable name)
    conn_settings.set_property(NM.SETTING_CONNECTION_ID, config.connection_name)

    # Generate and set UUID
    connection_uuid = str(uuid.uuid4())
    conn_settings.set_property(NM.SETTING_CONNECTION_UUID, connection_uuid)
    logger.debug("Generated UUID: %s", connection_uuid)

    # Set connection type to WireGuard
    conn_settings.set_property(NM.SETTING_CONNECTION_TYPE, NM.SETTING_WIREGUARD_SETTING_NAME)

    # Set interface name
    conn_settings.set_property(NM.SETTING_CONNECTION_INTERFACE_NAME, config.interface_name)

    # Disable autoconnect (user must manually activate)
    conn_settings.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, False)

    # Set permissions to allow current user to modify the connection
    # Format: "user:{username}:" allows the user to modify this connection
    # This prevents "Insufficient privileges" errors during token refresh
    try:
        username = get_current_username()
        conn_settings.add_permission("user", username, None)
        logger.debug("Set connection permissions for user: %s", username)
    except Exception as exc:
        logger.warning("Failed to set connection permissions: %s", exc)
        logger.warning("Connection will be system-wide and may require root to modify")

    # Add the settings to the connection
    connection.add_setting(conn_settings)


def _add_wireguard_settings(connection: NM.SimpleConnection, config: WireGuardConfig) -> None:
    """
    Add NM.SettingWireGuard with peer configuration to the connection.

    This creates the WireGuard peer with public key, endpoint, allowed-ips,
    and keepalive settings, then adds it to the WireGuard settings.

    Args:
        connection: NM.SimpleConnection to add settings to
        config: WireGuardConfig with WireGuard parameters
    """
    logger.debug("Adding WireGuard settings for: %s", config.connection_name)

    # Create WireGuard peer
    peer = _create_wireguard_peer(config)

    # Create WireGuard settings and add peer
    wg_settings = NM.SettingWireGuard.new()

    # Set private key
    wg_settings.set_property(NM.SETTING_WIREGUARD_PRIVATE_KEY, config.private_key)

    # Set firewall mark
    wg_settings.set_property(NM.SETTING_WIREGUARD_FWMARK, config.fwmark)

    # Append the configured peer
    wg_settings.append_peer(peer)

    # Add the settings to the connection
    connection.add_setting(wg_settings)


def _create_wireguard_peer(config: WireGuardConfig) -> NM.WireGuardPeer:
    """
    Create and configure a WireGuard peer.

    This creates an NM.WireGuardPeer object with the server's public key,
    endpoint, allowed-ips, and persistent keepalive. The peer is sealed
    (made immutable) and validated before being returned.

    Args:
        config: WireGuardConfig with peer parameters

    Returns:
        Configured and sealed NM.WireGuardPeer

    Raises:
        ValueError: If peer validation fails
    """
    logger.debug("Creating WireGuard peer for endpoint: %s", config.server_endpoint)

    # Create new peer object
    peer = NM.WireGuardPeer.new()

    # Set server public key
    # The second parameter is "allow_invalid" - False means validate the key format
    # Note: The key must be a valid base64-encoded Curve25519 public key (44 chars)
    peer.set_public_key(config.server_pubkey, False)

    # Set server endpoint (ip:port)
    peer.set_endpoint(config.server_endpoint, False)

    # Set allowed-ips (routes through VPN)
    peer.append_allowed_ip(config.allowed_ips, False)
    logger.debug("Set allowed-ips: %s", config.allowed_ips)

    # Set persistent keepalive (if non-zero)
    if config.persistent_keepalive > 0:
        peer.set_persistent_keepalive(config.persistent_keepalive)

    # Seal the peer to make it immutable
    # After sealing, the peer cannot be modified (except ref/unref)
    # This is required by NetworkManager before the peer can be used
    peer.seal()
    logger.debug("Peer sealed (made immutable)")

    # Validate the peer configuration
    # This ensures all required fields are set correctly
    # Parameters: (check_interface, check_property) - both True for strict validation
    try:
        is_valid = peer.is_valid(True, True)
        if not is_valid:
            raise ValueError("Peer validation failed: is_valid returned False")
        logger.debug("Peer validation successful")
    except Exception as exc:
        logger.error("Peer validation failed: %s", exc)
        raise ValueError(f"Peer validation failed: {exc}") from exc

    return peer


def _add_ipv4_settings(connection: NM.SimpleConnection, config: WireGuardConfig) -> None:
    """
    Add NM.SettingIP4Config to the connection.

    This configures IPv4 with manual addressing, DNS servers, and routing.

    Args:
        connection: NM.SimpleConnection to add settings to
        config: WireGuardConfig with IPv4 parameters
    """
    logger.debug("Adding IPv4 settings for: %s", config.connection_name)

    # Create IPv4 configuration
    ipv4_config = NM.SettingIP4Config.new()

    # Set method to manual (we specify the address)
    ipv4_config.set_property(NM.SETTING_IP_CONFIG_METHOD, NM.SETTING_IP4_CONFIG_METHOD_MANUAL)

    # Add peer IP address with /32 prefix
    # The /32 prefix means this is a point-to-point connection
    ip_address = NM.IPAddress.new(socket.AF_INET, config.peer_ip, 32)
    ipv4_config.add_address(ip_address)
    logger.debug("Set peer IP: %s/32", config.peer_ip)

    # Set gateway to 0.0.0.0 for point-to-point WireGuard connection
    # This tells NetworkManager this is a valid default route without a traditional gateway
    ipv4_config.set_property(NM.SETTING_IP_CONFIG_GATEWAY, "0.0.0.0")
    logger.debug("Set gateway to 0.0.0.0 for point-to-point connection")

    # Set route metric to 50
    # NetworkManager's wireguard.ip4-auto-default-route feature (enabled by default)
    # uses policy-based routing with a dedicated table. The metric is adjusted by adding
    # a 20000 offset, resulting in metric 20050 in the dedicated routing table.
    #
    # How it works:
    # 1. Policy rule 31707 selects which routing table to use (table 51880 for VPN)
    # 2. Once the table is selected, the kernel uses metrics to choose between routes
    # 3. In our case, there's only one default route in table 51880, so the metric
    #    doesn't affect route selection - but it's still the correct value to set
    # 4. If multiple routes existed in the table, the metric would determine priority
    #
    # This metric ensures proper priority if multiple routes are added to the table.
    ipv4_config.set_property(NM.SETTING_IP_CONFIG_ROUTE_METRIC, 50)
    logger.debug("Set route metric to 50 (will be 20050 in dedicated table)")

    # Note: NetworkManager automatically creates routes based on the WireGuard 
    # peer's allowed-ips setting. The peer's allowed-ips="0.0.0.0/0" tells NM 
    # to route all traffic through the VPN via policy-based routing rules.

    # Configure DNS if use_vpn_dns is enabled
    if config.use_vpn_dns:
        # Set DNS priority to -1500 (highest priority)
        # This ensures VPN DNS takes precedence over system DNS
        ipv4_config.set_property(NM.SETTING_IP_CONFIG_DNS_PRIORITY, -1500)

        # Ignore auto DNS from DHCP
        ipv4_config.set_property(NM.SETTING_IP_CONFIG_IGNORE_AUTO_DNS, True)

        # Add DNS servers
        for dns_server in config.dns_servers:
            ipv4_config.add_dns(dns_server)
        logger.debug("Added DNS servers: %s", config.dns_servers)

        # Add DNS search domain "~" to route all DNS queries through VPN
        # The "~" is a special NetworkManager syntax meaning "route all domains"
        ipv4_config.add_dns_search("~")
        logger.debug("Added DNS search domain: ~")
    else:
        logger.debug("VPN DNS disabled, using system DNS")

    # Add the settings to the connection
    connection.add_setting(ipv4_config)


def _add_ipv6_settings(connection: NM.SimpleConnection, config: WireGuardConfig) -> None:
    """
    Add NM.SettingIP6Config to the connection.

    This configures IPv6 (disabled by default to prevent leaks).

    Args:
        connection: NM.SimpleConnection to add settings to
        config: WireGuardConfig with IPv6 parameters
    """
    logger.debug("Adding IPv6 settings for: %s", config.connection_name)

    # Create IPv6 configuration
    ipv6_config = NM.SettingIP6Config.new()

    # Check if IPv6 is enabled
    if config.ipv6_enabled:
        # IPv6 is enabled - would configure manual addressing here
        # This is a placeholder for future IPv6 support
        logger.debug("IPv6 enabled (future feature)")
        ipv6_config.set_property(NM.SETTING_IP_CONFIG_METHOD, NM.SETTING_IP6_CONFIG_METHOD_MANUAL)
        # TODO: Add IPv6 address, DNS, etc. when PIA supports it
    else:
        # IPv6 is disabled (default)
        logger.debug("IPv6 disabled")
        ipv6_config.set_property(
            NM.SETTING_IP_CONFIG_METHOD, NM.SETTING_IP6_CONFIG_METHOD_DISABLED
        )

    # Add the settings to the connection
    connection.add_setting(ipv6_config)
