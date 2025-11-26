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
            logger.debug("Profile exists: %s", profile_name)
        else:
            logger.debug("Profile does not exist: %s", profile_name)

        return exists

    except subprocess.CalledProcessError as e:
        logger.error("nmcli failed to list profiles: %s", e.stderr)
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
            logger.debug("Failed to get active connections: %s", result.stderr)
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
            logger.debug("Profile is active: %s", profile_name)
        else:
            logger.debug("Profile is not active: %s", profile_name)

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

        logger.info("Found %d PIA-managed profiles", len(pia_profiles))
        return pia_profiles

    except subprocess.CalledProcessError as e:
        logger.error("nmcli failed to list profiles: %s", e.stderr)
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
    config: Dict[str, Any],
    listen_port: int = 0,
    keepalive: int = 25,
) -> bool:
    """Create a new WireGuard connection profile in NetworkManager.

    This function creates a WireGuard profile by importing a config file.

    Args:
        profile_name: Name for the connection profile (e.g., "PIA-US-East")
        config: Configuration dictionary with keys:
            - private_key: WireGuard private key (base64-encoded)
            - server_pubkey: WireGuard server public key (base64-encoded)
            - endpoint: VPN server endpoint in format "IP:PORT"
            - peer_ip: Assigned client IP address
            - dns_servers: List of DNS server IP addresses
        listen_port: WireGuard listen port (0 for automatic)
        keepalive: Persistent keepalive interval in seconds

    Returns:
        True if profile created successfully, False otherwise

    Raises:
        NetworkManagerError: If nmcli commands fail
    """
    import tempfile
    from pathlib import Path
    
    try:
        # Extract config values
        private_key = config["private_key"]
        server_pubkey = config["server_pubkey"]
        endpoint = config["endpoint"]
        peer_ip = config["peer_ip"]
        dns_servers = config["dns_servers"]

        # Generate interface name (max 15 chars for Linux)
        # Use a hash of profile name to keep it short and unique
        import hashlib
        name_hash = hashlib.md5(profile_name.encode()).hexdigest()[:8]
        ifname = f"wg-{name_hash}"

        logger.info("Creating WireGuard profile: %s", profile_name)

        # Create WireGuard config file
        dns_string = ",".join(dns_servers)
        wg_config = f"""[Interface]
PrivateKey = {private_key}
Address = {peer_ip}/32
DNS = {dns_string}

[Peer]
PublicKey = {server_pubkey}
Endpoint = {endpoint}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = {keepalive}
"""

        # Write config to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write(wg_config)
            temp_config_path = f.name

        try:
            # Import the WireGuard config
            logger.debug("Importing WireGuard config for: %s", profile_name)
            result = subprocess.run(
                [
                    "nmcli",
                    "connection",
                    "import",
                    "type",
                    "wireguard",
                    "file",
                    temp_config_path,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )

            # Get the connection name that was created (nmcli uses filename as connection name)
            imported_name = Path(temp_config_path).stem
            
            # Rename to our desired name if different
            if imported_name != profile_name:
                subprocess.run(
                    ["nmcli", "connection", "modify", imported_name, "connection.id", profile_name],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10,
                )
            
            # Set additional properties
            subprocess.run(
                [
                    "nmcli", "connection", "modify", profile_name,
                    "connection.interface-name", ifname,
                    "connection.autoconnect", "no",
                    "ipv4.dns-priority", "-100",
                    "ipv4.never-default", "no",
                    "ipv4.route-metric", "100",
                    "ipv6.method", "ignore",
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )

            logger.info("Successfully created profile: %s", profile_name)
            return True

        finally:
            # Clean up temp file
            Path(temp_config_path).unlink(missing_ok=True)

    except subprocess.CalledProcessError as e:
        logger.error("nmcli failed to create profile %s: %s", profile_name, e.stderr)
        raise NetworkManagerError(f"Failed to create profile {profile_name}: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        logger.error("nmcli command timed out creating %s", profile_name)
        raise NetworkManagerError(f"Profile creation timed out: {profile_name}") from e
    except FileNotFoundError as e:
        logger.error("nmcli command not found")
        raise NetworkManagerError(
            "nmcli command not found. Install NetworkManager: sudo apt install network-manager"
        ) from e


def update_profile(
    profile_name: str,
    config: Dict[str, Any],
    listen_port: int = 0,
    keepalive: int = 25,
) -> bool:
    """Update an existing WireGuard connection profile in NetworkManager.

    This function deletes and recreates the profile. Note: This will disconnect
    active connections.

    Args:
        profile_name: Name of the connection profile to update
        config: Configuration dictionary with keys:
            - private_key: WireGuard private key (base64-encoded)
            - server_pubkey: WireGuard server public key (base64-encoded)
            - endpoint: VPN server endpoint in format "IP:PORT"
            - peer_ip: Assigned client IP address
            - dns_servers: List of DNS server IP addresses
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
            logger.info("Profile %s is active, will be disconnected during update", profile_name)
        else:
            logger.info("Updating profile: %s", profile_name)

        # Delete existing profile
        delete_profile(profile_name)
        
        # Recreate with new config
        success = create_profile(profile_name, config, listen_port, keepalive)

        if was_active:
            logger.info(
                "Profile %s updated. Connection was disconnected, reconnect manually.", profile_name
            )
        else:
            logger.info("Successfully updated profile: %s", profile_name)

        return success

    except NetworkManagerError:
        raise
    except Exception as e:
        logger.error("Unexpected error updating profile %s: %s", profile_name, e)
        raise NetworkManagerError(f"Failed to update profile {profile_name}: {e}") from e


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
        logger.info("Deleting profile: %s", profile_name)

        result = subprocess.run(
            ["nmcli", "connection", "delete", profile_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        if result.returncode == 0:
            logger.info("Successfully deleted profile: %s", profile_name)
            return True
        else:
            # Check if error is "profile not found"
            if "not found" in result.stderr.lower() or "unknown" in result.stderr.lower():
                logger.debug("Profile not found (already deleted): %s", profile_name)
                return False
            else:
                logger.error("nmcli failed to delete profile %s: %s", profile_name, result.stderr)
                raise NetworkManagerError(
                    f"Failed to delete profile {profile_name}: {result.stderr}"
                )

    except subprocess.TimeoutExpired as e:
        logger.error("nmcli command timed out deleting %s", profile_name)
        raise NetworkManagerError(f"Profile deletion timed out: {profile_name}") from e
    except FileNotFoundError as e:
        logger.error("nmcli command not found")
        raise NetworkManagerError(
            "nmcli command not found. Install NetworkManager: sudo apt install network-manager"
        ) from e
