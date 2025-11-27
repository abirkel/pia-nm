# Troubleshooting Guide

Common issues and solutions for pia-nm.

## Authentication Failed

**Error:** `✗ Authentication failed: Invalid credentials`

**Solution:**

1. Verify credentials at https://www.privateinternetaccess.com/pages/login
2. Update credentials: `pia-nm setup`
3. Check internet connection: `ping 8.8.8.8`
4. View logs: `tail -f ~/.local/share/pia-nm/logs/pia-nm.log`

## NetworkManager Errors

### NetworkManager Not Running

**Error:** `✗ D-Bus error: NetworkManager not available`

**Solution:**

```bash
# Check status
systemctl status NetworkManager

# Start if needed
sudo systemctl start NetworkManager
sudo systemctl enable NetworkManager

# Verify version (need >= 1.16)
nmcli --version
```

### Connection Update Failed

**Error:** `✗ NetworkManager error: Failed to update connection`

**Solution:**

```bash
# Remove and recreate profile
pia-nm remove-region <region-id>
pia-nm add-region <region-id>

# Check NetworkManager logs
journalctl -u NetworkManager -n 50
```

## PyGObject Issues

### "No module named 'gi'"

**Solution:**

```bash
# Debian/Ubuntu
sudo apt install python3-gi

# Fedora
sudo dnf install python3-gobject

# Verify
python3 -c "import gi; print(gi.__version__)"
```

**Important:** Install via system package manager, not pip.

### "Namespace 'NM' not available"

**Solution:**

```bash
# Debian/Ubuntu
sudo apt install gir1.2-nm-1.0

# Fedora (usually included)
sudo dnf install NetworkManager

# Verify
python3 -c "from gi.repository import NM; print('OK')"
```

## Network Connectivity

**Error:** `✗ Network error: Unable to reach PIA servers`

**Solution:**

```bash
# Check internet
ping 8.8.8.8

# Check HTTPS
curl -I https://www.privateinternetaccess.com

# Check DNS
nslookup www.privateinternetaccess.com

# Retry
pia-nm refresh
```

## Systemd Timer Not Running

**Solution:**

```bash
# Check status
systemctl --user status pia-nm-refresh.timer

# Enable and start
systemctl --user enable --now pia-nm-refresh.timer

# Verify scheduled
systemctl --user list-timers pia-nm-refresh.timer

# View logs
journalctl --user -u pia-nm-refresh.service -f
```

## Profiles Not in GUI

**Solution:**

```bash
# Verify profiles exist
nmcli connection show | grep PIA

# Reload NetworkManager
sudo systemctl restart NetworkManager

# Recreate if needed
pia-nm remove-region <region-id>
pia-nm add-region <region-id>
```

## Credentials Not Stored

**Solution:**

```bash
# Check keyring
keyring get pia-nm username

# Run setup again
pia-nm setup

# Check keyring service
systemctl --user status gnome-keyring-daemon
```

## WireGuard Key Issues

**Solution:**

```bash
# Verify wireguard-tools installed
wg --version

# Install if needed
sudo dnf install wireguard-tools

# Check permissions
ls -la ~/.config/pia-nm/keys/

# Recreate region
pia-nm remove-region <region-id>
pia-nm add-region <region-id>
```

## Viewing Logs

### Application Logs

```bash
# Last 50 lines
tail -50 ~/.local/share/pia-nm/logs/pia-nm.log

# Follow in real-time
tail -f ~/.local/share/pia-nm/logs/pia-nm.log
```

### Systemd Logs

```bash
# Service logs
journalctl --user -u pia-nm-refresh.service -n 50

# Follow in real-time
journalctl --user -u pia-nm-refresh.service -f

# Timer logs
journalctl --user -u pia-nm-refresh.timer -f
```

## Getting Help

If issues persist:

1. **Collect system info:**
   ```bash
   uname -a
   python3 --version
   nmcli --version
   wg --version
   ```

2. **Collect logs:**
   ```bash
   cat ~/.local/share/pia-nm/logs/pia-nm.log
   journalctl --user -u pia-nm-refresh.service -n 100
   ```

3. **Open GitHub issue** with:
   - Error message
   - Relevant logs
   - System information
   - Steps to reproduce

**Note:** Logs never contain credentials, so they're safe to share.
