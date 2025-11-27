# Attribution and Acknowledgments

## ProtonVPN NetworkManager Integration

This project adapts D-Bus integration patterns and code from ProtonVPN's **python-proton-vpn-network-manager** library.

### Repository Information

- **Project**: ProtonVPN NetworkManager Integration
- **Repository**: https://github.com/ProtonVPN/python-proton-vpn-network-manager
- **License**: GNU General Public License v3.0 (GPLv3)
- **Copyright**: © 2023 Proton AG

### Code Reuse

The following modules in pia-nm contain code adapted from ProtonVPN:

#### `pia_nm/dbus_client.py`

Adapted from ProtonVPN's NetworkManager D-Bus client implementation:
- **Source Files**: 
  - `proton/vpn/connection/vpnconnection.py`
  - `proton/vpn/connection/vpnconnector.py`
- **Adapted Components**:
  - NM.Client singleton initialization
  - GLib MainLoop management in daemon thread
  - Thread-safe D-Bus operation execution
  - Callback-to-Future bridge for async operations
  - Connection lifecycle management (add, activate, remove)
  - Active connection querying

**Key Adaptations**:
- Simplified by removing ProtonVPN-specific features (account management, server selection UI, kill switch)
- Adapted for PIA's API response format
- Integrated with pia-nm's existing configuration and logging systems
- Added PIA-specific connection naming and management

#### `pia_nm/wireguard_connection.py`

Adapted from ProtonVPN's WireGuard connection builder:
- **Source Files**: 
  - `proton/vpn/connection/vpnconnection.py` (WireGuard connection creation methods)
- **Adapted Components**:
  - NM.SimpleConnection creation with WireGuard settings
  - NM.WireGuardPeer configuration (public key, endpoint, allowed-ips, keepalive)
  - NM.SettingWireGuard setup with peer management
  - IPv4 configuration (manual addressing, DNS, routing)
  - IPv6 configuration (disabled by default)
  - Connection validation before adding to NetworkManager

**Key Adaptations**:
- Adapted for PIA's WireGuard configuration format
- Simplified DNS configuration for PIA's DNS servers
- Removed ProtonVPN-specific features (NetShield, split tunneling UI)
- Added PIA-specific interface naming conventions

#### `pia_nm/token_refresh.py`

Adapted from ProtonVPN's connection update logic:
- **Source Files**: 
  - `proton/vpn/connection/vpnconnection.py` (connection update methods)
- **Adapted Components**:
  - GetAppliedConnection D-Bus call for active connections
  - Reapply method for live credential updates
  - Update2 method for saved profile updates
  - Active connection detection and preservation

**Key Adaptations**:
- Integrated with PIA's token refresh workflow
- Adapted for PIA's credential format (private key + endpoint)
- Added logging for live vs. saved updates
- Simplified to focus on token refresh use case

### Why ProtonVPN's Code?

ProtonVPN's NetworkManager integration is:
- **Production-tested**: Used by thousands of ProtonVPN users daily
- **Mature**: Well-established codebase with proven reliability
- **Well-architected**: Clean separation of concerns, proper thread safety
- **Comprehensive**: Handles edge cases and error conditions thoroughly

Rather than reimplementing NetworkManager D-Bus integration from scratch, we adapted ProtonVPN's proven patterns to PIA's needs. This approach:
- Reduces development time and potential bugs
- Leverages battle-tested code
- Benefits from ProtonVPN's experience with NetworkManager quirks
- Maintains high code quality standards

### License Compatibility

**IMPORTANT LICENSE ISSUE**:

- **ProtonVPN**: GNU General Public License v3.0 (GPLv3)
- **pia-nm**: MIT License

**This is a licensing conflict.** MIT and GPLv3 are NOT compatible. GPLv3 is a copyleft license that requires any derivative work to also be licensed under GPLv3. Since pia-nm adapts code from ProtonVPN's GPLv3-licensed project, pia-nm must also be licensed under GPLv3.

**Required Action**: The pia-nm project license must be changed from MIT to GPLv3 to comply with ProtonVPN's license terms. This affects:
- LICENSE file (must be changed to GPLv3)
- All source file headers (must include GPLv3 notice)
- README.md (must state GPLv3 license)
- Any documentation referencing the license

**Alternative**: If maintaining MIT license is required, all ProtonVPN-adapted code must be removed and D-Bus integration must be reimplemented from scratch using only NetworkManager documentation and examples.

### Copyright Notices

The following copyright notices apply to adapted code:

```
Copyright (C) 2023 Proton AG

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
```

### Changes Made

All adapted code includes comments indicating:
1. Original source from ProtonVPN
2. Specific adaptations made for pia-nm
3. ProtonVPN copyright notice

Example:
```python
"""
NetworkManager D-Bus client for PIA WireGuard connections.

Adapted from ProtonVPN's python-proton-vpn-network-manager:
https://github.com/ProtonVPN/python-proton-vpn-network-manager

Original Copyright (C) 2023 Proton AG
Licensed under GPLv3

Adaptations for pia-nm:
- Simplified by removing ProtonVPN-specific features
- Adapted for PIA's API response format
- Integrated with pia-nm configuration system
"""
```

## Other Acknowledgments

### NetworkManager

- **Project**: NetworkManager
- **Website**: https://networkmanager.dev/
- **License**: GNU General Public License v2.0 or later
- **Usage**: pia-nm uses NetworkManager's D-Bus API via PyGObject

### PyGObject

- **Project**: PyGObject (Python GObject Introspection)
- **Website**: https://pygobject.readthedocs.io/
- **License**: GNU Lesser General Public License v2.1 or later
- **Usage**: Python bindings for GObject introspection, enabling D-Bus access

### WireGuard

- **Project**: WireGuard VPN Protocol
- **Website**: https://www.wireguard.com/
- **License**: GNU General Public License v2.0
- **Usage**: VPN protocol used by PIA and configured by pia-nm

### Private Internet Access

- **Company**: Private Internet Access (Kape Technologies)
- **Website**: https://www.privateinternetaccess.com/
- **Usage**: VPN service provider; pia-nm automates their WireGuard configuration

**Note**: pia-nm is not affiliated with or endorsed by Private Internet Access. It is an independent community project.

## Contributing

If you contribute code to pia-nm that adapts patterns from other open-source projects:

1. Ensure license compatibility (GPLv3-compatible licenses)
2. Include proper attribution in code comments
3. Update this ATTRIBUTION.md file
4. Maintain original copyright notices
5. Document specific adaptations made

## Questions?

For questions about attribution, licensing, or code reuse:
- Open an issue on GitHub
- Review the LICENSE file
- Consult the GPLv3 license text: https://www.gnu.org/licenses/gpl-3.0.html

---

**Last Updated**: November 2025
