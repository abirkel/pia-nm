"""Command-line interface for PIA NetworkManager Integration."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional


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


from pia_nm.config import ConfigManager
from pia_nm.api_client import PIAClient
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
    list_profiles,
    profile_exists,
)
from pia_nm.systemd_manager import (
    install_units,
    uninstall_units,
    check_timer_status,
    enable_timer,
    disable_timer,
)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging to file and console."""
    log_dir = Path.home() / ".local/share/pia-nm/logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # File handler
    file_handler = logging.FileHandler(log_dir / "pia-nm.log")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(log_format))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


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


def format_profile_name(region_id: str) -> str:
    """Format region ID into profile name."""
    # Convert us-east -> PIA-US-East
    parts = region_id.split("-")
    formatted_parts = [part.upper() if len(part) <= 2 else part.title() for part in parts]
    return f"PIA-{'-'.join(formatted_parts)}"


def cmd_setup() -> None:
    """Interactive setup wizard."""
    import getpass

    logger = logging.getLogger(__name__)

    print("\n" + "=" * 50)
    print("PIA NetworkManager Setup")
    print("=" * 50)

    # 1. Get credentials
    username = input("\nPIA Username: ").strip()
    if not username:
        print("✗ Username cannot be empty")
        return

    password = getpass.getpass("PIA Password: ")
    if not password:
        print("✗ Password cannot be empty")
        return

    # 2. Test authentication
    print("\nTesting credentials...")
    try:
        api = PIAClient()
        token = api.authenticate(username, password)
        print("✓ Authentication successful")
        logger.info("Authentication successful during setup")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        logger.error(f"Authentication failed during setup: {e}")
        return

    # 3. Store credentials
    try:
        config_mgr = ConfigManager()
        config_mgr.set_credentials(username, password)
        print("✓ Credentials stored in keyring")
        logger.info("Credentials stored in keyring")
    except Exception as e:
        print(f"✗ Failed to store credentials: {e}")
        logger.error(f"Failed to store credentials: {e}")
        return

    # 4. Get available regions
    print("\nFetching available regions...")
    try:
        regions = api.get_regions()
        print(f"✓ Found {len(regions)} regions")
        logger.info(f"Retrieved {len(regions)} regions from PIA API")
    except Exception as e:
        print(f"✗ Failed to fetch regions: {e}")
        logger.error(f"Failed to fetch regions: {e}")
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
        return

    selected_ids = [s.strip() for s in selected_input.split(",")]

    # Validate selected regions
    valid_region_ids = {r["id"] for r in regions}
    invalid_ids = [rid for rid in selected_ids if rid not in valid_region_ids]

    if invalid_ids:
        print(f"✗ Invalid region IDs: {', '.join(invalid_ids)}")
        return

    # 6. Create profiles for each region
    print("\nCreating profiles...")
    successful_regions = []

    for region_id in selected_ids:
        try:
            print(f"  Setting up {region_id}...", end=" ", flush=True)

            # Load or generate keypair
            try:
                private_key, public_key = load_keypair(region_id)
            except FileNotFoundError:
                private_key, public_key = generate_keypair()
                save_keypair(region_id, private_key, public_key)

            # Register key with PIA
            conn_details = api.register_key(token, public_key, region_id)

            # Create NetworkManager profile
            profile_name = format_profile_name(region_id)
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
                logger.info(f"Successfully configured region: {region_id}")
            else:
                print("✗")
                logger.error(f"Failed to create profile for region: {region_id}")

        except Exception as e:
            print(f"✗ ({e})")
            logger.error(f"Failed to setup region {region_id}: {e}")

    if not successful_regions:
        print("✗ No regions were successfully configured")
        return

    # 7. Save config
    try:
        config_mgr = ConfigManager()
        config_mgr.save(
            {
                "regions": successful_regions,
                "preferences": {"dns": True, "ipv6": False, "port_forwarding": False},
                "metadata": {"version": 1, "last_refresh": None},
            }
        )
        print(f"✓ Configuration saved ({len(successful_regions)} regions)")
        logger.info(f"Configuration saved with {len(successful_regions)} regions")
    except Exception as e:
        print(f"✗ Failed to save configuration: {e}")
        logger.error(f"Failed to save configuration: {e}")
        return

    # 8. Install systemd units
    print("\nInstalling systemd timer...")
    try:
        install_units()
        print("✓ Systemd timer installed")
        logger.info("Systemd timer installed successfully")
    except Exception as e:
        print(f"✗ Failed to install systemd timer: {e}")
        logger.error(f"Failed to install systemd timer: {e}")
        return

    # Success message
    print("\n" + "=" * 50)
    print("✓ Setup Complete!")
    print("=" * 50)
    print(f"\nConfigured regions ({len(successful_regions)}):")
    for region in successful_regions:
        print(f"  • {region}")
    print("\nYou can now:")
    print("  • View status: pia-nm status")
    print("  • Connect via NetworkManager GUI")
    print("  • Manually refresh: pia-nm refresh")
    print("\nToken refresh runs automatically every 12 hours.")


def cmd_list_regions(port_forwarding: bool = False) -> None:
    """List available PIA regions."""
    logger = logging.getLogger(__name__)

    try:
        api = PIAClient()
        regions = api.get_regions()
        logger.info(f"Retrieved {len(regions)} regions from PIA API")

        if port_forwarding:
            regions = [r for r in regions if r.get("port_forward")]
            print(f"\nRegions with port forwarding ({len(regions)}):")
        else:
            print(f"\nAvailable regions ({len(regions)}):")

        print(f"{'ID':<20} {'Name':<30} {'Country':<10} {'Port Forward':<12}")
        print("-" * 72)

        for region in regions:
            pf = "Yes" if region.get("port_forward") else "No"
            print(
                f"{region['id']:<20} {region['name']:<30} {region['country']:<10} {pf:<12}"
            )

    except Exception as e:
        print(f"✗ Failed to list regions: {e}")
        logger.error(f"Failed to list regions: {e}")
        sys.exit(1)


def cmd_refresh(region: Optional[str] = None) -> None:
    """Refresh authentication tokens."""
    logger = logging.getLogger(__name__)

    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    regions_to_refresh = [region] if region else config.get("regions", [])

    if not regions_to_refresh:
        print("✗ No regions configured")
        logger.warning("No regions configured for refresh")
        return

    # Get credentials
    try:
        username, password = config_mgr.get_credentials()
    except Exception as e:
        print(f"✗ Failed to retrieve credentials: {e}")
        logger.error(f"Failed to retrieve credentials: {e}")
        sys.exit(1)

    # Authenticate
    try:
        api = PIAClient()
        token = api.authenticate(username, password)
        logger.info("Authentication successful for token refresh")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        logger.error(f"Authentication failed during refresh: {e}")
        sys.exit(1)

    # Refresh each region
    print("\nRefreshing tokens...")
    successful = 0
    failed = 0

    for region_id in regions_to_refresh:
        try:
            print(f"  {region_id}...", end=" ", flush=True)

            # Load keypair
            try:
                private_key, public_key = load_keypair(region_id)
            except FileNotFoundError:
                print("✗ (keypair not found)")
                logger.error(f"Keypair not found for region: {region_id}")
                failed += 1
                continue

            # Check if rotation needed
            if should_rotate_key(region_id):
                logger.info(f"Rotating key for region: {region_id}")
                private_key, public_key = generate_keypair()
                save_keypair(region_id, private_key, public_key)

            # Register key
            conn_details = api.register_key(token, public_key, region_id)

            # Update profile
            profile_name = format_profile_name(region_id)
            was_active = is_active(profile_name)

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
                    logger.info(f"Updated {region_id} (connection was active)")
                else:
                    logger.info(f"Updated {region_id}")
                successful += 1
            else:
                print("✗")
                logger.error(f"Failed to update profile for region: {region_id}")
                failed += 1

        except Exception as e:
            print(f"✗ ({e})")
            logger.error(f"Failed to refresh region {region_id}: {e}")
            failed += 1

    # Update last refresh timestamp
    try:
        config_mgr.update_last_refresh()
        logger.info("Updated last_refresh timestamp")
    except Exception as e:
        logger.warning(f"Failed to update last_refresh timestamp: {e}")

    # Summary
    print(f"\n✓ Refresh complete: {successful} successful, {failed} failed")
    if failed > 0:
        sys.exit(1)


def cmd_add_region(region_id: str) -> None:
    """Add a new region."""
    logger = logging.getLogger(__name__)

    # Verify region exists
    try:
        api = PIAClient()
        regions = api.get_regions()
        region_ids = {r["id"] for r in regions}

        if region_id not in region_ids:
            print(f"✗ Region '{region_id}' not found")
            logger.error(f"Region not found: {region_id}")
            sys.exit(1)

        logger.info(f"Verified region exists: {region_id}")
    except Exception as e:
        print(f"✗ Failed to verify region: {e}")
        logger.error(f"Failed to verify region: {e}")
        sys.exit(1)

    # Get credentials
    try:
        config_mgr = ConfigManager()
        username, password = config_mgr.get_credentials()
    except Exception as e:
        print(f"✗ Failed to retrieve credentials: {e}")
        logger.error(f"Failed to retrieve credentials: {e}")
        sys.exit(1)

    # Authenticate
    try:
        token = api.authenticate(username, password)
        logger.info("Authentication successful for add-region")
    except Exception as e:
        print(f"✗ Authentication failed: {e}")
        logger.error(f"Authentication failed during add-region: {e}")
        sys.exit(1)

    # Generate keypair
    try:
        print(f"Setting up {region_id}...", end=" ", flush=True)
        private_key, public_key = generate_keypair()
        save_keypair(region_id, private_key, public_key)
        logger.info(f"Generated keypair for region: {region_id}")
    except Exception as e:
        print(f"✗ ({e})")
        logger.error(f"Failed to generate keypair: {e}")
        sys.exit(1)

    # Register key
    try:
        conn_details = api.register_key(token, public_key, region_id)
        logger.info(f"Registered key with PIA for region: {region_id}")
    except Exception as e:
        print(f"✗ ({e})")
        logger.error(f"Failed to register key: {e}")
        sys.exit(1)

    # Create profile
    try:
        profile_name = format_profile_name(region_id)
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
            logger.error(f"Failed to create profile for region: {region_id}")
            sys.exit(1)

        print("✓")
        logger.info(f"Created NetworkManager profile for region: {region_id}")
    except Exception as e:
        print(f"✗ ({e})")
        logger.error(f"Failed to create profile: {e}")
        sys.exit(1)

    # Add to config
    try:
        config = config_mgr.load()
        if region_id not in config.get("regions", []):
            config["regions"].append(region_id)
            config_mgr.save(config)
            logger.info(f"Added region to configuration: {region_id}")
    except Exception as e:
        print(f"✗ Failed to update configuration: {e}")
        logger.error(f"Failed to update configuration: {e}")
        sys.exit(1)

    print(f"✓ Region '{region_id}' added successfully")


def cmd_remove_region(region_id: str) -> None:
    """Remove a region."""
    logger = logging.getLogger(__name__)

    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    if region_id not in config.get("regions", []):
        print(f"✗ Region '{region_id}' not configured")
        logger.warning(f"Region not configured: {region_id}")
        return

    # Delete profile
    try:
        profile_name = format_profile_name(region_id)
        success = delete_profile(profile_name)
        if success:
            logger.info(f"Deleted NetworkManager profile for region: {region_id}")
    except Exception as e:
        print(f"✗ Failed to delete profile: {e}")
        logger.error(f"Failed to delete profile: {e}")
        sys.exit(1)

    # Remove from config
    try:
        config["regions"].remove(region_id)
        config_mgr.save(config)
        logger.info(f"Removed region from configuration: {region_id}")
    except Exception as e:
        print(f"✗ Failed to update configuration: {e}")
        logger.error(f"Failed to update configuration: {e}")
        sys.exit(1)

    # Delete keypair
    try:
        delete_keypair(region_id)
        logger.info(f"Deleted keypair for region: {region_id}")
    except Exception as e:
        logger.warning(f"Failed to delete keypair: {e}")

    print(f"✓ Region '{region_id}' removed successfully")


def cmd_status() -> None:
    """Show status of configured regions and timer."""
    logger = logging.getLogger(__name__)

    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        logger.error(f"Failed to load configuration: {e}")
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
    else:
        print("  (none configured)")

    print(f"\nLast refresh: {last_refresh or 'Never'}")

    # Check timer status
    try:
        timer_status = check_timer_status()
        print(f"\nSystemd timer: {timer_status.get('status', 'Unknown')}")
        if timer_status.get("next_run"):
            print(f"Next refresh: {timer_status['next_run']}")
    except Exception as e:
        print(f"\nSystemd timer: Error ({e})")
        logger.warning(f"Failed to check timer status: {e}")

    print()


def cmd_install() -> None:
    """Install systemd units."""
    logger = logging.getLogger(__name__)

    try:
        install_units()
        print("✓ Systemd timer installed and enabled")
        logger.info("Systemd units installed successfully")
    except Exception as e:
        print(f"✗ Failed to install systemd units: {e}")
        logger.error(f"Failed to install systemd units: {e}")
        sys.exit(1)


def cmd_uninstall() -> None:
    """Uninstall and remove all components."""
    logger = logging.getLogger(__name__)

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
        return

    # Remove profiles
    print("\nRemoving profiles...")
    try:
        config_mgr = ConfigManager()
        config = config_mgr.load()
        regions = config.get("regions", [])

        for region_id in regions:
            profile_name = format_profile_name(region_id)
            try:
                delete_profile(profile_name)
                print(f"  ✓ Removed {profile_name}")
                logger.info(f"Removed profile: {profile_name}")
            except Exception as e:
                print(f"  ✗ Failed to remove {profile_name}: {e}")
                logger.error(f"Failed to remove profile {profile_name}: {e}")

    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        logger.error(f"Failed to load configuration: {e}")

    # Uninstall systemd units
    print("\nRemoving systemd units...")
    try:
        uninstall_units()
        print("  ✓ Removed systemd timer and service")
        logger.info("Removed systemd units")
    except Exception as e:
        print(f"  ✗ Failed to remove systemd units: {e}")
        logger.error(f"Failed to remove systemd units: {e}")

    # Delete config directory
    print("\nRemoving configuration...")
    try:
        config_dir = Path.home() / ".config/pia-nm"
        if config_dir.exists():
            import shutil

            shutil.rmtree(config_dir)
            print(f"  ✓ Removed {config_dir}")
            logger.info(f"Removed configuration directory: {config_dir}")
    except Exception as e:
        print(f"  ✗ Failed to remove configuration: {e}")
        logger.error(f"Failed to remove configuration: {e}")

    # Remove credentials from keyring
    print("\nRemoving credentials...")
    try:
        import keyring

        keyring.delete_password("pia-nm", "username")
        keyring.delete_password("pia-nm", "password")
        print("  ✓ Removed credentials from keyring")
        logger.info("Removed credentials from keyring")
    except Exception as e:
        print(f"  ✗ Failed to remove credentials: {e}")
        logger.warning(f"Failed to remove credentials: {e}")

    print("\n" + "=" * 50)
    print("✓ Uninstall Complete")
    print("=" * 50)


def cmd_enable() -> None:
    """Enable the systemd timer."""
    logger = logging.getLogger(__name__)

    try:
        enable_timer()
        print("✓ Systemd timer enabled")
        logger.info("Systemd timer enabled")
    except Exception as e:
        print(f"✗ Failed to enable timer: {e}")
        logger.error(f"Failed to enable timer: {e}")
        sys.exit(1)


def cmd_disable() -> None:
    """Disable the systemd timer."""
    logger = logging.getLogger(__name__)

    try:
        disable_timer()
        print("✓ Systemd timer disabled")
        logger.info("Systemd timer disabled")
    except Exception as e:
        print(f"✗ Failed to disable timer: {e}")
        logger.error(f"Failed to disable timer: {e}")
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

    # Check system dependencies
    if not check_system_dependencies():
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
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
