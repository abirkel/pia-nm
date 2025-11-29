# Packaging Refactor: PEX → RPM

## Summary

Refactored pia-nm packaging from PEX (Python EXecutable) to RPM (Red Hat Package Manager) format, with pip as a secondary installation method.

## Changes Made

### Files Deleted
- `build-pex.sh` - Local PEX build script
- `.github/workflows/build-pex.yml` - GitHub Actions PEX workflow

### Files Created
- `pia-nm.spec` - RPM spec file for building packages
- `.github/workflows/build-rpm.yml` - GitHub Actions RPM workflow

### Files Modified
- `Makefile` - Replaced `pex` and `install-pex` targets with `rpm` and `srpm` targets
- `INSTALL.md` - Complete rewrite with two installation methods (RPM and pip)
- `README.md` - Updated installation section to show RPM first, pip second
- `.kiro/steering/pia-nm-kiro-steering.md` - Updated packaging references

## Installation Methods

### Method 1: RPM (Recommended for Fedora-based systems)

**Target audience**: Aurora, Bluefin, Silverblue, Fedora, RHEL users

**Advantages**:
- Native package management (`dnf install`, `dnf update`, `dnf remove`)
- Automatic dependency resolution
- System integration (proper paths, systemd units)
- Familiar workflow for Fedora users
- Clean uninstallation

**Installation**:
```bash
# Download RPM
curl -L -O https://github.com/abirkel/pia-nm/releases/latest/download/pia-nm-0.1.0-1.fc41.noarch.rpm

# Traditional Fedora
sudo dnf install ./pia-nm-0.1.0-1.fc41.noarch.rpm

# Atomic Fedora (Aurora, Bluefin, Silverblue)
rpm-ostree install ./pia-nm-0.1.0-1.fc41.noarch.rpm
sudo systemctl reboot
```

### Method 2: pip (For Debian/Ubuntu and development)

**Target audience**: Debian/Ubuntu users, developers

**Installation**:
```bash
# Fedora/RHEL
sudo dnf install python3-gobject NetworkManager wireguard-tools python3-pip
pip install --user git+https://github.com/abirkel/pia-nm.git

# Debian/Ubuntu
sudo apt install python3-gi gir1.2-nm-1.0 network-manager wireguard-tools python3-pip
pip install --user git+https://github.com/abirkel/pia-nm.git
```

## RPM Spec File Details

**Package name**: `pia-nm`
**Version**: 0.1.0
**Release**: 1
**Architecture**: noarch (pure Python)

**Dependencies**:
- `python3 >= 3.9`
- `python3-requests >= 2.31.0`
- `python3-keyring >= 24.0.0`
- `python3-pyyaml >= 6.0`
- `python3-gobject >= 3.42.0` (system package required)
- `NetworkManager >= 1.16`
- `wireguard-tools`
- `systemd`

**Installed files**:
- `/usr/bin/pia-nm` - Main executable
- `/usr/lib/systemd/user/pia-nm-refresh.service` - Systemd service
- `/usr/lib/systemd/user/pia-nm-refresh.timer` - Systemd timer
- `/usr/lib/python3.*/site-packages/pia_nm/` - Python package
- Documentation files

## GitHub Actions Workflow

**Trigger**: 
- Push to tags matching `v*` (e.g., `v0.1.0`)
- Manual workflow dispatch with optional Fedora version override

**Default behavior**: Builds for latest Fedora version

**Override**: Users can specify Fedora version via workflow dispatch input

**Build process**:
1. Checkout code
2. Extract version from git tag
3. Create source tarball
4. Run Fedora container with rpmbuild
5. Build RPM inside container
6. Upload artifacts
7. Create GitHub release with RPM attached

**Container**: `fedora:latest` (or user-specified version)

## Local Development

### Build RPM locally

```bash
# Install build dependencies
sudo dnf install rpm-build python3-devel python3-setuptools python3-wheel

# Build source RPM
make srpm

# Build binary RPM
make rpm

# Install locally built RPM
sudo dnf install ~/rpmbuild/RPMS/noarch/pia-nm-*.rpm
```

### Development with pip

```bash
# Clone repo
git clone https://github.com/abirkel/pia-nm.git
cd pia-nm

# Install system dependencies
sudo dnf install python3-gobject NetworkManager wireguard-tools

# Install in editable mode
pip install --user -e ".[dev]"

# Run tests
pytest
```

## Critical Dependency Note

**PyGObject (python3-gobject / python3-gi) MUST be installed via system package manager**, not pip, because:
- Requires compiled C extensions linked to system libraries (GLib, GObject)
- Needs GObject introspection data files installed system-wide
- pip cannot provide these system-level dependencies

**GObject Introspection Data**:
- Fedora: Included with NetworkManager package
- Debian/Ubuntu: Requires separate `gir1.2-nm-1.0` package

## Why RPM over PEX?

**PEX limitations**:
- Cannot bundle PyGObject (system library dependency)
- Still requires system packages to be installed
- No native package management integration
- Manual updates required
- Less familiar to Fedora users

**RPM advantages**:
- Native to target platform (Fedora-based systems)
- Automatic dependency resolution
- System integration (paths, units, documentation)
- Familiar update/remove workflow
- Proper versioning and upgrades

## Migration Path for Existing Users

Users who previously installed via PEX should:

1. Remove PEX installation:
   ```bash
   rm ~/.local/bin/pia-nm
   ```

2. Install via RPM:
   ```bash
   sudo dnf install ./pia-nm-*.rpm
   ```

3. Configuration and data are preserved (stored in `~/.config/pia-nm/`)

## Future Considerations

- **Copr repository**: Host RPMs in Fedora Copr for easier installation (`dnf copr enable user/pia-nm`)
- **RPM signing**: Sign packages for production releases
- **Multi-version builds**: Build for specific Fedora versions if needed (currently builds for latest)
- **Debian packages**: Create `.deb` packages for Debian/Ubuntu users
- **PyPI release**: Publish to PyPI for easier pip installation

## Testing Checklist

- [ ] RPM builds successfully in GitHub Actions
- [ ] RPM installs on Fedora Workstation
- [ ] RPM installs on Aurora/Bluefin (rpm-ostree)
- [ ] All dependencies are automatically installed
- [ ] Systemd units are installed correctly
- [ ] `pia-nm` command works after installation
- [ ] pip installation works on Debian/Ubuntu
- [ ] pip installation works on Fedora
- [ ] Documentation is accurate and complete

## References

- ProtonVPN RPM spec: `reference-repos/protonvpn-nm/rpmbuild/SPECS/package.spec.template`
- RPM Packaging Guide: https://rpm-packaging-guide.github.io/
- Fedora Packaging Guidelines: https://docs.fedoraproject.org/en-US/packaging-guidelines/
