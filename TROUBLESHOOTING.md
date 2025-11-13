# Troubleshooting Guide

Solutions to common issues and problems with pia-nm.

## Authentication Failed

**Error:** `✗ Authentication failed: Invalid credentials`

**Causes:**
- Incorrect PIA username or password
- PIA subscription expired
- PIA account locked or disabled
- Network connectivity issue

**Solution:**

1. Verify your PIA credentials:
   - Visit https://www.privateinternetaccess.com/pages/login
   - Confirm your username and password are correct
   - Ensure your subscription is active

2. Update credentials:
   ```bash
   pia-nm setup
   ```

3. Check internet connection:
   ```bash
   ping 8.8.8.8
   ```

4. View detailed logs:
   ```bash
   tail -f ~/.local/share/pia-nm/logs/pia-nm.log
   ```

## NetworkManager Errors

**Error:** `✗ NetworkManager error: Failed to update connection`

**Causes:**
- NetworkManager not running
- Corrupted connection profile
- Permission issues
- Conflicting network configuration

**Solution:**

1. Verify NetworkManager is running:
   ```bash
   systemctl status NetworkManager
   ```

2. If not running, start it:
   ```bash
   systemctl start NetworkManager
   ```

3. Check for corrupted profiles:
   ```bash
   nmcli connection show | grep PIA
   ```

4. If a profile is corrupted, remove and recreate it:
   ```bash
   pia-nm remove-region <region-id>
   pia-nm add-region <region-id>
   ```

5. Check file permissions:
   ```bash
   ls -la ~/.config/pia-nm/
   ```
   Should show `drwx------` (0700) for the directory.

## Network Connectivity Issues

**Error:** `✗ Network error: Unable to reach PIA servers`

**Causes:**
- No internet connection
- Firewall blocking HTTPS
- DNS resolution failure
- PIA API temporarily unavailable

**Solution:**

1. Check internet connection:
   ```bash
   ping 8.8.8.8
   ```

2. Verify HTTPS connectivity:
   ```bash
   curl -I https://www.privateinternetaccess.com
   ```

3. Check DNS resolution:
   ```bash
   nslookup www.privateinternetaccess.com
   ```

4. If behind a firewall, ensure outbound HTTPS (port 443) is allowed

5. Try manual refresh:
   ```bash
   pia-nm refresh
   ```

6. If still failing, wait a few minutes and try again (PIA API might be temporarily down)

## Systemd Timer Not Running

**Error:** Timer shows as inactive or not scheduled

**Causes:**
- Timer not installed
- Timer disabled
- Systemd daemon not reloaded
- Service file missing

**Solution:**

1. Check timer status:
   ```bash
   systemctl --user status pia-nm-refresh.timer
   ```

2. If inactive, enable and start it:
   ```bash
   systemctl --user enable --now pia-nm-refresh.timer
   ```

3. Verify it's scheduled:
   ```bash
   systemctl --user list-timers pia-nm-refresh.timer
   ```

4. Check service file exists:
   ```bash
   ls -la ~/.config/systemd/user/pia-nm-refresh.*
   ```

5. If missing, reinstall:
   ```bash
   pia-nm install
   ```

6. View timer logs:
   ```bash
   journalctl --user -u pia-nm-refresh.service -f
   ```

## Connection Drops After Refresh

**Issue:** VPN connection disconnects during token refresh

**Note:** This should NOT happen. The tool uses `nmcli connection modify` which updates profiles without disconnecting active connections.

**Causes:**
- Connection was not actually active
- NetworkManager reloaded during refresh
- Profile corruption
- Systemd service configuration issue

**Solution:**

1. Check if connection was actually active:
   ```bash
   nmcli connection show --active
   ```

2. View refresh logs to see what happened:
   ```bash
   journalctl --user -u pia-nm-refresh.service -n 50
   ```

3. Check the service configuration:
   ```bash
   cat ~/.config/systemd/user/pia-nm-refresh.service
   ```

4. Manually reconnect:
   ```bash
   nmcli connection up PIA-<region>
   ```

5. If this keeps happening, report it as a bug with logs attached

## Profiles Not Appearing in NetworkManager GUI

**Issue:** Created profiles don't show in GNOME Settings or KDE Network Manager

**Causes:**
- Profiles not created properly
- NetworkManager cache not updated
- GUI not refreshed
- Profiles in wrong location

**Solution:**

1. Verify profiles exist:
   ```bash
   nmcli connection show | grep PIA
   ```

2. Check profile details:
   ```bash
   nmcli connection show PIA-US-East
   ```

3. Reload NetworkManager:
   ```bash
   systemctl restart NetworkManager
   ```

4. Refresh GUI (close and reopen settings)

5. If still not showing, check for errors:
   ```bash
   nmcli connection show PIA-US-East
   ```

6. Try recreating the profile:
   ```bash
   pia-nm remove-region us-east
   pia-nm add-region us-east
   ```

## Credentials Not Stored

**Issue:** Credentials not saved in keyring

**Causes:**
- Keyring service not running
- Keyring backend not configured
- Permission issues
- Keyring locked

**Solution:**

1. Check if keyring is available:
   ```bash
   keyring get pia-nm username
   ```

2. If not found, run setup again:
   ```bash
   pia-nm setup
   ```

3. Check keyring service status:
   ```bash
   systemctl --user status gnome-keyring-daemon
   ```

4. If not running, start it:
   ```bash
   systemctl --user start gnome-keyring-daemon
   ```

5. Check keyring backend:
   ```bash
   python3 -c "import keyring; print(keyring.get_keyring())"
   ```

6. View detailed logs:
   ```bash
   tail -f ~/.local/share/pia-nm/logs/pia-nm.log
   ```

## Tokens Not Refreshing

**Issue:** Tokens not refreshing automatically

**Causes:**
- Timer not running
- Service file has errors
- Credentials expired
- Network issues during refresh

**Solution:**

1. Check timer status:
   ```bash
   systemctl --user status pia-nm-refresh.timer
   ```

2. Check when timer last ran:
   ```bash
   systemctl --user list-timers pia-nm-refresh.timer
   ```

3. View service logs:
   ```bash
   journalctl --user -u pia-nm-refresh.service -n 50
   ```

4. Manually trigger refresh:
   ```bash
   pia-nm refresh
   ```

5. Check last refresh time:
   ```bash
   pia-nm status
   ```

6. If manual refresh works but timer doesn't, check service file:
   ```bash
   cat ~/.config/systemd/user/pia-nm-refresh.service
   ```

## WireGuard Key Issues

**Issue:** Key generation or registration fails

**Causes:**
- `wg` command not installed
- Permission issues
- PIA API error
- Corrupted key files

**Solution:**

1. Verify WireGuard tools installed:
   ```bash
   wg --version
   ```

2. If not installed:
   ```bash
   sudo dnf install wireguard-tools
   ```

3. Check key directory permissions:
   ```bash
   ls -la ~/.config/pia-nm/keys/
   ```
   Should show `drwx------` (0700).

4. Try refreshing:
   ```bash
   pia-nm refresh
   ```

5. If still failing, remove and recreate region:
   ```bash
   pia-nm remove-region <region-id>
   pia-nm add-region <region-id>
   ```

6. View logs for details:
   ```bash
   tail -f ~/.local/share/pia-nm/logs/pia-nm.log
   ```

## Configuration File Issues

**Issue:** Config file corrupted or invalid

**Causes:**
- Manual editing with syntax errors
- File permissions wrong
- Incomplete write
- Version mismatch

**Solution:**

1. Check config file:
   ```bash
   cat ~/.config/pia-nm/config.yaml
   ```

2. Validate YAML syntax:
   ```bash
   python3 -c "import yaml; yaml.safe_load(open('~/.config/pia-nm/config.yaml'))"
   ```

3. Check file permissions:
   ```bash
   ls -la ~/.config/pia-nm/config.yaml
   ```
   Should show `-rw-------` (0600).

4. If corrupted, back it up and recreate:
   ```bash
   cp ~/.config/pia-nm/config.yaml ~/.config/pia-nm/config.yaml.bak
   pia-nm setup
   ```

5. Restore regions if needed:
   ```bash
   # Edit config.yaml to restore regions from backup
   ```

## Permission Denied Errors

**Issue:** Permission denied when accessing files or running commands

**Causes:**
- Wrong file permissions
- Running as wrong user
- Systemd service permission issue
- SELinux or AppArmor restrictions

**Solution:**

1. Check file permissions:
   ```bash
   ls -la ~/.config/pia-nm/
   ls -la ~/.local/share/pia-nm/
   ```

2. Fix permissions if needed:
   ```bash
   chmod 0700 ~/.config/pia-nm/
   chmod 0700 ~/.config/pia-nm/keys/
   chmod 0600 ~/.config/pia-nm/config.yaml
   chmod 0600 ~/.config/pia-nm/keys/*
   ```

3. Ensure running as your user (not root):
   ```bash
   whoami
   ```

4. Check systemd service runs as correct user:
   ```bash
   cat ~/.config/systemd/user/pia-nm-refresh.service
   ```

5. If using SELinux or AppArmor, check for denials:
   ```bash
   # SELinux
   sudo ausearch -m avc | grep pia-nm
   
   # AppArmor
   sudo dmesg | grep apparmor
   ```

## Viewing Logs

### Application Logs

View the last 50 lines:
```bash
tail -50 ~/.local/share/pia-nm/logs/pia-nm.log
```

Follow logs in real-time:
```bash
tail -f ~/.local/share/pia-nm/logs/pia-nm.log
```

View all logs:
```bash
cat ~/.local/share/pia-nm/logs/pia-nm.log
```

### Systemd Service Logs

View recent service logs:
```bash
journalctl --user -u pia-nm-refresh.service -n 50
```

Follow service logs in real-time:
```bash
journalctl --user -u pia-nm-refresh.service -f
```

View timer logs:
```bash
journalctl --user -u pia-nm-refresh.timer -f
```

View all related logs:
```bash
journalctl --user -u pia-nm-refresh.service -u pia-nm-refresh.timer -f
```

## Getting Help

If you're still having issues:

1. **Collect diagnostic information:**
   ```bash
   # System info
   uname -a
   
   # Python version
   python3 --version
   
   # NetworkManager version
   nmcli --version
   
   # WireGuard tools
   wg --version
   
   # Systemd version
   systemctl --version
   
   # pia-nm version
   pia-nm --version
   ```

2. **Collect relevant logs (credentials are never logged):**
   ```bash
   # Application logs
   cat ~/.local/share/pia-nm/logs/pia-nm.log
   
   # Systemd logs
   journalctl --user -u pia-nm-refresh.service -n 100
   ```

3. **Open an issue on GitHub** with:
   - Error message (exact text)
   - Relevant log lines
   - System information from above
   - Steps to reproduce
   - What you've already tried

**Note:** Logs never contain credentials, passwords, or tokens, so they're safe to share.
