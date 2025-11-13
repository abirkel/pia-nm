# pia-nm Commands Reference

Detailed documentation for all pia-nm commands with examples.

## setup

Interactive setup wizard for initial configuration.

```bash
pia-nm setup
```

**What it does:**
- Prompts for PIA username and password
- Validates credentials with PIA API
- Stores credentials securely in system keyring
- Queries available PIA regions
- Lets you select regions to configure
- Generates WireGuard keys for each region
- Creates NetworkManager profiles
- Installs systemd timer for automatic refresh

**Example:**
```
$ pia-nm setup
PIA NetworkManager Setup
========================================

PIA Username: p1234567
PIA Password: ••••••••••••••••••

✓ Authentication successful
✓ Credentials stored in keyring

Fetching available regions...

Available regions:
  1. us-east              US East                    
  2. us-west              US West                    PF
  3. uk-london            UK London                  
  4. jp-tokyo             Japan Tokyo                
  5. de-frankfurt         Germany Frankfurt          PF

Enter region IDs to configure (comma-separated):
Example: us-east,uk-london,jp-tokyo
> us-east,uk-london

Setting up us-east...
✓ us-east configured

Setting up uk-london...
✓ uk-london configured

✓ Setup complete!

You can now:
  - View status: pia-nm status
  - Connect via NetworkManager GUI
  - Manually refresh: pia-nm refresh
```

## list-regions

List available PIA regions and their capabilities.

```bash
# Show all regions
pia-nm list-regions

# Show only regions with port forwarding
pia-nm list-regions --port-forwarding
```

**Example output:**
```
$ pia-nm list-regions
Available PIA Regions:

ID                  Location              Port Forward
─────────────────────────────────────────────────────
us-east             US East               No
us-west             US West               Yes
uk-london           UK London             No
jp-tokyo            Japan Tokyo           No
de-frankfurt        Germany Frankfurt     Yes
```

## refresh

Manually refresh authentication tokens for all or specific regions.

```bash
# Refresh all regions
pia-nm refresh

# Refresh specific region
pia-nm refresh --region us-east
```

**Example output:**
```
$ pia-nm refresh
Refreshing tokens...

✓ us-east: Token refreshed
✓ uk-london: Token refreshed

✓ All regions refreshed successfully
Next automatic refresh: 2025-11-14 10:30 UTC
```

**When to use:**
- After changing your PIA password
- If you suspect a token has expired
- Before a long trip where you want fresh tokens
- To test the refresh mechanism

## add-region

Add a new region to your configuration after initial setup.

```bash
pia-nm add-region us-west
```

**Example output:**
```
$ pia-nm add-region us-west
Verifying region us-west...
✓ Region verified

Setting up us-west...
✓ Generated WireGuard keypair
✓ Registered key with PIA
✓ Created NetworkManager profile

✓ Region us-west added successfully
```

**When to use:**
- You want to add more regions after initial setup
- You want to try a new region
- You need a region for a specific purpose

## remove-region

Remove a region from your configuration.

```bash
pia-nm remove-region us-west
```

**Example output:**
```
$ pia-nm remove-region us-west
Removing region us-west...
✓ Deleted NetworkManager profile
✓ Removed WireGuard keys
✓ Updated configuration

✓ Region us-west removed successfully
```

**When to use:**
- You no longer need a region
- You want to reduce the number of profiles
- You're cleaning up unused configurations

## status

Display current configuration and status.

```bash
pia-nm status
```

**Example output:**
```
$ pia-nm status
PIA NetworkManager Status

Configured Regions:
  • us-east
  • uk-london

Last Token Refresh: 2025-11-13 10:30 UTC (4 hours ago)

NetworkManager Profiles:
  ✓ PIA-US-East (exists)
  ✓ PIA-UK-London (exists)

Systemd Timer:
  ✓ pia-nm-refresh.timer is active
  Next refresh: 2025-11-14 10:30 UTC (in 20 hours)
```

**When to use:**
- Check if everything is configured correctly
- Verify the timer is running
- See when the next refresh is scheduled
- Troubleshoot configuration issues

## install

Install systemd timer for automatic token refresh.

```bash
pia-nm install
```

**What it does:**
- Copies systemd service and timer units to `~/.config/systemd/user/`
- Reloads systemd daemon
- Enables and starts the refresh timer
- Tokens will refresh automatically every 12 hours

**When to use:**
- After initial setup (usually done automatically)
- If you manually uninstalled the timer
- To re-enable automatic refresh

## uninstall

Remove all pia-nm components and clean up.

```bash
pia-nm uninstall
```

**What it does:**
- Removes all PIA NetworkManager profiles
- Disables and removes systemd timer and service
- Deletes configuration directory (`~/.config/pia-nm/`)
- Removes credentials from system keyring

**⚠️ Warning:** This is irreversible. You'll need to run `pia-nm setup` again to reconfigure.

**When to use:**
- You want to completely remove pia-nm
- You're switching to a different VPN solution
- You need to start fresh with a clean configuration

## enable / disable

Enable or disable the automatic refresh timer.

```bash
# Enable automatic refresh
pia-nm enable

# Disable automatic refresh (manual refresh still works)
pia-nm disable
```

**Example:**
```
$ pia-nm disable
✓ Systemd timer disabled

Automatic token refresh is now disabled.
You can still manually refresh with: pia-nm refresh

$ pia-nm enable
✓ Systemd timer enabled

Automatic token refresh is now active.
Next refresh: 2025-11-14 10:30 UTC
```

**When to use:**
- `disable`: You want to manually manage token refresh
- `disable`: You're troubleshooting timer issues
- `enable`: You want to resume automatic refresh
- `enable`: You've fixed an issue and want to re-enable automation

## Tips

### Batch Operations

Add multiple regions at once during setup:
```bash
pia-nm setup
# Select: us-east,us-west,uk-london,jp-tokyo
```

Or add them one by one:
```bash
pia-nm add-region us-east
pia-nm add-region us-west
pia-nm add-region uk-london
```

### Checking Logs

View what happened during the last refresh:
```bash
journalctl --user -u pia-nm-refresh.service -n 20
```

Follow logs in real-time:
```bash
journalctl --user -u pia-nm-refresh.service -f
```

### Manual Refresh Before Travel

Ensure tokens are fresh before a trip:
```bash
pia-nm refresh
pia-nm status
```

### Troubleshooting a Specific Region

Refresh just one region to test:
```bash
pia-nm refresh --region us-east
```

Check if the profile was updated:
```bash
nmcli connection show PIA-US-East
```
