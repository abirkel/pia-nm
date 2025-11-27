# Attribution

## ProtonVPN NetworkManager Integration

This project adapts D-Bus integration patterns from ProtonVPN's [python-proton-vpn-network-manager](https://github.com/ProtonVPN/python-proton-vpn-network-manager) library.

- **License**: GNU General Public License v3.0 (GPLv3)
- **Copyright**: © 2023 Proton AG

### Adapted Modules

The following pia-nm modules contain code adapted from ProtonVPN:

- `pia_nm/dbus_client.py` - D-Bus client implementation, GLib MainLoop management, thread-safe operations
- `pia_nm/wireguard_connection.py` - WireGuard connection builder, NetworkManager settings configuration
- `pia_nm/token_refresh.py` - Connection update logic, live credential refresh

Each adapted file includes detailed attribution comments with original source references and specific adaptations made for PIA.

### Why ProtonVPN's Code?

ProtonVPN's NetworkManager integration is production-tested, mature, and well-architected. Rather than reimplementing D-Bus integration from scratch, we adapted their proven patterns to PIA's needs, reducing bugs and leveraging their experience with NetworkManager.

## Other Acknowledgments

- **NetworkManager** - D-Bus API for VPN management
- **PyGObject** - Python GObject introspection bindings
- **WireGuard** - VPN protocol
- **Private Internet Access** - VPN service provider (not affiliated with this project)
