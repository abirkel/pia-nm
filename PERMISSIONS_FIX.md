# Connection Permissions Fix

## Problem

Token refresh was failing with "Insufficient privileges" error because connections were being created as system-wide connections without user permissions. Users couldn't modify their own VPN connections.

## Root Cause

When NetworkManager connections are created with `save_to_disk=True` but without explicit permissions, they become system-wide connections stored in `/etc/NetworkManager/system-connections/` with root ownership. Regular users need PolicyKit authentication to modify these connections.

## Solution

### 1. **Add User Permissions During Connection Creation**
   - Added `get_current_username()` utility function
   - Set `permissions = ['user:{username}:']` on connections
   - Connections are now user-owned and modifiable without root

### 2. **Improved Error Messages**
   - Extract full error details from GLib.Error (message, domain, code)
   - Show meaningful errors instead of just "0"
   - Add helpful hints for permission errors

### 3. **Fixed Misleading Setup Logs**
   - Changed "Private key not found" from ERROR to INFO
   - New message: "No existing keypair found, will generate new one"
   - Removes confusion during normal first-time setup

## Files Modified

- `pia_nm/wireguard_connection.py` - Add permissions to connections
- `pia_nm/dbus_client.py` - Better GLib.Error handling
- `pia_nm/token_refresh.py` - Improved error messages with hints
- `pia_nm/wireguard.py` - Fix misleading ERROR logs

## Testing

Users with existing connections will need to recreate them:
```bash
# Remove old system-wide connections
sudo rm /etc/NetworkManager/system-connections/PIA-*.nmconnection
sudo systemctl reload NetworkManager

# Recreate with proper permissions
pia-nm setup
```

New installations will automatically get user-owned connections.

## Expected Behavior

✅ Token refresh works without root privileges
✅ Clear error messages guide users to solutions  
✅ No misleading errors during setup
✅ Connections are user-owned and manageable
