"""Systemd integration for PIA NetworkManager token refresh automation.

This module handles:
- Installation of systemd service and timer units
- Timer control (enable/disable)
- Timer status checking
- Unit uninstallation
"""

import logging
import subprocess
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SystemdError(Exception):
    """Base exception for systemd operations."""

    pass


def _get_pia_nm_path() -> Path:
    """Get the path to the pia-nm executable.

    Returns:
        Path to pia-nm executable in ~/.local/bin/

    Raises:
        SystemdError: If pia-nm executable cannot be found
    """
    pia_nm_path = Path.home() / ".local/bin/pia-nm"

    if not pia_nm_path.exists():
        logger.warning(f"pia-nm executable not found at {pia_nm_path}")
        # Still return the path - it will be created during installation
        logger.info("Assuming pia-nm will be installed at ~/.local/bin/pia-nm")

    return pia_nm_path


def _get_service_unit_content(pia_nm_path: Path) -> str:
    """Generate service unit file content.

    Args:
        pia_nm_path: Path to pia-nm executable

    Returns:
        Service unit file content as string
    """
    return f"""[Unit]
Description=PIA WireGuard Token Refresh
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={pia_nm_path} refresh
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pia-nm-refresh
PrivateTmp=true
NoNewPrivileges=true
"""


def _get_timer_unit_content() -> str:
    """Generate timer unit file content.

    Returns:
        Timer unit file content as string
    """
    return """[Unit]
Description=PIA WireGuard Token Refresh Timer

[Timer]
OnBootSec=5min
OnUnitActiveSec=12h
Persistent=true

[Install]
WantedBy=timers.target
"""


def install_units() -> bool:
    """Install systemd service and timer units.

    Creates ~/.config/systemd/user/ directory if needed, writes service and timer
    unit files, reloads systemd daemon, and enables/starts the timer.

    Returns:
        True if installation successful, False otherwise

    Raises:
        SystemdError: If installation fails
    """
    try:
        logger.info("Installing systemd units")

        # Create systemd user directory
        systemd_user_dir = Path.home() / ".config/systemd/user"
        systemd_user_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created systemd user directory: {systemd_user_dir}")

        # Get pia-nm path
        pia_nm_path = _get_pia_nm_path()

        # Write service unit
        service_file = systemd_user_dir / "pia-nm-refresh.service"
        service_content = _get_service_unit_content(pia_nm_path)
        service_file.write_text(service_content)
        logger.debug(f"Wrote service unit: {service_file}")

        # Write timer unit
        timer_file = systemd_user_dir / "pia-nm-refresh.timer"
        timer_content = _get_timer_unit_content()
        timer_file.write_text(timer_content)
        logger.debug(f"Wrote timer unit: {timer_file}")

        # Reload systemd daemon
        logger.debug("Reloading systemd user daemon")
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Enable and start timer
        logger.debug("Enabling and starting pia-nm-refresh.timer")
        subprocess.run(
            ["systemctl", "--user", "enable", "--now", "pia-nm-refresh.timer"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        logger.info("Systemd units installed and timer enabled")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"systemctl command failed: {e.stderr}")
        raise SystemdError(f"Failed to install systemd units: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        logger.error("systemctl command timed out")
        raise SystemdError("systemctl command timed out") from e
    except FileNotFoundError as e:
        logger.error("systemctl command not found")
        raise SystemdError(
            "systemctl command not found. Install systemd: sudo apt install systemd"
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error installing systemd units: {e}")
        raise SystemdError(f"Failed to install systemd units: {e}") from e


def enable_timer() -> bool:
    """Enable the PIA token refresh timer.

    Returns:
        True if timer enabled successfully, False otherwise

    Raises:
        SystemdError: If enable operation fails
    """
    try:
        logger.info("Enabling pia-nm-refresh.timer")

        subprocess.run(
            ["systemctl", "--user", "enable", "pia-nm-refresh.timer"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        logger.info("Timer enabled successfully")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to enable timer: {e.stderr}")
        raise SystemdError(f"Failed to enable timer: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        logger.error("systemctl command timed out")
        raise SystemdError("systemctl command timed out") from e
    except FileNotFoundError as e:
        logger.error("systemctl command not found")
        raise SystemdError("systemctl command not found") from e
    except Exception as e:
        logger.error(f"Unexpected error enabling timer: {e}")
        raise SystemdError(f"Failed to enable timer: {e}") from e


def disable_timer() -> bool:
    """Disable the PIA token refresh timer.

    Returns:
        True if timer disabled successfully, False otherwise

    Raises:
        SystemdError: If disable operation fails
    """
    try:
        logger.info("Disabling pia-nm-refresh.timer")

        subprocess.run(
            ["systemctl", "--user", "disable", "pia-nm-refresh.timer"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        logger.info("Timer disabled successfully")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to disable timer: {e.stderr}")
        raise SystemdError(f"Failed to disable timer: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        logger.error("systemctl command timed out")
        raise SystemdError("systemctl command timed out") from e
    except FileNotFoundError as e:
        logger.error("systemctl command not found")
        raise SystemdError("systemctl command not found") from e
    except Exception as e:
        logger.error(f"Unexpected error disabling timer: {e}")
        raise SystemdError(f"Failed to disable timer: {e}") from e


def check_timer_status() -> Dict[str, Optional[str]]:
    """Check the status of the PIA token refresh timer.

    Returns:
        Dictionary with keys:
        - 'active': 'active' or 'inactive'
        - 'next_run': ISO 8601 timestamp of next scheduled run, or None if inactive

    Raises:
        SystemdError: If status check fails
    """
    try:
        logger.debug("Checking pia-nm-refresh.timer status")

        # Get timer status
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "pia-nm-refresh.timer"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        is_active = result.returncode == 0
        active_status = "active" if is_active else "inactive"

        # Get next run time
        next_run = None
        if is_active:
            try:
                result = subprocess.run(
                    ["systemctl", "--user", "list-timers", "pia-nm-refresh.timer", "--no-pager"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=True,
                )

                # Parse output to extract next run time
                # Output format includes a line with the next run time
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    # Second line contains the timer info
                    parts = lines[1].split()
                    if len(parts) >= 1:
                        # First column is the next run time
                        next_run = parts[0]

            except (subprocess.CalledProcessError, IndexError) as e:
                logger.warning(f"Could not parse timer next run time: {e}")

        status = {"active": active_status, "next_run": next_run}

        logger.debug(f"Timer status: {status}")
        return status

    except subprocess.TimeoutExpired as e:
        logger.error("systemctl command timed out")
        raise SystemdError("systemctl command timed out") from e
    except FileNotFoundError as e:
        logger.error("systemctl command not found")
        raise SystemdError("systemctl command not found") from e
    except Exception as e:
        logger.error(f"Unexpected error checking timer status: {e}")
        raise SystemdError(f"Failed to check timer status: {e}") from e


def uninstall_units() -> bool:
    """Uninstall systemd service and timer units.

    Disables and stops the timer, removes unit files, and reloads systemd daemon.

    Returns:
        True if uninstallation successful, False otherwise

    Raises:
        SystemdError: If uninstallation fails
    """
    try:
        logger.info("Uninstalling systemd units")

        # Disable and stop timer
        logger.debug("Disabling and stopping pia-nm-refresh.timer")
        try:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", "pia-nm-refresh.timer"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except subprocess.CalledProcessError as e:
            # If timer doesn't exist, that's okay
            if "not found" not in e.stderr.lower():
                raise

        # Remove unit files
        systemd_user_dir = Path.home() / ".config/systemd/user"
        service_file = systemd_user_dir / "pia-nm-refresh.service"
        timer_file = systemd_user_dir / "pia-nm-refresh.timer"

        if service_file.exists():
            service_file.unlink()
            logger.debug(f"Removed service unit: {service_file}")

        if timer_file.exists():
            timer_file.unlink()
            logger.debug(f"Removed timer unit: {timer_file}")

        # Reload systemd daemon
        logger.debug("Reloading systemd user daemon")
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )

        logger.info("Systemd units uninstalled successfully")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"systemctl command failed: {e.stderr}")
        raise SystemdError(f"Failed to uninstall systemd units: {e.stderr}") from e
    except subprocess.TimeoutExpired as e:
        logger.error("systemctl command timed out")
        raise SystemdError("systemctl command timed out") from e
    except FileNotFoundError as e:
        logger.error("systemctl command not found")
        raise SystemdError("systemctl command not found") from e
    except Exception as e:
        logger.error(f"Unexpected error uninstalling systemd units: {e}")
        raise SystemdError(f"Failed to uninstall systemd units: {e}") from e
