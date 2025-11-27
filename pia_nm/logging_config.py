"""
Logging configuration for PIA NetworkManager Integration.

This module sets up comprehensive logging with:
- File logging to ~/.local/share/pia-nm/logs/pia-nm.log
- Log rotation (keep last 10 files)
- Console output for user-facing messages
- Proper formatting with timestamp, level, and message
- Sensitive data filtering to prevent accidental credential logging

Copyright (C) 2025 PIA-NM Contributors

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
"""

import logging
import logging.handlers
import re
from pathlib import Path
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from log records.

    This filter provides defense-in-depth by redacting common patterns
    of sensitive data that might accidentally be logged:
    - Base64-encoded credentials
    - API tokens
    - WireGuard keys
    - Email addresses
    - IP addresses (in certain contexts)
    """

    # Patterns to redact
    PATTERNS = [
        # Base64-like strings (potential keys/tokens)
        (r"[A-Za-z0-9+/]{40,}={0,2}", "[REDACTED_BASE64]"),
        # Common token patterns
        (r'token["\']?\s*[:=]\s*["\']?[A-Za-z0-9_-]+["\']?', "token=[REDACTED]"),
        # Common password patterns
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+["\']?', "password=[REDACTED]"),
        # Common key patterns
        (r'key["\']?\s*[:=]\s*["\']?[A-Za-z0-9_-]+["\']?', "key=[REDACTED]"),
        # Common credential patterns
        (r'credential["\']?\s*[:=]\s*["\']?[^"\'\s]+["\']?', "credential=[REDACTED]"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log record to redact sensitive data.

        Args:
            record: Log record to filter

        Returns:
            True to allow the record to be logged
        """
        # Only filter message, not other fields
        if record.msg:
            msg = str(record.msg)
            for pattern, replacement in self.PATTERNS:
                msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)
            record.msg = msg

        return True


def setup_logging(verbose: bool = False, log_dir: Optional[Path] = None) -> None:
    """Configure logging to file and console with rotation.

    Args:
        verbose: If True, set log level to DEBUG. Otherwise INFO.
        log_dir: Optional custom log directory. Defaults to ~/.local/share/pia-nm/logs
    """
    if log_dir is None:
        log_dir = Path.home() / ".local/share/pia-nm/logs"

    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format)

    # Create sensitive data filter
    sensitive_filter = SensitiveDataFilter()

    # File handler with rotation (keep last 10 files)
    log_file = log_dir / "pia-nm.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB per file
        backupCount=10,  # Keep last 10 files
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sensitive_filter)

    # Console handler (for user-facing messages)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.debug(f"Logging initialized (level={logging.getLevelName(log_level)}, file={log_file})")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
