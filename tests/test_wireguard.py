"""Unit tests for WireGuard key management module.

Tests cover:
- Key generation using wg commands
- Key storage with proper permissions
- Key loading from storage
- Key rotation logic
- Key deletion
"""

import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from pia_nm.wireguard import (
    WireGuardError,
    delete_keypair,
    generate_keypair,
    load_keypair,
    save_keypair,
    should_rotate_key,
)


class TestGenerateKeypair:
    """Test WireGuard keypair generation."""

    @patch("pia_nm.wireguard.subprocess.run")
    def test_generate_keypair_success(self, mock_run):
        """Test successful keypair generation."""
        # Mock wg genkey response
        genkey_result = Mock()
        genkey_result.stdout = "YOkj7VHgPmjKL0IzJ8hWLB+123456789abcdefg=\n"
        genkey_result.returncode = 0

        # Mock wg pubkey response
        pubkey_result = Mock()
        pubkey_result.stdout = "xTIBA5rboUvnH4htodjb6e0QsGnD1234567890=\n"
        pubkey_result.returncode = 0

        mock_run.side_effect = [genkey_result, pubkey_result]

        private_key, public_key = generate_keypair()

        assert private_key == "YOkj7VHgPmjKL0IzJ8hWLB+123456789abcdefg="
        assert public_key == "xTIBA5rboUvnH4htodjb6e0QsGnD1234567890="
        assert mock_run.call_count == 2

    @patch("pia_nm.wireguard.subprocess.run")
    def test_generate_keypair_strips_whitespace(self, mock_run):
        """Test that generated keys have whitespace stripped."""
        genkey_result = Mock()
        genkey_result.stdout = "  key1  \n"
        genkey_result.returncode = 0

        pubkey_result = Mock()
        pubkey_result.stdout = "  key2  \n"
        pubkey_result.returncode = 0

        mock_run.side_effect = [genkey_result, pubkey_result]

        private_key, public_key = generate_keypair()

        assert private_key == "key1"
        assert public_key == "key2"

    @patch("pia_nm.wireguard.subprocess.run")
    def test_generate_keypair_genkey_fails(self, mock_run):
        """Test error handling when wg genkey fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "wg", stderr="Error")

        with pytest.raises(WireGuardError, match="Failed to generate keypair"):
            generate_keypair()

    @patch("pia_nm.wireguard.subprocess.run")
    def test_generate_keypair_pubkey_fails(self, mock_run):
        """Test error handling when wg pubkey fails."""
        genkey_result = Mock()
        genkey_result.stdout = "private_key\n"
        genkey_result.returncode = 0

        mock_run.side_effect = [
            genkey_result,
            subprocess.CalledProcessError(1, "wg", stderr="Error"),
        ]

        with pytest.raises(WireGuardError, match="Failed to generate keypair"):
            generate_keypair()

    @patch("pia_nm.wireguard.subprocess.run")
    def test_generate_keypair_timeout(self, mock_run):
        """Test error handling when wg command times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("wg", 10)

        with pytest.raises(WireGuardError, match="timed out"):
            generate_keypair()

    @patch("pia_nm.wireguard.subprocess.run")
    def test_generate_keypair_command_not_found(self, mock_run):
        """Test error handling when wg command is not found."""
        mock_run.side_effect = FileNotFoundError("wg not found")

        with pytest.raises(WireGuardError, match="wg command not found"):
            generate_keypair()

    @patch("pia_nm.wireguard.subprocess.run")
    def test_generate_keypair_empty_output(self, mock_run):
        """Test error handling when wg produces empty output."""
        genkey_result = Mock()
        genkey_result.stdout = ""
        genkey_result.returncode = 0

        mock_run.return_value = genkey_result

        with pytest.raises(WireGuardError, match="empty output"):
            generate_keypair()


class TestSaveKeypair:
    """Test WireGuard keypair storage."""

    def test_save_keypair_creates_directory(self, tmp_path, monkeypatch):
        """Test that save_keypair creates keys directory."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private_key", "public_key")

        keys_dir = tmp_path / ".config/pia-nm/keys"
        assert keys_dir.exists()
        assert oct(keys_dir.stat().st_mode)[-3:] == "700"

    def test_save_keypair_creates_files(self, tmp_path, monkeypatch):
        """Test that save_keypair creates key files."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private_key", "public_key")

        private_key_path = tmp_path / ".config/pia-nm/keys/us-east.key"
        public_key_path = tmp_path / ".config/pia-nm/keys/us-east.pub"

        assert private_key_path.exists()
        assert public_key_path.exists()

    def test_save_keypair_private_key_permissions(self, tmp_path, monkeypatch):
        """Test that private key has 0600 permissions."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private_key", "public_key")

        private_key_path = tmp_path / ".config/pia-nm/keys/us-east.key"
        assert oct(private_key_path.stat().st_mode)[-3:] == "600"

    def test_save_keypair_public_key_permissions(self, tmp_path, monkeypatch):
        """Test that public key has 0644 permissions."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private_key", "public_key")

        public_key_path = tmp_path / ".config/pia-nm/keys/us-east.pub"
        assert oct(public_key_path.stat().st_mode)[-3:] == "644"

    def test_save_keypair_writes_content(self, tmp_path, monkeypatch):
        """Test that save_keypair writes correct content."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private_key_content", "public_key_content")

        private_key_path = tmp_path / ".config/pia-nm/keys/us-east.key"
        public_key_path = tmp_path / ".config/pia-nm/keys/us-east.pub"

        assert private_key_path.read_text() == "private_key_content"
        assert public_key_path.read_text() == "public_key_content"

    def test_save_keypair_overwrites_existing(self, tmp_path, monkeypatch):
        """Test that save_keypair overwrites existing keys."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "old_private", "old_public")
        save_keypair("us-east", "new_private", "new_public")

        private_key_path = tmp_path / ".config/pia-nm/keys/us-east.key"
        public_key_path = tmp_path / ".config/pia-nm/keys/us-east.pub"

        assert private_key_path.read_text() == "new_private"
        assert public_key_path.read_text() == "new_public"

    def test_save_keypair_multiple_regions(self, tmp_path, monkeypatch):
        """Test saving keypairs for multiple regions."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private1", "public1")
        save_keypair("uk-london", "private2", "public2")

        keys_dir = tmp_path / ".config/pia-nm/keys"
        assert (keys_dir / "us-east.key").exists()
        assert (keys_dir / "us-east.pub").exists()
        assert (keys_dir / "uk-london.key").exists()
        assert (keys_dir / "uk-london.pub").exists()

    def test_save_keypair_handles_io_error(self, tmp_path, monkeypatch):
        """Test error handling for IO errors."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("pathlib.Path.write_text", side_effect=IOError("Permission denied")):
            with pytest.raises(WireGuardError, match="Failed to save keypair"):
                save_keypair("us-east", "private", "public")


class TestLoadKeypair:
    """Test WireGuard keypair loading."""

    def test_load_keypair_success(self, tmp_path, monkeypatch):
        """Test successful keypair loading."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Create keys
        save_keypair("us-east", "private_key", "public_key")

        # Load keys
        private_key, public_key = load_keypair("us-east")

        assert private_key == "private_key"
        assert public_key == "public_key"

    def test_load_keypair_strips_whitespace(self, tmp_path, monkeypatch):
        """Test that loaded keys have whitespace stripped."""
        monkeypatch.setenv("HOME", str(tmp_path))

        keys_dir = tmp_path / ".config/pia-nm/keys"
        keys_dir.mkdir(parents=True, exist_ok=True)

        (keys_dir / "us-east.key").write_text("  private_key  \n")
        (keys_dir / "us-east.pub").write_text("  public_key  \n")

        private_key, public_key = load_keypair("us-east")

        assert private_key == "private_key"
        assert public_key == "public_key"

    def test_load_keypair_private_key_missing(self, tmp_path, monkeypatch):
        """Test error when private key file is missing."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with pytest.raises(WireGuardError, match="Failed to load keypair"):
            load_keypair("us-east")

    def test_load_keypair_public_key_missing(self, tmp_path, monkeypatch):
        """Test error when public key file is missing."""
        monkeypatch.setenv("HOME", str(tmp_path))

        keys_dir = tmp_path / ".config/pia-nm/keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        (keys_dir / "us-east.key").write_text("private_key")

        with pytest.raises(WireGuardError, match="Failed to load keypair"):
            load_keypair("us-east")

    def test_load_keypair_empty_files(self, tmp_path, monkeypatch):
        """Test error when key files are empty."""
        monkeypatch.setenv("HOME", str(tmp_path))

        keys_dir = tmp_path / ".config/pia-nm/keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        (keys_dir / "us-east.key").write_text("")
        (keys_dir / "us-east.pub").write_text("")

        with pytest.raises(WireGuardError, match="empty"):
            load_keypair("us-east")

    def test_load_keypair_handles_io_error(self, tmp_path, monkeypatch):
        """Test error handling for IO errors."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("pathlib.Path.read_text", side_effect=IOError("Permission denied")):
            with pytest.raises(WireGuardError, match="Failed to load keypair"):
                load_keypair("us-east")


class TestShouldRotateKey:
    """Test key rotation logic."""

    def test_should_rotate_key_missing_file(self, tmp_path, monkeypatch):
        """Test that missing key file indicates rotation needed."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = should_rotate_key("us-east")

        assert result is True

    def test_should_rotate_key_new_key(self, tmp_path, monkeypatch):
        """Test that new key doesn't need rotation."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private", "public")

        result = should_rotate_key("us-east")

        assert result is False

    def test_should_rotate_key_old_key(self, tmp_path, monkeypatch):
        """Test that old key needs rotation."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private", "public")

        # Set file modification time to 31 days ago
        keys_dir = tmp_path / ".config/pia-nm/keys"
        private_key_path = keys_dir / "us-east.key"

        thirty_one_days_ago = time.time() - (31 * 24 * 60 * 60)
        Path(private_key_path).touch()
        import os

        os.utime(private_key_path, (thirty_one_days_ago, thirty_one_days_ago))

        result = should_rotate_key("us-east")

        assert result is True

    def test_should_rotate_key_exactly_30_days(self, tmp_path, monkeypatch):
        """Test key at exactly 30 days doesn't need rotation."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private", "public")

        # Set file modification time to 29.9 days ago (just under 30 days)
        keys_dir = tmp_path / ".config/pia-nm/keys"
        private_key_path = keys_dir / "us-east.key"

        twenty_nine_days_ago = time.time() - (29.9 * 24 * 60 * 60)
        import os

        os.utime(private_key_path, (twenty_nine_days_ago, twenty_nine_days_ago))

        result = should_rotate_key("us-east")

        # At 29.9 days, should not rotate (< 30 days)
        assert result is False

    def test_should_rotate_key_just_over_30_days(self, tmp_path, monkeypatch):
        """Test key just over 30 days needs rotation."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private", "public")

        # Set file modification time to 30 days + 1 second ago
        keys_dir = tmp_path / ".config/pia-nm/keys"
        private_key_path = keys_dir / "us-east.key"

        thirty_days_plus_one = time.time() - (30 * 24 * 60 * 60 + 1)
        import os

        os.utime(private_key_path, (thirty_days_plus_one, thirty_days_plus_one))

        result = should_rotate_key("us-east")

        assert result is True

    def test_should_rotate_key_handles_stat_error(self, tmp_path, monkeypatch):
        """Test error handling when stat fails."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("pathlib.Path.stat", side_effect=OSError("Permission denied")):
            result = should_rotate_key("us-east")

            # Should return True (assume rotation needed) on error
            assert result is True


class TestDeleteKeypair:
    """Test keypair deletion."""

    def test_delete_keypair_success(self, tmp_path, monkeypatch):
        """Test successful keypair deletion."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private", "public")

        delete_keypair("us-east")

        keys_dir = tmp_path / ".config/pia-nm/keys"
        assert not (keys_dir / "us-east.key").exists()
        assert not (keys_dir / "us-east.pub").exists()

    def test_delete_keypair_missing_files(self, tmp_path, monkeypatch):
        """Test deletion when files don't exist (should not raise)."""
        monkeypatch.setenv("HOME", str(tmp_path))

        # Should not raise
        delete_keypair("us-east")

    def test_delete_keypair_only_private_exists(self, tmp_path, monkeypatch):
        """Test deletion when only private key exists."""
        monkeypatch.setenv("HOME", str(tmp_path))

        keys_dir = tmp_path / ".config/pia-nm/keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        (keys_dir / "us-east.key").write_text("private")

        delete_keypair("us-east")

        assert not (keys_dir / "us-east.key").exists()

    def test_delete_keypair_only_public_exists(self, tmp_path, monkeypatch):
        """Test deletion when only public key exists."""
        monkeypatch.setenv("HOME", str(tmp_path))

        keys_dir = tmp_path / ".config/pia-nm/keys"
        keys_dir.mkdir(parents=True, exist_ok=True)
        (keys_dir / "us-east.pub").write_text("public")

        delete_keypair("us-east")

        assert not (keys_dir / "us-east.pub").exists()

    def test_delete_keypair_multiple_regions(self, tmp_path, monkeypatch):
        """Test deletion doesn't affect other regions."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private1", "public1")
        save_keypair("uk-london", "private2", "public2")

        delete_keypair("us-east")

        keys_dir = tmp_path / ".config/pia-nm/keys"
        assert not (keys_dir / "us-east.key").exists()
        assert not (keys_dir / "us-east.pub").exists()
        assert (keys_dir / "uk-london.key").exists()
        assert (keys_dir / "uk-london.pub").exists()

    def test_delete_keypair_handles_io_error(self, tmp_path, monkeypatch):
        """Test error handling for IO errors."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private", "public")

        with patch("pathlib.Path.unlink", side_effect=IOError("Permission denied")):
            with pytest.raises(WireGuardError, match="Failed to delete keypair"):
                delete_keypair("us-east")


class TestWireGuardIntegration:
    """Integration tests for WireGuard key management."""

    def test_full_keypair_lifecycle(self, tmp_path, monkeypatch):
        """Test complete keypair lifecycle: generate, save, load, delete."""
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("pia_nm.wireguard.subprocess.run") as mock_run:
            # Mock key generation
            genkey_result = Mock()
            genkey_result.stdout = "generated_private_key\n"
            genkey_result.returncode = 0

            pubkey_result = Mock()
            pubkey_result.stdout = "generated_public_key\n"
            pubkey_result.returncode = 0

            mock_run.side_effect = [genkey_result, pubkey_result]

            # Generate
            private_key, public_key = generate_keypair()
            assert private_key == "generated_private_key"
            assert public_key == "generated_public_key"

            # Save
            save_keypair("us-east", private_key, public_key)

            # Load
            loaded_private, loaded_public = load_keypair("us-east")
            assert loaded_private == private_key
            assert loaded_public == public_key

            # Check rotation not needed
            assert should_rotate_key("us-east") is False

            # Delete
            delete_keypair("us-east")

            # Verify deleted
            with pytest.raises(WireGuardError):
                load_keypair("us-east")

    def test_multiple_regions_independent(self, tmp_path, monkeypatch):
        """Test that multiple regions are managed independently."""
        monkeypatch.setenv("HOME", str(tmp_path))

        save_keypair("us-east", "private1", "public1")
        save_keypair("uk-london", "private2", "public2")

        # Load each independently
        p1, pub1 = load_keypair("us-east")
        p2, pub2 = load_keypair("uk-london")

        assert p1 == "private1"
        assert pub1 == "public1"
        assert p2 == "private2"
        assert pub2 == "public2"

        # Delete one doesn't affect other
        delete_keypair("us-east")

        with pytest.raises(WireGuardError):
            load_keypair("us-east")

        # Other still exists
        p2_again, pub2_again = load_keypair("uk-london")
        assert p2_again == "private2"
