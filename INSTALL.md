# Installation Guide for pia-nm

## For Atomic Fedora Systems (Aurora, Bluefin, Silverblue)

Since atomic Fedora systems have an immutable base, we distribute pia-nm as a PEX (Python EXecutable) file. This is a single executable that bundles all Python dependencies - no pip or package installation needed on your system.

### Prerequisites

Verify system packages are installed (usually pre-installed on Aurora/Bluefin):

```bash
# Check if packages are installed
rpm -q wireguard-tools NetworkManager python3-gobject

# If missing, install them
sudo rpm-ostree install wireguard-tools NetworkManager python3-gobject
sudo systemctl reboot
```

**Note**: PyGObject (python3-gobject) is required for D-Bus communication with NetworkManager. This is typically pre-installed on Fedora-based systems.

### Installation Steps

```bash
# Download the latest release (built automatically by GitHub Actions)
curl -L -o pia-nm https://github.com/abirkel/pia-nm/releases/latest/download/pia-nm.pex

# Make it executable
chmod +x pia-nm

# Move to your local bin directory
mkdir -p ~/.local/bin
mv pia-nm ~/.local/bin/

# Ensure ~/.local/bin is in your PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify installation
pia-nm --help
```

That's it! The PEX file contains everything needed. No pip, no virtual environments, no dependency hell.

### For Developers: Building from Source

Only needed if you're developing pia-nm. Regular users should use the pre-built PEX above.

```bash
# Clone the repository
git clone https://github.com/abirkel/pia-nm.git
cd pia-nm

# Build in a toolbox (keeps your base system clean)
toolbox create -c dev
toolbox enter dev
pip install pex
make pex
exit

# Install the locally-built PEX
cp pia-nm.pex ~/.local/bin/pia-nm
```

## For Traditional Linux Systems

If you're on a traditional (non-atomic) system, you can use either PEX or pip:

### Option 1: PEX (Recommended - Same as Atomic)

```bash
curl -L -o pia-nm https://github.com/abirkel/pia-nm/releases/latest/download/pia-nm.pex
chmod +x pia-nm
sudo mv pia-nm /usr/local/bin/
```

### Option 2: pip

```bash
# Install system dependencies (Debian/Ubuntu)
sudo apt install python3-gi gir1.2-nm-1.0 wireguard-tools network-manager python3-pip

# Or on Fedora/RHEL
sudo dnf install python3-gobject NetworkManager wireguard-tools python3-pip

# Install from GitHub
pip install --user git+https://github.com/abirkel/pia-nm.git
```

**Important**: PyGObject must be installed via system package manager (apt/dnf), not pip, as it requires system libraries.

## Verify D-Bus Setup

Before running the setup wizard, verify that all D-Bus dependencies are correctly installed:

```bash
python3 pia_nm/verify_dbus_setup.py
```

This script checks:
- Python version (>= 3.9)
- PyGObject installation
- NetworkManager GObject introspection (gir1.2-nm-1.0)
- NetworkManager version (>= 1.16 for WireGuard support)
- NM.Client creation

If any checks fail, install the missing dependencies as shown in the error messages.

## Initial Setup

After installation and verification, run the setup wizard:

```bash
pia-nm setup
```

This will:
1. Prompt for your PIA credentials
2. Let you select regions to configure
3. Create NetworkManager profiles
4. Install systemd timer for automatic token refresh

## Verify Installation

```bash
# Check version
pia-nm --version

# Check status
pia-nm status

# List available regions
pia-nm list-regions
```

## Troubleshooting

### "command not found: pia-nm"

Make sure `~/.local/bin` is in your PATH:

```bash
echo $PATH | grep -q "$HOME/.local/bin" || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### "No module named 'keyring'"

The PEX file should bundle all dependencies. If you see this error, rebuild the PEX:

```bash
pex . -r <(echo "requests>=2.31.0" && echo "keyring>=24.0.0" && echo "PyYAML>=6.0") -c pia-nm -o pia-nm.pex
```

### Permission Errors

Ensure the PEX file is executable:

```bash
chmod +x ~/.local/bin/pia-nm
```

## Uninstallation

```bash
# Remove the executable
rm ~/.local/bin/pia-nm

# Remove configuration and data
pia-nm uninstall  # Run this before removing the executable

# Or manually remove:
rm -rf ~/.config/pia-nm
rm -rf ~/.local/share/pia-nm
systemctl --user disable --now pia-nm-refresh.timer
rm ~/.config/systemd/user/pia-nm-refresh.*
```

## Next Steps

See [README.md](README.md) for usage instructions and [COMMANDS.md](COMMANDS.md) for detailed command reference.
