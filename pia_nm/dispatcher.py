"""NetworkManager dispatcher script management for IPv6 leak prevention."""

import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DISPATCHER_SCRIPT_NAME = "99-pia-nm-ipv6-guard.sh"
DISPATCHER_DIR = Path("/etc/NetworkManager/dispatcher.d")
LOGFILE = "/var/log/pia-nm-ipv6.log"

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
            tee_cmd,
            input=script_content.encode(),
            capture_output=True,
            check=True
        )
        
        # Make it executable and set ownership
        chmod_cmd = ["chmod", "+x", str(script_path)] if is_root else ["sudo", "chmod", "+x", str(script_path)]
        subprocess.run(chmod_cmd, check=True, capture_output=True)
        
        chown_cmd = ["chown", "root:root", str(script_path)] if is_root else ["sudo", "chown", "root:root", str(script_path)]
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
    
    status = {
        "installed": script_path.exists(),
        "path": str(script_path),
        "logfile": LOGFILE
    }
    
    if status["installed"]:
        try:
            # Check if executable
            result = subprocess.run(
                ["test", "-x", str(script_path)],
                capture_output=True
            )
            status["executable"] = result.returncode == 0
        except Exception:
            status["executable"] = False
    
    return status
