%define name pia-nm
%define version 0.1.0
%define release 1

Name:           %{name}
Version:        %{version}
Release:        %{release}%{?dist}
Summary:        Automated WireGuard token refresh for Private Internet Access VPN in NetworkManager

License:        GPLv3
URL:            https://github.com/abirkel/pia-nm
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel

Requires:       python3 >= 3.9
Requires:       python3-requests >= 2.31.0
Requires:       python3-keyring >= 24.0.0
Requires:       python3-pyyaml >= 6.0
Requires:       python3-gobject >= 3.42.0
Requires:       NetworkManager >= 1.16
Requires:       wireguard-tools
Requires:       systemd
Requires:       curl

%description
PIA-NM is a Python-based automation tool that maintains fresh WireGuard
connection profiles for Private Internet Access (PIA) VPN in NetworkManager.

It solves the problem of PIA's 24-hour token expiration by automatically
refreshing tokens via systemd timer, allowing users to maintain multiple
region profiles with native Linux VPN integration.

Features:
- Automatic token refresh every 12 hours
- Multiple region support
- NetworkManager integration (GUI, system settings)
- Systemd timer for background automation
- Secure credential storage via system keyring

%prep
%autosetup -n %{name}-%{version}

%build
%pyproject_wheel

%check
# Tests require NetworkManager D-Bus which isn't available in build environment
# Tests are run during development and CI

%install
%pyproject_install
%pyproject_save_files pia_nm

# Install systemd user units
mkdir -p %{buildroot}%{_userunitdir}
cat > %{buildroot}%{_userunitdir}/pia-nm-refresh.service << 'EOF'
[Unit]
Description=PIA WireGuard Token Refresh
Documentation=https://github.com/abirkel/pia-nm
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=%{_bindir}/pia-nm refresh
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pia-nm-refresh
PrivateTmp=true
NoNewPrivileges=true
EOF

cat > %{buildroot}%{_userunitdir}/pia-nm-refresh.timer << 'EOF'
[Unit]
Description=PIA WireGuard Token Refresh Timer
Documentation=https://github.com/abirkel/pia-nm

[Timer]
OnBootSec=5min
OnUnitActiveSec=12h
Persistent=true

[Install]
WantedBy=timers.target
EOF

%pre
# Pre-install: Nothing needed currently

%post
# Post-install: Inform user about setup
if [ "$1" -eq 1 ]; then
    # First install
    echo "pia-nm installed successfully!"
    echo "Run 'pia-nm setup' to configure your PIA VPN connections."
fi

%preun
# Pre-uninstall: Stop and disable timer before removing files
if [ "$1" -eq 0 ]; then
    # Complete uninstall (not upgrade)
    # Stop and disable the systemd timer for all users
    for user_home in /home/*; do
        if [ -d "$user_home" ]; then
            username=$(basename "$user_home")
            # Try to stop/disable timer as each user
            runuser -u "$username" -- systemctl --user disable --now pia-nm-refresh.timer 2>/dev/null || true
            runuser -u "$username" -- systemctl --user stop pia-nm-refresh.service 2>/dev/null || true
        fi
    done
    
    # Also try for root user
    systemctl --user disable --now pia-nm-refresh.timer 2>/dev/null || true
    systemctl --user stop pia-nm-refresh.service 2>/dev/null || true
fi

%postun
# Post-uninstall: Clean up user data and NetworkManager connections
if [ "$1" -eq 0 ]; then
    # Complete uninstall (not upgrade)
    
    # Remove NetworkManager PIA connections for all users
    for conn_file in /etc/NetworkManager/system-connections/PIA-*.nmconnection; do
        if [ -f "$conn_file" ]; then
            rm -f "$conn_file" 2>/dev/null || true
        fi
    done
    
    # Reload NetworkManager to pick up connection deletions
    systemctl reload NetworkManager 2>/dev/null || true
    
    # Clean up user configuration and data directories
    for user_home in /home/*; do
        if [ -d "$user_home" ]; then
            username=$(basename "$user_home")
            
            # Remove config directory
            if [ -d "$user_home/.config/pia-nm" ]; then
                rm -rf "$user_home/.config/pia-nm" 2>/dev/null || true
            fi
            
            # Remove data/logs directory
            if [ -d "$user_home/.local/share/pia-nm" ]; then
                rm -rf "$user_home/.local/share/pia-nm" 2>/dev/null || true
            fi
            
            # Remove systemd user units (in case they exist from pip install)
            rm -f "$user_home/.config/systemd/user/pia-nm-refresh.service" 2>/dev/null || true
            rm -f "$user_home/.config/systemd/user/pia-nm-refresh.timer" 2>/dev/null || true
            
            # Reload systemd user daemon
            runuser -u "$username" -- systemctl --user daemon-reload 2>/dev/null || true
            
            # Note: We don't automatically delete keyring credentials for security reasons
            # Users should manually clear if desired using:
            # python3 -c "import keyring; keyring.delete_password('pia-nm', 'username'); keyring.delete_password('pia-nm', 'password')"
        fi
    done
    
    # Also clean up for root user
    rm -rf /root/.config/pia-nm 2>/dev/null || true
    rm -rf /root/.local/share/pia-nm 2>/dev/null || true
    
    echo "pia-nm has been uninstalled."
    echo "Note: Keyring credentials were NOT automatically deleted for security."
    echo "To manually clear credentials, run:"
    echo "  python3 -c \"import keyring; keyring.delete_password('pia-nm', 'username'); keyring.delete_password('pia-nm', 'password')\""
fi

%files -f %{pyproject_files}
%license LICENSE
%doc README.md INSTALL.md COMMANDS.md TROUBLESHOOTING.md
%{_bindir}/pia-nm
%{_userunitdir}/pia-nm-refresh.service
%{_userunitdir}/pia-nm-refresh.timer

%changelog
* Sat Nov 29 2025 PIA-NM Contributors <pia-nm@example.com> - 0.1.0-1
- Initial RPM release
- Automated WireGuard token refresh for PIA VPN
- NetworkManager integration with D-Bus support
- Systemd timer for background automation
- Multi-region support
- Secure credential storage via keyring
