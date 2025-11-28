# NetworkManager DBus Implementation Analysis

**Date**: November 27, 2025  
**Purpose**: Analyze ProtonVPN and Mullvad reference implementations for proper WireGuard profile creation via NetworkManager's DBus API

---

## Executive Summary

After examining both ProtonVPN (Python) and Mullvad (Rust) implementations, it's clear that:

1. **nmcli is insufficient** for WireGuard profile creation - it cannot properly configure peers, allowed-ips, or routing
2. **DBus API is the only reliable method** for programmatic NetworkManager WireGuard configuration
3. **Both mature VPN clients use DBus exclusively** for WireGuard profile management
4. **Python has excellent DBus support** via PyGObject (gi.repository.NM)

---

## Key Findings

### 1. ProtonVPN Implementation (Python + PyGObject)

**Library Used**: `PyGObject` with `gi.repository.NM` (NetworkManager GObject introspection)

**Architecture**:
- Uses GLib MainLoop for async DBus operations
- Thread-safe callback system with Futures
- Native NetworkManager types (NM.SimpleConnection, NM.WireGuardPeer, etc.)

**Critical Code Pattern**:
```python
import gi
gi.require_version("NM", "1.0")
from gi.repository import NM

# Create connection object
connection = NM.SimpleConnection.new()
connection_settings = NM.SettingConnection.new()

# Configure WireGuard peer
peer = NM.WireGuardPeer.new()
peer.set_public_key(server_pubkey, False)
peer.set_endpoint(f"{server_ip}:{port}", False)
peer.append_allowed_ip("0.0.0.0/0", False)  # Default route
peer.seal()  # Make immutable
peer.is_valid(True, True)  # Validate

# Add WireGuard settings
wireguard_config = NM.SettingWireGuard.new()
wireguard_config.append_peer(peer)
wireguard_config.set_property(NM.SETTING_WIREGUARD_PRIVATE_KEY, private_key)
wireguard_config.set_property(NM.SETTING_WIREGUARD_FWMARK, fwmark)

connection.add_setting(wireguard_config)

# Add connection via DBus
nm_client.add_connection_async(connection)
```

**Routing Configuration**:
```python
# IPv4 configuration
ipv4_config = NM.SettingIP4Config.new()
ipv4_config.set_property(NM.SETTING_IP_CONFIG_METHOD, NM.SETTING_IP4_CONFIG_METHOD_MANUAL)
ipv4_config.add_address(
    NM.IPAddress.new(socket.AF_INET, "10.2.0.2", 32)
)

# DNS configuration
ipv4_config.set_property(NM.SETTING_IP_CONFIG_DNS_PRIORITY, -1500)
ipv4_config.set_property(NM.SETTING_IP_CONFIG_IGNORE_AUTO_DNS, True)
ipv4_config.add_dns("10.2.0.1")
ipv4_config.add_dns_search("~")  # Route all DNS through VPN

connection.add_setting(ipv4_config)
```

**Key Insights**:
- ✅ Full control over peer configuration (endpoint, allowed-ips, keepalive)
- ✅ Proper routing via allowed-ips="0.0.0.0/0" on peer
- ✅ DNS priority control (-1500 ensures VPN DNS takes precedence)
- ✅ Connection verification before activation
- ✅ Async operations with proper error handling

---

### 2. Mullvad Implementation (Rust + dbus-rs)

**Library Used**: `dbus` crate with manual DBus method calls

**Architecture**:
- Direct DBus proxy calls to NetworkManager
- Type-safe HashMap-based configuration
- Manual connection lifecycle management

**Critical Code Pattern**:
```rust
// Create connection via AddConnection2
let config: DeviceConfig = HashMap::new();
// config is HashMap<String, HashMap<String, Variant<Box<dyn RefArg>>>>

let (config_path, _): (dbus::Path, DeviceConfig) = 
    proxy.method_call(
        "org.freedesktop.NetworkManager.Settings",
        "AddConnection2",
        (config, NM_ADD_CONNECTION_VOLATILE, args)
    )?;

// Activate connection
let (connection_path,): (dbus::Path,) = 
    manager.method_call(
        "org.freedesktop.NetworkManager",
        "ActivateConnection",
        (config_path, device_path, specific_object)
    )?;
```

**DNS Management**:
```rust
// Fetch current device config
let (mut settings, version_id): (NetworkSettings, u64) =
    device.method_call("GetAppliedConnection", (0u32,))?;

// Update DNS settings
if let Some(ipv4_settings) = settings.get_mut("ipv4") {
    ipv4_settings.insert("dns-priority", Variant(Box::new(-2147483647i32)));
    ipv4_settings.insert("dns", Variant(Box::new(dns_servers)));
    ipv4_settings.insert("route-metric", Variant(Box::new(0u32)));
}

// Reapply settings
device.method_call("Reapply", (settings, version_id, 0u32))?;
```

**Key Insights**:
- ✅ Uses `AddConnection2` with `NM_ADD_CONNECTION_VOLATILE` flag (no disk persistence)
- ✅ Waits for device to reach ready state before proceeding
- ✅ Uses `GetAppliedConnection` + `Reapply` for live updates
- ✅ Preserves existing routes when updating DNS
- ✅ Handles NetworkManager version compatibility (1.16+ required for WireGuard)

---

## Comparison: nmcli vs DBus API

| Feature | nmcli | DBus API |
|---------|-------|----------|
| Create WireGuard connection | ✅ Basic | ✅ Full control |
| Add WireGuard peers | ❌ **Cannot** | ✅ Yes |
| Configure peer allowed-ips | ❌ **Cannot** | ✅ Yes |
| Set peer endpoint | ❌ **Cannot** | ✅ Yes |
| Configure keepalive | ❌ **Cannot** | ✅ Yes |
| Set DNS priority | ⚠️ Limited | ✅ Full control |
| Route management | ⚠️ Buggy | ✅ Reliable |
| Live config updates | ❌ No | ✅ Reapply method |
| Error handling | ⚠️ Parse stderr | ✅ Typed exceptions |
| Async operations | ❌ No | ✅ Yes |

**Verdict**: nmcli is fundamentally incomplete for WireGuard. DBus is required.

---

## Recommended Implementation for pia-nm

### Architecture Decision

**Use PyGObject (gi.repository.NM)** - Same as ProtonVPN

**Reasons**:
1. Native Python bindings (no subprocess calls)
2. Type-safe NetworkManager objects
3. Async support with GLib MainLoop
4. Excellent documentation and examples
5. Already proven in production (ProtonVPN)
6. Simpler than manual DBus calls

### Dependencies

```toml
[project.dependencies]
PyGObject = ">=3.42.0"  # Provides gi.repository.NM
```

**System Requirements**:
- `gir1.2-nm-1.0` (NetworkManager GObject introspection)
- NetworkManager 1.16+ (for native WireGuard support)

### Module Structure

```
pia_nm/
├── dbus_client.py          # NMClient wrapper (GLib MainLoop management)
├── wireguard_connection.py # WireGuard connection builder
├── network_manager.py      # High-level NM operations (DEPRECATED/REMOVED)
└── cli.py                  # CLI interface
```

---

## Implementation Plan

### Phase 1: Replace network_manager.py with dbus_client.py

Create new `dbus_client.py` based on ProtonVPN's nmclient.py:

```python
import gi
gi.require_version("NM", "1.0")
from gi.repository import NM, GLib
from concurrent.futures import Future
from threading import Thread, Lock

class NMClient:
    """NetworkManager DBus client with GLib MainLoop."""
    
    _lock = Lock()
    _main_context = None
    _nm_client = None
    
    @classmethod
    def initialize(cls):
        """Initialize NM client singleton with GLib MainLoop."""
        if cls._nm_client:
            return
        
        with cls._lock:
            if not cls._nm_client:
                cls._main_context = GLib.MainContext()
                cls._nm_client = NM.Client()
                Thread(target=cls._run_main_loop, daemon=True).start()
                
                # Async initialization
                callback, future = cls.create_callback("new_finish")
                cls._run_on_main_loop(
                    lambda: cls._nm_client.new_async(
                        cancellable=None, 
                        callback=callback, 
                        user_data=None
                    )
                )
                cls._nm_client = future.result()
    
    @classmethod
    def _run_main_loop(cls):
        main_loop = GLib.MainLoop(cls._main_context)
        cls._main_context.push_thread_default()
        main_loop.run()
    
    @classmethod
    def _run_on_main_loop(cls, function):
        cls._main_context.invoke_full(
            priority=GLib.PRIORITY_DEFAULT, 
            function=function
        )
    
    @classmethod
    def create_callback(cls, finish_method_name: str):
        """Create callback and Future for async operations."""
        future = Future()
        future.set_running_or_notify_cancel()
        
        def callback(source_object, res, userdata):
            try:
                if not source_object or not res:
                    raise Exception("DBus call failed")
                
                result = getattr(source_object, finish_method_name)(res)
                if not result:
                    raise Exception("Operation returned None")
                
                future.set_result(result)
            except Exception as exc:
                future.set_exception(exc)
        
        return callback, future
    
    def add_connection_async(self, connection: NM.Connection) -> Future:
        """Add connection asynchronously."""
        callback, future = self.create_callback("add_connection_finish")
        
        def add_connection():
            self._nm_client.add_connection_async(
                connection=connection,
                save_to_disk=False,  # Volatile connection
                cancellable=None,
                callback=callback,
                user_data=None
            )
        
        self._run_on_main_loop(add_connection)
        return future
    
    def activate_connection_async(self, connection: NM.Connection) -> Future:
        """Activate connection asynchronously."""
        callback, future = self.create_callback("activate_connection_finish")
        
        def activate():
            self._nm_client.activate_connection_async(
                connection, None, None, None, callback, None
            )
        
        self._run_on_main_loop(activate)
        return future
    
    def get_connection_by_uuid(self, uuid: str):
        """Get connection by UUID."""
        return self._nm_client.get_connection_by_uuid(uuid)
    
    def remove_connection_async(self, connection: NM.RemoteConnection) -> Future:
        """Remove connection asynchronously."""
        callback, future = self.create_callback("delete_finish")
        
        def delete():
            connection.delete_async(None, callback, None)
        
        self._run_on_main_loop(delete)
        return future
```

### Phase 2: Create wireguard_connection.py

```python
import gi
gi.require_version("NM", "1.0")
from gi.repository import NM
import socket
import uuid
from dataclasses import dataclass

@dataclass
class WireGuardConfig:
    """WireGuard connection configuration."""
    connection_name: str
    interface_name: str
    private_key: str
    server_pubkey: str
    server_endpoint: str  # "ip:port"
    peer_ip: str  # Client IP (e.g., "10.x.x.x")
    dns_servers: list[str]
    allowed_ips: str = "0.0.0.0/0"  # Default route
    persistent_keepalive: int = 25
    fwmark: int = 51820

def create_wireguard_connection(config: WireGuardConfig) -> NM.SimpleConnection:
    """Create a WireGuard connection using NetworkManager DBus API."""
    
    connection = NM.SimpleConnection.new()
    
    # 1. Connection settings
    conn_settings = NM.SettingConnection.new()
    conn_settings.set_property(NM.SETTING_CONNECTION_ID, config.connection_name)
    conn_settings.set_property(NM.SETTING_CONNECTION_UUID, str(uuid.uuid4()))
    conn_settings.set_property(NM.SETTING_CONNECTION_INTERFACE_NAME, config.interface_name)
    conn_settings.set_property(NM.SETTING_CONNECTION_TYPE, NM.SETTING_WIREGUARD_SETTING_NAME)
    conn_settings.set_property(NM.SETTING_CONNECTION_AUTOCONNECT, False)
    connection.add_setting(conn_settings)
    
    # 2. WireGuard settings
    wg_settings = NM.SettingWireGuard.new()
    wg_settings.set_property(NM.SETTING_WIREGUARD_PRIVATE_KEY, config.private_key)
    wg_settings.set_property(NM.SETTING_WIREGUARD_FWMARK, config.fwmark)
    
    # 3. WireGuard peer
    peer = NM.WireGuardPeer.new()
    peer.set_public_key(config.server_pubkey, False)
    peer.set_endpoint(config.server_endpoint, False)
    peer.append_allowed_ip(config.allowed_ips, False)  # THIS CREATES DEFAULT ROUTE
    peer.set_persistent_keepalive(config.persistent_keepalive, False)
    peer.seal()  # Make immutable
    
    if not peer.is_valid(True, True):
        raise ValueError("Invalid WireGuard peer configuration")
    
    wg_settings.append_peer(peer)
    connection.add_setting(wg_settings)
    
    # 4. IPv4 configuration
    ipv4_config = NM.SettingIP4Config.new()
    ipv4_config.set_property(NM.SETTING_IP_CONFIG_METHOD, NM.SETTING_IP4_CONFIG_METHOD_MANUAL)
    ipv4_config.add_address(NM.IPAddress.new(socket.AF_INET, config.peer_ip, 32))
    
    # DNS configuration
    ipv4_config.set_property(NM.SETTING_IP_CONFIG_DNS_PRIORITY, -1500)
    ipv4_config.set_property(NM.SETTING_IP_CONFIG_IGNORE_AUTO_DNS, True)
    for dns in config.dns_servers:
        ipv4_config.add_dns(dns)
    ipv4_config.add_dns_search("~")  # Route all DNS through VPN
    
    connection.add_setting(ipv4_config)
    
    # 5. IPv6 configuration (disabled)
    ipv6_config = NM.SettingIP6Config.new()
    ipv6_config.set_property(NM.SETTING_IP_CONFIG_METHOD, NM.SETTING_IP6_CONFIG_METHOD_DISABLED)
    connection.add_setting(ipv6_config)
    
    # 6. Verify connection
    if not connection.verify():
        raise ValueError("Connection verification failed")
    
    return connection
```

### Phase 3: Update cli.py

```python
import asyncio
from pia_nm.dbus_client import NMClient
from pia_nm.wireguard_connection import create_wireguard_connection, WireGuardConfig

async def setup_region(api_client, region_id: str):
    """Setup a region using DBus API."""
    
    # Initialize NM client
    NMClient.initialize()
    nm_client = NMClient()
    
    # Get PIA credentials and register key
    token = api_client.authenticate()
    private_key, public_key = load_or_generate_keypair(region_id)
    conn_details = api_client.register_key(token, public_key, region_id)
    
    # Create WireGuard connection
    config = WireGuardConfig(
        connection_name=f"PIA-{region_id}",
        interface_name=f"wg-pia-{region_id}",
        private_key=private_key,
        server_pubkey=conn_details["server_key"],
        server_endpoint=f"{conn_details['server_ip']}:{conn_details['server_port']}",
        peer_ip=conn_details["peer_ip"],
        dns_servers=conn_details["dns_servers"]
    )
    
    connection = create_wireguard_connection(config)
    
    # Add connection via DBus
    future = nm_client.add_connection_async(connection)
    loop = asyncio.get_running_loop()
    remote_connection = await loop.run_in_executor(None, future.result)
    
    logger.info(f"Created connection: {config.connection_name}")
    return remote_connection

def cmd_setup():
    """Setup command using async DBus."""
    asyncio.run(setup_wizard())

async def setup_wizard():
    # ... existing setup code ...
    
    for region_id in selected_regions:
        try:
            await setup_region(api_client, region_id)
            print(f"  ✓ {region_id} configured")
        except Exception as e:
            print(f"  ✗ {region_id} failed: {e}")
```

---

## Critical Implementation Details

### 1. Default Route via allowed-ips

The key to proper routing is setting `allowed-ips="0.0.0.0/0"` on the WireGuard peer:

```python
peer.append_allowed_ip("0.0.0.0/0", False)
```

This tells NetworkManager to route ALL traffic through the VPN. NetworkManager will:
- Create a default route via the WireGuard interface
- Add the route with appropriate metric
- Handle route conflicts automatically

**DO NOT** manually add routes via `ipv4_config.add_route()` - this causes conflicts.

### 2. DNS Priority

Set DNS priority to a very negative number to ensure VPN DNS takes precedence:

```python
ipv4_config.set_property(NM.SETTING_IP_CONFIG_DNS_PRIORITY, -1500)
```

NetworkManager uses DNS priority to order resolv.conf entries. Lower (more negative) = higher priority.

### 3. Connection Persistence

Use `save_to_disk=False` for volatile connections:

```python
nm_client.add_connection_async(
    connection=connection,
    save_to_disk=False,  # Don't persist to /etc/NetworkManager/system-connections/
    cancellable=None,
    callback=callback,
    user_data=None
)
```

This prevents cluttering the system with stale profiles.

### 4. Token Refresh Strategy

For token refresh, use `GetAppliedConnection` + `Reapply` pattern (Mullvad approach):

```python
# Get current connection
connection = nm_client.get_connection_by_uuid(uuid)
device_path = get_device_path_for_connection(connection)

# Get applied settings
device_proxy = create_device_proxy(device_path)
settings, version_id = device_proxy.GetAppliedConnection(0)

# Update WireGuard settings
settings["wireguard"]["private-key"] = new_private_key
settings["wireguard"]["peers"][0]["endpoint"] = new_endpoint

# Reapply without disconnecting
device_proxy.Reapply(settings, version_id, 0)
```

This updates the connection without dropping the tunnel.

---

## Testing Strategy

### Unit Tests

```python
def test_create_wireguard_connection():
    """Test connection creation."""
    config = WireGuardConfig(
        connection_name="Test-PIA",
        interface_name="wg-test",
        private_key="test_private_key",
        server_pubkey="test_server_key",
        server_endpoint="1.2.3.4:1337",
        peer_ip="10.0.0.1",
        dns_servers=["10.0.0.242"]
    )
    
    connection = create_wireguard_connection(config)
    
    # Verify connection properties
    assert connection.get_id() == "Test-PIA"
    
    # Verify WireGuard settings
    wg_settings = connection.get_setting_wireguard()
    assert wg_settings.get_private_key() == "test_private_key"
    
    # Verify peer configuration
    peer = wg_settings.get_peer(0)
    assert peer.get_public_key() == "test_server_key"
    assert peer.get_endpoint() == "1.2.3.4:1337"
    assert "0.0.0.0/0" in peer.get_allowed_ips()
```

### Integration Tests

```python
@pytest.mark.integration
async def test_full_connection_lifecycle():
    """Test creating, activating, and removing a connection."""
    NMClient.initialize()
    nm_client = NMClient()
    
    # Create connection
    config = WireGuardConfig(...)
    connection = create_wireguard_connection(config)
    
    # Add to NetworkManager
    future = nm_client.add_connection_async(connection)
    remote_connection = await asyncio.get_running_loop().run_in_executor(None, future.result)
    
    # Verify it exists
    uuid = remote_connection.get_uuid()
    assert nm_client.get_connection_by_uuid(uuid) is not None
    
    # Remove connection
    future = nm_client.remove_connection_async(remote_connection)
    await asyncio.get_running_loop().run_in_executor(None, future.result)
    
    # Verify removal
    assert nm_client.get_connection_by_uuid(uuid) is None
```

---

## Migration Path

### Step 1: Install Dependencies

```bash
# Debian/Ubuntu
sudo apt install python3-gi gir1.2-nm-1.0

# Fedora
sudo dnf install python3-gobject NetworkManager
```

### Step 2: Create New Modules

- Create `dbus_client.py`
- Create `wireguard_connection.py`
- Keep `network_manager.py` temporarily for comparison

### Step 3: Update CLI Commands

- Modify `cmd_setup()` to use new DBus approach
- Modify `cmd_refresh()` to use Reapply pattern
- Test thoroughly

### Step 4: Remove Old Code

- Delete `network_manager.py` (nmcli-based)
- Remove subprocess-based connection creation
- Update tests

### Step 5: Update Documentation

- Document DBus dependency
- Update installation instructions
- Add troubleshooting for GLib MainLoop issues

---

## Potential Issues and Solutions

### Issue 1: GLib MainLoop Thread Safety

**Problem**: GLib operations must run on MainLoop thread

**Solution**: Use `_run_on_main_loop()` wrapper for all NM operations

### Issue 2: Async/Await with GLib

**Problem**: GLib uses callbacks, Python uses async/await

**Solution**: Use `concurrent.futures.Future` as bridge (ProtonVPN pattern)

### Issue 3: Connection Not Becoming Active

**Problem**: Connection added but doesn't activate

**Solution**: Wait for device state to reach ACTIVATED (Mullvad pattern):

```python
def wait_for_device_ready(device_path, timeout=15):
    """Wait for device to reach ready state."""
    start = time.time()
    while time.time() - start < timeout:
        state = get_device_state(device_path)
        if state >= NM_DEVICE_STATE_ACTIVATED:
            return True
        time.sleep(0.5)
    return False
```

### Issue 4: DNS Not Working

**Problem**: DNS queries not going through VPN

**Solution**: Ensure DNS priority is set correctly and dns-search includes "~"

---

## Conclusion

**Recommendation**: Migrate pia-nm to use PyGObject (gi.repository.NM) for all NetworkManager operations.

**Benefits**:
- ✅ Proper WireGuard peer configuration
- ✅ Reliable routing via allowed-ips
- ✅ Live connection updates without disconnection
- ✅ Type-safe, well-documented API
- ✅ Proven in production (ProtonVPN, Mullvad)
- ✅ No subprocess parsing or error-prone nmcli commands

**Effort**: Medium (2-3 days)
- Day 1: Implement dbus_client.py and wireguard_connection.py
- Day 2: Update CLI commands and test
- Day 3: Integration testing and documentation

**Risk**: Low
- PyGObject is stable and well-maintained
- Pattern is proven by ProtonVPN
- Can keep old code temporarily for fallback

---

## References

1. python-proton-vpn-network-manager — the NetworkManager library used by ProtonVPN on Linux:
https://github.com/ProtonVPN/python-proton-vpn-network-manager
2. Mullvad VPN: https://github.com/mullvad/mullvad-vpn
3. NetworkManager DBus API: https://developer.gnome.org/NetworkManager/stable/
4. PyGObject Documentation: https://pygobject.readthedocs.io/
5. NetworkManager WireGuard Support: https://blogs.gnome.org/thaller/2019/03/15/wireguard-in-networkmanager/


---

## Appendix A: Optional Features

### Feature 1: Split Tunneling (Local Network Exclusion)

**Use Case**: Keep local network traffic (LAN, printers, file shares) on the physical interface while routing internet traffic through VPN.

**Implementation Approach**:

There are two methods to implement split tunneling:

#### Method 1: Exclude Local Subnets from allowed-ips (Recommended)

Instead of routing all traffic (`0.0.0.0/0`), explicitly route only non-RFC1918 ranges:

```python
def create_split_tunnel_allowed_ips() -> list[str]:
    """
    Generate allowed-ips that exclude private networks.
    
    Excludes:
    - 10.0.0.0/8 (RFC1918)
    - 172.16.0.0/12 (RFC1918)
    - 192.168.0.0/16 (RFC1918)
    - 169.254.0.0/16 (Link-local)
    - 224.0.0.0/4 (Multicast)
    """
    return [
        "0.0.0.0/5",      # 0.0.0.0 - 7.255.255.255
        "8.0.0.0/7",      # 8.0.0.0 - 9.255.255.255
        "11.0.0.0/8",     # 11.0.0.0 - 11.255.255.255
        "12.0.0.0/6",     # 12.0.0.0 - 15.255.255.255
        "16.0.0.0/4",     # 16.0.0.0 - 31.255.255.255
        "32.0.0.0/3",     # 32.0.0.0 - 63.255.255.255
        "64.0.0.0/2",     # 64.0.0.0 - 127.255.255.255
        "128.0.0.0/3",    # 128.0.0.0 - 159.255.255.255
        "160.0.0.0/5",    # 160.0.0.0 - 167.255.255.255
        "168.0.0.0/6",    # 168.0.0.0 - 171.255.255.255
        "172.0.0.0/12",   # 172.0.0.0 - 172.15.255.255
        "172.32.0.0/11",  # 172.32.0.0 - 172.63.255.255
        "172.64.0.0/10",  # 172.64.0.0 - 172.127.255.255
        "172.128.0.0/9",  # 172.128.0.0 - 172.255.255.255
        "173.0.0.0/8",    # 173.0.0.0 - 173.255.255.255
        "174.0.0.0/7",    # 174.0.0.0 - 175.255.255.255
        "176.0.0.0/4",    # 176.0.0.0 - 191.255.255.255
        "192.0.0.0/9",    # 192.0.0.0 - 192.127.255.255
        "192.128.0.0/11", # 192.128.0.0 - 192.159.255.255
        "192.160.0.0/13", # 192.160.0.0 - 192.167.255.255
        "192.169.0.0/16", # 192.169.0.0 - 192.169.255.255
        "192.170.0.0/15", # 192.170.0.0 - 192.171.255.255
        "192.172.0.0/14", # 192.172.0.0 - 192.175.255.255
        "192.176.0.0/12", # 192.176.0.0 - 192.191.255.255
        "192.192.0.0/10", # 192.192.0.0 - 192.255.255.255
        "193.0.0.0/8",    # 193.0.0.0 - 193.255.255.255
        "194.0.0.0/7",    # 194.0.0.0 - 195.255.255.255
        "196.0.0.0/6",    # 196.0.0.0 - 199.255.255.255
        "200.0.0.0/5",    # 200.0.0.0 - 207.255.255.255
        "208.0.0.0/4",    # 208.0.0.0 - 223.255.255.255
    ]

# Usage in wireguard_connection.py
def create_wireguard_connection(config: WireGuardConfig) -> NM.SimpleConnection:
    # ... existing code ...
    
    peer = NM.WireGuardPeer.new()
    peer.set_public_key(config.server_pubkey, False)
    peer.set_endpoint(config.server_endpoint, False)
    
    # Split tunnel: exclude private networks
    if config.split_tunnel:
        for allowed_ip in create_split_tunnel_allowed_ips():
            peer.append_allowed_ip(allowed_ip, False)
    else:
        # Full tunnel: route everything
        peer.append_allowed_ip("0.0.0.0/0", False)
    
    peer.set_persistent_keepalive(config.persistent_keepalive, False)
    peer.seal()
    
    # ... rest of code ...
```

#### Method 2: Route-Based Exclusion (Alternative)

Use full tunnel but add specific local routes with higher priority:

```python
def add_local_network_routes(ipv4_config: NM.SettingIP4Config):
    """Add routes for local networks with high priority (low metric)."""
    
    # Detect local network from default gateway
    import subprocess
    result = subprocess.run(
        ["ip", "route", "show", "default"],
        capture_output=True,
        text=True
    )
    # Parse: "default via 192.168.1.1 dev eth0"
    
    # Add local subnet route
    local_route = NM.IPRoute.new(
        family=socket.AF_INET,
        dest="192.168.1.0",  # Detected local network
        prefix=24,
        next_hop=None,  # Use interface's gateway
        metric=100  # Lower than VPN route
    )
    ipv4_config.add_route(local_route)
```

**Configuration**:

```yaml
# config.yaml
preferences:
  dns: true
  ipv6: false
  split_tunnel: false  # Set to true to exclude local networks
```

**Pros/Cons**:

| Method | Pros | Cons |
|--------|------|------|
| Method 1 (allowed-ips) | Clean, WireGuard-native, no route conflicts | Complex CIDR calculation |
| Method 2 (routes) | Simple, flexible | Requires detecting local network |

**Recommendation**: Use Method 1 (allowed-ips exclusion) - it's the WireGuard-native approach and more reliable.

---

### Feature 2: Optional VPN DNS

**Use Case**: Use system DNS instead of PIA's DNS servers (for split DNS setups, local DNS servers, or privacy preferences).

**Implementation**:

```python
@dataclass
class WireGuardConfig:
    """WireGuard connection configuration."""
    connection_name: str
    interface_name: str
    private_key: str
    server_pubkey: str
    server_endpoint: str
    peer_ip: str
    dns_servers: list[str]
    use_vpn_dns: bool = True  # NEW: Make DNS optional
    allowed_ips: str = "0.0.0.0/0"
    persistent_keepalive: int = 25
    fwmark: int = 51820

def create_wireguard_connection(config: WireGuardConfig) -> NM.SimpleConnection:
    # ... existing code ...
    
    # 4. IPv4 configuration
    ipv4_config = NM.SettingIP4Config.new()
    ipv4_config.set_property(NM.SETTING_IP_CONFIG_METHOD, NM.SETTING_IP4_CONFIG_METHOD_MANUAL)
    ipv4_config.add_address(NM.IPAddress.new(socket.AF_INET, config.peer_ip, 32))
    
    # DNS configuration (conditional)
    if config.use_vpn_dns:
        # Use PIA DNS servers
        ipv4_config.set_property(NM.SETTING_IP_CONFIG_DNS_PRIORITY, -1500)
        ipv4_config.set_property(NM.SETTING_IP_CONFIG_IGNORE_AUTO_DNS, True)
        for dns in config.dns_servers:
            ipv4_config.add_dns(dns)
        ipv4_config.add_dns_search("~")  # Route all DNS through VPN
        logger.info("Using VPN DNS servers: %s", config.dns_servers)
    else:
        # Use system DNS (don't override)
        ipv4_config.set_property(NM.SETTING_IP_CONFIG_IGNORE_AUTO_DNS, False)
        # Don't set DNS priority or servers - let NetworkManager use system defaults
        logger.info("Using system DNS (VPN DNS disabled)")
    
    connection.add_setting(ipv4_config)
    
    # ... rest of code ...
```

**Configuration**:

```yaml
# config.yaml
preferences:
  dns: true  # Set to false to use system DNS instead of PIA DNS
  ipv6: false
  split_tunnel: false
```

**CLI Support**:

```python
# cli.py
def cmd_setup():
    """Interactive setup wizard."""
    # ... existing code ...
    
    # Ask about DNS preference
    use_vpn_dns = input("Use PIA DNS servers? (Y/n): ").strip().lower()
    use_vpn_dns = use_vpn_dns != 'n'
    
    config.save({
        "regions": selected_ids,
        "preferences": {
            "dns": use_vpn_dns,
            "ipv6": False,
            "split_tunnel": False
        },
        # ...
    })
```

**Use Cases**:

1. **Local DNS Server**: User has Pi-hole or local DNS resolver
2. **Split DNS**: Corporate VPN requires local DNS for internal domains
3. **DNS Privacy**: User prefers their own DNS provider (Quad9, Cloudflare, etc.)
4. **Troubleshooting**: Isolate DNS issues from VPN connectivity

**Security Note**: 

When `use_vpn_dns=False`, DNS queries will leak outside the VPN tunnel. This may reveal browsing activity to the ISP. Document this clearly:

```python
if not config.use_vpn_dns:
    print("\n⚠️  WARNING: DNS queries will NOT go through the VPN")
    print("   Your ISP can see which domains you're accessing")
    print("   Only disable VPN DNS if you have a specific reason\n")
```

---

### Feature 3: Combined Configuration Example

**Full-featured config.yaml**:

```yaml
regions:
  - us-east
  - uk-london
  - jp-tokyo

preferences:
  # DNS Configuration
  dns: true              # Use PIA DNS (false = use system DNS)
  
  # IPv6 Support
  ipv6: false            # Enable IPv6 through VPN
  
  # Split Tunneling
  split_tunnel: false    # Exclude local networks from VPN
  
  # Port Forwarding (future feature)
  port_forwarding: false

metadata:
  version: 1
  last_refresh: "2025-11-27T10:30:00Z"
```

**CLI Commands**:

```bash
# Setup with custom preferences
pia-nm setup --no-vpn-dns --split-tunnel

# Change preferences after setup
pia-nm config set dns false
pia-nm config set split_tunnel true

# Show current configuration
pia-nm config show
```

**Implementation Priority**:

1. **Phase 1** (MVP): Basic DBus implementation with VPN DNS
2. **Phase 2** (v1.1): Add `use_vpn_dns` option
3. **Phase 3** (v1.2): Add `split_tunnel` option
4. **Phase 4** (v2.0): Port forwarding support

---

### Testing Split Tunnel and DNS Options

**Test Split Tunnel**:

```bash
# Enable split tunnel
pia-nm config set split_tunnel true
pia-nm refresh

# Connect to VPN
nmcli connection up PIA-US-East

# Test internet routing (should go through VPN)
curl -s https://ipinfo.io/ip
# Should show PIA server IP

# Test local network (should NOT go through VPN)
ping 192.168.1.1
# Should reach local gateway directly

# Verify routes
ip route show
# Should see specific routes for internet, not 0.0.0.0/0
```

**Test DNS Options**:

```bash
# Disable VPN DNS
pia-nm config set dns false
pia-nm refresh

# Connect to VPN
nmcli connection up PIA-US-East

# Check DNS servers
resolvectl status
# Should show system DNS, not PIA DNS (10.0.0.242)

# Test DNS leak
curl -s https://www.dnsleaktest.com/
# Will show your ISP's DNS servers (expected when dns=false)
```

---

## Appendix B: Why Mullvad Patterns for Specific Cases

### Token Refresh: GetAppliedConnection + Reapply

**Why not ProtonVPN's approach?**

ProtonVPN doesn't actually implement token refresh for WireGuard - they use ephemeral certificates that require creating entirely new connections when credentials expire. Their approach:

```python
# ProtonVPN: Recreate connection on credential change
await self.remove_connection(old_connection)
new_connection = self.setup()  # Creates fresh connection
await self.start_connection(new_connection)
```

This causes a brief disconnection (1-2 seconds) which is acceptable for their use case.

**Why Mullvad's Reapply pattern?**

PIA's tokens expire every 24 hours but we want **zero-downtime refresh**. Mullvad's `Reapply` method updates connection settings without dropping the tunnel:

```python
# Mullvad: Update settings without disconnecting
settings, version_id = device.GetAppliedConnection(0)
settings["wireguard"]["private-key"] = new_private_key
settings["wireguard"]["peers"][0]["endpoint"] = new_endpoint
device.Reapply(settings, version_id, 0)  # Seamless update
```

The active tunnel stays up, packets keep flowing, no reconnection needed.

### Connection Activation: Wait for Device Ready

**Why not ProtonVPN's approach?**

ProtonVPN uses an event-driven architecture with signal handlers:

```python
# ProtonVPN: Async signal-based state tracking
vpn_connection.connect("state-changed", self._on_state_changed)

def _on_state_changed(self, connection, state, reason):
    if state == NM.ActiveConnectionState.ACTIVATED:
        self._notify_subscribers(events.Connected(...))
```

This is elegant but adds complexity - you need a persistent event loop and state machine.

**Why Mullvad's synchronous wait?**

For a CLI tool, we want to confirm the connection is actually up before returning to the user:

```python
# Mullvad: Simple synchronous wait
connection = nm_client.add_connection_async(config).result()
nm_client.activate_connection_async(connection).result()

# Wait for device to be ready
if not wait_for_device_ready(device_path, timeout=15):
    raise Exception("Connection failed to activate")

print("✓ Connected to PIA-US-East")  # User sees immediate confirmation
```

This provides better UX for a CLI tool where users expect synchronous feedback.

**Summary**:

- **ProtonVPN patterns**: Best for GUI apps with persistent event loops
- **Mullvad patterns**: Best for CLI tools needing synchronous operations
- **pia-nm**: Hybrid approach - ProtonVPN's connection creation + Mullvad's operational patterns
