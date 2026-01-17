"""NetworkManager dispatcher script management for IPv6 leak prevention and connection notifications."""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# IPv6 Guard Script Configuration
DISPATCHER_SCRIPT_NAME = "99-pia-nm-ipv6-guard.sh"
DISPATCHER_DIR = Path("/etc/NetworkManager/dispatcher.d")
LOGFILE = "/var/log/pia-nm-ipv6.log"

# Connection Notification Script Configuration
NOTIFY_SCRIPT_NAME = "98-pia-nm-connection-notify.sh"
NOTIFY_LOGFILE = "/var/log/pia-nm-notify.log"
NOTIFY_PID_DIR = "/run/pia-nm"

# The dispatcher script content
DISPATCHER_SCRIPT = """#!/bin/bash
#
# PIA NetworkManager IPv6 Guard
# Disables IPv6 system-wide when PIA VPN is active to prevent leaks.
# Automatically restores IPv6 when VPN disconnects.
#

VPN_INTERFACE_PREFIX="wg-pia-"
LOGFILE="{logfile}"

# Ensure log file exists
[ -e "$LOGFILE" ] || touch "$LOGFILE"
chmod 644 "$LOGFILE"

log() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOGFILE"
}}

disable_ipv6() {{
    log "Disabling IPv6 system-wide (PIA VPN active)"
    sysctl -w net.ipv6.conf.all.disable_ipv6=1 >/dev/null 2>&1
    sysctl -w net.ipv6.conf.default.disable_ipv6=1 >/dev/null 2>&1
}}

enable_ipv6() {{
    log "Re-enabling IPv6 system-wide (PIA VPN inactive)"
    sysctl -w net.ipv6.conf.all.disable_ipv6=0 >/dev/null 2>&1
    sysctl -w net.ipv6.conf.default.disable_ipv6=0 >/dev/null 2>&1
}}

vpn_is_active() {{
    # Check if any PIA VPN interface is connected
    nmcli -t device | grep -E "^${{VPN_INTERFACE_PREFIX}}.*:connected$" >/dev/null 2>&1
}}

# Main dispatcher logic
INTERFACE="$1"
ACTION="$2"

case "$ACTION" in
    up)
        if [[ "$INTERFACE" == "${{VPN_INTERFACE_PREFIX}}"* ]]; then
            log "Dispatcher: PIA VPN interface $INTERFACE went UP"
            disable_ipv6
        fi
        ;;
    down)
        if [[ "$INTERFACE" == "${{VPN_INTERFACE_PREFIX}}"* ]]; then
            log "Dispatcher: PIA VPN interface $INTERFACE went DOWN"
            # Only re-enable if no other PIA VPN is active
            if ! vpn_is_active; then
                enable_ipv6
            else
                log "Another PIA VPN still active, keeping IPv6 disabled"
            fi
        fi
        ;;
    *)
        # Handle abnormal scenarios (NM restart, sleep/resume, etc.)
        # Check actual VPN state and correct IPv6 accordingly
        if vpn_is_active; then
            # VPN is active but we got an unexpected event - ensure IPv6 is disabled
            current_state=$(sysctl -n net.ipv6.conf.all.disable_ipv6 2>/dev/null)
            if [ "$current_state" != "1" ]; then
                log "Dispatcher: VPN active but IPv6 enabled (event=$ACTION) - correcting"
                disable_ipv6
            fi
        else
            # VPN is not active - ensure IPv6 is enabled
            current_state=$(sysctl -n net.ipv6.conf.all.disable_ipv6 2>/dev/null)
            if [ "$current_state" != "0" ]; then
                log "Dispatcher: VPN inactive but IPv6 disabled (event=$ACTION) - correcting"
                enable_ipv6
            fi
        fi
        ;;
esac

exit 0
"""

# Connection notification dispatcher script
NOTIFY_DISPATCHER_SCRIPT = """#!/bin/bash
#
# PIA NetworkManager Connection Notification
# Monitors WireGuard handshake completion and sends desktop notifications
# when VPN connections are fully established.
#

VPN_INTERFACE_PREFIX="wg-pia-"
LOGFILE="{logfile}"
PID_DIR="{pid_dir}"

# Ensure log file and PID directory exist
[ -e "$LOGFILE" ] || touch "$LOGFILE"
chmod 644 "$LOGFILE"
[ -d "$PID_DIR" ] || mkdir -p "$PID_DIR"

log() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "$LOGFILE"
}}

send_notification() {{
    local title="$1"
    local message="$2"
    local icon="$3"
    local urgency="$4"
    
    # Detect active X session user
    ACTIVE_USER=$(who | grep -E '\\(:0\\)' | head -1 | awk '{{print $1}}')
    
    if [[ -z "$ACTIVE_USER" ]]; then
        log "No active X session user found, cannot send notification"
        return 1
    fi
    
    USER_UID=$(id -u "$ACTIVE_USER" 2>/dev/null)
    if [[ -z "$USER_UID" ]]; then
        log "Could not determine UID for user $ACTIVE_USER"
        return 1
    fi
    
    # Send notification to user's desktop
    if sudo -u "$ACTIVE_USER" \\
        DISPLAY=:0 \\
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/${{USER_UID}}/bus" \\
        notify-send -i "$icon" -u "$urgency" "$title" "$message" 2>/dev/null; then
        log "Notification sent: $title - $message"
    else
        log "Failed to send notification (notify-send error)"
    fi
}}

check_wg_available() {{
    if ! command -v wg &>/dev/null; then
        log "ERROR: 'wg' command not found - WireGuard tools not installed"
        return 1
    fi
    return 0
}}

wait_for_handshake() {{
    local interface="$1"
    local pid_file="$PID_DIR/$interface.pid"
    local timeout=30
    local interval=0.5
    local iterations=$((timeout * 2))  # 30s / 0.5s = 60 iterations
    local start_time
    local end_time
    local elapsed
    
    start_time=$(date +%s.%N)
    
    log "Starting handshake monitor for $interface (timeout: ${{timeout}}s)"
    
    # Check if wg command is available
    if ! check_wg_available; then
        send_notification "PIA VPN Error" "WireGuard tools not installed" "dialog-error" "critical"
        return 1
    fi
    
    for ((i=1; i<=iterations; i++)); do
        # Check if we should exit (down event killed us)
        if [[ ! -f "$pid_file" ]]; then
            log "PID file removed, exiting handshake monitor for $interface"
            exit 0
        fi
        
        # Query WireGuard for handshake status
        HANDSHAKE=$(wg show "$interface" latest-handshakes 2>/dev/null | awk '{{print $2}}')
        
        # Check if handshake completed (non-zero timestamp)
        if [[ -n "$HANDSHAKE" ]] && [[ "$HANDSHAKE" != "0" ]]; then
            end_time=$(date +%s.%N)
            elapsed=$(echo "$end_time - $start_time" | bc 2>/dev/null || echo "?")
            
            log "Handshake completed for $interface in ${{elapsed}}s"
            
            # Get server endpoint for notification
            ENDPOINT=$(wg show "$interface" endpoints 2>/dev/null | awk '{{print $2}}')
            
            # Send success notification
            if [[ "$elapsed" != "?" ]]; then
                send_notification \\
                    "PIA VPN Connected" \\
                    "WireGuard tunnel ready (${{elapsed}}s)\\n$ENDPOINT" \\
                    "network-vpn" \\
                    "normal"
            else
                send_notification \\
                    "PIA VPN Connected" \\
                    "WireGuard tunnel ready\\n$ENDPOINT" \\
                    "network-vpn" \\
                    "normal"
            fi
            
            # Clean up and exit
            rm -f "$pid_file"
            exit 0
        fi
        
        sleep "$interval"
    done
    
    # Timeout reached
    log "Handshake timeout for $interface after ${{timeout}}s"
    send_notification \\
        "PIA VPN Connection" \\
        "Unable to verify connection for $interface" \\
        "dialog-warning" \\
        "critical"
    
    # Clean up and exit
    rm -f "$pid_file"
    exit 1
}}

kill_existing_monitor() {{
    local interface="$1"
    local pid_file="$PID_DIR/$interface.pid"
    local pid
    
    if [[ -f "$pid_file" ]]; then
        pid=$(cat "$pid_file" 2>/dev/null)
        
        # Check if PID is valid and process exists
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            log "Killing existing monitor for $interface (PID: $pid)"
            kill "$pid" 2>/dev/null
            
            # Wait briefly for process to die
            sleep 0.2
            
            # Force kill if still alive
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
            fi
        else
            log "Stale PID file found for $interface (PID: $pid not running)"
        fi
        
        rm -f "$pid_file"
    fi
}}

# Main dispatcher logic
INTERFACE="$1"
ACTION="$2"

case "$ACTION" in
    up)
        if [[ "$INTERFACE" == "${{VPN_INTERFACE_PREFIX}}"* ]]; then
            log "Dispatcher: PIA VPN interface $INTERFACE went UP"
            
            # Kill any existing monitor for this interface
            kill_existing_monitor "$INTERFACE"
            
            # Fork background process to monitor handshake
            (
                # Store our PID
                echo $$ > "$PID_DIR/$INTERFACE.pid"
                
                # Wait for handshake
                wait_for_handshake "$INTERFACE"
            ) &
            
            log "Started background handshake monitor for $INTERFACE (PID: $!)"
        fi
        ;;
    down)
        if [[ "$INTERFACE" == "${{VPN_INTERFACE_PREFIX}}"* ]]; then
            log "Dispatcher: PIA VPN interface $INTERFACE went DOWN"
            
            # Small delay to avoid race with up event
            sleep 0.1
            
            # Kill the background monitor if running
            kill_existing_monitor "$INTERFACE"
        fi
        ;;
esac

exit 0
"""


def install_dispatcher_script() -> bool:
    """
    Install NetworkManager dispatcher script for IPv6 leak prevention.

    Requires root privileges. Uses sudo if not already root.

    Returns:
        True if successful, False otherwise
    """
    import os

    try:
        # Create dispatcher directory if it doesn't exist
        if not DISPATCHER_DIR.exists():
            logger.error(f"Dispatcher directory does not exist: {DISPATCHER_DIR}")
            return False

        script_path = DISPATCHER_DIR / DISPATCHER_SCRIPT_NAME

        # Write the script
        script_content = DISPATCHER_SCRIPT.format(logfile=LOGFILE)

        # Check if we're already root
        is_root = os.geteuid() == 0

        # Write the file (use sudo if not root)
        tee_cmd = ["tee", str(script_path)] if is_root else ["sudo", "tee", str(script_path)]
        process = subprocess.run(
            tee_cmd, input=script_content.encode(), capture_output=True, check=True
        )

        # Make it executable and set ownership
        chmod_cmd = (
            ["chmod", "+x", str(script_path)]
            if is_root
            else ["sudo", "chmod", "+x", str(script_path)]
        )
        subprocess.run(chmod_cmd, check=True, capture_output=True)

        chown_cmd = (
            ["chown", "root:root", str(script_path)]
            if is_root
            else ["sudo", "chown", "root:root", str(script_path)]
        )
        subprocess.run(chown_cmd, check=True, capture_output=True)

        logger.info(f"Installed dispatcher script: {script_path}")
        return True

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "No error output"
        logger.error(f"Failed to install dispatcher script: {stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error installing dispatcher script: {e}")
        return False


def uninstall_dispatcher_script() -> bool:
    """
    Remove NetworkManager dispatcher script.

    Requires root privileges. Uses sudo if not already root.

    Returns:
        True if successful, False otherwise
    """
    import os

    try:
        script_path = DISPATCHER_DIR / DISPATCHER_SCRIPT_NAME

        if not script_path.exists():
            logger.info("Dispatcher script not installed, nothing to remove")
            return True

        # Check if we're already root
        is_root = os.geteuid() == 0

        # Remove the script (use sudo if not root)
        rm_cmd = ["rm", str(script_path)] if is_root else ["sudo", "rm", str(script_path)]
        subprocess.run(rm_cmd, check=True, capture_output=True)

        logger.info(f"Removed dispatcher script: {script_path}")
        return True

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "No error output"
        logger.error(f"Failed to remove dispatcher script: {stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error removing dispatcher script: {e}")
        return False


def is_dispatcher_installed() -> bool:
    """Check if the dispatcher script is installed."""
    script_path = DISPATCHER_DIR / DISPATCHER_SCRIPT_NAME
    return script_path.exists()


def get_dispatcher_status() -> dict:
    """
    Get status of the dispatcher script.

    Returns:
        Dictionary with status information
    """
    script_path = DISPATCHER_DIR / DISPATCHER_SCRIPT_NAME

    status = {"installed": script_path.exists(), "path": str(script_path), "logfile": LOGFILE}

    if status["installed"]:
        try:
            # Check if executable
            result = subprocess.run(["test", "-x", str(script_path)], capture_output=True)
            status["executable"] = result.returncode == 0
        except Exception:
            status["executable"] = False

    return status


# Connection Notification Script Management Functions


def install_notify_script() -> bool:
    """
    Install NetworkManager dispatcher script for connection notifications.

    Monitors WireGuard handshake completion and sends desktop notifications
    when VPN connections are fully established.

    Requires root privileges. Uses sudo if not already root.

    Returns:
        True if successful, False otherwise
    """
    import os

    try:
        # Create dispatcher directory if it doesn't exist
        if not DISPATCHER_DIR.exists():
            logger.error(f"Dispatcher directory does not exist: {DISPATCHER_DIR}")
            return False

        script_path = DISPATCHER_DIR / NOTIFY_SCRIPT_NAME

        # Write the script
        script_content = NOTIFY_DISPATCHER_SCRIPT.format(
            logfile=NOTIFY_LOGFILE, pid_dir=NOTIFY_PID_DIR
        )

        # Check if we're already root
        is_root = os.geteuid() == 0

        # Write the file (use sudo if not root)
        tee_cmd = ["tee", str(script_path)] if is_root else ["sudo", "tee", str(script_path)]
        process = subprocess.run(
            tee_cmd, input=script_content.encode(), capture_output=True, check=True
        )

        # Make it executable and set ownership
        chmod_cmd = (
            ["chmod", "+x", str(script_path)]
            if is_root
            else ["sudo", "chmod", "+x", str(script_path)]
        )
        subprocess.run(chmod_cmd, check=True, capture_output=True)

        chown_cmd = (
            ["chown", "root:root", str(script_path)]
            if is_root
            else ["sudo", "chown", "root:root", str(script_path)]
        )
        subprocess.run(chown_cmd, check=True, capture_output=True)

        # Create PID directory if it doesn't exist
        mkdir_cmd = (
            ["mkdir", "-p", NOTIFY_PID_DIR] if is_root else ["sudo", "mkdir", "-p", NOTIFY_PID_DIR]
        )
        subprocess.run(mkdir_cmd, check=True, capture_output=True)

        logger.info(f"Installed notification dispatcher script: {script_path}")
        return True

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "No error output"
        logger.error(f"Failed to install notification dispatcher script: {stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error installing notification dispatcher script: {e}")
        return False


def uninstall_notify_script() -> bool:
    """
    Remove NetworkManager notification dispatcher script.

    Requires root privileges. Uses sudo if not already root.

    Returns:
        True if successful, False otherwise
    """
    import os

    try:
        script_path = DISPATCHER_DIR / NOTIFY_SCRIPT_NAME

        if not script_path.exists():
            logger.info("Notification dispatcher script not installed, nothing to remove")
            return True

        # Check if we're already root
        is_root = os.geteuid() == 0

        # Remove the script (use sudo if not root)
        rm_cmd = ["rm", str(script_path)] if is_root else ["sudo", "rm", str(script_path)]
        subprocess.run(rm_cmd, check=True, capture_output=True)

        logger.info(f"Removed notification dispatcher script: {script_path}")
        return True

    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else "No error output"
        logger.error(f"Failed to remove notification dispatcher script: {stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error removing notification dispatcher script: {e}")
        return False


def is_notify_script_installed() -> bool:
    """Check if the notification dispatcher script is installed."""
    script_path = DISPATCHER_DIR / NOTIFY_SCRIPT_NAME
    return script_path.exists()


def get_notify_script_status() -> dict:
    """
    Get status of the notification dispatcher script.

    Returns:
        Dictionary with status information
    """
    script_path = DISPATCHER_DIR / NOTIFY_SCRIPT_NAME

    status = {
        "installed": script_path.exists(),
        "path": str(script_path),
        "logfile": NOTIFY_LOGFILE,
        "pid_dir": NOTIFY_PID_DIR,
    }

    if status["installed"]:
        try:
            # Check if executable
            result = subprocess.run(["test", "-x", str(script_path)], capture_output=True)
            status["executable"] = result.returncode == 0
        except Exception:
            status["executable"] = False

    return status
