"""Configuration management for PIA NetworkManager Integration.

This module handles:
- YAML configuration file read/write
- Configuration validation
- Keyring-based credential storage
- Region management
- Directory structure creation
"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import keyring
import yaml
from keyring.errors import KeyringError

logger = logging.getLogger(__name__)

# Service name for keyring entries
KEYRING_SERVICE = "pia-nm"
KEYRING_USERNAME_KEY = "username"
KEYRING_PASSWORD_KEY = "password"


class ConfigError(Exception):
    """Configuration-related error."""

    pass


class ConfigManager:
    """Manages configuration files and credentials for pia-nm."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize ConfigManager with optional custom config path.

        Args:
            config_path: Optional custom path to config file. Defaults to
                        ~/.config/pia-nm/config.yaml
        """
        if config_path is None:
            self.config_path = Path.home() / ".config/pia-nm/config.yaml"
        else:
            self.config_path = config_path

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories with proper permissions."""
        # Config directory
        config_dir = self.config_path.parent
        config_dir.mkdir(parents=True, exist_ok=True)
        config_dir.chmod(0o700)  # User read/write/execute only

        # Keys directory
        keys_dir = config_dir / "keys"
        keys_dir.mkdir(exist_ok=True)
        keys_dir.chmod(0o700)

        # Logs directory
        log_dir = Path.home() / ".local/share/pia-nm/logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_dir.chmod(0o755)  # Readable by others

        logger.debug("Ensured directory structure exists")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure.

        Returns:
            Dictionary with default configuration
        """
        return {
            "regions": [],
            "preferences": {
                "dns": True,
                "ipv6": False,
                "port_forwarding": False,
            },
            "metadata": {
                "version": 1,
                "last_refresh": None,
            },
        }

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration structure and data types.

        Args:
            config: Configuration dictionary to validate

        Raises:
            ConfigError: If configuration is invalid
        """
        # Check required top-level keys
        required_keys = ["regions", "preferences", "metadata"]
        for key in required_keys:
            if key not in config:
                raise ConfigError(f"Missing required key: {key}")

        # Validate regions
        if not isinstance(config["regions"], list):
            raise ConfigError("'regions' must be a list")

        for region in config["regions"]:
            if not isinstance(region, str):
                raise ConfigError(f"Region must be string, got {type(region)}")

        # Validate preferences
        prefs = config["preferences"]
        if not isinstance(prefs, dict):
            raise ConfigError("'preferences' must be a dictionary")

        required_prefs = ["dns", "ipv6", "port_forwarding"]
        for pref in required_prefs:
            if pref not in prefs:
                raise ConfigError(f"Missing preference: {pref}")
            if not isinstance(prefs[pref], bool):
                raise ConfigError(f"Preference '{pref}' must be boolean")

        # Validate metadata
        meta = config["metadata"]
        if not isinstance(meta, dict):
            raise ConfigError("'metadata' must be a dictionary")

        if "version" not in meta or not isinstance(meta["version"], int):
            raise ConfigError("Invalid metadata.version")

        if "last_refresh" in meta and meta["last_refresh"] is not None:
            if not isinstance(meta["last_refresh"], str):
                raise ConfigError("metadata.last_refresh must be string or null")

    def load(self) -> Dict[str, Any]:
        """Load and validate configuration from YAML file.

        Returns:
            Configuration dictionary

        Raises:
            ConfigError: If configuration file is invalid or missing
        """
        if not self.config_path.exists():
            logger.info("Config file not found, creating default")
            config = self._get_default_config()
            self.save(config)
            return config

        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)

            if config is None:
                config = self._get_default_config()

            self._validate_config(config)
            logger.debug("Configuration loaded and validated")
            return config

        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in config file: {e}")
        except OSError as e:
            raise ConfigError(f"Failed to read config file: {e}")

    def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to YAML file with proper permissions.

        Args:
            config: Configuration dictionary to save

        Raises:
            ConfigError: If validation fails or save operation fails
        """
        self._validate_config(config)

        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write config
            with open(self.config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            # Set restrictive permissions
            self.config_path.chmod(0o600)
            logger.debug("Configuration saved")

        except OSError as e:
            raise ConfigError(f"Failed to save config file: {e}")
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to serialize config to YAML: {e}")

    def get_credentials(self) -> Tuple[str, str]:
        """Retrieve username and password from system keyring.

        Returns:
            Tuple of (username, password)

        Raises:
            ConfigError: If credentials not found or keyring error occurs
        """
        try:
            username = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
            password = keyring.get_password(KEYRING_SERVICE, KEYRING_PASSWORD_KEY)

            if not username or not password:
                raise ConfigError("Credentials not found in keyring")

            logger.debug("Credentials retrieved from keyring")
            return username, password

        except KeyringError as e:
            raise ConfigError(f"Keyring error: {e}")

    def set_credentials(self, username: str, password: str) -> None:
        """Store username and password in system keyring.

        Args:
            username: PIA username
            password: PIA password

        Raises:
            ConfigError: If keyring operation fails
        """
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY, username)
            keyring.set_password(KEYRING_SERVICE, KEYRING_PASSWORD_KEY, password)
            logger.info("Credentials stored in system keyring")

        except KeyringError as e:
            raise ConfigError(f"Failed to store credentials in keyring: {e}")

    def add_region(self, region_id: str) -> None:
        """Add region to configuration.

        Args:
            region_id: Region identifier to add

        Raises:
            ConfigError: If region already exists or save fails
        """
        config = self.load()

        if region_id in config["regions"]:
            raise ConfigError(f"Region '{region_id}' already configured")

        config["regions"].append(region_id)
        self.save(config)
        logger.info(f"Added region: {region_id}")

    def remove_region(self, region_id: str) -> None:
        """Remove region from configuration.

        Args:
            region_id: Region identifier to remove

        Raises:
            ConfigError: If region not found or save fails
        """
        config = self.load()

        if region_id not in config["regions"]:
            raise ConfigError(f"Region '{region_id}' not configured")

        config["regions"].remove(region_id)
        self.save(config)
        logger.info(f"Removed region: {region_id}")

    def get_regions(self) -> List[str]:
        """Get list of configured regions.

        Returns:
            List of region identifiers
        """
        config = self.load()
        return config["regions"]

    def update_last_refresh(self) -> None:
        """Update last_refresh timestamp to current time.

        Raises:
            ConfigError: If save fails
        """
        config = self.load()
        config["metadata"]["last_refresh"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.save(config)
        logger.info("Updated last_refresh timestamp")

    def get_last_refresh(self) -> Optional[str]:
        """Get last refresh timestamp.

        Returns:
            ISO 8601 formatted timestamp or None if never refreshed
        """
        config = self.load()
        return config["metadata"]["last_refresh"]
