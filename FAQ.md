# Frequently Asked Questions (FAQ)

## General Questions

### Why do I need pia-nm if PIA has an official client?

The official PIA client doesn't work on immutable Linux distributions (Aurora, Bluefin, Silverblue) because they don't support traditional package installation. pia-nm integrates with NetworkManager instead, giving you native Linux VPN management without needing to install the official client.

### Does pia-nm work on non-immutable distributions?

Yes! pia-nm works on any Linux distribution with NetworkManager and systemd, including standard Fedora, Ubuntu, Debian, and others. It's not limited to immutable distributions.

### Is pia-nm affiliated with Private Internet Access?

No, pia-nm is a community project. It's not affiliated with or endorsed by Private Internet Access, but it uses their public API. It's an independent tool created to solve a specific problem on immutable Linux distributions.

### Can I use pia-nm with other VPN tools?

Yes, pia-nm only manages PIA profiles in NetworkManager. You can have other VPN profiles (OpenVPN, other WireGuard, etc.) alongside pia-nm profiles. NetworkManager handles all of them.

### Is pia-nm open source?

Yes, pia-nm is open source. You can review the code on GitHub to verify security practices and understand how it works.

## Setup & Configuration

### How often are tokens refreshed?

Tokens refresh automatically every 12 hours via systemd timer. The first refresh happens 5 minutes after system boot, then every 12 hours after that.

### Can I manually refresh tokens?

Yes, run `pia-nm refresh` anytime to manually refresh all regions or `pia-nm refresh --region <id>` for a specific region.

### What happens if I don't run the refresh?

Tokens officially expire after 24 hours, but empirically they last much longer (weeks to months). If a token expires, the connection will fail and you'll need to manually refresh or wait for the next scheduled refresh.

### Can I add or remove regions after initial setup?

Yes, use `pia-nm add-region <id>` and `pia-nm remove-region <id>` to manage regions anytime. You don't need to run setup again.

### Where are my credentials stored?

Credentials are stored in your system keyring (via the Python keyring library), never in plaintext files. This is the same secure storage used by other applications like Firefox, Chrome, and GNOME.

### Can I change my PIA password?

Yes, change your password at https://www.privateinternetaccess.com/pages/login, then run `pia-nm setup` again to update the stored credentials.

### How many regions can I configure?

You can configure as many regions as you want. Each region gets its own NetworkManager profile and WireGuard keypair.

### Can I configure pia-nm without the interactive setup?

Currently, setup is interactive. You can manually edit `~/.config/pia-nm/config.yaml` after setup, but the initial setup wizard is the recommended way to configure pia-nm.

## Connections & Usage

### How do I connect to a VPN region?

Use NetworkManager GUI (GNOME Settings, KDE Network Manager) or CLI:

```bash
nmcli connection up PIA-US-East
```

Or use the GUI to select the connection.

### Will my connection drop during token refresh?

No, pia-nm uses `nmcli connection modify` which updates profiles without disconnecting active connections. Your VPN will continue working seamlessly during refresh.

### Can I have multiple regions connected simultaneously?

No, NetworkManager only allows one active connection at a time. You can switch between regions by disconnecting one and connecting another.

### How do I check which region I'm connected to?

Use:
```bash
nmcli connection show --active
```

Or check your system settings GUI.

### Can I set a region to auto-connect?

Yes, you can configure auto-connect in NetworkManager settings:

```bash
nmcli connection modify PIA-US-East connection.autoconnect yes
```

However, this is not recommended as it may interfere with other connections.

### How do I disconnect from a VPN?

Use:
```bash
nmcli connection down PIA-US-East
```

Or use the NetworkManager GUI to disconnect.

### Can I use pia-nm on a laptop that moves between networks?

Yes, pia-nm works great on laptops. The VPN profiles will work on any network (WiFi, Ethernet, mobile hotspot, etc.).

## Security & Privacy

### Are my credentials logged?

No, credentials are never logged. The tool logs operations but filters out all sensitive data (passwords, tokens, keys).

### Are my WireGuard keys secure?

Yes, private keys are stored with 0600 permissions (user only) and are never logged or transmitted except to PIA's API over HTTPS.

### Does pia-nm collect any data?

No, pia-nm only communicates with PIA's API to authenticate and register keys. It doesn't collect or send any data to third parties.

### Can I audit the code?

Yes, the code is open source on GitHub. You can review it to verify security practices.

### Does pia-nm use HTTPS for API calls?

Yes, all communication with PIA's API uses HTTPS with certificate validation enabled.

### What if someone gains access to my computer?

If someone gains root access, they could potentially access your credentials from the keyring. However, pia-nm follows standard Linux security practices. Your credentials are as secure as any other application that uses the system keyring.

### Does pia-nm work with VPN kill switches?

pia-nm doesn't implement a kill switch itself, but you can use NetworkManager's built-in features or third-party tools like `ufw` to create a kill switch.

### Can I use pia-nm with a proxy?

Currently, pia-nm doesn't support proxies. It connects directly to PIA's API and WireGuard servers.

## Troubleshooting

### What if I forget my PIA password?

Reset it at https://www.privateinternetaccess.com/pages/login, then run `pia-nm setup` again to update credentials.

### How do I uninstall pia-nm?

Run `pia-nm uninstall` to remove all profiles, systemd units, and configuration. Then uninstall the Python package:

```bash
pip uninstall pia-nm
```

### Can I disable automatic refresh?

Yes, run `pia-nm disable` to stop the systemd timer. You can still manually refresh with `pia-nm refresh`. Re-enable with `pia-nm enable`.

### What if a profile gets corrupted?

Remove and recreate it:

```bash
pia-nm remove-region <region-id>
pia-nm add-region <region-id>
```

### How do I see what's happening during refresh?

View logs in real-time:

```bash
tail -f ~/.local/share/pia-nm/logs/pia-nm.log
journalctl --user -u pia-nm-refresh.service -f
```

### What if the timer doesn't run?

Check timer status:

```bash
systemctl --user status pia-nm-refresh.timer
systemctl --user list-timers pia-nm-refresh.timer
```

Enable it if needed:

```bash
systemctl --user enable --now pia-nm-refresh.timer
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for more detailed solutions.

## Performance & Compatibility

### Does pia-nm slow down my system?

No, pia-nm only runs during token refresh (every 12 hours) and uses minimal resources. It doesn't run continuously in the background.

### What Python version do I need?

Python 3.9 or later. Most modern distributions have this by default.

### Does pia-nm work with IPv6?

Currently, IPv6 is disabled by default for privacy. Full IPv6 support is planned for a future version.

### What are the system requirements?

- Linux distribution with NetworkManager and systemd
- Python 3.9 or later
- WireGuard tools
- Active PIA subscription

### Does pia-nm work on Raspberry Pi?

Yes, if it has a compatible Linux distribution with NetworkManager and Python 3.9+. However, Raspberry Pi OS (Debian-based) uses different package managers, so installation may differ.

### Does pia-nm work on WSL (Windows Subsystem for Linux)?

WSL doesn't have NetworkManager by default, so pia-nm won't work on WSL. It's designed for native Linux systems.

### Can I use pia-nm on a server?

Yes, pia-nm works on servers with NetworkManager and systemd. However, servers typically don't use NetworkManager, so you'd need to set it up first.

### Does pia-nm work with SELinux or AppArmor?

pia-nm should work with SELinux and AppArmor, but you may need to adjust policies if you encounter permission issues. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for details.

## Development & Contributing

### Can I contribute to pia-nm?

Yes! Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### How do I report a bug?

Open an issue on GitHub with:
- Error message (exact text)
- Relevant log lines
- System information (OS, Python version, etc.)
- Steps to reproduce
- What you've already tried

### How do I request a feature?

Open an issue on GitHub describing:
- What you want to do
- Why you need it
- How you'd like it to work

### Can I fork and modify pia-nm?

Yes, pia-nm is open source under the MIT License. You can fork, modify, and distribute it according to the license terms.

### What's the roadmap for pia-nm?

See the GitHub repository for planned features and milestones. Current plans include:
- IPv6 support
- Port forwarding support
- GUI application (?)
- PEX packaging for easier distribution

## Miscellaneous

### Why is it called pia-nm?

**pia** = Private Internet Access  
**nm** = NetworkManager

### How often is pia-nm updated?

Updates are released as needed for bug fixes and new features. Check GitHub for the latest version.

### What license is pia-nm under?

pia-nm is licensed under the MIT License. See the LICENSE file for details.

### Where can I get help?

- Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues
- Read [COMMANDS.md](COMMANDS.md) for command documentation
- Open an issue on GitHub
- Check existing GitHub issues for similar problems

### Can I use pia-nm commercially?

Yes, the MIT License allows commercial use. See the LICENSE file for details.

### Is pia-nm affiliated with any Linux distribution?

No, pia-nm is a community project. It's not affiliated with any Linux distribution, though it's designed with immutable distributions in mind.

### What if I have a question not answered here?

Open an issue on GitHub or check the existing issues. The community is happy to help!
