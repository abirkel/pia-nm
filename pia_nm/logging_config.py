"""Logging configuration for PIA NetworkManager Integration.

This module sets up comprehensive logging with:
- File logging to ~/.local/share/pia-nm/logs/pia-nm.log
- Log rotation (keep last 10 files)
- Console output for user-facing messages
- Proper formatting with timestamp, level, and message
"""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional


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

    # File handler with rotation (keep last 10 files)
    log_file = log_dir / "pia-nm.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB per file
        backupCount=10,  # Keep last 10 files
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Console handler (for user-facing messages)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

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
