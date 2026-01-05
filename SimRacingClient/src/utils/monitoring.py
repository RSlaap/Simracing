"""
Centralized logging configuration for SimRacingClient.

This module provides a configured logger that can be easily imported
and used throughout the application.

Usage:
    from utils.monitoring import get_logger

    logger = get_logger(__name__)
    logger.info("This is an info message")
    logger.error("This is an error message")
"""

import logging
import sys
from pathlib import Path
from typing import Optional


# ============================================================================
# Configuration
# ============================================================================

DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ============================================================================
# Logger Setup
# ============================================================================

def setup_logging(
    log_level: int = DEFAULT_LOG_LEVEL,
    log_file: Optional[Path] = None,
    console: bool = True
) -> None:
    """
    Configure the root logger with console and/or file handlers.

    Args:
        log_level: Logging level (e.g., logging.INFO, logging.DEBUG)
        log_file: Optional path to log file. If None, only console logging is used.
        console: Whether to enable console logging (default: True)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    return logging.getLogger(name)


# ============================================================================
# Auto-initialization
# ============================================================================

# Initialize logging on import with default configuration
# This ensures logging works even if setup_logging() is never called
_default_initialized = False

def _ensure_default_logging():
    """Ensure default logging is initialized."""
    global _default_initialized
    if not _default_initialized:
        # Default: console logging only
        setup_logging(console=True)
        _default_initialized = True

_ensure_default_logging()
