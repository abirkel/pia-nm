#!/usr/bin/env python3
"""
Test script for the connection notification dispatcher.

This script demonstrates how to install, check status, and uninstall
the notification dispatcher script.
"""

from pia_nm.dispatcher import (
    install_notify_script,
    uninstall_notify_script,
    is_notify_script_installed,
    get_notify_script_status,
)


def main():
    print("=" * 60)
    print("PIA NetworkManager Connection Notification Dispatcher")
    print("=" * 60)
    print()

    # Check current status
    print("Current Status:")
    print("-" * 60)
    installed = is_notify_script_installed()
    print(f"Installed: {installed}")

    status = get_notify_script_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    print()

    # Offer to install if not installed
    if not installed:
        print("The notification dispatcher script is not installed.")
        response = input("Would you like to install it? (y/n): ").strip().lower()

        if response == "y":
            print("\nInstalling notification dispatcher script...")
            print("(This requires sudo privileges)")

            success = install_notify_script()

            if success:
                print("✓ Installation successful!")
                print()
                print("The script will now:")
                print("  - Monitor WireGuard handshake completion")
                print("  - Send desktop notifications when VPN is ready")
                print("  - Log to /var/log/pia-nm-notify.log")
                print()
                print("Try connecting to a PIA VPN to see it in action!")
            else:
                print("✗ Installation failed. Check logs for details.")
        else:
            print("Installation cancelled.")
    else:
        print("The notification dispatcher script is already installed.")
        response = input("Would you like to uninstall it? (y/n): ").strip().lower()

        if response == "y":
            print("\nUninstalling notification dispatcher script...")

            success = uninstall_notify_script()

            if success:
                print("✓ Uninstallation successful!")
            else:
                print("✗ Uninstallation failed. Check logs for details.")
        else:
            print("Uninstallation cancelled.")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
