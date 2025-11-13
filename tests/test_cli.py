"""Tests for CLI module."""

import pytest
from unittest.mock import patch, MagicMock
from pia_nm.cli import (
    format_profile_name,
    check_system_dependencies,
)


def test_format_profile_name():
    """Test profile name formatting."""
    assert format_profile_name("us-east") == "PIA-US-East"
    assert format_profile_name("uk-london") == "PIA-UK-London"
    assert format_profile_name("jp-tokyo") == "PIA-JP-Tokyo"
    assert format_profile_name("de-frankfurt") == "PIA-DE-Frankfurt"


@patch("shutil.which")
def test_check_system_dependencies_success(mock_which):
    """Test system dependency check when all commands are available."""
    mock_which.return_value = "/usr/bin/command"
    assert check_system_dependencies() is True


@patch("shutil.which")
def test_check_system_dependencies_missing(mock_which, capsys):
    """Test system dependency check when commands are missing."""
    mock_which.return_value = None
    assert check_system_dependencies() is False
    captured = capsys.readouterr()
    assert "Missing required commands" in captured.out
