"""NetworkManager interface for WireGuard profile management.

This module provides functions to manage WireGuard connection profiles in NetworkManager
via the nmcli command-line interface. It handles:
- Creating WireGuard profiles
- Updating profiles without disconnecting active connections
- Deleting profiles
- Checking profile status
- Listing PIA-managed profiles
"""

import logging
import subprocess
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class NetworkManagerError(Exception):
    """Base exception for NetworkManager operations."""

    pass


def profile_exists(profile_name: str) -> bool:
    """Check if a NetworkManager connection profile exists.

    Args:
        profile_name: Name of the connection profile to check

    Returns:
        True if profile exists, False otherwise

    Raises:
        NetworkManagerError: If nmcli command fails
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME", "connection", "show"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        profiles = result.stdout.strip().split("\n")
        exists = profile_name in profiles

        if exists:
            logger.debug(f"Profile exists: {profile_name}")
        else:
            logger.debug(f"Profile does not exist: {profile_name}")

        return exists

    except subprocess.CalledProcessError as e:
        logger.error(f"nmcli failed to list profiles: {e.stderr}")
        raise NetworkManagerError(f"Failed to check if profile exists: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        logger.error("nmcli command timed out")
        raise NetworkManagerError("nmcli command timed out") from e
    except FileNotFoundError as e:
        logger.error("nmcli command not found")
        raise NetworkManagerError(
            "nmcli command not found. Install NetworkManager: sudo apt install network-manager"
        ) from e


def is_active(profile_name: str) -> bool:
    """Check if a NetworkManager connection profile is currently active.

    Args:
        profile_name: Name of the connection profile to check

    Returns:
        True if profile is active, False otherwise

    Raises:
        NetworkManagerError: If nmcli command fails
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        if result.returncode != 0:
            logger.debug(f"Failed to get active connections: {result.stderr}")
            return False

        # Parse output: each line is "name:device"
        active_profiles = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(":")
                if parts:
                    active_profiles.append(parts[0])

        is_active_result = profile_name in active_profiles

        if is_active_result:
            logger.debug(f"Profile is active: {profile_name}")
        else:
            logger.debug(f"Profile is not active: {profile_name}")

        return is_active_result

    except subprocess.TimeoutExpired as e:
        logger.error("nmcli command timed out")
        raise NetworkManagerError("nmcli command timed out") from e
    except FileNotFoundError as e:
        logger.error("nmcli command not found")
        raise NetworkManagerError(
            "nmcli command not found. Install NetworkManager: sudo apt install network-manager"
        ) from e


def list_profiles() -> List[str]:
    """List all PIA-managed NetworkManager connection profiles.

    Returns:
        List of profile names that start with "PIA-"

    Raises:
        NetworkManagerError: If nmcli command fails
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME", "connection", "show"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        all_profiles = result.stdout.strip().split("\n")
        pia_profiles = [p for p in all_profiles if p.startswith("PIA-")]

        logger.info(f"Found {len(pia_profiles)} PIA-managed profiles")
        return pia_profiles

    except subprocess.CalledProcessError as e:
        logger.error(f"nmcli failed to list profiles: {e.stderr}")
        raise NetworkManagerError(f"Failed to list profiles: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        logger.error("nmcli command timed out")
        raise NetworkManagerError("nmcli command timed out") from e
    except FileNotFoundError as e:
        logger.error("nmcli command not found")
        raise NetworkManagerError(
            "nmcli command not found. Install NetworkManager: sudo apt install network-manager"
        ) from e


def create_profile(
    profile_name: str,
    private_key: str,
    server_pubkey: str,
    endpoint: str,
    peer_ip: str,
    dns_servers: List[str],
    listen_port: int = 0,
    keepalive: int = 25,
) -> bool:
    """Create a new WireGuard connection profile in NetworkManager.

    This function creates a WireGuard profile in two steps:
    1. Create base connection with nmcli connection add
    2. Configure WireGuard peer and network settings with nmcli connection modify

    Args:
        profile_name: Name for the connection profile (e.g., "PIA-US-East")
        private_key: WireGuard private key (base64-encoded)
        server_pubkey: WireGuard server public key (base64-encoded)
        endpoint: VPN server endpoint in format "IP:PORT"
        peer_ip: Assigned client IP address
        dns_servers: List of DNS server IP addresses
        listen_port: WireGuard listen port (0 for automatic)
        keepalive: Persistent keepalive interval in seconds

    Returns:
        True if profile created successfully, False otherwise

    Raises:
        NetworkManagerError: If nmcli commands fail
    """
    try:
        # Generate interface name from profile name
        ifname = f"wg-{profile_name.lower().replace(' ', '-')}"

        logger.info(f"Creating WireGuard profile: {profile_name}")

        # Step 1: Create base WireGuard connection
        logger.debug(f"Creating base connection: {profile_name}")
        result = subprocess.run(
            [
                "nmcli",
                "connection",
                "add",
                "type",
                "wireguard",
                "con-name",
                profile_name,
                "ifname",
                ifname,
                "wireguard.private-key",
                private_key,
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        logger.debug(f"Base connection created: {result.stdout.strip()}")

        # Step 2: Configure WireGuard peer and network settings
        logger.debug(f"Configuring peer and network settings for: {profile_name}")

        # Build DNS string
        dns_string = " ".join(dns_servers)

        modify_args = [
            "nmcli",
            "connection",
            "modify",
            profile_name,
            "wireguard.listen-port",
            str(listen_port),
            "+wireguard.peer",
            server_pubkey,
            "wireguard.peer.endpoint",
            endpoint,
            "wireguard.peer.allowed-ips",
            "0.0.0.0/0",
            "wireguard.peer.persistent-keepalive",
            str(keepalive),
            "ipv4.method",
            "manual",
            "ipv4.addresses",
            f"{peer_ip}/32",
            "ipv4.dns",
            dns_string,
            "ipv4.dns-priority",
            "-100",
            "ipv4.ignore-auto-dns",
            "yes",
            "ipv6.method",
            "disabled",
            "connection.autoconnect",
            "no",
        ]

        result = subprocess.run(
            modify_args,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        logger.info(f"Successfully created profile: {profile_name}")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"nmcli failed to create profile {profile_name}: {e.stderr}")
        raise NetworkManagerError(
            f"Failed to create profile {profile_name}: {e.stderr}"
        ) from e
    except subprocess.TimeoutExpired as e:
        logger.error(f"nmcli command timed out creating {profile_name}")
        raise NetworkManagerError(f"Profile creation timed out: {profile_name}") from e
    except FileNotFoundError as e:
        logger.error("nmcli command not found")
        raise NetworkManagerError(
            "nmcli command not found. Install NetworkManager: sudo apt install network-manager"
        ) from e


def update_profile(
    profile_name: str,
    private_key: str,
    server_pubkey: str,
    endpoint: str,
    peer_ip: str,
    dns_servers: List[str],
    listen_port: int = 0,
    keepalive: int = 25,
) -> bool:
    """Update an existing WireGuard connection profile in NetworkManager.

    This function updates a profile using nmcli connection modify, which preserves
    active connections. The active connection continues using the old configuration
    until it reconnects, at which point it uses the updated configuration.

    Args:
        profile_name: Name of the connection profile to update
        private_key: WireGuard private key (base64-encoded)
        server_pubkey: WireGuard server public key (base64-encoded)
        endpoint: VPN server endpoint in format "IP:PORT"
        peer_ip: Assigned client IP address
        dns_servers: List of DNS server IP addresses
        listen_port: WireGuard listen port (0 for automatic)
        keepalive: Persistent keepalive interval in seconds

    Returns:
        True if profile updated successfully, False otherwise

    Raises:
        NetworkManagerError: If nmcli commands fail
    """
    try:
        # Check if connection is active (for logging only)
        was_active = is_active(profile_name)

        if was_active:
            logger.info(
                f"Profile {profile_name} is active, updating without disconnecting"
            )
        else:
            logger.info(f"Updating profile: {profile_name}")

        # Build DNS string
        dns_string = " ".join(dns_servers)

        # Update profile using modify (preserves active connections)
        modify_args = [
            "nmcli",
            "connection",
            "modify",
            profile_name,
            "wireguard.private-key",
            private_key,
            "wireguard.listen-port",
            str(listen_port),
            "+wireguard.peer",
            server_pubkey,
            "wireguard.peer.endpoint",
            endpoint,
            "wireguard.peer.allowed-ips",
            "0.0.0.0/0",
            "wireguard.peer.persistent-keepalive",
            str(keepalive),
            "ipv4.method",
            "manual",
            "ipv4.addresses",
            f"{peer_ip}/32",
            "ipv4.dns",
            dns_string,
            "ipv4.dns-priority",
            "-100",
            "ipv4.ignore-auto-dns",
            "yes",
            "ipv6.method",
            "disabled",
            "connection.autoconnect",
            "no",
        ]

        result = subprocess.run(
            modify_args,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )

        if was_active:
            logger.info(
                f"Profile {profile_name} updated. New config will be used on next connection."
            )
        else:
            logger.info(f"Successfully updated profile: {profile_name}")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"nmcli failed to update profile {profile_name}: {e.stderr}")
        raise NetworkManagerError(
            f"Failed to update profile {profile_name}: {e.stderr}"
        ) from e
    except subprocess.TimeoutExpired as e:
        logger.error(f"nmcli command timed out updating {profile_name}")
        raise NetworkManagerError(f"Profile update timed out: {profile_name}") from e
    except FileNotFoundError as e:
        logger.error("nmcli command not found")
        raise NetworkManagerError(
            "nmcli command not found. Install NetworkManager: sudo apt install network-manager"
        ) from e


def delete_profile(profile_name: str) -> bool:
    """Delete a NetworkManager connection profile.

    Args:
        profile_name: Name of the connection profile to delete

    Returns:
        True if profile deleted successfully, False if profile didn't exist

    Raises:
        NetworkManagerError: If nmcli command fails for reasons other than profile not found
    """
    try:
        logger.info(f"Deleting profile: {profile_name}")

        result = subprocess.run(
            ["nmcli", "connection", "delete", profile_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        if result.returncode == 0:
            logger.info(f"Successfully deleted profile: {profile_name}")
            return True
        else:
            # Check if error is "profile not found"
            if "not found" in result.stderr.lower() or "unknown" in result.stderr.lower():
                logger.debug(f"Profile not found (already deleted): {profile_name}")
                return False
            else:
                logger.error(f"nmcli failed to delete profile {profile_name}: {result.stderr}")
                raise NetworkManagerError(
                    f"Failed to delete profile {profile_name}: {result.stderr}"
                )

    except subprocess.TimeoutExpired as e:
        logger.error(f"nmcli command timed out deleting {profile_name}")
        raise NetworkManagerError(f"Profile deletion timed out: {profile_name}") from e
    except FileNotFoundError as e:
        logger.error("nmcli command not found")
        raise NetworkManagerError(
            "nmcli command not found. Install NetworkManager: sudo apt install network-manager"
        ) from e
