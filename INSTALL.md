# Installation Guide for pia-nm

## Quick Start

Choose your installation method based on your system:

- **Atomic Fedora (Aurora, Bluefin, Silverblue)**: Use RPM (recommended)
- **Traditional Fedora, Debian, Ubuntu**: Use pip
- **Development**: Use pip with editable install

---

## Method 1: RPM Installation (Recommended for Atomic Fedora Only)

### For Atomic Fedora Systems (Aurora, Bluefin, Silverblue)

```bash
# Download the latest RPM
curl -L -O https://github.com/abirkel/pia-nm/releases/latest/download/pia-nm-0.1.0-1.fc41.noarch.rpm

# Install with rpm-ostree
rpm-ostree install ./pia-nm-0.1.0-1.fc41.noarch.rpm

# Reboot to apply
sudo systemctl reboot
```

After reboot, verify installation:

```bash
pia-nm --help
```



### What Gets Installed

The RPM package installs:
- `/usr/bin/pia-nm` - Main executable
- `/usr/lib/systemd/user/pia-nm-refresh.service` - Systemd service unit
- `/usr/lib/systemd/user/pia-nm-refresh.timer` - Systemd timer unit
- Python package and dependencies

All dependencies are automatically installed:
- `python3-requests` - HTTP client for PIA API
- `python3-keyring` - Secure credential storage
- `python3-pyyaml` - Configuration file handling
- `python3-gobject` - D-Bus communication with NetworkManager
- `NetworkManager` - Network management daemon
- `wireguard-tools` - WireGuard key generation

---

## Method 2: pip Installation

### Fedora/RHEL Systems

```bash
# Install system dependencies (MUST be installed via dnf, not pip)
sudo dnf install python3-gobject NetworkManager wireguard-tools python3-pip

# Install pia-nm via pip
pip install --user git+https://github.com/abirkel/pia-nm.git

# Ensure ~/.local/bin is in your PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify installation
pia-nm --help
```

### Debian/Ubuntu Systems

```bash
# Install system dependencies (MUST be installed via apt, not pip)
sudo apt install python3-gi gir1.2-nm-1.0 network-manager wireguard-tools python3-pip

# Install pia-nm via pip
pip install --user git+https://github.com/abirkel/pia-nm.git

# Ensure ~/.local/bin is in your PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify installation
pia-nm --help
```

### Why System Packages Are Required

**PyGObject (python3-gobject / python3-gi)** MUST be installed via system package manager because:
- It requires compiled C extensions linked to system libraries (GLib, GObject)
- It needs GObject introspection data files installed system-wide
- pip cannot provide these system-level dependencies

**GObject Introspection Data (gir1.2-nm-1.0)** provides:
- Type information for NetworkManager's D-Bus API
- Enables type-safe Python bindings to NetworkManager
- On Fedora, this is typically included with the NetworkManager package
- On Debian/Ubuntu, it must be installed separately

---

## Verify D-Bus Setup

Before running setup, verify all D-Bus dependencies are correctly installed:

```bash
python3 -c "
import gi
gi.require_version('NM', '1.0')
from gi.repository import NM
client = NM.Client.new(None)
print(f'✓ NetworkManager version: {client.get_version()}')
print('✓ D-Bus setup is correct')
"
```

If this fails, install the missing dependencies as shown above.

---

## Initial Setup

After installation, run the setup wizard:

```bash
pia-nm setup
```

This interactive wizard will:
1. Prompt for your PIA credentials (stored securely in system keyring)
2. Let you select regions to configure
3. Create NetworkManager WireGuard profiles
4. Install and enable systemd timer for automatic token refresh

Example session:

```
PIA NetworkManager Setup
========================================

PIA Username: your_username
PIA Password: ********

Testing credentials...
✓ Authentication successful
✓ Credentials stored in keyring

Fetching available regions...

Available regions:
  1. us-east              US East
  2. us-west              US West
  3. uk-london            UK London
  4. jp-tokyo             Japan Tokyo
  ...

Enter region IDs to configure (comma-separated):
Example: us-east,uk-london,jp-tokyo
> us-east,uk-london

Creating profiles...
  Setting up us-east...
  ✓ us-east configured
  Setting up uk-london...
  ✓ uk-london configured

Installing systemd timer...
✓ Setup complete!

You can now:
  - View regions: pia-nm status
  - Connect via NetworkManager GUI
  - Connect via CLI: nmcli connection up PIA-US-East

Token refresh runs automatically every 12 hours.
```

---

## Verify Installation

```bash
# Check version
pia-nm --version

# Check status
pia-nm status

# List available regions
pia-nm list-regions

# Check systemd timer
systemctl --user status pia-nm-refresh.timer
```

---

## For Developers: Building from Source

### Build RPM Locally

```bash
# Clone repository
git clone https://github.com/abirkel/pia-nm.git
cd pia-nm

# Install build dependencies
sudo dnf install rpm-build python3-devel python3-setuptools python3-wheel

# Build source RPM
make srpm

# Build binary RPM
make rpm

# Install locally built RPM
sudo dnf install ~/rpmbuild/RPMS/noarch/pia-nm-*.rpm
```

### Development Install with pip

```bash
# Clone repository
git clone https://github.com/abirkel/pia-nm.git
cd pia-nm

# Install system dependencies
sudo dnf install python3-gobject NetworkManager wireguard-tools

# Install in editable mode with dev dependencies
pip install --user -e ".[dev]"

# Run tests
pytest

# Format code
black pia_nm/

# Type check
mypy pia_nm/

# Lint
pylint pia_nm/
```

---

## Troubleshooting

### "command not found: pia-nm"

**For RPM install**: The package installs to `/usr/bin/pia-nm` which should be in your PATH automatically.

**For pip install**: Make sure `~/.local/bin` is in your PATH:

```bash
echo $PATH | grep -q "$HOME/.local/bin" || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### "No module named 'gi'"

PyGObject is not installed. Install via system package manager:

```bash
# Fedora/RHEL
sudo dnf install python3-gobject

# Debian/Ubuntu
sudo apt install python3-gi
```

**Do NOT use pip** - PyGObject requires system libraries.

### "Namespace 'NM' not available"

NetworkManager GObject introspection data is missing:

```bash
# Debian/Ubuntu
sudo apt install gir1.2-nm-1.0

# Fedora/RHEL (usually included with NetworkManager)
sudo dnf install NetworkManager
```

### "NetworkManager version too old"

WireGuard support requires NetworkManager >= 1.16:

```bash
# Check version
nmcli --version

# Upgrade if needed
sudo dnf upgrade NetworkManager  # Fedora
sudo apt upgrade network-manager  # Debian/Ubuntu
```

### Permission Errors

Ensure your user has permission to modify NetworkManager connections:

```bash
# Check if you're in the right group
groups | grep -E 'wheel|sudo|netdev'

# On Fedora, users in 'wheel' group can modify connections
# On Debian/Ubuntu, users in 'netdev' group can modify connections
```

### RPM Installation Fails on Atomic Systems

On atomic Fedora systems (Aurora, Bluefin, Silverblue), use `rpm-ostree` instead of `dnf`:

```bash
rpm-ostree install ./pia-nm-*.rpm
sudo systemctl reboot
```

---

## Uninstallation

### RPM Uninstall

```bash
# Stop and disable timer first
systemctl --user disable --now pia-nm-refresh.timer

# Remove package
sudo dnf remove pia-nm  # Traditional Fedora
# OR
rpm-ostree uninstall pia-nm  # Atomic Fedora (requires reboot)

# Optionally remove configuration and data
rm -rf ~/.config/pia-nm
rm -rf ~/.local/share/pia-nm
```

### pip Uninstall

```bash
# Stop and disable timer first
systemctl --user disable --now pia-nm-refresh.timer

# Remove systemd units
rm ~/.config/systemd/user/pia-nm-refresh.*
systemctl --user daemon-reload

# Uninstall package
pip uninstall pia-nm

# Optionally remove configuration and data
rm -rf ~/.config/pia-nm
rm -rf ~/.local/share/pia-nm
```

---

## Next Steps

- See [README.md](README.md) for usage overview
- See [COMMANDS.md](COMMANDS.md) for detailed command reference
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
