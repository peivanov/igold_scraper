"""
Configuration management for igold scraper.
Centralize all configuration values from environment variables with sensible defaults.
"""

import os
import logging
import random
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from igold_scraper.exceptions import ConfigurationError

# Default configuration values
DEFAULT_IGOLD_BASE_URL = "https://igold.bg"
DEFAULT_TAVEX_BASE_URL = "https://tavex.bg"
DEFAULT_DATA_DIR = "data"
DEFAULT_DB_PATH = "data/products.db"
DEFAULT_PRICE_CHANGE_THRESHOLD = 5.0  # percentage

# Load .env file if it exists
_env_path: Path = Path(__file__).resolve().parent.parent.parent / '.env'
if _env_path.exists():
    load_dotenv(_env_path)


@dataclass
class Config:
    """Centralized configuration for the scraper."""

    # ========================================================================
    # Base URLs
    # ========================================================================
    IGOLD_BASE_URL: str = os.getenv('IGOLD_BASE_URL', DEFAULT_IGOLD_BASE_URL)
    TAVEX_BASE_URL: str = os.getenv('TAVEX_BASE_URL', DEFAULT_TAVEX_BASE_URL)

    # ========================================================================
    # Request settings
    # ========================================================================
    REQUEST_TIMEOUT: int = int(os.getenv('REQUEST_TIMEOUT', '30'))

    # ========================================================================
    # Rate limiting / delays
    # ========================================================================
    SCRAPE_DELAY_MIN: float = float(os.getenv('SCRAPE_DELAY_MIN', '1.0'))
    SCRAPE_DELAY_MAX: float = float(os.getenv('SCRAPE_DELAY_MAX', '2.5'))

    # ========================================================================
    # Discord notifications
    # ========================================================================
    DISCORD_WEBHOOK_URL: Optional[str] = os.getenv('DISCORD_WEBHOOK_URL', None)
    DISCORD_ENABLED: bool = os.getenv('DISCORD_ENABLED', 'true').lower() == 'true'

    # ========================================================================
    # Data management
    # ========================================================================
    DATA_DIR: str = os.getenv('DATA_DIR', DEFAULT_DATA_DIR)
    DATA_RETENTION_DAYS: int = int(os.getenv('DATA_RETENTION_DAYS', '180'))

    # ========================================================================
    # Price tracking
    # ========================================================================
    PRICE_CHANGE_THRESHOLD: float = float(
        os.getenv('PRICE_CHANGE_THRESHOLD', str(DEFAULT_PRICE_CHANGE_THRESHOLD))
    )

    # ========================================================================
    # API configuration
    # ========================================================================
    PRECIOUS_METALS_API_BASE: Optional[str] = os.getenv('PRECIOUS_METALS_API_BASE', None)
    PRECIOUS_METALS_API_KEY: Optional[str] = os.getenv('PRECIOUS_METALS_API_KEY', None)

    # ========================================================================
    # Logging
    # ========================================================================
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')

    def __post_init__(self) -> None:
        """Validate configuration values after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values."""
        if self.REQUEST_TIMEOUT <= 0:
            raise ConfigurationError(f"REQUEST_TIMEOUT must be positive, got {self.REQUEST_TIMEOUT}")

        if self.SCRAPE_DELAY_MIN < 0 or self.SCRAPE_DELAY_MAX < 0:
            raise ConfigurationError("Delay values cannot be negative")

        if self.SCRAPE_DELAY_MIN > self.SCRAPE_DELAY_MAX:
            raise ConfigurationError(
                f"SCRAPE_DELAY_MIN ({self.SCRAPE_DELAY_MIN}) cannot exceed "
                f"SCRAPE_DELAY_MAX ({self.SCRAPE_DELAY_MAX})"
            )

        if self.DATA_RETENTION_DAYS <= 0:
            raise ConfigurationError(f"DATA_RETENTION_DAYS must be positive, got {self.DATA_RETENTION_DAYS}")

        if self.PRICE_CHANGE_THRESHOLD < 0:
            raise ConfigurationError(f"PRICE_CHANGE_THRESHOLD cannot be negative, got {self.PRICE_CHANGE_THRESHOLD}")

        if self.LOG_LEVEL not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            raise ConfigurationError(f"Invalid LOG_LEVEL: {self.LOG_LEVEL}")

    def get_random_delay(self) -> float:
        """
        Get a random delay between min and max for rate limiting.

        Returns:
            Random float between SCRAPE_DELAY_MIN and SCRAPE_DELAY_MAX
        """
        return random.uniform(self.SCRAPE_DELAY_MIN, self.SCRAPE_DELAY_MAX)


_config_instance: Optional[Config] = None


def get_config() -> Config:
    """
    Get configuration instance (singleton).

    Returns:
        Config dataclass with all settings
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def configure_logging():
    """Configure Python logging based on config settings."""
    config = get_config()
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


if __name__ == '__main__':
    pass
