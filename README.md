# PIA NetworkManager Integration (pia-nm)

Automated WireGuard token refresh for Private Internet Access (PIA) VPN in NetworkManager.

## Overview

**pia-nm** is a Python-based automation tool that maintains fresh WireGuard connection profiles for PIA in NetworkManager. Instead of manually refreshing tokens every 24 hours or relying on the official PIA client, pia-nm automates the entire process via systemd timer.

Whether you can't use the official PIA client, prefer native Linux integration, or simply want a hands-off VPN setup, pia-nm provides automated token refresh while integrating seamlessly with NetworkManager for a native Linux VPN experience.

## Features

- **Automated Token Refresh**: Tokens refresh automatically every 12 hours via systemd timer
- **Zero-Downtime Refresh**: Live token updates using NetworkManager's Reapply method - active VPNs never disconnect
- **Multiple Region Profiles**: Configure and manage multiple PIA regions simultaneously
- **D-Bus Integration**: Direct NetworkManager D-Bus API access via PyGObject for reliable, type-safe operations
- **Secure Credential Storage**: Credentials stored in system keyring, never in plaintext
- **NetworkManager Integration**: VPN profiles appear in NetworkManager GUI with full WireGuard configuration
- **Easy Setup**: Interactive setup wizard guides initial configuration

## Requirements

- **OS**: Any Linux distribution with NetworkManager and systemd
- **Python**: 3.9 or later
- **NetworkManager**: 1.16 or later (for WireGuard support)
- **PyGObject**: 3.42.0 or later (Python GObject introspection bindings for D-Bus access)
- **GObject Introspection**: gir1.2-nm-1.0 (NetworkManager GObject introspection data)
- **wireguard-tools**: For WireGuard key generation
- **Active PIA subscription**: Valid username and password

### Install System Dependencies

On Debian/Ubuntu:

```bash
sudo apt install python3-gi gir1.2-nm-1.0 network-manager wireguard-tools
```

On Fedora-based systems (Aurora, Bluefin, Silverblue):

```bash
sudo dnf install python3-gobject NetworkManager wireguard-tools systemd
```

**Note**: PyGObject and gir1.2-nm-1.0 are required for D-Bus communication with NetworkManager. These must be installed via your system package manager (not pip) as they require system libraries.

### Verify Setup

After installing dependencies, verify your system is ready:

```bash
python3 pia_nm/verify_dbus_setup.py
```

This will check that all required components are installed and working correctly.

## Installation

Download the pre-built PEX executable (works on all systems, no pip needed):

```bash
curl -L -o pia-nm https://github.com/abirkel/pia-nm/releases/latest/download/pia-nm.pex
chmod +x pia-nm
mkdir -p ~/.local/bin
mv pia-nm ~/.local/bin/
```

**Traditional Linux users**: You can also use pip if preferred: `pip install --user git+https://github.com/abirkel/pia-nm.git`

See [INSTALL.md](INSTALL.md) for detailed instructions.

Verify installation:

```bash
pia-nm --help
```

## Quick Start

### 1. Initial Setup

```bash
pia-nm setup
```

This interactive wizard will guide you through:
- Entering your PIA credentials
- Selecting regions to configure
- Creating NetworkManager profiles
- Installing the automatic refresh timer

### 2. Connect via NetworkManager

Use the NetworkManager GUI (GNOME Settings, KDE Network Manager) or CLI:

```bash
# List available connections
nmcli connection show

# Connect to a region
nmcli connection up PIA-US-East

# Disconnect
nmcli connection down PIA-US-East
```

### 3. Check Status

```bash
pia-nm status
```

Shows configured regions, last refresh time, and timer status.

## Commands

| Command | Purpose |
|---------|---------|
| `pia-nm setup` | Interactive setup wizard |
| `pia-nm list-regions` | Show available PIA regions |
| `pia-nm refresh` | Manually refresh tokens |
| `pia-nm add-region <id>` | Add a new region |
| `pia-nm remove-region <id>` | Remove a region |
| `pia-nm status` | Show current status |
| `pia-nm install` | Install systemd timer |
| `pia-nm uninstall` | Remove all components |
| `pia-nm enable/disable` | Control automatic refresh |

See [COMMANDS.md](COMMANDS.md) for detailed examples of each command.

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

The systemd timer automatically refreshes tokens every 12 hours using NetworkManager's D-Bus API:

- **First refresh**: 5 minutes after system boot
- **Subsequent refreshes**: Every 12 hours
- **Active connections**: Preserved during refresh using Reapply method (zero downtime)
- **Inactive connections**: Saved profiles updated for next activation

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

Having issues? Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed solutions to common problems.

## Security

- Credentials stored in system keyring (never plaintext)
- All API communication over HTTPS
- WireGuard keys stored with restrictive permissions (0600)
- No credentials or tokens logged



## Contributing

Interested in contributing? See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, code standards, and contribution guidelines.

## License

This project is licensed under the GNU General Public License v3.0 or later (GPLv3+).

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

See the [LICENSE](LICENSE) file for full license text.

## Attribution

This project adapts D-Bus integration patterns from ProtonVPN's [python-proton-vpn-network-manager](https://github.com/ProtonVPN/python-proton-vpn-network-manager) (GPLv3). See [ATTRIBUTION.md](ATTRIBUTION.md) for details.

## References

- [PIA Manual Connections](https://github.com/pia-foss/manual-connections)
- [NetworkManager Documentation](https://networkmanager.dev/)
- [PyGObject Documentation](https://pygobject.readthedocs.io/)
- [WireGuard Protocol](https://www.wireguard.com/)
- [Systemd Timers](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)
- [ProtonVPN NetworkManager Integration](https://github.com/ProtonVPN/python-proton-vpn-network-manager)

## Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Note**: This tool is not affiliated with Private Internet Access. It is a community project created with immutable Linux distributions in mind, but works on any Linux system with NetworkManager and systemd.
