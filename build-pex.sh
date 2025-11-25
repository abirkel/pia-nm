#!/bin/bash
# Build script for creating PEX executable
# This is for local development only - GitHub Actions builds releases automatically

set -e

echo "Building pia-nm PEX executable..."
echo "Note: Regular users should download pre-built releases from GitHub"
echo ""

# Check if pex is installed
if ! command -v pex &> /dev/null; then
    echo "Error: pex is not installed"
    echo ""
    echo "For development, install pex in a toolbox:"
    echo "  toolbox create -c dev"
    echo "  toolbox enter dev"
    echo "  pip install pex"
    echo "  make pex"
    exit 1
fi

# Clean previous builds
rm -f pia-nm.pex
rm -rf build/ dist/ *.egg-info

# Build the PEX file
pex . \
    --requirement <(echo "requests>=2.31.0"; echo "keyring>=24.0.0"; echo "PyYAML>=6.0") \
    --console-script pia-nm \
    --output-file pia-nm.pex \
    --python-shebang "/usr/bin/env python3"

# Make it executable
chmod +x pia-nm.pex

echo "✓ Build complete: pia-nm.pex"
echo ""
echo "Test it with: ./pia-nm.pex --help"
echo "Install it with: cp pia-nm.pex ~/.local/bin/pia-nm"
