# PIA NetworkManager Integration (pia-nm)

Automate WireGuard token refresh for Private Internet Access (PIA) VPN in NetworkManager on immutable Linux distributions.

## Overview

**pia-nm** is a Python-based automation tool that maintains fresh WireGuard connection profiles for PIA in NetworkManager. It solves the problem that PIA's official VPN client is unavailable on immutable distributions (Aurora, Bluefin, Silverblue), and manual WireGuard configuration requires token refresh every 24 hours.

The tool automates token refresh via systemd timer while integrating with NetworkManager, providing users with a native Linux VPN experience including GUI integration, automatic reconnection, and system settings integration.

## Features

- **Automated Token Refresh**: Tokens refresh automatically every 12 hours via systemd timer
- **Multiple Region Profiles**: Configure and manage multiple PIA regions simultaneously
- **Active Connection Preservation**: Token refresh happens without disconnecting active VPNs
- **Secure Credential Storage**: Credentials stored in system keyring, never in plaintext
- **NetworkManager Integration**: VPN profiles appear in NetworkManager GUI
- **Immutable Distribution Support**: Works on Fedora Silverblue, Aurora, Bluefin, and similar
- **Easy Setup**: Interactive setup wizard guides initial configuration
- **Comprehensive Logging**: Detailed logs for troubleshooting

## Requirements

### System Requirements

- **OS**: Fedora Silverblue, Aurora, Bluefin, or similar immutable Linux distribution
- **Python**: 3.9 or later
- **NetworkManager**: With WireGuard support
- **systemd**: For timer-based automation
- **wireguard-tools**: For WireGuard key generation

### PIA Requirements

- Active PIA subscription
- Valid PIA username and password

### Installation of System Dependencies

On Fedora-based systems:

```bash
sudo dnf install NetworkManager wireguard-tools systemd
```

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/user/pia-nm.git
cd pia-nm

# Install in user directory
pip install --user .

# Or install in development mode
pip install --user -e .
```

### Verify Installation

```bash
# Check if pia-nm is available
pia-nm --help

# Verify system dependencies
pia-nm setup  # Will check for required commands
```

## Quick Start

### 1. Initial Setup

```bash
pia-nm setup
```

This interactive wizard will:
- Prompt for your PIA username and password
- Validate credentials with PIA API
- Store credentials securely in system keyring
- Query available PIA regions
- Let you select regions to configure
- Generate WireGuard keys for each region
- Create NetworkManager profiles
- Install systemd timer for automatic refresh

### 2. View Status

```bash
pia-nm status
```

Shows:
- Configured regions
- Last token refresh time
- NetworkManager profile status
- Systemd timer status
- Next scheduled refresh

### 3. Connect via NetworkManager

Use the NetworkManager GUI or CLI:

```bash
# List available connections
nmcli connection show

# Connect to a region
nmcli connection up PIA-US-East

# Disconnect
nmcli connection down PIA-US-East
```

## Commands

### setup
Interactive setup wizard for initial configuration.

```bash
pia-nm setup
```

### list-regions
List available PIA regions and their capabilities.

```bash
# Show all regions
pia-nm list-regions

# Show only regions with port forwarding
pia-nm list-regions --port-forwarding
```

### refresh
Manually refresh authentication tokens for all or specific regions.

```bash
# Refresh all regions
pia-nm refresh

# Refresh specific region
pia-nm refresh --region us-east
```

### add-region
Add a new region to your configuration.

```bash
pia-nm add-region us-west
```

### remove-region
Remove a region from your configuration.

```bash
pia-nm remove-region us-west
```

### status
Display current configuration and status.

```bash
pia-nm status
```

### install
Install systemd timer for automatic token refresh.

```bash
pia-nm install
```

### uninstall
Remove all pia-nm components and clean up.

```bash
pia-nm uninstall
```

### enable / disable
Enable or disable the automatic refresh timer.

```bash
# Enable automatic refresh
pia-nm enable

# Disable automatic refresh
pia-nm disable
```

## Configuration

Configuration is stored at `~/.config/pia-nm/config.yaml`:

```yaml
regions:
  - us-east
  - uk-london
  - jp-tokyo

preferences:
  dns: true              # Use PIA DNS servers
  ipv6: false            # Disable IPv6
  port_forwarding: false # Port forwarding (future feature)

metadata:
  version: 1
  last_refresh: "2025-11-13T10:30:00Z"
```

### File Locations

- **Config**: `~/.config/pia-nm/config.yaml`
- **WireGuard Keys**: `~/.config/pia-nm/keys/`
- **Logs**: `~/.local/share/pia-nm/logs/pia-nm.log`
- **Systemd Units**: `~/.config/systemd/user/`

## Automatic Token Refresh

The systemd timer automatically refreshes tokens every 12 hours:

- **First refresh**: 5 minutes after system boot
- **Subsequent refreshes**: Every 12 hours
- **Active connections**: Preserved during refresh (no disconnection)

Check timer status:

```bash
systemctl --user status pia-nm-refresh.timer
systemctl --user list-timers pia-nm-refresh.timer
```

View refresh logs:

```bash
journalctl --user -u pia-nm-refresh.service -f
```

## Troubleshooting

### Authentication Failed

Verify your PIA credentials:
1. Visit https://www.privateinternetaccess.com/pages/login
2. Confirm your username and password are correct
3. Run `pia-nm setup` again

### NetworkManager Errors

Check if NetworkManager is running:

```bash
systemctl status NetworkManager
```

If a profile is corrupted, remove and recreate it:

```bash
pia-nm remove-region <region-id>
pia-nm add-region <region-id>
```

### Network Connectivity Issues

Check your internet connection:

```bash
ping 8.8.8.8
```

If you're behind a firewall, ensure outbound HTTPS (port 443) is allowed.

### Systemd Timer Not Running

Enable the timer:

```bash
systemctl --user enable --now pia-nm-refresh.timer
```

### View Detailed Logs

```bash
# View application logs
tail -f ~/.local/share/pia-nm/logs/pia-nm.log

# View systemd service logs
journalctl --user -u pia-nm-refresh.service -f
```

## Security

### Credential Protection

- Credentials stored in system keyring (never plaintext)
- WireGuard private keys stored with 0600 permissions (user only)
- Configuration files stored with 0600 permissions
- Credentials never logged or displayed

### File Permissions

```
~/.config/pia-nm/config.yaml         0600 (user only)
~/.config/pia-nm/keys/*.key          0600 (user only)
~/.config/pia-nm/keys/*.pub          0644 (readable)
~/.local/share/pia-nm/logs/*.log     0644 (readable)
```

### API Communication

- All PIA API communication uses HTTPS
- TLS certificate validation enabled
- Credentials sent via HTTP Basic Auth (over TLS)

## Development

### Setup Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
black pia_nm/

# Type checking
mypy pia_nm/

# Linting
pylint pia_nm/
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure code passes linting and type checking
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## References

- [PIA Manual Connections](https://github.com/pia-foss/manual-connections)
- [NetworkManager Documentation](https://networkmanager.dev/)
- [WireGuard Protocol](https://www.wireguard.com/)
- [Systemd Timers](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Note**: This tool is not affiliated with Private Internet Access. It is a community project to improve VPN usability on immutable Linux distributions.
