# Installation Guide for pia-nm

## For Atomic Fedora Systems (Aurora, Bluefin, Silverblue)

Since atomic Fedora systems have an immutable base, we distribute pia-nm as a PEX (Python EXecutable) file. This is a single executable that bundles all Python dependencies - no pip or package installation needed on your system.

### Prerequisites

Verify system packages are installed (usually pre-installed on Aurora/Bluefin):

```bash
# Check if packages are installed
rpm -q wireguard-tools NetworkManager

# If missing, install them
sudo rpm-ostree install wireguard-tools NetworkManager
sudo systemctl reboot
```

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
# Install system dependencies
sudo dnf install wireguard-tools NetworkManager python3-pip

# Install from GitHub
pip install --user git+https://github.com/abirkel/pia-nm.git
```

## Initial Setup

After installation, run the setup wizard:

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
