# PolicyKit Configuration for Token Refresh

## Problem

Token refresh fails with "Insufficient privileges" error even though connections have user permissions set. This occurs because:

1. NetworkManager requires PolicyKit authorization for `settings.modify.system` action
2. Non-interactive sessions (SSH, systemd timers) cannot provide PolicyKit authentication
3. Even connections with `permissions=user:username:;` require PolicyKit auth to modify

## Root Cause

When connections are created with `save_to_disk=True`, they become system connections stored in `/etc/NetworkManager/system-connections/`. NetworkManager's PolicyKit policy requires authentication to modify these connections, regardless of the `permissions` field.

The `permissions` field controls **visibility** and **who can modify**, but PolicyKit controls **whether authentication is required**.

## Solutions

### Option 1: Run with sudo (Quick Fix)

```bash
sudo pia-nm refresh
```

Or configure the systemd timer to run as root:

```bash
sudo systemctl edit pia-nm-refresh.service
```

Add:
```ini
[Service]
User=root
```

**Pros:** Works immediately
**Cons:** Runs with elevated privileges

### Option 2: Add PolicyKit Rule (Recommended)

Create `/etc/polkit-1/rules.d/90-pia-nm.rules`:

```javascript
// Allow users in wheel group to modify NetworkManager connections without authentication
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.NetworkManager.settings.modify.system" &&
        subject.isInGroup("wheel")) {
        return polkit.Result.YES;
    }
});
```

Then reload PolicyKit:
```bash
sudo systemctl reload polkit
```

**Pros:** Secure, works for all users in wheel group, no password prompts
**Cons:** Requires root to configure, affects all NetworkManager operations

### Option 3: User-Specific PolicyKit Rule

Create `/etc/polkit-1/rules.d/90-pia-nm.rules`:

```javascript
// Allow specific user to modify NetworkManager connections without authentication
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.NetworkManager.settings.modify.system" &&
        subject.user == "YOUR_USERNAME") {
        return polkit.Result.YES;
    }
});
```

Replace `YOUR_USERNAME` with your actual username.

**Pros:** More restrictive than Option 2
**Cons:** Requires root to configure, must be done per-user

## Verification

After applying a PolicyKit rule, verify it works:

```bash
# Check PolicyKit permissions
nmcli general permissions

# Should show "yes" instead of "auth":
# org.freedesktop.NetworkManager.settings.modify.system  yes

# Test token refresh
pia-nm refresh
```

## Technical Details

### Why doesn't `permissions=user:X:;` work?

The `permissions` field in NetworkManager connections controls:
- **Visibility**: Who can see the connection
- **Ownership**: Who is allowed to modify it (if PolicyKit permits)

But PolicyKit is a separate authorization layer that controls:
- **Whether authentication is required** for the operation

Even if a connection says "user X can modify this", PolicyKit still asks "does user X need to authenticate to perform this modification?"

### Why does this fail in SSH/systemd?

PolicyKit authentication requires an interactive session where the user can enter a password. SSH sessions and systemd timers are non-interactive, so PolicyKit denies the operation rather than prompting for a password.

### Alternative: Volatile Connections

We could use `save_to_disk=False` to create volatile (in-memory) connections that don't require PolicyKit auth to modify. However:
- **Cons**: Lost on NetworkManager restart/reboot
- **Cons**: Would need to recreate connections on every boot
- **Not recommended** for this use case

## References

- [NetworkManager PolicyKit Documentation](https://networkmanager.dev/docs/api/latest/NetworkManager-conf.html)
- [PolicyKit Rule Syntax](https://www.freedesktop.org/software/polkit/docs/latest/polkit.8.html)
