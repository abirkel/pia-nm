# PIA NetworkManager Connection Notifications

## Overview

The connection notification dispatcher script monitors WireGuard handshake completion and sends desktop notifications when VPN connections are fully established. This solves the issue where NetworkManager shows "connected" immediately, but the WireGuard tunnel takes several seconds to actually negotiate and become ready for traffic.

## Features

- **Accurate Connection Status**: Only notifies when WireGuard handshake actually completes
- **Connection Time Tracking**: Shows how long it took to establish the connection
- **Timeout Handling**: Warns if connection cannot be verified within 30 seconds
- **Clean Lifecycle Management**: Automatically kills monitors when VPN disconnects
- **Stale PID Protection**: Handles system crashes and restarts gracefully
- **Separate Logging**: Logs to `/var/log/pia-nm-notify.log` for easy debugging

## How It Works

1. **On VPN Connect (`up` event)**:
   - Kills any existing monitor for the interface (handles reconnects)
   - Forks a background process to monitor handshake
   - Stores PID in `/run/pia-nm/<interface>.pid`
   - Polls `wg show <interface> latest-handshakes` every 0.5 seconds
   - Waits up to 30 seconds for handshake completion

2. **On Handshake Success**:
   - Calculates connection time
   - Sends notification: "PIA VPN Connected - WireGuard tunnel ready (X.Xs)"
   - Shows server endpoint
   - Uses `network-vpn` icon with normal urgency
   - Cleans up PID file and exits

3. **On Timeout (30 seconds)**:
   - Sends warning notification: "Unable to verify connection"
   - Uses `dialog-warning` icon with critical urgency
   - Cleans up PID file and exits

4. **On VPN Disconnect (`down` event)**:
   - Checks for PID file
   - Kills the background monitor process if running
   - Handles stale PIDs gracefully
   - Cleans up PID file

## Installation

### Using Python API

```python
from pia_nm.dispatcher import install_notify_script, get_notify_script_status

# Install the script
success = install_notify_script()

# Check status
status = get_notify_script_status()
print(status)
# {'installed': True, 'path': '/etc/NetworkManager/dispatcher.d/98-pia-nm-connection-notify.sh',
#  'logfile': '/var/log/pia-nm-notify.log', 'pid_dir': '/run/pia-nm', 'executable': True}
```

### Manual Installation

The script will be installed to:
- **Script**: `/etc/NetworkManager/dispatcher.d/98-pia-nm-connection-notify.sh`
- **Log file**: `/var/log/pia-nm-notify.log`
- **PID directory**: `/run/pia-nm/`

## Requirements

- **WireGuard Tools**: The `wg` command must be installed
- **Notification Daemon**: Desktop environment with notification support
- **NetworkManager**: Dispatcher service must be running

## Notifications

### Success Notification
- **Title**: "PIA VPN Connected"
- **Message**: "WireGuard tunnel ready (2.3s)\n192.0.2.1:1337"
- **Icon**: `network-vpn`
- **Urgency**: Normal

### Timeout Notification
- **Title**: "PIA VPN Connection"
- **Message**: "Unable to verify connection for wg-pia-us-east"
- **Icon**: `dialog-warning`
- **Urgency**: Critical (stays visible longer)

## Logging

All events are logged to `/var/log/pia-nm-notify.log`:

```
2026-01-17 15:30:45 - Dispatcher: PIA VPN interface wg-pia-us-east went UP
2026-01-17 15:30:45 - Started background handshake monitor for wg-pia-us-east (PID: 12345)
2026-01-17 15:30:45 - Starting handshake monitor for wg-pia-us-east (timeout: 30s)
2026-01-17 15:30:47 - Handshake completed for wg-pia-us-east in 2.3s
2026-01-17 15:30:47 - Notification sent: PIA VPN Connected - WireGuard tunnel ready (2.3s)
```

## Corner Cases Handled

1. **Rapid Connect/Disconnect**: PID file tracking ensures old monitors are killed
2. **Stale PIDs**: Checks if process actually exists before killing
3. **System Suspend/Resume**: Monitor exits if PID file is removed
4. **Multiple Connections**: Each interface gets its own monitor and PID file
5. **Missing WireGuard Tools**: Gracefully handles missing `wg` command
6. **No Active User**: Logs error if no X session user found
7. **Notification Daemon Down**: Fails gracefully if notify-send unavailable

## Uninstallation

```python
from pia_nm.dispatcher import uninstall_notify_script

success = uninstall_notify_script()
```

## Relationship to IPv6 Guard

The notification script (`98-pia-nm-connection-notify.sh`) runs **before** the IPv6 guard script (`99-pia-nm-ipv6-guard.sh`) due to alphabetical ordering. Both scripts:

- Run asynchronously (don't block NetworkManager)
- Handle the same interface prefix (`wg-pia-*`)
- Log to separate files for clarity
- Are independent and can be installed/uninstalled separately

## Troubleshooting

**No notifications appearing:**
1. Check if script is installed: `ls -la /etc/NetworkManager/dispatcher.d/98-pia-nm-connection-notify.sh`
2. Check if script is executable: `test -x /etc/NetworkManager/dispatcher.d/98-pia-nm-connection-notify.sh && echo "OK"`
3. Check log file: `tail -f /var/log/pia-nm-notify.log`
4. Verify WireGuard tools: `which wg`
5. Check for active X session: `who | grep '(:0)'`

**Timeout notifications:**
- Check WireGuard connection: `wg show`
- Verify server is reachable: Check firewall/network
- Review NetworkManager logs: `journalctl -u NetworkManager -f`

**Stale PID files:**
- PID files are automatically cleaned up on timeout or success
- Manual cleanup: `sudo rm /run/pia-nm/*.pid`
