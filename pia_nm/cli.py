"""Command-line interface for PIA NetworkManager Integration."""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional


class CompactHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom formatter that shows commands more compactly."""

    def _format_usage(self, usage, actions, groups, prefix):
        """Override to show {command} instead of listing all commands."""
        if prefix is None:
            prefix = "usage: "

        # Get the program name
        prog = self._prog

        # Build a compact usage string
        usage_str = f"{prefix}{prog} [-h] [-v] {{command}} [options]"
        return usage_str + "\n"


from pia_nm.logging_config import setup_logging
from pia_nm.error_handling import (
    log_operation_start,
    log_operation_success,
    log_operation_failure,
    log_api_operation,
    log_nm_operation,
    log_file_operation,
    print_error,
)
from pia_nm.config import ConfigManager, ConfigError
from pia_nm.api_client import PIAClient, AuthenticationError, NetworkError, APIError
from pia_nm.wireguard import (
    generate_keypair,
    save_keypair,
    load_keypair,
    should_rotate_key,
    delete_keypair,
)
from pia_nm.network_manager import (
    create_profile,
    update_profile,
    delete_profile,
    is_active,
    profile_exists,
)
from pia_nm.systemd_manager import (
    install_units,
    uninstall_units,
    check_timer_status,
    enable_timer,
    disable_timer,
)


def check_system_dependencies() -> bool:
    """Verify required system commands are available."""
    import shutil

    required = ["nmcli", "wg", "systemctl"]
    missing = []

    for cmd in required:
        if not shutil.which(cmd):
            missing.append(cmd)

    if missing:
        print(f"✗ Missing required commands: {', '.join(missing)}\n")
        print("Install missing dependencies:")
        print("  sudo dnf install NetworkManager wireguard-tools systemd\n")
        return False

    return True


def format_profile_name(region_name: str) -> str:
    """Format region name into profile name.
    
    NetworkManager connection names are limited to 32 characters.
    """
    # Remove special characters and truncate if needed
    # PIA- prefix (4 chars) + region name (max 28 chars)
    clean_name = region_name.replace(" ", "-")
    if len(clean_name) > 28:
        clean_name = clean_name[:28]
    return f"PIA-{clean_name}"


def cmd_setup() -> None:
    """Interactive setup wizard."""
    import getpass

    logger = logging.getLogger(__name__)
    log_operation_start("setup command")

    print("\n" + "=" * 50)
    print("PIA NetworkManager Setup")
    print("=" * 50)

    # 1. Get credentials
    username = input("\nPIA Username: ").strip()
    if not username:
        print("✗ Username cannot be empty")
        logger.warning("Setup cancelled: username empty")
        return

    password = getpass.getpass("PIA Password: ")
    if not password:
        print("✗ Password cannot be empty")
        logger.warning("Setup cancelled: password empty")
        return

    # 2. Test authentication
    print("\nTesting credentials...")
    try:
        log_api_operation("authenticate")
        api = PIAClient()
        token = api.authenticate(username, password)
        print("✓ Authentication successful")
        log_operation_success("authentication")
    except AuthenticationError as e:
        print(f"✗ Authentication failed: {e}")
        log_operation_failure("authentication", e)
        print_error("auth_invalid_credentials")
        return
    except NetworkError as e:
        print(f"✗ Network error: {e}")
        log_operation_failure("authentication", e)
        print_error("network_unreachable")
        return
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        log_operation_failure("authentication", e)
        return

    # 3. Store credentials
    try:
        log_operation_start("storing credentials in keyring")
        config_mgr = ConfigManager()
        config_mgr.set_credentials(username, password)
        print("✓ Credentials stored in keyring")
        log_operation_success("credentials stored")
    except ConfigError as e:
        print(f"✗ Failed to store credentials: {e}")
        log_operation_failure("store credentials", e)
        print_error("keyring_unavailable")
        return
    except Exception as e:
        print(f"✗ Failed to store credentials: {e}")
        log_operation_failure("store credentials", e)
        return

    # 4. Get available regions
    print("\nFetching available regions...")
    try:
        log_api_operation("get_regions")
        regions = api.get_regions()
        print(f"✓ Found {len(regions)} regions")
        log_operation_success("fetch regions", f"count={len(regions)}")
    except NetworkError as e:
        print(f"✗ Network error: {e}")
        log_operation_failure("fetch regions", e)
        print_error("network_unreachable")
        return
    except APIError as e:
        print(f"✗ API error: {e}")
        log_operation_failure("fetch regions", e)
        print_error("key_registration_failed")
        return
    except Exception as e:
        print(f"✗ Failed to fetch regions: {e}")
        log_operation_failure("fetch regions", e)
        return

    # 5. Display and select regions
    print("\nAvailable regions:")
    print(f"{'ID':<20} {'Name':<30} {'Port Forward':<12}")
    print("-" * 62)
    for region in regions:
        pf = "Yes" if region.get("port_forward") else "No"
        print(f"{region['id']:<20} {region['name']:<30} {pf:<12}")

    print("\nEnter region IDs to configure (comma-separated):")
    print("Example: us-east,uk-london,jp-tokyo")
    selected_input = input("> ").strip()

    if not selected_input:
        print("✗ No regions selected")
        logger.warning("Setup cancelled: no regions selected")
        return

    selected_ids = [s.strip() for s in selected_input.split(",")]

    # Validate selected regions
    valid_region_ids = {r["id"] for r in regions}
    invalid_ids = [rid for rid in selected_ids if rid not in valid_region_ids]

    if invalid_ids:
        print(f"✗ Invalid region IDs: {', '.join(invalid_ids)}")
        logger.error("Invalid region IDs: %s", invalid_ids)
        return

    logger.info("Selected regions for setup: %s", selected_ids)

    # 6. Create profiles for each region
    print("\nCreating profiles...")
    successful_regions: List[str] = []

    for region_id in selected_ids:
        try:
            print(f"  Setting up {region_id}...", end=" ", flush=True)
            log_operation_start(f"setup region {region_id}")

            # Find region data
            region_data = None
            for region in regions:
                if region.get("id") == region_id:
                    region_data = region
                    break

            if not region_data:
                print("✗")
                log_operation_failure(
                    f"setup region {region_id}", Exception(f"Region {region_id} not found")
                )
                continue

            # Get WireGuard server info
            wg_servers = region_data.get("servers", {}).get("wg", [])
            if not wg_servers:
                print("✗")
                log_operation_failure(
                    f"setup region {region_id}", Exception("No WireGuard servers available")
                )
                continue

            server_info = wg_servers[0]
            server_hostname = server_info.get("cn")
            server_ip = server_info.get("ip")

            if not server_hostname or not server_ip:
                print("✗")
                log_operation_failure(
                    f"setup region {region_id}", Exception("Invalid server information")
                )
                continue

            # Load or generate keypair
            try:
                private_key, public_key = load_keypair(region_id)
                logger.debug("Loaded existing keypair for region: %s", region_id)
            except (FileNotFoundError, Exception):
                # Generate new keypair if not found or loading fails
                log_operation_start(f"generate keypair for {region_id}")
                private_key, public_key = generate_keypair()
                save_keypair(region_id, private_key, public_key)
                log_operation_success(f"generate keypair for {region_id}")

            # Register key with PIA
            log_api_operation("register_key", region_id)
            conn_details = api.register_key(token, public_key, server_hostname, server_ip)

            # Create NetworkManager profile
            region_name = region_data.get("name", region_id)
            profile_name = format_profile_name(region_name)
            log_nm_operation("create_profile", profile_name)
            success = create_profile(
                profile_name,
                {
                    "private_key": private_key,
                    "server_pubkey": conn_details["server_key"],
                    "endpoint": f"{conn_details['server_ip']}:{conn_details['server_port']}",
                    "peer_ip": conn_details["peer_ip"],
                    "dns_servers": conn_details["dns_servers"],
                },
            )

            if success:
                print("✓")
                successful_regions.append(region_id)
                log_operation_success(f"setup region {region_id}")
            else:
                print("✗")
                log_operation_failure(
                    f"setup region {region_id}", Exception("profile creation failed")
                )

        except Exception as e:
            print(f"✗ ({e})")
            log_operation_failure(f"setup region {region_id}", e)

    if not successful_regions:
        print("✗ No regions were successfully configured")
        logger.error("Setup failed: no regions successfully configured")
        return

    # 7. Save config
    try:
        log_operation_start("save configuration")
        config_mgr = ConfigManager()
        config_mgr.save(
            {
                "regions": successful_regions,
                "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
                "metadata": {"version": 1, "last_refresh": None},
            }
        )
        print(f"✓ Configuration saved ({len(successful_regions)} regions)")
        log_operation_success("save configuration", f"regions={len(successful_regions)}")
    except ConfigError as e:
        print(f"✗ Failed to save configuration: {e}")
        log_operation_failure("save configuration", e)
        print_error("config_invalid")
        return
    except Exception as e:
        print(f"✗ Failed to save configuration: {e}")
        log_operation_failure("save configuration", e)
        return

    # 8. Install systemd units
    print("\nInstalling systemd timer...")
    try:
        log_operation_start("install systemd units")
        install_units()
        print("✓ Systemd timer installed")
        log_operation_success("install systemd units")
    except Exception as e:
        print(f"✗ Failed to install systemd timer: {e}")
        log_operation_failure("install systemd units", e)
        return

    # Success message
    print("\n" + "=" * 50)
    print("✓ Setup Complete!")
    print("=" * 50)
    print(f"\nConfigured regions ({len(successful_regions)}):")
    for region_name in successful_regions:
        print(f"  • {region_name}")
    print("\nYou can now:")
    print("  • View status: pia-nm status")
    print("  • Connect via NetworkManager GUI")
    print("  • Manually refresh: pia-nm refresh")
    print("\nToken refresh runs automatically every 12 hours.")
    log_operation_success("setup command")


def cmd_list_regions(port_forwarding: bool = False) -> None:
    """List available PIA regions."""
    log_operation_start("list-regions command", f"port_forwarding={port_forwarding}")

    try:
        log_api_operation("get_regions")
        api = PIAClient()
        regions = api.get_regions()
        log_operation_success("fetch regions", f"count={len(regions)}")

        if port_forwarding:
            regions = [r for r in regions if r.get("port_forward")]
            print(f"\nRegions with port forwarding ({len(regions)}):")
        else:
            print(f"\nAvailable regions ({len(regions)}):")

        print(f"{'ID':<20} {'Name':<30} {'Country':<10} {'Port Forward':<12}")
        print("-" * 72)

        for region in regions:
            pf = "Yes" if region.get("port_forward") else "No"
            print(f"{region['id']:<20} {region['name']:<30} {region['country']:<10} {pf:<12}")

        log_operation_success("list-regions command")

    except NetworkError as e:
        print(f"✗ Network error: {e}")
        log_operation_failure("fetch regions", e)
        print_error("network_unreachable")
        sys.exit(1)
    except APIError as e:
        print(f"✗ API error: {e}")
        log_operation_failure("fetch regions", e)
        print_error("key_registration_failed")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Failed to list regions: {e}")
        log_operation_failure("fetch regions", e)
        sys.exit(1)


def cmd_refresh(region: Optional[str] = None) -> None:
    """Refresh authentication tokens."""
    logger = logging.getLogger(__name__)
    log_operation_start("refresh command", f"region={region}" if region else "all regions")

    try:
        log_operation_start("load configuration")
        config_mgr = ConfigManager()
        config = config_mgr.load()
        log_operation_success("load configuration")
    except ConfigError as e:
        print(f"✗ Failed to load configuration: {e}")
        log_operation_failure("load configuration", e)
        print_error("config_not_found")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        log_operation_failure("load configuration", e)
        sys.exit(1)

    regions_to_refresh = [region] if region else config.get("regions", [])

    if not regions_to_refresh:
        print("✗ No regions configured")
        logger.warning("No regions configured for refresh")
        return

    logger.info("Refreshing %d region(s)", len(regions_to_refresh))

    # Get credentials
    try:
        log_operation_start("retrieve credentials from keyring")
        username, password = config_mgr.get_credentials()
        log_operation_success("retrieve credentials")
    except ConfigError as e:
        print(f"✗ Failed to retrieve credentials: {e}")
        log_operation_failure("retrieve credentials", e)
        print_error("keyring_unavailable")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Failed to retrieve credentials: {e}")
        log_operation_failure("retrieve credentials", e)
        sys.exit(1)

    # Authenticate
    try:
        log_api_operation("authenticate")
        api = PIAClient()
        token = api.authenticate(username, password)
        log_operation_success("authentication for refresh")
    except AuthenticationError as e:
        print(f"✗ Authentication failed: {e}")
        log_operation_failure("authentication", e)
        print_error("auth_invalid_credentials")
        sys.exit(1)
    except NetworkError as e:
        print(f"✗ Network error: {e}")
        log_operation_failure("authentication", e)
        print_error("network_unreachable")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        log_operation_failure("authentication", e)
        sys.exit(1)

    # Get regions data for server info
    try:
        log_api_operation("get_regions")
        regions = api.get_regions()
    except (NetworkError, APIError) as e:
        print(f"✗ Failed to fetch regions: {e}")
        log_operation_failure("fetch regions", e)
        sys.exit(1)

    # Refresh each region
    print("\nRefreshing tokens...")
    successful = 0
    failed = 0

    for region_id in regions_to_refresh:
        try:
            print(f"  {region_id}...", end=" ", flush=True)
            log_operation_start(f"refresh region {region_id}")

            # Find region data
            region_data = None
            for region in regions:
                if region.get("id") == region_id:
                    region_data = region
                    break

            if not region_data:
                print("✗ (region not found)")
                log_operation_failure(f"refresh region {region_id}", Exception("region not found"))
                failed += 1
                continue

            # Get WireGuard server info
            wg_servers = region_data.get("servers", {}).get("wg", [])
            if not wg_servers:
                print("✗ (no WG servers)")
                log_operation_failure(
                    f"refresh region {region_id}", Exception("No WireGuard servers available")
                )
                failed += 1
                continue

            server_info = wg_servers[0]
            server_hostname = server_info.get("cn")
            server_ip = server_info.get("ip")

            if not server_hostname or not server_ip:
                print("✗ (invalid server info)")
                log_operation_failure(
                    f"refresh region {region_id}", Exception("Invalid server information")
                )
                failed += 1
                continue

            # Load keypair
            try:
                private_key, public_key = load_keypair(region_id)
                logger.debug("Loaded keypair for region: %s", region_id)
            except FileNotFoundError:
                print("✗ (keypair not found)")
                log_operation_failure(f"refresh region {region_id}", Exception("keypair not found"))
                failed += 1
                continue

            # Check if rotation needed
            if should_rotate_key(region_id):
                log_operation_start(f"rotate key for {region_id}")
                private_key, public_key = generate_keypair()
                save_keypair(region_id, private_key, public_key)
                log_operation_success(f"rotate key for {region_id}")

            # Register key
            log_api_operation("register_key", region_id)
            conn_details = api.register_key(token, public_key, server_hostname, server_ip)

            # Update profile
            region_name = region_data.get("name", region_id)
            profile_name = format_profile_name(region_name)
            was_active = is_active(profile_name)

            log_nm_operation("update_profile", profile_name)
            success = update_profile(
                profile_name,
                {
                    "private_key": private_key,
                    "server_pubkey": conn_details["server_key"],
                    "endpoint": f"{conn_details['server_ip']}:{conn_details['server_port']}",
                    "peer_ip": conn_details["peer_ip"],
                    "dns_servers": conn_details["dns_servers"],
                },
            )

            if success:
                print("✓")
                if was_active:
                    log_operation_success(f"refresh region {region_id}", "connection was active")
                else:
                    log_operation_success(f"refresh region {region_id}")
                successful += 1
            else:
                print("✗")
                log_operation_failure(
                    f"refresh region {region_id}", Exception("profile update failed")
                )
                failed += 1

        except Exception as e:
            print(f"✗ ({e})")
            log_operation_failure(f"refresh region {region_id}", e)
            failed += 1

    # Update last refresh timestamp
    try:
        log_operation_start("update last_refresh timestamp")
        config_mgr.update_last_refresh()
        log_operation_success("update last_refresh timestamp")
    except Exception as e:
        logger.warning("Failed to update last_refresh timestamp: %s", e)

    # Summary
    print(f"\n✓ Refresh complete: {successful} successful, {failed} failed")
    log_operation_success("refresh command", f"successful={successful}, failed={failed}")
    if failed > 0:
        sys.exit(1)


def cmd_add_region(region_id: str) -> None:
    """Add a new region."""
    logger = logging.getLogger(__name__)
    log_operation_start("add-region command", f"region={region_id}")

    # Verify region exists
    try:
        log_api_operation("get_regions")
        api = PIAClient()
        regions = api.get_regions()
        region_ids = {r["id"] for r in regions}

        if region_id not in region_ids:
            print(f"✗ Region '{region_id}' not found")
            logger.error("Region not found: %s", region_id)
            sys.exit(1)

        logger.info("Verified region exists: %s", region_id)
    except Exception as e:
        print(f"✗ Failed to verify region: {e}")
        log_operation_failure("verify region", e)
        sys.exit(1)

    # Get credentials
    try:
        log_operation_start("retrieve credentials")
        config_mgr = ConfigManager()
        username, password = config_mgr.get_credentials()
        log_operation_success("retrieve credentials")
    except Exception as e:
        print(f"✗ Failed to retrieve credentials: {e}")
        log_operation_failure("retrieve credentials", e)
        print_error("keyring_unavailable")
        sys.exit(1)

    # Authenticate
    try:
        log_api_operation("authenticate")
        token = api.authenticate(username, password)
        log_operation_success("authentication for add-region")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        log_operation_failure("authentication", e)
        print_error("auth_invalid_credentials")
        sys.exit(1)

    # Generate keypair
    try:
        print(f"Setting up {region_id}...", end=" ", flush=True)
        log_operation_start(f"generate keypair for {region_id}")
        private_key, public_key = generate_keypair()
        save_keypair(region_id, private_key, public_key)
        log_operation_success(f"generate keypair for {region_id}")
    except Exception as e:
        print(f"✗ ({e})")
        log_operation_failure("generate keypair", e)
        sys.exit(1)

    # Register key
    try:
        log_api_operation("register_key", region_id)
        conn_details = api.register_key(token, public_key, region_id)
        log_operation_success("register key", region_id)
    except Exception as e:
        print(f"✗ ({e})")
        log_operation_failure("register key", e)
        print_error("key_registration_failed")
        sys.exit(1)

    # Create profile
    try:
        profile_name = format_profile_name(region_id)
        log_nm_operation("create_profile", profile_name)
        success = create_profile(
            profile_name,
            {
                "private_key": private_key,
                "server_pubkey": conn_details["server_key"],
                "endpoint": f"{conn_details['server_ip']}:{conn_details['server_port']}",
                "peer_ip": conn_details["peer_ip"],
                "dns_servers": conn_details["dns_servers"],
            },
        )

        if not success:
            print("✗")
            log_operation_failure("create profile", Exception("profile creation failed"))
            print_error("nm_operation_failed")
            sys.exit(1)

        print("✓")
        log_operation_success(f"create profile for {region_id}")
    except Exception as e:
        print(f"✗ ({e})")
        log_operation_failure("create profile", e)
        print_error("nm_operation_failed")
        sys.exit(1)

    # Add to config
    try:
        log_operation_start("update configuration")
        config = config_mgr.load()
        if region_id not in config.get("regions", []):
            config["regions"].append(region_id)
            config_mgr.save(config)
            log_operation_success("update configuration", f"added {region_id}")
    except Exception as e:
        print(f"✗ Failed to update configuration: {e}")
        log_operation_failure("update configuration", e)
        print_error("config_invalid")
        sys.exit(1)

    print(f"✓ Region '{region_id}' added successfully")
    log_operation_success("add-region command")


def cmd_remove_region(region_id: str) -> None:
    """Remove a region."""
    logger = logging.getLogger(__name__)
    log_operation_start("remove-region command", f"region={region_id}")

    try:
        log_operation_start("load configuration")
        config_mgr = ConfigManager()
        config = config_mgr.load()
        log_operation_success("load configuration")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        log_operation_failure("load configuration", e)
        print_error("config_not_found")
        sys.exit(1)

    if region_id not in config.get("regions", []):
        print(f"✗ Region '{region_id}' not configured")
        logger.warning("Region not configured: %s", region_id)
        return

    # Delete profile
    try:
        profile_name = format_profile_name(region_id)
        log_nm_operation("delete_profile", profile_name)
        success = delete_profile(profile_name)
        if success:
            log_operation_success(f"delete profile for {region_id}")
    except Exception as e:
        print(f"✗ Failed to delete profile: {e}")
        log_operation_failure("delete profile", e)
        print_error("nm_operation_failed")
        sys.exit(1)

    # Remove from config
    try:
        log_operation_start("update configuration")
        config["regions"].remove(region_id)
        config_mgr.save(config)
        log_operation_success("update configuration", f"removed {region_id}")
    except Exception as e:
        print(f"✗ Failed to update configuration: {e}")
        log_operation_failure("update configuration", e)
        print_error("config_invalid")
        sys.exit(1)

    # Delete keypair
    try:
        log_file_operation("delete", f"~/.config/pia-nm/keys/{region_id}.key")
        delete_keypair(region_id)
        log_operation_success(f"delete keypair for {region_id}")
    except Exception as e:
        logger.warning("Failed to delete keypair: %s", e)

    print(f"✓ Region '{region_id}' removed successfully")
    log_operation_success("remove-region command")


def cmd_status() -> None:
    """Show status of configured regions and timer."""
    logger = logging.getLogger(__name__)
    log_operation_start("status command")

    try:
        log_operation_start("load configuration")
        config_mgr = ConfigManager()
        config = config_mgr.load()
        log_operation_success("load configuration")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        log_operation_failure("load configuration", e)
        print_error("config_not_found")
        sys.exit(1)

    regions = config.get("regions", [])
    last_refresh = config.get("metadata", {}).get("last_refresh")

    print("\n" + "=" * 50)
    print("PIA NetworkManager Status")
    print("=" * 50)

    print(f"\nConfigured regions ({len(regions)}):")
    if regions:
        for region_id in regions:
            profile_name = format_profile_name(region_id)
            exists = profile_exists(profile_name)
            active = is_active(profile_name) if exists else False

            status = "✓ Active" if active else ("✓ Exists" if exists else "✗ Missing")
            print(f"  • {region_id:<20} {status}")
            logger.debug("Region %s: exists=%s, active=%s", region_id, exists, active)
    else:
        print("  (none configured)")

    print(f"\nLast refresh: {last_refresh or 'Never'}")

    # Check timer status
    try:
        log_operation_start("check systemd timer status")
        timer_status = check_timer_status()
        print(f"\nSystemd timer: {timer_status.get('status', 'Unknown')}")
        if timer_status.get("next_run"):
            print(f"Next refresh: {timer_status['next_run']}")
        log_operation_success("check systemd timer status")
    except Exception as e:
        print(f"\nSystemd timer: Error ({e})")
        logger.warning("Failed to check timer status: %s", e)

    print()
    log_operation_success("status command")


def cmd_install() -> None:
    """Install systemd units."""
    log_operation_start("install command")

    try:
        log_operation_start("install systemd units")
        install_units()
        print("✓ Systemd timer installed and enabled")
        log_operation_success("install systemd units")
        log_operation_success("install command")
    except Exception as e:
        print(f"✗ Failed to install systemd units: {e}")
        log_operation_failure("install systemd units", e)
        sys.exit(1)


def cmd_uninstall() -> None:
    """Uninstall and remove all components."""
    log_operation_start("uninstall command")

    # Confirm with user
    print("\n" + "=" * 50)
    print("Uninstall PIA NetworkManager Integration")
    print("=" * 50)
    print("\nThis will:")
    print("  • Remove all PIA NetworkManager profiles")
    print("  • Disable and remove systemd timer")
    print("  • Delete configuration directory")
    print("  • Remove credentials from keyring")

    confirm = input("\nContinue? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Uninstall cancelled")
        logging.getLogger(__name__).info("Uninstall cancelled by user")
        return

    # Remove profiles
    print("\nRemoving profiles...")
    try:
        log_operation_start("load configuration for uninstall")
        config_mgr = ConfigManager()
        config = config_mgr.load()
        regions = config.get("regions", [])
        log_operation_success("load configuration for uninstall")

        for region_id in regions:
            profile_name = format_profile_name(region_id)
            try:
                log_nm_operation("delete_profile", profile_name)
                delete_profile(profile_name)
                print(f"  ✓ Removed {profile_name}")
                log_operation_success(f"delete profile {profile_name}")
            except Exception as e:
                print(f"  ✗ Failed to remove {profile_name}: {e}")
                log_operation_failure(f"delete profile {profile_name}", e)

    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        log_operation_failure("load configuration for uninstall", e)

    # Uninstall systemd units
    print("\nRemoving systemd units...")
    try:
        log_operation_start("uninstall systemd units")
        uninstall_units()
        print("  ✓ Removed systemd timer and service")
        log_operation_success("uninstall systemd units")
    except Exception as e:
        print(f"  ✗ Failed to remove systemd units: {e}")
        log_operation_failure("uninstall systemd units", e)

    # Delete config directory
    print("\nRemoving configuration...")
    try:
        config_dir = Path.home() / ".config/pia-nm"
        if config_dir.exists():
            import shutil

            log_file_operation("delete", str(config_dir))
            shutil.rmtree(config_dir)
            print(f"  ✓ Removed {config_dir}")
            log_operation_success("delete configuration directory")
    except Exception as e:
        print(f"  ✗ Failed to remove configuration: {e}")
        log_operation_failure("delete configuration directory", e)

    # Remove credentials from keyring
    print("\nRemoving credentials...")
    try:
        import keyring

        log_operation_start("remove credentials from keyring")
        keyring.delete_password("pia-nm", "username")
        keyring.delete_password("pia-nm", "password")
        print("  ✓ Removed credentials from keyring")
        log_operation_success("remove credentials from keyring")
    except Exception as e:
        print(f"  ✗ Failed to remove credentials: {e}")
        logging.getLogger(__name__).warning("Failed to remove credentials: %s", e)

    print("\n" + "=" * 50)
    print("✓ Uninstall Complete")
    print("=" * 50)
    log_operation_success("uninstall command")


def cmd_enable() -> None:
    """Enable the systemd timer."""
    log_operation_start("enable command")

    try:
        log_operation_start("enable systemd timer")
        enable_timer()
        print("✓ Systemd timer enabled")
        log_operation_success("enable systemd timer")
        log_operation_success("enable command")
    except Exception as e:
        print(f"✗ Failed to enable timer: {e}")
        log_operation_failure("enable systemd timer", e)
        sys.exit(1)


def cmd_disable() -> None:
    """Disable the systemd timer."""
    log_operation_start("disable command")

    try:
        log_operation_start("disable systemd timer")
        disable_timer()
        print("✓ Systemd timer disabled")
        log_operation_success("disable systemd timer")
        log_operation_success("disable command")
    except Exception as e:
        print(f"✗ Failed to disable timer: {e}")
        log_operation_failure("disable systemd timer", e)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="pia-nm",
        description="PIA WireGuard integration for NetworkManager",
        formatter_class=CompactHelpFormatter,
        epilog="Commands:\n"
        "  setup              Interactive setup wizard\n"
        "  list-regions       List available PIA regions\n"
        "  refresh            Refresh authentication tokens\n"
        "  add-region         Add a new region\n"
        "  remove-region      Remove a region\n"
        "  status             Show status\n"
        "  install            Install systemd units\n"
        "  uninstall          Uninstall and remove all components\n"
        "  enable             Enable systemd timer\n"
        "  disable            Disable systemd timer\n",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    subparsers = parser.add_subparsers(dest="command", help=argparse.SUPPRESS)

    # setup
    subparsers.add_parser("setup", help="Interactive setup wizard")

    # list-regions
    list_parser = subparsers.add_parser("list-regions", help="List available regions")
    list_parser.add_argument(
        "--port-forwarding",
        action="store_true",
        help="Show only regions with port forwarding",
    )

    # refresh
    refresh_parser = subparsers.add_parser("refresh", help="Refresh authentication tokens")
    refresh_parser.add_argument(
        "--region",
        help="Specific region to refresh",
    )

    # add-region
    add_parser = subparsers.add_parser("add-region", help="Add a new region")
    add_parser.add_argument("region_id", help="Region ID to add")

    # remove-region
    remove_parser = subparsers.add_parser("remove-region", help="Remove a region")
    remove_parser.add_argument("region_id", help="Region ID to remove")

    # status
    subparsers.add_parser("status", help="Show status")

    # install
    subparsers.add_parser("install", help="Install systemd units")

    # uninstall
    subparsers.add_parser("uninstall", help="Uninstall and remove all components")

    # enable
    subparsers.add_parser("enable", help="Enable systemd timer")

    # disable
    subparsers.add_parser("disable", help="Disable systemd timer")

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    logger.info("pia-nm started (verbose=%s)", args.verbose)

    # Check system dependencies
    if not check_system_dependencies():
        logger.error("System dependencies check failed")
        sys.exit(1)

    # Route to appropriate handler
    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "setup":
            cmd_setup()
        elif args.command == "list-regions":
            cmd_list_regions(args.port_forwarding)
        elif args.command == "refresh":
            cmd_refresh(args.region)
        elif args.command == "add-region":
            cmd_add_region(args.region_id)
        elif args.command == "remove-region":
            cmd_remove_region(args.region_id)
        elif args.command == "status":
            cmd_status()
        elif args.command == "install":
            cmd_install()
        elif args.command == "uninstall":
            cmd_uninstall()
        elif args.command == "enable":
            cmd_enable()
        elif args.command == "disable":
            cmd_disable()
        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
