"""
Token refresh logic for PIA WireGuard connections.

This module provides functionality to refresh PIA authentication tokens
and update WireGuard connection settings without disconnecting active
connections. It uses NetworkManager's Reapply method for live updates
and Update2 for saved profile updates.

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
from typing import Optional, Dict, Any, Tuple

import gi

gi.require_version("NM", "1.0")  # noqa: required before importing NM module
# pylint: disable=wrong-import-position
from gi.repository import NM

from pia_nm.dbus_client import NMClient

logger = logging.getLogger(__name__)


def is_connection_active(nm_client: NMClient, connection: NM.RemoteConnection) -> bool:
    """
    Check if a connection is currently active.

    Args:
        nm_client: NMClient instance
        connection: NM.RemoteConnection to check

    Returns:
        True if the connection is active, False otherwise
    """
    conn_id = connection.get_id()
    active_conn = nm_client.get_active_connection(conn_id)
    return active_conn is not None


def get_connection_settings(
    nm_client: NMClient, connection: NM.RemoteConnection
) -> Optional[Dict[str, Any]]:
    """
    Get the current settings for a connection.

    For active connections, this retrieves the applied settings via
    GetAppliedConnection. For inactive connections, this retrieves
    the saved settings.

    Args:
        nm_client: NMClient instance
        connection: NM.RemoteConnection to get settings for

    Returns:
        Dictionary of connection settings, or None if retrieval fails
    """
    conn_id = connection.get_id()

    # Check if connection is active
    active_conn = nm_client.get_active_connection(conn_id)

    if active_conn:
        # Get applied settings for active connection
        logger.debug("Getting applied settings for active connection: %s", conn_id)
        device = nm_client.get_device_for_connection(connection)

        if not device:
            logger.error("Could not find device for active connection: %s", conn_id)
            return None

        result = nm_client.get_applied_connection(device)
        if result:
            settings, version_id = result
            logger.debug("Retrieved applied settings with version_id: %d", version_id)
            return settings
    else:
        # Get saved settings for inactive connection
        logger.debug("Getting saved settings for inactive connection: %s", conn_id)
        try:
            settings = connection.to_dbus(NM.ConnectionSerializationFlags.ALL)
            logger.debug("Retrieved saved settings")
            return settings
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to get saved settings: %s", exc)
            return None

    return None


def update_wireguard_settings(
    settings: Dict[str, Any], private_key: str, server_endpoint: str
) -> Dict[str, Any]:
    """
    Update WireGuard settings with new private key and endpoint.

    This function creates a new settings dictionary with only the
    WireGuard private key and peer endpoint updated. All other settings
    are preserved.

    Args:
        settings: Current connection settings dictionary
        private_key: New WireGuard private key (base64-encoded)
        server_endpoint: New server endpoint in "ip:port" format

    Returns:
        Updated settings dictionary with new WireGuard configuration

    Raises:
        ValueError: If settings don't contain WireGuard configuration
    """
    import copy

    if "wireguard" not in settings:
        raise ValueError("Settings do not contain WireGuard configuration")

    # Create a deep copy of settings to avoid modifying the original
    updated_settings = copy.deepcopy(settings)

    # Update WireGuard settings
    wg_settings = updated_settings.get("wireguard", {})

    # Update private key
    wg_settings["private-key"] = private_key
    logger.debug("Updated private key in WireGuard settings")

    # Update peer endpoint
    if "peers" in wg_settings and len(wg_settings["peers"]) > 0:
        # Update the first peer's endpoint
        peers = wg_settings["peers"]
        if isinstance(peers, list) and len(peers) > 0:
            # Peers might be a list of tuples or dicts
            peer = peers[0]
            if isinstance(peer, dict):
                peer["endpoint"] = server_endpoint
            else:
                # If it's a tuple or other structure, we need to handle it
                logger.warning("Unexpected peer structure: %s", type(peer))
        logger.debug("Updated endpoint in WireGuard peer: %s", server_endpoint)
    else:
        logger.warning("No peers found in WireGuard settings")

    return updated_settings


def get_applied_connection_with_version(
    nm_client: NMClient, connection: NM.RemoteConnection
) -> Optional[Tuple[Dict[str, Any], int]]:
    """
    Get applied connection settings and version ID for an active connection.

    This is used before calling reapply_connection to get the current
    settings and version_id needed for the Reapply method.

    Args:
        nm_client: NMClient instance
        connection: NM.RemoteConnection to get applied settings for

    Returns:
        Tuple of (settings_dict, version_id) if successful, None otherwise
    """
    conn_id = connection.get_id()

    # Get the device for this connection
    device = nm_client.get_device_for_connection(connection)
    if not device:
        logger.error("Could not find device for connection: %s", conn_id)
        return None

    # Get applied connection
    result = nm_client.get_applied_connection(device)
    if not result:
        logger.error("Failed to get applied connection for: %s", conn_id)
        return None

    settings, version_id = result
    logger.debug("Retrieved applied connection with version_id: %d", version_id)

    return settings, version_id


def refresh_active_connection(
    nm_client: NMClient, connection: NM.RemoteConnection, private_key: str, server_endpoint: str
) -> bool:
    """
    Refresh an active connection with new credentials using Reapply.

    This function updates an active connection without disconnecting it.
    It retrieves the currently applied settings, updates the WireGuard
    private key and endpoint, and calls Reapply to apply the changes.

    This is the zero-downtime token refresh mechanism.

    Args:
        nm_client: NMClient instance
        connection: NM.RemoteConnection to refresh
        private_key: New WireGuard private key (base64-encoded)
        server_endpoint: New server endpoint in "ip:port" format

    Returns:
        True if refresh successful, False otherwise
    """
    conn_id = connection.get_id()
    logger.info("Refreshing active connection: %s", conn_id)

    try:
        # Get applied connection settings and version ID
        result = get_applied_connection_with_version(nm_client, connection)
        if not result:
            logger.error("Failed to get applied connection for: %s", conn_id)
            return False

        settings, version_id = result

        # Update WireGuard settings
        try:
            updated_settings = update_wireguard_settings(settings, private_key, server_endpoint)
        except ValueError as exc:
            logger.error("Failed to update WireGuard settings: %s", exc)
            return False

        # Get device for the connection
        device = nm_client.get_device_for_connection(connection)
        if not device:
            logger.error("Could not find device for connection: %s", conn_id)
            return False

        # Call Reapply to apply settings without disconnecting
        success = nm_client.reapply_connection(device, updated_settings, version_id)

        if success:
            logger.info("Successfully updated live connection: %s", conn_id)
            logger.info("Connection %s updated live (no disconnection)", conn_id)
            return True
        else:
            logger.error("Reapply failed for connection: %s", conn_id)
            return False

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error refreshing active connection %s: %s", conn_id, exc)
        return False


def refresh_inactive_connection(
    nm_client: NMClient, connection: NM.RemoteConnection, private_key: str, server_endpoint: str
) -> bool:
    """
    Refresh an inactive connection by updating the saved profile.

    This function updates a saved connection profile that is not currently
    active. The changes will take effect the next time the connection is
    activated.

    Args:
        nm_client: NMClient instance
        connection: NM.RemoteConnection to refresh
        private_key: New WireGuard private key (base64-encoded)
        server_endpoint: New server endpoint in "ip:port" format

    Returns:
        True if update successful, False otherwise
    """
    conn_id = connection.get_id()
    logger.info("Updating saved profile for inactive connection: %s", conn_id)

    try:
        # Get saved connection settings
        try:
            settings = connection.to_dbus(NM.ConnectionSerializationFlags.ALL)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to get saved settings for %s: %s", conn_id, exc)
            return False

        # Update WireGuard settings
        try:
            updated_settings = update_wireguard_settings(settings, private_key, server_endpoint)
        except ValueError as exc:
            logger.error("Failed to update WireGuard settings: %s", exc)
            return False

        # Update the connection with new settings
        # The Update2 method saves the connection to disk
        try:
            future = nm_client.update_connection_async(connection, updated_settings)
            future.result()  # Wait for the async operation to complete
            logger.info("Successfully updated saved profile: %s", conn_id)
            logger.info(
                "Connection %s updated saved profile (will use on next activation)", conn_id
            )
            return True
        except Exception as exc:  # pylint: disable=broad-except
            error_msg = str(exc)
            logger.error("Failed to update connection %s: %s", conn_id, error_msg)

            # Provide helpful hint for permission errors
            if "Insufficient privileges" in error_msg or "nm-settings-error-quark: 1" in error_msg:
                logger.error(
                    "Permission denied: Connection may be system-owned. "
                    "Try recreating connections with 'pia-nm setup' to fix permissions."
                )

            return False

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error updating inactive connection %s: %s", conn_id, exc)
        return False
