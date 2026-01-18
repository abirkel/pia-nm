"""
WireGuard key management module.

This module handles WireGuard keypair generation, storage, loading, and rotation.
Keys are generated using the system's wg command-line tool via subprocess.

Functions:
- generate_keypair(): Generate new WireGuard private/public key pair
- save_keypair(): Store keypair to disk with proper permissions
- load_keypair(): Load existing keypair from disk
- should_rotate_key(): Check if key rotation is needed
- delete_keypair(): Delete keypair files

Copyright (C) 2025 PIA-NM Contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


class WireGuardError(Exception):
    """Base exception for WireGuard operations."""


def generate_keypair() -> Tuple[str, str]:
    """Generate a new WireGuard private/public key pair.

    Uses the system's wg command to generate keys. The private key is generated
    first, then the public key is derived from it.

    Returns:
        Tuple of (private_key, public_key) as base64-encoded strings

    Raises:
        WireGuardError: If key generation fails
    """
    try:
        # Generate private key
        result = subprocess.run(
            ["wg", "genkey"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        private_key = result.stdout.strip()

        if not private_key:
            raise WireGuardError("wg genkey produced empty output")

        # Derive public key from private key
        result = subprocess.run(
            ["wg", "pubkey"],
            input=private_key,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        public_key = result.stdout.strip()

        if not public_key:
            raise WireGuardError("wg pubkey produced empty output")

        logger.info("Generated new WireGuard keypair")
        return private_key, public_key

    except subprocess.CalledProcessError as e:
        logger.error(f"wg command failed: {e.stderr}")
        raise WireGuardError(f"Failed to generate keypair: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        logger.error("wg command timed out")
        raise WireGuardError("Key generation timed out") from e
    except FileNotFoundError as e:
        logger.error("wg command not found")
        raise WireGuardError(
            "wg command not found. Install wireguard-tools: sudo apt install wireguard-tools"
        ) from e


def save_keypair(region_id: str, private_key: str, public_key: str) -> None:
    """Save WireGuard keypair to disk with proper permissions.

    Private key is stored with 0600 permissions (user read/write only).
    Public key is stored with 0644 permissions (user read/write, others read).

    Args:
        region_id: Region identifier (e.g., 'us-east')
        private_key: Base64-encoded private key
        public_key: Base64-encoded public key

    Raises:
        WireGuardError: If key storage fails
    """
    try:
        keys_dir = Path.home() / ".config/pia-nm/keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        keys_dir.chmod(0o700)

        private_key_path = keys_dir / f"{region_id}.key"
        public_key_path = keys_dir / f"{region_id}.pub"

        # Write private key with restrictive permissions
        private_key_path.write_text(private_key)
        private_key_path.chmod(0o600)

        # Write public key with readable permissions
        public_key_path.write_text(public_key)
        public_key_path.chmod(0o644)

        logger.info(f"Saved keypair for region {region_id}")

    except (OSError, IOError) as e:
        logger.error(f"Failed to save keypair for {region_id}: {e}")
        raise WireGuardError(f"Failed to save keypair: {e}") from e


def load_keypair(region_id: str) -> Tuple[str, str]:
    """Load WireGuard keypair from disk.

    Args:
        region_id: Region identifier (e.g., 'us-east')

    Returns:
        Tuple of (private_key, public_key) as base64-encoded strings

    Raises:
        FileNotFoundError: If keypair files don't exist
        WireGuardError: If key loading fails
    """
    try:
        keys_dir = Path.home() / ".config/pia-nm/keys"
        private_key_path = keys_dir / f"{region_id}.key"
        public_key_path = keys_dir / f"{region_id}.pub"

        if not private_key_path.exists():
            logger.info(f"No existing keypair found for region {region_id}, will generate new one")
            raise FileNotFoundError(f"Private key not found: {private_key_path}")

        if not public_key_path.exists():
            logger.info(
                f"No existing public key found for region {region_id}, will generate new one"
            )
            raise FileNotFoundError(f"Public key not found: {public_key_path}")

        private_key = private_key_path.read_text().strip()
        public_key = public_key_path.read_text().strip()

        if not private_key or not public_key:
            raise WireGuardError("Keypair files are empty")

        logger.info(f"Loaded keypair for region {region_id}")
        return private_key, public_key

    except (OSError, IOError) as e:
        logger.debug(f"Failed to load keypair for {region_id}: {e}")
        raise WireGuardError(f"Failed to load keypair: {e}") from e


def should_rotate_key(region_id: str) -> bool:
    """Check if WireGuard key rotation is needed.

    A key should be rotated if it's older than 30 days.

    Args:
        region_id: Region identifier (e.g., 'us-east')

    Returns:
        True if key should be rotated, False otherwise
    """
    try:
        keys_dir = Path.home() / ".config/pia-nm/keys"
        private_key_path = keys_dir / f"{region_id}.key"

        if not private_key_path.exists():
            logger.debug(f"Key file not found for {region_id}, rotation needed")
            return True

        # Get file modification time
        mtime = private_key_path.stat().st_mtime
        current_time = time.time()
        age_seconds = current_time - mtime

        # 30 days in seconds
        thirty_days_seconds = 30 * 24 * 60 * 60

        should_rotate = age_seconds > thirty_days_seconds

        if should_rotate:
            age_days = age_seconds / (24 * 60 * 60)
            logger.info(f"Key for {region_id} is {age_days:.1f} days old, rotation needed")
        else:
            age_days = age_seconds / (24 * 60 * 60)
            logger.debug(f"Key for {region_id} is {age_days:.1f} days old, no rotation needed")

        return should_rotate

    except (OSError, IOError) as e:
        logger.error(f"Failed to check key age for {region_id}: {e}")
        # If we can't check, assume rotation is needed
        return True


def delete_keypair(region_id: str) -> None:
    """Delete WireGuard keypair files.

    Handles missing files gracefully - no error if files don't exist.

    Args:
        region_id: Region identifier (e.g., 'us-east')

    Raises:
        WireGuardError: If deletion fails for reasons other than missing files
    """
    try:
        keys_dir = Path.home() / ".config/pia-nm/keys"
        private_key_path = keys_dir / f"{region_id}.key"
        public_key_path = keys_dir / f"{region_id}.pub"

        # Delete private key if it exists
        if private_key_path.exists():
            private_key_path.unlink()
            logger.info(f"Deleted private key for {region_id}")

        # Delete public key if it exists
        if public_key_path.exists():
            public_key_path.unlink()
            logger.info(f"Deleted public key for {region_id}")

        if not private_key_path.exists() and not public_key_path.exists():
            logger.info(f"Keypair deleted for region {region_id}")

    except (OSError, IOError) as e:
        logger.error(f"Failed to delete keypair for {region_id}: {e}")
        raise WireGuardError(f"Failed to delete keypair: {e}") from e
