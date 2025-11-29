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
