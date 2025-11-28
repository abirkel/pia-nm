#!/usr/bin/env python3
"""Debug script to check WireGuard connection settings."""

import gi
gi.require_version("NM", "1.0")
from gi.repository import NM

# Initialize NM client
client = NM.Client.new(None)

# Get the connection
conn = client.get_connection_by_id("PIA-JP TOKYO")

if not conn:
    print("Connection not found!")
    exit(1)

print(f"Connection: {conn.get_id()}")
print(f"UUID: {conn.get_uuid()}")

# Get WireGuard settings
wg_setting = conn.get_setting_by_name("wireguard")

if not wg_setting:
    print("No WireGuard settings found!")
    exit(1)

print(f"\nWireGuard Settings:")
print(f"  Private key: {'<set>' if wg_setting.get_private_key() else '<not set>'}")
print(f"  FWMark: {wg_setting.get_fwmark()}")
print(f"  Peer count: {wg_setting.get_peers_len()}")

# Check peers
for i in range(wg_setting.get_peers_len()):
    peer = wg_setting.get_peer(i)
    print(f"\nPeer {i}:")
    print(f"  Public key: {peer.get_public_key()}")
    print(f"  Endpoint: {peer.get_endpoint()}")
    print(f"  Persistent keepalive: {peer.get_persistent_keepalive()}")
    print(f"  Allowed IPs count: {peer.get_allowed_ips_len()}")
    for j in range(peer.get_allowed_ips_len()):
        print(f"    Allowed IP {j}: {peer.get_allowed_ip(j, None)}")

# Get IPv4 settings
ipv4_setting = conn.get_setting_ip4_config()
if ipv4_setting:
    print(f"\nIPv4 Settings:")
    print(f"  Method: {ipv4_setting.get_method()}")
    print(f"  Address count: {ipv4_setting.get_num_addresses()}")
    for i in range(ipv4_setting.get_num_addresses()):
        addr = ipv4_setting.get_address(i)
        print(f"    Address {i}: {addr.get_address()}/{addr.get_prefix()}")
    print(f"  Route count: {ipv4_setting.get_num_routes()}")
    for i in range(ipv4_setting.get_num_routes()):
        route = ipv4_setting.get_route(i)
        print(f"    Route {i}: {route.get_dest()}/{route.get_prefix()} via {route.get_next_hop()}")
