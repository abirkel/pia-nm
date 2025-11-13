"""Unit tests for systemd integration module.

Tests cover:
- Service unit file generation
- Timer unit file generation
- Unit installation
- Timer control (enable/disable)
- Timer status checking
- Unit uninstallation
- Error handling
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

from pia_nm.systemd_manager import (
    SystemdError,
    _get_pia_nm_path,
    _get_service_unit_content,
    _get_timer_unit_content,
    install_units,
    enable_timer,
    disable_timer,
    check_timer_status,
    uninstall_units,
)


class TestGetPiaNmPath:
    """Test pia-nm path resolution."""

    @patch("pia_nm.systemd_manager.Path.home")
    def test_get_pia_nm_path_returns_correct_path(self, mock_home):
        """Test that _get_pia_nm_path returns ~/.local/bin/pia-nm."""
        mock_home.return_value = Path("/home/testuser")

        path = _get_pia_nm_path()

        assert path == Path("/home/testuser/.local/bin/pia-nm")

    @patch("pia_nm.systemd_manager.Path.home")
    def test_get_pia_nm_path_when_not_exists(self, mock_home):
        """Test _get_pia_nm_path when executable doesn't exist yet."""
        mock_home.return_value = Path("/home/testuser")

        # Should still return the path even if it doesn't exist
        path = _get_pia_nm_path()

        assert path == Path("/home/testuser/.local/bin/pia-nm")


class TestGetServiceUnitContent:
    """Test service unit file generation."""

    def test_service_unit_content_structure(self):
        """Test that service unit has required sections."""
        pia_nm_path = Path("/home/user/.local/bin/pia-nm")
        content = _get_service_unit_content(pia_nm_path)

        assert "[Unit]" in content
        assert "[Service]" in content
        assert "Description=PIA WireGuard Token Refresh" in content
        assert "Type=oneshot" in content
        assert "StandardOutput=journal" in content
        assert "StandardError=journal" in content

    def test_service_unit_exec_start_substitution(self):
        """Test that ExecStart path is properly substituted."""
        pia_nm_path = Path("/home/user/.local/bin/pia-nm")
        content = _get_service_unit_content(pia_nm_path)

        assert f"ExecStart={pia_nm_path} refresh" in content

    def test_service_unit_security_settings(self):
        """Test that service unit includes security hardening."""
        pia_nm_path = Path("/home/user/.local/bin/pia-nm")
        content = _get_service_unit_content(pia_nm_path)

        assert "PrivateTmp=true" in content
        assert "NoNewPrivileges=true" in content

    def test_service_unit_network_dependencies(self):
        """Test that service unit requires network."""
        pia_nm_path = Path("/home/user/.local/bin/pia-nm")
        content = _get_service_unit_content(pia_nm_path)

        assert "After=network-online.target" in content
        assert "Wants=network-online.target" in content


class TestGetTimerUnitContent:
    """Test timer unit file generation."""

    def test_timer_unit_content_structure(self):
        """Test that timer unit has required sections."""
        content = _get_timer_unit_content()

        assert "[Unit]" in content
        assert "[Timer]" in content
        assert "[Install]" in content

    def test_timer_unit_boot_delay(self):
        """Test that timer has 5 minute boot delay."""
        content = _get_timer_unit_content()

        assert "OnBootSec=5min" in content

    def test_timer_unit_interval(self):
        """Test that timer has 12 hour interval."""
        content = _get_timer_unit_content()

        assert "OnUnitActiveSec=12h" in content

    def test_timer_unit_persistent(self):
        """Test that timer is persistent across reboots."""
        content = _get_timer_unit_content()

        assert "Persistent=true" in content

    def test_timer_unit_install_target(self):
        """Test that timer installs to timers.target."""
        content = _get_timer_unit_content()

        assert "WantedBy=timers.target" in content


class TestInstallUnits:
    """Test unit installation."""

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    @patch("pia_nm.systemd_manager._get_pia_nm_path")
    def test_install_units_success(self, mock_get_path, mock_home, mock_run):
        """Test successful unit installation."""
        mock_home.return_value = Path("/home/testuser")
        mock_get_path.return_value = Path("/home/testuser/.local/bin/pia-nm")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text"):
            result = install_units()

        assert result is True
        # Should call systemctl twice: daemon-reload and enable --now
        assert mock_run.call_count == 2

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    @patch("pia_nm.systemd_manager._get_pia_nm_path")
    def test_install_units_creates_directory(self, mock_get_path, mock_home, mock_run):
        """Test that install_units creates systemd user directory."""
        mock_home.return_value = Path("/home/testuser")
        mock_get_path.return_value = Path("/home/testuser/.local/bin/pia-nm")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.mkdir") as mock_mkdir, patch("pathlib.Path.write_text"):
            install_units()

        # Should create the systemd user directory
        mock_mkdir.assert_called()

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    @patch("pia_nm.systemd_manager._get_pia_nm_path")
    def test_install_units_writes_service_file(self, mock_get_path, mock_home, mock_run):
        """Test that install_units writes service unit file."""
        mock_home.return_value = Path("/home/testuser")
        mock_get_path.return_value = Path("/home/testuser/.local/bin/pia-nm")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text") as mock_write:
            install_units()

        # Should write both service and timer files
        assert mock_write.call_count == 2

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    @patch("pia_nm.systemd_manager._get_pia_nm_path")
    def test_install_units_daemon_reload(self, mock_get_path, mock_home, mock_run):
        """Test that install_units calls daemon-reload."""
        mock_home.return_value = Path("/home/testuser")
        mock_get_path.return_value = Path("/home/testuser/.local/bin/pia-nm")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text"):
            install_units()

        # First call should be daemon-reload
        first_call = mock_run.call_args_list[0]
        assert "daemon-reload" in first_call[0][0]

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    @patch("pia_nm.systemd_manager._get_pia_nm_path")
    def test_install_units_enable_timer(self, mock_get_path, mock_home, mock_run):
        """Test that install_units enables and starts timer."""
        mock_home.return_value = Path("/home/testuser")
        mock_get_path.return_value = Path("/home/testuser/.local/bin/pia-nm")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text"):
            install_units()

        # Second call should be enable --now
        second_call = mock_run.call_args_list[1]
        assert "enable" in second_call[0][0]
        assert "--now" in second_call[0][0]
        assert "pia-nm-refresh.timer" in second_call[0][0]

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    @patch("pia_nm.systemd_manager._get_pia_nm_path")
    def test_install_units_subprocess_error(self, mock_get_path, mock_home, mock_run):
        """Test error handling when systemctl fails."""
        mock_home.return_value = Path("/home/testuser")
        mock_get_path.return_value = Path("/home/testuser/.local/bin/pia-nm")
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl", stderr="Error")

        with patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text"):
            with pytest.raises(SystemdError, match="Failed to install systemd units"):
                install_units()

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    @patch("pia_nm.systemd_manager._get_pia_nm_path")
    def test_install_units_timeout(self, mock_get_path, mock_home, mock_run):
        """Test error handling when systemctl times out."""
        mock_home.return_value = Path("/home/testuser")
        mock_get_path.return_value = Path("/home/testuser/.local/bin/pia-nm")
        mock_run.side_effect = subprocess.TimeoutExpired("systemctl", 10)

        with patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text"):
            with pytest.raises(SystemdError, match="timed out"):
                install_units()

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    @patch("pia_nm.systemd_manager._get_pia_nm_path")
    def test_install_units_command_not_found(self, mock_get_path, mock_home, mock_run):
        """Test error handling when systemctl command not found."""
        mock_home.return_value = Path("/home/testuser")
        mock_get_path.return_value = Path("/home/testuser/.local/bin/pia-nm")
        mock_run.side_effect = FileNotFoundError("systemctl not found")

        with patch("pathlib.Path.mkdir"), patch("pathlib.Path.write_text"):
            with pytest.raises(SystemdError, match="systemctl command not found"):
                install_units()


class TestEnableTimer:
    """Test timer enable functionality."""

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_enable_timer_success(self, mock_run):
        """Test successful timer enable."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = enable_timer()

        assert result is True
        mock_run.assert_called_once()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_enable_timer_calls_systemctl(self, mock_run):
        """Test that enable_timer calls systemctl with correct arguments."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        enable_timer()

        call_args = mock_run.call_args[0][0]
        assert "systemctl" in call_args or call_args[0] == "systemctl"
        assert "--user" in call_args
        assert "enable" in call_args
        assert "pia-nm-refresh.timer" in call_args

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_enable_timer_subprocess_error(self, mock_run):
        """Test error handling when systemctl fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl", stderr="Error")

        with pytest.raises(SystemdError, match="Failed to enable timer"):
            enable_timer()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_enable_timer_timeout(self, mock_run):
        """Test error handling when systemctl times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("systemctl", 10)

        with pytest.raises(SystemdError, match="timed out"):
            enable_timer()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_enable_timer_command_not_found(self, mock_run):
        """Test error handling when systemctl command not found."""
        mock_run.side_effect = FileNotFoundError("systemctl not found")

        with pytest.raises(SystemdError, match="systemctl command not found"):
            enable_timer()


class TestDisableTimer:
    """Test timer disable functionality."""

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_disable_timer_success(self, mock_run):
        """Test successful timer disable."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        result = disable_timer()

        assert result is True
        mock_run.assert_called_once()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_disable_timer_calls_systemctl(self, mock_run):
        """Test that disable_timer calls systemctl with correct arguments."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        disable_timer()

        call_args = mock_run.call_args[0][0]
        assert "systemctl" in call_args or call_args[0] == "systemctl"
        assert "--user" in call_args
        assert "disable" in call_args
        assert "pia-nm-refresh.timer" in call_args

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_disable_timer_subprocess_error(self, mock_run):
        """Test error handling when systemctl fails."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl", stderr="Error")

        with pytest.raises(SystemdError, match="Failed to disable timer"):
            disable_timer()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_disable_timer_timeout(self, mock_run):
        """Test error handling when systemctl times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("systemctl", 10)

        with pytest.raises(SystemdError, match="timed out"):
            disable_timer()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_disable_timer_command_not_found(self, mock_run):
        """Test error handling when systemctl command not found."""
        mock_run.side_effect = FileNotFoundError("systemctl not found")

        with pytest.raises(SystemdError, match="systemctl command not found"):
            disable_timer()


class TestCheckTimerStatus:
    """Test timer status checking."""

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_check_timer_status_active(self, mock_run):
        """Test checking status of active timer."""
        # First call: is-active returns 0 (active)
        # Second call: list-timers returns timer info
        mock_run.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),
            Mock(
                returncode=0,
                stdout="NEXT                        LEFT     LAST                        PASSED UNIT                   ACTIVATES\n"
                "Fri 2025-11-14 10:30:00 UTC 12h left  Thu 2025-11-13 10:30:00 UTC 12h ago  pia-nm-refresh.timer pia-nm-refresh.service\n",
                stderr="",
            ),
        ]

        status = check_timer_status()

        assert status["active"] == "active"
        assert status["next_run"] is not None

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_check_timer_status_inactive(self, mock_run):
        """Test checking status of inactive timer."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="")

        status = check_timer_status()

        assert status["active"] == "inactive"
        assert status["next_run"] is None

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_check_timer_status_timeout(self, mock_run):
        """Test error handling when systemctl times out."""
        mock_run.side_effect = subprocess.TimeoutExpired("systemctl", 10)

        with pytest.raises(SystemdError, match="timed out"):
            check_timer_status()

    @patch("pia_nm.systemd_manager.subprocess.run")
    def test_check_timer_status_command_not_found(self, mock_run):
        """Test error handling when systemctl command not found."""
        mock_run.side_effect = FileNotFoundError("systemctl not found")

        with pytest.raises(SystemdError, match="systemctl command not found"):
            check_timer_status()


class TestUninstallUnits:
    """Test unit uninstallation."""

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    def test_uninstall_units_success(self, mock_home, mock_run):
        """Test successful unit uninstallation."""
        mock_home.return_value = Path("/home/testuser")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.unlink"):
            result = uninstall_units()

        assert result is True
        # Should call systemctl twice: disable --now and daemon-reload
        assert mock_run.call_count == 2

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    def test_uninstall_units_disables_timer(self, mock_home, mock_run):
        """Test that uninstall_units disables and stops timer."""
        mock_home.return_value = Path("/home/testuser")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.unlink"):
            uninstall_units()

        # First call should be disable --now
        first_call = mock_run.call_args_list[0]
        assert "disable" in first_call[0][0]
        assert "--now" in first_call[0][0]

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    def test_uninstall_units_removes_files(self, mock_home, mock_run):
        """Test that uninstall_units removes unit files."""
        mock_home.return_value = Path("/home/testuser")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.unlink"
        ) as mock_unlink:
            uninstall_units()

        # Should unlink both service and timer files
        assert mock_unlink.call_count == 2

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    def test_uninstall_units_daemon_reload(self, mock_home, mock_run):
        """Test that uninstall_units calls daemon-reload."""
        mock_home.return_value = Path("/home/testuser")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.unlink"):
            uninstall_units()

        # Second call should be daemon-reload
        second_call = mock_run.call_args_list[1]
        assert "daemon-reload" in second_call[0][0]

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    def test_uninstall_units_handles_missing_files(self, mock_home, mock_run):
        """Test that uninstall_units handles missing unit files gracefully."""
        mock_home.return_value = Path("/home/testuser")
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with patch("pathlib.Path.exists", return_value=False), patch("pathlib.Path.unlink"):
            result = uninstall_units()

        assert result is True

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    def test_uninstall_units_subprocess_error(self, mock_home, mock_run):
        """Test error handling when systemctl fails."""
        mock_home.return_value = Path("/home/testuser")
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl", stderr="Error")

        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.unlink"):
            with pytest.raises(SystemdError, match="Failed to uninstall systemd units"):
                uninstall_units()

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    def test_uninstall_units_timeout(self, mock_home, mock_run):
        """Test error handling when systemctl times out."""
        mock_home.return_value = Path("/home/testuser")
        mock_run.side_effect = subprocess.TimeoutExpired("systemctl", 10)

        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.unlink"):
            with pytest.raises(SystemdError, match="timed out"):
                uninstall_units()

    @patch("pia_nm.systemd_manager.subprocess.run")
    @patch("pia_nm.systemd_manager.Path.home")
    def test_uninstall_units_command_not_found(self, mock_home, mock_run):
        """Test error handling when systemctl command not found."""
        mock_home.return_value = Path("/home/testuser")
        mock_run.side_effect = FileNotFoundError("systemctl not found")

        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.unlink"):
            with pytest.raises(SystemdError, match="systemctl command not found"):
                uninstall_units()
