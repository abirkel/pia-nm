"""Unit tests for configuration management module.

Tests cover:
- YAML read/write operations
- Configuration validation
- Keyring storage/retrieval (with mocking)
- Region management methods
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from pia_nm.config import ConfigError, ConfigManager, KEYRING_SERVICE


class TestConfigManagerInitialization:
    """Test ConfigManager initialization and directory creation."""

    def test_init_with_default_path(self, tmp_path, monkeypatch):
        """Test initialization with default config path."""
        monkeypatch.setenv("HOME", str(tmp_path))
        manager = ConfigManager()

        expected_path = tmp_path / ".config/pia-nm/config.yaml"
        assert manager.config_path == expected_path

    def test_init_with_custom_path(self, tmp_path):
        """Test initialization with custom config path."""
        custom_path = tmp_path / "custom/config.yaml"
        manager = ConfigManager(config_path=custom_path)

        assert manager.config_path == custom_path

    def test_ensure_directories_created(self, tmp_path, monkeypatch):
        """Test that required directories are created with proper permissions."""
        monkeypatch.setenv("HOME", str(tmp_path))
        manager = ConfigManager()

        config_dir = tmp_path / ".config/pia-nm"
        keys_dir = config_dir / "keys"
        log_dir = tmp_path / ".local/share/pia-nm/logs"

        assert config_dir.exists()
        assert keys_dir.exists()
        assert log_dir.exists()

        # Check permissions
        assert oct(config_dir.stat().st_mode)[-3:] == "700"
        assert oct(keys_dir.stat().st_mode)[-3:] == "700"
        assert oct(log_dir.stat().st_mode)[-3:] == "755"


class TestConfigValidation:
    """Test configuration validation."""

    def test_validate_valid_config(self, tmp_path):
        """Test validation of a valid configuration."""
        manager = ConfigManager(config_path=tmp_path / "config.yaml")
        valid_config = {
            "regions": ["us-east", "uk-london"],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": None},
        }

        # Should not raise
        manager._validate_config(valid_config)

    def test_validate_missing_required_key(self, tmp_path):
        """Test validation fails when required key is missing."""
        manager = ConfigManager(config_path=tmp_path / "config.yaml")
        invalid_config = {
            "regions": [],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            # Missing 'metadata'
        }

        with pytest.raises(ConfigError, match="Missing required key: metadata"):
            manager._validate_config(invalid_config)

    def test_validate_regions_not_list(self, tmp_path):
        """Test validation fails when regions is not a list."""
        manager = ConfigManager(config_path=tmp_path / "config.yaml")
        invalid_config = {
            "regions": "us-east",  # Should be list
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": None},
        }

        with pytest.raises(ConfigError, match="'regions' must be a list"):
            manager._validate_config(invalid_config)

    def test_validate_region_not_string(self, tmp_path):
        """Test validation fails when region is not a string."""
        manager = ConfigManager(config_path=tmp_path / "config.yaml")
        invalid_config = {
            "regions": [123],  # Should be string
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": None},
        }

        with pytest.raises(ConfigError, match="Region must be string"):
            manager._validate_config(invalid_config)

    def test_validate_missing_preference(self, tmp_path):
        """Test validation fails when preference is missing."""
        manager = ConfigManager(config_path=tmp_path / "config.yaml")
        invalid_config = {
            "regions": [],
            "preferences": {"dns": True, "ipv6": False},  # Missing port_forwarding
            "metadata": {"version": 1, "last_refresh": None},
        }

        with pytest.raises(ConfigError, match="Missing preference: port_forwarding"):
            manager._validate_config(invalid_config)

    def test_validate_preference_not_boolean(self, tmp_path):
        """Test validation fails when preference is not boolean."""
        manager = ConfigManager(config_path=tmp_path / "config.yaml")
        invalid_config = {
            "regions": [],
            "preferences": {"dns": "yes", "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": None},
        }

        with pytest.raises(ConfigError, match="Preference 'dns' must be boolean"):
            manager._validate_config(invalid_config)

    def test_validate_invalid_metadata_version(self, tmp_path):
        """Test validation fails when metadata version is invalid."""
        manager = ConfigManager(config_path=tmp_path / "config.yaml")
        invalid_config = {
            "regions": [],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": "1", "last_refresh": None},  # Should be int
        }

        with pytest.raises(ConfigError, match="Invalid metadata.version"):
            manager._validate_config(invalid_config)

    def test_validate_last_refresh_not_string(self, tmp_path):
        """Test validation fails when last_refresh is not string or null."""
        manager = ConfigManager(config_path=tmp_path / "config.yaml")
        invalid_config = {
            "regions": [],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": 12345},  # Should be string or null
        }

        with pytest.raises(ConfigError, match="metadata.last_refresh must be string or null"):
            manager._validate_config(invalid_config)


class TestConfigReadWrite:
    """Test YAML read/write operations."""

    def test_load_creates_default_config_if_missing(self, tmp_path):
        """Test that load creates default config if file doesn't exist."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        config = manager.load()

        assert config["regions"] == []
        assert config["preferences"]["dns"] is True
        assert config["preferences"]["ipv6"] is False
        assert config["preferences"]["port_forwarding"] is False
        assert config["metadata"]["version"] == 1
        assert config["metadata"]["last_refresh"] is None

    def test_load_existing_config(self, tmp_path):
        """Test loading an existing configuration file."""
        config_path = tmp_path / "config.yaml"
        test_config = {
            "regions": ["us-east", "uk-london"],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": "2025-11-13T10:30:00Z"},
        }

        with open(config_path, "w") as f:
            yaml.dump(test_config, f)

        manager = ConfigManager(config_path=config_path)
        loaded_config = manager.load()

        assert loaded_config == test_config

    def test_load_invalid_yaml(self, tmp_path):
        """Test loading invalid YAML raises ConfigError."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("invalid: yaml: content: [")

        manager = ConfigManager(config_path=config_path)

        with pytest.raises(ConfigError, match="Invalid YAML"):
            manager.load()

    def test_load_empty_file_creates_default(self, tmp_path):
        """Test loading empty YAML file creates default config."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("")

        manager = ConfigManager(config_path=config_path)
        config = manager.load()

        assert config["regions"] == []
        assert config["metadata"]["version"] == 1

    def test_save_creates_file_with_correct_permissions(self, tmp_path):
        """Test that save creates file with 0600 permissions."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        test_config = {
            "regions": ["us-east"],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": None},
        }

        manager.save(test_config)

        assert config_path.exists()
        # Check permissions are 0600
        assert oct(config_path.stat().st_mode)[-3:] == "600"

    def test_save_writes_valid_yaml(self, tmp_path):
        """Test that save writes valid YAML that can be read back."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        test_config = {
            "regions": ["us-east", "uk-london"],
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": "2025-11-13T10:30:00Z"},
        }

        manager.save(test_config)

        # Read back and verify
        with open(config_path, "r") as f:
            loaded = yaml.safe_load(f)

        assert loaded == test_config

    def test_save_validates_before_writing(self, tmp_path):
        """Test that save validates config before writing."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        invalid_config = {
            "regions": "not-a-list",
            "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
            "metadata": {"version": 1, "last_refresh": None},
        }

        with pytest.raises(ConfigError):
            manager.save(invalid_config)

        # File should not be created
        assert not config_path.exists()


class TestKeyringIntegration:
    """Test keyring storage and retrieval with mocking."""

    @patch("pia_nm.config.keyring.set_password")
    def test_set_credentials_stores_in_keyring(self, mock_set_password, tmp_path):
        """Test that set_credentials stores credentials in keyring."""
        manager = ConfigManager(config_path=tmp_path / "config.yaml")

        manager.set_credentials("testuser", "testpass")

        # Verify keyring.set_password was called correctly
        assert mock_set_password.call_count == 2
        calls = mock_set_password.call_args_list
        assert calls[0][0] == (KEYRING_SERVICE, "username", "testuser")
        assert calls[1][0] == (KEYRING_SERVICE, "password", "testpass")

    @patch("pia_nm.config.keyring.get_password")
    def test_get_credentials_retrieves_from_keyring(self, mock_get_password, tmp_path):
        """Test that get_credentials retrieves credentials from keyring."""
        mock_get_password.side_effect = ["testuser", "testpass"]

        manager = ConfigManager(config_path=tmp_path / "config.yaml")
        username, password = manager.get_credentials()

        assert username == "testuser"
        assert password == "testpass"
        assert mock_get_password.call_count == 2

    @patch("pia_nm.config.keyring.get_password")
    def test_get_credentials_raises_when_missing(self, mock_get_password, tmp_path):
        """Test that get_credentials raises ConfigError when credentials missing."""
        mock_get_password.return_value = None

        manager = ConfigManager(config_path=tmp_path / "config.yaml")

        with pytest.raises(ConfigError, match="Credentials not found"):
            manager.get_credentials()

    @patch("pia_nm.config.keyring.set_password")
    def test_set_credentials_handles_keyring_error(self, mock_set_password, tmp_path):
        """Test that set_credentials handles keyring errors gracefully."""
        from keyring.errors import KeyringError

        mock_set_password.side_effect = KeyringError("Keyring unavailable")

        manager = ConfigManager(config_path=tmp_path / "config.yaml")

        with pytest.raises(ConfigError, match="Failed to store credentials"):
            manager.set_credentials("user", "pass")

    @patch("pia_nm.config.keyring.get_password")
    def test_get_credentials_handles_keyring_error(self, mock_get_password, tmp_path):
        """Test that get_credentials handles keyring errors gracefully."""
        from keyring.errors import KeyringError

        mock_get_password.side_effect = KeyringError("Keyring unavailable")

        manager = ConfigManager(config_path=tmp_path / "config.yaml")

        with pytest.raises(ConfigError, match="Keyring error"):
            manager.get_credentials()


class TestRegionManagement:
    """Test region management methods."""

    def test_add_region_to_empty_config(self, tmp_path):
        """Test adding a region to empty configuration."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        manager.add_region("us-east")

        config = manager.load()
        assert "us-east" in config["regions"]
        assert len(config["regions"]) == 1

    def test_add_multiple_regions(self, tmp_path):
        """Test adding multiple regions."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        manager.add_region("us-east")
        manager.add_region("uk-london")
        manager.add_region("jp-tokyo")

        config = manager.load()
        assert config["regions"] == ["us-east", "uk-london", "jp-tokyo"]

    def test_add_duplicate_region_raises_error(self, tmp_path):
        """Test that adding duplicate region raises ConfigError."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        manager.add_region("us-east")

        with pytest.raises(ConfigError, match="already configured"):
            manager.add_region("us-east")

    def test_remove_region(self, tmp_path):
        """Test removing a region."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        manager.add_region("us-east")
        manager.add_region("uk-london")

        manager.remove_region("us-east")

        config = manager.load()
        assert "us-east" not in config["regions"]
        assert "uk-london" in config["regions"]

    def test_remove_nonexistent_region_raises_error(self, tmp_path):
        """Test that removing nonexistent region raises ConfigError."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        with pytest.raises(ConfigError, match="not configured"):
            manager.remove_region("us-east")

    def test_get_regions_returns_list(self, tmp_path):
        """Test get_regions returns list of configured regions."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        manager.add_region("us-east")
        manager.add_region("uk-london")

        regions = manager.get_regions()

        assert regions == ["us-east", "uk-london"]

    def test_get_regions_empty_list(self, tmp_path):
        """Test get_regions returns empty list when no regions configured."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        regions = manager.get_regions()

        assert regions == []


class TestLastRefreshTimestamp:
    """Test last refresh timestamp management."""

    def test_update_last_refresh_sets_timestamp(self, tmp_path):
        """Test that update_last_refresh sets current timestamp."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        before = datetime.utcnow().isoformat()
        manager.update_last_refresh()
        after = datetime.utcnow().isoformat()

        config = manager.load()
        timestamp = config["metadata"]["last_refresh"]

        assert timestamp is not None
        assert before <= timestamp <= after + "Z"

    def test_get_last_refresh_returns_none_initially(self, tmp_path):
        """Test that get_last_refresh returns None initially."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        timestamp = manager.get_last_refresh()

        assert timestamp is None

    def test_get_last_refresh_returns_timestamp_after_update(self, tmp_path):
        """Test that get_last_refresh returns timestamp after update."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        manager.update_last_refresh()
        timestamp = manager.get_last_refresh()

        assert timestamp is not None
        assert "Z" in timestamp  # ISO 8601 format with Z suffix

    def test_last_refresh_persists_across_loads(self, tmp_path):
        """Test that last_refresh timestamp persists across loads."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        manager.update_last_refresh()
        first_timestamp = manager.get_last_refresh()

        # Create new manager instance and load
        manager2 = ConfigManager(config_path=config_path)
        second_timestamp = manager2.get_last_refresh()

        assert first_timestamp == second_timestamp


class TestConfigIntegration:
    """Integration tests for configuration management."""

    def test_full_workflow(self, tmp_path):
        """Test complete workflow: create, add regions, update timestamp."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        # Add regions
        manager.add_region("us-east")
        manager.add_region("uk-london")

        # Update timestamp
        manager.update_last_refresh()

        # Load and verify
        config = manager.load()
        assert config["regions"] == ["us-east", "uk-london"]
        assert config["metadata"]["last_refresh"] is not None

        # Remove region
        manager.remove_region("us-east")

        # Verify removal
        regions = manager.get_regions()
        assert regions == ["uk-london"]

    def test_config_survives_multiple_manager_instances(self, tmp_path):
        """Test that config persists across multiple manager instances."""
        config_path = tmp_path / "config.yaml"

        # First manager
        manager1 = ConfigManager(config_path=config_path)
        manager1.add_region("us-east")
        manager1.update_last_refresh()

        # Second manager
        manager2 = ConfigManager(config_path=config_path)
        regions = manager2.get_regions()
        timestamp = manager2.get_last_refresh()

        assert regions == ["us-east"]
        assert timestamp is not None

    def test_default_config_structure(self, tmp_path):
        """Test that default config has correct structure."""
        config_path = tmp_path / "config.yaml"
        manager = ConfigManager(config_path=config_path)

        config = manager.load()

        # Verify structure
        assert "regions" in config
        assert "preferences" in config
        assert "metadata" in config

        # Verify preferences
        assert config["preferences"]["dns"] is True
        assert config["preferences"]["ipv6"] is False
        assert config["preferences"]["port_forwarding"] is False

        # Verify metadata
        assert config["metadata"]["version"] == 1
        assert config["metadata"]["last_refresh"] is None
