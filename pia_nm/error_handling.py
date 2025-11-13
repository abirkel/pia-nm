"""Error handling and user-friendly error messages for pia-nm.

This module provides:
- Custom exception classes
- Error message templates for common failures
- Troubleshooting guidance
- Consistent error reporting
"""

import logging
import sys
from typing import Optional

logger = logging.getLogger(__name__)


# Custom exception classes
class PIANMError(Exception):
    """Base exception for pia-nm."""


class AuthenticationError(PIANMError):
    """Authentication with PIA failed."""


class NetworkError(PIANMError):
    """Network communication failed."""


class APIError(PIANMError):
    """PIA API returned an error."""


class ConfigError(PIANMError):
    """Configuration file error."""


class NetworkManagerError(PIANMError):
    """NetworkManager operation failed."""


class SystemDependencyError(PIANMError):
    """Required system command not found."""


class WireGuardError(PIANMError):
    """WireGuard operation failed."""


# Error message templates
ERROR_MESSAGES = {
    "auth_invalid_credentials": {
        "title": "Authentication failed: Invalid credentials",
        "message": "Please verify your PIA username and password:",
        "steps": [
            "Visit https://www.privateinternetaccess.com/pages/login",
            "Confirm your credentials are correct",
            "Run: pia-nm setup",
        ],
        "additional": [
            "If you continue to have issues, check:",
            "  - Your PIA subscription is active",
            "  - Network connectivity to PIA servers",
        ],
    },
    "auth_expired_token": {
        "title": "Authentication failed: Token expired",
        "message": "Your authentication token has expired.",
        "steps": [
            "Run: pia-nm refresh",
            "Or run: pia-nm setup to reconfigure",
        ],
    },
    "network_unreachable": {
        "title": "Network error: Unable to reach PIA servers",
        "message": "Please check:",
        "steps": [
            "Your internet connection is active",
            "Firewall settings allow HTTPS traffic",
            "DNS resolution is working",
            "Try again: pia-nm refresh",
        ],
    },
    "network_timeout": {
        "title": "Network error: Connection timeout",
        "message": "PIA servers took too long to respond.",
        "steps": [
            "Check your internet connection",
            "Try again: pia-nm refresh",
            "If problem persists, check PIA status page",
        ],
    },
    "nm_profile_not_found": {
        "title": "NetworkManager error: Profile not found",
        "message": "The VPN profile does not exist in NetworkManager.",
        "steps": [
            "Recreate the profile: pia-nm add-region <region-id>",
            "Or run setup again: pia-nm setup",
        ],
    },
    "nm_operation_failed": {
        "title": "NetworkManager error: Operation failed",
        "message": "Failed to create or update VPN profile.",
        "steps": [
            "Verify NetworkManager is running: systemctl status NetworkManager",
            "Check system logs: journalctl -xe",
            "Try removing and recreating the profile:",
            "  pia-nm remove-region <region-id>",
            "  pia-nm add-region <region-id>",
        ],
    },
    "config_not_found": {
        "title": "Configuration error: Setup not completed",
        "message": "Configuration file not found.",
        "steps": [
            "Run initial setup: pia-nm setup",
            "Follow the interactive prompts",
        ],
    },
    "config_invalid": {
        "title": "Configuration error: Invalid configuration",
        "message": "Configuration file is corrupted or invalid.",
        "steps": [
            "Backup current config: cp ~/.config/pia-nm/config.yaml ~/.config/pia-nm/config.yaml.bak",
            "Run setup again: pia-nm setup",
            "Or manually edit: ~/.config/pia-nm/config.yaml",
        ],
    },
    "keyring_unavailable": {
        "title": "Credential storage error: Keyring unavailable",
        "message": "System keyring is not available.",
        "steps": [
            "Ensure libsecret is installed: sudo dnf install libsecret",
            "Check keyring service: systemctl --user status org.freedesktop.secrets",
            "Try again: pia-nm setup",
        ],
    },
    "wireguard_not_installed": {
        "title": "System dependency error: WireGuard not installed",
        "message": "The 'wg' command is not available.",
        "steps": [
            "Install WireGuard tools: sudo dnf install wireguard-tools",
            "Verify installation: wg --version",
            "Try again: pia-nm setup",
        ],
    },
    "nmcli_not_installed": {
        "title": "System dependency error: NetworkManager not installed",
        "message": "The 'nmcli' command is not available.",
        "steps": [
            "Install NetworkManager: sudo dnf install NetworkManager",
            "Verify installation: nmcli --version",
            "Try again: pia-nm setup",
        ],
    },
    "systemctl_not_installed": {
        "title": "System dependency error: systemd not available",
        "message": "The 'systemctl' command is not available.",
        "steps": [
            "Ensure systemd is installed (usually pre-installed)",
            "Verify installation: systemctl --version",
        ],
    },
    "key_generation_failed": {
        "title": "WireGuard error: Key generation failed",
        "message": "Failed to generate WireGuard keypair.",
        "steps": [
            "Verify WireGuard is installed: wg --version",
            "Check system resources (disk space, memory)",
            "Try again: pia-nm refresh",
        ],
    },
    "key_registration_failed": {
        "title": "API error: Key registration failed",
        "message": "Failed to register WireGuard key with PIA.",
        "steps": [
            "Verify your credentials are correct",
            "Check internet connectivity",
            "Try again: pia-nm refresh",
            "If problem persists, check PIA status page",
        ],
    },
}


def print_error(error_key: str, additional_info: Optional[str] = None) -> None:
    """Print a formatted error message with troubleshooting steps.

    Args:
        error_key: Key from ERROR_MESSAGES dict
        additional_info: Optional additional information to include
    """
    if error_key not in ERROR_MESSAGES:
        print(f"✗ Error: {error_key}")
        if additional_info:
            print(f"  {additional_info}")
        return

    error_info = ERROR_MESSAGES[error_key]

    print(f"\n✗ {error_info['title']}\n")
    print(f"{error_info['message']}")

    if "steps" in error_info:
        print()
        for step in error_info["steps"]:
            print(f"  {step}")

    if "additional" in error_info:
        print()
        for line in error_info["additional"]:
            print(f"  {line}")

    if additional_info:
        print(f"\nDetails: {additional_info}")

    print()


def handle_error(
    exception: Exception,
    context: Optional[str] = None,
    exit_code: int = 1,
) -> None:
    """Handle an exception with logging and user-friendly error message.

    Args:
        exception: The exception that occurred
        context: Optional context about what was being done
        exit_code: Exit code to use if exiting
    """
    error_type = type(exception).__name__
    error_msg = str(exception)

    # Log the error with full context
    if context:
        logger.error(f"{context}: {error_type}: {error_msg}", exc_info=True)
    else:
        logger.error(f"{error_type}: {error_msg}", exc_info=True)

    # Map exception types to error messages
    error_mapping = {
        "AuthenticationError": "auth_invalid_credentials",
        "NetworkError": "network_unreachable",
        "APIError": "key_registration_failed",
        "ConfigError": "config_invalid",
        "NetworkManagerError": "nm_operation_failed",
        "SystemDependencyError": "wireguard_not_installed",
        "WireGuardError": "key_generation_failed",
    }

    error_key = error_mapping.get(error_type, "auth_invalid_credentials")

    # Print user-friendly error message
    print_error(error_key, additional_info=error_msg if error_msg else None)

    # Exit if requested
    if exit_code is not None:
        sys.exit(exit_code)


def log_operation_start(operation: str, details: Optional[str] = None) -> None:
    """Log the start of an operation.

    Args:
        operation: Name of the operation
        details: Optional details about the operation
    """
    if details:
        logger.info("Starting: %s (%s)", operation, details)
    else:
        logger.info("Starting: %s", operation)


def log_operation_success(operation: str, details: Optional[str] = None) -> None:
    """Log successful completion of an operation.

    Args:
        operation: Name of the operation
        details: Optional details about the result
    """
    if details:
        logger.info("Success: %s (%s)", operation, details)
    else:
        logger.info("Success: %s", operation)


def log_operation_failure(operation: str, error: Exception, details: Optional[str] = None) -> None:
    """Log failure of an operation.

    Args:
        operation: Name of the operation
        error: The exception that caused the failure
        details: Optional additional details
    """
    if details:
        logger.error("Failed: %s (%s): %s", operation, details, error)
    else:
        logger.error("Failed: %s: %s", operation, error)


def log_api_operation(operation: str, region: Optional[str] = None) -> None:
    """Log an API operation (without credentials).

    Args:
        operation: Name of the API operation
        region: Optional region being operated on
    """
    if region:
        logger.info("API operation: %s (region=%s)", operation, region)
    else:
        logger.info("API operation: %s", operation)


def log_nm_operation(operation: str, profile: Optional[str] = None) -> None:
    """Log a NetworkManager operation.

    Args:
        operation: Name of the operation
        profile: Optional profile name
    """
    if profile:
        logger.info("NetworkManager: %s (profile=%s)", operation, profile)
    else:
        logger.info("NetworkManager: %s", operation)


def log_file_operation(operation: str, file_path: str, success: bool = True) -> None:
    """Log a file operation.

    Args:
        operation: Name of the operation (read, write, delete, etc.)
        file_path: Path to the file
        success: Whether the operation succeeded
    """
    status = "success" if success else "failed"
    logger.info("File operation: %s %s (%s)", operation, file_path, status)
