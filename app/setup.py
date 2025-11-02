"""Utility functions for ensuring application setup."""

import logging
import os

logger = logging.getLogger(__name__)


def ensure_directory_exists(directory_path: str):
    """Ensure a directory exists"""
    if not os.path.exists(directory_path):
        logger.info(f"Creating directory: {directory_path}")
        os.makedirs(directory_path, exist_ok=True)
    else:
        logger.debug(f"Directory already exists: {directory_path}")


def setup_directories() -> None:
    """Set up all required application directories."""
    logger.info("Setting up application directories")
    ensure_directory_exists("data")
    ensure_directory_exists("log")
    ensure_directory_exists("backups")
    logger.info("Application directories setup completed")
