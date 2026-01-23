"""File operations service for terminal configuration files."""

import logging
from pathlib import Path

from catio_terminals.models import TerminalConfig

logger = logging.getLogger(__name__)


class FileService:
    """Service for handling file operations."""

    @staticmethod
    def open_file(file_path: Path) -> TerminalConfig:
        """Open and load a terminal configuration file.

        Args:
            file_path: Path to YAML file

        Returns:
            TerminalConfig instance

        Raises:
            Exception: If file cannot be opened or parsed
        """
        logger.info(f"Opening file: {file_path}")
        return TerminalConfig.from_yaml(file_path)

    @staticmethod
    def save_file(config: TerminalConfig, file_path: Path) -> None:
        """Save terminal configuration to file.

        Args:
            config: Configuration to save
            file_path: Path to save to

        Raises:
            Exception: If file cannot be saved
        """
        logger.info(f"Saving to: {file_path}")
        config.to_yaml(file_path)

    @staticmethod
    def create_file(file_path: Path) -> TerminalConfig:
        """Create a new empty terminal configuration file.

        Args:
            file_path: Path for new file

        Returns:
            New empty TerminalConfig instance

        Raises:
            Exception: If file cannot be created
        """
        logger.info(f"Creating new file: {file_path}")
        config = TerminalConfig()
        config.to_yaml(file_path)
        return config
